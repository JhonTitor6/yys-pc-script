from __future__ import annotations

import uvicorn


def main() -> None:
    """启动桌面工作台后端服务。"""
    uvicorn.run("ui_backend.app:create_app", factory=True, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
