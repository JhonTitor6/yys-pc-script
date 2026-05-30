# 阴阳师脚本桌面工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Electron 本地桌面工作台，用于单脚本执行、脚本编排、实时日志、历史记录和进度快照展示。

**Architecture:** Electron 负责桌面窗口、托盘和 Python 后端进程管理；Python 后端拆为 `ui_backend/` 模块，提供 FastAPI HTTP 接口、WebSocket 事件、SQLite 持久化、脚本注册、单执行槽和调度器。前端采用无构建的 HTML/CSS/JS 控制台工作台风格，复用现有 Electron 壳但重写 UI 文件。

**Tech Stack:** Python 3.11、FastAPI、uvicorn、sqlite3、pytest、Electron、原生 HTML/CSS/JavaScript、WebSocket。

---

## 设计来源

- 设计规格：`docs/specs/2026-05-30-yys-desktop-workbench-design.md`
- 现有后端雏形：`web_server.py`
- 现有桌面壳：`gui/main.js`、`gui/preload.js`、`gui/index.html`
- 脚本生命周期基类：`win_util/event.py`、`yys/common/event_script_base.py`

## 文件结构

新增后端模块：

```text
ui_backend/
├── __init__.py
├── app.py                  # FastAPI 应用工厂和路由挂载
├── main.py                 # uvicorn 入口
├── models.py               # dataclass / TypedDict / 枚举
├── events/
│   ├── __init__.py
│   └── hub.py              # WebSocket 连接和事件广播
├── scripts/
│   ├── __init__.py
│   ├── registry.py         # 脚本注册和 schema 合并
│   └── default_registry.py # 第一版脚本注册表
├── runs/
│   ├── __init__.py
│   └── manager.py          # 单执行槽和脚本线程生命周期
├── scheduler/
│   ├── __init__.py
│   └── service.py          # 编排步骤推进和触发检查
└── storage/
    ├── __init__.py
    ├── database.py         # SQLite 连接、建表、事务
    └── repositories.py     # workflow/run/log/snapshot 仓库
```

新增测试：

```text
tests/ui_backend/
├── __init__.py
├── test_storage.py
├── test_script_registry.py
├── test_run_manager.py
├── test_scheduler.py
└── test_app_api.py
```

修改现有文件：

```text
requirements.txt            # 补齐 FastAPI 和 uvicorn
web_server.py               # 兼容入口，转调 ui_backend.main
yys/common/event_script_base.py
gui/main.js
gui/preload.js
gui/index.html
```

---

## Task 1: 建立后端依赖和包骨架

**Files:**
- Modify: `requirements.txt`
- Create: `ui_backend/__init__.py`
- Create: `ui_backend/models.py`
- Create: `ui_backend/main.py`
- Create: `tests/ui_backend/__init__.py`

- [ ] **Step 1: 补齐依赖**

在 `requirements.txt` 末尾加入：

```text
fastapi>=0.115.0,<1.0.0
uvicorn[standard]>=0.30.0,<1.0.0
```

- [ ] **Step 2: 创建后端包**

创建 `ui_backend/__init__.py`：

```python
"""桌面工作台后端模块。"""
```

创建 `tests/ui_backend/__init__.py`：

```python
"""桌面工作台后端测试。"""
```

- [ ] **Step 3: 定义共享模型**

创建 `ui_backend/models.py`：

```python
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
```

- [ ] **Step 4: 创建后端入口**

创建 `ui_backend/main.py`：

```python
from __future__ import annotations

import uvicorn


def main() -> None:
    """启动桌面工作台后端服务。"""
    uvicorn.run("ui_backend.app:create_app", factory=True, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 验证导入**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -c "from ui_backend.models import RunStatus; print(RunStatus.RUNNING.value)"
```

Expected:

```text
running
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt ui_backend/__init__.py ui_backend/models.py ui_backend/main.py tests/ui_backend/__init__.py
git commit -m "搭建桌面工作台后端包骨架"
```

---

## Task 2: 实现 SQLite 初始化和仓库

**Files:**
- Create: `ui_backend/storage/__init__.py`
- Create: `ui_backend/storage/database.py`
- Create: `ui_backend/storage/repositories.py`
- Test: `tests/ui_backend/test_storage.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/ui_backend/test_storage.py`：

```python
from __future__ import annotations

from pathlib import Path

from ui_backend.models import RunSourceType, RunStatus
from ui_backend.storage.database import Database
from ui_backend.storage.repositories import Storage


def test_storage_creates_workflow_run_log_and_snapshot(tmp_path: Path) -> None:
    db = Database(tmp_path / "ui.db")
    db.initialize()
    storage = Storage(db)

    workflow_id = storage.workflows.create(
        name="日常",
        group_name="默认",
        enabled=True,
        trigger_type="manual",
        trigger_config={},
        failure_policy="stop_workflow",
    )
    step_id = storage.workflow_steps.create(
        workflow_id=workflow_id,
        sort_order=1,
        step_type="run_script",
        script_id="soul_raid",
        config={"max_battle_count": 103},
        condition={},
        retry_count=0,
    )
    run_id = storage.runs.create(
        script_id="soul_raid",
        source_type=RunSourceType.WORKFLOW,
        config={"max_battle_count": 103},
        workflow_id=workflow_id,
        workflow_step_id=step_id,
    )

    storage.runs.update_status(run_id, RunStatus.RUNNING)
    storage.logs.append(run_id, "INFO", "开始运行")
    storage.snapshots.append(run_id, "soul_raid", {"battle_count": 1})

    run = storage.runs.get(run_id)
    assert run is not None
    assert run["status"] == "running"
    assert run["workflow_id"] == workflow_id
    assert storage.logs.list_by_run(run_id)[0]["message"] == "开始运行"
    assert storage.snapshots.latest_by_run(run_id)["state"]["battle_count"] == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_storage.py -v
```

Expected: FAIL，错误包含 `No module named 'ui_backend.storage'`。

- [ ] **Step 3: 创建 SQLite 连接和 schema**

创建 `ui_backend/storage/__init__.py`：

```python
"""SQLite 持久化模块。"""
```

创建 `ui_backend/storage/database.py`：

```python
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class Database:
    """SQLite 数据库连接工厂。"""

    def __init__(self, path: Path | str):
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
                    retry_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    script_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    workflow_id INTEGER REFERENCES workflows(id) ON DELETE SET NULL,
                    workflow_step_id INTEGER REFERENCES workflow_steps(id) ON DELETE SET NULL,
                    status TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT,
                    error_message TEXT
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

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                );
                """
            )
```

- [ ] **Step 4: 创建仓库实现**

创建 `ui_backend/storage/repositories.py`：

```python
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

    def __init__(self, db: Database):
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


class WorkflowStepRepository:
    """编排步骤仓库。"""

    def __init__(self, db: Database):
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


class RunRepository:
    """运行记录仓库。"""

    def __init__(self, db: Database):
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
        started_expr = "CURRENT_TIMESTAMP" if status == RunStatus.RUNNING else "started_at"
        ended_expr = "CURRENT_TIMESTAMP" if status in {RunStatus.SUCCESS, RunStatus.ERROR, RunStatus.STOPPED} else "ended_at"
        with self.db.connect() as conn:
            conn.execute(
                f"""
                UPDATE runs
                SET status = ?, started_at = {started_expr}, ended_at = {ended_expr}, error_message = ?
                WHERE id = ?
                """,
                (status.value, error_message, run_id),
            )

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

    def __init__(self, db: Database):
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

    def __init__(self, db: Database):
        self.db = db

    def append(self, run_id: int, script_id: str, state: dict[str, Any]) -> int:
        """追加状态快照。"""
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO state_snapshots (run_id, script_id, state_json) VALUES (?, ?, ?)",
                (run_id, script_id, json.dumps(state, ensure_ascii=False)),
            )
            return int(cur.lastrowid)

    def latest_by_run(self, run_id: int) -> dict[str, Any]:
        """读取某次运行的最新快照。"""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM state_snapshots WHERE run_id = ? ORDER BY id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        item = dict(row)
        item["state"] = json.loads(item.pop("state_json"))
        return item


class Storage:
    """所有仓库的聚合入口。"""

    def __init__(self, db: Database):
        self.db = db
        self.workflows = WorkflowRepository(db)
        self.workflow_steps = WorkflowStepRepository(db)
        self.runs = RunRepository(db)
        self.logs = LogRepository(db)
        self.snapshots = SnapshotRepository(db)
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_storage.py -v
```

Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add ui_backend/storage tests/ui_backend/test_storage.py
git commit -m "实现桌面工作台SQLite持久化"
```

---

## Task 3: 实现脚本注册表和参数 schema

**Files:**
- Create: `ui_backend/scripts/__init__.py`
- Create: `ui_backend/scripts/default_registry.py`
- Create: `ui_backend/scripts/registry.py`
- Test: `tests/ui_backend/test_script_registry.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/ui_backend/test_script_registry.py`：

```python
from __future__ import annotations

from ui_backend.models import ScriptCategory
from ui_backend.scripts.registry import ScriptRegistry


class ScriptWithSchema:
    """用于验证类内 schema 优先级的脚本。"""

    @classmethod
    def get_config_schema(cls) -> list[dict[str, object]]:
        return [
            {
                "key": "max_battle_count",
                "label": "类内次数",
                "field_type": "number",
                "default": 12,
                "min_value": 1,
                "max_value": 999,
            }
        ]


def test_registry_lists_stable_and_experimental_scripts() -> None:
    registry = ScriptRegistry()

    scripts = registry.list_scripts()
    script_ids = {item.script_id for item in scripts}

    assert "soul_raid" in script_ids
    assert "abyss_shadows" in script_ids
    assert registry.get("soul_raid").category == ScriptCategory.STABLE
    assert registry.get("abyss_shadows").category == ScriptCategory.EXPERIMENTAL


def test_class_schema_overrides_registry_schema() -> None:
    registry = ScriptRegistry(
        entries=[
            {
                "script_id": "custom",
                "display_name": "自定义",
                "module_path": "tests.ui_backend.test_script_registry",
                "class_name": "ScriptWithSchema",
                "category": "stable",
                "description": "测试脚本",
                "config_schema": [
                    {
                        "key": "max_battle_count",
                        "label": "注册表次数",
                        "field_type": "number",
                        "default": 99,
                    }
                ],
            }
        ]
    )

    definition = registry.get("custom")

    assert definition.config_schema[0].label == "类内次数"
    assert definition.default_config["max_battle_count"] == 12
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_script_registry.py -v
```

Expected: FAIL，错误包含 `No module named 'ui_backend.scripts'`。

- [ ] **Step 3: 创建默认注册表**

创建 `ui_backend/scripts/__init__.py`：

```python
"""脚本注册模块。"""
```

创建 `ui_backend/scripts/default_registry.py`：

```python
from __future__ import annotations

DEFAULT_SCRIPT_ENTRIES: list[dict[str, object]] = [
    {
        "script_id": "soul_raid",
        "display_name": "御魂",
        "module_path": "yys.soul_raid",
        "class_name": "SoulRaidScript",
        "category": "stable",
        "description": "御魂挂机",
        "config_schema": [
            {
                "key": "max_battle_count",
                "label": "战斗次数",
                "field_type": "number",
                "default": 103,
                "min_value": 1,
                "max_value": 999,
            },
            {
                "key": "loop_interval",
                "label": "循环间隔（秒）",
                "field_type": "number",
                "default": 5,
                "min_value": 1,
                "max_value": 120,
            },
        ],
    },
    {
        "script_id": "realm_raid",
        "display_name": "结界突破",
        "module_path": "yys.realm_raid",
        "class_name": "RealmRaidScript",
        "category": "stable",
        "description": "结界突破自动挑战",
        "config_schema": [
            {"key": "max_battle_count", "label": "挑战次数", "field_type": "number", "default": 9, "min_value": 1, "max_value": 99}
        ],
    },
    {
        "script_id": "exploration_28",
        "display_name": "探28",
        "module_path": "yys.exploration",
        "class_name": "ExplorationScript",
        "category": "stable",
        "description": "章节探索挂机",
        "config_schema": [
            {"key": "max_battle_count", "label": "战斗次数", "field_type": "number", "default": 200, "min_value": 1, "max_value": 999}
        ],
    },
    {
        "script_id": "yuling",
        "display_name": "御灵",
        "module_path": "yys.yuling",
        "class_name": "AutoYuling",
        "category": "stable",
        "description": "御灵副本挂机",
        "config_schema": [
            {"key": "max_battle_count", "label": "战斗次数", "field_type": "number", "default": 50, "min_value": 1, "max_value": 999}
        ],
    },
    {
        "script_id": "abyss_shadows",
        "display_name": "狭间暗域",
        "module_path": "yys.abyss_shadows.abyss_shadows_script",
        "class_name": "Main",
        "category": "experimental",
        "description": "狭间暗域挑战记录和自动挑战",
        "config_schema": [
            {"key": "boss_count", "label": "首领次数", "field_type": "number", "default": 2, "min_value": 0, "max_value": 4},
            {"key": "commander_count", "label": "副将次数", "field_type": "number", "default": 4, "min_value": 0, "max_value": 8},
            {"key": "elite_count", "label": "精英次数", "field_type": "number", "default": 6, "min_value": 0, "max_value": 12},
        ],
    },
]
```

- [ ] **Step 4: 创建 registry 实现**

创建 `ui_backend/scripts/registry.py`：

```python
from __future__ import annotations

import importlib
from typing import Any

from ui_backend.models import ConfigField, ScriptCategory, ScriptDefinition
from ui_backend.scripts.default_registry import DEFAULT_SCRIPT_ENTRIES


class ScriptRegistry:
    """脚本注册表，负责合并集中配置和类内 schema。"""

    def __init__(self, entries: list[dict[str, object]] | None = None):
        self._entries = entries or DEFAULT_SCRIPT_ENTRIES
        self._definitions = {item.script_id: item for item in self._load_definitions()}

    def list_scripts(self) -> list[ScriptDefinition]:
        """列出所有脚本定义。"""
        return list(self._definitions.values())

    def get(self, script_id: str) -> ScriptDefinition:
        """读取单个脚本定义。"""
        if script_id not in self._definitions:
            raise KeyError(f"未知脚本: {script_id}")
        return self._definitions[script_id]

    def load_class(self, script_id: str) -> type:
        """导入脚本类。"""
        definition = self.get(script_id)
        module = importlib.import_module(definition.module_path)
        script_class = getattr(module, definition.class_name)
        if not isinstance(script_class, type):
            raise TypeError(f"{script_id} 不是可实例化的脚本类")
        return script_class

    def _load_definitions(self) -> list[ScriptDefinition]:
        definitions: list[ScriptDefinition] = []
        for entry in self._entries:
            schema_items = self._schema_from_class(entry) or entry["config_schema"]
            schema = [self._parse_field(item) for item in schema_items]  # type: ignore[arg-type]
            default_config = {field.key: field.default for field in schema}
            definitions.append(
                ScriptDefinition(
                    script_id=str(entry["script_id"]),
                    display_name=str(entry["display_name"]),
                    module_path=str(entry["module_path"]),
                    class_name=str(entry["class_name"]),
                    category=ScriptCategory(str(entry["category"])),
                    description=str(entry["description"]),
                    config_schema=schema,
                    default_config=default_config,
                )
            )
        return definitions

    def _schema_from_class(self, entry: dict[str, object]) -> list[dict[str, Any]] | None:
        try:
            module = importlib.import_module(str(entry["module_path"]))
            script_class = getattr(module, str(entry["class_name"]))
        except Exception:
            return None
        get_schema = getattr(script_class, "get_config_schema", None)
        if get_schema is None:
            return None
        result = get_schema()
        if not isinstance(result, list):
            raise TypeError(f"{entry['script_id']} 的 get_config_schema 必须返回 list")
        return result

    @staticmethod
    def _parse_field(item: dict[str, Any]) -> ConfigField:
        """解析参数字段。"""
        return ConfigField(
            key=str(item["key"]),
            label=str(item["label"]),
            field_type=item["field_type"],
            default=item.get("default"),
            min_value=item.get("min_value"),
            max_value=item.get("max_value"),
            options=list(item.get("options", [])),
        )
```

- [ ] **Step 5: 运行测试确认通过**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_script_registry.py -v
```

Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add ui_backend/scripts tests/ui_backend/test_script_registry.py
git commit -m "实现桌面工作台脚本注册表"
```

---

## Task 4: 增加脚本状态快照接口

**Files:**
- Modify: `yys/common/event_script_base.py`
- Test: `tests/common/test_yys.py`

- [ ] **Step 1: 写失败测试**

在 `tests/common/test_yys.py` 追加：

```python
def test_base_script_state_snapshot(mock_env):
    from yys.soul_raid.soul_raid_script import SoulRaidScript

    script = SoulRaidScript(env=mock_env)
    script.set_max_battle_count(10)
    script._cur_battle_count = 3
    script._cur_battle_victory_count = 2

    snapshot = script.get_state_snapshot()

    assert snapshot["script_name"] == "soul_raid"
    assert snapshot["battle_count"] == 3
    assert snapshot["victory_count"] == 2
    assert snapshot["max_battle_count"] == 10
```

如果 `SoulRaidScript` 当前不接受 `env` 参数，则在本任务 Step 3 同步补上。

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_yys.py::test_base_script_state_snapshot -v
```

Expected: FAIL，错误包含 `get_state_snapshot` 不存在或 `SoulRaidScript.__init__` 不接受 `env`。

- [ ] **Step 3: 为基础脚本添加快照方法**

在 `yys/common/event_script_base.py` 的 `YYSBaseScript` 中添加：

```python
    def get_state_snapshot(self) -> dict[str, object]:
        """获取脚本当前状态快照，用于 UI 展示和历史记录。"""
        return {
            "script_name": self.script_name,
            "battle_count": self._cur_battle_count,
            "victory_count": self._cur_battle_victory_count,
            "max_battle_count": self._max_battle_count,
        }
```

如 `SoulRaidScript` 不支持测试注入，将 `yys/soul_raid/soul_raid_script.py` 中构造函数改为：

```python
    def __init__(self, env=None):
        super().__init__("soul_raid", env=env)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/test_yys.py::test_base_script_state_snapshot -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add yys/common/event_script_base.py yys/soul_raid/soul_raid_script.py tests/common/test_yys.py
git commit -m "增加脚本状态快照接口"
```

---

## Task 5: 实现事件广播中心

**Files:**
- Create: `ui_backend/events/__init__.py`
- Create: `ui_backend/events/hub.py`
- Test: `tests/ui_backend/test_app_api.py`

- [ ] **Step 1: 写事件中心测试**

创建或追加 `tests/ui_backend/test_app_api.py`：

```python
from __future__ import annotations

import pytest

from ui_backend.events.hub import EventHub


@pytest.mark.asyncio
async def test_event_hub_keeps_recent_events() -> None:
    hub = EventHub(max_recent_events=2)

    await hub.publish({"type": "log", "message": "第一条"})
    await hub.publish({"type": "log", "message": "第二条"})
    await hub.publish({"type": "log", "message": "第三条"})

    recent = hub.recent_events()
    assert [item["message"] for item in recent] == ["第二条", "第三条"]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_app_api.py::test_event_hub_keeps_recent_events -v
```

Expected: FAIL，错误包含 `No module named 'ui_backend.events'`。

- [ ] **Step 3: 创建事件中心**

创建 `ui_backend/events/__init__.py`：

```python
"""WebSocket 事件模块。"""
```

创建 `ui_backend/events/hub.py`：

```python
from __future__ import annotations

import asyncio
from collections import deque
from typing import Any

from fastapi import WebSocket


class EventHub:
    """负责保存近期事件并广播给 WebSocket 客户端。"""

    def __init__(self, max_recent_events: int = 200):
        self._connections: set[WebSocket] = set()
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=max_recent_events)
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, websocket: WebSocket) -> None:
        """接受并登记 WebSocket 连接。"""
        self._loop = asyncio.get_running_loop()
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        """移除 WebSocket 连接。"""
        async with self._lock:
            self._connections.discard(websocket)

    async def publish(self, event: dict[str, Any]) -> None:
        """保存并广播事件。"""
        self._recent_events.append(event)
        async with self._lock:
            targets = list(self._connections)
        for websocket in targets:
            try:
                await websocket.send_json(event)
            except Exception:
                await self.disconnect(websocket)

    def publish_from_thread(self, event: dict[str, Any]) -> None:
        """从脚本线程投递事件。"""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.publish(event), self._loop)

    def recent_events(self) -> list[dict[str, Any]]:
        """返回近期事件副本。"""
        return list(self._recent_events)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_app_api.py::test_event_hub_keeps_recent_events -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add ui_backend/events tests/ui_backend/test_app_api.py
git commit -m "实现桌面工作台事件广播中心"
```

---

## Task 6: 实现 RunManager 单执行槽

**Files:**
- Create: `ui_backend/runs/__init__.py`
- Create: `ui_backend/runs/manager.py`
- Test: `tests/ui_backend/test_run_manager.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/ui_backend/test_run_manager.py`：

```python
from __future__ import annotations

import time
from pathlib import Path

import pytest

from ui_backend.events.hub import EventHub
from ui_backend.models import RunRequest, RunStatus
from ui_backend.runs.manager import RunManager
from ui_backend.storage.database import Database
from ui_backend.storage.repositories import Storage


class FakeScript:
    """可控的测试脚本。"""

    def __init__(self) -> None:
        self._stopped = False
        self._paused = False
        self._max_battle_count = 3
        self._cur_battle_count = 0
        self._cur_battle_victory_count = 0

    def set_max_battle_count(self, value: int) -> "FakeScript":
        self._max_battle_count = value
        return self

    def run(self) -> None:
        while not self._stopped and self._cur_battle_count < self._max_battle_count:
            if not self._paused:
                self._cur_battle_count += 1
                self._cur_battle_victory_count += 1
            time.sleep(0.01)

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self._stopped = True

    def get_state_snapshot(self) -> dict[str, object]:
        return {
            "battle_count": self._cur_battle_count,
            "victory_count": self._cur_battle_victory_count,
            "max_battle_count": self._max_battle_count,
        }


class FakeRegistry:
    def load_class(self, script_id: str) -> type:
        assert script_id == "fake"
        return FakeScript


@pytest.fixture
def run_manager(tmp_path: Path) -> RunManager:
    db = Database(tmp_path / "ui.db")
    db.initialize()
    storage = Storage(db)
    return RunManager(storage=storage, registry=FakeRegistry(), event_hub=EventHub())


def test_run_manager_allows_only_one_active_run(run_manager: RunManager) -> None:
    first = run_manager.start(RunRequest(script_id="fake", config={"max_battle_count": 20}))

    with pytest.raises(RuntimeError, match="已有脚本正在运行"):
        run_manager.start(RunRequest(script_id="fake", config={"max_battle_count": 1}))

    run_manager.stop(first)


def test_run_manager_finishes_and_saves_snapshot(run_manager: RunManager) -> None:
    run_id = run_manager.start(RunRequest(script_id="fake", config={"max_battle_count": 2}))
    run_manager.wait(run_id, timeout=2)

    run = run_manager.storage.runs.get(run_id)
    snapshot = run_manager.storage.snapshots.latest_by_run(run_id)

    assert run["status"] == RunStatus.SUCCESS.value
    assert snapshot["state"]["battle_count"] == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_run_manager.py -v
```

Expected: FAIL，错误包含 `No module named 'ui_backend.runs'`。

- [ ] **Step 3: 创建 RunManager**

创建 `ui_backend/runs/__init__.py`：

```python
"""脚本运行管理模块。"""
```

创建 `ui_backend/runs/manager.py`：

```python
from __future__ import annotations

import threading
import traceback
from typing import Any

from ui_backend.events.hub import EventHub
from ui_backend.models import RunRequest, RunStatus
from ui_backend.scripts.registry import ScriptRegistry
from ui_backend.storage.repositories import Storage


class RunManager:
    """单客户端脚本运行管理器。"""

    def __init__(self, storage: Storage, registry: ScriptRegistry, event_hub: EventHub):
        self.storage = storage
        self.registry = registry
        self.event_hub = event_hub
        self._lock = threading.Lock()
        self._active_run_id: int | None = None
        self._active_script: Any | None = None
        self._threads: dict[int, threading.Thread] = {}

    def start(self, request: RunRequest) -> int:
        """启动脚本并返回 run_id。"""
        with self._lock:
            if self._active_run_id is not None:
                raise RuntimeError("已有脚本正在运行")
            run_id = self.storage.runs.create(
                script_id=request.script_id,
                source_type=request.source_type,
                config=request.config,
                workflow_id=request.workflow_id,
                workflow_step_id=request.workflow_step_id,
            )
            script_class = self.registry.load_class(request.script_id)
            script = script_class()
            self._apply_config(script, request.config)
            self._active_run_id = run_id
            self._active_script = script
            thread = threading.Thread(target=self._run_script, args=(run_id, request.script_id, script), daemon=True)
            self._threads[run_id] = thread
            self.storage.runs.update_status(run_id, RunStatus.RUNNING)
            self.storage.logs.append(run_id, "INFO", f"启动脚本 {request.script_id}")
            self._publish({"type": "run_status_changed", "run_id": run_id, "status": RunStatus.RUNNING.value})
            self._publish({"type": "log", "run_id": run_id, "level": "INFO", "message": f"启动脚本 {request.script_id}"})
            thread.start()
            return run_id

    def pause(self, run_id: int) -> None:
        """暂停当前脚本。"""
        with self._lock:
            self._ensure_active(run_id)
            self._active_script.pause()
            self.storage.runs.update_status(run_id, RunStatus.PAUSED)
            self._publish({"type": "run_status_changed", "run_id": run_id, "status": RunStatus.PAUSED.value})

    def resume(self, run_id: int) -> None:
        """恢复当前脚本。"""
        with self._lock:
            self._ensure_active(run_id)
            self._active_script.resume()
            self.storage.runs.update_status(run_id, RunStatus.RUNNING)
            self._publish({"type": "run_status_changed", "run_id": run_id, "status": RunStatus.RUNNING.value})

    def stop(self, run_id: int, timeout: float = 3.0) -> None:
        """请求停止当前脚本。"""
        with self._lock:
            self._ensure_active(run_id)
            self._active_script.stop()
            self.storage.runs.update_status(run_id, RunStatus.STOPPED)
            self._publish({"type": "run_status_changed", "run_id": run_id, "status": RunStatus.STOPPED.value})
        self.wait(run_id, timeout=timeout)
        if self.storage.runs.get(run_id)["status"] == RunStatus.RUNNING.value:
            self.storage.logs.append(run_id, "WARNING", "停止脚本超时，线程可能仍在退出中")
            self.storage.runs.update_status(run_id, RunStatus.STOPPED)
            self._clear_active(run_id)

    def wait(self, run_id: int, timeout: float) -> None:
        """等待脚本线程结束。"""
        thread = self._threads.get(run_id)
        if thread is not None:
            thread.join(timeout=timeout)

    def current_run_id(self) -> int | None:
        """返回当前活动 run_id。"""
        with self._lock:
            return self._active_run_id

    def _run_script(self, run_id: int, script_id: str, script: Any) -> None:
        try:
            script.run()
            snapshot = self._snapshot(script)
            self.storage.snapshots.append(run_id, script_id, snapshot)
            self.storage.logs.append(run_id, "INFO", "脚本执行结束")
            self._publish({"type": "state_snapshot", "run_id": run_id, "script_id": script_id, "state": snapshot})
            self._publish({"type": "log", "run_id": run_id, "level": "INFO", "message": "脚本执行结束"})
            previous = self.storage.runs.get(run_id)
            final_status = RunStatus.STOPPED if previous["status"] == RunStatus.STOPPED.value else RunStatus.SUCCESS
            self.storage.runs.update_status(run_id, final_status)
            self._publish({"type": "run_status_changed", "run_id": run_id, "status": final_status.value})
        except Exception as exc:
            self.storage.logs.append(run_id, "ERROR", f"脚本执行出错: {exc}")
            self.storage.logs.append(run_id, "ERROR", traceback.format_exc())
            self.storage.runs.update_status(run_id, RunStatus.ERROR, error_message=str(exc))
            self._publish({"type": "log", "run_id": run_id, "level": "ERROR", "message": f"脚本执行出错: {exc}"})
            self._publish({"type": "run_status_changed", "run_id": run_id, "status": RunStatus.ERROR.value})
        finally:
            self._clear_active(run_id)

    @staticmethod
    def _apply_config(script: Any, config: dict[str, Any]) -> None:
        if "max_battle_count" in config and hasattr(script, "set_max_battle_count"):
            script.set_max_battle_count(int(config["max_battle_count"]))

    @staticmethod
    def _snapshot(script: Any) -> dict[str, object]:
        if hasattr(script, "get_state_snapshot"):
            return dict(script.get_state_snapshot())
        return {}

    def _ensure_active(self, run_id: int) -> None:
        if self._active_run_id != run_id or self._active_script is None:
            raise RuntimeError("运行记录不是当前活动脚本")

    def _clear_active(self, run_id: int) -> None:
        with self._lock:
            if self._active_run_id == run_id:
                self._active_run_id = None
                self._active_script = None

    def _publish(self, event: dict[str, object]) -> None:
        self.event_hub.publish_from_thread(event)
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_run_manager.py -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add ui_backend/runs tests/ui_backend/test_run_manager.py
git commit -m "实现脚本单执行槽管理器"
```

---

## Task 7: 实现编排调度服务

**Files:**
- Create: `ui_backend/scheduler/__init__.py`
- Create: `ui_backend/scheduler/service.py`
- Test: `tests/ui_backend/test_scheduler.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/ui_backend/test_scheduler.py`：

```python
from __future__ import annotations

from datetime import datetime, timedelta

from ui_backend.models import WorkflowFailurePolicy, WorkflowStepType
from ui_backend.scheduler.service import SchedulerService


class FakeRunManager:
    def __init__(self) -> None:
        self.started: list[dict[str, object]] = []
        self.stopped: list[int] = []
        self.current = 7

    def start(self, request):
        self.started.append({"script_id": request.script_id, "config": request.config})
        return len(self.started)

    def stop(self, run_id: int) -> None:
        self.stopped.append(run_id)

    def current_run_id(self) -> int | None:
        return self.current


def test_scheduler_runs_steps_in_order() -> None:
    run_manager = FakeRunManager()
    scheduler = SchedulerService(run_manager=run_manager)

    workflow = {
        "id": 1,
        "failure_policy": WorkflowFailurePolicy.STOP_WORKFLOW.value,
        "steps": [
            {"id": 10, "step_type": WorkflowStepType.RUN_SCRIPT.value, "script_id": "exploration_28", "config": {"max_battle_count": 200}, "condition": {}},
            {"id": 11, "step_type": WorkflowStepType.RUN_SCRIPT.value, "script_id": "realm_raid", "config": {"max_battle_count": 9}, "condition": {}},
        ],
    }

    scheduler.run_workflow_now(workflow)

    assert [item["script_id"] for item in run_manager.started] == ["exploration_28", "realm_raid"]


def test_run_until_time_stops_current_run_when_time_reached() -> None:
    run_manager = FakeRunManager()
    scheduler = SchedulerService(run_manager=run_manager)
    target = (datetime.now() - timedelta(minutes=1)).strftime("%H:%M")

    scheduler.run_step(
        workflow_id=1,
        step={"id": 20, "step_type": WorkflowStepType.RUN_UNTIL_TIME.value, "script_id": "douji", "config": {}, "condition": {"until": target}},
    )

    assert run_manager.started[0]["script_id"] == "douji"
    assert run_manager.stopped == [7]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_scheduler.py -v
```

Expected: FAIL，错误包含 `No module named 'ui_backend.scheduler'`。

- [ ] **Step 3: 创建调度服务**

创建 `ui_backend/scheduler/__init__.py`：

```python
"""编排调度模块。"""
```

创建 `ui_backend/scheduler/service.py`：

```python
from __future__ import annotations

from datetime import datetime
from time import sleep
from typing import Any

from ui_backend.models import RunRequest, RunSourceType, WorkflowStepType


class SchedulerService:
    """编排调度服务。"""

    def __init__(self, run_manager: Any):
        self.run_manager = run_manager

    def run_workflow_now(self, workflow: dict[str, Any]) -> None:
        """立即按顺序执行编排任务。"""
        for step in workflow["steps"]:
            self.run_step(workflow_id=int(workflow["id"]), step=step)

    def run_step(self, workflow_id: int, step: dict[str, Any]) -> int | None:
        """执行单个编排步骤。"""
        step_type = WorkflowStepType(step["step_type"])
        if step_type == WorkflowStepType.WAIT_DURATION:
            sleep(float(step["condition"].get("seconds", 0)))
            return None

        run_id = self.run_manager.start(
            RunRequest(
                script_id=str(step["script_id"]),
                config=dict(step.get("config", {})),
                source_type=RunSourceType.WORKFLOW,
                workflow_id=workflow_id,
                workflow_step_id=int(step["id"]),
            )
        )

        if step_type == WorkflowStepType.RUN_UNTIL_TIME and self._time_reached(str(step["condition"]["until"])):
            current_run_id = self.run_manager.current_run_id()
            if current_run_id is not None:
                self.run_manager.stop(current_run_id)
        return run_id

    @staticmethod
    def _time_reached(target_hh_mm: str) -> bool:
        """判断当前本地时间是否已达到 HH:MM。"""
        now = datetime.now().time()
        target = datetime.strptime(target_hh_mm, "%H:%M").time()
        return now >= target
```

- [ ] **Step 4: 运行测试确认通过**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_scheduler.py -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add ui_backend/scheduler tests/ui_backend/test_scheduler.py
git commit -m "实现基础编排调度服务"
```

---

## Task 8: 实现 FastAPI 应用和 HTTP/WebSocket 接口

**Files:**
- Create: `ui_backend/app.py`
- Modify: `web_server.py`
- Test: `tests/ui_backend/test_app_api.py`

- [ ] **Step 1: 写 API 测试**

在 `tests/ui_backend/test_app_api.py` 追加：

```python
from pathlib import Path

from fastapi.testclient import TestClient

from ui_backend.app import create_app


def test_api_lists_scripts_and_starts_run(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "ui.db")
    client = TestClient(app)

    scripts_response = client.get("/api/scripts")
    assert scripts_response.status_code == 200
    assert any(item["script_id"] == "soul_raid" for item in scripts_response.json())

    current_response = client.get("/api/runs/current")
    assert current_response.status_code == 200
    assert current_response.json() is None


def test_workflow_create_and_list(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "ui.db")
    client = TestClient(app)

    response = client.post(
        "/api/workflows",
        json={
            "name": "日常探索",
            "group_name": "日常",
            "enabled": True,
            "trigger_type": "manual",
            "trigger_config": {},
            "failure_policy": "stop_workflow",
            "steps": [
                {
                    "sort_order": 1,
                    "step_type": "run_script",
                    "script_id": "exploration_28",
                    "config": {"max_battle_count": 200},
                    "condition": {},
                    "retry_count": 0,
                }
            ],
        },
    )

    assert response.status_code == 200
    workflow_id = response.json()["id"]
    assert workflow_id > 0
    assert client.get("/api/workflows").json()[0]["name"] == "日常探索"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_app_api.py -v
```

Expected: FAIL，错误包含 `No module named 'ui_backend.app'`。

- [ ] **Step 3: 创建 FastAPI 应用**

创建 `ui_backend/app.py`：

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from ui_backend.events.hub import EventHub
from ui_backend.models import RunRequest
from ui_backend.runs.manager import RunManager
from ui_backend.scripts.registry import ScriptRegistry
from ui_backend.scheduler.service import SchedulerService
from ui_backend.storage.database import Database
from ui_backend.storage.repositories import Storage


def create_app(db_path: Path | str | None = None) -> FastAPI:
    """创建桌面工作台 FastAPI 应用。"""
    app = FastAPI(title="YYS Desktop Workbench")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    database = Database(db_path or Path("config") / "ui_workbench.db")
    database.initialize()
    storage = Storage(database)
    registry = ScriptRegistry()
    event_hub = EventHub()
    run_manager = RunManager(storage=storage, registry=registry, event_hub=event_hub)
    scheduler = SchedulerService(run_manager=run_manager)

    app.state.storage = storage
    app.state.registry = registry
    app.state.event_hub = event_hub
    app.state.run_manager = run_manager
    app.state.scheduler = scheduler

    @app.get("/api/scripts")
    def list_scripts() -> list[dict[str, Any]]:
        return [
            {
                "script_id": item.script_id,
                "display_name": item.display_name,
                "category": item.category.value,
                "description": item.description,
                "config_schema": [field.__dict__ for field in item.config_schema],
                "default_config": item.default_config,
            }
            for item in registry.list_scripts()
        ]

    @app.get("/api/runs/current")
    def current_run() -> dict[str, Any] | None:
        return storage.runs.current()

    @app.post("/api/runs/start")
    def start_run(payload: dict[str, Any]) -> dict[str, int]:
        run_id = run_manager.start(RunRequest(script_id=payload["script_id"], config=payload.get("config", {})))
        return {"id": run_id}

    @app.post("/api/runs/{run_id}/pause")
    def pause_run(run_id: int) -> dict[str, str]:
        run_manager.pause(run_id)
        return {"status": "paused"}

    @app.post("/api/runs/{run_id}/resume")
    def resume_run(run_id: int) -> dict[str, str]:
        run_manager.resume(run_id)
        return {"status": "running"}

    @app.post("/api/runs/{run_id}/stop")
    def stop_run(run_id: int) -> dict[str, str]:
        run_manager.stop(run_id)
        return {"status": "stopped"}

    @app.get("/api/runs/{run_id}/logs")
    def run_logs(run_id: int) -> list[dict[str, Any]]:
        return storage.logs.list_by_run(run_id)

    @app.get("/api/runs/{run_id}/snapshots")
    def run_snapshots(run_id: int) -> list[dict[str, Any]]:
        latest = storage.snapshots.latest_by_run(run_id)
        return [latest]

    @app.get("/api/workflows")
    def list_workflows() -> list[dict[str, Any]]:
        return storage.workflows.list_all()

    @app.post("/api/workflows")
    def create_workflow(payload: dict[str, Any]) -> dict[str, int]:
        workflow_id = storage.workflows.create(
            name=payload["name"],
            group_name=payload["group_name"],
            enabled=bool(payload["enabled"]),
            trigger_type=payload["trigger_type"],
            trigger_config=dict(payload.get("trigger_config", {})),
            failure_policy=payload["failure_policy"],
        )
        for step in payload.get("steps", []):
            storage.workflow_steps.create(
                workflow_id=workflow_id,
                sort_order=int(step["sort_order"]),
                step_type=step["step_type"],
                script_id=step.get("script_id"),
                config=dict(step.get("config", {})),
                condition=dict(step.get("condition", {})),
                retry_count=int(step.get("retry_count", 0)),
            )
        return {"id": workflow_id}

    @app.post("/api/workflows/{workflow_id}/run-now")
    def run_workflow_now(workflow_id: int) -> dict[str, str]:
        workflows = [item for item in storage.workflows.list_all() if item["id"] == workflow_id]
        if not workflows:
            return {"status": "not_found"}
        workflow = workflows[0]
        workflow["steps"] = storage.workflow_steps.list_by_workflow(workflow_id)
        scheduler.run_workflow_now(workflow)
        return {"status": "started"}

    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket) -> None:
        await event_hub.connect(websocket)
        try:
            for event in event_hub.recent_events():
                await websocket.send_json(event)
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await event_hub.disconnect(websocket)

    return app
```

- [ ] **Step 4: 修改兼容入口**

将 `web_server.py` 简化为：

```python
from __future__ import annotations

from ui_backend.main import main


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 运行 API 测试确认通过**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend/test_app_api.py -v
```

Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add ui_backend/app.py web_server.py tests/ui_backend/test_app_api.py
git commit -m "实现桌面工作台后端API"
```

---

## Task 9: 重写 Electron 主进程托盘行为

**Files:**
- Modify: `gui/main.js`
- Modify: `gui/preload.js`

- [ ] **Step 1: 修改 main.js 使用新后端入口**

在 `gui/main.js` 中将 Python 启动参数改为：

```javascript
const pythonArgs = ['-m', 'ui_backend.main'];
pythonProcess = spawn(resolvePythonExecutable(), pythonArgs, {
  cwd: path.join(__dirname, '..'),
  stdio: ['pipe', 'pipe', 'pipe']
});
```

新增 Python 路径解析：

```javascript
function resolvePythonExecutable() {
  if (process.env.YYS_PYTHON) return process.env.YYS_PYTHON;
  return 'D:/ProgramData/anaconda3/envs/win_macro/python.exe';
}
```

- [ ] **Step 2: 添加托盘和关闭隐藏行为**

在 `gui/main.js` 中新增：

```javascript
const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } = require('electron');

let tray = null;
let isQuitting = false;

function createTrayIcon() {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32">
      <rect width="32" height="32" rx="7" fill="#111820"/>
      <text x="16" y="22" text-anchor="middle" font-size="18" fill="#35c28d" font-family="Arial">阴</text>
    </svg>`;
  return nativeImage.createFromDataURL(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`);
}

function createTray() {
  tray = new Tray(createTrayIcon());
  const menu = Menu.buildFromTemplate([
    { label: '显示工作台', click: () => mainWindow && mainWindow.show() },
    { label: '暂停当前脚本', click: () => mainWindow && mainWindow.webContents.send('tray-command', 'pause') },
    { label: '停止当前脚本', click: () => mainWindow && mainWindow.webContents.send('tray-command', 'stop') },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        isQuitting = true;
        app.quit();
      }
    }
  ]);
  tray.setToolTip('阴阳师脚本工作台');
  tray.setContextMenu(menu);
  tray.on('double-click', () => mainWindow && mainWindow.show());
}
```

在 `createWindow()` 的 close 事件中隐藏窗口：

```javascript
mainWindow.on('close', (event) => {
  if (!isQuitting) {
    event.preventDefault();
    mainWindow.hide();
  }
});
```

在 `app.whenReady()` 创建窗口后调用：

```javascript
createTray();
```

- [ ] **Step 3: 修改 preload.js 暴露托盘命令监听**

将 `gui/preload.js` 调整为：

```javascript
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('desktopBridge', {
  onTrayCommand: (callback) => ipcRenderer.on('tray-command', (_event, command) => callback(command)),
  minimizeWindow: () => ipcRenderer.send('minimize-window'),
  maximizeWindow: () => ipcRenderer.send('maximize-window'),
  closeWindow: () => ipcRenderer.send('close-window')
});
```

- [ ] **Step 4: 启动 Electron 手动验证**

Run:

```bash
cd gui
npm start
```

Expected:

- 桌面窗口打开。
- 关闭窗口后进程仍在，托盘图标存在。
- 托盘菜单可以重新显示窗口。
- 选择退出后 Python 后端退出。

- [ ] **Step 5: Commit**

```bash
git add gui/main.js gui/preload.js
git commit -m "实现桌面工作台托盘运行行为"
```

---

## Task 10: 重写前端执行页和基础 API 客户端

**Files:**
- Modify: `gui/index.html`
- Create: `gui/styles.css`
- Create: `gui/renderer.js`

- [ ] **Step 1: 将 index.html 改为三文件入口**

替换 `gui/index.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>阴阳师脚本工作台</title>
  <link rel="stylesheet" href="./styles.css">
</head>
<body>
  <div class="app-shell">
    <aside class="rail">
      <div class="brand-mark">阴</div>
      <button class="rail-button active" data-view="execute" title="执行">▶</button>
      <button class="rail-button" data-view="workflows" title="编排">⏱</button>
      <button class="rail-button" data-view="progress" title="进度">▦</button>
      <button class="rail-button" data-view="logs" title="日志">≡</button>
      <button class="rail-button" data-view="settings" title="设置">⚙</button>
    </aside>
    <aside class="script-panel">
      <div class="panel-title">
        <p>脚本列表</p>
        <h1>执行工作台</h1>
      </div>
      <div id="scriptList" class="script-list"></div>
    </aside>
    <main class="main-panel">
      <section id="executeView" class="view active">
        <header class="run-header">
          <div>
            <p class="eyebrow">当前运行</p>
            <h2 id="currentRunTitle">暂无运行脚本</h2>
          </div>
          <div class="run-actions">
            <span id="runStatus" class="status-pill idle">空闲</span>
            <button id="pauseButton" class="ghost-button" disabled>暂停</button>
            <button id="resumeButton" class="ghost-button" disabled>恢复</button>
            <button id="stopButton" class="danger-button" disabled>停止</button>
          </div>
        </header>
        <section class="run-summary">
          <div>
            <p class="eyebrow">参数</p>
            <p id="runConfigText" class="summary-value">未启动</p>
            <div class="progress-bar"><span id="progressBar"></span></div>
          </div>
          <div class="metric-grid">
            <div class="metric"><p>已战斗</p><strong id="battleCount">0 / 0</strong></div>
            <div class="metric"><p>胜利</p><strong id="victoryCount">0</strong></div>
            <div class="metric"><p>运行来源</p><strong id="runSource">-</strong></div>
          </div>
        </section>
        <section class="log-panel">
          <div class="log-header"><span>实时日志</span><button id="clearLogButton">清空</button></div>
          <div id="logBody" class="log-body"></div>
        </section>
      </section>
      <section id="workflowsView" class="view">
        <h2>编排任务</h2>
        <div id="workflowList" class="workflow-list"></div>
      </section>
    </main>
    <aside class="side-panel">
      <section class="side-card"><p class="eyebrow">调度预告</p><div id="schedulePreview">暂无启用任务</div></section>
      <section class="side-card"><p class="eyebrow">断点快照</p><div id="snapshotPreview">暂无快照</div></section>
      <section class="side-card"><p class="eyebrow">关键日志</p><div id="keyLogPreview">暂无警告或错误</div></section>
    </aside>
  </div>
  <script src="./renderer.js"></script>
</body>
</html>
```

- [ ] **Step 2: 创建样式文件**

创建 `gui/styles.css`。样式必须落实设计规格中的原型 A：深色、窄导航、脚本列表内联参数、日志主区域、右侧辅助栏。实现时从已验证原型 A 提炼样式，避免加入装饰性渐变球或营销式大标题。

验证重点：

- `body` 不滚动，主日志区域内部滚动。
- 脚本参数字段在 800px 宽度下不溢出。
- 日志行使用等宽字体。
- 颜色不形成单一紫蓝或棕橙主题。

- [ ] **Step 3: 创建 renderer.js API 客户端和渲染逻辑**

创建 `gui/renderer.js`：

```javascript
const API_BASE = 'http://127.0.0.1:8000';
const WS_URL = 'ws://127.0.0.1:8000/ws/events';

const state = {
  scripts: [],
  selectedScriptId: null,
  currentRun: null,
  logs: []
};

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(`请求失败: ${path}`);
  return response.json();
}

async function apiPost(path, body = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!response.ok) throw new Error(`请求失败: ${path}`);
  return response.json();
}

function renderScripts() {
  const container = document.getElementById('scriptList');
  container.innerHTML = '';
  for (const script of state.scripts) {
    const row = document.createElement('article');
    row.className = 'script-row';
    row.innerHTML = `
      <button class="script-head" data-script-id="${script.script_id}">
        <span>
          <strong>${script.display_name}</strong>
          <small>${script.category === 'experimental' ? '实验脚本' : '稳定脚本'}</small>
        </span>
        <span>›</span>
      </button>
      <form class="script-params ${state.selectedScriptId === script.script_id ? 'active' : ''}" data-script-form="${script.script_id}">
        ${script.config_schema.map(field => renderField(field)).join('')}
        <button type="submit" class="primary-button">启动</button>
      </form>
    `;
    container.appendChild(row);
  }
}

function renderField(field) {
  if (field.field_type === 'select') {
    const options = field.options.map(item => `<option value="${item.value}">${item.label}</option>`).join('');
    return `<label><span>${field.label}</span><select name="${field.key}">${options}</select></label>`;
  }
  const type = field.field_type === 'number' ? 'number' : 'text';
  return `<label><span>${field.label}</span><input name="${field.key}" type="${type}" value="${field.default ?? ''}"></label>`;
}

async function startScript(scriptId, form) {
  const config = Object.fromEntries(new FormData(form).entries());
  const run = await apiPost('/api/runs/start', { script_id: scriptId, config });
  state.currentRun = run;
  await refreshCurrentRun();
}

async function refreshCurrentRun() {
  state.currentRun = await apiGet('/api/runs/current');
  renderCurrentRun();
}

function renderCurrentRun() {
  const run = state.currentRun;
  document.getElementById('currentRunTitle').textContent = run ? run.script_id : '暂无运行脚本';
  document.getElementById('runStatus').textContent = run ? run.status : '空闲';
  document.getElementById('pauseButton').disabled = !run || run.status !== 'running';
  document.getElementById('resumeButton').disabled = !run || run.status !== 'paused';
  document.getElementById('stopButton').disabled = !run || !['running', 'paused', 'queued'].includes(run.status);
  document.getElementById('runSource').textContent = run ? run.source_type : '-';
  document.getElementById('runConfigText').textContent = run ? JSON.stringify(run.config) : '未启动';
}

function appendLog(event) {
  const body = document.getElementById('logBody');
  const line = document.createElement('div');
  line.className = `log-line ${event.level || 'INFO'}`;
  line.textContent = event.message || event.data || JSON.stringify(event);
  body.appendChild(line);
  body.scrollTop = body.scrollHeight;
}

function connectEvents() {
  const ws = new WebSocket(WS_URL);
  ws.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === 'log') appendLog(payload);
    if (payload.type === 'run_status_changed') refreshCurrentRun();
    if (payload.type === 'state_snapshot') renderSnapshot(payload.state);
  };
  ws.onclose = () => setTimeout(connectEvents, 2000);
}

function renderSnapshot(stateSnapshot) {
  document.getElementById('snapshotPreview').textContent = JSON.stringify(stateSnapshot);
  document.getElementById('battleCount').textContent = `${stateSnapshot.battle_count || 0} / ${stateSnapshot.max_battle_count || 0}`;
  document.getElementById('victoryCount').textContent = stateSnapshot.victory_count || 0;
}

function bindEvents() {
  document.getElementById('scriptList').addEventListener('click', (event) => {
    const button = event.target.closest('[data-script-id]');
    if (!button) return;
    state.selectedScriptId = button.dataset.scriptId;
    renderScripts();
  });
  document.getElementById('scriptList').addEventListener('submit', (event) => {
    event.preventDefault();
    const form = event.target;
    startScript(form.dataset.scriptForm, form);
  });
  document.getElementById('clearLogButton').addEventListener('click', () => {
    document.getElementById('logBody').innerHTML = '';
  });
}

async function init() {
  state.scripts = await apiGet('/api/scripts');
  state.selectedScriptId = state.scripts[0]?.script_id || null;
  renderScripts();
  bindEvents();
  await refreshCurrentRun();
  connectEvents();
}

init().catch((error) => appendLog({ level: 'ERROR', message: error.message }));
```

- [ ] **Step 4: 启动本地服务验证页面**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m ui_backend.main
```

另开终端：

```bash
cd gui
npm start
```

Expected:

- 脚本列表成功从 `/api/scripts` 加载。
- 点击脚本在左侧展开参数。
- 日志区域占据主区域大部分空间。
- 启动按钮向后端发起请求。

- [ ] **Step 5: Commit**

```bash
git add gui/index.html gui/styles.css gui/renderer.js
git commit -m "实现桌面工作台执行页界面"
```

---

## Task 11: 实现编排页最小可用界面

**Files:**
- Modify: `gui/index.html`
- Modify: `gui/styles.css`
- Modify: `gui/renderer.js`

- [ ] **Step 1: 扩展编排页 DOM**

在 `workflowsView` 中加入：

```html
<form id="workflowForm" class="workflow-editor">
  <label><span>名称</span><input name="name" value="日常探索突破"></label>
  <label><span>分组</span><input name="group_name" value="日常"></label>
  <label><span>失败策略</span>
    <select name="failure_policy">
      <option value="stop_workflow">失败后停止</option>
      <option value="continue_next">失败后继续</option>
      <option value="retry_then_stop">重试后停止</option>
    </select>
  </label>
  <div id="workflowSteps" class="workflow-steps"></div>
  <button type="button" id="addWorkflowStep" class="ghost-button">添加步骤</button>
  <button type="submit" class="primary-button">保存编排</button>
</form>
```

- [ ] **Step 2: 扩展 renderer.js 编排逻辑**

加入：

```javascript
function renderWorkflowStep(index) {
  return `
    <div class="workflow-step" data-step-index="${index}">
      <select name="step_type_${index}">
        <option value="run_script">运行脚本</option>
        <option value="wait_duration">等待</option>
        <option value="run_until_time">运行到指定时间</option>
      </select>
      <select name="script_id_${index}">
        ${state.scripts.map(script => `<option value="${script.script_id}">${script.display_name}</option>`).join('')}
      </select>
      <input name="max_battle_count_${index}" value="200" aria-label="战斗次数">
      <input name="until_${index}" value="21:03" aria-label="目标时间">
    </div>
  `;
}

function addWorkflowStep() {
  const container = document.getElementById('workflowSteps');
  const index = container.children.length;
  container.insertAdjacentHTML('beforeend', renderWorkflowStep(index));
}

async function saveWorkflow(form) {
  const data = new FormData(form);
  const steps = [...document.querySelectorAll('.workflow-step')].map((item, index) => ({
    sort_order: index + 1,
    step_type: data.get(`step_type_${index}`),
    script_id: data.get(`script_id_${index}`),
    config: { max_battle_count: Number(data.get(`max_battle_count_${index}`) || 0) },
    condition: { until: data.get(`until_${index}`) },
    retry_count: 0
  }));
  await apiPost('/api/workflows', {
    name: data.get('name'),
    group_name: data.get('group_name'),
    enabled: true,
    trigger_type: 'manual',
    trigger_config: {},
    failure_policy: data.get('failure_policy'),
    steps
  });
  await renderWorkflows();
}

async function renderWorkflows() {
  const workflows = await apiGet('/api/workflows');
  document.getElementById('workflowList').innerHTML = workflows.map(item => `
    <article class="workflow-card">
      <strong>${item.name}</strong>
      <small>${item.group_name}</small>
      <button data-run-workflow="${item.id}" class="ghost-button">立即运行</button>
    </article>
  `).join('');
}
```

在 `bindEvents()` 中加入：

```javascript
  document.getElementById('addWorkflowStep').addEventListener('click', addWorkflowStep);
  document.getElementById('workflowForm').addEventListener('submit', (event) => {
    event.preventDefault();
    saveWorkflow(event.target);
  });
  document.getElementById('workflowList').addEventListener('click', (event) => {
    const button = event.target.closest('[data-run-workflow]');
    if (!button) return;
    apiPost(`/api/workflows/${button.dataset.runWorkflow}/run-now`);
  });
```

在 `init()` 末尾加入：

```javascript
  addWorkflowStep();
  await renderWorkflows();
```

- [ ] **Step 3: 补充样式**

在 `gui/styles.css` 中增加：

```css
.workflow-editor,
.workflow-list {
  display: grid;
  gap: 12px;
}

.workflow-step,
.workflow-card {
  display: grid;
  grid-template-columns: 1fr 1fr 100px 100px;
  gap: 8px;
  align-items: center;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 255, 255, .035);
}
```

- [ ] **Step 4: 手动验证**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m ui_backend.main
cd gui
npm start
```

Expected:

- 编排页能新增步骤。
- 保存后刷新页面仍能看到编排任务。
- 点击立即运行后执行页能展示运行脚本。

- [ ] **Step 5: Commit**

```bash
git add gui/index.html gui/styles.css gui/renderer.js
git commit -m "实现编排任务最小可用界面"
```

---

## Task 12: 全量验证和文档更新

**Files:**
- Modify: `README.md`
- Modify: `docs/specs/2026-05-30-yys-desktop-workbench-design.md` if implementation decisions changed

- [ ] **Step 1: 运行后端单元测试**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/ui_backend tests/common/test_yys.py::test_base_script_state_snapshot -v
```

Expected: PASS。

- [ ] **Step 2: 运行现有关键测试**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m pytest tests/common/ yys/soul_raid/test_soul_raid.py -v
```

Expected: PASS。若失败，记录具体失败并只修复与本次 UI/状态快照相关的问题。

- [ ] **Step 3: 验证后端服务启动**

Run:

```bash
D:/ProgramData/anaconda3/envs/win_macro/python.exe -m ui_backend.main
```

Expected:

```text
Uvicorn running on http://127.0.0.1:8000
```

另开终端：

```bash
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/scripts
```

Expected: 返回脚本列表 JSON。

- [ ] **Step 4: 验证 Electron 工作台**

Run:

```bash
cd gui
npm start
```

Expected:

- 应用窗口打开并展示深色控制台工作台。
- 脚本列表按单列展示。
- 点击脚本展开参数。
- 执行页日志区域占主区域大部分空间。
- 编排页可以保存编排任务。
- 关闭窗口后应用隐藏到托盘。
- 托盘退出后 Python 后端停止。

- [ ] **Step 5: 更新 README**

在 `README.md` 的运行方法中加入：

```markdown
### 桌面工作台

```bash
cd gui
npm install
npm start
```

工作台会自动启动 Python 后端。关闭主窗口默认隐藏到托盘，选择托盘菜单中的“退出”才会停止后端和调度器。
```
```

- [ ] **Step 6: 查看变更**

Run:

```bash
git status --short
git diff --stat
```

Expected: 只包含本计划相关文件，不能包含用户未授权的 `yys/yuling/yuling_script.py` 修改。

- [ ] **Step 7: Commit**

```bash
git add README.md docs/specs/2026-05-30-yys-desktop-workbench-design.md
git commit -m "补充桌面工作台使用说明"
```

---

## 自审清单

- 设计规格中的单脚本执行由 Task 6、Task 8、Task 10 覆盖。
- 脚本特有参数由 Task 3、Task 10 覆盖。
- 编排任务命名、分组、持久化由 Task 2、Task 7、Task 8、Task 11 覆盖。
- 实时日志和历史日志由 Task 2、Task 6、Task 8、Task 10 覆盖。
- 断点进度展示由 Task 4、Task 6、Task 10 覆盖。
- Electron 桌面入口和托盘后台由 Task 9 覆盖。
- 测试和验证由 Task 2 到 Task 8 以及 Task 12 覆盖。
- 多客户端并行、自动快照续跑、Windows 服务不在第一版计划内。
