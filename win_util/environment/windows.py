"""Windows 真实游戏环境。"""

from __future__ import annotations

from ctypes import windll
from typing import Literal, Optional, Tuple

import win32api
import win32con
import win32gui
import win32ui
from PIL import Image, ImageGrab

from .base import GameEnvironment

CaptureMode = Literal["print_window", "foreground"]


class WindowsEnvironment(GameEnvironment):
    """通过 Win32 消息和客户区截图操作真实游戏窗口。"""

    def __init__(
        self,
        hwnd: Optional[int] = None,
        window_title: str = "阴阳师",
        capture_mode: CaptureMode = "print_window",
    ) -> None:
        """创建 Windows 环境并解析目标窗口。"""
        if capture_mode not in ("print_window", "foreground"):
            raise ValueError(f"不支持的截图模式: {capture_mode}")
        self._hwnd = hwnd or self.find_window(window_title)
        if self._hwnd is None:
            raise RuntimeError(f"未找到标题包含 {window_title!r} 的游戏窗口")
        self._capture_mode = capture_mode

    @property
    def hwnd(self) -> int:
        """返回已经校验的窗口句柄。"""
        return self._hwnd

    def capture_screen(self) -> Image.Image:
        """按照配置的模式截取目标窗口客户区。"""
        if self._capture_mode == "foreground":
            return self._capture_foreground_client()
        return self._capture_print_window_client()

    def activate_window(self) -> None:
        """恢复并激活目标游戏窗口，供交互式录制使用。"""
        try:
            if win32gui.IsIconic(self._hwnd):
                win32gui.ShowWindow(self._hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self._hwnd)
        except Exception as exc:
            title = win32gui.GetWindowText(self._hwnd)
            raise RuntimeError(
                f"激活游戏窗口失败: hwnd={self._hwnd}, title={title!r}, cause={exc!r}"
            ) from exc

    def _capture_foreground_client(self) -> Image.Image:
        """从桌面截取当前处于前台的游戏客户区。"""
        if win32gui.GetForegroundWindow() != self._hwnd:
            raise RuntimeError("录制画面要求游戏窗口位于前台")
        left, top, right, bottom = win32gui.GetClientRect(self._hwnd)
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            raise RuntimeError(f"游戏客户区尺寸无效: {width}x{height}")
        screen_left, screen_top = win32gui.ClientToScreen(self._hwnd, (left, top))
        screen_right, screen_bottom = win32gui.ClientToScreen(
            self._hwnd,
            (right, bottom),
        )
        image = ImageGrab.grab(
            bbox=(screen_left, screen_top, screen_right, screen_bottom),
            all_screens=True,
        ).convert("RGB")
        if image.size != (width, height):
            raise RuntimeError(
                f"游戏客户区截图尺寸异常: {(width, height)} → {image.size}"
            )
        return image

    def _capture_print_window_client(self) -> Image.Image:
        """使用 `PrintWindow(PW_CLIENTONLY)` 截取客户区。"""
        left, top, right, bottom = win32gui.GetClientRect(self._hwnd)
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            raise RuntimeError(f"游戏客户区尺寸无效: {width}x{height}")

        window_dc = win32gui.GetDC(self._hwnd)
        source_dc = win32ui.CreateDCFromHandle(window_dc)
        target_dc = source_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        target_dc.SelectObject(bitmap)
        try:
            rendered = windll.user32.PrintWindow(
                self._hwnd,
                target_dc.GetSafeHdc(),
                1,
            )
            if not rendered:
                target_dc.BitBlt(
                    (0, 0),
                    (width, height),
                    source_dc,
                    (0, 0),
                    win32con.SRCCOPY,
                )
            info = bitmap.GetInfo()
            bits = bitmap.GetBitmapBits(True)
            return Image.frombuffer(
                "RGB",
                (info["bmWidth"], info["bmHeight"]),
                bits,
                "raw",
                "BGRX",
                0,
                1,
            ).copy()
        finally:
            win32gui.DeleteObject(bitmap.GetHandle())
            target_dc.DeleteDC()
            source_dc.DeleteDC()
            win32gui.ReleaseDC(self._hwnd, window_dc)

    def left_click(self, x: int, y: int) -> None:
        """发送客户区左键点击。"""
        position = win32api.MAKELONG(x, y)
        win32api.SendMessage(
            self._hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, position
        )
        win32api.SendMessage(self._hwnd, win32con.WM_LBUTTONUP, 0, position)

    def right_click(self, x: int, y: int) -> None:
        """发送客户区右键点击。"""
        position = win32api.MAKELONG(x, y)
        win32api.SendMessage(
            self._hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, position
        )
        win32api.SendMessage(self._hwnd, win32con.WM_RBUTTONUP, 0, position)

    def left_double_click(self, x: int, y: int) -> None:
        """发送客户区左键双击。"""
        position = win32api.MAKELONG(x, y)
        win32api.SendMessage(
            self._hwnd, win32con.WM_LBUTTONDBLCLK, win32con.MK_LBUTTON, position
        )
        win32api.SendMessage(self._hwnd, win32con.WM_LBUTTONUP, 0, position)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """发送一组客户区拖拽消息。"""
        start = win32api.MAKELONG(x1, y1)
        end = win32api.MAKELONG(x2, y2)
        win32api.SendMessage(
            self._hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, start
        )
        win32api.SendMessage(
            self._hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, end
        )
        win32api.SendMessage(self._hwnd, win32con.WM_LBUTTONUP, 0, end)

    def key_press(self, key_code: int) -> None:
        """发送一次按键。"""
        self.key_down(key_code)
        self.key_up(key_code)

    def key_down(self, key_code: int) -> None:
        """发送按键按下。"""
        win32api.SendMessage(self._hwnd, win32con.WM_KEYDOWN, key_code, 0)

    def key_up(self, key_code: int) -> None:
        """发送按键释放。"""
        win32api.SendMessage(self._hwnd, win32con.WM_KEYUP, key_code, 0)

    def set_mouse_position(self, x: int, y: int) -> None:
        """设置桌面鼠标位置。"""
        win32api.SetCursorPos((x, y))

    def get_window_client_rect(self) -> Tuple[int, int, int, int]:
        """返回客户区矩形。"""
        return win32gui.GetClientRect(self._hwnd)

    def find_window(self, title_part: str) -> Optional[int]:
        """查找标题包含指定文本的顶层窗口。"""
        matches: list[tuple[int, int]] = []

        def collect(hwnd: int, _: object) -> bool:
            title = win32gui.GetWindowText(hwnd)
            # 工作台标题也包含“阴阳师”，不能被当成游戏窗口激活和截图。
            if title == "阴阳师脚本工作台" or title_part not in title:
                return True
            # 已知游戏标题优先于所有模糊匹配，避免浏览器页面标题抢先命中。
            if title == "阴阳师-网易游戏":
                priority = 0
            elif title == title_part:
                priority = 1
            elif title.startswith(title_part):
                priority = 2
            else:
                priority = 3
            matches.append((priority, hwnd))
            return True

        win32gui.EnumWindows(collect, None)
        return min(matches, key=lambda item: item[0])[1] if matches else None
