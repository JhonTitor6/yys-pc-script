import cv2
import numpy as np
import pytest

from yys.douji.douji_script import DouJi, _find_douji_slot_anchors, _find_douji_slot_point


def test_douji_config_exposes_target_slot() -> None:
    fields = {field["key"]: field for field in DouJi.get_config_schema()}

    assert fields["target_slot"]["default"] == 2
    assert fields["target_slot"]["min_value"] == 1
    assert fields["target_slot"]["max_value"] == 5


def _build_battle_frame(bar_positions: list[tuple[int, int]]) -> np.ndarray:
    """构造带五个己方血条和一个中线干扰血条的测试画面。"""
    frame = np.zeros((640, 1136, 3), dtype=np.uint8)
    hsv_color = np.array([[[20, 180, 240]]], dtype=np.uint8)
    bar_color = tuple(int(value) for value in cv2.cvtColor(hsv_color, cv2.COLOR_HSV2BGR)[0, 0])
    for x, y in bar_positions + [(535, 260)]:
        cv2.rectangle(frame, (x, y), (x + 88, y + 4), bar_color, -1)
    return frame


def test_douji_slot_anchors_are_sorted_and_ignore_middle_interference() -> None:
    frame = _build_battle_frame([(160, 330), (360, 320), (535, 410), (710, 290), (910, 350)])

    anchors = _find_douji_slot_anchors(frame)

    assert anchors is not None
    assert [x for x, _ in anchors] == [204, 404, 579, 754, 954]
    assert anchors[2][1] == 412


def test_douji_slot_point_uses_slot_offset() -> None:
    frame = _build_battle_frame([(160, 330), (360, 320), (535, 410), (710, 290), (910, 350)])

    assert _find_douji_slot_point(frame, 2) == (412, 382)
    assert _find_douji_slot_point(frame, 4) == (757, 402)


def test_douji_slot_point_ignores_noise_that_shifts_slot_numbers() -> None:
    """产品契约：画面干扰不得把己方左1误报为配置的左2。"""
    frame = _build_battle_frame([(160, 330), (360, 320), (535, 410), (710, 290), (910, 350)])
    hsv_color = np.array([[[20, 180, 240]]], dtype=np.uint8)
    bar_color = tuple(int(value) for value in cv2.cvtColor(hsv_color, cv2.COLOR_HSV2BGR)[0, 0])
    for x, y in [(16, 300), (786, 370), (866, 390)]:
        cv2.rectangle(frame, (x, y), (x + 88, y + 4), bar_color, -1)

    assert _find_douji_slot_point(frame, 2) == (412, 382)


def test_douji_slot_point_rejects_invalid_slot_and_incomplete_frame() -> None:
    frame = _build_battle_frame([(160, 330), (360, 320), (535, 410), (710, 290)])

    with pytest.raises(ValueError, match="1-5"):
        _find_douji_slot_point(frame, 6)
    assert _find_douji_slot_point(frame, 1) is None


def test_douji_target_failure_does_not_stop_script(monkeypatch: pytest.MonkeyPatch) -> None:
    """定位时仍在加载的画面只进入待重试，不得停止脚本。"""
    import yys.douji.douji_script as douji_script
    import yys.common.event_script_base as event_script_base

    class FakeFinder:
        screenshot_cache = np.zeros((640, 1136, 3), dtype=np.uint8)

        def update_screenshot_cache(self) -> None:
            return None

    class FakeLogger:
        messages: list[str] = []

        def debug(self, message: str) -> None:
            self.messages.append(message)

        def info(self, message: str) -> None:
            self.messages.append(message)

        def warning(self, message: str) -> None:
            self.messages.append(message)

    script = object.__new__(DouJi)
    script.image_finder = FakeFinder()
    script.target_slot = 2
    script._douji_target_pending = False
    script.max_battle_count = 30
    script._cur_battle_count = 0
    script.logger = FakeLogger()
    clicks: list[tuple[tuple[int, int], dict[str, int]]] = []
    script.bg_left_click = lambda point, **kwargs: clicks.append((point, kwargs))
    script.stop = lambda: pytest.fail("己方槽位定位失败不应停止脚本")
    monkeypatch.setattr(douji_script, "random_sleep", lambda *_: None)
    monkeypatch.setattr(douji_script.time, "sleep", lambda *_: None)
    monkeypatch.setattr(event_script_base, "random_sleep", lambda *_: None)

    script._on_change_to_auto_battle((100, 200))

    assert script._douji_target_pending is True
    assert clicks == [((100, 200), {})]
    assert "继续等待" in script.logger.messages[0]

    script.image_finder.screenshot_cache = _build_battle_frame(
        [(160, 330), (360, 320), (535, 410), (710, 290), (910, 350)]
    )
    script.after_iteration()

    assert script._douji_target_pending is False
    assert clicks[-1] == ((412, 382), {"x_range": 0, "y_range": 0})


def test_douji_victory_counts_once_per_battle(monkeypatch: pytest.MonkeyPatch) -> None:
    """产品契约：同场胜利结算重复识别只计一次，下一场可继续计数。"""
    import yys.douji.douji_script as douji_script

    script = object.__new__(DouJi)
    script._cur_battle_victory_count = 0
    script._douji_target_pending = False
    script._douji_victory_counted = False
    clicks: list[tuple[int, int]] = []
    script.bg_left_click = clicks.append
    monkeypatch.setattr(douji_script.time, "sleep", lambda *_: None)

    script._on_battle_victory((100, 200))
    script._on_battle_victory((100, 200))

    assert script._cur_battle_victory_count == 1
    assert clicks == [(100, 200), (100, 200)]

    script._on_douji_zhan((300, 400))
    script._on_battle_victory((100, 200))

    assert script._cur_battle_victory_count == 2
