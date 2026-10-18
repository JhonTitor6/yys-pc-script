"""每日活跃度奖励录制夹具回归。"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from tests.common.environment.mock_environment import MockEnvironment
from win_util.environment.guarded import GuardedEnvironment, RunGuard
from yys.daily_activity_rewards.daily_activity_rewards_script import (
    DailyActivityRewardsScript,
    RewardState,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "daily_activity_rewards"
IMAGES = ROOT / "yys" / "daily_activity_rewards" / "images"
SIZE = (1136, 640)


@pytest.fixture(autouse=True)
def _reuse_ocr_for_identical_replay_frames(
    monkeypatch: pytest.MonkeyPatch, cached_test_ocr: object,
) -> None:
    """相同回放帧复用 OCR；每种不同真实页面仍执行实际识别。"""
    monkeypatch.setattr("win_util.controller.CommonOcr", lambda: cached_test_ocr)


def _image(path: Path) -> np.ndarray:
    """读取裁切后的脱敏测试帧。"""
    image = cv2.imread(str(path))
    assert image is not None
    return image


def _frame(parts: list[tuple[Path, tuple[int, int]]]) -> np.ndarray:
    """将脱敏局部夹具放回其原始客户区位置。"""
    result = np.zeros((SIZE[1], SIZE[0], 3), dtype=np.uint8)
    for path, (x, y) in parts:
        image = _image(path)
        height, width = image.shape[:2]
        result[y:y + height, x:x + width] = image
    return result


def _home_frame(menu_open: bool) -> np.ndarray:
    parts = [(FIXTURES / "home_scene_marker.png", (630, 230))]
    if menu_open:
        parts.extend([
            (FIXTURES / "home_menu_expanded.png", (35, 520)),
            (FIXTURES / "home_menu_state.png", (1028, 440)),
        ])
    else:
        parts.append((IMAGES / "menu_toggle.png", (1045, 548)))
    return _frame(parts)


def _activity_frame(claimed: bool) -> np.ndarray:
    content = "activity_claimed.png" if claimed else "activity_claimable.png"
    top = 90 if claimed else 115
    return _frame([
        (FIXTURES / "activity_header.png", (0, 0)),
        (FIXTURES / content, (430, top)),
    ])


def _reward_frame() -> np.ndarray:
    return _frame([
        (FIXTURES / "activity_header.png", (0, 0)),
        (FIXTURES / "activity_claimable.png", (430, 115)),
        (FIXTURES / "reward_dialog.png", (300, 190)),
    ])


class _ReplayEnvironment(MockEnvironment):
    """按输入推进脱敏录制帧的环境。"""

    def __init__(self, frames: list[np.ndarray]) -> None:
        super().__init__()
        self._frames = frames
        self._index = 0
        self.inputs: list[tuple[int, int]] = []

    def capture_screen(self) -> Image.Image:
        rgb = cv2.cvtColor(self._frames[self._index], cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def left_click(self, x: int, y: int) -> None:
        super().left_click(x, y)
        self.inputs.append((x, y))
        self._index = min(self._index + 1, len(self._frames) - 1)


def test_classifies_all_reward_states() -> None:
    script = object.__new__(DailyActivityRewardsScript)
    frame = np.zeros((SIZE[1], SIZE[0], 3), dtype=np.uint8)

    setattr(script, "_daily_experience", lambda _frame: 0)
    setattr(script, "_claim_button", lambda _frame: (835, 562))
    assert script._classify_rewards(frame) == (RewardState.CLAIMABLE, 0, (835, 562))

    setattr(script, "_claim_button", lambda _frame: None)
    assert script._classify_rewards(frame) == (RewardState.NOT_ELIGIBLE, 0, None)
    setattr(script, "_daily_experience", lambda _frame: 36)
    assert script._classify_rewards(frame) == (RewardState.CLAIMED, 36, None)
    setattr(script, "_daily_experience", lambda _frame: None)
    assert script._classify_rewards(frame) == (RewardState.UNKNOWN, None, None)


def test_current_live_sakura_skin_is_home_but_activity_page_is_not() -> None:
    """产品契约：实机樱花庭院变体可识别，旧场景和非庭院负样本行为不变。"""
    frame = _image(ROOT / "tests/fixtures/lineup_switch/skins/home_day_current.png")
    env = _ReplayEnvironment([frame])
    script = DailyActivityRewardsScript(env=env)
    assert script._is_home(frame)
    assert not script._is_home(_activity_frame(claimed=False))
    assert env.inputs == []


def test_replay_claims_once_cleans_duplicate_reward_and_returns_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("yys.common.event_script_base.time.sleep", lambda _seconds: None)
    env = _ReplayEnvironment([
        _home_frame(menu_open=False),
        _home_frame(menu_open=True),
        _activity_frame(claimed=False),
        _reward_frame(),
        _reward_frame(),
        _activity_frame(claimed=True),
        _home_frame(menu_open=False),
    ])
    script = DailyActivityRewardsScript(env=env)

    script.run()

    snapshot = script.get_state_snapshot()
    assert snapshot["stage"] == "done"
    assert snapshot["outcome"] == "completed"
    assert snapshot["reward_state"] == RewardState.CLAIMED.value
    assert snapshot["claimed_count"] == 1
    assert snapshot["battle_count"] == 0
    assert len(env.inputs) == 6
    assert sum(780 <= x <= 900 and 520 <= y <= 610 for x, y in env.inputs) == 1
    assert sum(430 <= x <= 710 and 185 <= y <= 260 for x, y in env.inputs) == 2


def test_repeated_reward_frame_cleanup_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("yys.common.event_script_base.time.sleep", lambda _seconds: None)
    env = _ReplayEnvironment([
        _home_frame(menu_open=False),
        _home_frame(menu_open=True),
        _activity_frame(claimed=False),
        _reward_frame(),
        _reward_frame(),
        _reward_frame(),
        _reward_frame(),
    ])
    script = DailyActivityRewardsScript(env=env)

    with pytest.raises(RuntimeError, match="DAILY_REWARD_LIMIT"):
        script.run()

    assert script.get_state_snapshot()["stage"] == "failed"
    assert sum(780 <= x <= 900 and 520 <= y <= 610 for x, y in env.inputs) == 1
    assert sum(430 <= x <= 710 and 185 <= y <= 260 for x, y in env.inputs) == 3


def test_observe_mode_records_one_plan_without_sending_input() -> None:
    delegate = _ReplayEnvironment([_home_frame(menu_open=False)])
    guard = RunGuard(timeout_seconds=60, max_actions=8, unknown_limit=3)
    observed = GuardedEnvironment(delegate, guard, observe_only=True)
    script = DailyActivityRewardsScript(env=observed)

    with pytest.raises(RuntimeError, match="DAILY_OBSERVE"):
        script.run()

    assert script.get_state_snapshot()["outcome"] == "observing"
    assert delegate.inputs == []
    assert len(observed.action_records) == 1


def test_stop_before_entry_sends_no_input() -> None:
    env = _ReplayEnvironment([_home_frame(menu_open=False)])
    script = DailyActivityRewardsScript(env=env)
    script.stop()

    script.run()

    assert script.get_state_snapshot()["outcome"] == "stopped"
    assert env.inputs == []


def test_remembered_rewards_tab_opens_tasks_before_classifying_daily_rewards() -> None:
    """产品契约：实机花合战记住奖励页时，识别任务标签后才检查今日领奖。"""
    rewards = _image(FIXTURES / "activity_rewards_tab.png")
    env = _ReplayEnvironment([rewards, _activity_frame(claimed=True), _home_frame(menu_open=False)])
    script = DailyActivityRewardsScript(env=env)
    assert script._is_flower_page(rewards)
    assert not script._is_activity_page(rewards)
    script.run()
    assert len(env.inputs) == 2
    assert env.inputs[0][0] > 1040 and 270 < env.inputs[0][1] < 430
    assert script.get_state_snapshot()["outcome"] == "completed"
    assert script.get_state_snapshot()["claimed_count"] == 0
