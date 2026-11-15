from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np
from pytest import MonkeyPatch

from win_util.image import ScreenCapture
from yys.qilingtancha import qilingtancha_script as script


def test_click_tancha_captures_and_matches_using_hwnd(monkeypatch: MonkeyPatch) -> None:
    template = Path(__file__).parent / "images" / "qiling_tancha.bmp"
    frame = cv2.imread(str(template))
    assert frame is not None

    def capture(capture_target: ScreenCapture) -> np.ndarray:
        assert capture_target.hwnd == 123
        return frame

    click = Mock()
    monkeypatch.setattr(ScreenCapture, "capture_window_region", capture)
    monkeypatch.setattr(script, "bg_left_click_with_range", click)

    script.click_tancha(123)

    height, width = frame.shape[:2]
    click.assert_called_once_with(123, (width // 2, height // 2), x_range=20, y_range=20)


def test_main_only_counts_wins(monkeypatch: MonkeyPatch) -> None:
    scenes = iter(["", "battle_end_loss.bmp", "battle_end_1.bmp"] + ["battle_end_success.bmp"] * 100)
    current_scene = ""

    def next_scene(hwnd: int) -> None:
        nonlocal current_scene
        current_scene = next(scenes)

    def find(hwnd: int, path: str, similarity: float = 0.8) -> tuple[int, int]:
        return (100, 100) if Path(path).name == current_scene else (-1, -1)

    logger = Mock()
    monkeypatch.setattr(script, "find_window", lambda: 123)
    monkeypatch.setattr(script, "click_tancha", next_scene)
    monkeypatch.setattr(script, "_bg_find_pic", find)
    monkeypatch.setattr(script, "bg_left_click_with_range", lambda hwnd, point, **_: point != (-1, -1))
    monkeypatch.setattr(script.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(script, "logger", logger)

    script.main()

    assert next(scenes, None) is None
    assert logger.success.call_count == 100
    assert logger.success.call_args.args == ("通关次数：100",)
