"""使用脱敏正式录制验证结界突破真实界面流程。"""

from __future__ import annotations

from pathlib import Path

import pytest

import yys.common.scene_manager as scene_manager_module
import win_util.event as event_module
from tests.common.environment.scene_replay_environment import SceneReplayEnvironment
from tests.common.recorders.action_log import ActionLog
from win_util.controller import WinController
from yys.common.scene_manager import SceneManager
from yys.realm_raid.realm_raid_script import RealmRaidScript


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECORDED_FIXTURE_ROOT = (
    PROJECT_ROOT / "yys/realm_raid/images/test/recorded_v1"
)


def _create_environment(
    fixture_name: str,
    initial_scene: str,
    action_log: ActionLog | None = None,
) -> SceneReplayEnvironment:
    """按名称创建正式录制回放环境。"""
    fixture_dir = RECORDED_FIXTURE_ROOT / fixture_name
    fixture_path = fixture_dir / "fixture.json"
    return SceneReplayEnvironment(
        scene_dir=str(fixture_dir),
        transitions_config=str(fixture_path),
        initial_scene=initial_scene,
        action_log=action_log,
    )


def test_production_scene_manager_enters_realm_raid_from_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """生产场景管理器应能在真实录制画面上完成入口跳转。"""
    monkeypatch.setattr(scene_manager_module.time, "sleep", lambda _seconds: None)
    action_log = ActionLog()
    env = _create_environment("main", "home", action_log)
    controller = WinController(env=env)
    controller.update_screenshot_cache()
    manager = SceneManager(hwnd=0, win_controller=controller)
    manager.register_scenes_from_directory(
        str(PROJECT_ROOT / "yys/common/images/scene"),
        str(PROJECT_ROOT / "yys/common/images/scene_control"),
    )

    assert manager.goto_scene("barrier_breakthrough") is True
    assert env.get_current_scene() == "barrier_breakthrough"
    action_log.assert_click_count(2)
    action_log.assert_click_at(610, 140, tolerance=12)
    action_log.assert_click_at(253, 592, tolerance=12)


def test_recorded_main_fixture_replays_attack_and_retry_paths() -> None:
    """正式主流程夹具应覆盖进攻、失败重试和下一目标。"""
    env = _create_environment("main", "barrier_breakthrough")

    env.left_click(567, 300)
    assert env.get_current_scene() == "attack_dialog"
    env.left_click(670, 471)
    assert env.get_current_scene() == "battling"

    env.set_scene("battle_loss")
    env.left_click(757, 466)
    assert env.get_current_scene() == "retry_dialog"
    env.left_click(692, 387)
    assert env.get_current_scene() == "battling"

    env.set_scene("grid_after_first_win")
    env.left_click(880, 291)
    assert env.get_current_scene() == "attack_dialog"


def test_recorded_refresh_fixture_replays_automatic_new_grid() -> None:
    """最后一个目标结算后应直接进入新九宫格，不依赖刷新确认框。"""
    env = _create_environment("refresh", "last_attack_dialog")

    env.left_click(919, 587)
    assert env.get_current_scene() == "last_battle"
    env.set_scene("settlement_reward")
    env.left_click(851, 471)

    assert env.get_current_scene() == "new_grid"


def test_record_zero_template_matches_recorded_new_grid() -> None:
    """自动换组判据必须能在正式录制的新九宫格上命中。"""
    env = _create_environment("refresh", "new_grid")
    controller = WinController(env=env)
    controller.update_screenshot_cache()

    point = controller.find_image(
        "yys/realm_raid/images/realm_raid_record_zero.bmp",
        x0=0,
        y0=480,
        x1=280,
        y1=620,
    )

    assert point != (-1, -1)


def test_script_treats_recorded_battle_as_known_scene(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正式录制的战斗画面必须重置未知场景计数，且不得产生输入。"""
    monkeypatch.setattr(event_module.time, "sleep", lambda _seconds: None)
    action_log = ActionLog()
    env = _create_environment("main", "battling", action_log)
    script = RealmRaidScript(env=env)
    script.image_finder.update_screenshot_cache()

    triggered_event = script._trigger_event_from_screenshot_cache()

    assert triggered_event == "yys/realm_raid/images/realm_raid_battling.bmp"
    assert action_log.records == []


def test_battle_running_template_does_not_match_recorded_summary() -> None:
    """持久战斗标记不能把战后总结画面误判为仍在战斗。"""
    env = _create_environment("refresh", "last_battle")
    controller = WinController(env=env)
    controller.update_screenshot_cache()

    point = controller.find_image(
        "yys/realm_raid/images/realm_raid_battling.bmp",
        x0=0,
        y0=520,
        x1=130,
        y1=640,
    )

    assert point == (-1, -1)
