# tests/common/environment/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple
from PIL import Image


class ActionType(Enum):
    """操作类型枚举"""
    LEFT_CLICK = "left_click"
    RIGHT_CLICK = "right_click"
    LEFT_DOUBLE_CLICK = "left_double_click"
    DRAG = "drag"
    KEY_PRESS = "key_press"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"


@dataclass
class ActionRecord:
    """操作记录数据类"""
    action_type: str
    x: int
    y: int
    timestamp: float
    extra: dict = field(default_factory=dict)


class GameEnvironment(ABC):
    """游戏环境抽象基类，封装所有与 Windows 系统交互的操作"""

    @abstractmethod
    def capture_screen(self) -> Image.Image:
        """截取当前游戏画面"""

    @abstractmethod
    def left_click(self, x: int, y: int) -> None:
        """鼠标左键点击"""

    @abstractmethod
    def right_click(self, x: int, y: int) -> None:
        """鼠标右键点击"""

    @abstractmethod
    def left_double_click(self, x: int, y: int) -> None:
        """鼠标左键双击"""

    @abstractmethod
    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """拖拽操作"""

    @abstractmethod
    def key_press(self, key_code: int) -> None:
        """按键按下并释放"""

    @abstractmethod
    def key_down(self, key_code: int) -> None:
        """按键按下"""

    @abstractmethod
    def key_up(self, key_code: int) -> None:
        """按键释放"""

    @abstractmethod
    def set_mouse_position(self, x: int, y: int) -> None:
        """设置鼠标位置"""

    @abstractmethod
    def get_window_client_rect(self) -> Tuple[int, int, int, int]:
        """获取窗口客户区矩形 (left, top, right, bottom)"""

    @abstractmethod
    def find_window(self, title_part: str) -> Optional[int]:
        """查找窗口句柄"""