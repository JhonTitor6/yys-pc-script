"""隔离烟测用的假后端；由宿主按真实启动路径拉起，不导入业务代码。"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main() -> None:
    """绑定指定 loopback 端口，只回应烟测需要的接口。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    token = os.environ.get("YYS_UI_TOKEN", "")
    if len(token) < 32:
        raise SystemExit("缺少宿主导入的 UI token")
    resource_ids = json.loads(
        (Path.cwd() / "gui" / "build" / "tauri-image-resources.json").read_text(encoding="utf-8")
    )
    (root / "backend-env.json").write_text(
        json.dumps(
            {
                "user_data": os.environ.get("YYS_USER_DATA_DIR"),
                "encoding": os.environ.get("PYTHONIOENCODING"),
                "cwd": str(Path.cwd()),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "backend.pid").write_text(str(os.getpid()), encoding="utf-8")
    log = (root / "requests.log").open("w", encoding="utf-8")

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

        def authorized(self) -> bool:
            provided = self.headers.get("X-YYS-UI-Token") or self._query_token()
            return provided == token

        def _query_token(self) -> str:
            if "?" not in self.path:
                return ""
            query = self.path.split("?", 1)[1]
            for part in query.split("&"):
                key, _, value = part.partition("=")
                if key == "token":
                    return value
            return ""

        def do_OPTIONS(self) -> None:
            self.reply({})

        def do_GET(self) -> None:
            if self.path.startswith("/ws/events?"):
                if self.headers.get("Origin") != "http://tauri.localhost":
                    self.reply({}, 403)
                    return
                if self._query_token() != token:
                    self.reply({}, 403)
                    return
                key = self.headers.get("Sec-WebSocket-Key", "")
                accept = base64.b64encode(
                    hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
                ).decode()
                self.send_response(101)
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", accept)
                self.end_headers()
                log.write("WS /ws/events\n")
                log.flush()
                self.connection.settimeout(15)
                try:
                    self.connection.recv(1024)
                except TimeoutError:
                    pass
                return
            if not self.authorized():
                self.reply({}, 403)
                return
            log.write("GET " + self.path.split("?")[0] + "\n")
            log.flush()
            if self.path == "/smoke/resource":
                self.reply(resource_ids[0])
                return
            if self.path == "/api/scripts":
                self.reply([{"script_id": "soul_raid", "name": "御魂"}])
                return
            if self.path.startswith("/smoke/image"):
                png = base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
                )
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Access-Control-Allow-Origin", "http://tauri.localhost")
                self.send_header("Content-Length", str(len(png)))
                self.end_headers()
                self.wfile.write(png)
                return
            self.reply(None if self.path == "/api/runs/current" else [])

        def do_POST(self) -> None:
            if not self.authorized():
                self.reply({}, 403)
                return
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if self.path == "/smoke/tray":
                (root / "tray-request").touch()
            elif self.path == "/smoke/report":
                (root / "report.json").write_bytes(body)
            elif self.path == "/smoke/other":
                (root / "other.json").write_bytes(body)
            else:
                self.reply({}, 404)
                return
            self.reply({})

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"fake backend listening on {server.server_port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        log.close()
        (root / "backend.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
