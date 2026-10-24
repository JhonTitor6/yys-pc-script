"""ROI 识别区域：裁剪边界与坐标回加的契约测试。"""

from __future__ import annotations

import numpy as np

from win_util.ocr import CommonOcr


class RecordingBackend:
    """记录收到的图像与参数，返回固定文本框的假 backend。"""

    def __init__(self, box: list[list[int]], text: str = "测试文本", conf: float = 0.99) -> None:
        self.box = box
        self.text = text
        self.conf = conf
        self.shapes: list[tuple[int, ...]] = []
        self.kwargs: list[dict] = []

    def readtext(self, image: np.ndarray, **kwargs):
        self.shapes.append(image.shape)
        self.kwargs.append(kwargs)
        return [(self.box, self.text, self.conf)]


def make_ocr(box: list[list[int]]) -> tuple[CommonOcr, RecordingBackend]:
    backend = RecordingBackend(box)
    return CommonOcr(reader=backend), backend


def test_roi_crops_image_and_offsets_boxes() -> None:
    """产品契约：ROI 只缩小识别面积，返回坐标仍是整图坐标系。"""
    ocr, backend = make_ocr([[10, 5], [40, 5], [40, 15], [10, 15]])
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    results = ocr.ocr(image, roi=(50, 20, 150, 80))

    # backend 收到的是裁剪后 100×60、再放大 2 倍（200×120）的灰度图。
    assert backend.shapes == [(120, 200)]
    box = results[0][0]
    # 10/2+50=55、5/2+20=22；40/2+50=70、15/2+20=28。
    assert box == [[55, 22], [70, 22], [70, 28], [55, 28]]


def test_without_roi_coordinates_unchanged() -> None:
    """产品契约：不传 ROI 时行为与改动前一致。"""
    ocr, backend = make_ocr([[10, 5], [40, 5], [40, 15], [10, 15]])
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    results = ocr.ocr(image)

    assert backend.shapes == [(200, 400)]
    assert results[0][0] == [[5, 2], [20, 2], [20, 8], [5, 8]]


def test_find_text_position_uses_absolute_coordinates() -> None:
    """产品契约：带 ROI 时点击坐标必须落在整图上。"""
    ocr, _backend = make_ocr([[10, 5], [40, 5], [40, 15], [10, 15]])
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    position = ocr.find_text_position(image, "测试", roi=(50, 20, 150, 80))

    assert position == (62, 25)


def test_roi_is_clamped_to_image_bounds() -> None:
    """产品契约：越界 ROI 收敛到图像范围内，不能抛异常。"""
    ocr, backend = make_ocr([[0, 0], [10, 0], [10, 10], [0, 10]])
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    ocr.ocr(image, roi=(150, 80, 500, 500))

    # 有效区域是 x 150..200、y 80..100，放大 2 倍后为 100×40。
    assert backend.shapes == [(40, 100)]


def test_empty_roi_returns_empty_without_calling_backend() -> None:
    """产品契约：空 ROI 直接返回空结果，不触发推理。"""
    ocr, backend = make_ocr([[0, 0], [10, 0], [10, 10], [0, 10]])
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    assert ocr.ocr(image, roi=(150, 80, 100, 10)) == []
    assert backend.shapes == []


def test_readtext_kwargs_still_forwarded_with_roi() -> None:
    """产品契约：ROI 不能吞掉 use_det/allowlist 等透传参数。"""
    ocr, backend = make_ocr([[0, 0], [10, 0], [10, 10], [0, 10]])
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    ocr.find_all_texts(image, roi=(10, 10, 60, 40), use_det=False, allowlist="0123456789")

    assert backend.kwargs[-1] == {"use_det": False, "allowlist": "0123456789"}
