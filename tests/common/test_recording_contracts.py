"""伴随录制数据合约测试。"""

import json
from pathlib import Path

import pytest

from yys.common.recording.contracts import (
    RECORDING_SCHEMA_VERSION,
    RecordingEvent,
    load_events,
    write_events,
)


def _mouse_event(seq: int, elapsed_ms: int) -> RecordingEvent:
    """创建合法鼠标事件。"""
    return RecordingEvent(
        schema_version=RECORDING_SCHEMA_VERSION,
        seq=seq,
        elapsed_ms=elapsed_ms,
        kind="mouse",
        action="left_click",
        client_x=100,
        client_y=200,
        normalized_x=0.1,
        normalized_y=0.2,
        button="left",
    )


def test_recording_events_round_trip(tmp_path: Path) -> None:
    """JSONL 往返后应保留顺序和字段。"""
    path = tmp_path / "events.jsonl"
    write_events(path, [_mouse_event(1, 10), _mouse_event(2, 20)])

    events = load_events(path, client_size=(1154, 680))

    assert [event.seq for event in events] == [1, 2]
    assert events[0].client_x == 100


def test_recording_event_rejects_unknown_version() -> None:
    """读取器必须拒绝未知版本。"""
    payload = _mouse_event(1, 10).to_dict()
    payload["schema_version"] = 999

    with pytest.raises(ValueError, match="不支持"):
        RecordingEvent.from_dict(payload)


def test_recording_event_rejects_desktop_coordinates() -> None:
    """客户区外坐标不能进入持久化录制。"""
    event = _mouse_event(1, 10)

    with pytest.raises(ValueError, match="超出录制窗口"):
        event.validate((50, 50))


def test_load_events_rejects_sequence_gap(tmp_path: Path) -> None:
    """JSONL 事件序号必须连续。"""
    path = tmp_path / "events.jsonl"
    write_events(path, [_mouse_event(1, 10), _mouse_event(3, 20)])

    with pytest.raises(ValueError, match="seq 不连续"):
        load_events(path)


def test_recording_event_rejects_unknown_field() -> None:
    """消费者不能私自扩展未版本化字段。"""
    payload = _mouse_event(1, 10).to_dict()
    payload["screen_x"] = 999

    with pytest.raises(ValueError, match="未知字段"):
        RecordingEvent.from_dict(json.loads(json.dumps(payload)))
