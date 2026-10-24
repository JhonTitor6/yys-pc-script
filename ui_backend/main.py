from __future__ import annotations

from copy import deepcopy
import logging
import re

import uvicorn
from uvicorn.config import LOGGING_CONFIG


class RedactTokenFilter(logging.Filter):
    """在格式化之前遮盖 HTTP/WS URL 的鉴权 token，保留访问日志参数结构。"""

    def filter(self, record: logging.LogRecord) -> bool:
        """同时处理直接消息与格式化参数，避免访问日志和连接日志泄露。"""
        def redact(value: object) -> object:
            return re.sub(r"([?&]token=)[^&\s\"']+", r"\1[REDACTED]", value) if isinstance(value, str) else value

        record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact(value) for value in record.args)
        elif isinstance(record.args, dict):
            record.args = {key: redact(value) for key, value in record.args.items()}
        return True


def main() -> None:
    """启动桌面工作台后端服务。"""
    log_config = deepcopy(LOGGING_CONFIG)
    log_config["filters"] = {"redact-token": {"()": RedactTokenFilter}}
    for handler in log_config["handlers"].values():
        handler["filters"] = ["redact-token"]
    uvicorn.run("ui_backend.app:create_app", factory=True, host="127.0.0.1", port=8000, log_config=log_config)


if __name__ == "__main__":
    main()
