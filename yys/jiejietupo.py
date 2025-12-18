import time

from auto_script_base import YYSAutoScript
from common_util import *
from win_util.keyboard import *

class JieJieTuPo(YYSAutoScript):
    def __init__(self):
        super(JieJieTuPo, self).__init__(
            "jiejietupo",
            None
        )

    def click_challenge(self):
        try_bg_click_pic(self.hwnd, "images/jiejietupo_user_jiejie.bmp", x_range=5, y_range=5)
        random_sleep(1, 1.3)
        if not try_bg_click_pic(self.hwnd, "images/jiejietupo_jingong.bmp"):
            return False
        if self.cur_battle_count % 9 == 0:
            time.sleep(3)
            self.quit_3_times()
        else:
            time.sleep(10)
        return True


    def post_click_challenge_actions(self):
        point = bg_find_pic(self.hwnd, "images/douji_selection_auto_up.bmp")
        if point is not None and point[0] != -1 and point[1] != -1:
            try_bg_click_pic(self.hwnd, "images/battle_tianzhao.bmp", similarity=0.7, y_range=20)


    def on_battle_end_skip_success_actions(self, is_battle_victory):
        time.sleep(2)
        try_handle_battle_end(self.hwnd)
        point = bg_find_pic(self.hwnd, "images/jiejietupo_not_enough.bmp", similarity=0.9)
        if point is not None and point[0] != -1 and point[1] != -1:
            self.max_battle_count = self.cur_battle_count
            logger.info(f"没突破券了")


    def quit_3_times(self):
        logger.debug("准备退3次...")
        for i in range(0, 3):
            logger.debug(f"退出第{i + 1}次")
            bg_press_key(self.hwnd, 'ESC')
            random_sleep(0.05, 0.2)
            bg_press_key(self.hwnd, 'ENTER')
            time.sleep(3)
            try_bg_click_pic(self.hwnd, "images/jiejietupo_zai_ci_tiao_zhan.bmp")
            random_sleep(3, 3.5)


    def on_script_end(self):
        pass


if __name__ == '__main__':
    JieJieTuPo().run()