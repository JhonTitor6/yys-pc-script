import time

from win_util.image import ImageMatchConfig
from yys.event_script_base import YYSBaseScript, random_sleep

"""
结界突破脚本，使用事件驱动模式
"""


class RealmRaidScript(YYSBaseScript):
    def __init__(self):
        super(RealmRaidScript, self).__init__(
            "realm_raid"
        )

        # TODO: 加个config类
        self.quit_3_times_config = True
        self.attackable_barrier_list = []

        # 注册结界突破特定的图像匹配事件
        self._register_image_match_event(ImageMatchConfig("yys/realm_raid/images/realm_raid_not_enough.bmp", similarity=0.9),
                                         self._on_ticket_not_enough)
        # 注册挑战相关的事件
        self._register_image_match_event(ImageMatchConfig("yys/realm_raid/images/realm_raid_jingong.bmp"), self._on_attack)
        self._register_image_match_event(ImageMatchConfig("yys/realm_raid/images/realm_raid_user_realm.bmp"),
                                         self._on_attackable_barrier)
        # 检测是不是没有可以挑战的了
        self._register_image_match_event(ImageMatchConfig("yys/common/images/scene/barrier_breakthrough.bmp"),
                                         self.on_scene_barrier_breakthrough)

    def _on_ticket_not_enough(self, point):
        """处理结界突破券不足事件"""
        self._max_battle_count = self._cur_battle_count
        self.logger.info(f"没突破券了")

    def _on_attackable_barrier(self, point):
        """处理结界突破用户头像点击"""
        self.attackable_barrier_list = self.get_all_attackable_barrier()
        self.bg_left_click(point, x_range=5, y_range=5)
        random_sleep(1, 1.3)

    def get_all_attackable_barrier(self):
        """获取所有可以打的结界"""
        POSITION_1 = 125, 120, 425, 245

        x0_1, y0_1, x1_1, y1_1 = POSITION_1

        col_offset_x = 300
        row_offset_y = 120

        all_realms = []
        for row in range(3):
            for col in range(3):
                x0 = x0_1 + col * col_offset_x
                y0 = y0_1 + row * row_offset_y
                x1 = x1_1 + col * col_offset_x
                y1 = y1_1 + row * row_offset_y

                point = self.image_finder.bg_find_pic_by_cache(
                    "yys/realm_raid/images/realm_raid_user_realm.bmp",
                    x0=x0, y0=y0, x1=x1, y1=y1
                )
                self.logger.debug(f"第{row + 1}行第{col + 1}列的结界: ({x0}, {y0}, {x1}, {y1}) 坐标: {point}")
                if point is not None and point != (-1, -1):
                    all_realms.append(point)

        self.logger.debug(f"找到{len(all_realms)}个结界")
        return all_realms

    def _on_attack(self, point):
        """处理进攻按钮点击"""
        self.bg_left_click(point, x_range=10, y_range=10)
        if not self.quit_3_times_config or len(self.attackable_barrier_list) < 9:
            time.sleep(5)
            return
        # 打第一个结界时先退 3 次
        self.quit_3_times()

    def quit_3_times(self):
        self.logger.info("准备退3次...")
        time.sleep(3)
        for i in range(0, 3):
            self.logger.info(f"退出第{i + 1}次")
            self.keyboard.bg_press_key('ESC')
            random_sleep(0.05, 0.2)
            self.keyboard.bg_press_key('ENTER')
            random_sleep(2, 3)
            self.logger.info(f"准备点击【再次挑战】")
            if self.win_controller.find_and_click("yys/realm_raid/images/realm_raid_retry.bmp", timeout=5):
                random_sleep(1, 2)
            self.logger.info("检查【今日不再提醒】")
            silence_point = self.image_finder.bg_find_pic_with_timeout("yys/realm_raid/images/realm_raid_retry_silence.bmp", timeout=2)
            if silence_point is not None and silence_point != (-1, -1):
                self.logger.info("点击【今日不再提醒】")
                random_sleep(1, 2)
                self.bg_left_click((494, 317), x_range=10, y_range=10)
                random_sleep(0.2, 0.6)
                self.bg_left_click((672, 379), y_range=10)
            random_sleep(2.5, 3)
        self.logger.info("完成退3次")

    def on_scene_barrier_breakthrough(self, point):
        self.refresh_if_no_attackable_barrier()

    def refresh_if_no_attackable_barrier(self):
        """检查是否有未打的结界"""
        realm_list = self.image_finder.bg_find_pic_all_by_cache("yys/realm_raid/images/realm_raid_user_realm.bmp")
        if len(realm_list) > 0:
            return

        self.logger.info("没有可以打的结界了，准备刷新")
        self.win_controller.find_and_click("yys/realm_raid/images/realm_raid_refresh.bmp", x_range=10, y_range=10, timeout=1)
        random_sleep(1, 1.5)

        self.win_controller.update_screenshot_cache()
        self.win_controller.find_and_click("yys/realm_raid/images/realm_raid_refresh_confirm.bmp", x_range=10, y_range=10, timeout=1)
        random_sleep(1, 1.5)
        self.logger.info("刷新完成")

    def on_run(self):
        super().on_run()
        self.scene_manager.goto_scene("barrier_breakthrough")


if __name__ == '__main__':
    RealmRaidScript().run()
