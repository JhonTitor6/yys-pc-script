"""受保护真实运行环境的离线测试。"""

from __future__ import annotations

import pytest

import win_util.event as event_module
from tests.common.environment.mock_environment import MockEnvironment
from win_util.environment.guarded import (
    GuardedEnvironment,
    RunGuard,
    RunStopReason,
)
from win_util.event import EventBaseScript


def test_observe_mode_records_but_does_not_execute() -> None:
    """观察模式只能记录计划动作，不能把输入发给底层环境。"""
    delegate = MockEnvironment()
    guard = RunGuard()
    env = GuardedEnvironment(delegate, guard, observe_only=True)

    env.left_click(100, 200)

    assert len(delegate.action_log) == 0
    assert guard.action_count == 1
    assert len(env.action_records) == 1
    assert env.action_records[0].action_type == "left_click"


def test_live_mode_executes_within_action_budget() -> None:
    """执行模式在预算内将动作传递给底层环境。"""
    delegate = MockEnvironment()
    guard = RunGuard(max_actions=2)
    env = GuardedEnvironment(delegate, guard, observe_only=False)

    env.left_click(100, 200)
    env.key_press(13)

    assert len(delegate.action_log) == 2
    assert guard.action_count == 2
    assert guard.stop_reason is None


def test_action_over_budget_is_blocked() -> None:
    """达到动作上限后，额外动作必须被拦截。"""
    delegate = MockEnvironment()
    guard = RunGuard(max_actions=2)
    env = GuardedEnvironment(delegate, guard, observe_only=False)

    env.left_click(10, 10)
    env.left_click(20, 20)
    env.left_click(30, 30)

    assert len(delegate.action_log) == 2
    assert len(env.action_records) == 2
    assert guard.action_count == 2
    assert guard.stop_reason is RunStopReason.ACTION_LIMIT


def test_unknown_scene_counter_resets_after_recognition() -> None:
    """识别成功会清空连续未知画面计数。"""
    guard = RunGuard(unknown_limit=3)

    guard.note_iteration(False)
    guard.note_iteration(False)
    guard.note_iteration(True)
    guard.note_iteration(False)

    assert guard.consecutive_unknown == 1
    assert guard.stop_reason is None

    guard.note_iteration(False)
    guard.note_iteration(False)

    assert guard.stop_reason is RunStopReason.UNKNOWN_SCENE


def test_unknown_grace_is_temporary_and_ends_on_recognition() -> None:
    """触发动作本身不取消宽限，后续识别成功才结束宽限。"""
    now = [10.0]
    guard = RunGuard(unknown_limit=2, monotonic=lambda: now[0])

    guard.allow_unknown_for(5.0)
    guard.note_iteration(True)
    assert guard.snapshot()["unknown_grace_remaining_seconds"] == pytest.approx(5.0)

    now[0] = 12.0
    guard.note_iteration(False)
    now[0] = 14.9
    guard.note_iteration(False)

    assert guard.consecutive_unknown == 0
    assert guard.stop_reason is None
    assert guard.snapshot()["unknown_grace_remaining_seconds"] == pytest.approx(0.1)

    guard.note_iteration(True)
    assert guard.snapshot()["unknown_grace_remaining_seconds"] == 0.0
    guard.note_iteration(False)
    guard.note_iteration(False)

    assert guard.stop_reason is RunStopReason.UNKNOWN_SCENE


def test_unknown_grace_does_not_bypass_timeout() -> None:
    """未知宽限不得绕过总运行超时。"""
    now = [10.0]
    guard = RunGuard(
        timeout_seconds=5.0,
        monotonic=lambda: now[0],
    )
    guard.allow_unknown_for(30.0)
    now[0] = 15.0

    guard.note_iteration(False)

    assert guard.stop_reason is RunStopReason.TIMEOUT


def test_timeout_and_emergency_stop_are_deterministic() -> None:
    """超时和人工急停均应保留首个停机原因。"""
    now = [10.0]
    timeout_guard = RunGuard(timeout_seconds=5, monotonic=lambda: now[0])
    now[0] = 15.0

    assert timeout_guard.is_stopped is True
    assert timeout_guard.stop_reason is RunStopReason.TIMEOUT

    emergency_guard = RunGuard()
    emergency_guard.request_emergency_stop()
    assert emergency_guard.stop_reason is RunStopReason.EMERGENCY_STOP


def test_invalid_guard_limits_are_rejected() -> None:
    """安全预算不接受零或负数。"""
    with pytest.raises(ValueError):
        RunGuard(timeout_seconds=0)
    with pytest.raises(ValueError):
        RunGuard(max_actions=0)
    with pytest.raises(ValueError):
        RunGuard(unknown_limit=0)
    with pytest.raises(ValueError):
        RunGuard().allow_unknown_for(0)


def test_event_loop_stops_after_consecutive_unknown_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """事件循环必须把连续未知识别结果反馈给保险丝。"""
    monkeypatch.setattr(event_module, "random_sleep", lambda _start, _end: None)
    script = EventBaseScript()
    guard = RunGuard(unknown_limit=2)
    script.set_run_guard(guard)

    script.run()

    assert guard.stop_reason is RunStopReason.UNKNOWN_SCENE
    assert guard.consecutive_unknown == 2


def test_event_loop_preserves_grace_armed_by_current_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """事件回调开启的宽限不能被同一轮识别回执立即取消。"""
    now = [10.0]
    guard = RunGuard(monotonic=lambda: now[0])
    script = EventBaseScript()
    script.set_run_guard(guard)
    monkeypatch.setattr(event_module, "random_sleep", lambda _start, _end: None)

    def trigger_once() -> str:
        guard.allow_unknown_for(5.0)
        script.stop()
        return "attack"

    monkeypatch.setattr(script, "_trigger_event_from_screenshot_cache", trigger_once)

    script.run()

    assert guard.snapshot()["unknown_grace_remaining_seconds"] == pytest.approx(5.0)
