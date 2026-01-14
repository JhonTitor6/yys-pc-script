import time

from common_util import *
from event_component.event import Event, AutoImageEventScript
from pic_and_color_util import ImageMatchConfig
from my_mouse import *

end_script = Event("end_script")

"""
事件驱动
"""
class YYSAutoEventScript(AutoImageEventScript):
    def __init__(self, script_name):
        super().__init__()
        self.script_name = script_name
        # 日志
        logger.add(
            f"logs/{script_name}/{{time:YYYY-MM-DD}}.log",
            rotation="00:00",
            retention="7 days",
            encoding="utf-8",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
        )
        logger.info(f"初始化{self.script_name}脚本")
        self.script_start_time_mills = int(time.time() * 1000)

        self.running = True

        self._cur_battle_count = 0
        self._cur_battle_victory_count = 0
        self._max_battle_count = 0

        self._register_image_match_event(ImageMatchConfig("images/battle_end.bmp"), self._on_zhan_dou_wan_cheng_victory)
        self._register_image_match_event(ImageMatchConfig("images/battle_end_1.bmp"), self._on_zhan_dou_wan_cheng)
        self._register_image_match_event(ImageMatchConfig("images/xuanshangfengyin_accept.bmp"), self._on_event_bg_left_click)

    def find_window(self) -> str:
        return find_window()

    def _on_event_bg_left_click(self, point, x_range=20, y_range=20):
        bg_left_click_with_range(self.hwnd, point, x_range=x_range, y_range=y_range)

    def _on_zhan_dou_wan_cheng_victory(self, point):
        self._on_event_bg_left_click(point)
        self._cur_battle_victory_count += 1

    def _on_zhan_dou_wan_cheng(self, point):
        time.sleep(2)
        point = (1000, 400)
        bg_left_click_with_range(self.hwnd, point, x_range=30, y_range=50)
        self._cur_battle_count += 1
        self.log_battle_count()
        time.sleep(0.5)

    def log_battle_count(self):
        logger.success(
            f"战斗完成，已战斗{self._cur_battle_count}/{self._max_battle_count}次，胜利{self._cur_battle_victory_count}次")

    def run(self):
        self._max_battle_count = get_max_battle_count()
        logger.info(f"开始执行{self.script_name}，计划完成{self._max_battle_count}次战斗")
        while True:
            if not self.running:
                self._event_manager.trigger_event(end_script)
                break
            self._update_screenshot_cache()
            self._handle_event_from_screenshot_cache()
            random_sleep(0.2, 0.5)
            if self._cur_battle_count >= self._max_battle_count:
                self.running = False
