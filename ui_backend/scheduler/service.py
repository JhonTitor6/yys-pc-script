from __future__ import annotations

import threading
from datetime import datetime, timedelta
from time import sleep
from typing import Any

from ui_backend.events.hub import EventHub
from ui_backend.models import (
    RunRequest,
    RunSourceType,
    RunStatus,
    WorkflowFailurePolicy,
    WorkflowStepType,
)
from ui_backend.storage.repositories import Storage


class SchedulerService:
    """编排执行和周期调度服务。"""

    def __init__(
        self,
        run_manager: Any,
        storage: Storage | None = None,
        event_hub: EventHub | None = None,
    ) -> None:
        """初始化调度服务。"""
        self._run_manager = run_manager
        self._storage = storage
        self._event_hub = event_hub
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def run_workflow_now(self, workflow: dict[str, Any]) -> str:
        """按顺序执行工作流，并按工作流/步骤策略处理失败。

        _run_step_with_policy 返回：
        - True：步骤成功，继续下一步；
        - False：步骤未成功（error + continue/skip 策略），继续后续步骤；
        - None：人工介入（manual），中断后续步骤（AC13：等待关联重试）。
        """
        workflow_id = int(workflow["id"])
        workflow_success = True
        for step in workflow["steps"]:
            step_outcome = self._run_step_with_policy(workflow_id, workflow, step)
            if step_outcome is None:
                workflow_success = False
                break
            if not step_outcome:
                workflow_success = False
        return RunStatus.SUCCESS.value if workflow_success else RunStatus.ERROR.value

    def run_step(self, workflow_id: int, step: dict[str, Any]) -> int | None:
        """执行单个工作流步骤。"""
        step_type = str(step["step_type"])
        if step_type == WorkflowStepType.WAIT_DURATION.value:
            condition = step.get("condition", {})
            sleep(float(condition.get("seconds", 0)))
            return None

        seconds_until_stop: float | None = None
        if step_type == WorkflowStepType.RUN_UNTIL_TIME.value:
            condition = step.get("condition", {})
            until = condition.get("until")
            if until is None:
                raise ValueError("run_until_time 步骤必须提供 until")
            seconds_until_stop = self._seconds_until_target(str(until))

        request = RunRequest(
            script_id=str(step["script_id"]),
            config=dict(step.get("config", {})),
            source_type=RunSourceType.WORKFLOW,
            workflow_id=workflow_id,
            workflow_step_id=int(step["id"]),
            task_id=str(step.get("task_id") or workflow_id),
            step_id=int(step["id"]),
            retry_count=int(step.get("attempt", 0)),
        )
        run_id = self._run_manager.start(request)

        if seconds_until_stop is not None and seconds_until_stop <= 0:
            self._run_manager.stop(run_id)
        elif seconds_until_stop is not None:
            wait = getattr(self._run_manager, "wait", None)
            if callable(wait):
                finished = wait(run_id, timeout=seconds_until_stop)
                if not finished:
                    self._run_manager.stop(run_id)

        return run_id

    def preview_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """返回工作流的调度预览，不修改业务执行状态。"""
        result = dict(workflow)
        result["supported"] = workflow.get("trigger_type", "manual") in {
            "manual",
            "interval",
            "scheduled_time",
        }
        if not result["supported"]:
            result["schedule_note"] = "该触发类型暂未支持"
            result["next_run_at"] = None
            return result
        result["next_run_at"] = result.get("next_run_at") or self.calculate_next_run_at(workflow)
        return result

    def calculate_next_run_at(
        self,
        workflow: dict[str, Any],
        outcome: str | None = None,
        base_time: datetime | None = None,
    ) -> str | None:
        """使用统一规则计算预览和实际调度的下一次时间。"""
        trigger_type = str(workflow.get("trigger_type", "manual"))
        now = base_time or datetime.now()
        if trigger_type == "manual":
            return None
        if trigger_type == "interval":
            config = workflow.get("trigger_config") or {}
            default_interval = float(config.get("interval_seconds", 0) or 0)
            interval = (
                workflow.get("failure_interval_seconds")
                if outcome == RunStatus.ERROR.value
                else workflow.get("success_interval_seconds")
            )
            seconds = float(interval or default_interval)
            if seconds <= 0:
                return None
            last_run_at = self._parse_datetime(workflow.get("last_run_at"))
            anchor = last_run_at or now
            return (anchor + timedelta(seconds=seconds)).isoformat(timespec="seconds")
        if trigger_type == "scheduled_time":
            config = workflow.get("trigger_config") or {}
            target = str(config.get("time") or config.get("at") or "")
            return self._next_daily_time(target, now).isoformat(timespec="seconds")
        return None

    def run_pending(self, now: datetime | None = None) -> int:
        """触发到期的启用工作流，返回本轮触发数量。"""
        if self._storage is None:
            return 0
        current_time = now or datetime.now()
        workflows: list[dict[str, Any]] = []
        for item in self._storage.workflows.list_all():
            if not item.get("enabled") or item.get("trigger_type") == "manual":
                continue
            workflow = dict(item)
            workflow["steps"] = self._storage.workflow_steps.list_by_workflow(int(item["id"]))
            workflows.append(self.preview_workflow(workflow))
        due = [
            item
            for item in workflows
            if item.get("supported") and self._is_due(item.get("next_run_at"), current_time)
        ]
        due.sort(key=lambda item: (-int(item.get("priority", 0)), int(item["id"])))
        triggered = 0
        for workflow in due:
            current_run_id = getattr(self._run_manager, "current_run_id", None)
            active_run_id = current_run_id() if callable(current_run_id) else None
            if active_run_id is not None:
                self._publish(
                    {
                        "type": "scheduler_status",
                        "workflow_id": workflow["id"],
                        "status": "blocked_by_active_run",
                    }
                )
                continue
            triggered += 1
            self._storage.workflows.update_schedule_state(
                int(workflow["id"]),
                None,
                last_run_at=current_time.isoformat(timespec="seconds"),
            )
            outcome = RunStatus.SUCCESS.value
            try:
                result = self.run_workflow_now(workflow)
                if result == RunStatus.ERROR.value:
                    outcome = RunStatus.ERROR.value
            except Exception as exc:
                outcome = RunStatus.ERROR.value
                self._publish(
                    {
                        "type": "scheduler_status",
                        "workflow_id": workflow["id"],
                        "status": "error",
                        "message": str(exc),
                    }
                )
            refreshed = self._storage.workflows.get(int(workflow["id"])) or workflow
            next_run_at = self.calculate_next_run_at(refreshed, outcome, current_time)
            self._storage.workflows.update_schedule_state(
                int(workflow["id"]),
                next_run_at,
            )
            self._publish(
                {
                    "type": "scheduler_status",
                    "workflow_id": workflow["id"],
                    "status": "completed" if outcome == RunStatus.SUCCESS.value else "error",
                    "next_run_at": next_run_at,
                }
            )
        return triggered

    def start(self, interval_seconds: float = 1.0) -> None:
        """启动应用生命周期内的周期调度线程。"""
        if self._storage is None or self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()

        def _loop() -> None:
            while not self._stop_event.wait(interval_seconds):
                try:
                    self.run_pending()
                except Exception as exc:
                    self._publish({"type": "scheduler_status", "status": "error", "message": str(exc)})

        self._thread = threading.Thread(target=_loop, name="yys-scheduler", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """停止周期调度线程。"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout)
        self._thread = None

    def _run_step_with_policy(
        self,
        workflow_id: int,
        workflow: dict[str, Any],
        step: dict[str, Any],
    ) -> bool:
        """执行步骤并按策略重试、跳过或停止。"""
        policy = self._normalized_policy(step.get("failure_policy"), workflow.get("failure_policy"))
        max_retries = int(step.get("retry_count", 0) or 0) if policy == "retry" else 0
        attempts = 0
        while True:
            step_attempt = dict(step)
            step_attempt["attempt"] = attempts
            self._publish_step_event(workflow_id, step, "running", None, attempts)
            run_id = self.run_step(workflow_id=workflow_id, step=step_attempt)
            wait = getattr(self._run_manager, "wait", None)
            if run_id is not None and callable(wait):
                wait(run_id, timeout=None)
                status = self._run_status(run_id)
                if status == RunStatus.MANUAL.value:
                    # 人工接管（AC13）：原 run 不可变，中断后续步骤；
                    # 关联重试的新 run 独立记录结果，成功后由用户/后续执行推进。
                    self._publish_step_event(
                        workflow_id,
                        step,
                        "manual_intervention_required",
                        run_id,
                        attempts,
                    )
                    return None
                if status != RunStatus.ERROR.value:
                    self._publish_step_event(workflow_id, step, "success", run_id, attempts)
                    return True
                self._publish_step_event(workflow_id, step, "error", run_id, attempts)
                if attempts < max_retries:
                    attempts += 1
                    self._publish_step_event(workflow_id, step, "retry", run_id, attempts)
                    continue
                if policy in {"continue", "skip"}:
                    skip = getattr(self._run_manager, "skip", None)
                    if policy == "skip" and callable(skip):
                        try:
                            skip(run_id)
                        except RuntimeError:
                            pass
                    self._publish_step_event(workflow_id, step, "skipped", run_id, attempts)
                    return False
                if policy == "manual":
                    self._publish_step_event(
                        workflow_id,
                        step,
                        "manual_intervention_required",
                        run_id,
                        attempts,
                    )
                self._raise_if_run_failed(run_id)
            return True

    def _run_status(self, run_id: int) -> str | None:
        getter = getattr(self._run_manager, "run_status", None)
        return getter(run_id) if callable(getter) else None

    def _normalized_policy(self, step_policy: Any, workflow_policy: Any) -> str:
        """把旧策略值归一化为 stop/continue/retry/skip/manual。"""
        raw = str(step_policy or "inherit")
        if raw in {"", "inherit", WorkflowFailurePolicy.INHERIT.value}:
            raw = str(workflow_policy or WorkflowFailurePolicy.STOP_WORKFLOW.value)
        mapping = {
            "stop_workflow": "stop",
            "continue_next": "continue",
            "retry_then_stop": "retry",
        }
        return mapping.get(raw, raw)

    def _publish_step_event(
        self,
        workflow_id: int,
        step: dict[str, Any],
        status: str,
        run_id: int | None,
        attempt: int,
    ) -> None:
        """发布步骤推进事件。"""
        self._publish(
            {
                "type": "workflow_event",
                "workflow_id": workflow_id,
                "step_id": step.get("id"),
                "run_id": run_id,
                "status": status,
                "attempt": attempt,
            }
        )

    def _time_reached(self, target_hh_mm: str) -> bool:
        """判断今天当前本地时间是否已达到 HH:MM 目标时间。"""
        return self._seconds_until_target(target_hh_mm) <= 0

    def _seconds_until_target(self, target_hh_mm: str) -> float:
        """计算距离今天 HH:MM 目标时间还有多少秒。"""
        target_time = datetime.strptime(target_hh_mm, "%H:%M").time()
        if target_time.strftime("%H:%M") != target_hh_mm:
            raise ValueError("时间格式必须为零填充的 HH:MM")
        now = datetime.now()
        target_at = now.replace(
            hour=target_time.hour,
            minute=target_time.minute,
            second=0,
            microsecond=0,
        )
        return float((target_at - now).total_seconds())

    def _next_daily_time(self, target_hh_mm: str, now: datetime) -> datetime:
        """计算下一个本地每日时间点。"""
        target_time = datetime.strptime(target_hh_mm, "%H:%M").time()
        if target_time.strftime("%H:%M") != target_hh_mm:
            raise ValueError("时间格式必须为零填充的 HH:MM")
        target = now.replace(
            hour=target_time.hour,
            minute=target_time.minute,
            second=0,
            microsecond=0,
        )
        return target if target > now else target + timedelta(days=1)

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """解析本地无时区调度时间。"""
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    def _is_due(self, value: Any, now: datetime) -> bool:
        """判断下一次运行时间是否已到。"""
        parsed = self._parse_datetime(value)
        return parsed is not None and parsed <= now

    def _raise_if_run_failed(self, run_id: int) -> None:
        """在运行步骤进入错误终态后中断编排。"""
        status = self._run_status(run_id)
        if status == RunStatus.ERROR.value:
            raise RuntimeError(f"运行失败，编排已停止: {run_id}")

    def _publish(self, event: dict[str, Any]) -> None:
        """发布调度事件；没有事件中心时保持单元测试轻量。"""
        if self._event_hub is not None:
            self._event_hub.publish_from_thread(event)
