import random
import time

from win_util.mouse import bg_left_click, bg_left_click_with_range
from yys.common_util import logger, random_sleep
from yys.event_script_base import YYSBaseScript, ImageMatchConfig


class ExplorationScript(YYSBaseScript):
    def __init__(self):
        super().__init__("探索")
        logger.info("初始化探索脚本")

        # 没找到怪次数
        self.idle_count = 0

        # TODO: 图片匹配增加 场景（多个） 条件，当在某些场景下才进行匹配
        self._register_image_match_event(ImageMatchConfig("yys/images/tansuo_boss_tiaozhan.bmp"),
                                         self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/images/tansuo_tiaozhan.bmp"),
                                         self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/images/tansuo_boss_success_reward.bmp"),
                                         self._on_tansuo_boss_success_reward)
        self._register_image_match_event(ImageMatchConfig("yys/images/tansuo_bao_xiang.bmp"),
                                         self._on_tansuo_bao_xiang)
        self._register_image_match_event(ImageMatchConfig("yys/images/tansuo_bao_xiang_2.bmp"),
                                         self._on_tansuo_bao_xiang)
        self._register_image_match_event(ImageMatchConfig("yys/images/tansuo_kunnan.bmp"),
                                         self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/images/tansuo_tansuo.bmp"),
                                         self._on_tansuo_entering)
        self._register_image_match_event(ImageMatchConfig("yys/images/tansuo_28.bmp"),
                                         self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/images/tansuo_she_zhi.bmp"),
                                         self._on_tansuo_idle)

        logger.info("探索脚本初始化完成")

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
        self.image_finder.bg_find_pic("yys/images/tansuo_close.bmp")
        random_sleep(1, 1.6)
        bg_left_click_with_range(self.hwnd, point)

    def _on_tansuo_entering(self, point):
        self.mouse.bg_left_click(point)
        time.sleep(0.5)
        self.image_finder.update_screenshot_cache()
        if self.ocr.contains_text(self.image_finder.screenshot_cache, "己达本日上限"):
            self.stop()

    def _on_tansuo_idle(self, point):
        self.idle_count += 1
        if self.idle_count >= 3:
            self.idle_count = 0
            # 向右移动
            self.mouse.bg_left_click(random.randint(960, 1030), random.randint(450, 510))
            logger.debug("没有找到挑战按钮，往右移动...")
            random_sleep(1, 3)

    def on_run(self):
        super().on_run()
        self.idle_count = 0
        self.scene_manager.goto_scene("exploration")


if __name__ == '__main__':
    ExplorationScript().run()
