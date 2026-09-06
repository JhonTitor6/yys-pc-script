"""只记录目标游戏窗口输入的 Windows 监听器。"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable, Optional

import win32api
import win32con
import win32gui

MouseCallback = Callable[[str, int, int, Optional[int], Optional[int], str], None]
KeyboardCallback = Callable[[str, str], None]
StopCallback = Callable[[str], None]
WheelCallback = Callable[[int, int, int], None]


class _MouseHookData(ctypes.Structure):
    """Windows MSLLHOOKSTRUCT，最后一项使用指针宽度。"""

    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


_HookProc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SetWindowsHookExW.argtypes = [ctypes.c_int, _HookProc, wintypes.HINSTANCE, wintypes.DWORD]
_user32.SetWindowsHookExW.restype = wintypes.HANDLE
_user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
_user32.CallNextHookEx.restype = ctypes.c_ssize_t
_user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
_user32.UnhookWindowsHookEx.restype = wintypes.BOOL

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
        on_wheel: Optional[WheelCallback] = None,
    ) -> None:
        """创建输入监听器。"""
        self._hwnd = hwnd
        self._on_mouse = on_mouse
        self._on_keyboard = on_keyboard
        self._on_stop = on_stop
        self._poll_interval = poll_interval
        self._on_wheel = on_wheel
        self._ready = threading.Event()
        self._error: Optional[Exception] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._mouse_starts: dict[int, tuple[int, int]] = {}

    def start(self) -> None:
        """启动后台监听线程。"""
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("输入监听器已经启动")
        self._stop_event.clear()
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(
            target=self._run,
            name="gameplay-input-monitor",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=2.0):
            self.stop()
            raise RuntimeError("输入监听器启动超时")
        if self._error is not None:
            self.stop()

    def stop(self) -> None:
        """停止监听并等待线程退出。"""
        self._stop_event.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                raise RuntimeError("输入监听器未能停止")
        if self._error is not None:
            raise RuntimeError("输入监听器失败") from self._error

    def _run(self) -> None:
        hook = None
        # 回调必须在线程结束前保持强引用，避免原生钩子访问已释放对象。
        callback = _HookProc(self._wheel_hook)
        try:
            if self._on_wheel is not None:
                hook = _user32.SetWindowsHookExW(win32con.WH_MOUSE_LL, callback, None, 0)
                if not hook:
                    raise ctypes.WinError(ctypes.get_last_error())
            self._ready.set()
            self._poll_inputs()
        except Exception as exc:
            self._error = exc
            self._on_stop("input_monitor_error")
        finally:
            if hook and not _user32.UnhookWindowsHookEx(hook):
                self._error = ctypes.WinError(ctypes.get_last_error())
            self._ready.set()

    def _wheel_hook(self, code: int, message: int, pointer: int) -> int:
        """只观察滚轮并传递消息，不阻止游戏或其他钩子接收输入。"""
        try:
            if code >= 0 and message == win32con.WM_MOUSEWHEEL:
                data = ctypes.cast(pointer, ctypes.POINTER(_MouseHookData)).contents
                self._handle_wheel(data)
        except Exception as exc:
            self._error = exc
            self._stop_event.set()
            self._on_stop("input_monitor_error")
        return _user32.CallNextHookEx(None, code, message, pointer)

    def _handle_wheel(self, data: _MouseHookData) -> None:
        """仅接受前台目标客户区内的真人滚轮，使用事件自身的坐标。"""
        if self._on_wheel is None or data.flags & 1 or self._stop_event.is_set():
            return
        if win32gui.GetForegroundWindow() != self._hwnd:
            return
        screen_point = (data.pt.x, data.pt.y)
        target = win32gui.WindowFromPoint(screen_point)
        if target != self._hwnd and not win32gui.IsChild(self._hwnd, target):
            return
        x, y = win32gui.ScreenToClient(self._hwnd, screen_point)
        left, top, right, bottom = win32gui.GetClientRect(self._hwnd)
        delta = ctypes.c_short(data.mouseData >> 16).value
        if left <= x < right and top <= y < bottom and delta:
            self._on_wheel(x, y, delta)

    def _poll_inputs(self) -> None:
        """在原有按键轮询线程中分发滚轮钩子消息。"""
        previous = {key: self._is_down(key) for key in range(1, 256)}
        while not self._stop_event.wait(self._poll_interval):
            if self._on_wheel is not None:
                win32gui.PumpWaitingMessages()
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
