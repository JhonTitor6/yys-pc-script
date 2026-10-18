"""单人魂土入口、挑战与安全返回流程。"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, TypedDict, get_type_hints

import cv2
import numpy as np

from win_util.environment import GameEnvironment, GuardedEnvironment, RunGuard, WindowsEnvironment
from win_util.image import ImageMatchConfig, to_project_path
from yys.common.event_script_base import (
    BATTLE_END_LOSS_IMAGES,
    BATTLE_END_OTHER_IMAGES,
    BATTLE_END_SUCCESS_IMAGES,
    YYSBaseScript,
    _extract_config_meta,
)
from yys.common.lineup import LineupSwitcher
from yys.common.script_meta import ConfigMeta, ScriptMeta

_HOME = "yys/common/images/scene/home.bmp"
_HOME_SAKURA = "yys/common/images/scene/home/home_sakura_lantern.png"
_EXPLORATION = "yys/common/images/scene/exploration.bmp"
_BATTLE = "yys/common/images/scene/battling.bmp"
_PRESET_PANEL = "yys/common/images/lineup/preset_panel.png"
_PRESET_PANEL_NAMED = "yys/common/images/lineup/preset_panel_named.png"
_HOME_TO_EXPLORATION = "yys/common/images/scene_control/home_to_exploration.bmp"
_EXPLORATION_TO_SOUL = "yys/common/images/scene_control/exploration_to_soul.bmp"
_RETURN = "yys/common/images/scene_control/return.bmp"
_TO_HOME = "yys/common/images/scene_control/to_home.bmp"
_REWARD = "yys/common_challenge/images/gained_reward.bmp"
_IMAGE_DIR = "yys/soul_soil/images"
_TEMPLATES = (
    "yuhun_mode_card.png",
    "soul_stage_title.png",
    "solo_lobby_ready.png",
    "lobby_selected_row.png",
    "treasure_title.png",
)
_SIZE = (1136, 640)


class SoulSoilConfig(TypedDict, total=False):
    """单人魂土配置。"""

    max_battle_count: Annotated[int, ConfigMeta(
        default=10, min_value=1, max_value=999, field_type="number",
        label="最大战斗次数", group="基础", help="完成后自动停止的魂土场数（1-999）",
    )]
    lineup_group: Annotated[str, ConfigMeta(
        default="御魂", field_type="text", label="阵容分组", group="阵容",
        help="式神录与单人准备页使用的阵容分组",
    )]
    lineup_name: Annotated[str, ConfigMeta(
        default="魂土", field_type="text", label="阵容名称", group="阵容",
        help="应用后出战的魂土阵容",
    )]


class _Stopped(Exception):
    """脚本收到用户停止请求。"""


class SoulSoilScript(YYSBaseScript):
    """从庭院进入单人魂土，按配置完成指定场数并返回庭院。"""

    SCRIPT_META = ScriptMeta(
        display_name="单人魂土",
        category="日常",
        config_schema=SoulSoilConfig,
        default_config={
            "max_battle_count": 10,
            "lineup_group": "御魂",
            "lineup_name": "魂土",
        },
    )

    @classmethod
    def get_config_schema(cls) -> list[dict[str, Any]]:
        """从脚本元数据反射配置表单字段。"""
        result = []
        for name, value in get_type_hints(SoulSoilConfig, include_extras=True).items():
            meta = _extract_config_meta(value)
            if meta is not None:
                result.append({
                    "key": name, "label": meta.label or name, "field_type": meta.field_type,
                    "default": meta.default, "min_value": meta.min_value, "max_value": meta.max_value,
                    "options": list(meta.options or []), "hot_reloadable": meta.hot_reloadable,
                    "description": meta.help, "unit": meta.unit, "sensitive": meta.sensitive,
                })
        return result

    def __init__(
        self,
        script_name: str = "soul_soil",
        config: dict[str, Any] | None = None,
        env: GameEnvironment | None = None,
    ) -> None:
        """初始化脚本、环境保险丝与真实页面标记。"""
        requested = 10 if config is None else config.get("max_battle_count", 10)
        if type(requested) is not int or not 1 <= requested <= 999:
            raise ValueError("max_battle_count 必须是 1 到 999 的整数")
        actual = env if env is not None else WindowsEnvironment()
        guard = actual.guard if isinstance(actual, GuardedEnvironment) else RunGuard(
            timeout_seconds=180 + 180 * requested,
            max_actions=20 + 25 * requested,
            unknown_limit=3,
        )
        guarded = actual if isinstance(actual, GuardedEnvironment) else GuardedEnvironment(
            actual, guard, observe_only=False,
        )
        super().__init__(script_name, config=config, env=guarded)
        self.set_run_guard(guard)
        self._env = guarded
        self._run_guard = guard
        self._size = _SIZE
        self._stage = "idle"
        self._battle_started = False
        self._battle_counted = False
        self._victory_seen = False
        self._treasure_clicked = False
        self._last_triggered_event: str | None = None
        self._templates: dict[str, str] = {}
        for name in _TEMPLATES:
            path = Path(to_project_path(f"{_IMAGE_DIR}/{name}"))
            data = np.fromfile(path, dtype=np.uint8) if path.is_file() else np.array([], dtype=np.uint8)
            image = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
            if image is None or image.size == 0 or float(image.std()) < 1:
                raise ValueError(f"单人魂土模板无效：{path}")
            self._templates[name.removesuffix(".png")] = str(path)
        for path in (_HOME, _HOME_SAKURA, _EXPLORATION, _BATTLE,
                     _PRESET_PANEL, _PRESET_PANEL_NAMED):
            self._register_image_match_event(ImageMatchConfig(path), self._mark_known)
        for name in _TEMPLATES:
            self._register_image_match_event(
                ImageMatchConfig(f"{_IMAGE_DIR}/{name}"),
                self._on_treasure if name == "treasure_title.png" else self._mark_known,
            )
        self._register_image_match_event(ImageMatchConfig(_REWARD), self._on_gained_reward)

    def _mark_known(self, _point: tuple[int, int]) -> None:
        """将已核验页面注册为保险丝可识别状态。"""

    def on_run(self) -> None:
        """重置本次运行的计数和页面状态。"""
        super().on_run()
        self._stage = "starting"
        self._battle_started = False
        self._battle_counted = False
        self._victory_seen = False
        self._treasure_clicked = False
        self._last_triggered_event = None

    def get_state_snapshot(self) -> dict[str, object]:
        """暴露阶段和完整完成态，停止/观察不能被误记为完成。"""
        return {**super().get_state_snapshot(), "stage": self._stage,
                "flow_complete": self._stage == "done"}

    def run(self) -> None:
        """执行指定场数；每场结束都经识别控件返回庭院。"""
        self.on_run()
        try:
            frame = self._read()
            if self._env.observe_only:
                self._stage = "observing"
                if not self._is_home(frame):
                    raise RuntimeError("[SOUL_SOIL_ENTRY] 观察模式下无法确认庭院")
                raise RuntimeError("[SOUL_SOIL_OBSERVE] 观察模式未执行魂土流程")
            if not self._is_home(frame):
                raise RuntimeError("[SOUL_SOIL_ENTRY] 请从已识别的庭院启动单人魂土")
            self._stage = "lineup"
            LineupSwitcher(
                self._env,
                ocr=self.ocr,
                checkpoint=self._check,
            ).switch(self.lineup_group, self.lineup_name, home_verified=True)
            self._return_to_home(from_lineup=True)

            while self._can_start_next_battle():
                expected_count = self._cur_battle_count + 1
                self._battle_started = False
                self._battle_counted = False
                self._victory_seen = False
                self._treasure_clicked = False
                self._stage = "entering_soul_soil"
                self._open_solo_lobby()
                self._start_battle()
                self._wait_battle_end()
                self._return_to_home()
                if self._cur_battle_count != expected_count:
                    raise RuntimeError("[SOUL_SOIL_COUNT] 当前挑战未确认结算，停止后续挑战")
            self._check()
            if self._cur_battle_count != self.max_battle_count:
                raise RuntimeError("[SOUL_SOIL_COUNT] 未达到配置次数，不能报告完成")
            self._stage = "done"
        except _Stopped:
            self._stage = "stopped"
        except RuntimeError as exc:
            self._stage = "observing" if str(exc).startswith("[SOUL_SOIL_OBSERVE]") else "failed"
            raise
        except Exception:
            self._stage = "failed"
            raise
        finally:
            self._stop_threading_event.clear()

    def _can_start_next_battle(self) -> bool:
        """达到目标次数或收到停止后不再发起挑战。"""
        return (
            self._cur_battle_count < self.max_battle_count
            and not self._stop_threading_event.is_set()
        )

    def _open_solo_lobby(self) -> None:
        """按页面证据进入悲鸣并选择单人挑战。"""
        frame = self._read()
        if not self._is_home(frame):
            raise RuntimeError("[SOUL_SOIL_ENTRY] 进入探索前庭院状态丢失")
        lantern = self._match_shared(frame, _HOME_SAKURA)
        if lantern is not None:
            self._click(lantern)
        else:
            self._click_shared(frame, _HOME_TO_EXPLORATION, "庭院探索入口")
        frame = self._wait_for(self._is_exploration, "探索地图未确认")
        self._click_shared(frame, _EXPLORATION_TO_SOUL, "探索地图御魂入口")
        frame = self._wait_for(self._is_soul_modes, "御魂模式页未确认")
        point = self._match(frame, "yuhun_mode_card")
        if point is None:
            raise RuntimeError("[SOUL_SOIL_MODE] 未识别八岐大蛇模式卡")
        self._click(point)
        frame = self._wait_for(self._is_soul_stage, "八岐大蛇关卡页未确认")
        if not self._is_soul_soil_selected(frame):
            point = self._soul_soil_label(frame)
            if point is None:
                raise RuntimeError("[SOUL_SOIL_LEVEL] 未识别悲鸣选层")
            self._click(point)
            frame = self._wait_for(self._is_soul_soil_selected, "悲鸣选层未确认")
        team = self._unique_text(frame, "组队", (790, 500, 980, 610))
        challenge = self._unique_text(frame, "挑战", (980, 500, 1136, 610))
        if team is None or challenge is None:
            raise RuntimeError("[SOUL_SOIL_MODE] 未同时识别单人挑战与组队按钮")
        self._click(challenge)
        self._stage = "preparing"
        self._wait_for(self._is_lobby, "单人挑战准备页未确认")

    def _start_battle(self) -> None:
        """在单人准备页应用配置队伍并开始一次挑战。"""
        frame = self._read()
        if not self._is_lobby(frame):
            raise RuntimeError("[SOUL_SOIL_LOBBY] 当前不是可准备的单人页面")
        if not self._is_lobby_preset(frame):
            preset = self._unique_text(frame, "预设", (0, 555, 120, 640))
            if preset is None:
                raise RuntimeError("[SOUL_SOIL_LOBBY] 未识别队伍预设入口")
            self._click(preset)
            frame = self._wait_for(self._is_lobby_preset, "队伍预设面板未打开")
        group_point = self._unique_text(frame, self.lineup_group, (20, 190, 160, 610))
        if group_point is None:
            raise RuntimeError(f"[SOUL_SOIL_LINEUP] 未找到阵容分组：{self.lineup_group}")
        if not self._lobby_group_selected(frame, group_point):
            self._click(group_point)
            frame = self._wait_for(
                lambda current: self._is_lobby_preset(current)
                and (point := self._unique_text(
                    current, self.lineup_group, (20, 190, 160, 610)
                )) is not None and self._lobby_group_selected(current, point),
                "队伍预设分组未选中",
            )
        frame = self._select_lobby_lineup(frame)
        deploy = self._unique_text(frame, "出战", (290, 560, 460, 630))
        if deploy is None:
            raise RuntimeError("[SOUL_SOIL_LOBBY] 未识别出战按钮")
        self._click(deploy)
        frame = self._wait_for(
            lambda current: self._is_lobby(current) and not self._is_lobby_preset(current),
            "应用队伍后未返回准备页",
        )
        ready = self._match(frame, "solo_lobby_ready")
        if ready is None or self._unique_text(frame, "准备", (980, 470, 1136, 610)) is None:
            raise RuntimeError("[SOUL_SOIL_LOBBY] 未确认准备按钮")
        self._battle_started = True
        self._click(ready)
        self._stage = "waiting_battle"
        self._wait_for(self._is_battle, "挑战后未识别到战斗画面")

    def _select_lobby_lineup(
        self, frame: np.ndarray,
    ) -> np.ndarray:
        """在已选分组中选择准确预设，并确认高亮行。"""
        # 底部操作条遮住的卡片不能凭残缺名称参与选择。
        candidates = self._text_points(frame, self.lineup_name, (170, 195, 620, 520))
        if len(candidates) != 1:
            raise RuntimeError(f"[SOUL_SOIL_LINEUP] 预设名称不唯一或不可见：{self.lineup_name}")
        point = candidates[0]
        if not self._lobby_row_selected(frame, point):
            self._click(point)
            frame = self._wait_for(
                lambda current: self._lobby_row_selected(current, point),
                "目标队伍预设未高亮",
            )
        return frame

    def _wait_battle_end(self) -> None:
        """战斗零输入，直到结算及其奖励遮罩都已清理。"""
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            frame = self._read()
            if self._has_battle_or_settlement(frame):
                self._stage = "settlement" if self._battle_counted else "battle"
                self._wait_tick()
                continue
            if self._battle_counted:
                if (self._is_home(frame) or self._is_soul_stage(frame)
                        or self._is_soul_modes(frame) or self._is_exploration(frame)
                        or self._is_lobby(frame)):
                    return
                raise RuntimeError("[SOUL_SOIL_SETTLEMENT] 结算后出现未知页面，未执行返回")
            self._stage = "battle"
            self._wait_tick()
        raise RuntimeError("[SOUL_SOIL_TIMEOUT] 战斗或结算超时")

    def _return_to_home(self, *, from_lineup: bool = False) -> None:
        """只在已识别页面点击既有返回控件，并重新验证庭院。"""
        self._stage = "returning_home"
        for _ in range(4):
            frame = self._read()
            if self._has_exit_confirmation(frame):
                self._press_escape()
                self._wait_for(
                    lambda current: self._is_home(current)
                    and not self._has_exit_confirmation(current),
                    "取消离开弹窗后未确认庭院",
                )
                return
            if self._is_home(frame):
                return
            if not from_lineup and self._has_battle_or_settlement(frame):
                self._wait_tick()
                continue
            state = self._return_state(frame, from_lineup=from_lineup)
            if state is None:
                raise RuntimeError("[SOUL_SOIL_RETURN] 返回前的页面未知，未发送输入")
            point = (
                self._match_shared(frame, _RETURN) if from_lineup
                else self._match_shared(frame, _TO_HOME) or self._match_shared(frame, _RETURN)
            )
            if point is None:
                raise RuntimeError("[SOUL_SOIL_RETURN] 未识别庭院返回控件")
            self._click(point)
            self._wait_for(
                lambda current: self._return_state(current, from_lineup=from_lineup) != state,
                "返回控件操作后页面未变化",
                timeout_seconds=8,
            )
        self._wait_for(self._is_home, "返回控件操作后未确认庭院")

    def _return_state(self, frame: np.ndarray, *, from_lineup: bool = False) -> str | None:
        """返回当前已识别的庭院导航页名称。"""
        if from_lineup and self._is_shikigami_preset(frame):
            return "shikigami_preset"
        if from_lineup and any(self._match_shared(frame, path) is not None for path in (
            "yys/common/images/lineup/shikigami.png", "yys/common/images/lineup/shikigami_preset.png",
        )):
            return "shikigami"
        if self._is_home(frame):
            return "home"
        if self._is_lobby_preset(frame):
            return "lobby_preset"
        if self._is_lobby(frame):
            return "lobby"
        if self._is_soul_stage(frame):
            return "soul_stage"
        if self._is_soul_modes(frame):
            return "soul_modes"
        if self._is_exploration(frame):
            return "exploration"
        return None

    def _has_exit_confirmation(self, frame: np.ndarray) -> bool:
        """只识别明确的“确认离开”弹窗标题。"""
        labels = self.ocr.find_all_text_positions(frame[180:500, 220:920], 0.85)
        texts = [re.sub(r"\s+", "", text) for _, _, text, _ in labels]
        return any("确认离开" in text for text in texts)

    def _press_escape(self) -> None:
        """仅用 ESC 取消已识别的退出弹窗。"""
        self._check()
        self._env.key_press(27)
        if self._run_guard.is_stopped:
            self._check()
        self._run_guard.allow_unknown_for(8)

    def _on_battle_victory(self, point: tuple[int, int]) -> None:
        """复用通用胜利点击，胜利与总场数都只记一次。"""
        if not self._battle_started:
            return
        if self._victory_seen:
            self.bg_left_click(point)
            return
        super()._on_battle_victory(point)
        self._victory_seen = True
        self._record_battle()

    def _on_battle_end(self, point: tuple[int, int]) -> None:
        """复用通用结算点击；总场数由本类幂等记录。"""
        if not self._battle_started:
            return
        self._record_battle()
        super()._on_battle_end(point)

    def _on_treasure(self, _point: tuple[int, int]) -> None:
        """发现宝藏是本次结算的一部分，复用通用继续处理一次。"""
        if self._battle_started and not self._treasure_clicked:
            self._record_battle()
            self._treasure_clicked = True
            super()._on_ocr_click_screen_continue(None)

    def _on_gained_reward(self, _point: tuple[int, int]) -> None:
        """仅在识别到公共奖励页后使用通用位置清理遮罩。"""
        if self._battle_started:
            self._on_battle_end((960, 535))

    def _should_count_battle_end(self, _point: tuple[int, int]) -> bool:
        """总场数由 `_record_battle` 统一去重。"""
        return False

    def _record_battle(self) -> bool:
        """将本次挑战结算计数一次。"""
        if not self._battle_started or self._battle_counted:
            return False
        self._battle_counted = True
        self._cur_battle_count += 1
        self._log_battle_count()
        return True

    def bg_left_click(self, point: tuple, x_range: int = 20, y_range: int = 20) -> None:
        """让共享结算回调的点击经过环境、停止检查和保险丝。"""
        self._click(point)

    def _read(self) -> np.ndarray:
        """刷新客户区截图、触发已注册事件并回执 RunGuard。"""
        self._check()
        if not self._run_guard.before_iteration():
            self._check()
        image = self._env.capture_screen().convert("RGB")
        self._size = image.size
        if image.width < 500 or abs(image.width / image.height - _SIZE[0] / _SIZE[1]) > 0.03:
            raise RuntimeError("[SOUL_SOIL_CAPTURE] 客户区尺寸或比例未校准")
        frame = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        frame = cv2.resize(frame, _SIZE, interpolation=cv2.INTER_AREA)
        self.image_finder.screenshot_cache = frame
        triggered = self._trigger_event_from_screenshot_cache()
        self._last_triggered_event = triggered
        self._run_guard.note_iteration(triggered is not None)
        if self._run_guard.is_stopped:
            self._check()
        return frame

    def _click(self, point: tuple[int, int]) -> None:
        """仅点击新鲜截图识别出的客户区位置。"""
        self._check()
        if self._env.observe_only:
            self._stage = "observing"
            raise RuntimeError("[SOUL_SOIL_OBSERVE] 观察模式不发送输入")
        x, y = point
        self._env.left_click(
            round(x * self._size[0] / _SIZE[0]),
            round(y * self._size[1] / _SIZE[1]),
        )
        if self._run_guard.is_stopped:
            self._check()
        self._run_guard.allow_unknown_for(8)

    def _check(self) -> None:
        """在每次截图/输入前尊重暂停、停止与保险丝。"""
        self.pause_point()
        if self._stop_threading_event.is_set():
            raise _Stopped()
        if self._run_guard.is_stopped:
            if getattr(self._run_guard.stop_reason, "value", None) == "emergency_stop":
                raise _Stopped()
            raise RuntimeError(f"[SOUL_SOIL_GUARD] 运行保险丝停止：{self._run_guard.stop_reason}")

    def _wait_for(
        self, predicate: Callable[[np.ndarray], bool], failure: str,
        timeout_seconds: float = 20,
    ) -> np.ndarray:
        """逐张新截图等待指定状态，不重放操作。"""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            frame = self._read()
            if predicate(frame):
                return frame
            self._wait_tick()
        raise RuntimeError(f"[SOUL_SOIL_TRANSITION] {failure}")

    def _wait_tick(self) -> None:
        """短间隔等待，同时允许停止和暂停及时生效。"""
        self._check()
        self._stop_threading_event.wait(0.2)
        self._check()

    def _match(
        self, frame: np.ndarray, name: str,
        region: tuple[int, int, int, int] | None = None,
    ) -> tuple[int, int] | None:
        """以已提取生产模板识别页面或控件。"""
        path = self._templates[name]
        result = self.image_finder.best_match(frame, path, *(region or (0, 0, 99999, 99999)))
        return result.point if result.similarity >= 0.90 else None

    def _match_shared(self, frame: np.ndarray, path: str) -> tuple[int, int] | None:
        """识别既有通用页面/控件模板。"""
        result = self.image_finder.best_match(frame, path)
        return result.point if result.similarity >= 0.80 else None

    def _click_shared(self, frame: np.ndarray, path: str, label: str) -> None:
        """只点击当前已识别页面上的共享控件。"""
        point = self._match_shared(frame, path)
        if point is None:
            raise RuntimeError(f"[SOUL_SOIL_ENTRY] 未识别{label}")
        self._click(point)

    def _is_home(self, frame: np.ndarray) -> bool:
        return (self._match_shared(frame, _HOME) is not None
                or self._match_shared(frame, _HOME_SAKURA) is not None)

    def _is_exploration(self, frame: np.ndarray) -> bool:
        return self._match_shared(frame, _EXPLORATION) is not None

    def _is_soul_modes(self, frame: np.ndarray) -> bool:
        return self._match(frame, "yuhun_mode_card") is not None

    def _is_soul_stage(self, frame: np.ndarray) -> bool:
        return self._match(frame, "soul_stage_title") is not None

    def _soul_soil_label(self, frame: np.ndarray) -> tuple[int, int] | None:
        matches = [
            point for point, text, _ in self._text_points_with_content(
                frame, (90, 400, 180, 475), "悲鸣", similarity_threshold=0.70,
            )
        ]
        return matches[0] if len(matches) == 1 else None

    def _is_soul_soil_selected(self, frame: np.ndarray) -> bool:
        label = self._soul_soil_label(frame)
        if label is None:
            return False
        x, y = label
        area = cv2.cvtColor(frame[max(0, y - 16):y + 16, max(0, x - 30):x + 30], cv2.COLOR_BGR2GRAY)
        return int(np.count_nonzero(area > 170)) >= 150

    def _is_lobby(self, frame: np.ndarray) -> bool:
        return self._match(frame, "solo_lobby_ready") is not None

    def _is_lobby_preset(self, frame: np.ndarray) -> bool:
        return (
            self._match(frame, "lobby_selected_row", (140, 180, 640, 350)) is not None
            and self._unique_text(frame, "出战", (290, 560, 460, 630)) is not None
        )

    def _is_battle(self, frame: np.ndarray) -> bool:
        return self._last_triggered_event == _BATTLE or self._match_shared(frame, _BATTLE) is not None

    def _is_shikigami_preset(self, frame: np.ndarray) -> bool:
        return (
            self._match_shared(frame, _PRESET_PANEL) is not None
            or self._match_shared(frame, _PRESET_PANEL_NAMED) is not None
        )

    def _lobby_group_selected(self, frame: np.ndarray, point: tuple[int, int]) -> bool:
        x, y = point
        area = frame[max(0, y - 27):y + 27, max(0, x - 63):x + 63]
        if not area.size:
            return False
        hsv = cv2.cvtColor(area, cv2.COLOR_BGR2HSV)
        gold = cv2.inRange(hsv, (15, 100, 150), (42, 255, 255))
        return np.count_nonzero(gold) / gold.size > 0.20

    def _lobby_row_selected(self, frame: np.ndarray, point: tuple[int, int]) -> bool:
        x, y = point
        return self._match(
            frame, "lobby_selected_row", (max(150, x - 110), y - 24, min(630, x + 280), y + 12),
        ) is not None

    def _text_points(
        self, frame: np.ndarray, text: str, region: tuple[int, int, int, int],
    ) -> list[tuple[int, int]]:
        return [point for point, found, _ in self._text_points_with_content(frame, region, text)
                if found == text]

    def _unique_text(
        self, frame: np.ndarray, text: str, region: tuple[int, int, int, int],
    ) -> tuple[int, int] | None:
        points = self._text_points(frame, text, region)
        if len(points) > 1:
            raise RuntimeError(f"[SOUL_SOIL_OCR] 画面上出现多个目标文字：{text}")
        return points[0] if points else None

    def _text_points_with_content(
        self, frame: np.ndarray, region: tuple[int, int, int, int], text: str,
        similarity_threshold: float = 0.80,
    ) -> list[tuple[tuple[int, int], str, float]]:
        x0, y0, x1, y1 = region
        labels = self.ocr.find_all_text_positions(
            frame[y0:y1, x0:x1], similarity_threshold,
        )
        needle = re.sub(r"\s+", "", text)
        return [
            ((x0 + x, y0 + y), re.sub(r"\s+", "", found), confidence)
            for x, y, found, confidence in labels
            if needle in re.sub(r"\s+", "", found)
        ]

    def _has_battle_or_settlement(self, frame: np.ndarray) -> bool:
        events = set(BATTLE_END_SUCCESS_IMAGES + BATTLE_END_LOSS_IMAGES + BATTLE_END_OTHER_IMAGES)
        if self._last_triggered_event in events or self._last_triggered_event in {_BATTLE, _REWARD}:
            return True
        return (
            self._is_battle(frame)
            or self._match_shared(frame, _REWARD) is not None
            or self._match(frame, "treasure_title") is not None
        )
