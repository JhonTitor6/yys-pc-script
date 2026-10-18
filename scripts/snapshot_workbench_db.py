"""为工作台数据库做一致性快照，供回退到旧版前保留最新数据。

用法：
    python scripts/snapshot_workbench_db.py
    python scripts/snapshot_workbench_db.py --source <db> --output <file>

默认来源是桌面宿主使用的永久库；输出默认放在同目录的 backups/ 下。
快照使用 SQLite backup API，不复制 WAL 中的半写状态，也不修改源库。
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import datetime
from pathlib import Path
import sqlite3

DEFAULT_SOURCE = Path.home() / "AppData" / "Roaming" / "yys-script-manager" / "config" / "ui_workbench.db"


def snapshot(source: Path, output: Path) -> Path:
    """把源库一致性复制到输出文件，并校验副本完整性。"""
    if not source.is_file():
        raise FileNotFoundError(f"数据库不存在：{source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    output_connection = sqlite3.connect(output)
    try:
        source_connection.backup(output_connection)
        check = output_connection.execute("PRAGMA quick_check").fetchone()
        if not check or check[0] != "ok":
            raise RuntimeError(f"快照完整性检查失败：{check}")
    finally:
        output_connection.close()
        source_connection.close()
    return output


def main() -> None:
    """解析参数、生成快照并输出路径与哈希。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = args.source
    output = args.output or source.parent / "backups" / (
        f"ui_workbench-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    )
    result = snapshot(source, output)
    digest = hashlib.sha256(result.read_bytes()).hexdigest()
    print(f"快照：{result}")
    print(f"字节：{result.stat().st_size}")
    print(f"SHA-256：{digest}")


if __name__ == "__main__":
    main()
