"""为真实运行提供动作、时间和未知画面保险丝。"""

from __future__ import annotations

import time
from enum import Enum
from typing import Callable, Optional, Tuple

from PIL import Image

from .base import ActionRecord, ActionType, GameEnvironment


class RunStopReason(str, Enum):
    """受保护运行的停机原因。"""

    TIMEOUT = "timeout"
    ACTION_LIMIT = "action_limit"
    UNKNOWN_SCENE = "unknown_scene"
    EMERGENCY_STOP = "emergency_stop"


class RunGuard:
    """跟踪单次真实运行的安全预算。"""

    def __init__(
        self,
        timeout_seconds: float = 180.0,
        max_actions: int = 30,
        unknown_limit: int = 3,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """创建运行保险丝并立即开始计时。"""
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须为正数")
        if max_actions <= 0:
            raise ValueError("max_actions 必须为正数")
        if unknown_limit <= 0:
            raise ValueError("unknown_limit 必须为正数")
        self.timeout_seconds = timeout_seconds
        self.max_actions = max_actions
        self.unknown_limit = unknown_limit
        self._monotonic = monotonic
        self._started_at = monotonic()
        self._unknown_grace_until = self._started_at
        self._unknown_grace_armed_in_iteration = False
        self.action_count = 0
        self.consecutive_unknown = 0
        self.stop_reason: Optional[RunStopReason] = None

    @property
    def is_stopped(self) -> bool:
        """返回是否已触发保险丝，并同步检查超时。"""
        self._check_timeout()
        return self.stop_reason is not None

    @property
    def elapsed_seconds(self) -> float:
        """返回本次运行已持续的秒数。"""
        return max(0.0, self._monotonic() - self._started_at)

    def before_iteration(self) -> bool:
        """在新一轮识别前检查是否仍允许继续。"""
        return not self.is_stopped

    def allow_action(self) -> bool:
        """为一个逻辑动作申请预算。"""
        if self.is_stopped:
            return False
        if self.action_count >= self.max_actions:
            self._stop(RunStopReason.ACTION_LIMIT)
            return False
        self.action_count += 1
        return True

    def allow_unknown_for(self, seconds: float) -> None:
        """在当前已识别事件回调中，为动作后的画面过渡设置未知宽限。"""
        if seconds <= 0:
            raise ValueError("未知画面宽限秒数必须为正数")
        self._unknown_grace_until = max(
            self._unknown_grace_until,
            self._monotonic() + seconds,
        )
        self._unknown_grace_armed_in_iteration = True
        self.consecutive_unknown = 0

    def note_iteration(self, recognized: bool) -> None:
        """记录本轮是否识别到已注册事件。"""
        if self.is_stopped:
            return
        if recognized:
            self.consecutive_unknown = 0
            if self._unknown_grace_armed_in_iteration:
                # 当前识别事件触发了宽限，不应把自己的回执当作后续恢复信号。
                self._unknown_grace_armed_in_iteration = False
                return
            self._unknown_grace_until = self._monotonic()
            return
        self._unknown_grace_armed_in_iteration = False
        if self._monotonic() < self._unknown_grace_until:
            self.consecutive_unknown = 0
            return
        self.consecutive_unknown += 1
        if self.consecutive_unknown >= self.unknown_limit:
            self._stop(RunStopReason.UNKNOWN_SCENE)

    def request_emergency_stop(self) -> None:
        """由人工快捷键触发紧急停止。"""
        self._stop(RunStopReason.EMERGENCY_STOP)

    def snapshot(self) -> dict[str, object]:
        """返回可用于日志和测试的安全状态。"""
        return {
            "elapsed_seconds": self.elapsed_seconds,
            "action_count": self.action_count,
            "max_actions": self.max_actions,
            "consecutive_unknown": self.consecutive_unknown,
            "unknown_limit": self.unknown_limit,
            "unknown_grace_remaining_seconds": max(
                0.0,
                self._unknown_grace_until - self._monotonic(),
            ),
            "stop_reason": self.stop_reason.value if self.stop_reason else None,
        }

    def _check_timeout(self) -> None:
        if self.stop_reason is None and self.elapsed_seconds >= self.timeout_seconds:
            self._stop(RunStopReason.TIMEOUT)

    def _stop(self, reason: RunStopReason) -> None:
        if self.stop_reason is None:
            self.stop_reason = reason


class GuardedEnvironment(GameEnvironment):
    """在真实环境外包一层可观察、可截停的动作代理。"""

    def __init__(
        self,
        delegate: GameEnvironment,
        guard: RunGuard,
        observe_only: bool = True,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        """创建环境代理；观察模式只记录计划动作，不向窗口发送输入。"""
        self._delegate = delegate
        self.guard = guard
        self.observe_only = observe_only
        self._wall_clock = wall_clock
        self.action_records: list[ActionRecord] = []

    def capture_screen(self) -> Image.Image:
        """从真实环境截取目标客户区。"""
        return self._delegate.capture_screen()

    def left_click(self, x: int, y: int) -> None:
        """在预算允许时执行或记录左键点击。"""
        self._perform(ActionType.LEFT_CLICK.value, x, y, self._delegate.left_click)

    def right_click(self, x: int, y: int) -> None:
        """在预算允许时执行或记录右键点击。"""
        self._perform(ActionType.RIGHT_CLICK.value, x, y, self._delegate.right_click)

    def left_double_click(self, x: int, y: int) -> None:
        """在预算允许时执行或记录左键双击。"""
        self._perform(
            ActionType.LEFT_DOUBLE_CLICK.value,
            x,
            y,
            self._delegate.left_double_click,
        )

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """在预算允许时执行或记录一次逻辑拖拽。"""
        self._perform(
            ActionType.DRAG.value,
            x1,
            y1,
            lambda start_x, start_y: self._delegate.drag(
                start_x,
                start_y,
                x2,
                y2,
            ),
            {"end_x": x2, "end_y": y2},
        )

    def wheel(self, x: int, y: int, delta: int) -> None:
        """一次滚轮消耗一个逻辑动作；观察模式只记下位置和增量。"""
        self._perform(
            ActionType.WHEEL.value, x, y,
            lambda px, py: self._delegate.wheel(px, py, delta),
            {"wheel_delta": delta},
        )

    def key_press(self, key_code: int) -> None:
        """在预算允许时执行或记录一次按键。"""
        self._perform_key(ActionType.KEY_PRESS.value, key_code, self._delegate.key_press)

    def key_down(self, key_code: int) -> None:
        """在预算允许时执行或记录按键按下。"""
        self._perform_key(ActionType.KEY_DOWN.value, key_code, self._delegate.key_down)

    def key_up(self, key_code: int) -> None:
        """在预算允许时执行或记录按键释放。"""
        self._perform_key(ActionType.KEY_UP.value, key_code, self._delegate.key_up)

    def set_mouse_position(self, x: int, y: int) -> None:
        """在预算允许时执行或记录桌面鼠标移动。"""
        self._perform("set_mouse_position", x, y, self._delegate.set_mouse_position)

    def get_window_client_rect(self) -> Tuple[int, int, int, int]:
        """返回真实游戏窗口的客户区矩形。"""
        return self._delegate.get_window_client_rect()

    def find_window(self, title_part: str) -> Optional[int]:
        """委托真实环境查找窗口。"""
        return self._delegate.find_window(title_part)

    def _perform(
        self,
        action_type: str,
        x: int,
        y: int,
        operation: Callable[[int, int], None],
        extra: Optional[dict[str, object]] = None,
    ) -> None:
        if not self.guard.allow_action():
            return
        self.action_records.append(
            ActionRecord(
                action_type=action_type,
                x=x,
                y=y,
                timestamp=self._wall_clock(),
                extra=dict(extra or {}),
            )
        )
        if not self.observe_only:
            operation(x, y)

    def _perform_key(
        self,
        action_type: str,
        key_code: int,
        operation: Callable[[int], None],
    ) -> None:
        if not self.guard.allow_action():
            return
        self.action_records.append(
            ActionRecord(
                action_type=action_type,
                x=-1,
                y=-1,
                timestamp=self._wall_clock(),
                extra={"key_code": key_code},
            )
        )
        if not self.observe_only:
            operation(key_code)
