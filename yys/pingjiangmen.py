from yys.auto_event_script_base import YYSAutoEventScript
from event_component.event import ImageMatchConfig
from common_util import *

class PingJiangMen(YYSAutoEventScript):

    def __init__(self):
        super().__init__("pingjiangmen")
        super()._register_image_match_event(ImageMatchConfig("images/invite_jieshou.bmp"), self.bg_left_click)


    def _on_zhan_dou_wan_cheng(self, point):
        time.sleep(1.5)
        bg_left_click_with_range(self.hwnd, (554, 50), x_range=30, y_range=10)
        self._cur_battle_count += 1
        self.log_battle_count()


if __name__ == '__main__':
    PingJiangMen().run()