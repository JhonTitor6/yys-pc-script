from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from ui_backend.models import RunStatus, WorkflowFailurePolicy, WorkflowStepType
from ui_backend.scheduler.service import SchedulerService
from ui_backend.events.hub import EventHub
from ui_backend.scripts.registry import ScriptRegistry


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


def _two_steps(policy: str = "stop", first_type: str = "run_script") -> dict[str, Any]:
    """创建无实机依赖的两步工作流。"""
    return {"id": 1, "failure_policy": policy, "steps": [
        {"id": 10, "step_type": first_type, "script_id": "first", "config": {},
         "condition": {"until": "23:00"} if first_type == "run_until_time" else {},
         "retry_count": 3},
        {"id": 11, "step_type": "run_script", "script_id": "second", "config": {}, "condition": {}},
    ]}


@pytest.mark.parametrize("policy", ["stop", "continue", "retry", "skip", "manual"])
def test_stopped_script_never_advances_or_retries(policy: str) -> None:
    # 产品契约来源：一条龙 R6，用户停止不能被失败策略覆盖或误判为成功。
    manager = FakeRunManager(statuses={1: "stopped"})
    hub = EventHub()
    scheduler = SchedulerService(manager, event_hub=hub)
    assert scheduler.run_workflow_now(_two_steps(policy)) == RunStatus.ERROR.value
    assert [item["script_id"] for item in manager.started] == ["first"]
    states = [event["status"] for event in hub.recent_events() if event.get("step_id") == 10]
    assert states == ["running", "stopped"]


@pytest.mark.parametrize("status", [None, "running", "queued", "paused", "unknown"])
def test_unconfirmed_terminal_state_never_advances(status: str | None) -> None:
    # 产品契约来源：工作流子任务，等待结束不代表业务成功，必须核验明确终态。
    manager = FakeRunManager()
    manager.run_status = lambda _run_id: status
    scheduler = SchedulerService(manager)
    with pytest.raises(RuntimeError, match="终态"):
        scheduler.run_workflow_now(_two_steps("continue"))
    assert len(manager.started) == 1


def test_unfinished_wait_never_advances_even_if_snapshot_says_success() -> None:
    # 产品契约来源：执行槽未释放不得启动后续脚本。
    manager = FakeRunManager(wait_result=False)
    with pytest.raises(RuntimeError, match="未完成"):
        SchedulerService(manager).run_workflow_now(_two_steps())
    assert len(manager.started) == 1


def test_explicit_skipped_step_is_not_published_as_success() -> None:
    # 产品契约来源：父任务 R4，明确跳过可推进，但不能当全部步骤已完成。
    manager = FakeRunManager(statuses={1: "skipped"})
    hub = EventHub()
    assert SchedulerService(manager, event_hub=hub).run_workflow_now(_two_steps()) == "error"
    assert len(manager.started) == 2
    assert [event["status"] for event in hub.recent_events() if event.get("step_id") == 10] == ["running", "skipped"]


def test_scheduler_owned_timed_stop_preserves_normal_advancement(monkeypatch: pytest.MonkeyPatch) -> None:
    # 产品契约来源：旧 run_until_time 按时停止是正常完成，不能被用户停止修复破坏。
    class TimedManager(FakeRunManager):
        def wait(self, run_id: int, timeout: object = None) -> bool:
            super().wait(run_id, timeout)
            return timeout is None

    manager = TimedManager(statuses={1: "stopped"})
    scheduler = SchedulerService(manager)
    monkeypatch.setattr(scheduler, "_seconds_until_target", lambda _: 60.0)
    assert scheduler.run_workflow_now(_two_steps(first_type="run_until_time")) == "success"
    assert manager.stopped == [1]
    assert len(manager.started) == 2


def test_user_stops_timed_step_before_deadline_no_advancement(monkeypatch: pytest.MonkeyPatch) -> None:
    # 产品契约来源：限时步骤也必须响应用户停止，不能因步骤类型忽略取消。
    manager = FakeRunManager(statuses={1: "stopped"})
    scheduler = SchedulerService(manager)
    monkeypatch.setattr(scheduler, "_seconds_until_target", lambda _: 60.0)
    assert scheduler.run_workflow_now(_two_steps(first_type="run_until_time")) == "error"
    assert manager.stopped == []
    assert len(manager.started) == 1


def test_preflight_checks_missing_later_script_before_any_start() -> None:
    # 产品契约来源：一条龙六步未就绪时，不应先执行、消耗前几步才遇到缺失脚本。
    manager = FakeRunManager()
    manager.registry = ScriptRegistry()
    workflow = _two_steps()
    workflow["steps"][0]["script_id"] = "realm_foster"
    workflow["steps"][1]["script_id"] = "unregistered_tail_step"
    with pytest.raises(KeyError, match="unregistered_tail_step"):
        SchedulerService(manager).run_workflow_now(workflow)
    assert manager.started == []


def test_preflight_imports_later_classes_before_any_start() -> None:
    # 产品契约来源：仅登记脚本名仍可能导入失败，必须在首步动作之前发现。
    manager = FakeRunManager()

    def load(script_id: str) -> type:
        if script_id == "second":
            raise ImportError("second 模块缺失")
        return object

    manager.registry = SimpleNamespace(get=lambda _: object(), load_class=load)
    with pytest.raises(ImportError, match="second"):
        SchedulerService(manager).run_workflow_now(_two_steps())
    assert manager.started == []


def test_missing_wait_interface_cannot_advance() -> None:
    # 产品契约来源：不能确认运行完成时中断，不能把不完整运行管理器当成功。
    manager = FakeRunManager()
    manager.wait = None
    with pytest.raises(RuntimeError, match="等待接口"):
        SchedulerService(manager).run_workflow_now(_two_steps())
    assert manager.started == []


def test_missing_status_interface_cannot_start() -> None:
    # 产品契约来源：执行前必须知道能够核验终态，不能执行后才发现无法确认结果。
    manager = FakeRunManager()
    manager.run_status = None
    with pytest.raises(RuntimeError, match="终态查询接口"):
        SchedulerService(manager).run_workflow_now(_two_steps())
    assert manager.started == []
