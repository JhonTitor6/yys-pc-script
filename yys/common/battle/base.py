# yys.common.battle.base - 战斗流程基类
# 提供标准化的战斗流程实现

import time
from abc import ABC, abstractmethod
from typing import List, Dict, TYPE_CHECKING

from yys.common.constants import BattleSleep, ClickRange, ImageSimilarity, BattleEndType
from yys.common.operations import ImageOperations, OperationResult
from yys.common.battle.hooks import BattleHooks

if TYPE_CHECKING:
    pass


class BattleFlow(ABC):
    """
    战斗流程基类

    定义标准化的战斗流程，子类可通过覆盖方法自定义特定行为
    """

    # 战斗结束图片配置列表，子类可覆盖
    BATTLE_END_CONFIGS: List[Dict] = []

    def __init__(
        self,
        script_name: str,
        challenge_image: str,
        operations: ImageOperations,
        hooks: BattleHooks,
        max_battle_count: int = 100
    ):
        """
        初始化战斗流程

        :param script_name: 脚本名称
        :param challenge_image: 挑战按钮图片路径
        :param operations: 图像操作实例
        :param hooks: 战斗钩子实例
        :param max_battle_count: 最大战斗次数
        """
        self.script_name = script_name
        self.challenge_image = challenge_image
        self.operations = operations
        self.hooks = hooks
        self.max_battle_count = max_battle_count
        self.current_battle_count = 0
        self.current_victory_count = 0

    def execute_battle_loop(self) -> None:
        """执行战斗循环"""
        while self.hooks.should_continue():
            self._wait_challenge()
            self._click_challenge()
            self._wait_battle_start()
            end_type = self._wait_battle_end()
            self._handle_battle_end(end_type)

    def _wait_challenge(self) -> None:
        """等待挑战按钮出现"""
        result = self.operations.wait_for_image(
            self.challenge_image,
            timeout=30,
            similarity=ImageSimilarity.DEFAULT
        )
        if result.success and result.position:
            self.hooks.on_challenge_found(result.position)

    def _click_challenge(self) -> None:
        """点击挑战按钮"""
        result = self.operations.find_and_click(
            self.challenge_image,
            x_range=ClickRange.DEFAULT,
            y_range=ClickRange.DEFAULT
        )
        if result.success:
            self.hooks.on_challenge_clicked()

    def _wait_battle_start(self) -> None:
        """等待战斗开始"""
        time.sleep(BattleSleep.MEDIUM)

    def _wait_battle_end(self) -> BattleEndType:
        """
        等待战斗结束

        :return: 战斗结束类型
        """
        if self.BATTLE_END_CONFIGS:
            return self._poll_battle_end()

        # 默认轮询方式
        while self.hooks.should_continue():
            time.sleep(BattleSleep.SHORT)
        return BattleEndType.OTHER

    def _poll_battle_end(self) -> BattleEndType:
        """
        轮询检测战斗结束

        :return: 战斗结束类型
        """
        victory_images = [
            c['image'] for c in self.BATTLE_END_CONFIGS
            if c.get('type') == 'victory'
        ]
        defeat_images = [
            c['image'] for c in self.BATTLE_END_CONFIGS
            if c.get('type') == 'defeat'
        ]

        while self.hooks.should_continue():
            # 检查胜利图片
            for img in victory_images:
                result = self.operations.find_image(img)
                if result.success:
                    return BattleEndType.VICTORY

            # 检查失败图片
            for img in defeat_images:
                result = self.operations.find_image(img)
                if result.success:
                    return BattleEndType.DEFEAT

            time.sleep(BattleSleep.SHORT)

        return BattleEndType.OTHER

    def _handle_battle_end(self, end_type: BattleEndType) -> None:
        """
        处理战斗结束

        :param end_type: 战斗结束类型
        """
        self.hooks.on_battle_end(end_type)

        if end_type == BattleEndType.VICTORY:
            self.current_victory_count += 1
            self.hooks.on_victory()
        else:
            self.hooks.on_defeat()

        self.current_battle_count += 1
