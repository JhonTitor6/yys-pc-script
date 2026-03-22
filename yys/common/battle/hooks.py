# yys.common.battle.hooks - 战斗钩子接口
# 定义战斗流程各阶段的回调接口

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yys.common.constants import BattleEndType


class BattleHooks(ABC):
    """战斗钩子接口"""

    @abstractmethod
    def on_challenge_found(self, position: tuple) -> None:
        """
        挑战按钮被发现时调用

        :param position: 挑战按钮位置 (x, y)
        """
        pass

    @abstractmethod
    def on_challenge_clicked(self) -> None:
        """挑战按钮被点击后调用"""
        pass

    @abstractmethod
    def on_battle_start(self) -> None:
        """战斗开始时调用"""
        pass

    @abstractmethod
    def on_battle_end(self, end_type: 'BattleEndType') -> None:
        """
        战斗结束时调用

        :param end_type: 战斗结束类型
        """
        pass

    @abstractmethod
    def on_victory(self) -> None:
        """战斗胜利时调用"""
        pass

    @abstractmethod
    def on_defeat(self) -> None:
        """战斗失败时调用"""
        pass

    @abstractmethod
    def should_continue(self) -> bool:
        """
        检查是否继续战斗

        :return: True 继续战斗，False 停止战斗
        """
        pass
