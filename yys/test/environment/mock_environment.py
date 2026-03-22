# yys/test/environment/mock_environment.py
from PIL import Image
from typing import Optional, Tuple
import time

from .base import GameEnvironment, ActionType, ActionRecord
from ..providers.file_image_provider import FileImageProvider
from ..recorders.action_recorder import ActionRecorder
from ..recorders.action_log import ActionLog


class MockEnvironment(GameEnvironment):
    """Mock 测试环境，不依赖真实游戏窗口"""

    def __init__(
        self,
        image_provider: Optional[FileImageProvider] = None,
        action_log: Optional[ActionLog] = None
    ):
        self._image_provider = image_provider or FileImageProvider()
        self._action_log = action_log or ActionLog()
        self._recorder = ActionRecorder(self._action_log)
        self._window_rect: Tuple[int, int, int, int] = (0, 0, 1154, 680)
        self._hwnd: Optional[int] = None

    @property
    def action_log(self) -> ActionLog:
        """获取操作日志"""
        return self._action_log

    @property
    def image_provider(self) -> FileImageProvider:
        """获取图片提供者"""
        return self._image_provider

    def capture_screen(self) -> Image.Image:
        """截取当前游戏画面（从文件加载）"""
        return self._image_provider.get_current_image()

    def left_click(self, x: int, y: int) -> None:
        """鼠标左键点击"""
        self._recorder.record_click(ActionType.LEFT_CLICK.value, x, y)

    def right_click(self, x: int, y: int) -> None:
        """鼠标右键点击"""
        self._recorder.record_click(ActionType.RIGHT_CLICK.value, x, y)

    def left_double_click(self, x: int, y: int) -> None:
        """鼠标左键双击"""
        self._recorder.record_click(ActionType.LEFT_DOUBLE_CLICK.value, x, y)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """拖拽操作"""
        self._action_log.add(ActionRecord(
            action_type=ActionType.DRAG.value,
            x=x1,
            y=y1,
            timestamp=time.time(),
            extra={"end_x": x2, "end_y": y2}
        ))

    def key_press(self, key_code: int) -> None:
        """按键按下并释放"""
        self._recorder.record_key(ActionType.KEY_PRESS.value, key_code)

    def key_down(self, key_code: int) -> None:
        """按键按下"""
        self._recorder.record_key(ActionType.KEY_DOWN.value, key_code)

    def key_up(self, key_code: int) -> None:
        """按键释放"""
        self._recorder.record_key(ActionType.KEY_UP.value, key_code)

    def set_mouse_position(self, x: int, y: int) -> None:
        """设置鼠标位置（Mock 环境不需要真实移动）"""
        pass

    def get_window_client_rect(self) -> Tuple[int, int, int, int]:
        """获取窗口客户区矩形"""
        return self._window_rect

    def find_window(self, title_part: str) -> Optional[int]:
        """查找窗口句柄（Mock 返回固定值）"""
        self._hwnd = 12345
        return self._hwnd
