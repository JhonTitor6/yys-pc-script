import time

from auto_script_base import YYSAutoScript
from common_util import *
from my_mouse import *
import random


class TanSuo(YYSAutoScript):
    def __init__(self):
        super().__init__("tansuo", None)

    def click_challenge(self):
        if try_bg_click_pic(self.hwnd, "images/tansuo_28.bmp"):
            random_sleep(1, 3)
        if try_bg_click_pic(self.hwnd, "images/tansuo_kunnan.bmp"):
            random_sleep(1, 2)
        if try_bg_click_pic(self.hwnd, "images/tansuo_tansuo.bmp"):
            random_sleep(1, 2)
        try_bg_click_pic(self.hwnd, "images/tansuo_boss_tiaozhan.bmp", similarity=0.7)
        click_tiao_zhan_res = try_bg_click_pic(self.hwnd, "images/tansuo_tiaozhan.bmp", similarity=0.7)
        if click_tiao_zhan_res:
            time.sleep(7)
            return click_tiao_zhan_res
        logger.debug("没有找到挑战按钮，往右移动...")
        # 往右移动
        bg_left_click(self.hwnd, random.randint(960, 1030), random.randint(450, 510))
        return False

    def post_click_challenge_actions(self):
        """

        :return:
        """
        try_bg_click_pic(self.hwnd, "images/tansuo_boss_success_reward.bmp")

    def on_battle_end_skip_success_actions(self, is_battle_victory):
        if try_bg_click_pic(self.hwnd, "images/tansuo_boss_success_reward.bmp"):
            random_sleep(1, 2)
            bg_left_click(self.hwnd, random.randint(960, 1030), random.randint(450, 510))

    def on_script_start(self):
        """开金币加成"""
        if try_bg_click_pic(self.hwnd, "images/jia_cheng.bmp"):
            random_sleep(1, 2)
        p = bg_find_pic(self.hwnd, "images/jia_cheng_jinbi_100.bmp")
        if p is not None and p[0] != -1 and p[1] != -1:
            p = bg_find_pic(self.hwnd, "images/jia_cheng_wei_ji_huo.bmp", similarity=0.9,
                            x0=p[0] + 50,
                            x1=p[0] + 200,
                            y0=p[1] - 40,
                            y1=p[1] + 40
                            )
            bg_left_click_with_range(self.hwnd, p, x_range=5, y_range=5)
            random_sleep(0.5, 1)
            bg_left_click_with_range(self.hwnd, (970, 280), x_range=50, y_range=50)


if __name__ == '__main__':
    TanSuo().run()
