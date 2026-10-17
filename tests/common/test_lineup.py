"""产品契约：docs/plans/2026-09-06-lineup-wheel-recording-plan.md。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import pytest
from PIL import Image

from tests.common.environment.mock_environment import MockEnvironment
from tests.common.environment.scene_replay_environment import SceneReplayEnvironment
from win_util.environment.guarded import GuardedEnvironment, RunGuard, RunStopReason
from win_util.environment.windows import WindowsEnvironment
from win_util.ocr import CommonOcr
from yys.common.lineup import LineupSwitcher

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/lineup_switch"
_REGIONAL_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/regional_demon_boss"
_SKIN_FIXTURES = _FIXTURES / "skins"


def _replay(initial: str = "home") -> SceneReplayEnvironment:
    return SceneReplayEnvironment(str(_FIXTURES), str(_FIXTURES / "fixture.json"), initial)


def test_recorded_switch_uses_real_ocr_and_same_five_actions() -> None:
    """真实录制证明的五步流程：准确选寮活动/通用，确认一次并见到成功。"""
    env = _replay()
    guarded = GuardedEnvironment(env, RunGuard(max_actions=5), observe_only=False)
    LineupSwitcher(guarded).switch("寮活动", "通用")
    assert [record.action_type for record in guarded.action_records] == ["left_click"] * 5
    assert env._current_scene == "success"


def test_skin_entry_matching_and_collapsed_menu_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """生产匹配器识别夜间入口，收起菜单先展开一次再点击入口。"""
    collapsed = cv2.imread(str(_SKIN_FIXTURES / "collapsed.png"))
    expanded = cv2.imread(str(_SKIN_FIXTURES / "expanded.png"))
    shikigami_night = cv2.imread(str(_SKIN_FIXTURES / "shikigami_night.png"))
    assert collapsed is not None
    assert expanded is not None
    assert shikigami_night is not None
    switcher = LineupSwitcher(MockEnvironment())

    assert switcher._match(expanded, "home_entry") is None
    assert switcher._match(expanded, "home_entry_night") is not None
    assert switcher._match(collapsed, "home_entry") is None
    assert switcher._match(collapsed, "home_entry_night") is None
    assert switcher._match(collapsed, "home_menu_collapsed_night") is not None
    assert switcher._match(expanded, "home_menu_collapsed_night") is None
    assert switcher._text_point(shikigami_night, "preset", "预设") == (337, 88)

    current = [Image.open(_SKIN_FIXTURES / "collapsed.png")]
    heading_ready = [False]
    panel_ready = [False]
    env = MockEnvironment()
    monkeypatch.setattr(env, "capture_screen", lambda: current[0])
    switcher = LineupSwitcher(env)
    switcher._guard = RunGuard(max_actions=5)
    monkeypatch.setattr(switcher, "_panel", lambda _: panel_ready[0])
    monkeypatch.setattr(switcher, "_heading", lambda _: heading_ready[0])
    monkeypatch.setattr(
        switcher,
        "_text_point",
        lambda _image, region, text: (335, 85)
        if (region, text) == ("preset", "预设")
        else None,
    )
    original_click = env.left_click
    click_points: list[tuple[int, int]] = []

    def click(point_x: int, point_y: int) -> None:
        click_points.append((point_x, point_y))
        original_click(point_x, point_y)
        if len(click_points) == 1:
            current[0] = Image.open(_SKIN_FIXTURES / "expanded.png")
        elif len(click_points) == 2:
            heading_ready[0] = True
        else:
            panel_ready[0] = True

    monkeypatch.setattr(env, "left_click", click)
    switcher._open_presets()

    assert len(click_points) == 3
    assert click_points[0] == (1073, 482)
    assert 978 <= click_points[1][0] <= 1056
    assert 529 <= click_points[1][1] <= 608
    assert click_points[2] == (335, 85)


def test_verified_home_allows_fixed_menu_button_without_dynamic_background() -> None:
    """产品契约：参数只放宽已确认庭院的固定菜单按钮，不放宽未知页面。"""
    menu = Image.open("yys/common/images/lineup/home_menu_expand.png").convert("RGB")
    frame = Image.new("RGB", (1136, 640))
    frame.paste(menu, (1047, 451))
    image = cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR)
    switcher = LineupSwitcher(MockEnvironment())

    assert switcher._home_menu_expand_point(image, home_verified=False) is None
    assert switcher._home_menu_expand_point(image, home_verified=True) == (1073, 482)


@pytest.mark.parametrize("reward_visible", [True, False])
def test_open_presets_dismisses_gained_reward_once(
    reward_visible: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """入口命中奖励遮罩只点击一次并等待消失，未命中不产生动作。"""
    reward_template = Image.open(Path("yys/common_challenge/images/gained_reward.bmp"))
    reward_frame = Image.new("RGB", (1136, 640))
    reward_frame.paste(reward_template.convert("RGB"), (450, 187))
    clear_frame = Image.new("RGB", (1136, 640))
    current = [reward_frame if reward_visible else clear_frame]
    captures: list[Image.Image] = []
    env = MockEnvironment()

    def capture_screen() -> Image.Image:
        captures.append(current[0])
        return current[0]

    monkeypatch.setattr(env, "capture_screen", capture_screen)
    switcher = LineupSwitcher(env)
    switcher._guard = RunGuard()
    monkeypatch.setattr(switcher, "_panel", lambda _: True)
    original_click = env.left_click

    def dismiss_reward(x: int, y: int) -> None:
        original_click(x, y)
        current[0] = clear_frame

    monkeypatch.setattr(env, "left_click", dismiss_reward)
    switcher._open_presets()

    env.action_log.assert_click_count(1 if reward_visible else 0)
    if reward_visible:
        env.action_log.assert_click_at(960, 535, tolerance=0)
        assert captures[-1] is clear_frame
        assert len(captures) >= 2


def test_direct_success_accepts_both_fresh_real_frame_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    """应用后同一张真实帧同时出现两条提示时直接成功，不点击确认。"""
    preset = Image.open(_REGIONAL_FIXTURES / "lineup_preset.png")
    direct_success = Image.open(_REGIONAL_FIXTURES / "lineup_direct_success.png")
    current = [preset]
    env = MockEnvironment()
    monkeypatch.setattr(env, "capture_screen", lambda: current[0])
    original_click = env.left_click

    def click_and_show_success(x: int, y: int) -> None:
        original_click(x, y)
        current[0] = direct_success

    monkeypatch.setattr(env, "left_click", click_and_show_success)
    LineupSwitcher(env).switch("地域鬼王", "悬赏")
    env.action_log.assert_click_count(1)


def test_direct_success_rejects_a_single_real_frame_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """只有契灵成功提示时不能把应用结果当作成功，也不能重复点击。"""
    preset = Image.open(_REGIONAL_FIXTURES / "lineup_preset.png")
    incomplete = Image.open(_REGIONAL_FIXTURES / "lineup_direct_success.png").copy()
    incomplete.paste(preset.crop((400, 160, 800, 205)), (400, 160))
    current = [preset]
    env = MockEnvironment()
    monkeypatch.setattr(env, "capture_screen", lambda: current[0])
    original_click = env.left_click

    def click_and_show_incomplete(x: int, y: int) -> None:
        original_click(x, y)
        current[0] = incomplete

    monkeypatch.setattr(env, "left_click", click_and_show_incomplete)
    clock = [0.0]

    def monotonic() -> float:
        clock[0] += 1.0
        return clock[0]

    monkeypatch.setattr("yys.common.lineup.time.monotonic", monotonic)
    monkeypatch.setattr("yys.common.lineup.time.sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="结果不确定"):
        LineupSwitcher(env).switch("地域鬼王", "悬赏")
    env.action_log.assert_click_count(1)


def test_stale_direct_success_frame_is_rejected_before_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """应用前已存在的双提示不能冒认为本次应用成功。"""
    stale = Image.open(_REGIONAL_FIXTURES / "lineup_direct_success.png")
    current = [stale]
    env = MockEnvironment()
    monkeypatch.setattr(env, "capture_screen", lambda: current[0])
    clock = [0.0]

    def monotonic() -> float:
        clock[0] += 1.0
        return clock[0]

    monkeypatch.setattr("yys.common.lineup.time.monotonic", monotonic)
    monkeypatch.setattr("yys.common.lineup.time.sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="旧成功提示未消失"):
        LineupSwitcher(env).switch("地域鬼王", "悬赏")
    env.action_log.assert_click_count(0)


def test_direct_success_requires_the_verified_preset_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同样的双提示离开预设页后不能满足直接成功契约。"""
    image = cv2.imread(str(_REGIONAL_FIXTURES / "lineup_direct_success.png"))
    switcher = LineupSwitcher(MockEnvironment())
    monkeypatch.setattr(switcher, "_panel", lambda _: False)
    assert not switcher._direct_success(image)


@pytest.mark.parametrize("initial", ["confirm", "unknown"])
def test_existing_dialog_or_unknown_screen_sends_no_input(initial: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """现存确认弹窗不能冒认为本次操作，未知画面不得猜点。"""
    env = _replay("confirm") if initial == "confirm" else MockEnvironment()
    if initial == "unknown":
        monkeypatch.setattr(env, "capture_screen", lambda: Image.new("RGB", (1136, 640)))
    guarded = GuardedEnvironment(env, RunGuard(), observe_only=False)
    with pytest.raises(RuntimeError, match="当前不是"):
        LineupSwitcher(guarded).switch("寮活动", "通用")
    assert guarded.action_records == []


def test_exact_names_do_not_match_substrings_and_duplicates_fail() -> None:
    """通用不能选中 pve通用；同屏重复全名必须失败。"""
    assert LineupSwitcher._unique([(1035, 294, "pve通用", 0.99)], "通用") is None
    assert LineupSwitcher._unique([(532, 147, "通 用", 0.99)], "通用") == (532, 147)
    with pytest.raises(RuntimeError, match="同名"):
        LineupSwitcher._unique([(1, 2, "通用", 0.99), (3, 4, "通用", 0.99)], "通用")


@pytest.mark.parametrize("region,target,expected_x", [("groups", "寮活动", 1036), ("lineups", "通用", 629)])
def test_search_scrolls_up_then_down_in_only_the_correct_list(
    monkeypatch: pytest.MonkeyPatch, region: str, target: str, expected_x: int,
) -> None:
    """可见区域没有目标时先找上边界，再下翻；两个参数不得串到另一列表。"""
    env = MockEnvironment()
    scrolls: list[tuple[int, int, int]] = []
    monkeypatch.setattr(env, "wheel", lambda *args: scrolls.append(args))
    switcher = LineupSwitcher(env)
    switcher._guard = RunGuard()
    image = cv2.imread(str(_FIXTURES / "preset_target.png"))
    monkeypatch.setattr(switcher, "_read", lambda: image)
    monkeypatch.setattr(switcher, "_panel", lambda _: True)
    monkeypatch.setattr(switcher, "_selected_group", lambda *_: True)
    monkeypatch.setattr(switcher, "_apply_point", lambda _, point: (880, point[1]))
    monkeypatch.setattr("yys.common.lineup.time.sleep", lambda _: None)

    def labels(_image: object, selected_region: str) -> list[tuple[int, int, str, float]]:
        assert selected_region == region
        if scrolls and scrolls[-1][2] < 0:
            return [(expected_x, 200, target, 0.99)]
        return [(expected_x, 100, "另一目标", 0.99)]

    monkeypatch.setattr(switcher, "_labels", labels)
    assert switcher._find_name(region, target, 8, "寮活动" if region == "lineups" else None) == (expected_x, 200)
    assert [delta for _, _, delta in scrolls] == [120, 120, -120]
    assert {x for x, _, _ in scrolls} == {expected_x}


def test_missing_target_stops_after_both_unchanged_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    """到达上下边界且目标不存在时不能无限滚轮。"""
    env = MockEnvironment()
    monkeypatch.setattr(env, "capture_screen", lambda: Image.new("RGB", (1136, 640)))
    scrolls: list[int] = []
    monkeypatch.setattr(env, "wheel", lambda x, y, delta: scrolls.append(delta))
    switcher = LineupSwitcher(env)
    switcher._guard = RunGuard()
    monkeypatch.setattr(switcher, "_panel", lambda _: True)
    monkeypatch.setattr(switcher, "_labels", lambda *_: [(1000, 100, "默认分组", 0.99)])
    monkeypatch.setattr("yys.common.lineup.time.sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="未找到分组"):
        switcher._find_name("groups", "不存在", 10)
    assert scrolls == [120, 120, -120, -120]


def test_wheel_observe_mode_and_action_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """滚轮复用观察模式和预算，不触发真实输入且不影响已有动作语义。"""
    env = MockEnvironment()
    called: list[tuple[int, int, int]] = []
    monkeypatch.setattr(env, "wheel", lambda *args: called.append(args))
    observed = GuardedEnvironment(env, RunGuard(max_actions=1), observe_only=True)
    observed.wheel(100, 200, -120)
    observed.wheel(100, 200, 120)
    assert called == []
    assert observed.action_records[0].extra == {"wheel_delta": -120}
    assert observed.guard.stop_reason is RunStopReason.ACTION_LIMIT
    executing = GuardedEnvironment(env, RunGuard(max_actions=1), observe_only=False)
    executing.wheel(100, 200, 120)
    assert called == [(100, 200, 120)]


def test_windows_wheel_translates_client_position_without_moving_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows 只接收目标窗口消息；负屏幕坐标及向下滚动保留有符号位。"""
    from win_util.environment import windows as native

    messages: list[tuple[int, int, int, int]] = []
    monkeypatch.setattr(native.win32gui, "GetClientRect", lambda _: (0, 0, 1136, 640))
    monkeypatch.setattr(native.win32gui, "ClientToScreen", lambda _, p: (p[0] - 1500, p[1] - 400))
    monkeypatch.setattr(native.win32api, "SendMessage", lambda *args: messages.append(args))
    monkeypatch.setattr(native.win32api, "SetCursorPos", lambda _: pytest.fail("不应移动桌面鼠标"))
    env = WindowsEnvironment(hwnd=123)
    env.wheel(100, 200, -120)
    assert messages == [(123, native.win32con.WM_MOUSEWHEEL,
                         native.win32api.MAKELONG(0, (-120) & 0xFFFF),
                         native.win32api.MAKELONG((-1400) & 0xFFFF, (-200) & 0xFFFF))]
    with pytest.raises(ValueError):
        env.wheel(-1, 20, 120)
    assert len(messages) == 1


def test_legacy_environment_still_constructs_and_explicitly_rejects_wheel() -> None:
    """新增能力不能让没有 wheel 实现的旧环境变成抽象类。"""
    with pytest.raises(NotImplementedError, match="不支持"):
        MockEnvironment().wheel(1, 2, 120)


def test_applied_without_success_never_retries_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    """确认后只回到预设页不代表成功；异常不能再点一次应用。"""
    env = _replay("preset_target")
    env._fixture.transitions[-1] = replace(
        env._fixture.transitions[-1], to_scene="preset_target",
    )
    now = [0.0]

    def clock() -> float:
        now[0] += 0.25
        return now[0]

    monkeypatch.setattr("yys.common.lineup.time.monotonic", clock)
    monkeypatch.setattr("yys.common.lineup.time.sleep", lambda _: None)
    guarded = GuardedEnvironment(env, RunGuard(timeout_seconds=1000), observe_only=False)
    with pytest.raises(RuntimeError, match="结果不确定"):
        LineupSwitcher(guarded).switch("寮活动", "通用", timeout_seconds=1000)
    assert len(guarded.action_records) == 2


def test_caller_cancellation_prevents_input() -> None:
    """调用方停止时必须先退出，不能继续截图后点击。"""
    env = GuardedEnvironment(_replay(), RunGuard(), observe_only=False)

    def cancelled() -> None:
        raise RuntimeError("调用脚本已停止")

    with pytest.raises(RuntimeError, match="调用脚本已停止"):
        LineupSwitcher(env, checkpoint=cancelled).switch("寮活动", "通用")
    assert env.action_records == []


def test_base_script_reuses_injected_environment_and_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    """基础脚本仅在显式调用时执行，并复用已有环境、OCR、暂停与停止入口。"""
    from threading import Event
    from types import SimpleNamespace
    from yys.common.event_script_base import YYSBaseScript

    env = MockEnvironment()
    ocr = CommonOcr()
    calls: list[object] = []

    class Service:
        """只观测公共集成边界，不触发实际游戏。"""

        def __init__(self, actual_env: object, *, ocr: object, checkpoint: Callable[[], None]) -> None:
            calls.append((actual_env, ocr))
            self.checkpoint = checkpoint

        def switch(self, group_name: str, lineup_name: str, **kwargs: object) -> None:
            self.checkpoint()
            calls.append((group_name, lineup_name, kwargs))

    monkeypatch.setattr("yys.common.lineup.LineupSwitcher", Service)
    script = SimpleNamespace(_env=env, _run_guard=None, _stop_threading_event=Event(),
                             win_controller=SimpleNamespace(ocr=ocr), pause_point=lambda: calls.append("pause"))
    YYSBaseScript.switch_lineup(script, "寮活动", "通用")
    assert calls == [
        "pause",
        (env, ocr),
        "pause",
        (
            "寮活动",
            "通用",
            {
                "timeout_seconds": 60.0,
                "max_scrolls": 30,
                "home_verified": False,
            },
        ),
    ]
    script._stop_threading_event.set()
    with pytest.raises(RuntimeError, match="脚本已停止"):
        YYSBaseScript.switch_lineup(script, "寮活动", "通用")
