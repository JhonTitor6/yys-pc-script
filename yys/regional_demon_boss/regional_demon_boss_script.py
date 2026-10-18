"""地域鬼王固定目标单次挑战脚本。"""

from __future__ import annotations

import time
from enum import Enum
from pathlib import Path
from typing import Any, NamedTuple, Optional, TYPE_CHECKING

import cv2
import numpy as np

from win_util.environment.windows import WindowsEnvironment
from win_util.event import ImageMatchConfig
from win_util.image import to_project_path
from yys.common.event_script_base import YYSBaseScript
from yys.common.script_meta import ScriptMeta

if TYPE_CHECKING:
    from tests.common.environment.base import GameEnvironment


class RegionalDemonBossError(RuntimeError):
    """地域鬼王流程无法安全继续时抛出的业务错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code


class _UserStopped(RuntimeError):
    """用户主动停止脚本。"""


class RegionalDemonBossState(str, Enum):
    """地域鬼王最小业务状态。"""

    INITIAL = "initial"
    HOME = "home"
    EXPLORATION = "exploration"
    MAP = "map"
    DETAIL = "detail"
    WAITING_BATTLE = "waiting_battle"
    BATTLE = "battle"
    SETTLEMENT = "settlement"
    REWARD = "reward"
    OBSERVING = "observing"
    DONE = "done"
    FAILED = "failed"
    STOPPED = "stopped"


class _TemplateSpec(NamedTuple):
    """一个生产模板及其可验证搜索区域。"""

    path: str
    roi: tuple[int, int, int, int]
    threshold: float = 0.80
    click_offset: tuple[int, int] = (0, 0)
    max_absdiff: float = 25.0


class RegionalDemonBossScript(YYSBaseScript):
    """从庭院进入地域鬼王并挑战丹霞山/山童一次。"""

    SCRIPT_META = ScriptMeta(
        display_name="地域鬼王",
        category="日常",
        config_schema=None,
        default_config={},
    )

    TARGET_REGION = "丹霞山"
    TARGET_BOSS = "山童"
    MAX_BATTLES = 1
    FLOW_TIMEOUT_SECONDS = 180.0
    POLL_INTERVAL_SECONDS = 0.10
    UNKNOWN_LIMIT = 3

    # 录制中唯一的地图拖拽，坐标为游戏客户区坐标。
    MAP_DRAG = (961, 183, 225, 544)
    CLIENT_ROI = (0, 0, 1136, 640)

    # 这些是唯一允许使用的生产模板。地图、目标和详情模板由录制素材生成；
    # 每个 key 只接受显式声明的模板，不做别名猜测或缺失降级。
    _TEMPLATE_SPECS: dict[str, tuple[_TemplateSpec, ...]] = {
        "loading": (
            _TemplateSpec("yys/regional_demon_boss/images/loading_footer.png",
                          (450, 595, 710, 640), 0.90),
        ),
        "home": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/home_marker.bmp",
                CLIENT_ROI,
            ),
            _TemplateSpec(
                "yys/regional_demon_boss/images/home_marker_night.bmp",
                CLIENT_ROI,
            ),
        ),
        "home_to_exploration": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/home_marker.bmp",
                CLIENT_ROI,
            ),
            _TemplateSpec(
                "yys/regional_demon_boss/images/home_marker_night.bmp",
                CLIENT_ROI,
            ),
        ),
        "exploration": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/exploration_marker.bmp",
                (480, 480, 700, 640),
            ),
        ),
        "exploration_to_regional": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/exploration_marker.bmp",
                (480, 480, 700, 640),
            ),
        ),
        "map": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/map_initial.bmp",
                (400, 0, 750, 80),
            ),
        ),
        "target": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/map_target.bmp",
                (600, 60, 900, 380),
                click_offset=(11, 41),
            ),
        ),
        "detail_title": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/detail_title.bmp",
                (50, 20, 320, 110),
            ),
        ),
        "detail_boss": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/detail_boss.bmp",
                (520, 40, 660, 200),
            ),
        ),
        "challenge": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/challenge.bmp",
                (900, 380, 1136, 620),
                click_offset=(-21, 5),
            ),
        ),
        "preparation": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/preparation.bmp",
                (900, 380, 1136, 640),
            ),
        ),
        "battle": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/battling_early.bmp",
                (0, 0, 250, 120),
            ),
        ),
        "settlement_success": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/result_success.bmp",
                (350, 430, 1000, 640),
            ),
        ),
        # 录制只有成功结算；没有经过真实帧确认的失败模板不启用。
        # 回放测试可显式注入失败模板，生产未知结算仍会安全失败。
        "settlement_failure": (),
        "reward": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/reward.bmp",
                (150, 80, 800, 600),
            ),
        ),
        "settlement_continue": (
            _TemplateSpec(
                "yys/regional_demon_boss/images/settlement_continue.bmp",
                (350, 540, 800, 640),
            ),
        ),
        "return": (
            _TemplateSpec("yys/common/images/scene_control/return.bmp", CLIENT_ROI),
        ),
    }

    _REQUIRED_TEMPLATE_KEYS = tuple(
        key for key in _TEMPLATE_SPECS if key != "settlement_failure"
    )

    def __init__(
        self,
        script_name: str = "regional_demon_boss",
        env: Optional["GameEnvironment"] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        """初始化脚本并一次性加载、验证全部生产模板。"""
        super().__init__(script_name, config=config if config is not None else {}, env=env)
        self.entry_scene = None
        self.max_battle_count = self.MAX_BATTLES
        self._runtime_env = env or WindowsEnvironment(hwnd=self.hwnd)
        self._templates: dict[str, tuple[tuple[_TemplateSpec, np.ndarray], ...]] = {}
        self._state = RegionalDemonBossState.INITIAL
        self._stop_reason: str | None = None
        self._challenge_sent = False
        self._settlement_consumed = False
        self._settlement_result: str | None = None
        self._settlement_clicks = 0
        self._drag_used = False
        self._target_verified = False
        self._deadline = 0.0
        self._unknown_frames = 0
        self._local_grace_until = 0.0
        self._load_templates()
        self._register_runtime_events()

    @property
    def observe_only(self) -> bool:
        """返回注入环境是否为观察模式。"""
        return bool(getattr(self._runtime_env, "observe_only", False))

    def _load_templates(self) -> None:
        """加载并验证模板；缺失或损坏时在构造阶段明确失败。"""
        for key, specs in self._TEMPLATE_SPECS.items():
            loaded: list[tuple[_TemplateSpec, np.ndarray]] = []
            for spec in specs:
                path = Path(to_project_path(spec.path))
                if not path.is_file():
                    raise RegionalDemonBossError(
                        "REGIONAL_TEMPLATE_MISSING",
                        f"缺少地域鬼王真实模板：{spec.path}",
                    )
                data = np.fromfile(path, dtype=np.uint8)
                template = cv2.imdecode(data, cv2.IMREAD_COLOR)
                if template is None or template.ndim != 3 or template.size == 0:
                    raise RegionalDemonBossError(
                        "REGIONAL_TEMPLATE_INVALID",
                        f"模板无法解码：{spec.path}",
                    )
                if template.dtype != np.uint8 or float(template.std()) == 0:
                    raise RegionalDemonBossError(
                        "REGIONAL_TEMPLATE_INVALID",
                        f"模板内容无效：{spec.path}",
                    )
                x0, y0, x1, y1 = spec.roi
                height, width = template.shape[:2]
                if not (0 <= x0 < x1 and 0 <= y0 < y1):
                    raise RegionalDemonBossError(
                        "REGIONAL_TEMPLATE_INVALID",
                        f"模板 ROI 无效：{spec.path} {spec.roi}",
                    )
                if width > x1 - x0 or height > y1 - y0:
                    raise RegionalDemonBossError(
                        "REGIONAL_TEMPLATE_INVALID",
                        f"模板超出 ROI：{spec.path} {spec.roi}",
                    )
                loaded.append((spec, template))
            self._templates[key] = tuple(loaded)

    def _register_runtime_events(self) -> None:
        """注册准备、战斗、结算和奖励事件，回调均不发送输入。"""
        for key in (
            "preparation",
            "battle",
            "settlement_success",
            "settlement_failure",
            "reward",
        ):
            for spec, _template in self._templates.get(key, ()):
                self._register_image_match_event(
                    ImageMatchConfig(spec.path, similarity=spec.threshold),
                    self._on_registered_visual,
                )

    def _on_registered_visual(self, _point: tuple[int, int]) -> None:
        """刷新长生命周期状态识别；战斗和准备阶段严禁输入。"""
        return None

    def on_run(self) -> None:
        """重置单次挑战状态。"""
        super().on_run()
        self.max_battle_count = self.MAX_BATTLES
        self._state = RegionalDemonBossState.INITIAL
        self._stop_reason = None
        self._challenge_sent = False
        self._settlement_consumed = False
        self._settlement_result = None
        self._settlement_clicks = 0
        self._drag_used = False
        self._target_verified = False
        self._unknown_frames = 0
        self._local_grace_until = 0.0
        self._deadline = time.monotonic() + self.FLOW_TIMEOUT_SECONDS

    def run(self) -> None:
        """执行一次流程；用户停止正常返回，其他失败抛结构化异常。"""
        if self._stop_threading_event.is_set():
            if self._state is RegionalDemonBossState.STOPPED:
                return
            self._stop_threading_event.clear()
        self.on_run()
        try:
            if self.observe_only:
                self._run_observe_once()
            else:
                self._run_execute()
        except _UserStopped:
            return
        except RegionalDemonBossError:
            raise
        except Exception as exc:
            self._fail("REGIONAL_FLOW_ERROR", str(exc))

    def _run_execute(self) -> None:
        """执行入口、目标选择、战斗观察和结算清理。"""
        self._prepare_home()
        self._navigate_to_map()
        self._select_target()
        self._challenge()
        self._wait_for_settlement()
        self._finish_success()

    def _run_observe_once(self) -> None:
        """观察模式只规划当前页动作，不切阵容、不等待转场。"""
        self._checkpoint()
        frame = self._read_frame()
        self._state = RegionalDemonBossState.OBSERVING
        if self._is_home(frame):
            self._click_named("home_to_exploration", frame)
        elif self._is_exploration(frame):
            self._click_named("exploration_to_regional", frame)
        elif self._is_map(frame):
            target = self._find_template(frame, "target")
            if target is not None:
                self._click(target)
            elif not self._drag_used:
                self._drag_map()
        elif self._is_verified_detail(frame):
            self._click_named("challenge", frame)
        elif self._is_settlement(frame) or self._is_reward(frame):
            self._click_continue(frame)
        self._stop_reason = "observe_only"

    def _prepare_home(self) -> None:
        """从庭院应用地域鬼王/悬赏预设，再安全回到庭院。"""
        self._checkpoint()
        frame = self._read_frame()
        if not self._is_home(frame):
            self._fail("REGIONAL_ENTRY_NOT_HOME", "当前画面不是已确认的庭院")
        self._state = RegionalDemonBossState.HOME
        try:
            self.switch_lineup("地域鬼王", "悬赏", home_verified=True)
        except _UserStopped:
            raise
        except Exception as exc:
            if self._stop_threading_event.is_set():
                raise _UserStopped from exc
            self._fail("REGIONAL_LINEUP_FAILED", str(exc))
        self._checkpoint()
        frame = self._read_frame()
        if self._is_home(frame):
            return
        self._click_named("return", frame)
        self._wait_until(self._is_home, "预设完成后未返回庭院", "REGIONAL_HOME_RETURN_FAILED")

    def _navigate_to_map(self) -> None:
        """按录制流程进入探索页和地域鬼王地图。"""
        self._checkpoint()
        frame = self._read_frame()
        if not self._is_home(frame):
            self._fail("REGIONAL_HOME_UNKNOWN", "返回庭院后页面无法确认")
        self._click_named("home_to_exploration", frame)
        frame = self._wait_until(
            self._is_exploration,
            "未到达探索页",
            "REGIONAL_EXPLORATION_FAILED",
        )
        self._state = RegionalDemonBossState.EXPLORATION
        self._click_named("exploration_to_regional", frame)
        self._wait_until(self._is_map, "未到达地域鬼王地图", "REGIONAL_MAP_FAILED")
        self._state = RegionalDemonBossState.MAP

    def _select_target(self) -> None:
        """目标已可见时直接点击，否则只执行一次录制拖拽后再识别。"""
        self._checkpoint()
        frame = self._read_frame()
        if not self._is_map(frame):
            self._fail("REGIONAL_MAP_UNKNOWN", "当前不是已确认的地域鬼王地图")
        point = self._find_template(frame, "target")
        if point is None:
            self._drag_map()
            frame = self._wait_until(
                lambda image: self._find_template(image, "target") is not None,
                "一次录制拖拽后未识别到丹霞山",
                "REGIONAL_TARGET_MISSING",
            )
            point = self._find_template(frame, "target")
        if point is None:
            self._fail("REGIONAL_TARGET_MISSING", "目标位置在新鲜帧中不可确认")
        self._click(point)
        detail = self._wait_until(
            self._is_verified_detail,
            "目标点击后未到达丹霞山/山童详情页",
            "REGIONAL_WRONG_TARGET",
        )
        if not self._is_verified_detail(detail):
            self._fail("REGIONAL_WRONG_TARGET", "详情页目标与丹霞山/山童不一致")
        self._state = RegionalDemonBossState.DETAIL
        self._target_verified = True

    def _challenge(self) -> None:
        """详情标题、首领和挑战按钮均确认后只点击一次。"""
        if self._challenge_sent or not self._target_verified:
            self._fail("REGIONAL_CHALLENGE_STATE", "挑战前目标未核验或挑战已发送")
        self._checkpoint()
        frame = self._read_frame()
        if not self._is_verified_detail(frame):
            self._fail("REGIONAL_WRONG_TARGET", "挑战前详情页未通过完整核验")
        self._click_named("challenge", frame)
        self._challenge_sent = True
        self._state = RegionalDemonBossState.WAITING_BATTLE
        self._allow_transition_grace()

    def _wait_for_settlement(self) -> None:
        """准备、战斗和旧详情残留只观察，结算和奖励按模板清理。"""
        while True:
            self._checkpoint()
            frame = self._read_frame()
            if self._is_settlement_success(frame):
                self._on_settlement_frame("success", frame)
            elif self._is_settlement_failure(frame):
                self._on_settlement_frame("failure", frame)
            elif self._is_reward(frame):
                self._on_reward_frame(frame)
            elif self._is_verified_detail(frame):
                if self._settlement_consumed:
                    self._state = RegionalDemonBossState.DONE
                    return
                self._state = RegionalDemonBossState.WAITING_BATTLE
                self._recognized()
            elif self._is_preparation(frame):
                self._state = RegionalDemonBossState.BATTLE
                self._recognized()
            elif self._is_battle(frame):
                self._state = RegionalDemonBossState.BATTLE
                self._recognized()
                self._allow_transition_grace()
            else:
                self._unknown()
            time.sleep(self.POLL_INTERVAL_SECONDS)

    def _on_settlement_frame(self, result: str, frame: np.ndarray) -> None:
        """首次明确成功/失败结算消费一次总战斗计数，后续只清理画面。"""
        self._state = RegionalDemonBossState.SETTLEMENT
        self._recognized()
        if not self._settlement_consumed:
            if not self._challenge_sent:
                self._fail("REGIONAL_SETTLEMENT_UNARMED", "未发起挑战却出现结算")
            self._settlement_consumed = True
            self._settlement_result = result
            self._cur_battle_count += 1
            if result == "success":
                self._cur_battle_victory_count += 1
            self._log_battle_count()
        self._click_continue(frame)

    def _on_reward_frame(self, frame: np.ndarray) -> None:
        """奖励画面只清理，不增加战斗计数。"""
        self._state = RegionalDemonBossState.REWARD
        self._recognized()
        self._click_continue(frame)

    def _finish_success(self) -> None:
        """只有完成一次已确认结算并返回详情页才正常结束。"""
        if (
            self._cur_battle_count != self.MAX_BATTLES
            or not self._challenge_sent
            or not self._settlement_consumed
        ):
            self._fail("REGIONAL_INCOMPLETE", "流程结束但未完成一次已确认结算")
        self._state = RegionalDemonBossState.DONE
        self._stop_reason = "completed"
        super().stop()

    def _drag_map(self) -> None:
        """执行录制确认的一次地图拖拽。"""
        if self._drag_used:
            self._fail("REGIONAL_DRAG_LIMIT", "地域鬼王地图拖拽次数超出录制范围")
        self._checkpoint()
        self._runtime_env.drag(*self.MAP_DRAG)
        if self._run_guard is not None and self._run_guard.is_stopped:
            self._fail("REGIONAL_GUARD_STOPPED", "运行保险丝已停止脚本")
        self._drag_used = True
        self._allow_transition_grace()

    def _click_named(self, key: str, frame: np.ndarray) -> None:
        """只点击新鲜画面中确认的模板位置。"""
        point = self._find_template(frame, key)
        if point is None:
            self._fail("REGIONAL_ACTION_UNCONFIRMED", f"未确认动作位置：{key}")
        self._click(point)

    def _click_continue(self, frame: np.ndarray) -> None:
        """点击已识别的结算清理位置。"""
        point = self._find_template(frame, "settlement_continue")
        if point is None:
            self._fail("REGIONAL_SETTLEMENT_ACTION_UNKNOWN", "未确认结算清理位置")
        self._click(point)
        self._settlement_clicks += 1

    def _click(self, point: tuple[int, int]) -> None:
        self._checkpoint()
        self._runtime_env.left_click(int(point[0]), int(point[1]))
        if self._run_guard is not None and self._run_guard.is_stopped:
            self._fail("REGIONAL_GUARD_STOPPED", "运行保险丝已停止脚本")

    def _read_frame(self) -> np.ndarray:
        """读取新鲜客户区截图并规范为 BGR 数组。"""
        image = self._runtime_env.capture_screen()
        if hasattr(image, "convert"):
            rgb = np.asarray(image.convert("RGB"))
            frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        else:
            frame = np.asarray(image)
            if frame.ndim == 3 and frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        if (
            frame.ndim != 3
            or frame.shape[2] != 3
            or frame.shape[0] < 100
            or frame.shape[1] < 100
        ):
            self._fail("REGIONAL_CAPTURE_FAILED", "游戏客户区截图无效")
        return frame

    def _wait_until(self, predicate: Any, message: str, code: str) -> np.ndarray:
        """等待明确页面；未知帧达到上限或超时即失败。"""
        while True:
            self._checkpoint()
            frame = self._read_frame()
            if predicate(frame):
                self._recognized()
                return frame
            if "loading" in self._templates and self._find_template(frame, "loading") is not None:
                self._recognized()
            else:
                self._unknown(code)
            if time.monotonic() >= self._deadline:
                self._fail(code, message)
            time.sleep(self.POLL_INTERVAL_SECONDS)

    def _checkpoint(self) -> None:
        """检查暂停、用户停止、保险丝和总超时。"""
        self.pause_point()
        if self._stop_threading_event.is_set():
            self._stop_reason = self._stop_reason or "user_stop"
            self._state = RegionalDemonBossState.STOPPED
            raise _UserStopped("用户停止地域鬼王脚本")
        if self._run_guard is not None and not self._run_guard.before_iteration():
            self._fail("REGIONAL_GUARD_STOPPED", "运行保险丝已停止脚本")
        if time.monotonic() >= self._deadline:
            self._fail("REGIONAL_TIMEOUT", "地域鬼王流程超时")

    def _recognized(self) -> None:
        """记录本轮识别成功，保持保险丝未知计数清零。"""
        self._unknown_frames = 0
        self._local_grace_until = 0.0
        if self._run_guard is not None:
            self._run_guard.note_iteration(True)

    def _unknown(self, code: str = "REGIONAL_UNKNOWN_SCENE") -> None:
        """记录未知画面；动作宽限期内不累积本地未知计数。"""
        local_grace = time.monotonic() < self._local_grace_until
        if self._run_guard is not None:
            self._run_guard.note_iteration(False)
            snapshot = self._run_guard.snapshot()
            if snapshot["stop_reason"] is not None:
                self._fail("REGIONAL_GUARD_STOPPED", "运行保险丝已停止脚本")
            if snapshot["unknown_grace_remaining_seconds"]:
                self._unknown_frames = 0
                return
        if local_grace:
            self._unknown_frames = 0
            return
        self._unknown_frames += 1
        if self._unknown_frames >= self.UNKNOWN_LIMIT:
            self._fail(code, "地域鬼王流程出现连续未知画面")

    def _allow_transition_grace(self) -> None:
        self._local_grace_until = max(
            self._local_grace_until,
            time.monotonic() + 5.0,
        )
        if self._run_guard is not None:
            self._run_guard.allow_unknown_for(5.0)

    def _find_template(self, frame: np.ndarray, key: str) -> tuple[int, int] | None:
        """在声明 ROI 内匹配模板并返回模板中心加显式点击偏移。"""
        for spec, template in self._templates[key]:
            x0, y0, x1, y1 = spec.roi
            if frame.shape[1] < x1 or frame.shape[0] < y1:
                continue
            search = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
            needle = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            if search.shape[0] < needle.shape[0] or search.shape[1] < needle.shape[1]:
                continue
            _min, score, _min_loc, location = cv2.minMaxLoc(
                cv2.matchTemplate(search, needle, cv2.TM_CCOEFF_NORMED)
            )
            if score < spec.threshold:
                continue
            height, width = needle.shape[:2]
            matched = search[location[1]:location[1] + height, location[0]:location[0] + width]
            if matched.shape != needle.shape:
                continue
            if float(cv2.absdiff(matched, needle).mean()) > spec.max_absdiff:
                continue
            return (
                x0 + location[0] + width // 2 + spec.click_offset[0],
                y0 + location[1] + height // 2 + spec.click_offset[1],
            )
        return None

    def _is_home(self, frame: np.ndarray) -> bool:
        return self._find_template(frame, "home") is not None

    def _is_exploration(self, frame: np.ndarray) -> bool:
        return self._find_template(frame, "exploration") is not None

    def _is_map(self, frame: np.ndarray) -> bool:
        return self._find_template(frame, "map") is not None

    def _is_preparation(self, frame: np.ndarray) -> bool:
        return self._find_template(frame, "preparation") is not None

    def _is_battle(self, frame: np.ndarray) -> bool:
        return self._find_template(frame, "battle") is not None

    def _is_settlement_success(self, frame: np.ndarray) -> bool:
        return self._find_template(frame, "settlement_success") is not None

    def _is_settlement_failure(self, frame: np.ndarray) -> bool:
        return bool(
            self._templates.get("settlement_failure")
            and self._find_template(frame, "settlement_failure") is not None
        )

    def _is_settlement(self, frame: np.ndarray) -> bool:
        """兼容测试和状态检查的成功/失败结算判断。"""
        return self._is_settlement_success(frame) or self._is_settlement_failure(frame)

    def _is_reward(self, frame: np.ndarray) -> bool:
        return self._find_template(frame, "reward") is not None

    def _is_verified_detail(self, frame: np.ndarray) -> bool:
        return all(
            self._find_template(frame, key) is not None
            for key in ("detail_title", "detail_boss", "challenge")
        )

    def _fail(self, code: str, message: str) -> None:
        self._state = RegionalDemonBossState.FAILED
        self._stop_reason = code
        super().stop()
        raise RegionalDemonBossError(code, message)

    def stop(self) -> None:
        """响应用户主动停止，保留已完成/失败状态。"""
        if self._state not in {RegionalDemonBossState.DONE, RegionalDemonBossState.FAILED}:
            self._state = RegionalDemonBossState.STOPPED
            self._stop_reason = self._stop_reason or "user_stop"
        super().stop()

    def get_state_snapshot(self) -> dict[str, object]:
        """返回 UI/运行管理器可审阅的单次流程状态。"""
        snapshot = super().get_state_snapshot()
        snapshot.update(
            {
                "state": self._state.value,
                "stop_reason": self._stop_reason,
                "target_region": self.TARGET_REGION,
                "target_boss": self.TARGET_BOSS,
                "challenge_sent": self._challenge_sent,
                "settlement_consumed": self._settlement_consumed,
                "settlement_result": self._settlement_result,
                "settlement_clicks": self._settlement_clicks,
                "drag_used": self._drag_used,
                "target_verified": self._target_verified,
            }
        )
        return snapshot


if __name__ == '__main__':
    RegionalDemonBossScript().run()
