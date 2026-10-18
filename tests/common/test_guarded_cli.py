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


@pytest.mark.parametrize("script_id", ["realm_raid", "regional_demon_boss"])
def test_default_mode_is_observe_only(script_id: str) -> None:
    """未显式传入 --execute 时只能进入观察模式。"""
    args = run_guarded_script.build_parser().parse_args([script_id])

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


@pytest.mark.parametrize("script_id", ["realm_raid", "regional_demon_boss"])
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
    script_id: str,
    execute: bool,
    confirmation: str,
    capture_mode: str,
    activate_count: int,
    non_interactive: bool,
) -> None:
    """产品契约：两脚本沿用相同确认与截图边界，地域鬼王固定单次。"""
    confirmation = confirmation.replace("realm_raid", script_id)
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
    script.entry_scene = "regional_demon_boss"
    script.get_state_snapshot.return_value = {}
    monitor = Mock()

    monkeypatch.setattr(
        windows_module,
        "WindowsEnvironment",
        environment_factory,
    )
    monkeypatch.setattr(guarded_module, "RunGuard", Mock(return_value=guard))
    guarded_factory = Mock(return_value=guarded_env)
    monkeypatch.setattr(
        guarded_module,
        "GuardedEnvironment",
        guarded_factory,
    )
    script_factory = Mock(return_value=script)
    if script_id == "realm_raid":
        monkeypatch.setattr(realm_module, "RealmRaidScript", script_factory)
    else:
        import yys.regional_demon_boss.regional_demon_boss_script as regional_module

        monkeypatch.setattr(regional_module, "RegionalDemonBossScript", script_factory)
    monkeypatch.setattr(
        input_module,
        "WindowsInputMonitor",
        Mock(return_value=monitor),
    )

    argv = [script_id, "--execute"] if execute else [script_id]
    argv.extend(["--max-battles", "7", "--skip-quit-three"])
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
    guarded_factory.assert_called_once_with(
        real_env, guard, observe_only=not execute,
    )
    expected_config = (
        {"max_battle_count": 7, "quit_3_times_config": False}
        if script_id == "realm_raid" else {}
    )
    script_factory.assert_called_once_with(script_id, env=guarded_env, config=expected_config)
    script.run.assert_called_once_with()
    if script_id == "regional_demon_boss":
        assert script.entry_scene == "regional_demon_boss"
    monitor.start.assert_called_once_with()
    monitor.stop.assert_called_once_with()


def test_script_exception_returns_failure_and_stops_monitor(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """脚本异常不得输出成功摘要，输入监听器仍必须停止。"""
    monkeypatch.setattr(run_guarded_script.sys, "stdin", _NonInteractiveInput())
    real_env = SimpleNamespace(hwnd=123, activate_window=Mock())
    guard = Mock()
    guarded_env = SimpleNamespace(action_records=[])
    script = Mock()
    script.run.side_effect = RuntimeError("回放失败")
    script_factory = Mock(return_value=script)
    monitor = Mock()

    monkeypatch.setattr(windows_module, "WindowsEnvironment", Mock(return_value=real_env))
    monkeypatch.setattr(guarded_module, "RunGuard", Mock(return_value=guard))
    monkeypatch.setattr(guarded_module, "GuardedEnvironment", Mock(return_value=guarded_env))
    import yys.regional_demon_boss.regional_demon_boss_script as regional_module

    monkeypatch.setattr(regional_module, "RegionalDemonBossScript", script_factory)
    monkeypatch.setattr(input_module, "WindowsInputMonitor", Mock(return_value=monitor))

    args = run_guarded_script.build_parser().parse_args(
        ["regional_demon_boss", "--confirmation-phrase", "OBSERVE regional_demon_boss"]
    )

    assert run_guarded_script.run_command(args) == 1
    captured = capsys.readouterr()
    assert "脚本运行失败: 回放失败" in captured.err
    assert "auto_restart" not in captured.out
    monitor.start.assert_called_once_with()
    monitor.stop.assert_called_once_with()


def test_script_construction_exception_stops_monitor_without_starting_it(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """脚本构造失败不得启动脚本或监听线程，但仍清理监听器对象。"""
    monkeypatch.setattr(run_guarded_script.sys, "stdin", _NonInteractiveInput())
    real_env = SimpleNamespace(hwnd=123, activate_window=Mock())
    guard = Mock()
    guarded_env = SimpleNamespace(action_records=[])
    script_factory = Mock(side_effect=RuntimeError("构造失败"))
    monitor = Mock()

    monkeypatch.setattr(windows_module, "WindowsEnvironment", Mock(return_value=real_env))
    monkeypatch.setattr(guarded_module, "RunGuard", Mock(return_value=guard))
    monkeypatch.setattr(guarded_module, "GuardedEnvironment", Mock(return_value=guarded_env))
    import yys.regional_demon_boss.regional_demon_boss_script as regional_module

    monkeypatch.setattr(regional_module, "RegionalDemonBossScript", script_factory)
    monkeypatch.setattr(input_module, "WindowsInputMonitor", Mock(return_value=monitor))

    args = run_guarded_script.build_parser().parse_args(
        ["regional_demon_boss", "--confirmation-phrase", "OBSERVE regional_demon_boss"]
    )

    assert run_guarded_script.run_command(args) == 1
    assert "脚本运行失败: 构造失败" in capsys.readouterr().err
    monitor.start.assert_not_called()
    monitor.stop.assert_called_once_with()


@pytest.mark.parametrize("script_id,battles,expected", [
    ("daily_collect", 7, {}), ("daily_activity_rewards", 7, {}),
    ("realm_foster", 7, {}), ("fengmo", 7, {}),
    ("soul_soil", None, {"max_battle_count": 10}),
    ("soul_soil", 1, {"max_battle_count": 1}),
])
def test_daily_guarded_cli_only_soul_soil_uses_battle_count(
    monkeypatch: pytest.MonkeyPatch, script_id: str, battles: int | None, expected: dict,
) -> None:
    """产品契约：实机接线时参数只影响对应脚本，确认、F12 和前台截图边界保持。"""
    import ui_backend.scripts.registry as registry_module

    monkeypatch.setattr(run_guarded_script.sys, "stdin", _NonInteractiveInput())
    monkeypatch.setattr(run_guarded_script.time, "sleep", lambda _: None)
    env = SimpleNamespace(hwnd=123, activate_window=Mock())
    wrapped = SimpleNamespace(action_records=[])
    guard, monitor, script = Mock(), Mock(), Mock()
    guard.snapshot.return_value = {}
    script.get_state_snapshot.return_value = {}
    factory = Mock(return_value=script)
    registry = Mock()
    registry.load_class.return_value = factory
    monkeypatch.setattr(registry_module, "ScriptRegistry", Mock(return_value=registry))
    monkeypatch.setattr(windows_module, "WindowsEnvironment", Mock(return_value=env))
    monkeypatch.setattr(guarded_module, "RunGuard", Mock(return_value=guard))
    monkeypatch.setattr(guarded_module, "GuardedEnvironment", Mock(return_value=wrapped))
    monkeypatch.setattr(input_module, "WindowsInputMonitor", Mock(return_value=monitor))
    argv = [script_id, "--execute", "--confirmation-phrase", f"RUN {script_id}"]
    if battles is not None:
        argv += ["--max-battles", str(battles)]
    assert run_guarded_script.main(argv) == 0
    factory.assert_called_once_with(script_id, env=wrapped, config=expected)
    env.activate_window.assert_called_once()
    monitor.start.assert_called_once()
    monitor.stop.assert_called_once()
