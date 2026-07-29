"""伴随录制会话。"""

from __future__ import annotations

import os
import queue
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Protocol, TextIO

import cv2
import numpy as np

from win_util.environment.base import GameEnvironment

from .contracts import (
    RECORDING_SCHEMA_VERSION,
    RecordingEvent,
    RecordingEventKind,
    RecordingMetadata,
    dump_event,
    save_metadata,
)

_SCENARIO_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class InputMonitor(Protocol):
    """录制会话依赖的最小输入监听接口。"""

    def start(self) -> None:
        """开始监听。"""

    def stop(self) -> None:
        """停止监听。"""


class VideoWriter(Protocol):
    """OpenCV VideoWriter 的最小可测试接口。"""

    def isOpened(self) -> bool:
        """返回编码器是否已经打开。"""

    def write(self, frame: np.ndarray) -> None:
        """写入一帧。"""

    def release(self) -> None:
        """关闭编码器。"""


VideoWriterFactory = Callable[[Path, str, float, tuple[int, int]], VideoWriter]


@dataclass(frozen=True)
class _QueuedEvent:
    event: RecordingEvent
    before_frame: Optional[np.ndarray]


class RecordingSession:
    """把客户区画面和输入事件写入一个原子录制目录。"""

    def __init__(
        self,
        env: GameEnvironment,
        scenario: str,
        output_root: Path = Path("recordings"),
        window_title: str = "阴阳师",
        fps: float = 8.0,
        codec: str = "mp4v",
        recording_id: Optional[str] = None,
        video_writer_factory: Optional[VideoWriterFactory] = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """创建尚未开始的录制会话。"""
        if not _SCENARIO_PATTERN.fullmatch(scenario):
            raise ValueError("scenario 只能包含字母、数字、下划线和连字符")
        if fps <= 0:
            raise ValueError("fps 必须为正数")
        self._env = env
        self._scenario = scenario
        self._output_root = output_root
        self._window_title = window_title
        self._fps = fps
        self._codec = codec
        self._recording_id = recording_id or self._new_recording_id()
        self._writer_factory = video_writer_factory or self._create_video_writer
        self._monotonic = monotonic
        self._stop_event = threading.Event()
        self._event_queue: queue.SimpleQueue[_QueuedEvent] = queue.SimpleQueue()
        self._event_lock = threading.Lock()
        self._frame_lock = threading.Lock()
        self._last_frame: Optional[np.ndarray] = None
        self._start_monotonic = 0.0
        self._started_at = ""
        self._seq = 0
        self._event_count = 0
        self._dropped_frames = 0
        self._stop_reason: Optional[str] = None
        self._client_size = (0, 0)

    @property
    def recording_id(self) -> str:
        """返回本次录制的稳定标识。"""
        return self._recording_id

    @property
    def dropped_frame_count(self) -> int:
        """返回因写入落后而跳过的计划帧数。"""
        return self._dropped_frames

    def request_stop(self, reason: str = "user_stop") -> None:
        """请求录制循环安全停止。"""
        if self._stop_reason is None:
            self._stop_reason = reason
        self._stop_event.set()

    def record_mouse(
        self,
        action: str,
        x: int,
        y: int,
        end_x: Optional[int] = None,
        end_y: Optional[int] = None,
        button: str = "left",
    ) -> None:
        """将一个客户区鼠标动作放入无损事件队列。"""
        width, height = self._client_size
        if width <= 0 or height <= 0:
            return
        event = self._new_event(
            kind="mouse",
            action=action,
            client_x=x,
            client_y=y,
            normalized_x=x / max(width - 1, 1),
            normalized_y=y / max(height - 1, 1),
            end_client_x=end_x,
            end_client_y=end_y,
            button=button,
        )
        event.validate(self._client_size)
        self._enqueue_event(event)

    def record_keyboard(self, action: str, key: str) -> None:
        """将一个目标窗口键盘动作放入无损事件队列。"""
        if self._client_size == (0, 0):
            return
        event = self._new_event(kind="keyboard", action=action, key=key)
        event.validate(self._client_size)
        self._enqueue_event(event)

    def run(self, input_monitor: InputMonitor) -> Path:
        """开始录制并阻塞到停止，返回最终目录。"""
        partial_dir, final_dir = self._prepare_directories()
        events_path = partial_dir / "events.jsonl"
        frames_dir = partial_dir / "frames"
        frames_dir.mkdir()
        writer: Optional[VideoWriter] = None
        monitor_started = False
        status = "failed"
        try:
            first_frame = self._capture_frame()
            self._validate_first_frame(first_frame)
            height, width = first_frame.shape[:2]
            self._client_size = (width, height)
            writer = self._writer_factory(
                partial_dir / "recording.mp4",
                self._codec,
                self._fps,
                self._client_size,
            )
            if not writer.isOpened():
                raise RuntimeError(f"无法打开视频编码器: {self._codec}")
            self._start_monotonic = self._monotonic()
            self._started_at = self._now_iso()
            self._store_last_frame(first_frame)
            writer.write(first_frame)
            self._write_metadata(partial_dir, "recording", None)
            with events_path.open("w", encoding="utf-8", newline="\n") as stream:
                input_monitor.start()
                monitor_started = True
                try:
                    self._capture_loop(writer, stream, frames_dir)
                except KeyboardInterrupt:
                    self.request_stop("user_interrupt")
                finally:
                    try:
                        if monitor_started:
                            monitor_started = False
                            input_monitor.stop()
                    finally:
                        self._drain_events(
                            stream,
                            frames_dir,
                            self._last_frame_copy(),
                        )
            status = "completed"
        except Exception as exc:
            self._stop_reason = f"error:{type(exc).__name__}:{exc}"
            raise
        finally:
            if monitor_started:
                input_monitor.stop()
            if writer is not None:
                writer.release()
            self._write_metadata(partial_dir, status, self._stop_reason)
        if final_dir.exists():
            raise FileExistsError(f"录制目标目录已经存在: {final_dir}")
        partial_dir.rename(final_dir)
        return final_dir

    def _capture_loop(
        self,
        writer: VideoWriter,
        stream: TextIO,
        frames_dir: Path,
    ) -> None:
        interval = 1.0 / self._fps
        next_frame_at = self._monotonic() + interval
        while not self._stop_event.is_set():
            delay = next_frame_at - self._monotonic()
            if delay > 0:
                self._stop_event.wait(delay)
            if self._stop_event.is_set():
                break
            frame = self._capture_frame()
            writer.write(frame)
            self._store_last_frame(frame)
            self._drain_events(stream, frames_dir, frame)
            next_frame_at += interval
            next_frame_at = self._skip_missed_frame_deadlines(
                next_frame_at,
                interval,
            )

    def _drain_events(
        self,
        stream: TextIO,
        frames_dir: Path,
        after_frame: Optional[np.ndarray],
    ) -> None:
        while True:
            try:
                queued = self._event_queue.get_nowait()
            except queue.Empty:
                return
            stream.write(f"{dump_event(queued.event)}\n")
            stream.flush()
            self._event_count += 1
            prefix = f"{queued.event.seq:06d}"
            if queued.before_frame is not None:
                cv2.imwrite(str(frames_dir / f"{prefix}-before.png"), queued.before_frame)
            if after_frame is not None:
                cv2.imwrite(str(frames_dir / f"{prefix}-after.png"), after_frame)

    def _capture_frame(self) -> np.ndarray:
        image = self._env.capture_screen().convert("RGB")
        frame = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        if self._client_size != (0, 0):
            height, width = frame.shape[:2]
            if (width, height) != self._client_size:
                self.request_stop("window_resized")
                raise RuntimeError(
                    f"录制期间客户区尺寸变化: {self._client_size} → {(width, height)}"
                )
        return frame

    @staticmethod
    def _validate_first_frame(frame: np.ndarray) -> None:
        """拒绝近似纯色首帧，避免生成无法用于回放的录制。"""
        if frame.size == 0 or float(frame.std()) < 1.0:
            raise RuntimeError(
                "录制首帧近似纯色，请确认游戏窗口已正常显示后重新录制"
            )

    def _new_event(
        self,
        kind: RecordingEventKind,
        action: str,
        **fields: object,
    ) -> RecordingEvent:
        with self._event_lock:
            self._seq += 1
            elapsed_ms = max(
                0,
                int((self._monotonic() - self._start_monotonic) * 1000),
            )
            return RecordingEvent(
                schema_version=RECORDING_SCHEMA_VERSION,
                seq=self._seq,
                elapsed_ms=elapsed_ms,
                kind=kind,
                action=action,
                **fields,
            )

    def _enqueue_event(self, event: RecordingEvent) -> None:
        self._event_queue.put(
            _QueuedEvent(event=event, before_frame=self._last_frame_copy())
        )

    def _prepare_directories(self) -> tuple[Path, Path]:
        scenario_root = (self._output_root / self._scenario).resolve()
        scenario_root.mkdir(parents=True, exist_ok=True)
        partial_dir = scenario_root / f"{self._recording_id}.partial"
        final_dir = scenario_root / self._recording_id
        if partial_dir.exists() or final_dir.exists():
            raise FileExistsError(f"录制标识已经存在: {self._recording_id}")
        partial_dir.mkdir()
        return partial_dir, final_dir

    def _write_metadata(
        self,
        directory: Path,
        status: str,
        stop_reason: Optional[str],
    ) -> None:
        elapsed = 0
        if self._start_monotonic > 0:
            elapsed = max(
                0,
                int((self._monotonic() - self._start_monotonic) * 1000),
            )
        width, height = self._client_size
        metadata = RecordingMetadata(
            schema_version=RECORDING_SCHEMA_VERSION,
            recording_id=self._recording_id,
            scenario=self._scenario,
            started_at=self._started_at or self._now_iso(),
            ended_at=self._now_iso() if status != "recording" else None,
            duration_ms=elapsed,
            window_title=self._window_title,
            client_width=max(width, 1),
            client_height=max(height, 1),
            fps=self._fps,
            codec=self._codec,
            event_count=self._event_count,
            dropped_frame_count=self._dropped_frames,
            status=status,
            stop_reason=stop_reason,
        )
        save_metadata(directory / "metadata.json", metadata)

    def _store_last_frame(self, frame: np.ndarray) -> None:
        with self._frame_lock:
            self._last_frame = frame.copy()

    def _last_frame_copy(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            return None if self._last_frame is None else self._last_frame.copy()

    def _skip_missed_frame_deadlines(
        self,
        next_frame_at: float,
        interval: float,
    ) -> float:
        now = self._monotonic()
        if next_frame_at > now:
            return next_frame_at
        missed = int((now - next_frame_at) // interval) + 1
        self._dropped_frames += missed
        return next_frame_at + missed * interval

    @staticmethod
    def _create_video_writer(
        path: Path,
        codec: str,
        fps: float,
        size: tuple[int, int],
    ) -> VideoWriter:
        fourcc = cv2.VideoWriter_fourcc(*codec)
        if os.name == "nt":
            writer = cv2.VideoWriter(
                str(path),
                cv2.CAP_MSMF,
                fourcc,
                fps,
                size,
            )
            if writer.isOpened():
                return writer
            writer.release()
        return cv2.VideoWriter(str(path), fourcc, fps, size)

    @staticmethod
    def _new_recording_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{timestamp}-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
