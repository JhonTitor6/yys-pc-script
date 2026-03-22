# yys.common - 阴阳师公共模块
# 提供常量、公共操作和战斗流程标准化接口

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
    ClickRange,
    ImageSimilarity,
    BattleEndType,
)
from yys.common.operations import ImageOperations, OperationResult
from yys.common.battle.base import BattleFlow
from yys.common.battle.hooks import BattleHooks
from yys.common.battle.flow import BattleStateMachine, BattlePhase

__all__ = [
    # constants
    'BATTLE_SLEEP_SHORT',
    'BATTLE_SLEEP_MEDIUM',
    'BATTLE_SLEEP_LONG',
    'BATTLE_VICTORY_SLEEP',
    'BATTLE_END_SLEEP',
    'BATTLE_END_CLICK_SLEEP',
    'DEFAULT_CLICK_RANGE',
    'BATTLE_END_CLICK_RANGE_X',
    'BATTLE_END_CLICK_RANGE_Y',
    'OCR_CLICK_RANGE',
    'BattleSleep',
    'ClickRange',
    'ImageSimilarity',
    'BattleEndType',
    # operations
    'ImageOperations',
    'OperationResult',
    # battle
    'BattleFlow',
    'BattleHooks',
    'BattleStateMachine',
    'BattlePhase',
]
