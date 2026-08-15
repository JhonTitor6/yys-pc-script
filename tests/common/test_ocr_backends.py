"""测试 OcrBackend Protocol 契约。"""
import pytest
from typing import Any

from win_util.ocr_backends.base import OcrBackend, OcrResult
from win_util.ocr_backends.rapid import RapidOcrBackend


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


def test_rapid_backend_normalizes_recognition_only_results():
    """产品契约：无检测结果也必须符合统一 OCR 三元组格式。"""
    class _FakeEngine:
        def __init__(self, result: list[Any]) -> None:
            self.result = result

        def __call__(self, image: Any, **kwargs: Any) -> tuple[list[Any], list[float]]:
            return self.result, [0.01]

    backend = RapidOcrBackend.__new__(RapidOcrBackend)
    backend._engine = _FakeEngine([["33871291", 0.99]])

    result = backend.readtext(None, use_det=False, use_cls=False, use_rec=True)

    assert result == [([], "33871291", 0.99)]

    backend._engine = _FakeEngine([
        [[[0, 0], [10, 0], [10, 10], [0, 10]], "text", 0.9],
    ])
    assert backend.readtext(None) == [
        [[[0, 0], [10, 0], [10, 10], [0, 10]], "text", 0.9],
    ]
