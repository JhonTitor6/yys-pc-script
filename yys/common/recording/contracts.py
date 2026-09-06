"""伴随录制文件的版本化数据合约。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Optional

RECORDING_SCHEMA_VERSION = 2
RecordingEventKind = Literal["mouse", "keyboard"]

_MOUSE_ACTIONS = {"left_click", "right_click", "left_double_click", "drag", "wheel"}
_KEYBOARD_ACTIONS = {"key_press", "key_down", "key_up"}


@dataclass(frozen=True)
class RecordingEvent:
    """一条已经转换为客户区坐标的录制事件。"""

    schema_version: int
    seq: int
    elapsed_ms: int
    kind: RecordingEventKind
    action: str
    client_x: Optional[int] = None
    client_y: Optional[int] = None
    normalized_x: Optional[float] = None
    normalized_y: Optional[float] = None
    end_client_x: Optional[int] = None
    end_client_y: Optional[int] = None
    button: Optional[str] = None
    key: Optional[str] = None
    wheel_delta: Optional[int] = None

    def validate(self, client_size: Optional[tuple[int, int]] = None) -> None:
        """校验版本、顺序字段和种类特有字段。"""
        if self.schema_version not in (1, RECORDING_SCHEMA_VERSION):
            raise ValueError(f"不支持的录制事件版本: {self.schema_version}")
        if self.action == "wheel":
            if self.schema_version < 2 or self.kind != "mouse":
                raise ValueError("滚轮事件必须使用 v2 鼠标事件")
            if type(self.wheel_delta) is not int or not -32768 <= self.wheel_delta <= 32767 or self.wheel_delta == 0:
                raise ValueError("wheel_delta 必须是非零有符号 16 位整数")
        elif self.wheel_delta is not None:
            raise ValueError("wheel_delta 只能用于滚轮事件")
        if self.seq < 1:
            raise ValueError("事件 seq 必须从 1 开始")
        if self.elapsed_ms < 0:
            raise ValueError("事件 elapsed_ms 不能为负数")
        if self.kind == "mouse":
            self._validate_mouse(client_size)
            return
        if self.kind == "keyboard":
            if self.action not in _KEYBOARD_ACTIONS or not self.key:
                raise ValueError("键盘事件缺少合法 action 或 key")
            return
        raise ValueError(f"未知录制事件种类: {self.kind}")

    def _validate_mouse(self, client_size: Optional[tuple[int, int]]) -> None:
        if self.action not in _MOUSE_ACTIONS:
            raise ValueError(f"未知鼠标动作: {self.action}")
        if self.client_x is None or self.client_y is None:
            raise ValueError("鼠标事件缺少客户区坐标")
        if self.normalized_x is None or self.normalized_y is None:
            raise ValueError("鼠标事件缺少归一化坐标")
        if not 0.0 <= self.normalized_x <= 1.0:
            raise ValueError("normalized_x 超出 [0, 1]")
        if not 0.0 <= self.normalized_y <= 1.0:
            raise ValueError("normalized_y 超出 [0, 1]")
        if self.action == "drag":
            if self.end_client_x is None or self.end_client_y is None:
                raise ValueError("拖拽事件缺少终点坐标")
        if client_size is not None:
            width, height = client_size
            if not 0 <= self.client_x < width or not 0 <= self.client_y < height:
                raise ValueError("鼠标客户区坐标超出录制窗口")
            if self.end_client_x is not None and not 0 <= self.end_client_x < width:
                raise ValueError("拖拽终点 X 超出录制窗口")
            if self.end_client_y is not None and not 0 <= self.end_client_y < height:
                raise ValueError("拖拽终点 Y 超出录制窗口")

    def to_dict(self) -> dict[str, Any]:
        """转换为可写入 JSONL 的字典。"""
        self.validate()
        return {key: value for key, value in asdict(self).items() if value is not None}

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        client_size: Optional[tuple[int, int]] = None,
    ) -> "RecordingEvent":
        """从未知 JSON 映射解码并严格校验。"""
        allowed = set(cls.__dataclass_fields__)
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"录制事件包含未知字段: {sorted(unknown)}")
        try:
            event = cls(**dict(data))
        except TypeError as exc:
            raise ValueError(f"录制事件字段不完整: {exc}") from exc
        event.validate(client_size)
        return event


@dataclass
class RecordingMetadata:
    """一次录制的可持久化元数据。"""

    schema_version: int
    recording_id: str
    scenario: str
    started_at: str
    ended_at: Optional[str]
    duration_ms: int
    window_title: str
    client_width: int
    client_height: int
    fps: float
    codec: str
    event_count: int
    dropped_frame_count: int
    status: str
    stop_reason: Optional[str]

    def validate(self) -> None:
        """校验元数据的稳定字段。"""
        if self.schema_version not in (1, RECORDING_SCHEMA_VERSION):
            raise ValueError(f"不支持的录制元数据版本: {self.schema_version}")
        if self.client_width <= 0 or self.client_height <= 0:
            raise ValueError("录制客户区尺寸必须为正数")
        if self.fps <= 0:
            raise ValueError("录制帧率必须为正数")
        if self.event_count < 0 or self.dropped_frame_count < 0:
            raise ValueError("录制计数不能为负数")

    def to_dict(self) -> dict[str, Any]:
        """转换为 JSON 字典。"""
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RecordingMetadata":
        """从 JSON 映射解码元数据。"""
        try:
            metadata = cls(**dict(data))
        except TypeError as exc:
            raise ValueError(f"录制元数据字段不完整: {exc}") from exc
        metadata.validate()
        return metadata


def dump_event(event: RecordingEvent) -> str:
    """将单条事件编码为一行紧凑 JSON。"""
    return json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))


def load_events(
    path: Path,
    client_size: Optional[tuple[int, int]] = None,
) -> list[RecordingEvent]:
    """读取 JSONL，并校验序号和时间严格单调。"""
    events: list[RecordingEvent] = []
    previous_seq = 0
    previous_elapsed = -1
    with path.open("r", encoding="utf-8") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"events.jsonl 第 {line_number} 行不是合法 JSON") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"events.jsonl 第 {line_number} 行必须是对象")
            event = RecordingEvent.from_dict(payload, client_size)
            if event.seq != previous_seq + 1:
                raise ValueError(f"事件 seq 不连续: {previous_seq} → {event.seq}")
            if event.elapsed_ms < previous_elapsed:
                raise ValueError("事件 elapsed_ms 出现倒退")
            events.append(event)
            previous_seq = event.seq
            previous_elapsed = event.elapsed_ms
    return events


def save_metadata(path: Path, metadata: RecordingMetadata) -> None:
    """以 UTF-8 JSON 写入元数据。"""
    path.write_text(
        json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_metadata(path: Path) -> RecordingMetadata:
    """读取并校验元数据。"""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("metadata.json 顶层必须是对象")
    return RecordingMetadata.from_dict(payload)


def write_events(path: Path, events: Iterable[RecordingEvent]) -> None:
    """写入一组完整事件，主要用于测试和转换工具。"""
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for event in events:
            stream.write(f"{dump_event(event)}\n")
