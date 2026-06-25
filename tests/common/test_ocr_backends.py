"""测试 OcrBackend Protocol 契约。"""
import pytest
from typing import Any

from win_util.ocr_backends.base import OcrBackend, OcrResult


class _FakeBackend:
    """满足 OcrBackend Protocol 的最小实现。"""
    name = "fake"

    def readtext(self, image: Any, **kwargs) -> list[OcrResult]:
        return [([[0, 0], [10, 0], [10, 10], [0, 10]], "hello", 0.99)]


def test_protocol_accepts_duck_typed_impl():
    backend: OcrBackend = _FakeBackend()  # type: ignore[assignment]
    result = backend.readtext(None)
    assert result[0][1] == "hello"
    assert result[0][2] == pytest.approx(0.99)


def test_ocrresult_is_tuple():
    r: OcrResult = ([[0, 0]], "x", 0.5)
    assert len(r) == 3
