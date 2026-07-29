"""生产环境抽象迁移的兼容性测试。"""

import pytest
from PIL import Image

from tests.common.environment.base import (
    ActionRecord as CompatActionRecord,
    ActionType as CompatActionType,
    GameEnvironment as CompatGameEnvironment,
)
from tests.common.environment.mock_environment import MockEnvironment
from tests.common.recorders.action_log import ActionLog
from win_util.controller import WinController
import win_util.environment.windows as windows_module
from win_util.environment.base import ActionRecord, ActionType, GameEnvironment
from win_util.environment.windows import WindowsEnvironment
from win_util.keyboard import KeyboardController
from win_util.mouse import MouseController


def test_legacy_environment_imports_reexport_production_types() -> None:
    """旧测试路径应继续导出同一组生产类型。"""
    assert CompatActionRecord is ActionRecord
    assert CompatActionType is ActionType
    assert CompatGameEnvironment is GameEnvironment


def test_keyboard_controller_records_logical_key_press_via_environment() -> None:
    """环境模式下单次按键只记录一个逻辑动作。"""
    log = ActionLog()
    env = MockEnvironment(action_log=log)
    keyboard = KeyboardController(env=env)

    keyboard.bg_press_key("ESC")

    records = log.records
    assert len(records) == 1
    assert records[0].action_type == ActionType.KEY_PRESS.value
    assert records[0].extra["key_code"] == 27


def test_win_controller_injects_environment_into_keyboard() -> None:
    """WinController 的键盘组件必须复用注入环境。"""
    log = ActionLog()
    env = MockEnvironment(action_log=log)
    controller = WinController(env=env)

    controller.press_key("ENTER")

    assert log.records[0].action_type == ActionType.KEY_PRESS.value
    assert log.records[0].extra["key_code"] == 13


def test_environment_swipe_records_single_drag() -> None:
    """环境模式滑动应记录一个拖拽，而不是多个点击。"""
    log = ActionLog()
    env = MockEnvironment(action_log=log)
    mouse = MouseController(env=env)

    assert mouse.bg_swipe(100, 200, 300, 400)

    records = log.records
    assert len(records) == 1
    assert records[0].action_type == ActionType.DRAG.value
    assert (records[0].x, records[0].y) == (100, 200)
    assert records[0].extra == {"end_x": 300, "end_y": 400}


def test_windows_environment_foreground_capture_uses_client_screen_rect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """前台截图模式必须把客户区坐标转换为桌面坐标后采集。"""
    captured: dict[str, object] = {}
    monkeypatch.setattr(windows_module.win32gui, "GetForegroundWindow", lambda: 123)
    monkeypatch.setattr(
        windows_module.win32gui,
        "GetClientRect",
        lambda _hwnd: (0, 0, 320, 180),
    )
    monkeypatch.setattr(
        windows_module.win32gui,
        "ClientToScreen",
        lambda _hwnd, point: (point[0] + 50, point[1] + 80),
    )

    def grab(**kwargs: object) -> Image.Image:
        captured.update(kwargs)
        return Image.new("RGB", (320, 180), color=(10, 20, 30))

    monkeypatch.setattr(windows_module.ImageGrab, "grab", grab)

    image = WindowsEnvironment(hwnd=123, capture_mode="foreground").capture_screen()

    assert image.size == (320, 180)
    assert captured == {"bbox": (50, 80, 370, 260), "all_screens": True}


def test_windows_environment_foreground_capture_requires_target_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """目标窗口不在前台时不得误录其他桌面内容。"""
    monkeypatch.setattr(windows_module.win32gui, "GetForegroundWindow", lambda: 456)
    environment = WindowsEnvironment(hwnd=123, capture_mode="foreground")

    with pytest.raises(RuntimeError, match="游戏窗口位于前台"):
        environment.capture_screen()


def test_windows_environment_activate_restores_and_focuses_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """交互式录制开始前应恢复最小化窗口并将其切到前台。"""
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(windows_module.win32gui, "IsIconic", lambda _hwnd: True)
    monkeypatch.setattr(
        windows_module.win32gui,
        "ShowWindow",
        lambda *args: calls.append(("show", *args)),
    )
    monkeypatch.setattr(
        windows_module.win32gui,
        "SetForegroundWindow",
        lambda *args: calls.append(("focus", *args)),
    )

    WindowsEnvironment(hwnd=123, capture_mode="foreground").activate_window()

    assert calls == [
        ("show", 123, windows_module.win32con.SW_RESTORE),
        ("focus", 123),
    ]


def test_windows_environment_rejects_unknown_capture_mode() -> None:
    """未知截图模式应在创建环境时立即失败。"""
    with pytest.raises(ValueError, match="不支持的截图模式"):
        WindowsEnvironment(hwnd=123, capture_mode="unknown")
