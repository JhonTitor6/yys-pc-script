from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from ui_backend.events.hub import EventHub
from ui_backend.models import RunSourceType, RunStatus, WorkflowFailurePolicy
from ui_backend.scheduler.service import SchedulerService
from ui_backend.scripts.registry import ScriptRegistry
from ui_backend.storage.database import Database
from ui_backend.storage.repositories import Storage
from ui_backend.app import create_app


def test_script_schema_exposes_renderable_metadata() -> None:
    """产品契约：通用脚本表单必须拿到稳定的说明和扩展元数据。"""
    scripts = ScriptRegistry().list_scripts()

    assert scripts
    for script in scripts:
        for field in script.config_schema:
            assert field.description
            assert isinstance(field.hot_reloadable, bool)
            assert field.unit is None or isinstance(field.unit, str)
            assert isinstance(field.sensitive, bool)


def test_workflow_and_step_schedule_fields_round_trip(tmp_path: Path) -> None:
    """产品契约：旧表可迁移，新工作流字段和步骤策略可完整读回。"""
    database = Database(tmp_path / "ui.db")
    database.initialize()
    storage = Storage(database)
    workflow_id = storage.workflows.create(
        name="夜间任务",
        group_name="日常",
        enabled=True,
        trigger_type="interval",
        trigger_config={"interval_seconds": 600},
        failure_policy=WorkflowFailurePolicy.CONTINUE.value,
        priority=8,
        success_interval_seconds=600,
        failure_interval_seconds=120,
        next_run_at="2026-08-08T22:00:00",
    )
    storage.workflow_steps.create(
        workflow_id=workflow_id,
        sort_order=1,
        step_type="run_script",
        script_id="soul_raid",
        config={"max_battle_count": 3},
        condition={},
        retry_count=2,
        failure_policy=WorkflowFailurePolicy.RETRY.value,
    )

    workflow = storage.workflows.get(workflow_id)
    steps = storage.workflow_steps.list_by_workflow(workflow_id)

    assert workflow is not None
    assert workflow["enabled"] is True
    assert workflow["priority"] == 8
    assert workflow["success_interval_seconds"] == 600
    assert workflow["failure_interval_seconds"] == 120
    assert workflow["next_run_at"] == "2026-08-08T22:00:00"
    assert steps[0]["failure_policy"] == "retry"
    assert steps[0]["retry_count"] == 2


def test_scheduler_policy_retry_and_step_events() -> None:
    """产品契约：retry 按次数重试，成功后才推进工作流。"""
    class FakeRunManager:
        def __init__(self) -> None:
            self.started: list[int] = []

        def start(self, request: Any) -> int:
            run_id = len(self.started) + 1
            self.started.append(run_id)
            return run_id

        def wait(self, run_id: int, timeout: float | None = None) -> bool:
            return True

        def run_status(self, run_id: int) -> str:
            return RunStatus.ERROR.value if run_id == 1 else RunStatus.SUCCESS.value

    run_manager = FakeRunManager()
    event_hub = EventHub()
    scheduler = SchedulerService(run_manager=run_manager, event_hub=event_hub)

    scheduler.run_workflow_now(
        {
            "id": 1,
            "failure_policy": WorkflowFailurePolicy.STOP.value,
            "steps": [
                {
                    "id": 10,
                    "step_type": "run_script",
                    "script_id": "soul_raid",
                    "config": {},
                    "condition": {},
                    "failure_policy": WorkflowFailurePolicy.RETRY.value,
                    "retry_count": 1,
                }
            ],
        }
    )

    events = event_hub.recent_events()
    assert run_manager.started == [1, 2]
    assert [event["status"] for event in events if event["type"] == "workflow_event"] == [
        "running",
        "error",
        "retry",
        "running",
        "success",
    ]


def test_run_detail_contains_workflow_logs_snapshots_and_evidence(tmp_path: Path) -> None:
    """产品契约：历史详情必须一次返回运行回看所需的全部分层数据。"""
    app = create_app(db_path=tmp_path / "ui.db")
    storage: Storage = app.state.storage
    workflow_id = storage.workflows.create(
        name="历史任务",
        group_name="测试",
        enabled=False,
        trigger_type="manual",
        trigger_config={},
        failure_policy=WorkflowFailurePolicy.STOP.value,
    )
    step_id = storage.workflow_steps.create(
        workflow_id=workflow_id,
        sort_order=1,
        step_type="run_script",
        script_id="soul_raid",
        config={"max_battle_count": 1},
        condition={},
        retry_count=0,
    )
    run_id = storage.runs.create(
        script_id="soul_raid",
        source_type=RunSourceType.WORKFLOW,
        config={"max_battle_count": 1},
        workflow_id=workflow_id,
        workflow_step_id=step_id,
    )
    storage.runs.update_status(run_id, RunStatus.ERROR, error_code="TEST_ERROR")
    storage.logs.append(run_id, "ERROR", "测试错误")
    storage.snapshots.append(run_id, "soul_raid", {"battle_count": 1})
    storage.evidence.append(run_id, "failure", capture_error="测试环境无截图")

    with TestClient(app) as client:
        response = client.get(f"/api/runs/{run_id}")

    body = response.json()
    assert response.status_code == 200
    assert body["workflow"]["id"] == workflow_id
    assert body["workflow_step"]["id"] == step_id
    assert body["logs"][0]["message"] == "测试错误"
    assert body["snapshots"][0]["state"]["battle_count"] == 1
    assert body["evidence"][0]["capture_error"] == "测试环境无截图"


def test_scheduler_preview_uses_same_interval_calculation() -> None:
    """产品契约：预览与调度使用同一个下一次时间计算函数。"""
    scheduler = SchedulerService(run_manager=object())
    base_time = datetime(2026, 8, 8, 20, 0, 0)
    workflow = {
        "trigger_type": "interval",
        "trigger_config": {"interval_seconds": 60},
        "success_interval_seconds": 300,
        "failure_interval_seconds": 30,
        "last_run_at": "2026-08-08T19:59:00",
    }

    success = scheduler.calculate_next_run_at(workflow, RunStatus.SUCCESS.value, base_time)
    failure = scheduler.calculate_next_run_at(workflow, RunStatus.ERROR.value, base_time)

    assert success == "2026-08-08T20:04:00"
    assert failure == "2026-08-08T19:59:30"


def test_scheduler_pending_loads_steps_and_orders_by_priority(tmp_path: Path) -> None:
    """产品契约：到期任务按优先级执行，调度线程不能丢失步骤定义。"""
    class FakeRunManager:
        def __init__(self) -> None:
            self.started: list[str] = []

        def current_run_id(self) -> None:
            return None

        def start(self, request: Any) -> int:
            self.started.append(request.script_id)
            return len(self.started)

        def wait(self, run_id: int, timeout: float | None = None) -> bool:
            return True

        def run_status(self, run_id: int) -> str:
            return RunStatus.SUCCESS.value

    database = Database(tmp_path / "scheduler.db")
    database.initialize()
    storage = Storage(database)
    for name, script_id, priority in (
        ("低优先级", "realm_raid", 1),
        ("高优先级", "soul_raid", 9),
    ):
        workflow_id = storage.workflows.create(
            name=name,
            group_name="测试",
            enabled=True,
            trigger_type="interval",
            trigger_config={"interval_seconds": 600},
            failure_policy=WorkflowFailurePolicy.STOP.value,
            priority=priority,
            success_interval_seconds=600,
            next_run_at="2026-08-08T19:00:00",
        )
        storage.workflow_steps.create(
            workflow_id=workflow_id,
            sort_order=1,
            step_type="run_script",
            script_id=script_id,
            config={},
            condition={},
            retry_count=0,
        )

    manager = FakeRunManager()
    scheduler = SchedulerService(run_manager=manager, storage=storage)
    triggered = scheduler.run_pending(datetime(2026, 8, 8, 20, 0, 0))

    assert triggered == 2
    assert manager.started == ["soul_raid", "realm_raid"]
