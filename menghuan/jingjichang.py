from abc import ABC

from event_component.event import *
from pic_and_color_util import ImageMatchConfig
from common_util import find_window


class AutoJingJiChang(AutoImageEventScript, ABC):
    def __init__(self):
        super().__init__()
        super()._register_image_match_event(ImageMatchConfig("images/auto_2.bmp"), self._on_event_bg_left_click)
        super()._register_image_match_event(ImageMatchConfig("images/jingjichang_pipei.bmp"),
                                            self._on_event_bg_left_click)

    def find_window(self) -> str:
        return find_window()


if __name__ == '__main__':
    AutoJingJiChang().run()
