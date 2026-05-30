from __future__ import annotations

from datetime import datetime
from time import sleep
from typing import Any

from ui_backend.models import RunRequest, RunSourceType, RunStatus, WorkflowStepType


class SchedulerService:
    """编排调度服务。"""

    def __init__(self, run_manager: Any) -> None:
        """初始化调度服务。"""
        self._run_manager = run_manager

    def run_workflow_now(self, workflow: dict[str, Any]) -> None:
        """同步执行工作流步骤。

        第一版会在每个运行类步骤完成后再推进下一步；异常向上传播，
        等价于失败即停止，暂不单独实现 failure_policy。
        """
        workflow_id = int(workflow["id"])
        for step in workflow["steps"]:
            run_id = self.run_step(workflow_id=workflow_id, step=step)
            wait = getattr(self._run_manager, "wait", None)
            if run_id is not None and callable(wait):
                wait(run_id, timeout=None)
                self._raise_if_run_failed(run_id)

    def run_step(self, workflow_id: int, step: dict[str, Any]) -> int | None:
        """执行单个工作流步骤。"""
        step_type = step["step_type"]
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

    def _time_reached(self, target_hh_mm: str) -> bool:
        """判断今天当前本地时间是否已达到 HH:MM 目标时间。

        第一版不处理跨午夜窗口，只比较今天的当前时间是否大于等于目标时间。
        """
        return self._seconds_until_target(target_hh_mm) <= 0

    def _seconds_until_target(self, target_hh_mm: str) -> float:
        """计算距离今天 HH:MM 目标时间还有多少秒，负数表示已过。"""
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

    def _raise_if_run_failed(self, run_id: int) -> None:
        """在运行步骤进入错误终态后中断编排。"""
        status_getter = getattr(self._run_manager, "run_status", None)
        if not callable(status_getter):
            return
        status = status_getter(run_id)
        if status == RunStatus.ERROR.value:
            raise RuntimeError(f"运行失败，编排已停止: {run_id}")
