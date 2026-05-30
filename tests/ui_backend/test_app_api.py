from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ui_backend.app import create_app
from ui_backend.events.hub import EventHub
from ui_backend.models import RunRequest, RunSourceType, RunStatus


class _DummyScript:
    def run(self) -> None:
        pass


class _FakeRunManager:
    def __init__(self) -> None:
        self.request: RunRequest | None = None

    def start(self, request: RunRequest) -> int:
        self.request = request
        return 42


def _load_dummy_script(script_id: str) -> type[_DummyScript]:
    return _DummyScript


class _FakeWorkflowRepository:
    def list_all(self) -> list[dict[str, Any]]:
        return [
            {
                "id": 99,
                "name": "替换任务",
                "group_name": "测试",
                "enabled": True,
                "trigger_type": "manual",
                "trigger_config": {},
                "failure_policy": "stop_workflow",
            }
        ]


class _FakeWorkflowStepRepository:
    def list_by_workflow(self, workflow_id: int) -> list[dict[str, Any]]:
        return [
            {
                "id": 100,
                "workflow_id": workflow_id,
                "sort_order": 1,
                "step_type": "run_script",
                "script_id": "fake_script",
                "config": {},
                "condition": {},
                "retry_count": 0,
            }
        ]


class _FakeStorage:
    def __init__(self) -> None:
        self.workflows = _FakeWorkflowRepository()
        self.workflow_steps = _FakeWorkflowStepRepository()


class _SlowScheduler:
    def __init__(self) -> None:
        self.finished = threading.Event()
        self.workflow: dict[str, Any] | None = None

    def run_workflow_now(self, workflow: dict[str, Any]) -> None:
        self.workflow = workflow
        time.sleep(0.2)
        self.finished.set()


class _FailingScheduler:
    def run_workflow_now(self, workflow: dict[str, Any]) -> None:
        raise RuntimeError("编排失败")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_event_hub_keeps_recent_events() -> None:
    hub = EventHub(max_recent_events=2)

    await hub.publish({"type": "log", "message": "第一条"})
    await hub.publish({"type": "log", "message": "第二条"})
    await hub.publish({"type": "log", "message": "第三条"})

    recent = hub.recent_events()
    assert [item["message"] for item in recent] == ["第二条", "第三条"]


def test_event_hub_thread_publish_keeps_recent_without_loop() -> None:
    hub = EventHub()

    hub.publish_from_thread({"type": "log", "message": "线程日志"})

    recent = hub.recent_events()
    assert [item["message"] for item in recent] == ["线程日志"]


def test_event_hub_thread_publish_ignores_closed_loop() -> None:
    hub = EventHub()
    loop = asyncio.new_event_loop()
    loop.close()
    hub._loop = loop

    hub.publish_from_thread({"type": "log", "message": "关闭循环日志"})

    recent = hub.recent_events()
    assert [item["message"] for item in recent] == ["关闭循环日志"]


def test_api_lists_scripts_and_starts_run(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "ui.db")
    app.state.registry.load_class = _load_dummy_script
    fake_run_manager = _FakeRunManager()
    app.state.run_manager = fake_run_manager
    client = TestClient(app)

    scripts_response = client.get("/api/scripts")
    assert scripts_response.status_code == 200
    assert any(item["script_id"] == "soul_raid" for item in scripts_response.json())

    current_response = client.get("/api/runs/current")
    assert current_response.status_code == 200
    assert current_response.json() is None

    start_response = client.post(
        "/api/runs/start",
        json={"script_id": "soul_raid", "config": {"max_battle_count": 3}},
    )
    assert start_response.status_code == 200
    assert start_response.json() == {"id": 42}
    assert fake_run_manager.request is not None
    assert fake_run_manager.request.script_id == "soul_raid"
    assert fake_run_manager.request.config == {"max_battle_count": 3}


def test_api_token_protects_http_routes_when_enabled(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "ui.db", api_token="secret-token")
    client = TestClient(app)

    missing_response = client.get("/api/scripts")
    wrong_response = client.get("/api/scripts", headers={"X-YYS-UI-Token": "wrong"})
    header_response = client.get("/api/scripts", headers={"X-YYS-UI-Token": "secret-token"})
    query_response = client.get("/api/scripts?token=secret-token")
    preflight_response = client.options(
        "/api/scripts",
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert missing_response.status_code == 403
    assert wrong_response.status_code == 403
    assert header_response.status_code == 200
    assert query_response.status_code == 200
    assert preflight_response.status_code == 200


def test_websocket_requires_token_when_enabled(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "ui.db", api_token="secret-token")
    app.state.event_hub.publish_from_thread({"type": "log", "message": "已连接"})
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/events"):
            pass

    with client.websocket_connect("/ws/events?token=secret-token") as websocket:
        assert websocket.receive_json()["message"] == "已连接"


def test_create_app_marks_unfinished_runs_error_on_startup(tmp_path: Path) -> None:
    db_path = tmp_path / "ui.db"
    first_app = create_app(db_path=db_path)
    run_id = first_app.state.storage.runs.create(
        script_id="soul_raid",
        source_type=RunSourceType.MANUAL,
        config={},
    )
    first_app.state.storage.runs.update_status(run_id, RunStatus.RUNNING)

    restarted_app = create_app(db_path=db_path)
    client = TestClient(restarted_app)

    assert client.get("/api/runs/current").json() is None
    run = restarted_app.state.storage.runs.get(run_id)
    assert run is not None
    assert run["status"] == RunStatus.ERROR.value
    assert "后端重启" in run["error_message"]


def test_workflow_create_and_list(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "ui.db")
    client = TestClient(app)

    response = client.post(
        "/api/workflows",
        json={
            "name": "日常探索",
            "group_name": "日常",
            "enabled": True,
            "trigger_type": "manual",
            "trigger_config": {},
            "failure_policy": "stop_workflow",
            "steps": [
                {
                    "sort_order": 1,
                    "step_type": "run_script",
                    "script_id": "exploration_28",
                    "config": {"max_battle_count": 200},
                    "condition": {},
                    "retry_count": 0,
                }
            ],
        },
    )

    assert response.status_code == 200
    workflow_id = response.json()["id"]
    assert workflow_id > 0
    workflow = client.get("/api/workflows").json()[0]
    assert workflow["name"] == "日常探索"
    assert workflow["steps"][0]["script_id"] == "exploration_28"


def test_run_workflow_now_submits_scheduler_without_blocking(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "ui.db")
    scheduler = _SlowScheduler()
    app.state.scheduler = scheduler
    client = TestClient(app)

    response = client.post(
        "/api/workflows",
        json={
            "name": "后台执行",
            "group_name": "测试",
            "enabled": True,
            "trigger_type": "manual",
            "trigger_config": {},
            "failure_policy": "stop_workflow",
            "steps": [
                {
                    "sort_order": 1,
                    "step_type": "run_script",
                    "script_id": "exploration_28",
                    "config": {},
                    "condition": {},
                    "retry_count": 0,
                }
            ],
        },
    )
    workflow_id = response.json()["id"]

    started_at = time.perf_counter()
    run_response = client.post(f"/api/workflows/{workflow_id}/run-now")
    elapsed = time.perf_counter() - started_at

    assert run_response.status_code == 200
    assert run_response.json() == {"status": "started"}
    assert elapsed < 0.15
    assert scheduler.finished.wait(1)
    assert scheduler.workflow is not None
    assert scheduler.workflow["steps"][0]["script_id"] == "exploration_28"


def test_run_workflow_now_publishes_background_error_event(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "ui.db")
    app.state.scheduler = _FailingScheduler()
    client = TestClient(app)

    response = client.post(
        "/api/workflows",
        json={
            "name": "失败编排",
            "group_name": "测试",
            "enabled": True,
            "trigger_type": "manual",
            "trigger_config": {},
            "failure_policy": "stop_workflow",
            "steps": [
                {
                    "sort_order": 1,
                    "step_type": "run_script",
                    "script_id": "exploration_28",
                    "config": {},
                    "condition": {},
                    "retry_count": 0,
                }
            ],
        },
    )
    workflow_id = response.json()["id"]

    run_response = client.post(f"/api/workflows/{workflow_id}/run-now")

    assert run_response.status_code == 200
    assert run_response.json() == {"status": "started"}
    event = _wait_for_workflow_error(app.state.event_hub, workflow_id)
    assert event is not None
    assert "编排失败" in event["message"]


def test_routes_use_app_state_storage_for_workflows(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "ui.db")
    app.state.storage = _FakeStorage()
    client = TestClient(app)

    workflows = client.get("/api/workflows").json()

    assert workflows[0]["name"] == "替换任务"
    assert workflows[0]["steps"][0]["script_id"] == "fake_script"


def _wait_for_workflow_error(
    event_hub: EventHub,
    workflow_id: int,
    timeout: float = 1.0,
) -> dict[str, Any] | None:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        for event in event_hub.recent_events():
            if event.get("type") == "workflow_error" and event.get("workflow_id") == workflow_id:
                return event
        time.sleep(0.01)
    return None
