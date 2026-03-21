from win_util.image import ImageMatchConfig
from yys.event_script_base import YYSBaseScript


class Main(YYSBaseScript):
    """
    葛叶-影域精锐
    """
    def __init__(self):
        super().__init__("葛叶-影域精锐")
        self._register_image_match_event(ImageMatchConfig("yys/kuzunoha/images/challenge_button.bmp"), self.bg_left_click)


if __name__ == '__main__':
    Main().set_max_battle_count(48).run()