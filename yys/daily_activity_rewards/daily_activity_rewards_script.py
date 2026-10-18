"""花合战每日奖励领取脚本。"""

from __future__ import annotations

import re
import time
from enum import Enum
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from win_util.environment.base import GameEnvironment
from win_util.environment.guarded import GuardedEnvironment, RunGuard
from win_util.environment.windows import WindowsEnvironment
from win_util.image import to_project_path
from yys.common.event_script_base import YYSBaseScript
from yys.common.script_meta import ScriptMeta


class RewardState(str, Enum):
    """当前花合战今日奖励状态。"""

    CLAIMABLE = "claimable"
    CLAIMED = "claimed"
    NOT_ELIGIBLE = "not_eligible"
    UNKNOWN = "unknown"


class _Stopped(Exception):
    """用户停止或观察模式结束流程。"""


class DailyActivityRewardsScript(YYSBaseScript):
    """领取花合战今日页当前可领取的奖励并确认返回庭院。"""

    SCRIPT_META = ScriptMeta("每日活跃度奖励", "日常", None, {})
    SIZE = (1136, 640)
    TIMEOUT_SECONDS = 180.0
    MAX_ACTIONS = 12
    TRANSITION_SECONDS = 12.0
    REWARD_DISMISS_LIMIT = 3
    MENU_TOGGLE = "menu_toggle.png"
    RETURN_BUTTON = "yys/common/images/scene_control/return.bmp"
    CLAIM_ROI = (780, 520, 900, 610)
    EXPERIENCE_ROI = (900, 155, 1050, 200)
    ACTIVITY_TITLE_ROI = (75, 5, 290, 75)
    TODAY_TAB_ROI = (435, 140, 590, 205)
    TASK_TAB_ROI = (1040, 270, 1125, 430)
    FLOWER_MENU_ROI = (650, 540, 780, 625)
    REWARD_TITLE_ROI = (430, 185, 710, 260)

    def __init__(
        self,
        script_name: str = "daily_activity_rewards",
        config: dict[str, object] | None = None,
        env: GameEnvironment | None = None,
    ) -> None:
        """初始化环境与保险丝；脚本无用户可配置字段。"""
        actual_env = env if env is not None else WindowsEnvironment()
        guard = (
            actual_env.guard
            if isinstance(actual_env, GuardedEnvironment)
            else RunGuard(
                timeout_seconds=self.TIMEOUT_SECONDS,
                max_actions=self.MAX_ACTIONS,
                unknown_limit=3,
            )
        )
        runtime_env = (
            actual_env
            if isinstance(actual_env, GuardedEnvironment)
            else GuardedEnvironment(actual_env, guard, observe_only=False)
        )
        super().__init__(script_name, config=config or {}, env=runtime_env)
        self._runtime_env = runtime_env
        self.set_run_guard(guard)
        self._size = self.SIZE
        self._stage = "initial"
        self._outcome = "pending"
        self._reward_state = RewardState.UNKNOWN.value
        self._claimed_count = 0
        self._images = Path(to_project_path("yys/daily_activity_rewards/images"))
        self._menu_toggle_path = str(self._images / self.MENU_TOGGLE)
        if cv2.imread(self._menu_toggle_path) is None:
            raise ValueError(f"缺少庭院菜单模板：{self._menu_toggle_path}")

    @property
    def observe_only(self) -> bool:
        """返回注入环境是否为观察模式。"""
        return bool(getattr(self._runtime_env, "observe_only", False))

    def on_run(self) -> None:
        """重置业务快照。"""
        super().on_run()
        self._stage = "initial"
        self._outcome = "pending"
        self._reward_state = RewardState.UNKNOWN.value
        self._claimed_count = 0

    def get_state_snapshot(self) -> dict[str, object]:
        """返回领奖阶段与结果，不将领取动作计入战斗次数。"""
        return {
            **super().get_state_snapshot(),
            "stage": self._stage,
            "outcome": self._outcome,
            "reward_state": self._reward_state,
            "claimed_count": self._claimed_count,
        }

    def run(self) -> None:
        """从庭院领取当前可领奖励，并在确认庭院后正常结束。"""
        self.on_run()
        try:
            frame = self._read()
            if not self._is_home(frame) and not self._is_flower_page(frame):
                self._note_known(False)
                raise RuntimeError("[DAILY_ENTRY] 请从已识别的庭院启动")
            self._note_known(True)
            frame = self._open_activity_page(frame)
            state, experience, claim_point = self._classify_rewards(frame)
            self._note_known(True)
            if state is RewardState.UNKNOWN or experience is None:
                raise RuntimeError("[DAILY_REWARDS_UNKNOWN] 无法可靠识别今日领奖状态")

            self._reward_state = state.value
            if state is RewardState.CLAIMABLE:
                if claim_point is None:
                    raise RuntimeError("[DAILY_CLAIM_TARGET] 未定位唯一领取按钮")
                self._stage = "claiming"
                self._click(claim_point)
                self._wait_for(
                    lambda current: self._reward_dialog_point(current) is not None,
                    "未识别到领取后的奖励弹窗",
                )
                self._stage = "clearing_reward"
                self._clear_reward_dialog()
                frame = self._read()
                if not self._is_activity_page(frame) or self._reward_dialog_point(frame) is not None:
                    self._note_known(False)
                    raise RuntimeError("[DAILY_REWARD_RETURN] 清理奖励后未确认花合战今日页")
                self._note_known(True)
                after_state, after_experience, after_button = self._classify_rewards(frame)
                if (
                    after_state is not RewardState.CLAIMED
                    or after_experience is None
                    or after_experience <= experience
                    or after_button is not None
                ):
                    raise RuntimeError("[DAILY_CLAIM_UNCONFIRMED] 页面反馈未证明奖励已领取")
                self._reward_state = RewardState.CLAIMED.value
                self._claimed_count = 1

            self._return_home(frame)
            self._stage = "done"
            self._outcome = "completed"
        except _Stopped:
            if self._outcome == "observing":
                self._stage = "observing"
                raise RuntimeError("[DAILY_OBSERVE] 观察模式只记录计划动作，未完成业务") from None
            if self._stop_threading_event.is_set():
                return
            self._stage, self._outcome = "failed", "failed"
            raise RuntimeError("[DAILY_STOP] 保险丝停止脚本，不能报告完成") from None
        except Exception:
            self._stage, self._outcome = "failed", "failed"
            raise

    def _open_activity_page(self, frame: np.ndarray) -> np.ndarray:
        """确认并展开庭院菜单，再进入花合战今日页。"""
        if not self._is_flower_page(frame):
            visible = self._text_points(frame, self.FLOWER_MENU_ROI, "花合战")
            collapsed = self._template_point(frame, self._menu_toggle_path, 0.90)
            if len(visible) > 1:
                raise RuntimeError("[DAILY_MENU_TARGET] 花合战菜单项不唯一")
            if not visible:
                if collapsed is None:
                    raise RuntimeError("[DAILY_MENU] 未确认庭院菜单状态")
                self._stage = "opening_menu"
                self._click(collapsed)
                frame = self._wait_for(
                    lambda current: self._is_home(current)
                    and len(self._text_points(current, self.FLOWER_MENU_ROI, "花合战")) == 1,
                    "庭院菜单未能展开",
                )
            flower_points = self._text_points(frame, self.FLOWER_MENU_ROI, "花合战")
            if len(flower_points) != 1:
                raise RuntimeError("[DAILY_MENU_TARGET] 未能唯一识别花合战菜单项")
            self._stage = "opening_activity"
            self._click(flower_points[0])
            frame = self._wait_for(self._is_flower_page, "未能确认花合战页面")
        if self._reward_dialog_point(frame) is not None:
            raise RuntimeError("[DAILY_ENTRY_OVERLAY] 进入前已有奖励弹窗，停止以避免误清理")
        if not self._is_activity_page(frame):
            tasks = self._text_points(frame, self.TASK_TAB_ROI, "任务")
            if len(tasks) != 1:
                raise RuntimeError("[DAILY_TASK_TAB] 未唯一识别花合战任务标签")
            self._stage = "opening_tasks"
            self._click(tasks[0])
            frame = self._wait_for(self._is_activity_page, "未能确认花合战今日页")
        if self._reward_dialog_point(frame) is not None:
            raise RuntimeError("[DAILY_ENTRY_OVERLAY] 进入前已有奖励弹窗，停止以避免误清理")
        return frame

    def _classify_rewards(
        self,
        frame: np.ndarray,
    ) -> tuple[RewardState, int | None, tuple[int, int] | None]:
        """按领取按钮及今日经验区分可领、已领与未达条件。"""
        experience = self._daily_experience(frame)
        if experience is None:
            return RewardState.UNKNOWN, None, None
        claim_point = self._claim_button(frame)
        if claim_point is not None:
            return RewardState.CLAIMABLE, experience, claim_point
        state = RewardState.CLAIMED if experience > 0 else RewardState.NOT_ELIGIBLE
        return state, experience, None

    def _claim_button(self, frame: np.ndarray) -> tuple[int, int] | None:
        """只返回 OCR 唯一识别到的“全部领取”按钮位置。"""
        labels = self._labels(frame, self.CLAIM_ROI)
        combined = [(x, y) for x, y, text in labels if text == "全部领取"]
        all_labels = [(x, y) for x, y, text in labels if text == "全部"]
        claim_labels = [(x, y) for x, y, text in labels if text == "领取"]
        if combined:
            if len(combined) != 1 or all_labels or claim_labels:
                raise RuntimeError("[DAILY_CLAIM_AMBIGUOUS] 领取按钮 OCR 结果重复")
            return combined[0]
        if not all_labels and not claim_labels:
            return None
        if len(all_labels) != 1 or len(claim_labels) != 1:
            raise RuntimeError("[DAILY_CLAIM_AMBIGUOUS] 无法唯一识别领取按钮文字")
        all_x, all_y = all_labels[0]
        claim_x, claim_y = claim_labels[0]
        if abs(all_x - claim_x) > 30 or not 5 <= claim_y - all_y <= 45:
            raise RuntimeError("[DAILY_CLAIM_AMBIGUOUS] 领取按钮文字位置不一致")
        return (round((all_x + claim_x) / 2), round((all_y + claim_y) / 2))

    def _daily_experience(self, frame: np.ndarray) -> int | None:
        """读取今日获得经验数；字段缺失或无法解析时返回未知。"""
        labels = [
            text
            for _, _, text in self._labels(frame, self.EXPERIENCE_ROI)
            if text.startswith("今日获得经验")
        ]
        if len(labels) != 1:
            return None
        match = re.search(r"今日获得经验[:：]?\s*(\d+)", labels[0])
        return int(match.group(1)) if match else None

    def _clear_reward_dialog(self) -> None:
        """用通用结算点击器清理已识别弹窗，重复帧最多点击三次。"""
        for _ in range(self.REWARD_DISMISS_LIMIT):
            frame = self._read()
            point = self._reward_dialog_point(frame)
            if point is None:
                if not self._is_activity_page(frame):
                    self._note_known(False)
                    raise RuntimeError("[DAILY_REWARD_UNKNOWN] 奖励弹窗消失后页面未知")
                self._note_known(True)
                return
            self._note_known(True)
            self._check()
            self._on_battle_end(point)
            if self.observe_only:
                self._stage, self._outcome = "observing", "observing"
                raise _Stopped()
        frame = self._read()
        if self._reward_dialog_point(frame) is not None:
            self._note_known(True)
            raise RuntimeError("[DAILY_REWARD_LIMIT] 重复奖励弹窗超过清理上限")
        if not self._is_activity_page(frame):
            self._note_known(False)
            raise RuntimeError("[DAILY_REWARD_UNKNOWN] 奖励弹窗清理后页面未知")
        self._note_known(True)

    def _return_home(self, frame: np.ndarray) -> None:
        """点击已识别的返回控件，并重新识别庭院。"""
        if not self._is_activity_page(frame):
            raise RuntimeError("[DAILY_RETURN_PAGE] 返回前未确认花合战今日页")
        result = self.image_finder.best_match(
            frame,
            to_project_path(self.RETURN_BUTTON),
            0,
            0,
            100,
            80,
        )
        if result.similarity < 0.70 or result.point == (-1, -1):
            raise RuntimeError("[DAILY_RETURN_TARGET] 未确认花合战返回控件")
        self._stage = "returning_home"
        self._click(result.point)
        self._wait_for(self._is_home, "返回后未确认庭院")

    def _wait_for(
        self,
        predicate: Callable[[np.ndarray], bool],
        description: str,
    ) -> np.ndarray:
        """轮询新截图等待识别状态，超时或未知画面不重复输入。"""
        deadline = time.monotonic() + self.TRANSITION_SECONDS
        while time.monotonic() < deadline:
            frame = self._read()
            known = predicate(frame)
            self._note_known(known)
            if known:
                return frame
            self._stop_threading_event.wait(0.2)
        raise RuntimeError(f"[DAILY_TRANSITION] {description}")

    def _read(self) -> np.ndarray:
        """直接经环境获取新截图，不复用失败或过期缓存。"""
        self._check()
        try:
            image = self._runtime_env.capture_screen().convert("RGB")
        except Exception as exc:
            raise RuntimeError("[DAILY_CAPTURE] 无法获取当前游戏画面") from exc
        self._size = image.size
        if (
            image.width < 500
            or image.height < 300
            or abs(image.width / image.height - self.SIZE[0] / self.SIZE[1]) > 0.03
        ):
            raise RuntimeError("[DAILY_CAPTURE] 游戏客户区尺寸或比例未校准")
        frame = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        frame = cv2.resize(frame, self.SIZE)
        self.image_finder.screenshot_cache = frame
        return frame

    def _check(self) -> None:
        """在输入和截图前处理暂停、停止与保险丝。"""
        self.pause_point()
        if self._stop_threading_event.is_set():
            self._stage, self._outcome = "stopped", "stopped"
            raise _Stopped()
        if not self._run_guard.before_iteration():
            if getattr(self._run_guard.stop_reason, "value", None) == "emergency_stop":
                self._stage, self._outcome = "stopped", "stopped"
                raise _Stopped()
            raise RuntimeError(f"[DAILY_GUARD] 运行保险丝已停止：{self._run_guard.stop_reason}")

    def _click(self, point: tuple[int, int]) -> None:
        """经 guarded environment 点击识别位置；观察模式不发送真实输入。"""
        self._check()
        x, y = self._point(point)
        self._runtime_env.left_click(x, y)
        if self._run_guard.is_stopped:
            raise RuntimeError(f"[DAILY_GUARD] 输入预算已停止：{self._run_guard.stop_reason}")
        self._run_guard.allow_unknown_for(8)
        if self.observe_only:
            self._stage, self._outcome = "observing", "observing"
            raise _Stopped()

    def _point(self, point: tuple[int, int]) -> tuple[int, int]:
        """将基准帧识别坐标换算到当前客户区。"""
        return (
            round(point[0] * self._size[0] / self.SIZE[0]),
            round(point[1] * self._size[1] / self.SIZE[1]),
        )

    def _template_point(
        self,
        frame: np.ndarray,
        path: str,
        threshold: float,
    ) -> tuple[int, int] | None:
        """返回超过校准阈值的模板命中位置。"""
        match = self.image_finder.best_match(frame, to_project_path(path))
        return match.point if match.similarity >= threshold else None

    def _is_home(self, frame: np.ndarray) -> bool:
        """通过公共场景管理器识别庭院。"""
        detection = self.scene_manager.detect_current_scene(frame)
        return detection is not None and detection.scene_name == "home"

    def _is_activity_page(self, frame: np.ndarray) -> bool:
        """要求同时识别花合战标题和今日标签。"""
        title = self._text_points(frame, self.ACTIVITY_TITLE_ROI, "花合战")
        today = self._text_points(frame, self.TODAY_TAB_ROI, "今日")
        return len(title) == 1 and len(today) == 1

    def _is_flower_page(self, frame: np.ndarray) -> bool:
        return len(self._text_points(frame, self.ACTIVITY_TITLE_ROI, "花合战")) == 1

    def _reward_dialog_point(self, frame: np.ndarray) -> tuple[int, int] | None:
        """返回唯一“获得奖励”标题位置。"""
        points = self._text_points(frame, self.REWARD_TITLE_ROI, "获得奖励")
        if len(points) > 1:
            raise RuntimeError("[DAILY_REWARD_AMBIGUOUS] 奖励弹窗标题重复")
        return points[0] if points else None

    def _text_points(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
        target: str,
    ) -> list[tuple[int, int]]:
        return [
            (x, y)
            for x, y, text in self._labels(frame, roi)
            if text == target
        ]

    def _labels(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int],
    ) -> list[tuple[int, int, str]]:
        x0, y0, x1, y1 = roi
        return [
            (x + x0, y + y0, "".join(text.split()))
            for x, y, text, _ in self.ocr.find_all_text_positions(
                frame[y0:y1, x0:x1],
                0.88,
            )
        ]

    def _note_known(self, known: bool) -> None:
        """把本轮新截图的识别结果交给运行保险丝。"""
        self._run_guard.note_iteration(known)

    def bg_left_click(
        self,
        point: tuple[int, int],
        x_range: int = 0,
        y_range: int = 0,
    ) -> None:
        """让通用结算回调使用 OCR 已定位点，不再叠加随机偏移。"""
        self._click(point)

    def _should_count_battle_end(self, _point: tuple[int, int]) -> bool:
        """活跃度奖励弹窗不是战斗结算，不增加战斗计数。"""
        return False


if __name__ == "__main__":
    DailyActivityRewardsScript().run()
