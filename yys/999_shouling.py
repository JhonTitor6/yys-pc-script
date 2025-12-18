from auto_event_script_base import *


class AutoShouLing(YYSAutoEventScript):
    def __init__(self):
        super().__init__("shouling")
        super()._register_image_match_event(ImageMatchConfig("images/xueyuqian/shouling_tiaozhan.bmp"),
                                            self._on_event_bg_left_click)
        super()._register_image_match_event(ImageMatchConfig("images/xueyuqian/shouling_battle_end_close.bmp"),
                                            self._on_event_bg_left_click)


if __name__ == '__main__':
    AutoShouLing().run()