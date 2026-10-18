"""逢魔真实帧和未完成边界回归。"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from win_util.environment.guarded import GuardedEnvironment, RunGuard
from win_util.image import ImageFinder
from win_util.ocr import CommonOcr
from yys.fengmo.fengmo_script import FengmoScript


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/fengmo"


def script() -> FengmoScript:
    """构造离线识别器，不连接游戏。"""
    result = FengmoScript.__new__(FengmoScript)
    result._images = ROOT / "yys/fengmo/images"
    result.image_finder = ImageFinder.__new__(ImageFinder)
    result.image_finder.screenshot_capture = Mock(save_source_img=False)
    result.pause_point = Mock()
    result._run_guard = None
    result._stop_threading_event = threading.Event()
    result._size = result.SIZE
    result.ocr = Mock()
    result.ocr.find_all_text_positions.return_value = []
    result.logger = Mock()
    result._cur_battle_count = 0
    result._cur_battle_victory_count = 0
    result.max_battle_count = 1
    result.script_name = "fengmo"
    result._stage = "initial"
    result._settlement_seen = False
    result._victory_seen = False
    return result


@pytest.mark.parametrize("scene,marker", [
    ("home", "home"), ("home", "daily_entry"), ("daily", "entry"),
    ("map", "map"), ("explored", "claim"), ("reward", "reward"),
    ("boss", "boss"), ("detail", "detail"), ("lobby", "lobby"),
])
def test_recorded_markers_and_foreign_page(scene: str, marker: str) -> None:
    # 产品契约来源：逢魔只接受自身录制标记，不以狭间页面替代。
    runner = script()
    assert runner._match(cv2.imread(str(FIXTURES / f"{scene}.png")), marker) is not None
    foreign = cv2.imread(str(ROOT / "tests/fixtures/realm_foster/taiko.png"))
    assert runner._match(foreign, marker) is None


def test_remaining_count_requires_map_and_exact_counter() -> None:
    # 产品契约来源：不能把任意 0 或挑战次数当作探索完成。
    runner = script()
    frame = cv2.imread(str(FIXTURES / "map.png"))
    assert runner._remaining(frame) == 4
    frame[600:641, 1060:1138] = 0
    with pytest.raises(RuntimeError, match="FENGMO_COUNT"):
        runner._remaining(frame)


def test_real_frame_distinguishes_four_explorations_and_zero_remaining() -> None:
    # 产品契约来源：本录制探索前 4/4，探索后 0/4；校验真实小字 ROI。
    runner = script()
    assert runner._remaining(cv2.imread(str(FIXTURES / "map.png"))) == 4
    assert runner._remaining(cv2.imread(str(FIXTURES / "explored.png"))) == 0


def test_lobby_continues_shared_finish_instead_of_requiring_recording() -> None:
    # 产品契约来源：用户明确结算、领奖复用现有处理，不在集结页要求重复录制。
    runner = script()
    runner.on_run = Mock()
    runner._env = Mock(observe_only=False)
    runner._read = Mock(return_value=cv2.imread(str(FIXTURES / "lobby.png")))
    runner._finish_battle_and_return = Mock()
    runner.run()
    runner._finish_battle_and_return.assert_called_once()
    assert not runner.get_state_snapshot()["flow_complete"]


def test_observe_does_not_switch_lineup_or_send_input() -> None:
    # 产品契约来源：观察模式只记录当前页一步，不做预设切换和真实输入。
    runner = script()
    runner.on_run = Mock()
    runner._read = Mock(return_value=cv2.imread(str(FIXTURES / "home.png")))
    runner.switch_lineup = Mock()
    delegate = Mock()
    runner._env = GuardedEnvironment(delegate, RunGuard(), observe_only=True)
    runner.run()
    runner.switch_lineup.assert_not_called()
    delegate.left_click.assert_not_called()
    assert len(runner._env.action_records) == 1


def test_reused_settlement_counts_once_and_all_clicks_use_guarded_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 产品契约来源：结算、领奖复用公共回调；多层／重复页面不得计多场。
    runner = script()
    delegate = Mock()
    runner._env = GuardedEnvironment(delegate, RunGuard(), observe_only=False)
    monkeypatch.setattr("yys.common.event_script_base.time.sleep", lambda _: None)
    runner._consume_settlement("victory", (400, 300))
    runner._consume_settlement("victory", (400, 300))
    runner._consume_settlement("reward", (500, 200))
    runner._consume_settlement("reward", (500, 200))
    assert runner._cur_battle_count == 1
    assert runner._cur_battle_victory_count == 1
    assert len(runner._env.action_records) == 4
    assert [(call.args) for call in delegate.left_click.call_args_list][-2:] == [(960, 535)] * 2
    runner._consume_settlement("continue", (567, 620))
    assert runner._cur_battle_count == 1
    assert runner._cur_battle_victory_count == 1
    assert delegate.left_click.call_args_list[-1].args == (567, 460)


def test_return_uses_return_then_to_home_on_fresh_frames_and_verifies_home() -> None:
    # 产品契约来源：用户“先点返回按钮，再点 to_home”；两个按钮同屏也不反序。
    runner = script()
    delegate = Mock()
    runner._env = GuardedEnvironment(delegate, RunGuard(), observe_only=False)
    initial, returned, home = [np.full((641, 1138, 3), value, dtype=np.uint8) for value in (1, 2, 3)]
    runner._read = Mock(side_effect=[initial, returned, home])
    runner._settlement = Mock(return_value=None)
    history: list[tuple[int, str]] = []

    def shared(frame: np.ndarray, path: str) -> tuple[int, int] | None:
        scene = int(frame[0, 0, 0])
        history.append((scene, path))
        if path == runner.RETURN_IMAGE and scene == 1:
            return 25, 40
        if path == runner.HOME_IMAGE and scene in (1, 2):
            return 105, 40
        return None

    runner._shared_match = shared
    runner._match = lambda frame, name: (600, 150) if name == "home" and frame is home else None
    runner._return_home()
    assert [call.args for call in delegate.left_click.call_args_list] == [(25, 40), (105, 40)]
    assert (2, runner.HOME_IMAGE) in history
    assert runner._read.call_count == 3
    assert not runner.get_state_snapshot()["flow_complete"]


def test_waiting_battle_sends_no_input_then_clears_settlement_and_returns() -> None:
    # 产品契约来源：集结与战斗零输入，看到结算并确认庭院后才能报告完成。
    runner = script()
    frames = [np.full((641, 1138, 3), value, dtype=np.uint8) for value in (1, 2, 3, 4)]
    runner._read = Mock(side_effect=frames)
    runner._settlement = lambda frame: ("victory", (400, 300)) if int(frame[0, 0, 0]) == 3 else None
    runner._shared_match = lambda frame, path: (50, 50) if int(frame[0, 0, 0]) == 2 and path == runner.BATTLE_IMAGE else None
    runner._match = lambda frame, name: (30, 450) if int(frame[0, 0, 0]) == 1 and name == "lobby" else None
    runner._env = GuardedEnvironment(Mock(), RunGuard(), observe_only=False)
    clicks: list[int] = []

    def consume(_kind: str, _point: tuple[int, int]) -> None:
        clicks.append(runner._read.call_count)
        runner._settlement_seen = True

    runner._consume_settlement = consume
    runner._return_home = Mock()
    runner._finish_battle_and_return()
    assert clicks == [3]
    runner._return_home.assert_called_once()
    assert runner.get_state_snapshot()["flow_complete"]


def test_missing_navigation_or_stop_cannot_report_complete() -> None:
    # 产品契约来源：缺少返回、to_home 或庭院确认时不能提前成功；停止后零输入。
    runner = script()
    delegate = Mock()
    runner._env = GuardedEnvironment(delegate, RunGuard(), observe_only=False)
    runner._wait = Mock(side_effect=RuntimeError("FENGMO_TRANSITION"))
    with pytest.raises(RuntimeError, match="FENGMO_TRANSITION"):
        runner._return_home()
    assert not runner.get_state_snapshot()["flow_complete"]
    delegate.left_click.assert_not_called()
    runner._stop_threading_event.set()
    runner._read = FengmoScript._read.__get__(runner)
    with pytest.raises(Exception) as stopped:
        runner._read()
    assert type(stopped.value).__name__ == "_Stopped"
    delegate.left_click.assert_not_called()


def test_reused_controls_match_real_map_and_return_in_order() -> None:
    # 产品契约来源：返回和 to_home 复用现有图片，在逢魔真实页验证位置和次序。
    runner = script()
    delegate = Mock()
    runner._env = GuardedEnvironment(delegate, RunGuard(), observe_only=False)
    runner._settlement_seen = True
    frames = [cv2.imread(str(FIXTURES / f"{name}.png")) for name in ("lobby", "map", "home")]
    runner._read = Mock(side_effect=frames)
    runner._return_home()
    points = [call.args for call in delegate.left_click.call_args_list]
    assert len(points) == 2
    assert points[0][0] < 60 and points[1][0] > 90
    assert runner._read.call_count == 3


def test_reused_real_settlement_and_battle_marker_have_expected_boundaries() -> None:
    # 产品契约来源：用户要求通用结算复用，既有真实帧中的继续文字与战斗标记能识别。
    runner = script()
    runner.ocr = CommonOcr()
    frame = cv2.imread(str(ROOT / "tests/fixtures/regional_demon_boss/result.png"))
    assert runner._settlement(frame)[0] == "continue"
    reward = cv2.imread(str(FIXTURES / "reward.png"))
    assert runner._settlement(reward)[0] == "reward"
    for name in ("battling_early.png", "battling_middle.png", "battling_late.png"):
        frame = cv2.imread(str(ROOT / "tests/fixtures/regional_demon_boss" / name))
        assert runner._shared_match(frame, runner.BATTLE_IMAGE) is not None
        assert runner._match(frame, "lobby") is None
