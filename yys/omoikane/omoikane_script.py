import time

from win_util.event import ImageMatchConfig, random_sleep
from yys.common import BATTLE_END_SLEEP, BATTLE_END_CLICK_RANGE_X, BATTLE_END_CLICK_RANGE_Y, BATTLE_END_CLICK_SLEEP
from yys.common.event_script_base import YYSBaseScript


class OmoikaneScript(YYSBaseScript):
    def __init__(self):
        super().__init__("思金神")
        self._register_image_match_event(ImageMatchConfig("yys/omoikane/images/chanllange.png"), self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_close.bmp"), self.bg_left_click)

    def _on_battle_end(self, point: tuple):
        # 不可去掉。如果不等一会，没点掉导致触发多次的话，会多次触发_cur_battle_count+=1
        time.sleep(BATTLE_END_SLEEP)
        # 使用匹配到的实际位置点击
        self.bg_left_click((995, 540), x_range=BATTLE_END_CLICK_RANGE_X, y_range=BATTLE_END_CLICK_RANGE_Y)
        random_sleep(0.5, 1)
        self.bg_left_click((995, 540), x_range=BATTLE_END_CLICK_RANGE_X, y_range=BATTLE_END_CLICK_RANGE_Y)
        self._cur_battle_count += 1
        self._log_battle_count()
        time.sleep(BATTLE_END_CLICK_SLEEP)


if __name__ == '__main__':
    OmoikaneScript().set_max_battle_count(150).run()
