"""OCR backend 抽象层。"""
from win_util.ocr_backends.base import OcrBackend, OcrResult
from win_util.ocr_backends.rapid import RapidOcrBackend
from win_util.ocr_backends.easy import EasyOcrBackend

__all__ = ["OcrBackend", "OcrResult", "RapidOcrBackend", "EasyOcrBackend"]
