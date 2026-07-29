"""伴随录制会话测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pytest
from PIL import Image

import yys.common.recording.session as session_module
from win_util.environment.base import GameEnvironment
from yys.common.recording.contracts import load_events, load_metadata
from yys.common.recording.session import RecordingSession


class StaticEnvironment(GameEnvironment):
    """返回固定客户区画面的测试环境。"""

    def __init__(self, size: tuple[int, int] = (320, 180)) -> None:
        self.size = size

    def capture_screen(self) -> Image.Image:
        image = Image.new("RGB", self.size, color=(20, 30, 40))
        image.paste((220, 210, 200), (0, 0, 16, 16))
        return image

    def left_click(self, x: int, y: int) -> None:
        pass

    def right_click(self, x: int, y: int) -> None:
        pass

    def left_double_click(self, x: int, y: int) -> None:
        pass

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        pass

    def key_press(self, key_code: int) -> None:
        pass

    def key_down(self, key_code: int) -> None:
        pass

    def key_up(self, key_code: int) -> None:
        pass

    def set_mouse_position(self, x: int, y: int) -> None:
        pass

    def get_window_client_rect(self) -> Tuple[int, int, int, int]:
        return (0, 0, self.size[0], self.size[1])

    def find_window(self, title_part: str) -> Optional[int]:
        return 12345


class FakeVideoWriter:
    """不依赖真实编码器的测试写入器。"""

    def __init__(self, path: Path, opened: bool = True) -> None:
        self.path = path
        self.opened = opened
        self.frames: list[np.ndarray] = []
        self.released = False
        path.write_bytes(b"fake-video")

    def isOpened(self) -> bool:
        return self.opened

    def write(self, frame: np.ndarray) -> None:
        self.frames.append(frame.copy())

    def release(self) -> None:
        self.released = True


class ImmediateStopMonitor:
    """启动后写入一次点击并立即停止。"""

    def __init__(self, session: RecordingSession) -> None:
        self.session = session
        self.stopped = False

    def start(self) -> None:
        self.session.record_mouse("left_click", 100, 80, button="left")
        self.session.request_stop("test_stop")

    def stop(self) -> None:
        self.stopped = True


def test_client_size_change_stops_capture() -> None:
    """录制期间客户区尺寸变化时必须拒绝继续写入异尺寸帧。"""
    environment = StaticEnvironment(size=(320, 180))
    session = RecordingSession(
        env=environment,
        scenario="realm_raid",
    )
    session._client_size = environment.size
    environment.size = (321, 180)

    with pytest.raises(RuntimeError, match="录制期间客户区尺寸变化"):
        session._capture_frame()


def test_windows_video_writer_prefers_msmf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows 录制应避开可能损坏的默认 GStreamer 后端。"""
    calls: list[tuple[object, ...]] = []

    def create_writer(*args: object) -> FakeVideoWriter:
        calls.append(args)
        return FakeVideoWriter(Path(str(args[0])))

    monkeypatch.setattr(session_module.os, "name", "nt")
    monkeypatch.setattr(session_module.cv2, "VideoWriter_fourcc", lambda *_args: 1234)
    monkeypatch.setattr(session_module.cv2, "VideoWriter", create_writer)

    path = tmp_path / "recording.mp4"
    writer = RecordingSession._create_video_writer(path, "mp4v", 8.0, (320, 180))

    assert writer.isOpened()
    assert calls == [
        (str(path), session_module.cv2.CAP_MSMF, 1234, 8.0, (320, 180))
    ]


def test_windows_video_writer_falls_back_when_msmf_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MSMF 不可用时应释放失败写入器并回退到 OpenCV 默认选择。"""
    writers: list[FakeVideoWriter] = []
    calls: list[tuple[object, ...]] = []

    def create_writer(*args: object) -> FakeVideoWriter:
        calls.append(args)
        writer = FakeVideoWriter(
            Path(str(args[0])),
            opened=len(calls) > 1,
        )
        writers.append(writer)
        return writer

    monkeypatch.setattr(session_module.os, "name", "nt")
    monkeypatch.setattr(session_module.cv2, "VideoWriter_fourcc", lambda *_args: 1234)
    monkeypatch.setattr(session_module.cv2, "VideoWriter", create_writer)

    path = tmp_path / "recording.mp4"
    writer = RecordingSession._create_video_writer(path, "mp4v", 8.0, (320, 180))

    assert writer.isOpened()
    assert writers[0].released is True
    assert calls == [
        (str(path), session_module.cv2.CAP_MSMF, 1234, 8.0, (320, 180)),
        (str(path), 1234, 8.0, (320, 180)),
    ]


def test_recording_session_finalizes_atomic_directory(tmp_path: Path) -> None:
    """正常停止后应生成可校验的最终目录。"""
    writers: list[FakeVideoWriter] = []

    def create_writer(
        path: Path,
        codec: str,
        fps: float,
        size: tuple[int, int],
    ) -> FakeVideoWriter:
        assert codec == "mp4v"
        assert fps == 8.0
        assert size == (320, 180)
        writer = FakeVideoWriter(path)
        writers.append(writer)
        return writer

    session = RecordingSession(
        env=StaticEnvironment(),
        scenario="realm_raid",
        output_root=tmp_path,
        recording_id="test-recording",
        video_writer_factory=create_writer,
    )
    monitor = ImmediateStopMonitor(session)

    output_dir = session.run(monitor)

    assert output_dir == tmp_path / "realm_raid" / "test-recording"
    assert not (tmp_path / "realm_raid" / "test-recording.partial").exists()
    metadata = load_metadata(output_dir / "metadata.json")
    events = load_events(
        output_dir / "events.jsonl",
        (metadata.client_width, metadata.client_height),
    )
    assert metadata.status == "completed"
    assert metadata.stop_reason == "test_stop"
    assert metadata.event_count == 1
    assert events[0].client_x == 100
    assert (output_dir / "frames" / "000001-before.png").exists()
    assert (output_dir / "frames" / "000001-after.png").exists()
    assert writers[0].released
    assert monitor.stopped


def test_recording_session_preserves_partial_directory_on_codec_error(
    tmp_path: Path,
) -> None:
    """编码器不可用时保留失败元数据，不伪装成完成录制。"""

    def create_closed_writer(
        path: Path,
        codec: str,
        fps: float,
        size: tuple[int, int],
    ) -> FakeVideoWriter:
        return FakeVideoWriter(path, opened=False)

    session = RecordingSession(
        env=StaticEnvironment(),
        scenario="realm_raid",
        output_root=tmp_path,
        recording_id="failed-recording",
        video_writer_factory=create_closed_writer,
    )
    monitor = ImmediateStopMonitor(session)

    with pytest.raises(RuntimeError, match="无法打开视频编码器"):
        session.run(monitor)

    partial = tmp_path / "realm_raid" / "failed-recording.partial"
    metadata = load_metadata(partial / "metadata.json")
    assert metadata.status == "failed"
    assert metadata.stop_reason is not None
    assert metadata.stop_reason.startswith("error:RuntimeError")


def test_recording_session_rejects_uniform_first_frame(tmp_path: Path) -> None:
    """纯色首帧应立即失败，避免用户完成一整段无效录制。"""
    writer_created = False

    def create_writer(
        path: Path,
        codec: str,
        fps: float,
        size: tuple[int, int],
    ) -> FakeVideoWriter:
        nonlocal writer_created
        writer_created = True
        return FakeVideoWriter(path)

    environment = StaticEnvironment()
    environment.capture_screen = lambda: Image.new(
        "RGB",
        environment.size,
        color="white",
    )
    session = RecordingSession(
        env=environment,
        scenario="realm_raid",
        output_root=tmp_path,
        recording_id="uniform-recording",
        video_writer_factory=create_writer,
    )

    with pytest.raises(RuntimeError, match="录制首帧近似纯色"):
        session.run(ImmediateStopMonitor(session))

    partial = tmp_path / "realm_raid" / "uniform-recording.partial"
    metadata = load_metadata(partial / "metadata.json")
    assert writer_created is False
    assert metadata.status == "failed"
    assert metadata.stop_reason is not None
    assert metadata.stop_reason.startswith("error:RuntimeError")


def test_recording_session_counts_missed_frame_deadlines(tmp_path: Path) -> None:
    """编码写入落后时应跳过过期计划帧并累计掉帧数。"""
    now = [0.0]
    session = RecordingSession(
        env=StaticEnvironment(),
        scenario="realm_raid",
        output_root=tmp_path,
        monotonic=lambda: now[0],
    )
    now[0] = 0.55

    next_frame_at = session._skip_missed_frame_deadlines(0.2, 0.1)

    assert next_frame_at == pytest.approx(0.6)
    assert session.dropped_frame_count == 4


def test_keyboard_interrupt_drains_queued_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """人工中断时应先停监听器，再排空已经进入队列的输入事件。"""
    session = RecordingSession(
        env=StaticEnvironment(),
        scenario="realm_raid",
        output_root=tmp_path,
        recording_id="interrupted-recording",
        video_writer_factory=lambda path, _codec, _fps, _size: FakeVideoWriter(path),
    )
    monitor = ImmediateStopMonitor(session)

    def interrupt_capture(*_args: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(session, "_capture_loop", interrupt_capture)

    output_dir = session.run(monitor)
    metadata = load_metadata(output_dir / "metadata.json")
    events = load_events(
        output_dir / "events.jsonl",
        (metadata.client_width, metadata.client_height),
    )

    assert monitor.stopped is True
    assert metadata.status == "completed"
    assert metadata.stop_reason == "test_stop"
    assert len(events) == 1
