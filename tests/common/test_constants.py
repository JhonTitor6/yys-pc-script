# tests.common.test_constants - 常量模块测试

import pytest
from yys.common.constants import (
    BATTLE_SLEEP_SHORT,
    BATTLE_SLEEP_MEDIUM,
    BATTLE_SLEEP_LONG,
    BATTLE_VICTORY_SLEEP,
    BATTLE_END_SLEEP,
    BATTLE_END_CLICK_SLEEP,
    DEFAULT_CLICK_RANGE,
    BATTLE_END_CLICK_RANGE_X,
    BATTLE_END_CLICK_RANGE_Y,
    OCR_CLICK_RANGE,
    BattleSleep,
    BattleEndType,
    ClickRange,
    ImageSimilarity,
)


def test_battle_sleep_values():
    """测试战斗等待时间常量值"""
    assert BATTLE_SLEEP_SHORT == 0.5
    assert BATTLE_SLEEP_MEDIUM == 1.0
    assert BATTLE_SLEEP_LONG == 2.0
    assert BATTLE_VICTORY_SLEEP == 1.0
    assert BATTLE_END_SLEEP == 2.0
    assert BATTLE_END_CLICK_SLEEP == 0.5


def test_battle_sleep_class():
    """测试 BattleSleep 类常量"""
    assert BattleSleep.SHORT == 0.5
    assert BattleSleep.MEDIUM == 1.0
    assert BattleSleep.LONG == 2.0
    assert BattleSleep.VICTORY == 1.0
    assert BattleSleep.END == 2.0
    assert BattleSleep.CLICK_AFTER == 0.5


def test_battle_end_type():
    """测试 BattleEndType 枚举"""
    assert BattleEndType.VICTORY.value == "victory"
    assert BattleEndType.DEFEAT.value == "defeat"
    assert BattleEndType.OTHER.value == "other"


def test_click_range_constants():
    """测试点击偏移常量"""
    assert DEFAULT_CLICK_RANGE == 20
    assert BATTLE_END_CLICK_RANGE_X == 30
    assert BATTLE_END_CLICK_RANGE_Y == 50
    assert OCR_CLICK_RANGE == 10


def test_click_range_class():
    """测试 ClickRange 类常量"""
    assert ClickRange.DEFAULT == 20
    assert ClickRange.BATTLE_END_X == 30
    assert ClickRange.BATTLE_END_Y == 50
    assert ClickRange.OCR == 10


def test_image_similarity_constants():
    """测试图像相似度常量"""
    assert ImageSimilarity.DEFAULT == 0.8
    assert ImageSimilarity.HIGH == 0.9
    assert ImageSimilarity.LOW == 0.7
