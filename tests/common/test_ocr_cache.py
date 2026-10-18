"""测试 OCR 截图缓存只复用逐像素相同的输入。"""

from __future__ import annotations

import numpy as np

from tests.common.ocr_cache import OcrImageCache


def test_ocr_cache_reuses_identical_pixels_and_returns_independent_results() -> None:
    class FakeOcr:
        def __init__(self) -> None:
            self.calls = 0

        def ocr(self, image: np.ndarray, **kwargs: object) -> list[object]:
            self.calls += 1
            return [([[0, 0], [1, 0], [1, 1], [0, 1]], "测试", 0.99)]

    backend = FakeOcr()
    cached = OcrImageCache(backend)
    image = np.zeros((2, 2, 3), dtype=np.uint8)

    first = cached.ocr(image)
    first[0][0][0][0] = 99
    assert cached.ocr(image.copy())[0][0][0][0] == 0
    assert backend.calls == 1

    changed = image.copy()
    changed[0, 0, 0] = 1
    cached.ocr(changed)
    assert backend.calls == 2
