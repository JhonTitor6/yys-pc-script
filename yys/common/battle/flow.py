# yys.common.battle.flow - 战斗状态机接口（预留）
# 提供战斗阶段的状态机定义

from enum import Enum
from typing import Optional, Dict, Any


class BattlePhase(Enum):
    """战斗阶段枚举"""
    IDLE = "idle"                       # 空闲状态
    WAIT_CHALLENGE = "wait_challenge"   # 等待挑战按钮
    CLICK_CHALLENGE = "click_challenge" # 点击挑战按钮
    WAIT_BATTLE_START = "wait_battle_start"  # 等待战斗开始
    BATTLE_RUNNING = "battle_running"   # 战斗进行中
    WAIT_BATTLE_END = "wait_battle_end" # 等待战斗结束
    BATTLE_END = "battle_end"           # 战斗结束


class BattleStateMachine:
    """
    战斗状态机（预留接口）

    提供战斗流程的状态转换管理，当前为预留接口，
    后续可用于实现更复杂的状态机逻辑
    """

    def __init__(self):
        """初始化状态机"""
        self.current_phase: BattlePhase = BattlePhase.IDLE
        self.phase_data: Dict[str, Any] = {}

    def transition_to(self, new_phase: BattlePhase, data: Optional[Dict] = None) -> None:
        """
        状态转换

        :param new_phase: 新状态
        :param data: 状态转换时携带的数据
        """
        self.current_phase = new_phase
        if data:
            self.phase_data.update(data)

    def get_current_phase(self) -> BattlePhase:
        """
        获取当前状态

        :return: 当前战斗阶段
        """
        return self.current_phase
