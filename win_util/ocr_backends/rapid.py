"""RapidOCR backend（onnxruntime 引擎）。

模型位置：
- dev 模式：从 site-packages/rapidocr_onnxruntime/models/ 读（包内默认）
- pack 模式：从 _MEIPASS/rapidocr/ 读（通过 model_dir 显式传绝对路径）

注意：rapidocr-onnxruntime 把字符字典内嵌在 rec onnx 模型内，
所以只需要 3 个 .onnx 文件，不需要额外的字典 .txt。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from win_util.ocr_backends.base import OcrResult


# 模型文件名（实测确认）
_DET_MODEL = "ch_PP-OCRv4_det_infer.onnx"
_REC_MODEL = "ch_PP-OCRv4_rec_infer.onnx"
_CLS_MODEL = "ch_ppocr_mobile_v2.0_cls_infer.onnx"


class RapidOcrBackend:
    """基于 RapidOCR（onnxruntime 引擎）的 OCR backend 实现。

    复用了 easyocr 的 `(box, text, conf)` 返回格式，与 `OcrBackend` Protocol 对齐。
    模型字符字典内嵌在 rec onnx 中，不需要额外的字典文件。
    """

    name = "rapidocr"

    def __init__(self, model_dir: Path | None = None) -> None:
        """初始化 RapidOCR 引擎。

        Args:
            model_dir: 模型目录绝对路径。PyInstaller 打包场景（`pack` 模式）下需显式传入；
                `None` 时使用 `rapidocr_onnxruntime` 包内自带的默认模型（`dev` 模式）。
        """
        from rapidocr_onnxruntime import RapidOCR  # 懒导入

        if model_dir is not None and model_dir.is_dir():
            # pack 模式：用绝对路径覆盖，update_model_path 看到绝对路径会保留
            self._engine = RapidOCR(
                Det_model_path=str(model_dir / _DET_MODEL),
                Rec_model_path=str(model_dir / _REC_MODEL),
                Cls_model_path=str(model_dir / _CLS_MODEL),
            )
            logger.info(f"[RapidOCR] 已初始化（pack 模式），model_dir={model_dir}")
        else:
            # dev 模式：用包内默认模型
            self._engine = RapidOCR()
            logger.info("[RapidOCR] 已初始化（dev 模式，包内默认模型）")

    def readtext(self, image: Any, **kwargs) -> list[OcrResult]:
        """识别图像中的文字。

        Args:
            image: 待识别图像，底层传给 RapidOCR（支持 numpy ndarray、PIL Image、文件路径等）。
            **kwargs: 透传给 RapidOCR 的额外参数。

        Returns:
            识别结果列表，每项为 `(box, text, conf)`，与 easyocr 格式一致；
            box 是 4 点像素坐标 `[[x1,y1], [x2,y2], [x3,y3], [x4,y4]]`，text 是字符串，conf 是置信度。
            无识别结果时返回空列表。
        """
        # RapidOCR(image) 返回 (result, elapsed)；result 是 [[box,text,conf],...]
        result, _elapsed = self._engine(image, **kwargs)
        if kwargs.get("use_det") is False:
            # RapidOCR 关闭检测时返回 [text, conf]，补空 box 维持统一 backend 契约。
            normalized_results: list[OcrResult] = []
            for item in result or []:
                if len(item) == 2:
                    text, confidence = item
                    normalized_results.append(([], text, confidence))
                else:
                    box, text, confidence = item
                    normalized_results.append((box, text, confidence))
            return normalized_results
        return result or []
