"""产品契约：docs/plans/2026-09-06-lineup-wheel-recording-plan.md。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

import cv2
import pytest
from PIL import Image

from tests.common.environment.mock_environment import MockEnvironment
from tests.common.environment.scene_replay_environment import SceneReplayEnvironment
from win_util.environment.guarded import GuardedEnvironment, RunGuard, RunStopReason
from win_util.environment.windows import WindowsEnvironment
from win_util.ocr import CommonOcr
from yys.common.lineup import LineupSwitcher

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/lineup_switch"


def _replay(initial: str = "home") -> SceneReplayEnvironment:
    return SceneReplayEnvironment(str(_FIXTURES), str(_FIXTURES / "fixture.json"), initial)


def test_recorded_switch_uses_real_ocr_and_same_five_actions() -> None:
    """真实录制证明的五步流程：准确选寮活动/通用，确认一次并见到成功。"""
    env = _replay()
    guarded = GuardedEnvironment(env, RunGuard(max_actions=5), observe_only=False)
    LineupSwitcher(guarded).switch("寮活动", "通用")
    assert [record.action_type for record in guarded.action_records] == ["left_click"] * 5
    assert env._current_scene == "success"


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
    assert calls == ["pause", (env, ocr), "pause", ("寮活动", "通用", {"timeout_seconds": 60.0, "max_scrolls": 30})]
    script._stop_threading_event.set()
    with pytest.raises(RuntimeError, match="脚本已停止"):
        YYSBaseScript.switch_lineup(script, "寮活动", "通用")
