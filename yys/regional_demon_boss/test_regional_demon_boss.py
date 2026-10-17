"""地域鬼王真实帧回放与安全边界测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
from unittest.mock import Mock

import cv2
import numpy as np
import pytest
from PIL import Image

from win_util.environment.guarded import GuardedEnvironment, RunGuard
from yys.regional_demon_boss.regional_demon_boss_script import (
    RegionalDemonBossError,
    RegionalDemonBossScript,
    RegionalDemonBossState,
    _TemplateSpec,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "regional_demon_boss"
ROI = RegionalDemonBossScript.CLIENT_ROI


class ReplayEnvironment:
    """只提供客户区截图与输入记录的可控回放环境。"""

    def __init__(self, frames: list[str], *, observe_only: bool = False) -> None:
        self._frames = [FIXTURES / name for name in frames]
        self._index = 0
        self.observe_only = observe_only
        self.actions: list[tuple[str, tuple[int, ...], int]] = []

    def capture_screen(self) -> Image.Image:
        path = self._frames[min(self._index, len(self._frames) - 1)]
        self._index += 1
        with Image.open(path) as image:
            return image.convert("RGB")

    def left_click(self, x: int, y: int) -> None:
        self.actions.append(("left_click", (x, y), self._index))

    def right_click(self, x: int, y: int) -> None:
        self.actions.append(("right_click", (x, y), self._index))

    def left_double_click(self, x: int, y: int) -> None:
        self.actions.append(("left_double_click", (x, y), self._index))

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self.actions.append(("drag", (x1, y1, x2, y2), self._index))

    def wheel(self, x: int, y: int, delta: int) -> None:
        self.actions.append(("wheel", (x, y, delta), self._index))

    def key_press(self, key_code: int) -> None:
        self.actions.append(("key_press", (key_code,), self._index))

    def key_down(self, key_code: int) -> None:
        self.actions.append(("key_down", (key_code,), self._index))

    def key_up(self, key_code: int) -> None:
        self.actions.append(("key_up", (key_code,), self._index))

    def set_mouse_position(self, x: int, y: int) -> None:
        self.actions.append(("set_mouse_position", (x, y), self._index))

    def get_window_client_rect(self) -> tuple[int, int, int, int]:
        return (0, 0, 1136, 640)

    def find_window(self, _title_part: str) -> Optional[int]:
        return 12345


def _specs(*, failure: bool = False) -> dict[str, tuple[_TemplateSpec, ...]]:
    def one(name: str) -> tuple[_TemplateSpec, ...]:
        return (_TemplateSpec(str(FIXTURES / name), ROI),)

    specs: dict[str, tuple[_TemplateSpec, ...]] = {
        "home": one("home.png"),
        "home_to_exploration": one("home.png"),
        "exploration": one("exploration.png"),
        "exploration_to_regional": one("exploration.png"),
        "map": one("map_initial.png"),
        "target": (_TemplateSpec(str(FIXTURES / "map_target.png"), ROI, 0.95),),
        "detail_title": one("detail.png"),
        "detail_boss": one("detail.png"),
        "challenge": one("detail.png"),
        "preparation": one("preparation.png"),
        "battle": (
            _TemplateSpec(str(FIXTURES / "battling_early.png"), ROI),
            _TemplateSpec(str(FIXTURES / "battling_middle.png"), ROI),
            _TemplateSpec(str(FIXTURES / "battling_late.png"), ROI),
        ),
        "settlement_success": one("result.png"),
        "settlement_failure": one("detail_return.png" if failure else "result.png"),
        "reward": one("reward.png"),
        "settlement_continue": (
            _TemplateSpec(str(FIXTURES / "result.png"), ROI),
            _TemplateSpec(str(FIXTURES / "reward.png"), ROI),
            _TemplateSpec(str(FIXTURES / "detail_return.png"), ROI),
        ),
        "return": one("lineup_preset.png"),
    }
    if not failure:
        specs["settlement_failure"] = ()
    return specs


def _script(
    env: ReplayEnvironment,
    *,
    failure: bool = False,
) -> RegionalDemonBossScript:
    # WinController/ImageFinder 会在构造时刷新一次截图缓存；回放保留首帧供业务入口再次读取。
    env._frames.insert(0, env._frames[0])
    script = RegionalDemonBossScript.__new__(RegionalDemonBossScript)
    original = RegionalDemonBossScript._TEMPLATE_SPECS
    RegionalDemonBossScript._TEMPLATE_SPECS = _specs(failure=failure)
    try:
        script.__init__(env=env, config={})
    finally:
        RegionalDemonBossScript._TEMPLATE_SPECS = original
    script.switch_lineup = Mock()  # type: ignore[method-assign]
    script.POLL_INTERVAL_SECONDS = 0
    script.FLOW_TIMEOUT_SECONDS = 30
    return script


def _success_frames() -> list[str]:
    return [
        "home.png",
        "lineup_preset.png",
        "home.png",
        "home.png",
        "exploration.png",
        "map_initial.png",
        "map_initial.png",
        "map_target.png",
        "detail.png",
        "detail.png",
        "detail.png",
        "preparation.png",
        "battling_early.png",
        "battling_middle.png",
        "battling_late.png",
        "result.png",
        "result.png",
        "reward.png",
        "reward.png",
        "detail.png",
    ]


def test_recorded_flow_challenges_once_and_waits_for_detail_return() -> None:
    """产品契约：一次拖拽、一次挑战，结算重复帧只清理不重复计数。"""
    env = ReplayEnvironment(_success_frames())
    script = _script(env)

    script.run()

    assert script.switch_lineup.call_args.args == ("地域鬼王", "悬赏")
    assert script.switch_lineup.call_args.kwargs == {"home_verified": True}
    assert script._drag_used is True
    assert len([a for a in env.actions if a[0] == "drag"]) == 1
    assert script._challenge_sent is True
    assert script._settlement_consumed is True
    assert script._settlement_clicks == 4
    assert script._cur_battle_count == 1
    assert script._cur_battle_victory_count == 1
    assert script._state is RegionalDemonBossState.DONE

    challenge_index = next(i for i, action in enumerate(env.actions) if action[0] == "left_click" and i >= 5)
    battle_actions = [
        action for action in env.actions[challenge_index + 1 :]
        if 11 <= action[2] <= 15
    ]
    assert battle_actions == []


def test_failure_settlement_counts_total_once_without_victory() -> None:
    """产品契约：明确失败结算只增加总次数，不增加胜利次数。"""
    env = ReplayEnvironment(["detail_return.png", "detail_return.png"])
    script = _script(env, failure=True)
    script.on_run()
    script._challenge_sent = True
    frame = cv2.imread(str(FIXTURES / "detail_return.png"))
    assert frame is not None

    script._on_settlement_frame("failure", frame)
    script._on_settlement_frame("failure", frame)

    assert script._cur_battle_count == 1
    assert script._cur_battle_victory_count == 0
    assert script._settlement_clicks == 2


def test_unknown_frame_fails_with_explicit_code() -> None:
    """产品契约：未知页面达到阈值时抛错，不猜测或盲点。"""
    env = ReplayEnvironment(["home.png"] * 4)
    script = _script(env)
    script.on_run()

    with pytest.raises(RegionalDemonBossError) as exc_info:
        script._wait_until(lambda _frame: False, "未知", "REGIONAL_UNKNOWN_SCENE")

    assert exc_info.value.code == "REGIONAL_UNKNOWN_SCENE"
    assert not env.actions


def test_observe_only_plans_current_page_without_lineup_or_wait() -> None:
    """产品契约：观察模式只记录当前页动作，不切阵容、不等待转场。"""
    env = ReplayEnvironment(["home.png"], observe_only=True)
    script = _script(env)

    script.run()

    script.switch_lineup.assert_not_called()
    assert [a[0] for a in env.actions] == ["left_click"]
    assert script._stop_reason == "observe_only"


def test_constructor_rejects_missing_production_template() -> None:
    """产品契约：缺少真实模板在构造阶段明确失败。"""
    env = ReplayEnvironment(["home.png"])
    specs = _specs()
    specs["map"] = (_TemplateSpec(str(FIXTURES / "missing.bmp"), ROI),)
    original = RegionalDemonBossScript._TEMPLATE_SPECS
    RegionalDemonBossScript._TEMPLATE_SPECS = specs
    try:
        with pytest.raises(RegionalDemonBossError) as exc_info:
            RegionalDemonBossScript(env=env, config={})
    finally:
        RegionalDemonBossScript._TEMPLATE_SPECS = original

    assert exc_info.value.code == "REGIONAL_TEMPLATE_MISSING"


def test_user_stop_returns_without_input() -> None:
    """产品契约：用户主动停止是正常返回，不发送业务输入。"""
    env = ReplayEnvironment(["home.png"])
    script = _script(env)
    script.stop()

    script.run()

    assert script._state is RegionalDemonBossState.STOPPED
    assert script._stop_reason == "user_stop"
    assert not env.actions


def test_guard_action_limit_raises_instead_of_reporting_success() -> None:
    """产品契约：保险丝拒绝动作时流程失败，不能把正常返回当作完成。"""
    env = ReplayEnvironment(_success_frames())
    script = _script(env)
    guard = RunGuard(max_actions=1)
    script._runtime_env = GuardedEnvironment(env, guard, observe_only=False)
    script.set_run_guard(guard)

    with pytest.raises(RegionalDemonBossError) as exc_info:
        script.run()

    assert exc_info.value.code == "REGIONAL_GUARD_STOPPED"
