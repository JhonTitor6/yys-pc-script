from auto_event_script_base import YYSAutoEventScript
from event_component.event import *

"""
魔兽讨伐
"""
class MoShouTaoFa(YYSAutoEventScript):
    def __init__(self):
        super().__init__(script_name="魔兽讨伐")

        self._register_image_match_event(ImageMatchConfig("images/mo_shou_tiao_zhan.bmp"), self._on_event_bg_left_click)


if __name__ == '__main__':
    MoShouTaoFa().run()