"""工作台数据库路径解析与旧库迁移的契约测试。"""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from ui_backend.app import create_app
from ui_backend.storage.database import Database
from ui_backend.storage.workbench_db import (
    DB_PATH_ENV,
    LEGACY_DB_ENV,
    MIGRATION_MIGRATED,
    MIGRATION_SKIPPED,
    MIGRATION_TARGET_EXISTS,
    migrate_legacy_database,
    resolve_db_path,
)


def make_legacy_db(path: Path, marker: str) -> None:
    """构造一个带标记行的旧库。"""
    Database(path).initialize()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "insert into app_settings (key, value_json) values ('legacy-marker', ?)",
            (f'"{marker}"',),
        )


def read_marker(path: Path) -> str | None:
    """读取迁移后的标记行。"""
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "select value_json from app_settings where key = 'legacy-marker'"
        ).fetchone()
    return row[0] if row else None


def test_resolve_db_path_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """产品契约：AC27，显式参数优先于配置，配置优先于 cwd 回退。"""
    monkeypatch.delenv(DB_PATH_ENV, raising=False)
    assert resolve_db_path() == Path("config") / "ui_workbench.db"
    monkeypatch.setenv(DB_PATH_ENV, str(tmp_path / "configured.db"))
    assert resolve_db_path() == tmp_path / "configured.db"
    assert resolve_db_path(tmp_path / "explicit.db") == tmp_path / "explicit.db"


def test_migration_creates_target_from_readonly_snapshot(tmp_path: Path) -> None:
    """产品契约：AC24，旧库一致性复制到永久位置且数据完整。"""
    source = tmp_path / "legacy.db"
    make_legacy_db(source, "portable")
    target = tmp_path / "user-data" / "config" / "ui_workbench.db"

    assert migrate_legacy_database(target, source) == MIGRATION_MIGRATED
    assert target.is_file()
    assert read_marker(target) == '"portable"'
    with sqlite3.connect(target) as connection:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    # 迁移不移动也不改写源库。
    assert source.is_file()
    assert read_marker(source) == '"portable"'


def test_migration_never_overwrites_existing_target(tmp_path: Path) -> None:
    """产品契约：AC25，目标已存在时复用且不被来源覆盖。"""
    target = tmp_path / "config" / "ui_workbench.db"
    make_legacy_db(target, "current")
    source = tmp_path / "legacy.db"
    make_legacy_db(source, "stale")

    assert migrate_legacy_database(target, source) == MIGRATION_TARGET_EXISTS
    assert read_marker(target) == '"current"'


def test_migration_reports_missing_source_without_creating_empty_db(tmp_path: Path) -> None:
    """产品契约：AC25，来源不可用要明确报错，不能静默建空库。"""
    target = tmp_path / "config" / "ui_workbench.db"

    with pytest.raises(FileNotFoundError):
        migrate_legacy_database(target, tmp_path / "missing.db")
    assert not target.exists()

    assert migrate_legacy_database(target, None) == MIGRATION_SKIPPED
    assert not target.exists()


def test_app_uses_configured_path_and_migrates_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """产品契约：AC24/AC26，宿主配置的目标库在首次启动完成迁移，再次启动不重复导入。"""
    source = tmp_path / "portable.db"
    make_legacy_db(source, "portable")
    target = tmp_path / "user-data" / "config" / "ui_workbench.db"
    monkeypatch.setenv(DB_PATH_ENV, str(target))
    monkeypatch.setenv(LEGACY_DB_ENV, str(source))

    first = create_app(api_token="token")
    assert first.state.db_path == target
    assert first.state.migration == MIGRATION_MIGRATED
    assert read_marker(target) == '"portable"'

    with sqlite3.connect(target) as connection:
        connection.execute(
            "update app_settings set value_json = ? where key = 'legacy-marker'",
            ('"edited"',),
        )
    second = create_app(api_token="token")
    assert second.state.migration == MIGRATION_TARGET_EXISTS
    assert read_marker(target) == '"edited"'


def test_explicit_db_path_wins_over_configured_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """产品契约：AC27，显式 db_path 压过配置，且不受迁移配置影响。"""
    monkeypatch.setenv(DB_PATH_ENV, str(tmp_path / "ignored.db"))
    explicit = tmp_path / "explicit.db"

    app = create_app(db_path=explicit)

    assert app.state.db_path == explicit
    assert explicit.exists()
    assert not (tmp_path / "ignored.db").exists()
