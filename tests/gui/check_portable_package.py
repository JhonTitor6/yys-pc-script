"""用真实 NSIS 和最小宿主验证同版本便携包更新、重复启动与载荷清理。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def run(command: list[str], env: dict[str, str] | None = None, cwd: Path | None = None) -> None:
    """执行有界构建或替身宿主；不运行游戏脚本。"""
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError((result.stdout + result.stderr).decode("utf-8", "replace"))


def main() -> None:
    """产品契约 AC23：每次使用完整当前载荷，退出清理只涉及自己的临时目录。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    build = repo / "build"
    build.mkdir(exist_ok=True)
    nsis = Path(os.environ["LOCALAPPDATA"]) / "tauri/NSIS/makensis.exe"
    rustc = Path.home() / ".cargo/bin/rustc.exe"
    with tempfile.TemporaryDirectory(prefix="portable-regression-", dir=build) as folder:
        root = Path(folder).resolve()
        assert root.is_relative_to(build.resolve())
        fixture = root / "payload with spaces"
        (fixture / "backend").mkdir(parents=True)
        (fixture / "backend/yys-backend.exe").write_bytes(b"not-executed")
        asset = fixture / "backend/required.txt"
        asset.write_text("required", encoding="utf-8")
        report = root / "launches.txt"
        sentinel = root / "permanent.db"
        sentinel.write_bytes(b"keep")
        env = {**os.environ, "YYS_PORTABLE_TEST_LOG": str(report)}

        def build_wrapper(marker: str) -> Path:
            """两个不同载荷使用相同产品版本，验证同版本修复包不会读旧内容。"""
            source = root / "stub.rs"
            source.write_text('''#![windows_subsystem = "windows"]
use std::io::Write;
fn main() {
    let exe = std::env::current_exe().unwrap();
    let asset = std::fs::read_to_string(exe.parent().unwrap().join("backend/required.txt")).unwrap();
    let mut log = std::fs::OpenOptions::new().append(true).create(true)
        .open(std::env::var_os("YYS_PORTABLE_TEST_LOG").unwrap()).unwrap();
    writeln!(log, "MARKER|{}|{}", exe.display(), asset).unwrap();
}
'''.replace("MARKER", marker), encoding="utf-8")
            run([str(rustc), "+1.99.1", str(source), "-o", str(fixture / "yys-desktop.exe")])
            output = root / f"{marker}.exe"
            run([str(nsis), f"/DAPPDIR={fixture}", f"/DOUTPUTFILE={output}", "/DAPP_VERSION=1.0.0", str(repo / "scripts/portable.nsi")])
            return output

        old = build_wrapper("old")
        run([str(old)], env, root)
        new = build_wrapper("new")
        run([str(new)], env, build)
        run([str(new)], env, fixture)
        records = [line.split("|") for line in report.read_text(encoding="utf-8").splitlines()]
        assert [item[0] for item in records] == ["old", "new", "new"], records
        assert all(item[2] == "required" for item in records), records
        assert len({item[1] for item in records}) == 3, records
        assert all(not Path(item[1]).parent.exists() for item in records), records
        assert sentinel.read_bytes() == b"keep"
        result = {"same_version_update": True, "repeat_start": True, "complete_payload_each_time": True,
                  "unique_payload_directories": True, "exit_cleanup": True, "permanent_data_preserved": True}
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
