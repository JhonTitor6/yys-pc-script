"""OCR backend 抽象接口（与 easyocr.readtext 返回格式一致）。"""
from __future__ import annotations

from typing import Any, Protocol

# 单条识别结果：(box, text, conf)，box 是 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] 像素坐标
OcrResult = tuple[list[list[int]], str, float]


class OcrBackend(Protocol):
    """统一的 OCR backend 接口。"""
    name: str

    def readtext(self, image: Any, **kwargs) -> list[OcrResult]:
        """识别图像中的文字，返回 [(box, text, conf), ...]。"""
        ...
