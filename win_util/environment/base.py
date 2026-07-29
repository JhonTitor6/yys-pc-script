"""游戏环境公共合约。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Tuple

from PIL import Image


class ActionType(Enum):
    """环境支持的逻辑输入动作类型。"""

    LEFT_CLICK = "left_click"
    RIGHT_CLICK = "right_click"
    LEFT_DOUBLE_CLICK = "left_double_click"
    DRAG = "drag"
    KEY_PRESS = "key_press"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"


@dataclass
class ActionRecord:
    """一条可用于断言或回放的逻辑输入记录。"""

    action_type: str
    x: int
    y: int
    timestamp: float
    extra: dict[str, Any] = field(default_factory=dict)


class GameEnvironment(ABC):
    """封装截图与输入操作的运行环境。"""

    @abstractmethod
    def capture_screen(self) -> Image.Image:
        """截取目标游戏客户区。"""

    @abstractmethod
    def left_click(self, x: int, y: int) -> None:
        """在客户区坐标执行左键点击。"""

    @abstractmethod
    def right_click(self, x: int, y: int) -> None:
        """在客户区坐标执行右键点击。"""

    @abstractmethod
    def left_double_click(self, x: int, y: int) -> None:
        """在客户区坐标执行左键双击。"""

    @abstractmethod
    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """在客户区坐标执行拖拽。"""

    @abstractmethod
    def key_press(self, key_code: int) -> None:
        """按下并释放一个按键。"""

    @abstractmethod
    def key_down(self, key_code: int) -> None:
        """按下一个按键。"""

    @abstractmethod
    def key_up(self, key_code: int) -> None:
        """释放一个按键。"""

    @abstractmethod
    def set_mouse_position(self, x: int, y: int) -> None:
        """设置桌面鼠标位置。"""

    @abstractmethod
    def get_window_client_rect(self) -> Tuple[int, int, int, int]:
        """返回客户区矩形 `(left, top, right, bottom)`。"""

    @abstractmethod
    def find_window(self, title_part: str) -> Optional[int]:
        """按标题片段查找窗口句柄。"""
