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


def test_douji_slot_point_rejects_invalid_slot_and_incomplete_frame() -> None:
    frame = _build_battle_frame([(160, 330), (360, 320), (535, 410), (710, 290)])

    with pytest.raises(ValueError, match="1-5"):
        _find_douji_slot_point(frame, 6)
    assert _find_douji_slot_point(frame, 1) is None
