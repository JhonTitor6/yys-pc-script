from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PIL import Image

from tests.common.environment.mock_environment import MockEnvironment
from ui_backend.scripts.registry import ScriptRegistry
from yys.super_demon_boss.super_demon_boss_script import SuperDemonBossScript


def _frame(*templates: tuple[str, int, int]) -> np.ndarray:
    frame = np.zeros((641, 1138, 3), dtype=np.uint8)
    for path, x, y in templates:
        template = cv2.imread(path)
        assert template is not None, path
        height, width = template.shape[:2]
        frame[y:y + height, x:x + width] = template
    return frame


@pytest.mark.parametrize(("action", "stage"), [
    ("pause", "summon"), ("stop", "challenge"), ("pause", "settlement"),
])
def test_pending_click_is_cancelled(
    monkeypatch: pytest.MonkeyPatch, action: str, stage: str,
) -> None:
    """产品契约：已匹配的画面在暂停或停止后不能发出点击或推进步骤。"""
    env = MockEnvironment()
    monkeypatch.setattr(env, "capture_screen", lambda: Image.new("RGB", (1138, 641)))
    script = SuperDemonBossScript(env=env)
    script.on_run()

    activity = ("yys/super_demon_boss/images/activity.png", 130, 15)
    summon = ("yys/super_demon_boss/images/summon.png", 1019, 520)
    challenge = ("yys/common_challenge/images/challenge.bmp", 1010, 540)
    loss = ("yys/images/battle_end_loss.bmp", 382, 85)
    script.image_finder.screenshot_cache = _frame(activity, summon if stage == "summon" else challenge)
    interrupt_module = "win_util.event.time"
    expected_clicks = 0
    if stage == "settlement":
        script._trigger_event_from_screenshot_cache()
        expected_clicks = 1
        script.image_finder.screenshot_cache = _frame(loss)
        interrupt_module = "yys.common.event_script_base.time"

    with monkeypatch.context() as interrupt:
        interrupt.setattr(interrupt_module, SimpleNamespace(sleep=lambda _: getattr(script, action)()))
        assert script._trigger_event_from_screenshot_cache() is None

    env.action_log.assert_click_count(expected_clicks)
    assert not script._summon_requested
    assert script.get_state_snapshot()["battle_count"] == 0

    if action == "pause":
        script.resume()
        monkeypatch.setattr("yys.common.event_script_base.BATTLE_END_SLEEP", 0)
        monkeypatch.setattr("yys.common.event_script_base.BATTLE_END_CLICK_SLEEP", 0)
        script._trigger_event_from_screenshot_cache()
        env.action_log.assert_click_count(expected_clicks + 1)


@pytest.mark.parametrize(("already_summoned", "result", "target"), [
    (False, "reward", 1), (True, "direct", 1), (False, "loss", 1),
    (False, "reward", 2), (True, "direct", 2), (False, "loss", 2),
])
def test_battle_count_from_workbench_config(
    monkeypatch: pytest.MonkeyPatch, already_summoned: bool, result: str, target: int,
) -> None:
    """产品契约：按 GUI 目标场数运行，加载零输入，同一场结算只计一次。"""
    monkeypatch.setattr("win_util.event.EVENT_TRIGGER_DELAY", 0)
    for delay in ("BATTLE_VICTORY_SLEEP", "BATTLE_END_SLEEP", "BATTLE_END_CLICK_SLEEP"):
        monkeypatch.setattr(f"yys.common.event_script_base.{delay}", 0)
    env = MockEnvironment()
    monkeypatch.setattr(env, "capture_screen", lambda: Image.new("RGB", (1138, 641)))
    registry = ScriptRegistry()
    definition = registry.get("super_demon_boss")
    assert definition.config_schema[0].label == "战斗场数"
    assert definition.default_config == {"max_battle_count": 20}
    script = registry.load_class("super_demon_boss")(config={"max_battle_count": target}, env=env)
    script.on_run()

    activity = ("yys/super_demon_boss/images/activity.png", 130, 15)
    summon = ("yys/super_demon_boss/images/summon.png", 1019, 520)
    challenge = ("yys/common_challenge/images/challenge.bmp", 1010, 540)
    ready = ("yys/images/ready.bmp", 990, 555)
    battling = ("yys/common/images/scene/battling.bmp", 40, 50)
    victory = ("yys/images/battle_end.bmp", 381, 84)

    def show(click_count: int, *templates: tuple[str, int, int]) -> None:
        script.before_iteration()
        script.image_finder.screenshot_cache = _frame(*templates)
        script._trigger_event_from_screenshot_cache()
        script.after_iteration()
        env.action_log.assert_click_count(click_count)

    show(0, challenge)
    show(0, summon)
    clicks = 0
    if not already_summoned:
        clicks += 1
        show(clicks, activity, summon)
        show(clicks, activity, summon)
        env.action_log.assert_click_at(1049, 552, tolerance=1)

    clicks += 1
    show(clicks, activity, challenge)
    env.action_log.assert_click_at(1046, 560, tolerance=0)
    show(clicks, activity, challenge)
    show(clicks)
    # 实机准备按钮出现前后都可能匹配战斗返回图标。
    show(clicks, battling)
    if not already_summoned:
        clicks += 1
        show(clicks, battling, ready)
        show(clicks, battling, ready)
        env.action_log.assert_click_at(1030, 580, tolerance=0)
    show(clicks, battling)
    assert script.get_state_snapshot()["battle_count"] == 0

    settlement = None
    if result != "loss":
        clicks += 1
        show(clicks, victory)
        assert script.get_state_snapshot()["battle_count"] == 0
        assert not script._stop_threading_event.is_set()
    if result == "loss":
        settlement = ("yys/images/battle_end_loss.bmp", 382, 85)
    elif result == "reward":
        settlement = ("yys/common_challenge/images/gained_reward.bmp", 451, 130)

    if settlement is not None:
        clicks += 1
        show(clicks, settlement)
    else:
        show(clicks, activity, summon)

    assert script.get_state_snapshot()["battle_count"] == 1
    if target == 2:
        assert not script._stop_threading_event.is_set()
        if settlement is not None:
            clicks += 1
            show(clicks, settlement)
            assert script.get_state_snapshot()["battle_count"] == 1
            show(clicks, activity, summon)
        show(clicks + 1, activity, summon)
        show(clicks + 2, activity, challenge)
        show(clicks + 3, victory)
        show(clicks + 3, activity, summon)

    snapshot = script.get_state_snapshot()
    assert snapshot["battle_count"] == snapshot["max_battle_count"] == target
    assert snapshot["victory_count"] == target - int(result == "loss")
    assert script._stop_threading_event.is_set()
