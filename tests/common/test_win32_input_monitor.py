"""Windows 输入监听器的无窗口单元测试。"""

from __future__ import annotations

from typing import Callable

import pytest
import win32con

from yys.common.recording.win32_input import WindowsInputMonitor


def _new_monitor(
    mouse_events: list[tuple[object, ...]],
    keyboard_events: list[tuple[str, str]],
    stop_reasons: list[str],
) -> WindowsInputMonitor:
    """创建只把回调参数收集到列表的监听器。"""
    return WindowsInputMonitor(
        hwnd=12345,
        on_mouse=lambda *args: mouse_events.append(args),
        on_keyboard=lambda *args: keyboard_events.append(args),
        on_stop=stop_reasons.append,
    )


def test_drag_is_emitted_as_one_client_relative_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """鼠标按下和释放之间的位移应合并成一次拖拽。"""
    mouse_events: list[tuple[object, ...]] = []
    monitor = _new_monitor(mouse_events, [], [])
    positions = iter([(10, 20), (40, 60)])
    monkeypatch.setattr(
        monitor,
        "_client_cursor_position",
        lambda: next(positions),
    )

    monitor._handle_mouse_transition(win32con.VK_LBUTTON, False, True)
    monitor._handle_mouse_transition(win32con.VK_LBUTTON, True, False)

    assert mouse_events == [("drag", 10, 20, 40, 60, "left")]


def test_release_outside_target_window_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """在窗口外释放的鼠标动作不得进入录制事件。"""
    mouse_events: list[tuple[object, ...]] = []
    monitor = _new_monitor(mouse_events, [], [])
    positions = iter([(10, 20), None])
    monkeypatch.setattr(
        monitor,
        "_client_cursor_position",
        lambda: next(positions),
    )

    monitor._handle_mouse_transition(win32con.VK_LBUTTON, False, True)
    monitor._handle_mouse_transition(win32con.VK_LBUTTON, True, False)

    assert mouse_events == []


def test_f12_stops_before_dispatching_other_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F12 上升沿必须优先触发停止且不作为普通键盘事件记录。"""
    mouse_events: list[tuple[object, ...]] = []
    keyboard_events: list[tuple[str, str]] = []
    stop_reasons: list[str] = []
    monitor = _new_monitor(mouse_events, keyboard_events, stop_reasons)
    key_state_calls = 0

    def fake_is_down(key: int) -> bool:
        nonlocal key_state_calls
        key_state_calls += 1
        initialized = key_state_calls > 255
        return initialized and key == win32con.VK_F12

    class _OneIterationStopEvent:
        """让监听循环只进入一次。"""

        def wait(self, _timeout: float) -> bool:
            return False

        def set(self) -> None:
            return None

    monkeypatch.setattr(monitor, "_is_down", fake_is_down)
    monkeypatch.setattr(monitor, "_stop_event", _OneIterationStopEvent())
    monkeypatch.setattr(
        "yys.common.recording.win32_input.win32gui.GetForegroundWindow",
        _returning(12345),
    )

    monitor._run()

    assert stop_reasons == ["emergency_stop"]
    assert keyboard_events == []
    assert mouse_events == []


def _returning(value: int) -> Callable[[], int]:
    """创建返回固定值的无参函数。"""
    return lambda: value
