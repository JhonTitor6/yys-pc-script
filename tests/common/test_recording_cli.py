"""伴随录制器命令行编排测试。"""

from argparse import Namespace
from pathlib import Path

import pytest

import tools.record_gameplay as recorder_cli
import win_util.environment.windows as windows_module
import yys.common.recording.session as session_module
import yys.common.recording.win32_input as input_module


class InteractiveInput:
    """提供交互式终端判定的最小替身。"""

    def isatty(self) -> bool:
        """模拟交互式标准输入。"""
        return True


def test_record_command_activates_game_before_session_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """录制命令必须启用前台截图，并在采集前自动激活游戏。"""
    events: list[object] = []

    class FakeEnvironment:
        """记录构造参数与激活动作。"""

        hwnd = 123

        def __init__(self, **kwargs: object) -> None:
            events.append(("environment", kwargs))

        def activate_window(self) -> None:
            events.append("activate")

    class FakeSession:
        """记录会话启动顺序。"""

        recording_id = "test-recording"

        def __init__(self, **kwargs: object) -> None:
            events.append(("session", kwargs))

        def record_mouse(self, *_args: object, **_kwargs: object) -> None:
            """模拟鼠标事件回调。"""

        def record_keyboard(self, *_args: object, **_kwargs: object) -> None:
            """模拟键盘事件回调。"""

        def request_stop(self, *_args: object, **_kwargs: object) -> None:
            """模拟停止回调。"""

        def run(self, monitor: object) -> Path:
            events.append(("run", monitor))
            return tmp_path / "realm_raid" / self.recording_id

    class FakeMonitor:
        """保存输入监听器构造参数。"""

        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    monkeypatch.setattr(windows_module, "WindowsEnvironment", FakeEnvironment)
    monkeypatch.setattr(session_module, "RecordingSession", FakeSession)
    monkeypatch.setattr(input_module, "WindowsInputMonitor", FakeMonitor)
    monkeypatch.setattr(recorder_cli.sys, "stdin", InteractiveInput())
    monkeypatch.setattr("builtins.input", lambda _prompt: "")
    monkeypatch.setattr(
        recorder_cli.time,
        "sleep",
        lambda seconds: events.append(("sleep", seconds)),
    )
    args = Namespace(
        window_title="阴阳师",
        scenario="realm_raid",
        output_root=tmp_path,
        fps=8.0,
    )

    result = recorder_cli.record_command(args)

    assert events[0] == (
        "environment",
        {"window_title": "阴阳师", "capture_mode": "foreground"},
    )
    activate_index = events.index("activate")
    sleep_index = events.index(("sleep", 0.5))
    run_index = next(
        index
        for index, event in enumerate(events)
        if isinstance(event, tuple) and event[0] == "run"
    )
    assert activate_index < sleep_index < run_index
    assert result == 0


def test_missing_game_window_creates_no_recording_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """找不到目标窗口时必须在创建录制目录之前明确失败。"""
    class MissingEnvironment:
        """模拟无法解析目标游戏窗口。"""

        def __init__(self, **_kwargs: object) -> None:
            raise RuntimeError("未找到标题包含 '阴阳师' 的游戏窗口")

    monkeypatch.setattr(recorder_cli.sys, "stdin", InteractiveInput())
    monkeypatch.setattr(
        windows_module,
        "WindowsEnvironment",
        MissingEnvironment,
    )
    args = Namespace(
        window_title="阴阳师",
        scenario="realm_raid",
        output_root=tmp_path,
        fps=8.0,
    )

    with pytest.raises(RuntimeError, match="未找到标题包含"):
        recorder_cli.record_command(args)

    assert list(tmp_path.iterdir()) == []
