"""ImageFinder.best_match 候选识别契约测试。

产品契约：PRD AC1 / 设计 §4.1——识别器必须能提供阈值以下的最佳候选证据，
供入口准备阶段做"最高候选相似度"解释；接口只读，不发送任何输入。
"""
from __future__ import annotations

import tempfile

import cv2
import numpy as np

from win_util.image import ImageFinder, ImageMatchResult


def _make_finder() -> ImageFinder:
    """构造无窗口依赖的 ImageFinder（截图缓存可能为 None，不触发输入）。"""
    return ImageFinder(env=None, hwnd=None)


def _write_image(path: str, img: np.ndarray) -> str:
    cv2.imwrite(path, img)
    return path


def test_best_match_returns_high_score_for_identical_region() -> None:
    """模板与截图子区域完全一致时，best_match 返回高分与正确位置。"""
    rng = np.random.default_rng(42)
    big = rng.integers(0, 255, (120, 120, 3), dtype=np.uint8)
    small = big[30:50, 30:50].copy()

    with tempfile.TemporaryDirectory() as tmp:
        small_path = _write_image(f"{tmp}/tpl.bmp", small)
        finder = _make_finder()
        result: ImageMatchResult = finder.best_match(big, small_path)

    assert result.is_found
    assert result.similarity >= 0.8
    # 中心点：模板左上角 (30, 30)，尺寸 20x20 → 中心 (40, 40)
    assert result.point == (40, 40)


def test_best_match_returns_below_threshold_candidate() -> None:
    """低于常规阈值 0.8 时，bg_find_pic_all 为空但 best_match 仍返回最佳候选。"""
    rng = np.random.default_rng(7)
    big = rng.integers(0, 255, (120, 120, 3), dtype=np.uint8)
    region = big[60:80, 60:80].copy()
    # 反色模板：结构一致但颜色完全不同，合成分数必然低于常规阈值
    small = (255 - region).astype(np.uint8)

    with tempfile.TemporaryDirectory() as tmp:
        small_path = _write_image(f"{tmp}/tpl_inverted.bmp", small)
        finder = _make_finder()

        all_matches = finder.bg_find_pic_all(big, small_path, similarity=0.8)
        best = finder.best_match(big, small_path)

    assert all_matches == []
    assert best.is_found
    assert best.similarity < 0.8
    assert best.image_path == small_path
    assert best.point != (-1, -1)


def test_best_match_returns_miss_for_none_screenshot() -> None:
    """截图缺失时返回未命中结果而非异常。"""
    finder = _make_finder()
    result: ImageMatchResult = finder.best_match(None, "any/path.bmp")
    assert not result.is_found
    assert result.point == (-1, -1)
    assert result.similarity == 0.0
