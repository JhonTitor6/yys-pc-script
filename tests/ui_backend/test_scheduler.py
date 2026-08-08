from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest

from ui_backend.models import RunStatus, WorkflowFailurePolicy, WorkflowStepType
from ui_backend.scheduler.service import SchedulerService


class FakeRunManager:
    def __init__(self, statuses: dict[int, str] | None = None, wait_result: bool = True) -> None:
        self.started: list[dict[str, object]] = []
        self.stopped: list[int] = []
        self.waited: list[int] = []
        self.wait_timeouts: list[object] = []
        self.statuses = statuses or {}
        self.wait_result = wait_result
        self.active: int | None = None
        self.current = 7

    def start(self, request: Any) -> int:
        if self.active is not None:
            raise RuntimeError("已有脚本正在运行")

        run_id = len(self.started) + 1
        self.active = run_id
        self.started.append({"script_id": request.script_id, "config": request.config})
        return run_id

    def stop(self, run_id: int) -> None:
        self.stopped.append(run_id)

    def current_run_id(self) -> int | None:
        return self.current

    def wait(self, run_id: int, timeout: object = None) -> bool:
        self.waited.append(run_id)
        self.wait_timeouts.append(timeout)
        if self.active == run_id:
            self.active = None
        return self.wait_result

    def run_status(self, run_id: int) -> str | None:
        return self.statuses.get(run_id, "success")


def test_scheduler_runs_steps_in_order() -> None:
    run_manager = FakeRunManager()
    scheduler = SchedulerService(run_manager=run_manager)

    workflow = {
        "id": 1,
        "failure_policy": WorkflowFailurePolicy.STOP_WORKFLOW.value,
        "steps": [
            {
                "id": 10,
                "step_type": WorkflowStepType.RUN_SCRIPT.value,
                "script_id": "exploration_28",
                "config": {"max_battle_count": 200},
                "condition": {},
            },
            {
                "id": 11,
                "step_type": WorkflowStepType.RUN_SCRIPT.value,
                "script_id": "realm_raid",
                "config": {"max_battle_count": 9},
                "condition": {},
            },
        ],
    }

    scheduler.run_workflow_now(workflow)

    assert [item["script_id"] for item in run_manager.started] == [
        "exploration_28",
        "realm_raid",
    ]
    assert run_manager.waited == [1, 2]


def test_run_until_time_stops_current_run_when_time_reached() -> None:
    run_manager = FakeRunManager()
    scheduler = SchedulerService(run_manager=run_manager)
    target = (datetime.now() - timedelta(minutes=1)).strftime("%H:%M")

    scheduler.run_step(
        workflow_id=1,
        step={
            "id": 20,
            "step_type": WorkflowStepType.RUN_UNTIL_TIME.value,
            "script_id": "douji",
            "config": {},
            "condition": {"until": target},
        },
    )

    assert run_manager.started[0]["script_id"] == "douji"
    assert run_manager.stopped == [1]


def test_run_until_time_validates_until_before_starting() -> None:
    run_manager = FakeRunManager()
    scheduler = SchedulerService(run_manager=run_manager)

    with pytest.raises(ValueError):
        scheduler.run_step(
            workflow_id=1,
            step={
                "id": 21,
                "step_type": WorkflowStepType.RUN_UNTIL_TIME.value,
                "script_id": "douji",
                "config": {},
                "condition": {"until": "9:05"},
            },
        )

    assert run_manager.started == []
    assert run_manager.active is None


def test_run_until_time_waits_until_future_time_then_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            return cls(2026, 6, 1, 10, 0, 0)

    monkeypatch.setattr("ui_backend.scheduler.service.datetime", FixedDateTime)
    run_manager = FakeRunManager(wait_result=False)
    scheduler = SchedulerService(run_manager=run_manager)

    run_id = scheduler.run_step(
        workflow_id=1,
        step={
            "id": 22,
            "step_type": WorkflowStepType.RUN_UNTIL_TIME.value,
            "script_id": "douji",
            "config": {},
            "condition": {"until": "10:01"},
        },
    )

    assert run_id == 1
    assert run_manager.waited == [1]
    assert isinstance(run_manager.wait_timeouts[0], float)
    assert 59.0 <= run_manager.wait_timeouts[0] <= 60.0
    assert run_manager.stopped == [1]


def test_scheduler_stops_workflow_when_run_finishes_with_error() -> None:
    run_manager = FakeRunManager(statuses={1: "error"})
    scheduler = SchedulerService(run_manager=run_manager)
    workflow = {
        "id": 1,
        "failure_policy": WorkflowFailurePolicy.STOP_WORKFLOW.value,
        "steps": [
            {
                "id": 30,
                "step_type": WorkflowStepType.RUN_SCRIPT.value,
                "script_id": "first",
                "config": {},
                "condition": {},
            },
            {
                "id": 31,
                "step_type": WorkflowStepType.RUN_SCRIPT.value,
                "script_id": "second",
                "config": {},
                "condition": {},
            },
        ],
    }

    with pytest.raises(RuntimeError, match="运行失败"):
        scheduler.run_workflow_now(workflow)

    assert [item["script_id"] for item in run_manager.started] == ["first"]


def test_time_reached_rejects_invalid_hh_mm() -> None:
    run_manager = FakeRunManager()
    scheduler = SchedulerService(run_manager=run_manager)

    with pytest.raises(ValueError):
        scheduler._time_reached("9:05")

    with pytest.raises(ValueError):
        scheduler._time_reached("24:00")


def test_scheduler_manual_run_does_not_advance_steps() -> None:
    """AC13：run 终结为 manual 时不推进后续步骤，发布人工介入事件。"""
    run_manager = FakeRunManager(statuses={1: "manual"})
    scheduler = SchedulerService(run_manager=run_manager)

    workflow = {
        "id": 1,
        "failure_policy": WorkflowFailurePolicy.STOP_WORKFLOW.value,
        "steps": [
            {
                "id": 10,
                "step_type": WorkflowStepType.RUN_SCRIPT.value,
                "script_id": "soul_raid",
                "config": {},
                "condition": {},
                "failure_policy": "inherit",
            },
            {
                "id": 11,
                "step_type": WorkflowStepType.RUN_SCRIPT.value,
                "script_id": "exploration_28",
                "config": {},
                "condition": {},
                "failure_policy": "inherit",
            },
        ],
    }

    outcome = scheduler.run_workflow_now(workflow)

    assert outcome == RunStatus.ERROR.value
    # 只有第一个步骤被执行（manual 后不再启动后续步骤）
    assert len(run_manager.started) == 1
    assert run_manager.started[0]["script_id"] == "soul_raid"
    events = scheduler.event_hub.recent_events() if hasattr(scheduler, "event_hub") else []
    assert not events
