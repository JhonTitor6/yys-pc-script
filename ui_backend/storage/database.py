from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Database:
    """SQLite 数据库连接工厂。"""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """创建一个启用外键和 Row 工厂的连接。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """初始化桌面工作台数据库表。"""
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    trigger_type TEXT NOT NULL,
                    trigger_config_json TEXT NOT NULL,
                    failure_policy TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    success_interval_seconds REAL NOT NULL DEFAULT 0,
                    failure_interval_seconds REAL NOT NULL DEFAULT 0,
                    next_run_at TEXT,
                    last_run_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS workflow_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id INTEGER NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
                    sort_order INTEGER NOT NULL,
                    step_type TEXT NOT NULL,
                    script_id TEXT,
                    config_json TEXT NOT NULL,
                    condition_json TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    failure_policy TEXT NOT NULL DEFAULT 'inherit'
                );

                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_uuid TEXT NOT NULL DEFAULT '',
                    script_id TEXT NOT NULL,
                    task_id TEXT,
                    source_type TEXT NOT NULL,
                    workflow_id INTEGER REFERENCES workflows(id) ON DELETE SET NULL,
                    workflow_step_id INTEGER REFERENCES workflow_steps(id) ON DELETE SET NULL,
                    step_id INTEGER,
                    action_id TEXT,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL DEFAULT 'queued',
                    progress_json TEXT NOT NULL DEFAULT '{}',
                    config_json TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    available_actions_json TEXT NOT NULL DEFAULT '[]',
                    latest_evidence_json TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS run_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS state_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    script_id TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS run_evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    path TEXT,
                    description TEXT NOT NULL DEFAULT '',
                    capture_error TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS script_user_configs (
                    script_id TEXT PRIMARY KEY,
                    config_json TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            self._ensure_columns(
                conn,
                "workflows",
                {
                    "priority": "INTEGER NOT NULL DEFAULT 0",
                    "success_interval_seconds": "REAL NOT NULL DEFAULT 0",
                    "failure_interval_seconds": "REAL NOT NULL DEFAULT 0",
                    "next_run_at": "TEXT",
                    "last_run_at": "TEXT",
                },
            )
            self._ensure_columns(
                conn,
                "workflow_steps",
                {
                    "failure_policy": "TEXT NOT NULL DEFAULT 'inherit'",
                },
            )
            self._ensure_columns(
                conn,
                "runs",
                {
                    "run_uuid": "TEXT NOT NULL DEFAULT ''",
                    "task_id": "TEXT",
                    "step_id": "INTEGER",
                    "action_id": "TEXT",
                    "stage": "TEXT NOT NULL DEFAULT 'queued'",
                    "progress_json": "TEXT NOT NULL DEFAULT '{}'",
                    "error_code": "TEXT",
                    "retry_count": "INTEGER NOT NULL DEFAULT 0",
                    "available_actions_json": "TEXT NOT NULL DEFAULT '[]'",
                    "latest_evidence_json": "TEXT",
                    "updated_at": "TEXT",
                },
            )
            conn.execute(
                "UPDATE runs SET run_uuid = CAST(id AS TEXT) WHERE run_uuid = '' OR run_uuid IS NULL"
            )
            conn.execute(
                "UPDATE runs SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"
            )

    @staticmethod
    def _ensure_columns(
        conn: sqlite3.Connection,
        table: str,
        columns: dict[str, str],
    ) -> None:
        """为已有数据库幂等补齐新增列。"""
        existing = {
            str(row[1])
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
