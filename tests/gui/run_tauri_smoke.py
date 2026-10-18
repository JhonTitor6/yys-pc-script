"""只启动显式 smoke-test 宿主与它自己拉起的假后端，不访问固定 8000 端口。"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def free_loopback_port() -> int:
    """让系统分配一个独立 loopback 端口，不使用生产固定端口。"""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def pid_alive(pid: int) -> bool:
    """用 tasklist 判断子进程是否仍然存活。"""
    completed = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True,
        text=True,
        encoding="mbcs",
        errors="replace",
    )
    return str(pid) in completed.stdout


def run_host(executable: Path, root: Path, repo: Path, timeout: int = 80) -> int:
    """运行宿主并等待退出；超时即视为失败。"""
    env = {**os.environ, "YYS_TAURI_SMOKE_ROOT": str(root)}
    with (root / "host.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [str(executable)],
            cwd=repo,
            env=env,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise


def start_protected_backend(port: int) -> ThreadingHTTPServer:
    """模拟端口上已有受保护后端：鉴权失败返回 403。"""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            """静默处理测试请求。"""

        def do_GET(self) -> None:
            body = b'{"detail":"UI token \xe6\x97\xa0\xe6\x95\x88"}'
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run_blocked(executable: Path, root: Path, repo: Path, port: int) -> None:
    """验证端口被占用时的失败路径：不启动后端、不建窗口、写出明确原因。"""
    server = start_protected_backend(port)
    config = {
        "apiBase": f"http://127.0.0.1:{port}",
        "launch": {
            "program": sys.executable,
            "args": ["-c", "import sys; sys.exit(0)"],
            "cwd": str(repo),
        },
    }
    (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
    try:
        code = run_host(executable, root, repo)
        error_file = root / "startup-error.txt"
        assert code == 1, f"端口冲突时应以 1 退出，实际 {code}"
        assert error_file.exists(), "缺少启动失败原因"
        assert "受保护" in error_file.read_text(encoding="utf-8"), error_file.read_text(
            encoding="utf-8"
        )
        assert not (root / "report.json").exists(), "端口冲突时不应创建窗口"
        print(json.dumps({"root": str(root), "port": port, "blocked": True}, ensure_ascii=False))
    finally:
        server.shutdown()
        server.server_close()
        (root / "config.json").unlink(missing_ok=True)


def run_crash(executable: Path, root: Path, repo: Path, port: int) -> None:
    """验证宿主被强杀时 Job Object 会回收后端，不留下占端口的孤儿进程。"""
    config = {
        "apiBase": f"http://127.0.0.1:{port}",
        "launch": {
            "program": sys.executable,
            "args": [
                str(Path(__file__).with_name("fake_backend.py")),
                "--port",
                str(port),
                "--root",
                str(root),
            ],
            "cwd": str(repo),
        },
    }
    (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
    env = {**os.environ, "YYS_TAURI_SMOKE_ROOT": str(root)}
    try:
        with (root / "host.log").open("w", encoding="utf-8") as log:
            host = subprocess.Popen(
                [str(executable)],
                cwd=repo,
                env=env,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            try:
                deadline = time.monotonic() + 40
                pid = 0
                while time.monotonic() < deadline:
                    pid_file = root / "backend.pid"
                    if pid_file.exists():
                        pid = int(pid_file.read_text(encoding="utf-8"))
                        break
                    time.sleep(0.2)
                assert pid, "宿主未拉起后端"
                time.sleep(1)
                host.kill()
                host.wait(timeout=10)
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline and pid_alive(pid):
                    time.sleep(0.2)
                assert not pid_alive(pid), f"宿主被强杀后后端仍在运行：{pid}"
                print(
                    json.dumps(
                        {
                            "root": str(root),
                            "port": port,
                            "crash_cleanup": True,
                            "backend_pid": pid,
                        },
                        ensure_ascii=False,
                    )
                )
            finally:
                if host.poll() is None:
                    host.kill()
                    host.wait()
    finally:
        (root / "config.json").unlink(missing_ok=True)


def main() -> None:
    """为本次烟测分配独立目录与端口，验证宿主真实拉起后端后的完整链路。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--restore", action="store_true", help="验证旧格式离屏窗口恢复")
    parser.add_argument("--blocked", action="store_true", help="验证端口被占用时的失败路径")
    parser.add_argument("--crash", action="store_true", help="验证宿主被强杀时回收后端")
    args = parser.parse_args()
    executable = args.executable.resolve()
    if b"YYS_TAURI_SMOKE_ONLY" not in executable.read_bytes():
        raise ValueError("拒绝启动非 smoke-test 宿主，防止写入正常用户目录")
    repo = Path(__file__).resolve().parents[2]
    root = repo / "build" / "tauri-smoke" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    root.mkdir(parents=True)
    if args.restore:
        (root / "window-state.json").write_text(
            json.dumps({"width": 900, "height": 650, "x": 99999, "y": 99999}), encoding="utf-8"
        )
    resource_ids = json.loads(
        (repo / "gui/build/tauri-image-resources.json").read_text(encoding="utf-8")
    )
    image = root / "image-overrides" / resource_ids[0]
    image.parent.mkdir(parents=True)
    image.write_bytes(b"BM")
    port = free_loopback_port()
    if args.crash:
        run_crash(executable, root, repo, port)
        return
    if args.blocked:
        run_blocked(executable, root, repo, port)
        return
    config = {
        "apiBase": f"http://127.0.0.1:{port}",
        "launch": {
            "program": sys.executable,
            "args": [
                str(Path(__file__).with_name("fake_backend.py")),
                "--port",
                str(port),
                "--root",
                str(root),
            ],
            "cwd": str(repo),
        },
    }
    (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
    try:
        code = run_host(executable, root, repo)
        assert not (root / "startup-error.txt").exists(), (
            root / "startup-error.txt"
        ).read_text(encoding="utf-8")
        report = json.loads((root / "report.json").read_text(encoding="utf-8"))
        other = json.loads((root / "other.json").read_text(encoding="utf-8"))
        native = json.loads((root / "native.json").read_text(encoding="utf-8"))
        backend_env = json.loads((root / "backend-env.json").read_text(encoding="utf-8"))
        requests = (root / "requests.log").read_text(encoding="utf-8").splitlines()
        assert code == 0 and report["ok"], report
        assert other["denied"], other
        assert native["width"] == 900.0 and native["height"] == 650.0, native
        assert not native["decorated"] and native["resizable"] and native["visible_on_screen"], native
        assert native["minimum"] == [800.0, 600.0] and native["resize_left"], native
        # 宿主必须把 token、用户数据目录、编码和 cwd 传给后端，并在退出时回收它。
        assert backend_env["user_data"] == str(root), backend_env
        assert backend_env["encoding"] == "utf-8", backend_env
        assert Path(backend_env["cwd"]) == repo, backend_env
        pid = int((root / "backend.pid").read_text(encoding="utf-8"))
        assert not pid_alive(pid), f"假后端未被回收：{pid}"
        assert "WS /ws/events" in requests, requests
        assert "GET /api/scripts" in requests, requests
        print(
            json.dumps(
                {
                    "root": str(root),
                    "port": port,
                    "checks": report["checks"],
                    "unauthorized_window_denied": True,
                    "native": native,
                    "backend_env": backend_env,
                    "requests": requests,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        leftover = root / "backend.pid"
        if leftover.exists():
            subprocess.run(
                ["taskkill", "/F", "/PID", leftover.read_text(encoding="utf-8").strip()],
                capture_output=True,
            )
        # 测试配置不保留。
        (root / "config.json").unlink(missing_ok=True)
        print(f"烟测证据目录：{root}")


if __name__ == "__main__":
    main()
