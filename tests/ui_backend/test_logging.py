"""桌面后端鉴权日志脱敏契约。"""
from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

import pytest
from uvicorn.config import LOGGING_CONFIG
from uvicorn.logging import AccessFormatter

from ui_backend.main import RedactTokenFilter, main


def test_http_access_log_redacts_query_without_breaking_formatter() -> None:
    """产品契约：设计要求日志不得泄露 token，且访问日志仍包含路径与状态。"""
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                               ("127.0.0.1:1234", "GET", "/api/image?x=1&token=secret&variant=effective", "1.1", 200), None)
    assert RedactTokenFilter().filter(record)
    rendered = AccessFormatter(fmt="%(request_line)s %(status_code)s", use_colors=False).format(record)
    assert "secret" not in rendered
    assert "token=[REDACTED]&variant=effective" in rendered
    assert "200" in rendered


@pytest.mark.parametrize("message,args", [
    ('WebSocket %s [accepted]', ('/ws/events?token=secret',)),
    ('connection /ws/events?token=secret', ()),
    ('connection %(path)s', {"path": '/ws/events?token=secret&after_seq=3'}),
])
def test_connection_logs_redact_token(message: str, args: Any) -> None:
    """产品契约：WebSocket 连接日志的直接消息、元组及字典参数均不得含 token。"""
    record = logging.LogRecord("uvicorn.error", logging.INFO, "", 0, message, (args,) if isinstance(args, dict) else args, None)
    RedactTokenFilter().filter(record)
    assert "secret" not in record.getMessage()
    assert "token=[REDACTED]" in record.getMessage()


def test_entry_config_filters_all_uvicorn_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """产品契约：正式入口的访问与连接日志都经过脱敏，不修改 Uvicorn 默认配置。"""
    before = deepcopy(LOGGING_CONFIG)
    captured: dict[str, Any] = {}
    monkeypatch.setattr("ui_backend.main.uvicorn.run", lambda *args, **kwargs: captured.update(kwargs))
    main()
    config = captured["log_config"]
    assert config["filters"]["redact-token"]["()"] is RedactTokenFilter
    assert all(handler["filters"] == ["redact-token"] for handler in config["handlers"].values())
    assert LOGGING_CONFIG == before
