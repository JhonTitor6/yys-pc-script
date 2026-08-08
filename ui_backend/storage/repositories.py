from __future__ import annotations

import json
import uuid
from typing import Any

from ui_backend.models import (
    RunSourceType,
    RunStatus,
    available_actions_for_run,
    available_actions_for_status,
)
from ui_backend.storage.database import Database


def _row_to_dict(row: Any) -> dict[str, Any] | None:
    """将 sqlite Row 转为 dict。"""
    if row is None:
        return None
    return dict(row)


def _load_json(value: Any, fallback: Any) -> Any:
    """安全解析 JSON 列，兼容旧数据库中的空值。"""
    if value in (None, ""):
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


class WorkflowRepository:
    """编排任务仓库。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        name: str,
        group_name: str,
        enabled: bool,
        trigger_type: str,
        trigger_config: dict[str, Any],
        failure_policy: str,
        priority: int = 0,
        success_interval_seconds: float = 0,
        failure_interval_seconds: float = 0,
        next_run_at: str | None = None,
    ) -> int:
        """创建编排任务并返回主键。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO workflows
                    (name, group_name, enabled, trigger_type, trigger_config_json,
                     failure_policy, priority, success_interval_seconds,
                     failure_interval_seconds, next_run_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    group_name,
                    1 if enabled else 0,
                    trigger_type,
                    json.dumps(trigger_config, ensure_ascii=False),
                    failure_policy,
                    int(priority),
                    float(success_interval_seconds),
                    float(failure_interval_seconds),
                    next_run_at,
                ),
            )
            return int(cur.lastrowid)

    def list_all(self) -> list[dict[str, Any]]:
        """列出所有编排任务。"""
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM workflows ORDER BY group_name, name").fetchall()
        result = [dict(row) for row in rows]
        for item in result:
            item["enabled"] = bool(item["enabled"])
            item["trigger_config"] = _load_json(item.pop("trigger_config_json"), {})
            item["priority"] = int(item.get("priority") or 0)
            item["success_interval_seconds"] = float(item.get("success_interval_seconds") or 0)
            item["failure_interval_seconds"] = float(item.get("failure_interval_seconds") or 0)
        return result

    def get(self, workflow_id: int) -> dict[str, Any] | None:
        """按主键读取编排任务。"""
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        item = _row_to_dict(row)
        if item is not None:
            item["enabled"] = bool(item["enabled"])
            item["trigger_config"] = _load_json(item.pop("trigger_config_json"), {})
            item["priority"] = int(item.get("priority") or 0)
            item["success_interval_seconds"] = float(item.get("success_interval_seconds") or 0)
            item["failure_interval_seconds"] = float(item.get("failure_interval_seconds") or 0)
        return item

    def update(
        self,
        workflow_id: int,
        name: str,
        group_name: str,
        enabled: bool,
        trigger_type: str,
        trigger_config: dict[str, Any],
        failure_policy: str,
        priority: int = 0,
        success_interval_seconds: float = 0,
        failure_interval_seconds: float = 0,
    ) -> bool:
        """更新编排任务，返回是否找到并更新。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                UPDATE workflows
                SET name=?, group_name=?, enabled=?, trigger_type=?, trigger_config_json=?,
                    failure_policy=?, priority=?, success_interval_seconds=?,
                    failure_interval_seconds=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    name,
                    group_name,
                    1 if enabled else 0,
                    trigger_type,
                    json.dumps(trigger_config, ensure_ascii=False),
                    failure_policy,
                    int(priority),
                    float(success_interval_seconds),
                    float(failure_interval_seconds),
                    workflow_id,
                ),
            )
            return cur.rowcount > 0

    def update_with_steps(
        self,
        workflow_id: int,
        name: str,
        group_name: str,
        enabled: bool,
        trigger_type: str,
        trigger_config: dict[str, Any],
        failure_policy: str,
        steps: list[dict[str, Any]],
        priority: int = 0,
        success_interval_seconds: float = 0,
        failure_interval_seconds: float = 0,
    ) -> bool:
        """单事务内全量覆盖编排任务及其步骤，返回是否找到并更新。

        若任一写操作失败，整个事务回滚，保证 workflow 元数据与 steps 同步。
        """
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                UPDATE workflows
                SET name=?, group_name=?, enabled=?, trigger_type=?, trigger_config_json=?,
                    failure_policy=?, priority=?, success_interval_seconds=?,
                    failure_interval_seconds=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    name,
                    group_name,
                    1 if enabled else 0,
                    trigger_type,
                    json.dumps(trigger_config, ensure_ascii=False),
                    failure_policy,
                    int(priority),
                    float(success_interval_seconds),
                    float(failure_interval_seconds),
                    workflow_id,
                ),
            )
            if cur.rowcount == 0:
                return False
            conn.execute("DELETE FROM workflow_steps WHERE workflow_id=?", (workflow_id,))
            for step in steps:
                conn.execute(
                    """
                    INSERT INTO workflow_steps
                        (workflow_id, sort_order, step_type, script_id, config_json,
                         condition_json, retry_count, failure_policy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workflow_id,
                        int(step["sort_order"]),
                        str(step["step_type"]),
                        None if step.get("script_id") is None else str(step.get("script_id")),
                        json.dumps(dict(step.get("config", {})), ensure_ascii=False),
                        json.dumps(dict(step.get("condition", {})), ensure_ascii=False),
                        int(step.get("retry_count", 0)),
                        str(step.get("failure_policy", "inherit")),
                    ),
                )
            return True

    def delete(self, workflow_id: int) -> bool:
        """按主键删除编排任务，返回是否找到并删除。"""
        with self.db.connect() as conn:
            cur = conn.execute("DELETE FROM workflows WHERE id=?", (workflow_id,))
            return cur.rowcount > 0

    def has_active_run(self, workflow_id: int) -> bool:
        """检查是否存在与该编排关联的活动运行。"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM runs WHERE workflow_id=? AND status IN ('queued','running','paused') LIMIT 1",
                (workflow_id,),
            ).fetchone()
        return row is not None

    def update_schedule_state(
        self,
        workflow_id: int,
        next_run_at: str | None,
        last_run_at: str | None = None,
    ) -> bool:
        """更新调度预览状态。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                UPDATE workflows
                SET next_run_at=?,
                    last_run_at=COALESCE(?, last_run_at),
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (next_run_at, last_run_at, workflow_id),
            )
            return cur.rowcount > 0


class WorkflowStepRepository:
    """编排步骤仓库。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        workflow_id: int,
        sort_order: int,
        step_type: str,
        script_id: str | None,
        config: dict[str, Any],
        condition: dict[str, Any],
        retry_count: int,
        failure_policy: str = "inherit",
    ) -> int:
        """创建编排步骤并返回主键。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO workflow_steps
                    (workflow_id, sort_order, step_type, script_id, config_json,
                     condition_json, retry_count, failure_policy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow_id,
                    sort_order,
                    step_type,
                    script_id,
                    json.dumps(config, ensure_ascii=False),
                    json.dumps(condition, ensure_ascii=False),
                    retry_count,
                    failure_policy,
                ),
            )
            return int(cur.lastrowid)

    def list_by_workflow(self, workflow_id: int) -> list[dict[str, Any]]:
        """按编排任务列出步骤。"""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM workflow_steps WHERE workflow_id = ? ORDER BY sort_order",
                (workflow_id,),
            ).fetchall()
        result = [dict(row) for row in rows]
        for item in result:
            item["config"] = _load_json(item.pop("config_json"), {})
            item["condition"] = _load_json(item.pop("condition_json"), {})
            item["failure_policy"] = str(item.get("failure_policy") or "inherit")
        return result

    def delete_by_workflow(self, workflow_id: int) -> int:
        """删除某编排任务下的全部步骤，返回删除条数。"""
        with self.db.connect() as conn:
            cur = conn.execute("DELETE FROM workflow_steps WHERE workflow_id=?", (workflow_id,))
            return int(cur.rowcount)


class RunRepository:
    """运行记录仓库。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        script_id: str,
        source_type: RunSourceType,
        config: dict[str, Any],
        workflow_id: int | None = None,
        workflow_step_id: int | None = None,
        task_id: str | None = None,
        step_id: int | None = None,
        action_id: str | None = None,
        retry_count: int = 0,
        parent_run_id: int | None = None,
    ) -> int:
        """创建 run 记录并返回主键。

        parent_run_id：关联重试的来源 run（AC12），旧库迁移后为 NULL。
        """
        run_uuid = str(uuid.uuid4())
        resolved_step_id = step_id if step_id is not None else workflow_step_id
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO runs
                    (run_uuid, script_id, task_id, source_type, workflow_id,
                     workflow_step_id, step_id, action_id, status, stage,
                     progress_json, config_json, retry_count, available_actions_json,
                     parent_run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_uuid,
                    script_id,
                    task_id,
                    source_type.value,
                    workflow_id,
                    workflow_step_id,
                    resolved_step_id,
                    action_id,
                    RunStatus.QUEUED.value,
                    RunStatus.QUEUED.value,
                    json.dumps({}, ensure_ascii=False),
                    json.dumps(config, ensure_ascii=False),
                    retry_count,
                    json.dumps(available_actions_for_status(RunStatus.QUEUED), ensure_ascii=False),
                    parent_run_id,
                ),
            )
            return int(cur.lastrowid)

    def update_status(
        self,
        run_id: int,
        status: RunStatus,
        error_message: str | None = None,
        error_code: str | None = None,
        stage: str | None = None,
        progress: dict[str, Any] | None = None,
        available_actions: list[str] | None = None,
    ) -> None:
        """更新 run 状态和规范化运行观察字段。"""
        started_expr = "COALESCE(started_at, CURRENT_TIMESTAMP)" if status == RunStatus.RUNNING else "started_at"
        ended_expr = (
            "COALESCE(ended_at, CURRENT_TIMESTAMP)"
            if status
            in {
                RunStatus.SUCCESS,
                RunStatus.ERROR,
                RunStatus.STOPPED,
                RunStatus.SKIPPED,
                RunStatus.MANUAL,
            }
            else "ended_at"
        )
        values: list[Any] = [status.value, error_message, error_code]
        assignments = [
            "status = ?",
            "error_message = ?",
            "error_code = ?",
            f"started_at = {started_expr}",
            f"ended_at = {ended_expr}",
            "stage = COALESCE(?, stage)",
            "progress_json = COALESCE(?, progress_json)",
            "available_actions_json = COALESCE(?, available_actions_json)",
            "updated_at = CURRENT_TIMESTAMP",
        ]
        values.extend(
            [
                stage,
                json.dumps(progress, ensure_ascii=False) if progress is not None else None,
                json.dumps(
                    available_actions
                    if available_actions is not None
                    else available_actions_for_run(status, stage),
                    ensure_ascii=False,
                ),
            ]
        )
        values.append(run_id)
        with self.db.connect() as conn:
            conn.execute(
                f"""
                UPDATE runs
                SET {', '.join(assignments)}
                WHERE id = ?
                """,
                values,
            )

    def update_observation(
        self,
        run_id: int,
        stage: str | None = None,
        progress: dict[str, Any] | None = None,
    ) -> None:
        """更新运行阶段和进度，不改变终态。"""
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET stage = COALESCE(?, stage),
                    progress_json = COALESCE(?, progress_json),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    stage,
                    json.dumps(progress, ensure_ascii=False) if progress is not None else None,
                    run_id,
                ),
            )

    def set_latest_evidence(self, run_id: int, evidence: dict[str, Any]) -> None:
        """关联某次运行的最新证据摘要。"""
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE runs SET latest_evidence_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (json.dumps(evidence, ensure_ascii=False), run_id),
            )

    def mark_unfinished_as_error(self, message: str) -> int:
        """将后端重启前遗留的未完成 run 标记为错误，并返回数量。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                UPDATE runs
                SET status = ?,
                    ended_at = COALESCE(ended_at, CURRENT_TIMESTAMP),
                    error_code = ?,
                    error_message = ?,
                    stage = ?,
                    available_actions_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status IN (?, ?, ?)
                """,
                (
                    RunStatus.ERROR.value,
                    "BACKEND_RESTART",
                    message,
                    "backend_restarted",
                    json.dumps(available_actions_for_status(RunStatus.ERROR), ensure_ascii=False),
                    RunStatus.QUEUED.value,
                    RunStatus.RUNNING.value,
                    RunStatus.PAUSED.value,
                ),
            )
            return int(cur.rowcount)

    def get(self, run_id: int) -> dict[str, Any] | None:
        """按主键读取 run。"""
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._normalize(row)

    def current(self) -> dict[str, Any] | None:
        """读取当前运行中的 run。"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE status IN ('queued', 'running', 'paused') ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return self._normalize(row)

    def list_history(
        self,
        script_id: str | None = None,
        source_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """按筛选条件列出历史运行摘要。"""
        clauses: list[str] = []
        values: list[Any] = []
        if script_id:
            clauses.append("script_id = ?")
            values.append(script_id)
        if source_type:
            clauses.append("source_type = ?")
            values.append(source_type)
        if status:
            clauses.append("status = ?")
            values.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        bounded_limit = max(1, min(int(limit), 200))
        bounded_offset = max(0, int(offset))
        values.extend([bounded_limit, bounded_offset])
        with self.db.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM runs {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                values,
            ).fetchall()
        return [item for row in rows if (item := self._normalize(row)) is not None]

    def _normalize(self, row: Any) -> dict[str, Any] | None:
        """把数据库行转换为兼容的规范化运行快照。"""
        item = _row_to_dict(row)
        if item is None:
            return None
        item["config"] = _load_json(item.pop("config_json"), {})
        item["progress"] = _load_json(item.pop("progress_json", "{}"), {})
        item["available_actions"] = _load_json(
            item.pop("available_actions_json", "[]"),
            available_actions_for_run(
                str(item.get("status", "")), str(item.get("stage", "") or None)
            ),
        )
        latest_evidence = item.pop("latest_evidence_json", None)
        item["latest_evidence"] = _load_json(latest_evidence, None)
        item["run_id"] = int(item["id"])
        item["step_id"] = item.get("step_id") or item.get("workflow_step_id")
        item["task_id"] = item.get("task_id") or item.get("script_id")
        return item


class LogRepository:
    """运行日志仓库。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def append(self, run_id: int, level: str, message: str) -> int:
        """追加运行日志。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO run_logs (run_id, level, message) VALUES (?, ?, ?)",
                (run_id, level, message),
            )
            return int(cur.lastrowid)

    def list_by_run(self, run_id: int) -> list[dict[str, Any]]:
        """读取某次运行的日志。"""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM run_logs WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]


class EvidenceRepository:
    """运行失败证据仓库。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def append(
        self,
        run_id: int,
        kind: str,
        path: str | None = None,
        description: str = "",
        capture_error: str | None = None,
    ) -> int:
        """追加截图或证据捕获结果。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO run_evidence (run_id, kind, path, description, capture_error)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, kind, path, description, capture_error),
            )
            return int(cur.lastrowid)

    def list_by_run(self, run_id: int) -> list[dict[str, Any]]:
        """列出某次运行的全部证据。"""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM run_evidence WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_by_run(self, run_id: int) -> dict[str, Any] | None:
        """读取某次运行的最新证据。"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM run_evidence WHERE run_id = ? ORDER BY id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        return _row_to_dict(row)


class SnapshotRepository:
    """状态快照仓库。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def append(self, run_id: int, script_id: str, state: dict[str, Any]) -> int:
        """追加状态快照。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO state_snapshots (run_id, script_id, state_json) VALUES (?, ?, ?)",
                (run_id, script_id, json.dumps(state, ensure_ascii=False)),
            )
            return int(cur.lastrowid)

    def latest_by_run(self, run_id: int) -> dict[str, Any] | None:
        """读取某次运行的最新快照。"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM state_snapshots WHERE run_id = ? ORDER BY id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        item = _row_to_dict(row)
        if item is None:
            return None
        item["state"] = json.loads(item.pop("state_json"))
        return item

    def list_by_run(self, run_id: int) -> list[dict[str, Any]]:
        """按时间顺序读取某次运行的全部状态快照。"""
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM state_snapshots WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["state"] = _load_json(item.pop("state_json"), {})
            result.append(item)
        return result


class ScriptUserConfigRepository:
    """脚本用户最近一次配置仓库。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self, script_id: str) -> dict[str, Any] | None:
        """读取脚本的用户配置，序列化后的 dict。"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT config_json FROM script_user_configs WHERE script_id = ?",
                (script_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["config_json"])

    def upsert(self, script_id: str, config: dict[str, Any]) -> None:
        """写入或更新脚本的用户配置。"""
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO script_user_configs (script_id, config_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(script_id) DO UPDATE SET
                    config_json = excluded.config_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (script_id, json.dumps(config, ensure_ascii=False)),
            )


class Storage:
    """所有仓库的聚合入口。"""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.workflows = WorkflowRepository(db)
        self.workflow_steps = WorkflowStepRepository(db)
        self.runs = RunRepository(db)
        self.logs = LogRepository(db)
        self.snapshots = SnapshotRepository(db)
        self.evidence = EvidenceRepository(db)
        self.script_user_configs = ScriptUserConfigRepository(db)
