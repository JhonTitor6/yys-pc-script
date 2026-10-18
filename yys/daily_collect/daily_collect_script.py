"""按已确认页面领取庭院事务奖励并返回庭院。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from win_util.environment.base import GameEnvironment
from win_util.environment.guarded import GuardedEnvironment, RunGuard, RunStopReason
from win_util.environment.windows import WindowsEnvironment
from win_util.image import to_project_path
from yys.common.event_script_base import YYSBaseScript
from yys.common.script_meta import ScriptMeta


class _Stopped(Exception):
    """用户或保险丝请求停止。"""


class _Observed(Exception):
    """观察模式已记录一步计划动作。"""


class DailyCollectScript(YYSBaseScript):
    """从庭院打开一键收菜，只点击一次并确认完成后回庭院。"""

    SCRIPT_META = ScriptMeta("官方一键收菜", "日常", None, {})
    SIZE = (1136, 640)
    WAIT_TIMEOUT = 20.0
    POLL_INTERVAL = 0.2
    UNKNOWN_GRACE_SECONDS = 8.0
    HOME_MARKER = "yys/common/images/scene/home.bmp"
    SUCCESS_DISMISS_OFFSET = (429, 37)

    def __init__(
        self,
        script_name: str = "daily_collect",
        config: dict | None = None,
        env: GameEnvironment | None = None,
    ) -> None:
        """复用现有环境、图像识别与保险丝；配置不暴露额外选项。"""
        actual = env if env is not None else WindowsEnvironment()
        guard = actual.guard if isinstance(actual, GuardedEnvironment) else RunGuard(
            timeout_seconds=90,
            max_actions=4,
            unknown_limit=3,
        )
        guarded = actual if isinstance(actual, GuardedEnvironment) else GuardedEnvironment(
            actual,
            guard,
            observe_only=False,
        )
        super().__init__(script_name, config=config, env=guarded)
        self.set_run_guard(guard)
        self._images = Path(to_project_path("yys/daily_collect/images"))
        for name in (
            "home_entry",
            "home_lantern",
            "home_lantern_sakura",
            "task_title",
            "collect_button",
            "success_popup_title",
            "success_banner",
            "completed_stamp",
            "home_button",
        ):
            if cv2.imread(str(self._images / f"{name}.png")) is None:
                raise FileNotFoundError(f"官方一键收菜模板缺失或不可读: {name}")
        self._size = self.SIZE
        self._stage = "initial"
        self._outcome = "pending"
        self._collect_sent = False

    def on_run(self) -> None:
        """重置本轮业务标志。"""
        super().on_run()
        self._stage = "initial"
        self._outcome = "pending"
        self._collect_sent = False

    def get_state_snapshot(self) -> dict[str, object]:
        """公开单次收菜的可观察结果。"""
        return {
            **super().get_state_snapshot(),
            "stage": self._stage,
            "outcome": self._outcome,
            "flow_complete": self._outcome == "completed",
        }

    def run(self) -> None:
        """领取任务奖励；只有识别成功并重新确认庭院后才正常返回。"""
        self.on_run()
        try:
            frame = self._read()
            if not self._is_home(frame):
                raise RuntimeError("[DAILY_COLLECT_ENTRY] 请从已识别的庭院启动一键收菜")
            entry = self._match(frame, "home_entry")
            if entry is None:
                raise RuntimeError("[DAILY_COLLECT_ENTRY] 未确认庭院事务入口")
            self._stage = "opening"
            self._click(entry)

            self._stage = "waiting_tasks"
            frame = self._wait(
                lambda current: self._is_task_page(current)
                and (
                    self._has_completed_stamp(current)
                    or self._match(current, "collect_button") is not None
                ),
                "未确认庭院事务的一键完成按钮",
            )
            if self._has_completed_stamp(frame):
                raise RuntimeError(
                    "[DAILY_COLLECT_PREEXISTING] 启动时已有完成标记，无法确认待领取状态"
                )
            if self._collect_sent:
                raise RuntimeError("[DAILY_COLLECT_REPEAT] 本轮已经发送一键完成")
            button = self._match(frame, "collect_button")
            if button is None:
                raise RuntimeError("[DAILY_COLLECT_BUTTON] 未确认一键完成按钮")
            self._collect_sent = True
            self._stage = "collecting"
            self._click(button)

            self._stage = "waiting_result"
            frame = self._wait(
                lambda current: self._has_success_popup(current)
                or self._has_success_evidence(current),
                "未出现领取成功或已完成信号",
            )
            if self._has_success_popup(frame):
                self._stage = "closing_success"
                point = self._dismiss_point(frame)
                if point is None:
                    raise RuntimeError("[DAILY_COLLECT_POPUP] 未确认领取成功弹层关闭位置")
                self._click(point)
                self._stage = "verifying_result"
                frame = self._wait(
                    self._has_success_evidence,
                    "关闭领取弹层后未确认任务完成",
                )
            if not self._has_success_evidence(frame):
                raise RuntimeError("[DAILY_COLLECT_RESULT] 未确认任务领取成功")
            self._stage = "returning_home"
            home_button = self._match(frame, "home_button")
            if home_button is None:
                raise RuntimeError("[DAILY_COLLECT_RETURN] 未确认页头庭院按钮")
            self._click(home_button)
            self._wait(self._is_home, "领取完成后未确认返回庭院")
            self._stage = "done"
            self._outcome = "completed"
            self.logger.success("官方一键收菜已领取并确认返回庭院")
        except _Observed:
            self._stage = "observing"
            self._outcome = "observing"
            raise RuntimeError("[DAILY_COLLECT_OBSERVE] 观察模式只记录一步计划动作") from None
        except _Stopped:
            self._stage = "stopped"
            self._outcome = "stopped"
            raise RuntimeError("[DAILY_COLLECT_STOP] 用户停止了一键收菜") from None
        except Exception:
            self._stage = "failed"
            self._outcome = "failed"
            raise

    def _check(self) -> None:
        """在截图和输入前处理暂停、停止及运行保险丝。"""
        self.pause_point()
        if self._stop_threading_event.is_set():
            raise _Stopped()
        if self._run_guard is not None and not self._run_guard.before_iteration():
            if self._run_guard.stop_reason is RunStopReason.EMERGENCY_STOP:
                raise _Stopped()
            raise RuntimeError("[DAILY_COLLECT_GUARD] 运行保险丝已停止")

    def _read(self) -> np.ndarray:
        """每次从注入环境获取新帧并归一到录制客户区。"""
        self._check()
        image = self._env.capture_screen().convert("RGB")
        self._size = image.size
        expected_ratio = self.SIZE[0] / self.SIZE[1]
        if image.width < 500 or abs(image.width / image.height - expected_ratio) > 0.03:
            raise RuntimeError("[DAILY_COLLECT_CAPTURE] 客户区尺寸或比例不受支持")
        frame = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        if frame.shape[1::-1] != self.SIZE:
            frame = cv2.resize(frame, self.SIZE)
        self.image_finder.screenshot_cache = frame
        return frame

    def _click(self, point: tuple[int, int]) -> None:
        """输入只使用已识别目标，且观察模式不向底层环境发送输入。"""
        self._check()
        x, y = point
        if not (0 <= x < self.SIZE[0] and 0 <= y < self.SIZE[1]):
            raise RuntimeError("[DAILY_COLLECT_COORDINATE] 识别目标超出客户区")
        self._env.left_click(
            round(x * self._size[0] / self.SIZE[0]),
            round(y * self._size[1] / self.SIZE[1]),
        )
        if self._env.observe_only:
            raise _Observed()
        if self._run_guard is not None:
            if self._run_guard.is_stopped:
                raise RuntimeError("[DAILY_COLLECT_GUARD] 点击未获保险丝许可")
            self._run_guard.allow_unknown_for(self.UNKNOWN_GRACE_SECONDS)

    def _wait(self, predicate: Callable[[np.ndarray], bool], failure: str) -> np.ndarray:
        """只重拍和等待，不重发之前的输入。"""
        deadline = time.monotonic() + self.WAIT_TIMEOUT
        while True:
            frame = self._read()
            if predicate(frame):
                if self._run_guard is not None:
                    self._run_guard.note_iteration(True)
                return frame
            if self._run_guard is not None:
                self._run_guard.note_iteration(self._is_known(frame))
                if self._run_guard.is_stopped:
                    raise RuntimeError("[DAILY_COLLECT_GUARD] 连续未知画面触发保险丝")
            if time.monotonic() >= deadline:
                raise RuntimeError(f"[DAILY_COLLECT_TRANSITION] {failure}")
            self._stop_threading_event.wait(self.POLL_INTERVAL)

    def _match(self, frame: np.ndarray, name: str) -> tuple[int, int] | None:
        """使用项目现有图像匹配器识别本流程模板。"""
        path = self._images / f"{name}.png"
        result = self.image_finder.best_match(frame, str(path))
        threshold = 0.80 if name == "home_button" else 0.90
        return result.point if result.similarity >= threshold else None

    def _home_marker(self, frame: np.ndarray) -> tuple[int, int] | None:
        """匹配公共庭院场景标记，配合入口模板避免误认其他页面。"""
        result = self.image_finder.best_match(
            frame,
            to_project_path(self.HOME_MARKER),
        )
        return result.point if result.similarity >= 0.72 else None

    def _is_home(self, frame: np.ndarray) -> bool:
        """公共庭院标记与一个真实庭院皮肤灯笼同时出现才确认庭院。"""
        return self._home_marker(frame) is not None and any(
            self._match(frame, name) is not None
            for name in ("home_lantern", "home_lantern_sakura")
        )

    def _is_task_page(self, frame: np.ndarray) -> bool:
        """确认庭院事务标题。"""
        return self._match(frame, "task_title") is not None

    def _has_success_popup(self, frame: np.ndarray) -> bool:
        """确认领取成功弹层标题。"""
        return self._match(frame, "success_popup_title") is not None

    def _has_success_evidence(self, frame: np.ndarray) -> bool:
        """确认领取成功横幅或事务页的已完成印章。"""
        return self._match(frame, "success_banner") is not None or (
            self._is_task_page(frame)
            and self._has_completed_stamp(frame)
        )

    def _has_completed_stamp(self, frame: np.ndarray) -> bool:
        """匹配庭院事务列表中的已完成印章。"""
        return self._match(frame, "completed_stamp") is not None

    def _dismiss_point(self, frame: np.ndarray) -> tuple[int, int] | None:
        """仅在领取成功标题命中后，按录制确认的相对空白位置计算关闭点。"""
        anchor = self._match(frame, "success_popup_title")
        if anchor is None:
            return None
        return (
            anchor[0] + self.SUCCESS_DISMISS_OFFSET[0],
            anchor[1] + self.SUCCESS_DISMISS_OFFSET[1],
        )

    def _is_known(self, frame: np.ndarray) -> bool:
        """用于保险丝统计已识别场景，不将未知画面当作完成。"""
        return (
            self._is_home(frame)
            or self._is_task_page(frame)
            or self._has_success_popup(frame)
            or self._has_success_evidence(frame)
        )
