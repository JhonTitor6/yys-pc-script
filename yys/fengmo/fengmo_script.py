"""独立逢魔流程，复用通用结算与领奖，按返回、to_home 顺序回庭院。"""

from __future__ import annotations

import time
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Callable, TypedDict, get_type_hints

import cv2
import numpy as np

from win_util.environment.base import GameEnvironment
from win_util.environment.guarded import GuardedEnvironment, RunGuard
from win_util.environment.windows import WindowsEnvironment
from win_util.image import to_project_path
from yys.common.event_script_base import (
    BATTLE_END_SUCCESS_IMAGES, BATTLE_END_LOSS_IMAGES, BATTLE_END_OTHER_IMAGES,
    OCR_CLICK_SCREEN_CONTINUE, YYSBaseScript, _extract_config_meta,
)
from yys.common.script_meta import ConfigMeta, ScriptMeta


class FengmoConfig(TypedDict, total=False):
    """预设名称按既有阵容切换器完整匹配。"""

    lineup_group: Annotated[str, ConfigMeta(default="逢魔", label="阵容分组")]
    lineup_name: Annotated[str, ConfigMeta(default="通用", label="阵容预设")]


class _Stopped(Exception):
    """用户停止或已规划观察动作。"""


class FengmoScript(YYSBaseScript):
    """应用预设、探索、等待首领战斗，清理通用结算后返回庭院。"""

    SCRIPT_META = ScriptMeta("逢魔", "日常", FengmoConfig,
                             {"lineup_group": "逢魔", "lineup_name": "通用"})
    SIZE = (1138, 641)
    REWARD_IMAGE = "yys/common_challenge/images/gained_reward.bmp"
    BATTLE_IMAGE = "yys/common/images/scene/battling.bmp"
    RETURN_IMAGE = "yys/common/images/scene_control/return.bmp"
    HOME_IMAGE = "yys/common/images/scene_control/to_home.bmp"

    @classmethod
    def get_config_schema(cls) -> list[dict[str, object]]:
        """从类内元数据公开两个预设名称字段，供现有脚本列表和配置表单使用。"""
        return [{"key": key, **asdict(meta)} for key, value in
                get_type_hints(FengmoConfig, include_extras=True).items()
                if (meta := _extract_config_meta(value)) is not None]

    def __init__(
        self, script_name: str = "fengmo", config: dict | None = None,
        env: GameEnvironment | None = None,
    ) -> None:
        """所有真实输入通过注入环境，等待集结与战斗也受总超时限制。"""
        actual = env if env is not None else WindowsEnvironment()
        guard = actual.guard if isinstance(actual, GuardedEnvironment) else RunGuard(
            timeout_seconds=600, max_actions=60, unknown_limit=3,
        )
        guarded = actual if isinstance(actual, GuardedEnvironment) else GuardedEnvironment(
            actual, guard, observe_only=False,
        )
        super().__init__(script_name, config=config, env=guarded)
        self.max_battle_count = 1
        self.set_run_guard(guard)
        self._images = Path(to_project_path("yys/fengmo/images"))
        self._size = self.SIZE
        self._stage = "initial"
        self._settlement_seen = False
        self._victory_seen = False

    def on_run(self) -> None:
        """重置独立逢魔状态，不运行狭间暗域业务。"""
        super().on_run()
        self._stage = "initial"
        self._settlement_seen = False
        self._victory_seen = False

    def get_state_snapshot(self) -> dict[str, object]:
        """只有结算清理和两步返回完成后才公开完整完成。"""
        return {**super().get_state_snapshot(), "stage": self._stage,
                "flow_complete": self._stage == "done"}

    def run(self) -> None:
        """运行独立逢魔流程，支持从已进入的集结页继续等待。"""
        self.on_run()
        try:
            frame = self._read()
            if self._match(frame, "lobby") is not None:
                if self._env.observe_only:
                    self._stage = "observing"
                else:
                    self._finish_battle_and_return()
                return
            if self._env.observe_only:
                for name in ("daily_entry", "entry", "explore", "assemble"):
                    point = self._match(frame, name)
                    if point is not None:
                        self._click(point)
                raise RuntimeError("[FENGMO_UNKNOWN] 当前页没有已核验的观察动作")
            if self._match(frame, "home") is None:
                raise RuntimeError("[FENGMO_ENTRY] 请从庭院启动逢魔")
            self._stage = "lineup"
            self.switch_lineup(self.lineup_group, self.lineup_name, home_verified=True)
            self._check()
            self._env.key_press(27)
            frame = self._wait(lambda f: self._match(f, "home") is not None)
            self._click(self._required(frame, "daily_entry"))
            frame = self._wait(lambda f: self._match(f, "daily_panel") is not None)
            self._click(self._required(frame, "entry"))
            frame = self._wait(lambda f: self._match(f, "map") is not None)
            self._stage = "exploring"
            if self._remaining(frame) > 0:
                x, y = self._required(frame, "explore")
                self._click((x, y - 52))
                frame = self._wait(lambda f: self._match(f, "map") is not None
                                   and self._remaining(f) == 0)
            claim = self._match(frame, "claim")
            if claim is not None:
                self._click(claim)
                self._wait(lambda f: self._match(f, "reward") is not None)
                self._click((943, 440))
                frame = self._wait(lambda f: self._match(f, "map") is not None)
            self._stage = "searching_boss"
            x, y = self._required(frame, "search")
            self._click((x, y - 40))
            frame = self._wait(lambda f: self._match(f, "map") is not None
                               and self._match(f, "boss") is not None
                               and not self.ocr.contains_text(f[185:235, 400:760], "正在替您搜索"))
            self._click(self._required(frame, "boss"))
            frame = self._wait(lambda f: self._match(f, "detail") is not None)
            self._click(self._required(frame, "assemble"))
            self._wait(lambda f: self._match(f, "lobby") is not None)
            self._finish_battle_and_return()
        except _Stopped:
            return
        except Exception:
            self._stage = "failed"
            raise

    def bg_left_click(self, point: tuple, x_range: int = 20, y_range: int = 20) -> None:
        """将通用结算回调的点击接入本脚本坐标换算、停止检查和保险丝。"""
        self._click(point)

    def _should_count_battle_end(self, _point: tuple[int, int]) -> bool:
        """本脚本统一单次计数，通用奖励回调不重复累计。"""
        return False

    def _shared_match(self, frame: np.ndarray, path: str) -> tuple[int, int] | None:
        point = self.image_finder.bg_find_pic(frame, path)
        return point if point is not None and point != (-1, -1) else None

    def _settlement(self, frame: np.ndarray) -> tuple[str, tuple[int, int]] | None:
        for kind, paths in (("victory", BATTLE_END_SUCCESS_IMAGES),
                            ("other", BATTLE_END_LOSS_IMAGES + BATTLE_END_OTHER_IMAGES),
                            ("reward", [self.REWARD_IMAGE])):
            for path in paths:
                point = self._shared_match(frame, path)
                if point is not None:
                    return kind, point
        reward = self._match(frame, "reward")
        if reward is not None:
            return "reward", reward
        for x, y, text, _ in self.ocr.find_all_text_positions(frame[400:641], 0.90):
            if "".join(text.split()) == OCR_CLICK_SCREEN_CONTINUE:
                return "continue", (x, y + 400)
        return None

    def _consume_settlement(self, kind: str, point: tuple[int, int]) -> None:
        """复用父类结算操作，首次结算计一场，重复结算继续清理但不重复计数。"""
        self._stage = "settlement"
        if kind == "victory":
            if self._victory_seen:
                self._click(point)
            else:
                super()._on_battle_victory(point)
                self._victory_seen = True
        elif kind == "continue":
            super()._on_ocr_click_screen_continue(point)
        else:
            # 通用挑战也在奖励页点击右侧空白位置，避免点击奖励图标。
            super()._on_battle_end((960, 535) if kind == "reward" else point)
        if not self._settlement_seen:
            self._cur_battle_count = 1
            self._log_battle_count()
        self._settlement_seen = True

    def _finish_battle_and_return(self) -> None:
        self._stage = "waiting_battle"
        while True:
            frame = self._read()
            result = self._settlement(frame)
            if result is not None:
                self._consume_settlement(*result)
                continue
            lobby = self._match(frame, "lobby") is not None
            battle = not lobby and self._shared_match(frame, self.BATTLE_IMAGE) is not None
            if self._settlement_seen and not battle:
                self._return_home()
                self._stage = "done"
                return
            known = battle or lobby
            if self._run_guard is not None:
                self._run_guard.note_iteration(known)
            self._stage = "battle" if battle else "waiting_battle"
            self._stop_threading_event.wait(0.2)

    def _return_home(self) -> None:
        """严格先返回、再重新识别 to_home，庭院确认后才能完成。"""
        self._stage = "returning_home"
        for path in (self.RETURN_IMAGE, self.HOME_IMAGE):
            frame = self._wait(lambda f: self._settlement(f) is None
                               and (self._match(f, "lobby") is not None
                                    or self._shared_match(f, self.BATTLE_IMAGE) is None)
                               and self._navigation_point(f, path) is not None)
            point = self._navigation_point(frame, path)
            if point is None:
                raise RuntimeError("[FENGMO_RETURN] 返回控件已消失")
            self._click(point)
            self._stop_threading_event.wait(0.25)
        self._wait(lambda f: self._match(f, "home") is not None)

    def _navigation_point(self, frame: np.ndarray, path: str) -> tuple[int, int] | None:
        point = self._shared_match(frame, path)
        if point is None and path == self.RETURN_IMAGE and self._settlement_seen:
            if self._match(frame, "lobby") is not None:
                return self._match(frame, "lobby_return")
        return point

    def _check(self) -> None:
        self.pause_point()
        if self._stop_threading_event.is_set():
            self._stage = "stopped"
            raise _Stopped()
        if self._run_guard is not None and not self._run_guard.before_iteration():
            raise RuntimeError("[FENGMO_GUARD] 逢魔保险丝已停止")

    def _read(self) -> np.ndarray:
        self._check()
        image = self._env.capture_screen().convert("RGB")
        self._size = image.size
        if image.width < 500 or abs(image.width / image.height - self.SIZE[0] / self.SIZE[1]) > 0.03:
            raise RuntimeError("[FENGMO_CAPTURE] 客户区尺寸或比例未校准")
        frame = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        self.image_finder.screenshot_cache = frame
        return cv2.resize(frame, self.SIZE)

    def _click(self, point: tuple[int, int]) -> None:
        self._check()
        x, y = point
        self._env.left_click(round(x * self._size[0] / self.SIZE[0]),
                             round(y * self._size[1] / self.SIZE[1]))
        if self._run_guard is not None:
            self._run_guard.allow_unknown_for(8)
        if self._env.observe_only:
            self._stage = "observing"
            raise _Stopped()

    def _match(self, frame: np.ndarray, name: str) -> tuple[int, int] | None:
        path = self._images / f"{name}.png"
        result = self.image_finder.best_match(frame, str(path))
        if result.similarity < 0.92:
            return None
        template = cv2.imread(str(path))
        h, w = template.shape[:2]
        x, y = result.point
        patch = frame[y - h // 2:y - h // 2 + h, x - w // 2:x - w // 2 + w]
        if patch.shape != template.shape or float(cv2.absdiff(patch, template).mean()) > 22:
            return None
        return result.point

    def _required(self, frame: np.ndarray, name: str) -> tuple[int, int]:
        point = self._match(frame, name)
        if point is None:
            raise RuntimeError(f"[FENGMO_TARGET] 未确认逢魔控件：{name}")
        return point

    def _wait(self, predicate: Callable[[np.ndarray], bool]) -> np.ndarray:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            frame = self._read()
            known = predicate(frame)
            if self._run_guard is not None:
                self._run_guard.note_iteration(known)
            if known:
                return frame
            self._stop_threading_event.wait(0.2)
        raise RuntimeError("[FENGMO_TRANSITION] 逢魔转场未确认，未重复输入")

    def _remaining(self, frame: np.ndarray) -> int:
        if self._match(frame, "map") is None:
            raise RuntimeError("[FENGMO_MAP] 未确认逢魔地图")
        # 倾斜数字紧贴窗口底边，真实帧 OCR 会拆成多个字；用已录数字模板校验。
        area = frame[600:641, 1060:1138]
        values = [value for value, marker in ((4, "explore_available"), (0, "explore_empty"))
                  if self._match(area, marker) is not None]
        if len(values) != 1:
            raise RuntimeError("[FENGMO_COUNT] 现世逢魔次数无法可靠识别")
        return values[0]
