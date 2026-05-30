from typing import Optional, TYPE_CHECKING

from win_util.image import ImageMatchConfig
from yys.common.event_script_base import YYSBaseScript

if TYPE_CHECKING:
    from tests.common.environment.base import GameEnvironment


class SoulRaidScript(YYSBaseScript):
    """
    御魂挂机
    """
    def __init__(self, env: Optional["GameEnvironment"] = None) -> None:
        """初始化御魂脚本，支持测试环境注入。"""
        super().__init__("soul_raid", env=env)
        # 注册御魂挑战按钮事件
        self._register_image_match_event(ImageMatchConfig("yys/soul_raid/images/yuhun_tiaozhan.bmp"), self._on_yuhun_tiaozhan)
        # 注册锁定接受邀请事件
        self._register_image_match_event(ImageMatchConfig("yys/soul_raid/images/lock_accept_invitation.bmp"), self._on_lock_accept_invitation)

    def _on_yuhun_tiaozhan(self, point):
        """处理御魂挑战按钮点击"""
        self.bg_left_click(point, x_range=20, y_range=20)

    def _on_lock_accept_invitation(self, point):
        """处理锁定接受邀请点击"""
        self.bg_left_click(point, x_range=15, y_range=15)


def main():
    script = SoulRaidScript()
    script.set_max_battle_count(307)
    script.run()


if __name__ == '__main__':
    main()
