from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class ScriptCategory(StrEnum):
    """脚本分类。"""

    STABLE = "stable"
    EXPERIMENTAL = "experimental"


class ConnectionStatus(StrEnum):
    """桌面客户端与后端的连接状态。"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


class RunStatus(StrEnum):
    """脚本运行状态。"""

    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCESS = "success"
    ERROR = "error"
    STOPPED = "stopped"
    SKIPPED = "skipped"
    MANUAL = "manual"


class RunStage(StrEnum):
    """规范化运行阶段（设计 §4.4）。

    RunStatus 保持粗粒度生命周期；RunStage 描述准备、等待、导航、
    验证与业务运行等细粒度阶段。REST、WebSocket、SQLite 与 GUI
    使用完全相同的字符串值，GUI 不得从日志推断阶段。
    """

    QUEUED = "queued"
    PREPARING = "preparing"
    WAITING_SAFE_ENTRY = "waiting_safe_entry"
    WAITING_SAFE_ENTRY_TIMEOUT = "waiting_safe_entry_timeout"
    NAVIGATING = "navigating"
    VERIFYING_ENTRY = "verifying_entry"
    SCRIPT_RUNNING = "script_running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ENTRY_FAILED = "entry_failed"
    MANUAL_TAKEOVER = "manual_takeover"
    STOPPED = "stopped"
    STOPPING = "stopping"
    STOP_TIMEOUT = "stop_timeout"
    START_FAILED = "start_failed"
    SCRIPT_FAILED = "script_failed"
    STOPPED_AFTER_ERROR = "stopped_after_error"
    BACKEND_RESTARTED = "backend_restarted"
    SKIPPED = "skipped"


class WorkflowStepStatus(StrEnum):
    """工作流步骤状态。"""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"
    MANUAL = "manual"


class AtomicActionStatus(StrEnum):
    """运行过程中原子控制动作的状态。"""

    AVAILABLE = "available"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class RunSourceType(StrEnum):
    """运行来源。"""

    MANUAL = "manual"
    WORKFLOW = "workflow"


class WorkflowStepType(StrEnum):
    """编排步骤类型。"""

    RUN_SCRIPT = "run_script"
    WAIT_DURATION = "wait_duration"
    RUN_UNTIL_TIME = "run_until_time"


class WorkflowFailurePolicy(StrEnum):
    """编排失败策略。"""

    STOP_WORKFLOW = "stop_workflow"
    CONTINUE_NEXT = "continue_next"
    RETRY_THEN_STOP = "retry_then_stop"
    STOP = "stop"
    CONTINUE = "continue"
    RETRY = "retry"
    SKIP = "skip"
    MANUAL = "manual"
    INHERIT = "inherit"


@dataclass(frozen=True)
class ConfigField:
    """脚本参数字段定义。"""

    key: str
    label: str
    field_type: Literal["number", "text", "select", "boolean"]
    default: Any
    min_value: int | float | None = None
    max_value: int | float | None = None
    options: list[dict[str, Any]] = field(default_factory=list)
    hot_reloadable: bool = True
    description: str = ""
    unit: str | None = None
    sensitive: bool = False


@dataclass(frozen=True)
class ScriptDefinition:
    """UI 可执行脚本定义。"""

    script_id: str
    display_name: str
    module_path: str
    class_name: str
    category: ScriptCategory
    description: str
    config_schema: list[ConfigField]
    default_config: dict[str, Any]


@dataclass(frozen=True)
class RunRequest:
    """启动脚本请求。"""

    script_id: str
    config: dict[str, Any]
    source_type: RunSourceType = RunSourceType.MANUAL
    workflow_id: int | None = None
    workflow_step_id: int | None = None
    task_id: str | None = None
    step_id: int | None = None
    action_id: str | None = None
    retry_count: int = 0
    parent_run_id: int | None = None


def available_actions_for_status(status: str | RunStatus) -> list[str]:
    """根据运行状态返回后端允许的控制动作。"""
    value = status.value if isinstance(status, RunStatus) else str(status)
    actions = {
        RunStatus.QUEUED.value: ["stop"],
        RunStatus.RUNNING.value: ["pause", "stop"],
        RunStatus.PAUSED.value: ["resume", "stop"],
        RunStatus.ERROR.value: ["retry", "skip", "stop", "manual_takeover"],
    }
    return list(actions.get(value, []))


def available_actions_for_run(
    status: str | RunStatus,
    stage: str | RunStage | None = None,
) -> list[str]:
    """根据 (status, stage) 共同派生可用操作（设计 §8.2）。

    后端是操作真源；GUI 只渲染本函数返回的数组。
    新增阶段/动作必须同步维护本矩阵与对应测试。
    """
    status_value = status.value if isinstance(status, RunStatus) else str(status)
    stage_value = stage.value if isinstance(stage, RunStage) else (str(stage) if stage else None)

    if status_value == RunStatus.QUEUED.value:
        return ["stop"]
    if status_value == RunStatus.RUNNING.value:
        if stage_value == RunStage.WAITING_SAFE_ENTRY_TIMEOUT.value:
            return ["continue_waiting", "manual_takeover", "stop"]
        if stage_value == RunStage.SCRIPT_RUNNING.value:
            return ["pause", "stop"]
        # 准备/等待/导航/验证阶段：只允许停止
        return ["stop"]
    if status_value == RunStatus.PAUSED.value:
        return ["resume", "stop"]
    if status_value == RunStatus.ERROR.value:
        return ["retry", "skip", "stop", "manual_takeover"]
    if status_value == RunStatus.MANUAL.value:
        # 人工接管后“重新识别并重试”创建关联新 run（AC12）
        return ["retry"]
    return []
