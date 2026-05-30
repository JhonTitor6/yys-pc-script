from win_util.event import ImageMatchConfig
from yys.common.event_script_base import YYSBaseScript


class LoopChallenge(YYSBaseScript):
    def __init__(self):
        super().__init__("通用挑战脚本")
        self._register_image_match_event(ImageMatchConfig("yys/common_challenge/images/challenge.bmp"), self.bg_left_click)


if __name__ == '__main__':
    LoopChallenge().set_max_battle_count(140).run()
