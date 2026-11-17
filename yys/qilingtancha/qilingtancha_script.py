"""契灵探查的独立运行入口和工作台脚本。"""

import random

from win_util.controller import WinController
from win_util.environment.base import GameEnvironment
from win_util.event import EventBaseScript, ImageMatchConfig
from yys.common.constants import BATTLE_END_SLEEP, BATTLE_VICTORY_SLEEP
from yys.common.event_script_base import BATTLE_END_LOSS_IMAGES, find_window
from yys.common.log_manager import get_logger


class QilingTanchaScript(EventBaseScript):
    """根据探查、战斗和结算画面推进，按胜场结束。"""

    DEFAULT_WIN_COUNT = 100
    MAX_WIN_COUNT = 999

    @classmethod
    def get_config_schema(cls) -> list[dict[str, object]]:
        """声明工作台的目标胜场字段。"""
        return [{
            "key": "max_battle_count",
            "label": "目标胜场",
            "field_type": "number",
            "integer_only": True,
            "default": cls.DEFAULT_WIN_COUNT,
            "min_value": 1,
            "max_value": cls.MAX_WIN_COUNT,
            "hot_reloadable": False,
            "description": f"输入 1 到 {cls.MAX_WIN_COUNT} 的整数。达到目标并结算后停止。",
        }]

    def __init__(
        self,
        script_name: str = "qilingtancha",
        config: dict[str, object] | None = None,
        env: GameEnvironment | None = None,
    ) -> None:
        """校验胜场目标并初始化窗口控制器。"""
        target = (config or {}).get("max_battle_count", self.DEFAULT_WIN_COUNT)
        if type(target) is not int or not 1 <= target <= self.MAX_WIN_COUNT:
            raise ValueError(f"目标胜场必须是 1 到 {self.MAX_WIN_COUNT} 的整数")
        self.max_battle_count = target
        self.win_controller = WinController(hwnd=find_window()) if env is None else WinController(env=env)
        super().__init__(self.win_controller.image_finder)
        self.logger = get_logger(script_name)
        self._win_count = 0
        self._result_seen = False
        self._register_image_match_event(
            ImageMatchConfig(["yys/images/battle_end.bmp", "yys/images/battle_end_success.bmp"]), self._on_victory,
        )
        self._register_image_match_event(ImageMatchConfig(BATTLE_END_LOSS_IMAGES), self._on_loss)
        self._register_image_match_event(ImageMatchConfig("yys/images/suipian.png"), self._on_fragment)
        self._register_image_match_event(
            ImageMatchConfig("yys/images/battle_end_1.bmp", similarity=0.7), self._on_reward_with_delay,
        )
        self._register_image_match_event(
            ImageMatchConfig("yys/images/battle_end_2.bmp", similarity=0.7), self._on_reward,
        )
        self._register_image_match_event(
            ImageMatchConfig("yys/common/images/scene/battling.bmp"), self._on_battling,
        )
        self._register_image_match_event(
            ImageMatchConfig("yys/qilingtancha/images/qiling_tancha.bmp", similarity=0.7), self._on_tancha,
        )

    def on_run(self) -> None:
        """从当前画面接管并重置本次胜场。"""
        self._win_count = 0
        self._result_seen = False

    def before_iteration(self) -> None:
        """截图失败时避免沿用上一轮的画面执行点击。"""
        self.win_controller.image_finder.screenshot_cache = None

    def after_iteration(self) -> None:
        """沿用探查脚本的点击间隔，收到停止信号时立即结束等待。"""
        self._stop_threading_event.wait(random.randint(1, 3))

    def get_state_snapshot(self) -> dict[str, object]:
        """向工作台报告胜场进度。"""
        return {"victory_count": self._win_count, "progress_count": self._win_count, "max_battle_count": self.max_battle_count}

    def _click(self, point: tuple[int, int], x_range: int, y_range: int) -> bool:
        if self._stop_threading_event.is_set() or not self._pause_threading_event.is_set():
            return False
        return self.win_controller.mouse.bg_left_click_with_range(point, x_range=x_range, y_range=y_range)

    def _on_tancha(self, point: tuple[int, int]) -> None:
        if self._win_count >= self.max_battle_count:
            self.stop()
        elif self._click(point, 20, 20):
            self._result_seen = False

    def _on_battling(self, _point: tuple[int, int]) -> None:
        """识别战斗中画面并等待结算。"""

    def _on_victory(self, point: tuple[int, int]) -> None:
        if not self._click(point, 200, 50):
            return
        if not self._result_seen:
            self._result_seen = True
            self._win_count += 1
            self.logger.success(f"通关次数：{self._win_count}/{self.max_battle_count}")
        self._stop_threading_event.wait(BATTLE_VICTORY_SLEEP)

    def _on_loss(self, point: tuple[int, int]) -> None:
        if self._click(point, 200, 50):
            self._result_seen = True

    def _on_fragment(self, point: tuple[int, int]) -> None:
        self._click(point, 100, 100)

    def _on_reward_with_delay(self, point: tuple[int, int]) -> None:
        if not self._stop_threading_event.wait(BATTLE_END_SLEEP):
            self._on_reward(point)

    def _on_reward(self, point: tuple[int, int]) -> None:
        self._click(point, 300, 50)


def main() -> None:
    """独立运行契灵探查。"""
    QilingTanchaScript().run()


if __name__ == '__main__':
    main()
