from win_util.event import ImageMatchConfig

from yys.event_script_base import YYSBaseScript


class AutoYuling(YYSBaseScript):
    def __init__(self):
        super().__init__("御灵")
        self._register_image_match_event(ImageMatchConfig("images/yuling_tiaozhan.bmp"), self.bg_left_click)


if __name__ == '__main__':
    AutoYuling().set_max_battle_count(307).run()
