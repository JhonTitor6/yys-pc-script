"""tools/migrate_ui_config.py 的单元测试。

覆盖 4 个核心场景（auto-registry Step 5 verify 钩子）：
1. 旧 ui_config.json 4 项正确映射到 SQLite
2. 模糊匹配未匹配的 task 跳过（不抛错）
3. 旧文件归档为 .bak
4. 新 SQLite 数据可读 + 旧文件已删除
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tools import migrate_ui_config


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """创建临时工作区：config/ui_config.json + config/ui_workbench.db。

    Returns:
        包含 ui_config / sqlite / backup 路径的字典。
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    old_config = config_dir / "ui_config.json"
    sqlite_db = config_dir / "ui_workbench.db"
    backup = config_dir / "ui_config.json.bak"

    # 写入 4 项手写 task
    old_config.write_text(
        json.dumps(
            {
                "last_selected_task": "御魂",
                "tasks": {
                    "御魂": {"max_battle_count": 103, "loop_interval": 5},
                    "结界突破": {"max_battle_count": 9, "loop_interval": 3},
                    "探28": {"max_battle_count": 50, "loop_interval": 3},
                    "御灵": {"max_battle_count": 50, "loop_interval": 5},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # 预先创建空 SQLite 数据库（确保存在，触发 _migrate_to_sqlite 写入）
    sqlite_db.touch()

    # 用 monkeypatch 切到临时工作区
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(migrate_ui_config, "OLD_CONFIG", old_config)
    monkeypatch.setattr(migrate_ui_config, "BACKUP", backup)
    monkeypatch.setattr(migrate_ui_config, "SQLITE_DB", sqlite_db)

    return {
        "ui_config": old_config,
        "sqlite": sqlite_db,
        "backup": backup,
        "config_dir": config_dir,
    }


def test_old_config_4_tasks_migrate_to_sqlite(workspace: dict[str, Path]) -> None:
    """4 项手写 task 正确写入 SQLite。

    验证点：
    - 4 个 task 全部迁移（按 task_name → script_id 模糊匹配）
    - 写入的 config_json 与原 task_config 完全一致
    """
    migrate_ui_config.migrate()

    conn = sqlite3.connect(str(workspace["sqlite"]))
    try:
        rows = conn.execute(
            "SELECT script_id, config_json FROM script_user_configs ORDER BY script_id"
        ).fetchall()
    finally:
        conn.close()

    # 4 个 task 全部存在
    assert len(rows) == 4
    by_id = {r[0]: json.loads(r[1]) for r in rows}
    assert by_id["soul_raid"] == {"max_battle_count": 103, "loop_interval": 5}
    assert by_id["realm_raid"] == {"max_battle_count": 9, "loop_interval": 3}
    assert by_id["exploration_28"] == {"max_battle_count": 50, "loop_interval": 3}
    assert by_id["yuling"] == {"max_battle_count": 50, "loop_interval": 5}


def test_unmatched_task_skipped_silently(workspace: dict[str, Path], capsys) -> None:
    """未匹配的 task 跳过（不抛错）+ 输出提示。

    验证点：
    - 添加一个未在映射中的 task（如 "新脚本"）
    - 迁移不抛错
    - 输出包含"未匹配"字样
    - SQLite 中不含该 task
    """
    config = json.loads(workspace["ui_config"].read_text(encoding="utf-8"))
    config["tasks"]["新脚本"] = {"max_battle_count": 1}
    workspace["ui_config"].write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )

    migrate_ui_config.migrate()  # 不应抛错

    captured = capsys.readouterr()
    assert "未匹配" in captured.out

    conn = sqlite3.connect(str(workspace["sqlite"]))
    try:
        rows = conn.execute(
            "SELECT script_id FROM script_user_configs WHERE script_id = '新脚本'"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [], "未匹配的 task 不应写入 SQLite"


def test_old_config_archived_to_bak(workspace: dict[str, Path]) -> None:
    """旧文件归档为 .bak。

    验证点：
    - .bak 文件存在且内容与旧 ui_config.json 完全一致
    - 原 ui_config.json 已被删除
    """
    original_content = workspace["ui_config"].read_text(encoding="utf-8")

    migrate_ui_config.migrate()

    assert workspace["backup"].exists(), "备份文件应存在"
    assert workspace["backup"].read_text(encoding="utf-8") == original_content, (
        "备份内容应与原文件一致"
    )
    assert not workspace["ui_config"].exists(), "原文件应被删除"


def test_sqlite_data_persisted_and_old_file_gone(workspace: dict[str, Path]) -> None:
    """迁移后 SQLite 数据持久化 + 旧文件已删除。

    验证点：
    - SQLite script_user_configs 表行数 = 4
    - 旧 ui_config.json 已被删除
    - .bak 存在
    """
    migrate_ui_config.migrate()

    # SQLite 数据持久化
    conn = sqlite3.connect(str(workspace["sqlite"]))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM script_user_configs"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 4

    # 旧文件删除
    assert not workspace["ui_config"].exists()
    # 备份存在
    assert workspace["backup"].exists()


def test_migrate_idempotent_when_old_config_missing(
    workspace: dict[str, Path], capsys
) -> None:
    """旧文件不存在时跳过迁移（不抛错）。

    验证点：
    - 旧文件已删除后再次运行 migrate() 不抛错
    - 输出包含"不存在"或"跳过"字样
    """
    # 第一次迁移
    migrate_ui_config.migrate()
    # 第二次迁移（旧文件已删）
    migrate_ui_config.migrate()  # 不应抛错

    captured = capsys.readouterr()
    assert "不存在" in captured.out or "跳过" in captured.out
