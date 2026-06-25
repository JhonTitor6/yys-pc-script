"""OCR backend 配置读取（仅读 config/ui_config.json）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from loguru import logger

BackendName = Literal["rapidocr", "easyocr"]
DEFAULT_BACKEND: BackendName = "rapidocr"
VALID_BACKENDS: tuple[str, ...] = ("rapidocr", "easyocr")


def _config_path() -> Path:
    """dev/pack 模式下都基于 cwd（pack 模式 cwd = exe 同目录）。"""
    return Path("config") / "ui_config.json"


def get_ocr_backend_name() -> BackendName:
    """从 ui_config.json 读取 ocr_backend，缺失/非法则返回默认。"""
    p = _config_path()
    if not p.is_file():
        return DEFAULT_BACKEND
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"[ocr_config] 读取 {p} 失败: {exc}，回退到 {DEFAULT_BACKEND}")
        return DEFAULT_BACKEND

    raw = str(data.get("ocr_backend", DEFAULT_BACKEND)).strip().lower()
    if raw not in VALID_BACKENDS:
        logger.warning(
            f"[ocr_config] ocr_backend={raw!r} 非法，"
            f"有效值 {VALID_BACKENDS}，回退到 {DEFAULT_BACKEND}"
        )
        return DEFAULT_BACKEND
    return raw  # type: ignore[return-value]


def get_ocr_model_dir(backend: BackendName) -> Path | None:
    """pack 模式下从 _MEIPASS 读模型目录；dev 模式返回 None（用包内默认）。

    目录约定（与 build_backend.spec datas 注入路径对齐）：
    - rapidocr  → _MEIPASS/rapidocr/  （见 Task 10）
    - easyocr   → _MEIPASS/.EasyOCR/model/
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        if backend == "rapidocr":
            candidate = meipass / "rapidocr"
            return candidate if candidate.is_dir() else None
        candidate = meipass / ".EasyOCR" / "model"
        return candidate if candidate.is_dir() else None
    return None
