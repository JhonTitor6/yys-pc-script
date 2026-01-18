from win_util.image import ImageMatchConfig
from yys.event_script_base import YYSBaseScript

"""
御魂挂机
"""

class YuHunScript(YYSBaseScript):
    def __init__(self):
        super().__init__("yuhun")
        # 注册御魂挑战按钮事件
        self._register_image_match_event(ImageMatchConfig("images/yuhun_tiaozhan.bmp"), self._on_yuhun_tiaozhan)
        # 注册锁定接受邀请事件
        self._register_image_match_event(ImageMatchConfig("images/lock_accept_invitation.bmp"), self._on_lock_accept_invitation)

    def _on_yuhun_tiaozhan(self, point):
        """处理御魂挑战按钮点击"""
        self.bg_left_click(point, x_range=20, y_range=20)

    def _on_lock_accept_invitation(self, point):
        """处理锁定接受邀请点击"""
        self.bg_left_click(point, x_range=15, y_range=15)


def main():
    script = YuHunScript()
    script.set_max_battle_count(307)
    script.run()


if __name__ == '__main__':
    main()