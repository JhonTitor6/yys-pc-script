# yys.soul_raid.soul_raid_script - 御魂挂机脚本
# 使用 BattleFlow 重构御魂战斗流程

import time

from yys.event_script_base import YYSBaseScript
from yys.common.battle.base import BattleFlow
from yys.common.battle.hooks import BattleHooks
from yys.common.constants import (
    BattleSleep,
    BattleEndType,
    ImageSimilarity,
    ClickRange,
)


class SoulRaidHooks(BattleHooks):
    """
    御魂战斗钩子实现

    定义御魂战斗流程各阶段的回调处理
    """

    # 战斗结束图片配置
    BATTLE_END_CONFIGS = [
        {'image': 'yys/images/battle_end_success.bmp', 'type': 'victory'},
        {'image': 'yys/images/battle_end_loss.bmp', 'type': 'defeat'},
    ]

    def __init__(self, script: YYSBaseScript):
        """
        初始化御魂战斗钩子

        :param script: YYSBaseScript 实例
        """
        self.script = script
        self.lock_invitation_image = "yys/soul_raid/images/lock_accept_invitation.bmp"

    def on_challenge_found(self, position: tuple) -> None:
        """挑战按钮被发现时调用"""
        pass

    def on_challenge_clicked(self) -> None:
        """挑战按钮被点击后调用"""
        # 御魂特有：点击挑战后，会弹出"锁定邀请"对话框
        time.sleep(BattleSleep.SHORT)
        self.script.win_controller.find_and_click(
            self.lock_invitation_image,
            x_range=15,
            y_range=15,
            similarity=ImageSimilarity.DEFAULT
        )

    def on_battle_start(self) -> None:
        """战斗开始时调用"""
        pass

    def on_battle_end(self, end_type: BattleEndType) -> None:
        """
        战斗结束时调用

        :param end_type: 战斗结束类型
        """
        pass

    def on_victory(self) -> None:
        """战斗胜利时调用"""
        self.script.logger.success(
            f"战斗胜利 {self.script._cur_battle_victory_count}/{self.script._max_battle_count}"
        )

    def on_defeat(self) -> None:
        """战斗失败时调用"""
        pass

    def should_continue(self) -> bool:
        """
        检查是否继续战斗

        :return: True 继续战斗，False 停止战斗
        """
        return self.script._cur_battle_count < self.script._max_battle_count


class SoulRaidScript(YYSBaseScript):
    """
    御魂挂机脚本

    使用 BattleFlow 标准化战斗流程
    """

    def __init__(self):
        super().__init__("soul_raid")

        # 创建操作封装
        self.operations = self._create_operations()

        # 创建钩子
        hooks = SoulRaidHooks(self)

        # 创建战斗流程
        self.battle_flow = BattleFlow(
            script_name="soul_raid",
            challenge_image="yys/soul_raid/images/yuhun_tiaozhan.bmp",
            operations=self.operations,
            hooks=hooks,
            max_battle_count=307
        )

        # 设置战斗结束检测配置
        self.battle_flow.BATTLE_END_CONFIGS = SoulRaidHooks.BATTLE_END_CONFIGS

    def _create_operations(self):
        """创建操作封装实例"""
        from yys.common.operations import ImageOperations
        return ImageOperations(self.win_controller)

    def run(self):
        """启动御魂挂机"""
        self.logger.info("启动御魂挂机脚本")
        self.battle_flow.execute_battle_loop()


def main():
    """主入口"""
    script = SoulRaidScript()
    script.set_max_battle_count(307)
    script.run()


if __name__ == '__main__':
    main()
