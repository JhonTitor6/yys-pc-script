import time

from my_mouse import bg_left_click_with_range
from win_util.image import ImageMatchConfig
from win_util.image import ImageFinder
from win_util.keyboard import bg_press_key
from yys.common_util import logger, bg_find_pic, random_sleep, try_handle_battle_end, try_bg_click_pic_with_timeout
from yys.event_script_base import YYSBaseScript

"""
结界突破脚本，使用事件驱动模式
"""
class JieJieTuPoScript(YYSBaseScript):
    def __init__(self):
        super(JieJieTuPoScript, self).__init__(
            "jiejietupo"
        )

        # TODO: 加个config类
        self.quit_3_times_config = True
        self.image_finder = ImageFinder(self.hwnd)

        # 注册借借突破特定的图像匹配事件
        self._register_image_match_event(ImageMatchConfig("images/jiejietupo_not_enough.bmp", similarity=0.9), self._on_jiejietupo_not_enough)
        # 注册挑战相关的事件
        self._register_image_match_event(ImageMatchConfig("images/jiejietupo_jingong.bmp"), self._on_jiejietupo_jingong)
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

    def _on_jiejietupo_jingong(self, point):
        """处理进攻按钮点击"""
        if self.quit_3_times_config and self._cur_battle_count % 9 == 0:
            # 点击进攻后，稍等片刻再执行退出逻辑
            self.bg_left_click(point, x_range=20, y_range=20)
            self.quit_3_times()
        else:
            self.bg_left_click(point, x_range=20, y_range=20)
            time.sleep(10)  # 等待战斗开始

    def _on_zhan_dou_wan_cheng(self, point):
        super()._on_zhan_dou_wan_cheng(point)
        time.sleep(2)
        try_handle_battle_end(self.hwnd)

    def quit_3_times(self):
        logger.info("准备退3次...")
        time.sleep(3)
        for i in range(0, 3):
            logger.info(f"退出第{i + 1}次")
            bg_press_key(self.hwnd, 'ESC')
            random_sleep(0.05, 0.2)
            bg_press_key(self.hwnd, 'ENTER')
            random_sleep(2, 3)
            logger.info(f"准备点击【再次挑战】")
            try_bg_click_pic_with_timeout(self.hwnd, "images/jiejietupo_zai_ci_tiao_zhan.bmp", timeout=5)
            time.sleep(0.5)
            silence_point = bg_find_pic(self.hwnd, "images/jiejietupo_zai_ci_tiao_zhan_silence.bmp")
            if silence_point is not None and silence_point != (-1, -1):
                logger.info("点击【今日不再提醒】")
                random_sleep(1, 2)
                bg_left_click_with_range(self.hwnd, (494, 317), x_range=10, y_range=10)
                random_sleep(0.2, 0.6)
                bg_left_click_with_range(self.hwnd, (672, 379), y_range=10)
            random_sleep(2.5, 3)
        logger.info("完成退3次")

    def on_run(self):
        super().on_run()
        self.scene_manager.goto_scene("barrier_breakthrough")



if __name__ == '__main__':
    JieJieTuPoScript().run()