# tests/common/recorders/action_recorder.py
import time
from .action_log import ActionLog, ActionRecord


class ActionRecorder:
    """操作记录器，包装操作并记录到 ActionLog"""

    def __init__(self, log: ActionLog):
        self._log = log

    def record_click(self, action_type: str, x: int, y: int, **extra) -> None:
        """记录点击操作"""
        self._log.add(ActionRecord(
            action_type=action_type,
            x=x,
            y=y,
            timestamp=time.time(),
            extra=extra
        ))

    def record_key(self, action_type: str, key_code: int) -> None:
        """记录键盘操作"""
        self._log.add(ActionRecord(
            action_type=action_type,
            x=-1,
            y=-1,
            timestamp=time.time(),
            extra={"key_code": key_code}
        ))