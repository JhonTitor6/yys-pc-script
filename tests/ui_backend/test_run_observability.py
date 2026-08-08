from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from ui_backend.app import create_app
from ui_backend.events.hub import EventHub
from ui_backend.models import RunRequest, RunSourceType, RunStatus
from ui_backend.runs.manager import RunManager
from ui_backend.storage.database import Database
from ui_backend.storage.repositories import Storage


class _FailingScript:
    """用于验证产品契约：脚本异常必须留下可观察失败事实。"""

    def run(self) -> None:
        raise RuntimeError("测试脚本失败")


class _FailingRegistry:
    def load_class(self, _script_id: str) -> type[_FailingScript]:
        return _FailingScript

    def get(self, _script_id: str) -> Any:
        return type("Definition", (), {"default_config": {}})()


def test_event_hub_assigns_sequence_and_supports_incremental_replay() -> None:
    """产品契约：重连只消费快照之后的新事件。"""
    hub = EventHub()

    hub.publish_from_thread({"type": "log", "message": "第一条"})
    hub.publish_from_thread({"type": "log", "message": "第二条"})

    events = hub.recent_events()
    assert events[0]["seq"] < events[1]["seq"]
    assert events[0]["event_id"]
    assert events[0]["timestamp"]
    assert [event["message"] for event in hub.recent_events(after_seq=events[0]["seq"])] == [
        "第二条"
    ]


def test_run_repository_exposes_normalized_snapshot(tmp_path: Path) -> None:
    """产品契约：API、WebSocket 和 GUI 读取同一组运行字段。"""
    database = Database(tmp_path / "ui.db")
    database.initialize()
    storage = Storage(database)
    run_id = storage.runs.create(
        script_id="fake",
        source_type=RunSourceType.MANUAL,
        config={"max_battle_count": 10},
        task_id="fake-task",
    )

    queued = storage.runs.get(run_id)
    assert queued is not None
    assert queued["run_id"] == run_id
    assert queued["task_id"] == "fake-task"
    assert queued["available_actions"] == ["stop"]

    storage.runs.update_status(
        run_id,
        RunStatus.ERROR,
        error_code="SCRIPT_EXCEPTION",
        error_message="失败",
        stage="script_failed",
        progress={"current": 2, "total": 10, "percent": 20},
    )
    failed = storage.runs.get(run_id)
    assert failed is not None
    assert failed["error_code"] == "SCRIPT_EXCEPTION"
    assert failed["progress"]["percent"] == 20
    assert failed["available_actions"] == ["retry", "skip", "stop", "manual_takeover"]


def test_run_manager_failure_records_evidence_and_recovery(tmp_path: Path) -> None:
    """产品契约：失败至少有日志和证据捕获结果，且可执行跳过。"""
    database = Database(tmp_path / "ui.db")
    database.initialize()
    storage = Storage(database)
    manager = RunManager(storage, _FailingRegistry(), EventHub())

    run_id = manager.start(RunRequest(script_id="fake", config={}))
    deadline = time.time() + 2
    while time.time() < deadline:
        if storage.runs.get(run_id)["status"] == RunStatus.ERROR.value:
            break
        time.sleep(0.01)

    failed = storage.runs.get(run_id)
    assert failed is not None
    assert failed["status"] == RunStatus.ERROR.value
    assert failed["error_code"] == "SCRIPT_EXCEPTION"
    assert failed["available_actions"]
    assert storage.logs.list_by_run(run_id)
    evidence = storage.evidence.list_by_run(run_id)
    assert len(evidence) == 1
    assert evidence[0]["capture_error"]

    manager.skip(run_id)
    skipped = storage.runs.get(run_id)
    assert skipped is not None
    assert skipped["status"] == RunStatus.SKIPPED.value
    assert skipped["available_actions"] == []


def test_websocket_sends_current_snapshot_before_incremental_events(tmp_path: Path) -> None:
    """产品契约：WebSocket 重连先恢复当前运行，再回放增量事件。"""
    app = create_app(db_path=tmp_path / "ui.db")
    run_id = app.state.storage.runs.create(
        script_id="fake",
        source_type=RunSourceType.MANUAL,
        config={},
    )
    app.state.storage.runs.update_status(run_id, RunStatus.RUNNING, stage="script_running")
    app.state.event_hub.publish_from_thread({"type": "log", "run_id": run_id, "message": "运行中"})

    with TestClient(app).websocket_connect("/ws/events") as websocket:
        first = websocket.receive_json()

    assert first["type"] == "run_snapshot"
    assert first["snapshot"]["run_id"] == run_id
    assert first["snapshot"]["status"] == RunStatus.RUNNING.value
    assert "pause" in first["snapshot"]["available_actions"]
