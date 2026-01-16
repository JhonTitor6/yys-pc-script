import time

from auto_event_script_base import YYSAutoEventScript
from common_util import *
from win_util.keyboard import *
from pic_and_color_util import ImageMatchConfig
from my_mouse import bg_left_click_with_range

"""
借借突破脚本，使用事件驱动模式
"""
class JieJieTuPo(YYSAutoEventScript):
    def __init__(self, quit_3_times_flag=True):
        super(JieJieTuPo, self).__init__(
            "jiejietupo"
        )

        self.quit_3_times_flag = quit_3_times_flag
        self.image_finder = ImageFinder(self.hwnd)
        
        # 注册借借突破特定的图像匹配事件
        self._register_image_match_event(ImageMatchConfig("images/jiejietupo_not_enough.bmp", similarity=0.9), self._on_jiejietupo_not_enough)
        # 注册挑战相关的事件
        self._register_image_match_event(ImageMatchConfig("images/jiejietupo_user_jiejie.bmp"), self._on_jiejietupo_user_jiejie)

    def _on_jiejietupo_not_enough(self, point):
        """处理借借突破券不足事件"""
        self._max_battle_count = self._cur_battle_count
        logger.info(f"没突破券了")
        # 停止脚本运行
        self.running = False

    def _on_jiejietupo_user_jiejie(self, point):
        """处理借借突破用户头像点击"""
        self.bg_left_click(point, x_range=5, y_range=5)
        random_sleep(1, 1.3)
        jingong_point = bg_find_pic(self.hwnd, "images/jiejietupo_jingong.bmp")
        if jingong_point is not None and jingong_point != (-1, -1):
            self._on_jiejietupo_jingong(jingong_point)

    def _on_jiejietupo_jingong(self, point):
        """处理进攻按钮点击"""
        if self.quit_3_times_flag and self._cur_battle_count % 9 == 0:
            # 点击进攻后，稍等片刻再执行退出逻辑
            self.bg_left_click(point, x_range=20, y_range=20)
            time.sleep(10)  # 等待战斗开始
            self.quit_3_times()
        else:
            self.bg_left_click(point, x_range=20, y_range=20)

    def _on_zhan_dou_wan_cheng(self, point):
        super()._on_zhan_dou_wan_cheng(point)
        time.sleep(2)
        try_handle_battle_end(self.hwnd)

    def quit_3_times(self):
        logger.debug("准备退3次...")
        time.sleep(3)
        for i in range(0, 3):
            logger.debug(f"退出第{i + 1}次")
            bg_press_key(self.hwnd, 'ESC')
            random_sleep(0.05, 0.2)
            bg_press_key(self.hwnd, 'ENTER')
            random_sleep(2, 3)
            logger.debug(f"准备点击【再次挑战】")
            try_bg_click_pic_with_timeout(self.hwnd, "images/jiejietupo_zai_ci_tiao_zhan.bmp", timeout=5)
            time.sleep(0.5)
            silence_point = bg_find_pic(self.hwnd, "images/jiejietupo_zai_ci_tiao_zhan_silence.bmp")
            if silence_point is not None and silence_point != (-1, -1):
                logger.debug("点击【今日不再提醒】")
                random_sleep(1, 2)
                bg_left_click_with_range(self.hwnd, (494, 317), x_range=10, y_range=10)
                random_sleep(0.2, 0.6)
                bg_left_click_with_range(self.hwnd, (672, 379), y_range=10)
            random_sleep(2.5, 3)
        logger.debug("完成退3次")


if __name__ == '__main__':
    JieJieTuPo().run()