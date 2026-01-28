from win_util.image import ImageMatchConfig
from yys.event_script_base import YYSBaseScript

class Main(YYSBaseScript):
    """
    藤原道长-传承试炼
    """
    def __init__(self):
        super().__init__("藤原道长-传承试炼")

        self._register_image_match_event(ImageMatchConfig("yys/fujiwara/images/challenge_button.bmp"), self.bg_left_click)


if __name__ == '__main__':
    Main().run()