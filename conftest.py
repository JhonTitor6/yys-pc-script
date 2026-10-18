"""仓库级 pytest fixtures。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.common.ocr_cache import OcrImageCache


@pytest.fixture(scope="session")
def cached_test_ocr() -> OcrImageCache:
    """复用真实 OCR 后端，并缓存逐像素相同截图的识别结果。"""
    from tests.common.ocr_cache import OcrImageCache
    from win_util.ocr import CommonOcr

    return OcrImageCache(CommonOcr())
