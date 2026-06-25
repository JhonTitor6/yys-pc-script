"""CommonOcr 入口：懒加载 + 转发到 backend。

向后兼容（关键）：
- 旧调用 CommonOcr(['ch_sim', 'en']) 仍能工作（YysYuHunOCR 实际使用方式）
- 旧测试通过 set_reader 注入的 mock reader 仍生效
- ocr() 保留 2× 灰度放大 + 坐标缩回（御魂小字识别依赖）
- get_reader() 标记 deprecated
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from loguru import logger

from win_util.ocr_backends.base import OcrBackend, OcrResult
from win_util.ocr_config import BackendName, get_ocr_backend_name


DEFAULT_SIMILARITY_THRESHOLD = 0.3


class CommonOcr:
    """统一 OCR 入口。

    主要职责：
    - 懒加载选择的 backend（首次访问 .backend 时实例化）
    - 统一 ocr() 流程：灰度 → 2× 放大 → backend.readtext → 坐标缩回
    - 兼容旧 API（set_reader / get_reader），便于历史测试与 YysYuHunOCR 复用

    状态：
    - _backend 初始为 None，访问 .backend 时触发 _create_backend() 实例化
    - _legacy_reader 用于 set_reader 注入的 mock；优先于 backend 实例
    """

    def __init__(
        self,
        reader: Any = None,                    # 旧第一个位置参数
        lang_list: list[str] | None = None,    # 旧/新：传给 easyocr
        gpu: bool = False,                     # 旧：传给 easyocr
        backend: BackendName | None = None,    # 新
        model_dir: Path | None = None,         # 新
        **kwargs,
    ) -> None:
        # 关键兼容：旧 YysYuHunOCR 第 35 行写的是 CommonOcr(['ch_sim', 'en'])，
        # 第一个位置参数是 list 列表。区分逻辑：
        #   - 如果是 list/tuple（lang_list 旧式位置传参），当作 lang_list 用，_legacy_reader = None
        #   - 如果是别的对象（reader），当作注入的 reader 用
        #   - 如果是 None，保持 None
        if isinstance(reader, (list, tuple)) and lang_list is None:
            self._legacy_reader: Any = None
            self._legacy_lang_list: list[str] | None = list(reader)
        else:
            self._legacy_reader = reader
            self._legacy_lang_list = lang_list
        self._legacy_gpu = gpu

        self._backend_name = backend or get_ocr_backend_name()
        self._model_dir = model_dir
        self._backend: Any = None  # 懒加载

    @property
    def backend(self) -> OcrBackend:
        if self._backend is None:
            self._backend = self._create_backend()
        return self._backend

    def _create_backend(self) -> OcrBackend:
        # legacy 优先：测试用 set_reader 注入的 mock 直接用
        if self._legacy_reader is not None:
            return self._legacy_reader

        from win_util.ocr_backends.rapid import RapidOcrBackend
        from win_util.ocr_backends.easy import EasyOcrBackend

        if self._backend_name == "rapidocr":
            return RapidOcrBackend(model_dir=self._model_dir)
        elif self._backend_name == "easyocr":
            return EasyOcrBackend(
                lang_list=self._legacy_lang_list or ["ch_sim", "en"],
                gpu=self._legacy_gpu,
                model_dir=self._model_dir,
            )
        else:  # pragma: no cover
            raise ValueError(f"未知 OCR backend: {self._backend_name}")

    def ocr(self, img: np.ndarray | None, **readtext_kwargs) -> list[OcrResult]:
        """识别图像，返回 [(box, text, conf), ...]（box 坐标为原图坐标系）。

        实现：灰度 → 2× 放大 → backend.readtext → 坐标缩回。
        这个放大对御魂小字识别至关重要（即使是 rapidocr 模式也保留）。
        """
        if img is None:
            return []

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray_resized = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

        ocr_results = self.backend.readtext(gray_resized, **readtext_kwargs)

        # 缩回原图坐标
        rh, rw = gray_resized.shape[:2]
        scale_x = rw / float(w)
        scale_y = rh / float(h)

        scaled_results = []
        for box, text, conf in ocr_results:
            new_box = []
            for (px, py) in box:
                nx = int(round(px / scale_x))
                ny = int(round(py / scale_y))
                new_box.append([nx, ny])
            scaled_results.append((new_box, text, conf))

        return scaled_results

    def contains_text(self, img: np.ndarray | None, target_text, case_sensitive: bool = False) -> bool:
        ocr_results = self.ocr(img)
        detected_texts = [text for _, text, _ in ocr_results]
        if not case_sensitive:
            detected_texts = [t.lower() for t in detected_texts]
            if isinstance(target_text, str):
                target_text = target_text.lower()
            else:
                target_text = [t.lower() for t in target_text]
        if isinstance(target_text, str):
            return any(target_text in t for t in detected_texts)
        return any(any(tg in t for t in detected_texts) for tg in target_text)

    def find_text_position(
        self,
        img: np.ndarray | None,
        target_text,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        case_sensitive: bool = False,
    ) -> tuple[int, int] | None:
        ocr_results = self.ocr(img)
        compare_target = target_text if case_sensitive else target_text.lower()
        best = None
        best_conf = -1.0
        for box, text, conf in ocr_results:
            compare_text = text if case_sensitive else text.lower()
            if compare_target in compare_text and conf >= similarity_threshold:
                if conf > best_conf:
                    best = (box, text, conf)
                    best_conf = conf
        if best is None:
            return None
        box = best[0]
        cx = int((box[0][0] + box[2][0]) / 2)
        cy = int((box[0][1] + box[2][1]) / 2)
        return (cx, cy)

    def find_text_positions(
        self,
        img: np.ndarray | None,
        target_text,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        case_sensitive: bool = False,
    ) -> list[tuple[int, int, float]]:
        ocr_results = self.ocr(img)
        compare_target = target_text if case_sensitive else target_text.lower()
        positions = []
        for box, text, conf in ocr_results:
            compare_text = text if case_sensitive else text.lower()
            if compare_target in compare_text and conf >= similarity_threshold:
                cx = int((box[0][0] + box[2][0]) / 2)
                cy = int((box[0][1] + box[2][1]) / 2)
                positions.append((cx, cy, conf))
        return positions

    def find_text_boxes(
        self,
        img: np.ndarray | None,
        target_text,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        case_sensitive: bool = False,
    ) -> list[tuple[list[list[int]], str, float]]:
        ocr_results = self.ocr(img)
        compare_target = target_text if case_sensitive else target_text.lower()
        return [
            (box, text, conf)
            for box, text, conf in ocr_results
            if (target_text if case_sensitive else target_text.lower()) in (text if case_sensitive else text.lower())
            and conf >= similarity_threshold
        ]

    def find_all_texts(
        self,
        img: np.ndarray | None,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        **readtext_kwargs,
    ) -> list[str]:
        ocr_result = self.ocr(img, **readtext_kwargs)
        return [text for _, text, conf in ocr_result if conf >= similarity_threshold]

    def find_all_text_positions(
        self,
        img: np.ndarray | None,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> list[tuple[int, int, str, float]]:
        ocr_results = self.ocr(img)
        positions = []
        for box, text, conf in ocr_results:
            if conf >= similarity_threshold:
                cx = int((box[0][0] + box[2][0]) / 2)
                cy = int((box[0][1] + box[2][1]) / 2)
                positions.append((cx, cy, text, conf))
        return positions

    # 兼容旧 API
    def get_reader(self) -> Any:
        """已废弃。rapid 模式返回 backend 自身；easyocr 模式返回原生 reader。

        真实调用方：YysYuHunOCR.reader property（yys/util/yys_yu_hun_ocr.py:55-59）
        建议在 YysYuHunOCR 里改用 .ocr(img) 而不是暴露 reader。
        """
        warnings.warn(
            "CommonOcr.get_reader() 已被废弃，请改用 .ocr(img) 入口",
            DeprecationWarning,
            stacklevel=2,
        )
        backend = self.backend
        return getattr(backend, "_reader", backend)

    def set_reader(self, reader: Any) -> None:
        """直接注入 reader（兼容旧测试）。"""
        self._legacy_reader = reader
        self._backend = reader  # 立即生效
