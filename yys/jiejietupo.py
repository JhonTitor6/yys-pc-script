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
            random_sleep(2, 3)
            try_bg_click_pic_with_timeout(self.hwnd, "images/jiejietupo_zai_ci_tiao_zhan.bmp", timeout=5)
            time.sleep(0.5)
            silence_point = bg_find_pic(self.hwnd, "images/jiejietupo_zai_ci_tiao_zhan_silence.bmp")
            if silence_point is not None and silence_point != (-1, -1):
                random_sleep(1, 2)
                bg_left_click_with_range(self.hwnd, (494, 317), x_range=10, y_range=10)
                random_sleep(0.2, 0.6)
                bg_left_click_with_range(self.hwnd, (672, 379), y_range=10)
            random_sleep(2.5, 3)


    def on_script_end(self):
        pass


if __name__ == '__main__':
    JieJieTuPo().run()