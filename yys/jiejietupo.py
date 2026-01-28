import time

from win_util.image import ImageFinder
from win_util.image import ImageMatchConfig
from win_util.mouse import bg_left_click_with_range
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
        self.image_finder: ImageFinder = ImageFinder(self.hwnd)
        self.attackable_barrier_list = []

        # 注册借借突破特定的图像匹配事件
        self._register_image_match_event(ImageMatchConfig("yys/images/jiejietupo_not_enough.bmp", similarity=0.9),
                                         self._on_ticket_not_enough)
        # 注册挑战相关的事件
        self._register_image_match_event(ImageMatchConfig("yys/images/jiejietupo_jingong.bmp"), self._on_attack)
        self._register_image_match_event(ImageMatchConfig("yys/images/jiejietupo_user_jiejie.bmp"),
                                         self._on_attackable_barrier)
        # 检测是不是没有可以挑战的了
        self._register_image_match_event(ImageMatchConfig("yys/images/scene/barrier_breakthrough.bmp"),
                                         self.on_scene_barrier_breakthrough)

    def _on_ticket_not_enough(self, point):
        """处理借借突破券不足事件"""
        self._max_battle_count = self._cur_battle_count
        logger.info(f"没突破券了")

    def _on_attackable_barrier(self, point):
        """处理借借突破用户头像点击"""
        self.attackable_barrier_list = self.get_all_attackable_barrier()
        self.bg_left_click(point, x_range=5, y_range=5)
        random_sleep(1, 1.3)

    def get_all_attackable_barrier(self):
        """获取所有可以打的结界"""
        POSITION_1 = 125, 120, 425, 245

        x0_1, y0_1, x1_1, y1_1 = POSITION_1

        col_offset_x = 300
        row_offset_y = 120

        all_jiejie = []
        for row in range(3):
            for col in range(3):
                x0 = x0_1 + col * col_offset_x
                y0 = y0_1 + row * row_offset_y
                x1 = x1_1 + col * col_offset_x
                y1 = y1_1 + row * row_offset_y

                point = self.image_finder.bg_find_pic_by_cache(
                    "yys/images/jiejietupo_user_jiejie.bmp",
                    x0=x0, y0=y0, x1=x1, y1=y1
                )
                logger.debug(f"第{row + 1}行第{col + 1}列的结界: ({x0}, {y0}, {x1}, {y1}) 坐标: {point}")
                if point is not None and point != (-1, -1):
                    all_jiejie.append(point)

        logger.debug(f"找到{len(all_jiejie)}个结界")
        return all_jiejie

    def _on_attack(self, point):
        """处理进攻按钮点击"""
        self.bg_left_click(point, x_range=10, y_range=10)
        if not self.quit_3_times_config or len(self.attackable_barrier_list) < 9:
            time.sleep(5)
            return
        # 打第一个结界时先退 3 次
        self.quit_3_times()

    def _on_zhan_dou_wan_cheng(self, point):
        super()._on_zhan_dou_wan_cheng(point)
        time.sleep(2)
        try_handle_battle_end(self.hwnd)

    def quit_3_times(self):
        logger.info("准备退3次...")
        time.sleep(3)
        for i in range(0, 3):
            logger.info(f"退出第{i + 1}次")
            self.keyboard.bg_press_key('ESC')
            random_sleep(0.05, 0.2)
            self.keyboard.bg_press_key('ENTER')
            random_sleep(2, 3)
            logger.info(f"准备点击【再次挑战】")
            try_bg_click_pic_with_timeout(self.hwnd, "yys/images/jiejietupo_zai_ci_tiao_zhan.bmp", timeout=5)
            time.sleep(0.5)
            silence_point = bg_find_pic(self.hwnd, "yys/images/jiejietupo_zai_ci_tiao_zhan_silence.bmp")
            if silence_point is not None and silence_point != (-1, -1):
                logger.info("点击【今日不再提醒】")
                random_sleep(1, 2)
                bg_left_click_with_range(self.hwnd, (494, 317), x_range=10, y_range=10)
                random_sleep(0.2, 0.6)
                bg_left_click_with_range(self.hwnd, (672, 379), y_range=10)
            random_sleep(2.5, 3)
        logger.info("完成退3次")

    def on_scene_barrier_breakthrough(self, point):
        self.refresh_if_no_attackable_barrier()

    def refresh_if_no_attackable_barrier(self):
        """检查是否有未打的结界"""
        jiejie_list = self.image_finder.bg_find_pic_all_by_cache("yys/images/jiejietupo_user_jiejie.bmp")
        if len(jiejie_list) > 0:
            return

        logger.info("没有可以打的结界了，准备刷新")
        refresh_button_pos = self.ocr.find_text_position(self.image_finder.screenshot_cache, "刷新")
        if not refresh_button_pos:
            logger.warning("未找到刷新按钮")
            return

        logger.info(f"找到刷新按钮位置: {refresh_button_pos}")
        self.bg_left_click(refresh_button_pos, x_range=10, y_range=10)
        random_sleep(1, 1.5)

        self.image_finder.update_screenshot_cache()
        confirm_button_pos = self.ocr.find_text_position(self.image_finder.screenshot_cache, "确定")
        if not confirm_button_pos:
            logger.warning("未找到确定按钮")
            return

        logger.info(f"找到确定按钮位置: {confirm_button_pos}")
        self.bg_left_click(confirm_button_pos, x_range=10, y_range=10)
        random_sleep(1, 1.5)
        logger.info("刷新完成")

    def on_run(self):
        super().on_run()
        self.scene_manager.goto_scene("barrier_breakthrough")


if __name__ == '__main__':
    JieJieTuPoScript().run()
