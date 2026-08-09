"""结界突破九宫格状态机的离线测试。"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

import yys.realm_raid.realm_raid_script as realm_module
from tests.common.environment.mock_environment import MockEnvironment
from win_util.environment.guarded import RunGuard
from yys.realm_raid.realm_raid_script import (
    RealmRaidScript,
    RealmRaidStopReason,
    RealmTarget,
)


@pytest.fixture
def script(monkeypatch: pytest.MonkeyPatch) -> RealmRaidScript:
    """创建不执行真实等待的结界突破脚本。"""
    monkeypatch.setattr(realm_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(realm_module, "random_sleep", lambda _start, _end: None)
    script = RealmRaidScript(env=MockEnvironment())
    monkeypatch.setattr(script.win_controller, "update_screenshot_cache", Mock())
    return script


def test_targets_are_scanned_in_row_major_order(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """九宫格目标必须按从左到右、从上到下返回。"""
    visible_cells = {(0, 0), (0, 2), (1, 1), (2, 0)}

    def fake_find(
        _image_path: str,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
    ) -> tuple[int, int]:
        del x1, y1
        row = (y0 - 120) // 120
        col = (x0 - 125) // 300
        if (row, col) in visible_cells:
            return x0 + 20, y0 + 20
        return -1, -1

    monkeypatch.setattr(script.image_finder, "bg_find_pic_by_cache", fake_find)

    targets = script.get_all_attackable_barrier()

    assert [(target.row, target.col) for target in targets] == [
        (0, 0),
        (0, 2),
        (1, 1),
        (2, 0),
    ]


def test_attackable_event_selects_next_unattempted_target(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """重复识别九宫格时不得再次选择本轮已尝试目标。"""
    targets = [
        RealmTarget(row=0, col=0, point=(200, 180)),
        RealmTarget(row=0, col=1, point=(500, 180)),
    ]
    find_targets = Mock(return_value=targets)
    click = Mock()
    monkeypatch.setattr(script, "get_all_attackable_barrier", find_targets)
    monkeypatch.setattr(script, "bg_left_click", click)

    script._on_attackable_barrier((999, 999))
    script._on_attackable_barrier((999, 999))

    assert [call.args[0] for call in click.call_args_list] == [
        (200, 180),
        (500, 180),
    ]
    assert script.round_state.attempted_cells == {(0, 0), (0, 1)}


def test_automatic_new_grid_resets_round_before_target_selection(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """有新增胜场且攻略记录归零时，应先重置轮次再选择新组同位置目标。"""
    target = RealmTarget(row=0, col=0, point=(200, 180))
    click = Mock()
    monkeypatch.setattr(
        script.image_finder,
        "bg_find_pic_by_cache",
        Mock(return_value=(100, 540)),
    )
    monkeypatch.setattr(
        script.image_finder,
        "bg_find_pic_all_by_cache",
        Mock(return_value=[(i, i, 0.9) for i in range(9)]),
    )
    monkeypatch.setattr(script, "get_all_attackable_barrier", Mock(return_value=[target]))
    monkeypatch.setattr(script, "bg_left_click", click)
    script.round_state.attempted_cells.add((0, 0))
    script.round_state.quit_three_completed = True
    script.round_state.victory_count_at_start = 1
    script._cur_battle_victory_count = 2

    script._on_attackable_barrier((999, 999))

    assert script.round_state.generation == 2
    assert script.round_state.victory_count_at_start == 2
    assert script.round_state.quit_three_completed is False
    assert script.round_state.attempted_cells == {(0, 0)}
    click.assert_called_once_with((200, 180), x_range=5, y_range=5)


def test_record_zero_on_partial_grid_does_not_reset_round(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """打了一半的旧组即使 record_zero 模板命中，也不能误判自动换组。"""
    target = RealmTarget(row=0, col=0, point=(200, 180))
    monkeypatch.setattr(
        script.image_finder,
        "bg_find_pic_by_cache",
        Mock(return_value=(100, 540)),
    )
    monkeypatch.setattr(
        script.image_finder,
        "bg_find_pic_all_by_cache",
        Mock(return_value=[(i, i, 0.9) for i in range(3)]),
    )
    monkeypatch.setattr(script.image_finder, "screenshot_cache", None)
    monkeypatch.setattr(script, "get_all_attackable_barrier", Mock(return_value=[target]))
    monkeypatch.setattr(script, "bg_left_click", Mock())
    script.round_state.attempted_cells.add((0, 0))
    script.round_state.quit_three_completed = True
    script.round_state.victory_count_at_start = 1
    script._cur_battle_victory_count = 2

    script._on_attackable_barrier((999, 999))

    assert script.round_state.generation == 1
    assert script.round_state.quit_three_completed is True
    assert script.round_state.attempted_cells == {(0, 0)}


def test_record_zero_during_quit_sequence_does_not_reset_round(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """退出三次期间尚无新增胜场，即使记录为零也不能误判自动换组。"""
    target = RealmTarget(row=0, col=1, point=(500, 180))
    monkeypatch.setattr(
        script.image_finder,
        "bg_find_pic_by_cache",
        Mock(return_value=(100, 540)),
    )
    monkeypatch.setattr(script, "get_all_attackable_barrier", Mock(return_value=[target]))
    monkeypatch.setattr(script, "bg_left_click", Mock())
    script.round_state.attempted_cells.add((0, 0))

    script._on_attackable_barrier((999, 999))

    assert script.round_state.generation == 1
    assert script.round_state.attempted_cells == {(0, 0), (0, 1)}


def test_repeatedly_missing_unattempted_target_stops(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一画面连续无法选出新目标时应停止，不能无限空转。"""
    target = RealmTarget(row=0, col=0, point=(200, 180))
    stop = Mock()
    monkeypatch.setattr(script, "get_all_attackable_barrier", Mock(return_value=[target]))
    monkeypatch.setattr(script, "bg_left_click", Mock())
    monkeypatch.setattr(script, "stop", stop)

    script._on_attackable_barrier((999, 999))  # 首次尝试
    script._on_attackable_barrier((999, 999))  # 重试 1
    script._on_attackable_barrier((999, 999))  # 重试 2
    script._on_attackable_barrier((999, 999))  # 重试 3
    script._on_attackable_barrier((999, 999))  # 超过重试上限

    stop.assert_called_once_with()
    assert script.stop_reason is RealmRaidStopReason.NO_ATTACKABLE_TARGET


def test_retry_reattempts_attackable_but_attempted_target(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """点击未生效（结界仍可攻击）时应限次重试，而不是立即停机。"""
    target = RealmTarget(row=0, col=0, point=(200, 180))
    click = Mock()
    monkeypatch.setattr(script, "get_all_attackable_barrier", Mock(return_value=[target]))
    monkeypatch.setattr(script, "bg_left_click", click)
    script.round_state.attempted_cells.add((0, 0))

    script._on_attackable_barrier((999, 999))
    script._on_attackable_barrier((999, 999))

    assert click.call_count == 2
    assert script.round_state.retry_count == 2
    assert script.stop_reason is None


def test_no_attackable_barrier_counts_observations(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """九宫格内没有可攻击结界时维持原有观测计数停机逻辑。"""
    stop = Mock()
    monkeypatch.setattr(script, "get_all_attackable_barrier", Mock(return_value=[]))
    monkeypatch.setattr(script, "bg_left_click", Mock())
    monkeypatch.setattr(script, "stop", stop)

    for _ in range(3):
        script._on_attackable_barrier((999, 999))

    assert script.round_state.no_target_observations == 3
    assert script.round_state.retry_count == 0
    stop.assert_called_once_with()
    assert script.stop_reason is RealmRaidStopReason.NO_ATTACKABLE_TARGET


def test_quit_three_times_runs_once_per_grid(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一九宫格仅退三次一次，刷新后的新九宫格可再次执行。"""
    quit_three = Mock(return_value=True)
    monkeypatch.setattr(script, "quit_3_times", quit_three)
    monkeypatch.setattr(script, "bg_left_click", Mock())

    script._on_attack((700, 400))
    script._on_attack((700, 400))
    assert quit_three.call_count == 1

    script._start_new_round()
    script._on_attack((700, 400))

    assert quit_three.call_count == 2
    assert script.round_state.generation == 2
    assert script.round_state.quit_three_completed is True


def test_attack_opens_temporary_unknown_grace(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """点击进攻后应容忍加载动画，但不修改全局未知阈值。"""
    now = [10.0]
    guard = RunGuard(unknown_limit=3, monotonic=lambda: now[0])
    script.set_run_guard(guard)
    script.quit_3_times_config = False
    monkeypatch.setattr(script, "bg_left_click", Mock())

    script._on_attack((700, 400))
    guard.note_iteration(True)
    guard.note_iteration(False)
    guard.note_iteration(False)
    guard.note_iteration(False)

    assert guard.stop_reason is None
    assert guard.unknown_limit == 3
    assert guard.snapshot()["unknown_grace_remaining_seconds"] == pytest.approx(
        script.BATTLE_TRANSITION_GRACE_SECONDS,
    )


def test_battling_refreshes_settlement_transition_grace(
    script: RealmRaidScript,
) -> None:
    """战斗标记消失后应容忍短暂结算动画，且不发送额外输入。"""
    now = [10.0]
    guard = RunGuard(unknown_limit=3, monotonic=lambda: now[0])
    script.set_run_guard(guard)

    script._on_battling((48, 593))
    guard.note_iteration(True)
    now[0] += 1.0
    guard.note_iteration(False)
    guard.note_iteration(False)
    guard.note_iteration(False)

    assert guard.stop_reason is None
    assert guard.unknown_limit == 3
    assert guard.snapshot()["unknown_grace_remaining_seconds"] == pytest.approx(
        script.BATTLE_SETTLEMENT_GRACE_SECONDS - 1.0,
    )


def test_ticket_not_enough_stops_with_reason(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """突破券不足必须直接停机并暴露原因。"""
    stop = Mock()
    monkeypatch.setattr(script, "stop", stop)

    script._on_ticket_not_enough((100, 100))

    stop.assert_called_once_with()
    assert script.stop_reason is RealmRaidStopReason.TICKET_NOT_ENOUGH


def test_missing_retry_button_stops_quit_sequence(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """找不到再次挑战按钮时不能继续盲点后续步骤。"""
    stop = Mock()
    find_and_click = Mock(return_value=False)
    monkeypatch.setattr(script, "stop", stop)
    monkeypatch.setattr(script.win_controller, "find_and_click", find_and_click)

    result = script.quit_3_times()

    assert result is False
    stop.assert_called_once_with()
    assert script.stop_reason is RealmRaidStopReason.RETRY_FAILED
    assert find_and_click.call_count == 1


def test_refresh_starts_new_round_only_after_targets_are_confirmed(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """刷新、确认和新目标识别全部成功后才切换九宫格轮次。"""
    refreshed_targets = [RealmTarget(row=0, col=0, point=(200, 180))]
    monkeypatch.setattr(
        script.image_finder,
        "bg_find_pic_all_by_cache",
        Mock(return_value=[]),
    )
    monkeypatch.setattr(
        script.win_controller,
        "find_and_click",
        Mock(side_effect=[True, True]),
    )
    monkeypatch.setattr(script.win_controller, "update_screenshot_cache", Mock())
    monkeypatch.setattr(
        script,
        "get_all_attackable_barrier",
        Mock(return_value=refreshed_targets),
    )
    script.round_state.attempted_cells.add((0, 0))
    script.round_state.quit_three_completed = True

    result = script.refresh_if_no_attackable_barrier()

    assert result is True
    assert script.round_state.generation == 2
    assert script.round_state.attempted_cells == set()
    assert script.round_state.quit_three_completed is False
    assert script.attackable_barrier_list == refreshed_targets


@pytest.mark.parametrize(
    ("click_results", "expected_calls"),
    [
        ([False], 1),
        ([True, False], 2),
    ],
)
def test_refresh_click_failure_stops_without_advancing_round(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
    click_results: list[bool],
    expected_calls: int,
) -> None:
    """刷新按钮或确认按钮失败时保持当前轮次并停机。"""
    stop = Mock()
    find_and_click = Mock(side_effect=click_results)
    monkeypatch.setattr(script, "stop", stop)
    monkeypatch.setattr(
        script.image_finder,
        "bg_find_pic_all_by_cache",
        Mock(return_value=[]),
    )
    monkeypatch.setattr(script.win_controller, "find_and_click", find_and_click)
    monkeypatch.setattr(script.win_controller, "update_screenshot_cache", Mock())

    result = script.refresh_if_no_attackable_barrier()

    assert result is False
    assert find_and_click.call_count == expected_calls
    assert script.round_state.generation == 1
    assert script.stop_reason is RealmRaidStopReason.REFRESH_FAILED
    stop.assert_called_once_with()


def test_on_run_does_not_repeat_entry_navigation(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """入口跳转由父类 run 统一负责，on_run 不应再次跳转。"""
    goto_scene = Mock()
    monkeypatch.setattr(script.scene_manager, "goto_scene", goto_scene)

    script.on_run()

    goto_scene.assert_not_called()


def test_battle_loss_keeps_round_progress(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """战斗失败沿用公共结算，但不能清空本轮已尝试目标。"""
    monkeypatch.setattr(script, "bg_left_click", Mock())
    script.round_state.attempted_cells.add((1, 2))
    script._on_battling((48, 593))

    script._on_battle_end((500, 300))

    assert script._cur_battle_count == 1
    assert script.round_state.attempted_cells == {(1, 2)}


def test_unrelated_reward_dialog_is_dismissed_without_counting(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """没有对应战斗时，结界奖励弹窗只关闭，不增加战斗次数。"""
    click = Mock()
    monkeypatch.setattr(script, "bg_left_click", click)

    script._on_battle_end((500, 300))

    assert script._cur_battle_count == 0
    click.assert_called_once_with((500, 300), x_range=30, y_range=50)


def test_one_battle_counts_only_first_matching_settlement(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一场战斗后重复出现同模板奖励画面时只能计数一次。"""
    monkeypatch.setattr(script, "bg_left_click", Mock())
    script._on_battling((48, 593))

    script._on_battle_end((500, 300))
    script._on_battle_end((500, 300))

    assert script._cur_battle_count == 1


def test_max_battle_count_has_explicit_stop_reason(
    script: RealmRaidScript,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """达到最大次数时状态快照应包含明确原因。"""
    stop = Mock()
    monkeypatch.setattr(script, "stop", stop)
    script.max_battle_count = 1
    script._cur_battle_count = 1

    script.after_iteration()

    stop.assert_called_once_with()
    assert script.stop_reason is RealmRaidStopReason.MAX_BATTLE_COUNT
