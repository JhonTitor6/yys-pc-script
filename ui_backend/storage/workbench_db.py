"""工作台数据库的路径解析与旧库首次迁移。"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

#: 未配置时保持既有 cwd 相对定位。
DEFAULT_DB_PATH = Path("config") / "ui_workbench.db"
#: 桌面宿主注入的永久数据库路径。
DB_PATH_ENV = "YYS_WORKBENCH_DB_PATH"
#: 首次启动时由宿主导入的旧库来源，导入完成后不再需要。
LEGACY_DB_ENV = "YYS_LEGACY_DB_PATH"

MIGRATION_MIGRATED = "migrated"
MIGRATION_TARGET_EXISTS = "target-exists"
MIGRATION_SKIPPED = "skipped"


def resolve_db_path(db_path: Path | str | None = None) -> Path:
    """显式参数优先，其次永久路径配置，最后回退到 cwd 相对定位。"""
    if db_path is not None:
        return Path(db_path)
    configured = os.environ.get(DB_PATH_ENV)
    if configured:
        return Path(configured)
    return DEFAULT_DB_PATH


def legacy_source() -> Path | None:
    """读取旧库来源配置；未配置表示不是迁移场景。"""
    configured = os.environ.get(LEGACY_DB_ENV)
    return Path(configured) if configured else None


def migrate_legacy_database(target: Path, source: Path | None) -> str:
    """把旧库一致性复制到永久位置；目标已存在时绝不覆盖。

    源库只读打开并走 SQLite backup API，避免直接复制 WAL 中的半写状态。
    迁移先写同目录临时文件，完整性检查通过后再原子替换。
    """
    if target.exists():
        return MIGRATION_TARGET_EXISTS
    if source is None:
        return MIGRATION_SKIPPED
    if not source.is_file():
        raise FileNotFoundError(f"旧库来源不存在：{source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f"{target.name}.migrating")
    staging.unlink(missing_ok=True)
    source_connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    target_connection = sqlite3.connect(staging)
    try:
        source_connection.backup(target_connection)
        check = target_connection.execute("PRAGMA quick_check").fetchone()
        if not check or check[0] != "ok":
            raise RuntimeError(f"迁移副本完整性检查失败：{check}")
    except Exception:
        staging.unlink(missing_ok=True)
        raise
    finally:
        target_connection.close()
        source_connection.close()
    os.replace(staging, target)
    return MIGRATION_MIGRATED
