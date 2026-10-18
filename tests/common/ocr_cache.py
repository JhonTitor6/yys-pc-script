"""只供测试使用的相同截图 OCR 结果缓存。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np


class OcrImageCache:
    """缓存逐像素相同图像的 OCR 结果，其他图像仍走真实 OCR。"""

    def __init__(self, backend: Any) -> None:
        self._backend = backend
        self._original_ocr = backend.ocr
        self._cache: dict[tuple[tuple[int, ...], str, bytes], list[Any]] = {}
        backend.ocr = self.ocr

    def __getattr__(self, name: str) -> Any:
        return getattr(self._backend, name)

    def ocr(self, image: np.ndarray | None, **kwargs: Any) -> list[Any]:
        """相同截图复用结果副本，避免调用者修改缓存。"""
        if image is None or kwargs:
            return self._original_ocr(image, **kwargs)
        key = (
            image.shape,
            image.dtype.str,
            image.tobytes(),
        )
        if key not in self._cache:
            self._cache[key] = deepcopy(self._original_ocr(image))
        return deepcopy(self._cache[key])
