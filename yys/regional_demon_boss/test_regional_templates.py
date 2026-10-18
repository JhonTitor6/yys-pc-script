"""地域鬼王生产模板的真实录制帧回归。"""

from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np

from yys.regional_demon_boss.regional_demon_boss_script import RegionalDemonBossScript


FIXTURES = Path("tests/fixtures/regional_demon_boss")


def _script() -> RegionalDemonBossScript:
    """只加载生产模板，避免测试构造真实游戏环境。"""
    script = object.__new__(RegionalDemonBossScript)
    script._templates = {}
    script._load_templates()
    return script


def _frame(name: str) -> np.ndarray:
    frame = cv2.imdecode(np.fromfile(FIXTURES / f"{name}.png", dtype=np.uint8), cv2.IMREAD_COLOR)
    assert frame is not None
    return frame


def test_map_target_and_detail_actions_match_only_confirmed_pages() -> None:
    """产品契约：目标和挑战只能来自对应真实页面，转场暗层不得触发挑战。"""
    script = _script()

    assert script._find_template(_frame("map_initial"), "map") is not None
    assert script._find_template(_frame("map_initial"), "target") is None
    assert script._find_template(_frame("map_target"), "target") == (761, 256)
    assert script._find_template(_frame("detail"), "detail_title") is not None
    assert script._find_template(_frame("detail"), "detail_boss") is not None
    assert script._find_template(_frame("detail"), "challenge") == (1027, 507)
    assert script._find_template(_frame("detail_transition"), "challenge") is None


def test_recorded_entry_templates_find_the_recorded_actions() -> None:
    """产品契约：庭院和探索入口必须在录制动作位置附近识别，不能使用旧盲点。"""
    script = _script()

    assert script._find_template(_frame("home_entry"), "home") == (445, 130)
    assert script._find_template(_frame("home_entry"), "home_to_exploration") == (445, 130)
    assert script._find_template(_frame("exploration_entry"), "exploration") == (585, 582)
    assert script._find_template(_frame("exploration_entry"), "exploration_to_regional") == (585, 582)


def test_home_marker_searches_panned_skin_across_the_client_area() -> None:
    """产品契约：镜头平移后的新皮肤庭院仍须命中真实灯笼位置。"""
    script = _script()
    frame = _frame("home_pan_night")

    assert script._find_template(frame, "home") == (557, 145)
    assert script._find_template(frame, "home_to_exploration") == (557, 145)
    for name in (
        "exploration_entry",
        "map_initial",
        "map_target",
        "detail",
        "detail_transition",
        "preparation",
        "battling_early",
        "battling_middle",
        "battling_late",
        "result",
        "reward",
    ):
        assert script._find_template(_frame(name), "home") is None


def test_battle_and_settlement_templates_separate_long_lived_states() -> None:
    """产品契约：战斗早中晚均已知，结算与奖励互不冒认且共用已识别继续位置。"""
    script = _script()

    for name in ("battling_early", "battling_middle", "battling_late"):
        # 产品契约：单张生产模板覆盖战斗早、中、晚真实截图。
        assert script._find_template(_frame(name), "battle") is not None
        assert script._find_template(_frame(name), "settlement_success") is None
    assert script._find_template(_frame("result"), "battle") is None
    assert script._find_template(_frame("result"), "settlement_success") is not None
    assert script._find_template(_frame("result"), "reward") is None
    assert script._find_template(_frame("reward"), "settlement_success") is None
    assert script._find_template(_frame("reward"), "reward") is not None
    assert script._find_template(_frame("result"), "settlement_continue") is not None
    assert script._find_template(_frame("reward"), "settlement_continue") is not None


def test_live_loading_waits_without_input_or_weakening_unknown_guard() -> None:
    """产品契约：2026-10-18 实机加载页只等待，普通未知画面仍交给保险丝。"""
    script = _script()
    loading = _frame("loading_live")
    exploration = _frame("exploration_entry")
    assert script._find_template(loading, "loading") is not None
    assert script._find_template(exploration, "loading") is None
    frames = iter([loading] * 4 + [exploration])
    script._read_frame = lambda: next(frames)
    script._checkpoint = Mock()
    script._recognized = Mock()
    script._unknown = Mock(side_effect=AssertionError("已确认加载页不算未知"))
    script._runtime_env = Mock()
    script._deadline = float("inf")
    assert script._wait_until(script._is_exploration, "未进入探索", "test") is exploration
    script._runtime_env.left_click.assert_not_called()
