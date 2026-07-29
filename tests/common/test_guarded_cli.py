"""受保护运行命令行入口的安全边界测试。"""

from __future__ import annotations

import builtins
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tools import run_guarded_script
import win_util.environment.guarded as guarded_module
import win_util.environment.windows as windows_module
import yys.common.recording.win32_input as input_module
import yys.realm_raid.realm_raid_script as realm_module


class _InteractiveInput:
    """只为 CLI 测试提供交互终端标记。"""

    def isatty(self) -> bool:
        """声明当前输入流是交互终端。"""
        return True


class _NonInteractiveInput:
    """只为 CLI 测试提供非交互终端标记。"""

    def isatty(self) -> bool:
        """声明当前输入流不是交互终端。"""
        return False


def test_default_mode_is_observe_only() -> None:
    """未显式传入 --execute 时只能进入观察模式。"""
    args = run_guarded_script.build_parser().parse_args(["realm_raid"])

    assert args.execute is False
    assert args.timeout_seconds == 180.0
    assert args.max_actions == 30
    assert args.unknown_limit == 3
    assert args.confirmation_phrase is None


def test_non_interactive_start_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """代理或管道不能绕过人工启动要求。"""
    monkeypatch.setattr(run_guarded_script.sys, "stdin", _NonInteractiveInput())
    args = run_guarded_script.build_parser().parse_args(["realm_raid", "--execute"])

    assert run_guarded_script.run_command(args) == 2


def test_confirmation_mismatch_does_not_construct_real_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """确认短语错误时必须在解析真实窗口前退出。"""
    monkeypatch.setattr(run_guarded_script.sys, "stdin", _InteractiveInput())
    monkeypatch.setattr(builtins, "input", lambda _prompt: "错误确认")

    args = run_guarded_script.build_parser().parse_args(["realm_raid", "--execute"])

    assert run_guarded_script.run_command(args) == 1


def test_non_interactive_confirmation_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非交互确认短语必须与当前模式和脚本精确匹配。"""
    monkeypatch.setattr(run_guarded_script.sys, "stdin", _NonInteractiveInput())
    args = run_guarded_script.build_parser().parse_args(
        [
            "realm_raid",
            "--execute",
            "--confirmation-phrase",
            "RUN wrong_script",
        ]
    )

    assert run_guarded_script.run_command(args) == 1


@pytest.mark.parametrize(
    (
        "execute",
        "confirmation",
        "capture_mode",
        "activate_count",
        "non_interactive",
    ),
    [
        (True, "RUN realm_raid", "foreground", 1, False),
        (False, "OBSERVE realm_raid", "print_window", 0, False),
        (True, "RUN realm_raid", "foreground", 1, True),
    ],
)
def test_capture_mode_matches_guarded_run_mode(
    monkeypatch: pytest.MonkeyPatch,
    execute: bool,
    confirmation: str,
    capture_mode: str,
    activate_count: int,
    non_interactive: bool,
) -> None:
    """执行模式必须读取前台真实帧，观察模式不得主动抢占窗口。"""
    input_mock = Mock(return_value=confirmation)
    stdin = _NonInteractiveInput() if non_interactive else _InteractiveInput()
    monkeypatch.setattr(run_guarded_script.sys, "stdin", stdin)
    monkeypatch.setattr(builtins, "input", input_mock)
    monkeypatch.setattr(run_guarded_script.time, "sleep", lambda _seconds: None)

    real_env = SimpleNamespace(hwnd=123, activate_window=Mock())
    environment_factory = Mock(return_value=real_env)
    guard = Mock()
    guard.snapshot.return_value = {}
    guarded_env = SimpleNamespace(action_records=[])
    script = Mock()
    script.get_state_snapshot.return_value = {}
    monitor = Mock()

    monkeypatch.setattr(
        windows_module,
        "WindowsEnvironment",
        environment_factory,
    )
    monkeypatch.setattr(guarded_module, "RunGuard", Mock(return_value=guard))
    monkeypatch.setattr(
        guarded_module,
        "GuardedEnvironment",
        Mock(return_value=guarded_env),
    )
    monkeypatch.setattr(
        realm_module,
        "RealmRaidScript",
        Mock(return_value=script),
    )
    monkeypatch.setattr(
        input_module,
        "WindowsInputMonitor",
        Mock(return_value=monitor),
    )

    argv = ["realm_raid", "--execute"] if execute else ["realm_raid"]
    if non_interactive:
        argv.extend(["--confirmation-phrase", confirmation])
    args = run_guarded_script.build_parser().parse_args(argv)

    assert run_guarded_script.run_command(args) == 0
    environment_factory.assert_called_once_with(
        window_title="阴阳师",
        capture_mode=capture_mode,
    )
    assert real_env.activate_window.call_count == activate_count
    assert input_mock.call_count == (0 if non_interactive else 1)
    monitor.start.assert_called_once_with()
    monitor.stop.assert_called_once_with()
