"""只启动隔离假后端和显式 smoke-test 宿主，不访问固定 8000 端口。"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime


def main() -> None:
    """为本次烟测分配独立目录与端口，验证实际浏览器回报。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--restore", action="store_true", help="验证旧格式离屏窗口恢复")
    args = parser.parse_args()
    executable = args.executable.resolve()
    if b"YYS_TAURI_STAGE1_SMOKE_ONLY" not in executable.read_bytes():
        raise ValueError("拒绝启动非 smoke-test 宿主，防止写入正常用户目录")
    repo = Path(__file__).resolve().parents[2]
    root = repo / "build" / "tauri-stage1-smoke" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    root.mkdir(parents=True)
    if args.restore:
        (root / "window-state.json").write_text(json.dumps({"width": 900, "height": 650, "x": 99999, "y": 99999}), encoding="utf-8")
    resource_ids = json.loads((repo / "gui/build/tauri-image-resources.json").read_text(encoding="utf-8"))
    image = root / "image-overrides" / resource_ids[0]
    image.parent.mkdir(parents=True)
    image.write_bytes(b"BM")
    token = secrets.token_hex(32)
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            """不把请求 URL 内的测试 token 写入日志。"""

        def reply(self, value: object, status: int = 200) -> None:
            data = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "http://tauri.localhost")
            self.send_header("Access-Control-Allow-Headers", "X-YYS-UI-Token, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self) -> None:
            self.reply({})

        def do_GET(self) -> None:
            if self.path.startswith("/ws/events?"):
                if self.headers.get("Origin") != "http://tauri.localhost" or self.path != f"/ws/events?token={token}":
                    self.reply({}, 403)
                    return
                key = self.headers.get("Sec-WebSocket-Key", "")
                accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                self.send_response(101)
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", accept)
                self.end_headers()
                requests.append("WS /ws/events")
                self.connection.settimeout(15)
                try:
                    self.connection.recv(1024)
                except TimeoutError:
                    pass
                return
            if self.headers.get("X-YYS-UI-Token") != token:
                self.reply({}, 401)
                return
            requests.append("GET " + self.path.split("?")[0])
            if self.path == "/smoke/resource":
                self.reply(resource_ids[0])
                return
            self.reply(None if self.path == "/api/runs/current" else [])

        def do_POST(self) -> None:
            if self.headers.get("X-YYS-UI-Token") != token:
                self.reply({}, 401)
                return
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if self.path == "/smoke/tray":
                (root / "tray-request").touch()
            elif self.path in {"/smoke/report", "/smoke/other"}:
                (root / ("report.json" if self.path.endswith("report") else "other.json")).write_bytes(body)
            else:
                self.reply({}, 404)
                return
            self.reply({})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    assert server.server_port != 8000
    (root / "config.json").write_text(json.dumps({"apiBase": f"http://127.0.0.1:{server.server_port}", "token": token}), encoding="utf-8")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with (root / "host.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen([str(executable)], cwd=repo, env={**os.environ, "YYS_TAURI_SMOKE_ROOT": str(root)}, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                code = process.wait(timeout=80)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise
        report = json.loads((root / "report.json").read_text(encoding="utf-8"))
        other = json.loads((root / "other.json").read_text(encoding="utf-8"))
        native = json.loads((root / "native.json").read_text(encoding="utf-8"))
        (root / "requests.json").write_text(json.dumps(requests, indent=2), encoding="utf-8")
        assert code == 0 and report["ok"], report
        assert other["denied"], other
        assert native["width"] == 900.0 and native["height"] == 650.0, native
        assert not native["decorated"] and native["resizable"] and native["visible_on_screen"], native
        assert native["minimum"] == [800.0, 600.0] and native["resize_left"], native
        assert "WS /ws/events" in requests, requests
        print(json.dumps({"root": str(root), "port": server.server_port, "checks": report["checks"], "unauthorized_window_denied": True, "native": native}, ensure_ascii=False, indent=2))
    finally:
        server.shutdown()
        server.server_close()
        # 测试 token 无须持久保留。
        (root / "config.json").unlink(missing_ok=True)
        print(f"烟测证据目录：{root}")


if __name__ == "__main__":
    main()
