"""EasyOCR backend（保留兜底，标 deprecated）。"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from loguru import logger

from win_util.ocr_backends.base import OcrResult


class EasyOcrBackend:
    """基于 EasyOCR 的 OCR backend 实现。

    已 deprecated：torch 依赖巨大，推荐改用 ``RapidOcrBackend``。
    本类保留作为 ``ocr_backend=easyocr`` 配置项的兜底实现。
    复用了 easyocr 原生返回格式，与 ``OcrBackend`` Protocol 对齐。
    """

    name: str = "easyocr"

    def __init__(
        self,
        lang_list: list[str] | None = None,
        gpu: bool = False,
        model_dir: Path | None = None,
    ) -> None:
        """初始化 EasyOCR 引擎。

        Args:
            lang_list: easyocr 支持的语言代码列表，默认 ``["ch_sim", "en"]``（简体中文 + 英文）。
            gpu: 是否使用 GPU 加速。默认 ``False``（CPU 模式）。
            model_dir: easyocr 模型存储目录绝对路径；``None`` 时使用 easyocr 默认下载目录。
        """
        warnings.warn(
            "EasyOcrBackend 已被弃用，torch 依赖巨大，建议改用 rapidocr-onnxruntime",
            DeprecationWarning,
            stacklevel=2,
        )
        import easyocr  # 懒导入

        if lang_list is None:
            lang_list = ["ch_sim", "en"]
        kwargs: dict[str, Any] = {}
        if gpu:
            kwargs["gpu"] = True
        if model_dir is not None:
            kwargs["model_storage_directory"] = str(model_dir)
        self._reader = easyocr.Reader(lang_list, **kwargs)
        logger.info(f"[EasyOCR] 已初始化，lang_list={lang_list}, model_dir={model_dir}")

    def readtext(self, image: Any, **kwargs) -> list[OcrResult]:
        """识别图像中的文字。

        Args:
            image: 待识别图像，底层透传给 easyocr（支持 numpy ndarray、PIL Image、文件路径等）。
            **kwargs: 透传给 easyocr ``readtext`` 的额外参数。

        Returns:
            识别结果列表，每项为 ``(box, text, conf)``，与 easyocr 原生格式一致；
            box 是 4 点像素坐标 ``[[x1,y1], [x2,y2], [x3,y3], [x4,y4]]``，text 是字符串，conf 是置信度。
            无识别结果时返回 easyocr 原生空列表。
        """
        return self._reader.readtext(image, **kwargs)
