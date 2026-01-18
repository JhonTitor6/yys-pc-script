import time

from common_util import logger, try_handle_battle_end
from event_script_base import YYSBaseScript, ImageMatchConfig


class DouJi(YYSBaseScript):
    """
    斗技挂机
    """

    def __init__(self):
        super().__init__(script_name="douji")

        self._has_clicked_tianzhao = False

        self._register_image_match_event(ImageMatchConfig("images/douji_zhan.bmp"), self._on_douji_zhan)
        self._register_image_match_event(ImageMatchConfig("images/change_to_auto_battle.bmp"), self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("images/douji_selection_auto_up.bmp", similarity=0.7),
                                         self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig(
            ["images/battle_tianzhao.bmp", "images/battle_tianzhao2.bmp", "images/battle_tianzhao3.bmp"], y0=262,
            similarity=0.75), self._on_battle_tianzhao)
        self._register_image_match_event(ImageMatchConfig("images/douji_battle_end.bmp"), self._on_zhan_dou_wan_cheng)
        self._register_image_match_event(ImageMatchConfig("images/battle_end_loss.bmp"), self._on_battle_end_loss)
        self._register_image_match_event(ImageMatchConfig("images/douji_battle_end_victory.bmp"),
                                         self._on_zhan_dou_wan_cheng)

    def try_skip_battle_end(self, point):
        """
        处理战斗结束
        """
        time.sleep(2)
        return try_handle_battle_end(self.hwnd)

    def _on_zhan_dou_wan_cheng_victory(self, point):
        super()._on_zhan_dou_wan_cheng_victory(point)
        super().log_battle_count()

    def _on_battle_end_loss(self, point):
        super().bg_left_click(point)
        self._cur_battle_count += 1
        super().log_battle_count()

    def _on_douji_zhan(self, point):
        super().bg_left_click(point)
        self._has_clicked_tianzhao = False

    def _on_battle_tianzhao(self, point):
        # TODO: 检测上方是否有绿色标记
        if not self._has_clicked_tianzhao:
            time.sleep(2)
            logger.info("点击标记天照")
            super().bg_left_click(point, x_range=2, y_range=2)
            self._has_clicked_tianzhao = True


if __name__ == '__main__':
    DouJi().run()
