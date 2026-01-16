from auto_event_script_base import YYSAutoEventScript, ImageMatchConfig
from common_util import *
from my_mouse import *
import config

config.DEBUG = True

class Auto999(YYSAutoEventScript):
    def __init__(self):
        super().__init__("999")
        self.next_need_sleep_count = random.randint(50, 80)

        self._register_image_match_event(ImageMatchConfig("images/999_tiaozhan.bmp"), self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig(["images/battle_end.bmp", "images/999_battle_end.bmp"]), self._on_zhan_dou_wan_cheng)

    def _on_zhan_dou_wan_cheng(self, point):
        self._cur_battle_victory_count += 1
        super()._on_zhan_dou_wan_cheng(point)
        if self._cur_battle_victory_count == self.next_need_sleep_count:
            logger.info(f"已通关{self._cur_battle_victory_count}次，随机休眠1-3分钟")
            random_sleep(30, 120)
            self.next_need_sleep_count += random.randint(50, 80)


if __name__ == '__main__':
    Auto999().run()