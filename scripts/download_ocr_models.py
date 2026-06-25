"""
预复制 OCR backend 模型到 assets/，便于 PyInstaller 打包。

执行逻辑：
  - rapidocr: 从 site-packages/rapidocr_onnxruntime/models/ 复制 3 个 .onnx
              到 <project>/assets/ocr_models_rapid/
  - easyocr:  实例化 easyocr.Reader 触发下载到 ~/.EasyOCR/model/，
              然后复制到 <project>/assets/ocr_models_easy/

用法：
  python scripts/download_ocr_models.py                  # 默认 rapidocr
  python scripts/download_ocr_models.py --backend rapidocr
  python scripts/download_ocr_models.py --backend easyocr

幂等：assets/ocr_models_<backend>/ 已存在且非空则跳过。
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# backend → assets/ 子目录后缀映射（单一真相源）
_BACKEND_DIR_SUFFIX = {
    "rapidocr": "rapid",
    "easyocr": "easy",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="预复制 OCR 模型")
    p.add_argument(
        "--backend",
        choices=["rapidocr", "easyocr"],
        default="rapidocr",
        help="OCR backend（默认 rapidocr）",
    )
    return p.parse_args()


def is_already_downloaded(backend: str) -> bool:
    suffix = _BACKEND_DIR_SUFFIX[backend]
    target = PROJECT_ROOT / "assets" / f"ocr_models_{suffix}"
    if not target.is_dir():
        return False
    return any(target.iterdir())


def ensure_rapidocr_models() -> Path:
    """从 rapidocr_onnxruntime pip 包内复制模型到 assets/。"""
    import rapidocr_onnxruntime  # noqa: F401  仅用于触发模块检查

    src = Path(rapidocr_onnxruntime.__file__).resolve().parent / "models"
    if not src.is_dir():
        raise FileNotFoundError(
            f"rapidocr-onnxruntime 包内模型目录不存在: {src}\n"
            f"提示：pip install --force-reinstall rapidocr-onnxruntime"
        )
    target = PROJECT_ROOT / "assets" / f"ocr_models_{_BACKEND_DIR_SUFFIX['rapidocr']}"
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, target)
    return target


def ensure_easyocr_models() -> Path:
    """触发 easyocr 下载到 ~/.EasyOCR/model/，复制到 assets/。"""
    import easyocr  # type: ignore  # noqa: F401

    user_dir = Path.home() / ".EasyOCR" / "model"
    user_dir.mkdir(parents=True, exist_ok=True)
    # 这一步会按需下载缺失模型到 user_dir
    _ = easyocr.Reader(["ch_sim", "en"], gpu=False, model_storage_directory=str(user_dir))

    target = PROJECT_ROOT / "assets" / f"ocr_models_{_BACKEND_DIR_SUFFIX['easyocr']}"
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(user_dir, target)
    return target


def main() -> int:
    args = parse_args()
    backend = args.backend

    if is_already_downloaded(backend):
        print(f"[download_ocr_models] {backend} 模型已存在，跳过")
        return 0

    print(f"[download_ocr_models] 处理 {backend} 模型...")
    try:
        if backend == "rapidocr":
            target = ensure_rapidocr_models()
        else:
            target = ensure_easyocr_models()
    except Exception as exc:
        print(f"[download_ocr_models] 失败: {exc}", file=sys.stderr)
        return 1

    print(f"[download_ocr_models] 已就绪 -> {target}")
    print(f"[download_ocr_models] 文件清单:")
    for name in sorted(target.iterdir()):
        size_mb = name.stat().st_size / 1024 / 1024
        print(f"  {size_mb:6.1f} MB  {name.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
