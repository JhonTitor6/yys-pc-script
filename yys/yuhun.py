import time

from common_util import *
from loguru import logger
from auto_event_script_base import YYSAutoEventScript
from pic_and_color_util import ImageMatchConfig

"""
御魂挂机
"""

class YuHunScript(YYSAutoEventScript):
    def __init__(self):
        super().__init__("yuhun")
        # 注册御魂挑战按钮事件
        self._register_image_match_event(ImageMatchConfig("images/yuhun_tiaozhan.bmp"), self._on_yuhun_tiaozhan)
        # 注册锁定接受邀请事件
        self._register_image_match_event(ImageMatchConfig("images/lock_accept_invitation.bmp"), self._on_lock_accept_invitation)
        # 注册御魂战斗结束相关事件
        self._register_image_match_event(ImageMatchConfig(["images/battle_end_success.bmp", "images/battle_end.bmp"]), self._on_battle_end_success)
        self._register_image_match_event(ImageMatchConfig("images/battle_end_loss.bmp"), self._on_battle_end_loss)
        self._register_image_match_event(ImageMatchConfig(["images/battle_end_1.bmp", "images/battle_end_2.bmp"]), self._on_battle_end_1)

    def _on_yuhun_tiaozhan(self, point):
        """处理御魂挑战按钮点击"""
        self.bg_left_click(point, x_range=20, y_range=20)

    def _on_lock_accept_invitation(self, point):
        """处理锁定接受邀请点击"""
        self.bg_left_click(point, x_range=15, y_range=15)

    def _on_battle_end_success(self, point):
        """处理战斗胜利结束"""
        self.bg_left_click(point, x_range=200, y_range=50)
        self._cur_battle_victory_count += 1
        self._cur_battle_count += 1
        self.log_battle_count()

    def _on_battle_end_loss(self, point):
        """处理战斗失败结束"""
        self.bg_left_click(point, x_range=200, y_range=50)
        self._cur_battle_count += 1
        self.log_battle_count()

    def _on_battle_end_1(self, point):
        """处理战斗结束1"""
        self.bg_left_click(point, x_range=300, y_range=50)


def main():
    script = YuHunScript()
    script.run()


if __name__ == '__main__':
    main()