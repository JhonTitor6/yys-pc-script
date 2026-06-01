from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class ScriptCategory(StrEnum):
    """脚本分类。"""

    STABLE = "stable"
    EXPERIMENTAL = "experimental"


class RunStatus(StrEnum):
    """脚本运行状态。"""

    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCESS = "success"
    ERROR = "error"
    STOPPED = "stopped"


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
