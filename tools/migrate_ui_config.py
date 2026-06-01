"""一次性迁移工具：把 `config/ui_config.json` 的 4 个手写 task 转 `config/script_registry.json`。

背景：
- plan §5 Step 5 写的是 `config/script_registry.json`（**纯文件**）
- Step 3 实施时为兼容 owner 决策改用 SQLite (`config/ui_workbench.db`)
  + `ScriptUserConfigRepository`，不再需要 `config/script_registry.json`
- 但旧 `config/ui_config.json` 仍存在 4 项手写 task，需要：
  1. 把 task name 模糊匹配到 SCRIPT_META.display_name
  2. 写入 SQLite 的 `script_user_configs` 表（**真实**持久化路径）
  3. 旧 `ui_config.json` 归档为 `.bak`（不改 SQLite 中的数据）

owner 决策：本工具**只读** `ui_config.json` + 写入 SQLite + 备份，不修改
已有 SQLite 数据（不动 `config/ui_workbench.db` 的脚本/工作流/历史运行记录）。

模糊匹配规则（4 项）：
- "御魂"      → soul_raid
- "结界突破"  → realm_raid
- "探28"      → exploration_28
- "御灵"      → yuling

未匹配的 task 跳过（不抛错），便于未来新增 task 时不破坏迁移。
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

OLD_CONFIG = Path("config/ui_config.json")
BACKUP = Path("config/ui_config.json.bak")
SQLITE_DB = Path("config/ui_workbench.db")

# 模糊匹配：UI 配置文件中的中文 task name → script_id
# 来源：原 ui_config.json 的 4 项（last_selected_task + tasks）
TASK_NAME_TO_SCRIPT_ID: dict[str, str] = {
    "御魂": "soul_raid",
    "结界突破": "realm_raid",
    "探28": "exploration_28",
    "御灵": "yuling",
}


def _migrate_to_sqlite(tasks: dict[str, dict]) -> int:
    """把 task 配置写入 SQLite `script_user_configs` 表。

    Args:
        tasks: 旧 ui_config.json 中的 tasks 字典（task_name → config dict）。

    Returns:
        成功迁移的 task 数。
    """
    if not SQLITE_DB.exists():
        print(f"SQLite 数据库不存在: {SQLITE_DB}，跳过 SQLite 写入（仅生成 .bak）")
        return 0

    conn = sqlite3.connect(str(SQLITE_DB))
    try:
        # 幂等 upsert：若 script_id 已存在则覆盖
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS script_user_configs (
                script_id TEXT PRIMARY KEY,
                config_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS script_user_configs_updated_at
                AFTER UPDATE ON script_user_configs
            BEGIN
                UPDATE script_user_configs
                SET updated_at = CURRENT_TIMESTAMP
                WHERE script_id = NEW.script_id;
            END
            """
        )
        migrated = 0
        for task_name, task_config in tasks.items():
            script_id = TASK_NAME_TO_SCRIPT_ID.get(task_name)
            if script_id is None:
                print(f"  未匹配 task {task_name!r}，跳过（不在 4 项映射中）")
                continue
            conn.execute(
                """
                INSERT INTO script_user_configs (script_id, config_json)
                VALUES (?, ?)
                ON CONFLICT(script_id) DO UPDATE SET
                    config_json = excluded.config_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (script_id, json.dumps(task_config, ensure_ascii=False)),
            )
            migrated += 1
            print(f"  {task_name!r} → {script_id}: {task_config}")
        conn.commit()
        return migrated
    finally:
        conn.close()


def migrate() -> None:
    """执行一次性迁移：读旧 ui_config.json → 写 SQLite → 备份旧文件。

    行为：
    - 旧文件不存在：跳过（视为已迁移），不抛错
    - SQLite 不存在：仅做备份，不抛错
    - 未匹配的 task：跳过（不抛错），便于未来扩展
    """
    if not OLD_CONFIG.exists():
        print(f"{OLD_CONFIG} 不存在，跳过迁移（视为已迁移）")
        return

    print(f"读取旧配置: {OLD_CONFIG}")
    with OLD_CONFIG.open(encoding="utf-8") as f:
        old = json.load(f)

    tasks = old.get("tasks", {})
    print(f"发现 {len(tasks)} 个 task: {list(tasks.keys())}")

    print(f"写入 SQLite ({SQLITE_DB})")
    migrated_count = _migrate_to_sqlite(tasks)
    print(f"成功迁移 {migrated_count} 个 task")

    # 备份旧文件
    shutil.copy2(OLD_CONFIG, BACKUP)
    OLD_CONFIG.unlink()
    print(f"旧文件已备份: {BACKUP}")
    print(f"旧文件已删除: {OLD_CONFIG}")
    print("迁移完成")


if __name__ == "__main__":
    migrate()
