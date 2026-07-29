"""游戏运行环境抽象。"""

from .base import ActionRecord, ActionType, GameEnvironment
from .guarded import GuardedEnvironment, RunGuard, RunStopReason
from .windows import WindowsEnvironment

__all__ = [
    "ActionRecord",
    "ActionType",
    "GameEnvironment",
    "GuardedEnvironment",
    "RunGuard",
    "RunStopReason",
    "WindowsEnvironment",
]
