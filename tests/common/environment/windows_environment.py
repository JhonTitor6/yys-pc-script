# tests/common/environment/windows_environment.py
from PIL import Image
from typing import Optional, Tuple
import win32gui
import win32con
import win32api
import win32ui

from .base import GameEnvironment


class WindowsEnvironment(GameEnvironment):
    """Windows 生产环境，执行真实的窗口操作"""

    def __init__(self, hwnd: Optional[int] = None):
        self._hwnd = hwnd
        if self._hwnd is None:
            self._hwnd = win32gui.FindWindow(None, "阴阳师")

    @property
    def hwnd(self) -> Optional[int]:
        """获取窗口句柄"""
        return self._hwnd

    def capture_screen(self) -> Image.Image:
        """截取当前游戏画面"""
        left, top, right, bottom = win32gui.GetClientRect(self._hwnd)
        w, h = right - left, bottom - top
        hwnd_dc = win32gui.GetWindowDC(self._hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(save_bitmap)
        win32gui.BitBlt(save_dc, 0, 0, w, h, mfc_dc, 0, 0, win32con.SRCCOPY)
        bmpinfo = save_bitmap.GetInfo()
        bmpstr = save_bitmap.GetBitmapBits(True)
        img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)
        win32gui.DeleteObject(save_bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(self._hwnd, hwnd_dc)
        return img

    def left_click(self, x: int, y: int) -> None:
        """鼠标左键点击"""
        long_position = win32api.MAKELONG(x, y)
        win32api.SendMessage(self._hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, long_position)
        win32api.SendMessage(self._hwnd, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON, long_position)

    def right_click(self, x: int, y: int) -> None:
        """鼠标右键点击"""
        long_position = win32api.MAKELONG(x, y)
        win32api.SendMessage(self._hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, long_position)
        win32api.SendMessage(self._hwnd, win32con.WM_RBUTTONUP, win32con.MK_RBUTTON, long_position)

    def left_double_click(self, x: int, y: int) -> None:
        """鼠标左键双击"""
        long_position = win32api.MAKELONG(x, y)
        win32api.SendMessage(self._hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, long_position)
        win32api.SendMessage(self._hwnd, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON, long_position)
        win32api.SendMessage(self._hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, long_position)
        win32api.SendMessage(self._hwnd, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON, long_position)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """拖拽操作"""
        win32api.SetCursorPos((x1, y1))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.SetCursorPos((x2, y2))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def key_press(self, key_code: int) -> None:
        """按键按下并释放"""
        win32api.SendMessage(self._hwnd, win32con.WM_KEYDOWN, key_code, 0)
        win32api.SendMessage(self._hwnd, win32con.WM_KEYUP, key_code, 0)

    def key_down(self, key_code: int) -> None:
        """按键按下"""
        win32api.SendMessage(self._hwnd, win32con.WM_KEYDOWN, key_code, 0)

    def key_up(self, key_code: int) -> None:
        """按键释放"""
        win32api.SendMessage(self._hwnd, win32con.WM_KEYUP, key_code, 0)

    def set_mouse_position(self, x: int, y: int) -> None:
        """设置鼠标位置"""
        win32api.SetCursorPos((x, y))

    def get_window_client_rect(self) -> Tuple[int, int, int, int]:
        """获取窗口客户区矩形"""
        return win32gui.GetClientRect(self._hwnd)

    def find_window(self, title_part: str) -> Optional[int]:
        """查找窗口句柄"""
        return win32gui.FindWindow(None, title_part)