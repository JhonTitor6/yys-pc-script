# yys.common.constants - 统一常量管理
# 提供战斗、点击、图像识别等相关常量

from enum import Enum

# ============ 具体常量值（向后兼容） ============
BATTLE_SLEEP_SHORT = 0.5
BATTLE_SLEEP_MEDIUM = 1.0
BATTLE_SLEEP_LONG = 2.0
BATTLE_VICTORY_SLEEP = 1.0
BATTLE_END_SLEEP = 2.0
BATTLE_END_CLICK_SLEEP = 0.5

DEFAULT_CLICK_RANGE = 20
BATTLE_END_CLICK_RANGE_X = 30
BATTLE_END_CLICK_RANGE_Y = 50
OCR_CLICK_RANGE = 10

# ============ 类常量（推荐使用） ============
class BattleSleep:
    """战斗等待时间常量（秒）"""
    SHORT = 0.5      # 短等待
    MEDIUM = 1.0     # 中等等待
    LONG = 2.0       # 长等待
    VICTORY = 1.0    # 胜利后等待
    END = 2.0        # 战斗结束等待
    CLICK_AFTER = 0.5  # 点击后等待


class ClickRange:
    """点击偏移范围常量"""
    DEFAULT = 20           # 默认点击偏移
    BATTLE_END_X = 30     # 战斗结束点击X偏移
    BATTLE_END_Y = 50     # 战斗结束点击Y偏移
    OCR = 10              # OCR点击偏移


class ImageSimilarity:
    """图像相似度常量"""
    DEFAULT = 0.8  # 默认相似度
    HIGH = 0.9     # 高相似度要求
    LOW = 0.7      # 低相似度要求


class BattleEndType(Enum):
    """战斗结束类型枚举"""
    VICTORY = "victory"  # 胜利
    DEFEAT = "defeat"    # 失败
    OTHER = "other"      # 其他（超时等）
