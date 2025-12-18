from auto_event_script_base import *
from common_util import *
from event_component.event import Event
from my_mouse import *

tan_suo_xiao_guai = Event("tan_suo_xiao_guai")
tan_suo_boss = Event("tan_suo_boss")
tan_suo = Event("tan_suo")
tansuo_boss_success_reward = Event("tansuo_boss_success_reward")
tansuo_bao_xiang = Event("tansuo_bao_xiang")
tansuo_28 = Event("tansuo_28")
tansuo = Event("tansuo_she_zhi")
tansuo_kunnan = Event("tansuo_kunnan")
tansuo_tansuo = Event("tansuo_tansuo")


class AutoTanSuoEventScript(YYSAutoEventScript):
    def __init__(self):
        super().__init__("探索")

        # 没找到怪次数
        self._on_tansuo_count = 0

        self._register_image_match_event(ImageMatchConfig("images/tansuo_boss_tiaozhan.bmp"),
                                         self._on_event_bg_left_click)
        self._register_image_match_event(ImageMatchConfig("images/tansuo_tiaozhan.bmp"),
                                         self._on_event_bg_left_click)
        self._register_image_match_event(ImageMatchConfig("images/tansuo_boss_success_reward.bmp"),
                                         self._on_tansuo_boss_success_reward)
        self._register_image_match_event(ImageMatchConfig("images/tansuo_bao_xiang.bmp"),
                                         self._on_tansuo_bao_xiang)
        self._register_image_match_event(ImageMatchConfig("images/tansuo_bao_xiang_2.bmp"),
                                         self._on_tansuo_bao_xiang)
        self._register_image_match_event(ImageMatchConfig("images/tansuo_kunnan.bmp"),
                                         self._on_event_bg_left_click)
        self._register_image_match_event(ImageMatchConfig("images/tansuo_tansuo.bmp"),
                                         self._on_event_bg_left_click)
        self._register_image_match_event(ImageMatchConfig("images/tansuo_28.bmp"),
                                         self._on_event_bg_left_click)
        self._register_image_match_event(ImageMatchConfig("images/tansuo_she_zhi.bmp"),
                                         self._on_tansuo)

    def _on_zhan_dou_wan_cheng(self, point):
        super()._on_zhan_dou_wan_cheng(point)
        random_sleep(1, 3)
        script_run_minutes = int((int(time.time() * 1000) - self.script_start_time_mills) / 1000 / 60)
        if script_run_minutes > 0 and script_run_minutes % 26 == 0:
            logger.info(f"已运行{script_run_minutes}分钟，随机休眠1-3分钟...")
            random_sleep(60, 180)

    def _on_tansuo_boss_success_reward(self, point):
        bg_left_click_with_range(self.hwnd, point, x_range=20, y_range=20)
        random_sleep(1, 1.6)
        bg_left_click(self.hwnd, random.randint(960, 1030), random.randint(450, 510))

    def _on_tansuo_bao_xiang(self, point):
        random_sleep(1, 2)
        try_bg_click_pic_by_screenshot(self.screenshot_cache, "images/tansuo_close.bmp")
        random_sleep(1, 1.6)
        bg_left_click_with_range(self.hwnd, point)

    def _on_tansuo(self, point):
        self._on_tansuo_count += 1
        if self._on_tansuo_count >= 3:
            self.on_tansuo_count = 0
            # 向右移动
            bg_left_click(self.hwnd, random.randint(960, 1030), random.randint(450, 510))
            logger.debug("没有找到挑战按钮，往右移动...")
            random_sleep(1, 3)


if __name__ == '__main__':
    AutoTanSuoEventScript().run()
