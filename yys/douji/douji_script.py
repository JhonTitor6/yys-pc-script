from __future__ import annotations

import time
from typing import Annotated, Any, Optional, TYPE_CHECKING, TypedDict, get_type_hints

import cv2
import numpy as np

from yys.common.event_script_base import YYSBaseScript, ImageMatchConfig, _extract_config_meta, random_sleep
from yys.common.script_meta import ConfigMeta, ScriptMeta

if TYPE_CHECKING:
    from tests.common.environment.base import GameEnvironment


_DOUJI_SLOT_CLICK_OFFSETS: tuple[tuple[int, int], ...] = (
    (10, 70),
    (8, 60),
    (-8, -55),
    (3, 110),
    (-28, 70),
)


def _find_douji_bar_candidates(frame: np.ndarray) -> list[tuple[int, int, int]]:
    """从战斗画面中找出横向血条候选，返回中心点和宽度。"""
    if frame.ndim != 3 or frame.shape[2] != 3:
        return []

    height, width = frame.shape[:2]
    scale_x = width / 1136
    scale_y = height / 640
    y_start = max(0, int(220 * scale_y))
    y_end = min(height, int(500 * scale_y))
    if y_start >= y_end:
        return []

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # ponytail：当前依赖金色血条色相；主题颜色变化时再升级为模板与几何双重锚点。
    mask = cv2.inRange(
        hsv,
        np.array([10, 60, 80], dtype=np.uint8),
        np.array([45, 255, 255], dtype=np.uint8),
    ) > 0
    min_width = max(35, int(35 * scale_x))
    max_width = int(105 * scale_x)
    runs: list[tuple[int, int, int]] = []

    for y in range(y_start, y_end):
        row = mask[y]
        changes = np.diff(np.r_[False, row, False].astype(np.int8))
        starts = np.where(changes == 1)[0]
        ends = np.where(changes == -1)[0]
        for start, end in zip(starts, ends):
            if min_width <= end - start <= max_width:
                runs.append((int(start), int(end), y))

    groups: list[list[tuple[int, int, int]]] = []
    for run in runs:
        start, end, y = run
        matches: list[tuple[int, int]] = []
        for index, group in enumerate(groups):
            last_start, last_end, last_y = group[-1]
            if y - last_y > 2:
                continue
            overlap = min(end, last_end) - max(start, last_start)
            required_overlap = 0.5 * min(end - start, last_end - last_start)
            if overlap >= required_overlap:
                matches.append((overlap, index))
        if matches:
            _, group_index = max(matches)
            groups[group_index].append(run)
        else:
            groups.append([run])

    candidates: list[tuple[int, int, int]] = []
    for group in groups:
        if len(group) < 3:
            continue
        x0 = min(run[0] for run in group)
        x1 = max(run[1] for run in group)
        y0 = min(run[2] for run in group)
        y1 = max(run[2] for run in group)
        candidate_width = x1 - x0
        candidate_height = y1 - y0 + 1
        if candidate_width < min_width or candidate_width > max_width:
            continue
        if not 3 <= candidate_height <= 10:
            continue
        candidates.append(((x0 + x1) // 2, (y0 + y1) // 2, candidate_width))
    return candidates


def _find_douji_slot_anchors(frame: np.ndarray) -> Optional[list[tuple[int, int]]]:
    """按从左到右顺序返回己方五个槽位的血条锚点。"""
    height, width = frame.shape[:2]
    scale_x = width / 1136
    scale_y = height / 640
    min_bar_width = max(50, int(50 * scale_x))
    max_bar_y = int(450 * scale_y)
    candidates = [
        candidate
        for candidate in _find_douji_bar_candidates(frame)
        if candidate[2] >= min_bar_width and candidate[1] <= max_bar_y
    ]
    candidates.sort(key=lambda candidate: candidate[0])

    clusters: list[list[tuple[int, int, int]]] = []
    cluster_gap = int(80 * scale_x)
    for candidate in candidates:
        if clusters and candidate[0] - clusters[-1][-1][0] <= cluster_gap:
            clusters[-1].append(candidate)
        else:
            clusters.append([candidate])

    if len(clusters) != 5:
        return None

    anchors: list[tuple[int, int]] = []
    for index, cluster in enumerate(clusters):
        # 中间槽位可能同时命中对手和己方血条，己方血条位于更下方。
        if index == 2:
            selected = max(cluster, key=lambda candidate: candidate[1])
        else:
            selected = min(cluster, key=lambda candidate: candidate[1])
        anchors.append((selected[0], selected[1]))

    min_spacing = int(100 * scale_x)
    if any(right[0] - left[0] < min_spacing for left, right in zip(anchors, anchors[1:])):
        return None
    return anchors


def _find_douji_slot_point(frame: np.ndarray, slot: int) -> Optional[tuple[int, int]]:
    """根据己方槽位编号返回客户区点击点，槽位编号从一开始。"""
    if not 1 <= slot <= 5:
        raise ValueError(f"斗技己方槽位必须在 1-5 之间: {slot}")

    anchors = _find_douji_slot_anchors(frame)
    if anchors is None:
        return None

    height, width = frame.shape[:2]
    scale_x = width / 1136
    scale_y = height / 640
    anchor_x, anchor_y = anchors[slot - 1]
    offset_x, offset_y = _DOUJI_SLOT_CLICK_OFFSETS[slot - 1]
    return (
        round(anchor_x + offset_x * scale_x),
        round(anchor_y + offset_y * scale_y),
    )


class DouJiConfig(TypedDict, total=False):
    """斗技脚本的可配置字段。"""
    max_battle_count: Annotated[int, ConfigMeta(
        default=30,
        min_value=1,
        max_value=999,
        field_type="number",
        label="最大战斗次数",
        group="基础",
        help="脚本自动停止前执行的最大战斗次数（1-999）",
        hot_reloadable=True,
    )]
    target_slot: Annotated[int, ConfigMeta(
        default=2,
        min_value=1,
        max_value=5,
        field_type="number",
        label="己方目标槽位",
        group="战斗",
        help="斗技中从左到右选择己方第几个式神（1-5）",
        hot_reloadable=True,
    )]


class DouJi(YYSBaseScript):
    """
    斗技挂机
    """
    SCRIPT_META = ScriptMeta(
        display_name="斗技",
        category="日常",
        config_schema=DouJiConfig,
        default_config={"max_battle_count": 30, "target_slot": 2},
    )

    @classmethod
    def get_config_schema(cls) -> list[dict[str, Any]]:
        """从 SCRIPT_META 反射 config_schema 为 wire format list of dict。"""
        meta = cls.SCRIPT_META
        if meta is None or meta.config_schema is None:
            return []
        try:
            hints = get_type_hints(meta.config_schema, include_extras=True)
        except Exception:
            hints = {}
        result: list[dict[str, Any]] = []
        for field_name, annotated_type in hints.items():
            config_meta = _extract_config_meta(annotated_type)
            if config_meta is None:
                continue
            result.append({
                "key": field_name,
                "label": config_meta.label or field_name,
                "field_type": config_meta.field_type,
                "default": config_meta.default,
                "min_value": config_meta.min_value,
                "max_value": config_meta.max_value,
                "options": list(config_meta.options or []),
                "hot_reloadable": config_meta.hot_reloadable,
                "description": config_meta.help,
                "unit": config_meta.unit,
                "sensitive": config_meta.sensitive,
            })
        return result

    def __init__(
        self,
        script_name: str = "douji",
        env: Optional["GameEnvironment"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """初始化斗技脚本。

        Args:
            script_name: 脚本名，默认 "douji"。
            env: GameEnvironment 实例，用于 Mock 测试时注入。
            config: 配置字典（可选）。
        """
        super().__init__(script_name, config=config, env=env)
        self._douji_target_pending = False
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/douji_zhan.bmp", similarity=0.7), self._on_douji_zhan)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/change_to_auto_battle.bmp"), self._on_change_to_auto_battle)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/douji_selection_auto_up.bmp", similarity=0.7),
                                         self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/douji_battle_end.bmp"), self._on_battle_end)
        self._register_image_match_event(ImageMatchConfig("yys/images/battle_end_loss.bmp"), self._on_battle_end)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/douji_battle_end_victory.bmp", similarity=0.6),
                                         self._on_battle_victory)
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_close.bmp", similarity=0.7), self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/images/ready.bmp", similarity=0.7), self.bg_left_click)

    def _on_battle_victory(self, point):
        """战斗胜利处理"""
        self._douji_target_pending = False
        self.bg_left_click(point)
        self._cur_battle_victory_count += 1
        time.sleep(1.0)

    def _on_battle_end(self, point):
        """战斗结束（失败/奖励）处理"""
        self._douji_target_pending = False
        time.sleep(2.0)
        self.bg_left_click(point, x_range=30, y_range=50)
        self._cur_battle_count += 1
        self._log_battle_count()
        time.sleep(0.5)

    def _on_douji_zhan(self, point):
        self.bg_left_click(point)

    def _try_click_douji_target(self, *, refresh: bool) -> bool:
        """尝试从当前截图定位并点击己方目标槽位。"""
        if self.image_finder is None:
            return False
        if refresh:
            self.image_finder.update_screenshot_cache()
        frame = self.image_finder.screenshot_cache
        if frame is None:
            return False
        target_point = _find_douji_slot_point(frame, self.target_slot)
        if target_point is None:
            return False
        self.logger.debug(f"斗技己方左{self.target_slot}点击坐标: {target_point}")
        self.bg_left_click(target_point, x_range=0, y_range=0)
        return True

    def _log_douji_target_failure(self) -> None:
        """记录定位失败时的截图和候选信息，不执行兜底点击。"""
        frame = self.image_finder.screenshot_cache if self.image_finder is not None else None
        frame_shape = frame.shape if frame is not None else None
        candidates = _find_douji_bar_candidates(frame) if frame is not None else []
        self.logger.warning(
            f"斗技己方左{self.target_slot}暂未定位，继续等待："
            f"截图尺寸={frame_shape}，候选血条={candidates}"
        )

    def _on_change_to_auto_battle(self, point: tuple[int, int]) -> None:
        self._douji_target_pending = False
        self.bg_left_click(point)
        random_sleep(3, 4)
        for _ in range(5):
            if self._try_click_douji_target(refresh=True):
                return
            time.sleep(0.2)

        self._douji_target_pending = True
        self._log_douji_target_failure()

    def after_iteration(self) -> None:
        """在战斗画面晚于自动战斗按钮出现时继续尝试定位。"""
        if self._douji_target_pending and self._try_click_douji_target(refresh=False):
            self._douji_target_pending = False
            self.logger.info(f"斗技己方左{self.target_slot}延迟定位成功")
        super().after_iteration()

    def on_run(self):
        """脚本启动钩子（实现抽象基类要求）"""
        super().on_run()


if __name__ == '__main__':
    DouJi().run()
