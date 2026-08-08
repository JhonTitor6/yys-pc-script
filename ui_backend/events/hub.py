from __future__ import annotations

import asyncio
import threading
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


class EventHub:
    """负责保存近期事件并广播给 WebSocket 客户端。"""

    def __init__(self, max_recent_events: int = 200) -> None:
        self._connections: set[WebSocket] = set()
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=max_recent_events)
        self._recent_events_lock = threading.Lock()
        self._next_seq = 0
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, websocket: WebSocket) -> None:
        """接受并登记 WebSocket 连接。"""
        self._loop = asyncio.get_running_loop()
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """移除 WebSocket 连接。"""
        async with self._lock:
            self._connections.discard(websocket)

    async def publish(self, event: dict[str, Any]) -> None:
        """保存并广播事件。"""
        normalized = self._normalize(event)
        self._append_recent(normalized)
        await self._broadcast(normalized)

    async def _broadcast(self, event: dict[str, Any]) -> None:
        """广播事件给当前连接。"""
        async with self._lock:
            targets = list(self._connections)
        for websocket in targets:
            try:
                await websocket.send_json(event)
            except Exception:
                await self.disconnect(websocket)

    def publish_from_thread(self, event: dict[str, Any]) -> None:
        """从脚本线程投递事件。"""
        normalized = self._normalize(event)
        self._append_recent(normalized)
        if self._loop is None or self._loop.is_closed():
            return
        coroutine = self._broadcast(normalized)
        try:
            asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        except RuntimeError:
            coroutine.close()

    def _append_recent(self, event: dict[str, Any]) -> None:
        """保存近期事件。"""
        with self._recent_events_lock:
            self._recent_events.append(event)

    def recent_events(self, after_seq: int | None = None) -> list[dict[str, Any]]:
        """返回近期事件副本，可按序号过滤。"""
        with self._recent_events_lock:
            events = list(self._recent_events)
        if after_seq is None:
            return events
        return [event for event in events if int(event.get("seq", 0)) > after_seq]

    def _normalize(self, event: dict[str, Any]) -> dict[str, Any]:
        """为业务事件补齐统一的序号、ID 和时间。"""
        with self._recent_events_lock:
            self._next_seq += 1
            seq = self._next_seq
        normalized = dict(event)
        normalized.setdefault("seq", seq)
        normalized.setdefault("event_id", str(uuid.uuid4()))
        normalized.setdefault(
            "timestamp",
            datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        )
        return normalized
