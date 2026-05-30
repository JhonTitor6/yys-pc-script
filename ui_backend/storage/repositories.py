from __future__ import annotations

import json
from typing import Any

from ui_backend.models import RunSourceType, RunStatus
from ui_backend.storage.database import Database


def _row_to_dict(row: Any) -> dict[str, Any] | None:
    """将 sqlite Row 转为 dict。"""
    if row is None:
        return None
    return dict(row)


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
    ) -> int:
        """创建编排任务并返回主键。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO workflows
                    (name, group_name, enabled, trigger_type, trigger_config_json, failure_policy)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    group_name,
                    1 if enabled else 0,
                    trigger_type,
                    json.dumps(trigger_config, ensure_ascii=False),
                    failure_policy,
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
            item["trigger_config"] = json.loads(item.pop("trigger_config_json"))
        return result

    def get(self, workflow_id: int) -> dict[str, Any] | None:
        """按主键读取编排任务。"""
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        item = _row_to_dict(row)
        if item is not None:
            item["enabled"] = bool(item["enabled"])
            item["trigger_config"] = json.loads(item.pop("trigger_config_json"))
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
    ) -> bool:
        """更新编排任务，返回是否找到并更新。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                "UPDATE workflows SET name=?, group_name=?, enabled=?, trigger_type=?, trigger_config_json=?, failure_policy=? WHERE id=?",
                (
                    name,
                    group_name,
                    1 if enabled else 0,
                    trigger_type,
                    json.dumps(trigger_config, ensure_ascii=False),
                    failure_policy,
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
    ) -> bool:
        """单事务内全量覆盖编排任务及其步骤，返回是否找到并更新。

        若任一写操作失败，整个事务回滚，保证 workflow 元数据与 steps 同步。
        """
        with self.db.connect() as conn:
            cur = conn.execute(
                "UPDATE workflows SET name=?, group_name=?, enabled=?, trigger_type=?, trigger_config_json=?, failure_policy=? WHERE id=?",
                (
                    name,
                    group_name,
                    1 if enabled else 0,
                    trigger_type,
                    json.dumps(trigger_config, ensure_ascii=False),
                    failure_policy,
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
                        (workflow_id, sort_order, step_type, script_id, config_json, condition_json, retry_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        workflow_id,
                        int(step["sort_order"]),
                        str(step["step_type"]),
                        None if step.get("script_id") is None else str(step.get("script_id")),
                        json.dumps(dict(step.get("config", {})), ensure_ascii=False),
                        json.dumps(dict(step.get("condition", {})), ensure_ascii=False),
                        int(step.get("retry_count", 0)),
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
    ) -> int:
        """创建编排步骤并返回主键。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO workflow_steps
                    (workflow_id, sort_order, step_type, script_id, config_json, condition_json, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow_id,
                    sort_order,
                    step_type,
                    script_id,
                    json.dumps(config, ensure_ascii=False),
                    json.dumps(condition, ensure_ascii=False),
                    retry_count,
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
            item["config"] = json.loads(item.pop("config_json"))
            item["condition"] = json.loads(item.pop("condition_json"))
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
    ) -> int:
        """创建 run 记录并返回主键。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO runs
                    (script_id, source_type, workflow_id, workflow_step_id, status, config_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    script_id,
                    source_type.value,
                    workflow_id,
                    workflow_step_id,
                    RunStatus.QUEUED.value,
                    json.dumps(config, ensure_ascii=False),
                ),
            )
            return int(cur.lastrowid)

    def update_status(self, run_id: int, status: RunStatus, error_message: str | None = None) -> None:
        """更新 run 状态。"""
        started_expr = "COALESCE(started_at, CURRENT_TIMESTAMP)" if status == RunStatus.RUNNING else "started_at"
        ended_expr = (
            "COALESCE(ended_at, CURRENT_TIMESTAMP)"
            if status in {RunStatus.SUCCESS, RunStatus.ERROR, RunStatus.STOPPED}
            else "ended_at"
        )
        with self.db.connect() as conn:
            conn.execute(
                f"""
                UPDATE runs
                SET status = ?, started_at = {started_expr}, ended_at = {ended_expr}, error_message = ?
                WHERE id = ?
                """,
                (status.value, error_message, run_id),
            )

    def mark_unfinished_as_error(self, message: str) -> int:
        """将后端重启前遗留的未完成 run 标记为错误，并返回数量。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                UPDATE runs
                SET status = ?,
                    ended_at = COALESCE(ended_at, CURRENT_TIMESTAMP),
                    error_message = ?
                WHERE status IN (?, ?, ?)
                """,
                (
                    RunStatus.ERROR.value,
                    message,
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
        item = _row_to_dict(row)
        if item is not None:
            item["config"] = json.loads(item.pop("config_json"))
        return item

    def current(self) -> dict[str, Any] | None:
        """读取当前运行中的 run。"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE status IN ('queued', 'running', 'paused') ORDER BY id DESC LIMIT 1"
            ).fetchone()
        item = _row_to_dict(row)
        if item is not None:
            item["config"] = json.loads(item.pop("config_json"))
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
        self.script_user_configs = ScriptUserConfigRepository(db)
