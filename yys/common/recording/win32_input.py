"""只记录目标游戏窗口输入的 Windows 监听器。"""

from __future__ import annotations

import threading
from typing import Callable, Optional

import win32api
import win32con
import win32gui

MouseCallback = Callable[[str, int, int, Optional[int], Optional[int], str], None]
KeyboardCallback = Callable[[str, str], None]
StopCallback = Callable[[str], None]

_MOUSE_KEYS = {
    win32con.VK_LBUTTON,
    win32con.VK_RBUTTON,
    win32con.VK_MBUTTON,
    win32con.VK_XBUTTON1,
    win32con.VK_XBUTTON2,
}


class WindowsInputMonitor:
    """通过 `GetAsyncKeyState` 监听目标窗口内的人工输入。"""

    def __init__(
        self,
        hwnd: int,
        on_mouse: MouseCallback,
        on_keyboard: KeyboardCallback,
        on_stop: StopCallback,
        poll_interval: float = 0.01,
    ) -> None:
        """创建输入监听器。"""
        self._hwnd = hwnd
        self._on_mouse = on_mouse
        self._on_keyboard = on_keyboard
        self._on_stop = on_stop
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._mouse_starts: dict[int, tuple[int, int]] = {}

    def start(self) -> None:
        """启动后台监听线程。"""
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("输入监听器已经启动")
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="gameplay-input-monitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """停止监听并等待线程退出。"""
        self._stop_event.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        previous = {key: self._is_down(key) for key in range(1, 256)}
        while not self._stop_event.wait(self._poll_interval):
            foreground = win32gui.GetForegroundWindow() == self._hwnd
            for key in range(1, 256):
                current = self._is_down(key)
                was_down = previous[key]
                previous[key] = current
                if key == win32con.VK_F12 and current and not was_down:
                    self._on_stop("emergency_stop")
                    return
                if key in _MOUSE_KEYS and current != was_down:
                    self._handle_mouse_transition(key, was_down, current)
                elif foreground and current and not was_down:
                    self._on_keyboard("key_press", f"VK_{key}")

    def _handle_mouse_transition(
        self,
        key: int,
        was_down: bool,
        is_down: bool,
    ) -> None:
        if key not in {win32con.VK_LBUTTON, win32con.VK_RBUTTON}:
            return
        position = self._client_cursor_position()
        if is_down and not was_down:
            if position is not None:
                self._mouse_starts[key] = position
            return
        if not is_down and was_down:
            start = self._mouse_starts.pop(key, None)
            if start is None or position is None:
                return
            button = "left" if key == win32con.VK_LBUTTON else "right"
            if button == "left" and self._is_drag(start, position):
                self._on_mouse(
                    "drag",
                    start[0],
                    start[1],
                    position[0],
                    position[1],
                    button,
                )
                return
            action = "left_click" if button == "left" else "right_click"
            self._on_mouse(action, position[0], position[1], None, None, button)

    def _client_cursor_position(self) -> Optional[tuple[int, int]]:
        screen_position = win32api.GetCursorPos()
        x, y = win32gui.ScreenToClient(self._hwnd, screen_position)
        left, top, right, bottom = win32gui.GetClientRect(self._hwnd)
        if left <= x < right and top <= y < bottom:
            return x, y
        return None

    @staticmethod
    def _is_down(key: int) -> bool:
        return bool(win32api.GetAsyncKeyState(key) & 0x8000)

    @staticmethod
    def _is_drag(start: tuple[int, int], end: tuple[int, int]) -> bool:
        return abs(start[0] - end[0]) > 3 or abs(start[1] - end[1]) > 3
