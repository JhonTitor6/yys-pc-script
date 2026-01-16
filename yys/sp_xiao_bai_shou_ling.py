from auto_event_script_base import YYSAutoEventScript
from event_component.event import *
from yys.common_util import *

"""
sp小白首领
"""


class SpXiaoBaiShouLing(YYSAutoEventScript):
    def __init__(self):
        super().__init__(script_name="sp小白首领")
        self._register_image_match_event(ImageMatchConfig("images/xiao_bai_shou_ling_zhan.bmp"), self.on_zhan)
        self._register_image_match_event(ImageMatchConfig("images/xiao_bai_shou_ling_battle_end_close.bmp"), self.bg_left_click)

    def on_zhan(self, point):
        super().bg_left_click(point, x_range=5, y_range=5)
        random_sleep(20, 22)
        click_count = random.randint(8, 11)
        for i in range(click_count):
            self.click_dao_cao_ren()
            random_sleep(0.05, 0.1)

    def click_dao_cao_ren(self):
        dao_cao_ren_point = (632, 370)
        return bg_left_click_with_range(self.hwnd, dao_cao_ren_point, x_range=4, y_range=4)


if __name__ == '__main__':
    job = SpXiaoBaiShouLing()
    job.run()

    # click_count = random.randint(8, 11)
    # for i in range(click_count):
    #     job.click_dao_cao_ren()
    #     random_sleep(0.05, 0.1)

