"""测试 ocr_config 读取逻辑。"""
import json
from pathlib import Path

from win_util.ocr_config import (
    DEFAULT_BACKEND,
    VALID_BACKENDS,
    get_ocr_backend_name,
    get_ocr_model_dir,
)


def _write_ui_config(tmp_path: Path, content):
    """在 tmp_path 写入 ui_config.json；None 表示不写文件。"""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    p = cfg_dir / "ui_config.json"
    if content is None:
        return p
    if isinstance(content, str):
        p.write_text(content, encoding="utf-8")
    else:
        p.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return p


def test_missing_ui_config_returns_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert get_ocr_backend_name() == DEFAULT_BACKEND
    assert DEFAULT_BACKEND == "rapidocr"


def test_explicit_rapidocr(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_ui_config(tmp_path, {"ocr_backend": "rapidocr"})
    assert get_ocr_backend_name() == "rapidocr"


def test_explicit_easyocr(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_ui_config(tmp_path, {"ocr_backend": "easyocr"})
    assert get_ocr_backend_name() == "easyocr"


def test_case_insensitive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_ui_config(tmp_path, {"ocr_backend": "  RAPIDOCR  "})
    assert get_ocr_backend_name() == "rapidocr"


def test_invalid_value_falls_back(tmp_path, monkeypatch, caplog):
    import logging
    monkeypatch.chdir(tmp_path)
    _write_ui_config(tmp_path, {"ocr_backend": "garbage"})
    assert get_ocr_backend_name() == DEFAULT_BACKEND


def test_invalid_json_falls_back(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_ui_config(tmp_path, "{ this is not json")
    assert get_ocr_backend_name() == DEFAULT_BACKEND


def test_valid_backends_constant():
    assert "rapidocr" in VALID_BACKENDS
    assert "easyocr" in VALID_BACKENDS


def test_get_ocr_model_dir_returns_none_in_dev():
    """dev 模式（非 frozen）返回 None，由 backend 用包内默认。"""
    assert get_ocr_model_dir("rapidocr") is None
    assert get_ocr_model_dir("easyocr") is None
