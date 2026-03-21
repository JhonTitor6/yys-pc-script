import time

from yys.event_script_base import YYSBaseScript, ImageMatchConfig


class DouJi(YYSBaseScript):
    """
    斗技挂机
    """

    def __init__(self):
        super().__init__(script_name="douji")

        self._has_clicked_tianzhao = False

        self._register_image_match_event(ImageMatchConfig("yys/douji/images/douji_zhan.bmp"), self._on_douji_zhan)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/change_to_auto_battle.bmp"), self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/douji_selection_auto_up.bmp", similarity=0.7),
                                         self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig(
            ["yys/douji/images/battle_tianzhao.bmp", "yys/douji/images/battle_tianzhao2.bmp", "yys/douji/images/battle_tianzhao3.bmp"], y0=262,
            similarity=0.75), self._on_battle_tianzhao)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/douji_battle_end.bmp"), self._on_battle_end)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/battle_end_loss.bmp"), self._on_battle_end)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/douji_battle_end_victory.bmp"),
                                         self._on_battle_victory)

    def _on_battle_victory(self, point):
        """战斗胜利处理"""
        self.bg_left_click(point)
        self._cur_battle_victory_count += 1
        time.sleep(1.0)

    def _on_battle_end(self, point):
        """战斗结束（失败/奖励）处理"""
        time.sleep(2.0)
        self.bg_left_click(point, x_range=30, y_range=50)
        self._cur_battle_count += 1
        self._log_battle_count()
        time.sleep(0.5)

    def _on_douji_zhan(self, point):
        self.bg_left_click(point)
        self._has_clicked_tianzhao = False

    def _on_battle_tianzhao(self, point):
        if not self._has_clicked_tianzhao:
            time.sleep(2)
            self.logger.info("点击标记天照")
            self.bg_left_click(point, x_range=2, y_range=2)
            self._has_clicked_tianzhao = True


if __name__ == '__main__':
    DouJi().run()
