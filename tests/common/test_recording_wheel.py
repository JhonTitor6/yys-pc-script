"""产品契约：docs/plans/2026-09-06-lineup-wheel-recording-plan.md。"""

from __future__ import annotations

import ctypes
import json
from dataclasses import replace
from pathlib import Path

import pytest

from tests.common.test_recording_session import FakeVideoWriter, StaticEnvironment
from yys.common.recording import win32_input
from yys.common.recording.contracts import RecordingEvent, load_events, load_metadata
from yys.common.recording.fixture_builder import build_candidates, build_confirmed_fixture
from yys.common.recording.session import RecordingSession


@pytest.mark.parametrize("delta", [120, -120, 30, -240])
def test_wheel_persists_direction_position_frames_and_candidates(tmp_path: Path, delta: int) -> None:
    """真人滚轮必须完整进入录制和 AI 候选材料，不能丢失方向和细小增量。"""
    session = RecordingSession(
        env=StaticEnvironment(), scenario="lineup_switch", output_root=tmp_path,
        video_writer_factory=lambda path, *_args: FakeVideoWriter(path),
    )

    class Monitor:
        """产生一个滚轮事件后结束录制。"""

        def start(self) -> None:
            session.record_wheel(100, 80, delta)
            session.request_stop()

        def stop(self) -> None:
            pass

    output = session.run(Monitor())
    event = load_events(output / "events.jsonl", (320, 180))[0]
    assert (event.action, event.wheel_delta, event.client_x, event.client_y) == ("wheel", delta, 100, 80)
    assert (event.normalized_x, event.normalized_y) == (100 / 319, 80 / 179)
    assert load_metadata(output / "metadata.json").status == "completed"
    assert (output / "frames/000001-before.png").is_file()
    assert (output / "frames/000001-after.png").is_file()
    candidates = build_candidates(output, output / "candidates.json")
    assert json.loads(candidates.read_text(encoding="utf-8"))["candidates"][0]["wheel_delta"] == delta

    confirmation = output / "confirmation.json"
    confirmation.write_text(json.dumps({"initial_scene": "start", "transitions": [{"action": "wheel"}]}))
    with pytest.raises(ValueError, match="尚不支持滚轮"):
        build_confirmed_fixture(output, confirmation, tmp_path / "fixture")
    assert not (tmp_path / "fixture").exists()
    confirmation.write_text(json.dumps({"initial_scene": "start", "transitions": [{"event_seq": "1"}]}))
    with pytest.raises(ValueError, match="尚不支持滚轮"):
        build_confirmed_fixture(output, confirmation, tmp_path / "fixture")


@pytest.mark.parametrize("delta", [None, 0, True, 1.5, "120", 32768, -32769])
def test_invalid_wheel_delta_is_rejected(delta: object) -> None:
    """输入边界不得接受缺失、非整数或溢出的滚轮增量。"""
    payload = dict(schema_version=2, seq=1, elapsed_ms=0, kind="mouse", action="wheel",
                   client_x=1, client_y=2, normalized_x=0.1, normalized_y=0.2, wheel_delta=delta)
    with pytest.raises(ValueError, match="wheel_delta"):
        RecordingEvent.from_dict(payload)


def test_v1_click_remains_readable_but_cannot_claim_wheel_support() -> None:
    """旧记录保持原义，不能用 v1 偷渡 v2 滚轮字段。"""
    event = RecordingEvent(1, 1, 0, "mouse", "left_click", 10, 20, 0.1, 0.2)
    assert RecordingEvent.from_dict(event.to_dict()) == event
    with pytest.raises(ValueError, match="v2"):
        replace(event, action="wheel", wheel_delta=120).validate()


@pytest.mark.parametrize("delta,foreground,target,point,flags,expected", [
    (120, 123, 123, (110, 220), 0, [(10, 20, 120)]),
    (-120, 123, 123, (110, 220), 0, [(10, 20, -120)]),
    (30, 123, 123, (110, 220), 0, [(10, 20, 30)]),
    (120, 999, 123, (110, 220), 0, []),
    (120, 123, 999, (110, 220), 0, []),
    (120, 123, 123, (90, 220), 0, []),
    (120, 123, 123, (110, 220), 1, []),
])
def test_native_wheel_is_filtered_and_uses_event_position(
    monkeypatch: pytest.MonkeyPatch, delta: int, foreground: int, target: int,
    point: tuple[int, int], flags: int, expected: list[tuple[int, int, int]],
) -> None:
    """只记录实际落在前台游戏客户区的人工滚轮，以事件坐标确定列表。"""
    events: list[tuple[int, int, int]] = []
    monitor = win32_input.WindowsInputMonitor(123, lambda *_: None, lambda *_: None,
                                              lambda _: None, on_wheel=lambda *args: events.append(args))
    monkeypatch.setattr(win32_input.win32gui, "GetForegroundWindow", lambda: foreground)
    monkeypatch.setattr(win32_input.win32gui, "WindowFromPoint", lambda _: target)
    monkeypatch.setattr(win32_input.win32gui, "IsChild", lambda *_: False)
    monkeypatch.setattr(win32_input.win32gui, "ScreenToClient", lambda _, p: (p[0] - 100, p[1] - 200))
    monkeypatch.setattr(win32_input.win32gui, "GetClientRect", lambda _: (0, 0, 320, 180))
    data = win32_input._MouseHookData()
    data.pt.x, data.pt.y = point
    data.mouseData = (delta & 0xFFFF) << 16
    data.flags = flags
    monitor._handle_wheel(data)
    assert events == expected


def test_hook_start_failure_fails_recording(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """原生监听失败必须留下 failed 元数据，不能生成虚假的完整录制。"""
    monkeypatch.setattr(win32_input._user32, "SetWindowsHookExW", lambda *_: 0)
    session = RecordingSession(env=StaticEnvironment(), scenario="lineup_switch", output_root=tmp_path,
                               video_writer_factory=lambda path, *_args: FakeVideoWriter(path))
    monitor = win32_input.WindowsInputMonitor(123, session.record_mouse, session.record_keyboard,
                                              session.request_stop, on_wheel=session.record_wheel)
    with pytest.raises(RuntimeError, match="输入监听器失败"):
        session.run(monitor)
    output = next((tmp_path / "lineup_switch").iterdir())
    assert output.name.endswith(".partial")
    assert load_metadata(output / "metadata.json").status == "failed"


def test_hook_forwards_native_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    """监听不能吞掉输入；负数钩子码不得解引用消息数据。"""
    monitor = win32_input.WindowsInputMonitor(123, lambda *_: None, lambda *_: None, lambda _: None)
    forwarded: list[tuple[object, ...]] = []
    observed: list[int] = []

    def forward(*args: object) -> int:
        forwarded.append(args)
        return 77

    monkeypatch.setattr(win32_input._user32, "CallNextHookEx", forward)
    monkeypatch.setattr(monitor, "_handle_wheel", lambda data: observed.append(data.mouseData))
    data = win32_input._MouseHookData()
    data.mouseData = 120 << 16
    assert monitor._wheel_hook(0, win32_input.win32con.WM_MOUSEWHEEL, ctypes.addressof(data)) == 77
    assert monitor._wheel_hook(-1, win32_input.win32con.WM_MOUSEWHEEL, 0) == 77
    assert observed == [120 << 16]
    assert len(forwarded) == 2


def test_poll_failure_unhooks_before_reporting_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """监听运行异常后必须卸载钩子并向调用者报告失败。"""
    unhooked: list[int] = []
    monitor = win32_input.WindowsInputMonitor(123, lambda *_: None, lambda *_: None,
                                              lambda _: None, on_wheel=lambda *_: None)
    monkeypatch.setattr(win32_input._user32, "SetWindowsHookExW", lambda *_: 77)
    monkeypatch.setattr(win32_input._user32, "UnhookWindowsHookEx", lambda handle: unhooked.append(handle) or 1)

    def fail() -> None:
        raise RuntimeError("模拟消息循环失败")

    monkeypatch.setattr(monitor, "_poll_inputs", fail)
    with pytest.raises(RuntimeError, match="输入监听器失败"):
        monitor.start()
        monitor.stop()
    assert unhooked == [77]
