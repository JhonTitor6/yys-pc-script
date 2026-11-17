"""超鬼王挑战脚本。"""

from __future__ import annotations

from win_util.environment import GameEnvironment
from win_util.image import ImageMatchConfig
from yys.common.constants import DEFAULT_CLICK_RANGE
from yys.common.event_script_base import YYSBaseScript
from yys.common.script_meta import ScriptMeta

_ACTIVITY = ImageMatchConfig("yys/super_demon_boss/images/activity.png", similarity=0.85)
_SUMMON = ImageMatchConfig("yys/super_demon_boss/images/summon.png", similarity=0.90)
_CHALLENGE = ImageMatchConfig([
    "yys/common_challenge/images/challenge.bmp",
    "yys/common_challenge/images/challenge_1.bmp",
    "yys/common_challenge/images/region_challenge.bmp",
])
_READY = ImageMatchConfig("yys/images/ready.bmp")
_BATTLING = ImageMatchConfig("yys/common/images/scene/battling.bmp")
_REWARD = ImageMatchConfig("yys/common_challenge/images/gained_reward.bmp")


class _ClickCancelled(Exception):
    """暂停或停止后中断当前画面事件，避免推进未点击的步骤。"""


class SuperDemonBossScript(YYSBaseScript):
    """从超鬼王活动页召唤并挑战，达到战斗场数后停止。"""

    SCRIPT_META = ScriptMeta(display_name="超鬼王", category="活动", config_schema=None)
    DEFAULT_BATTLE_COUNT = 20
    MAX_BATTLE_COUNT = 9999

    @classmethod
    def get_config_schema(cls) -> list[dict[str, object]]:
        """声明工作台的战斗场数字段。"""
        return [{
            "key": "max_battle_count",
            "label": "战斗场数",
            "field_type": "number",
            "integer_only": True,
            "default": cls.DEFAULT_BATTLE_COUNT,
            "min_value": 1,
            "max_value": cls.MAX_BATTLE_COUNT,
            "hot_reloadable": False,
            "description": "胜负均按结算计入场数，达到目标后停止。",
        }]

    def __init__(
        self,
        script_name: str = "super_demon_boss",
        config: dict[str, object] | None = None,
        env: GameEnvironment | None = None,
    ) -> None:
        target = (config or {}).get("max_battle_count", self.DEFAULT_BATTLE_COUNT)
        if type(target) is not int or not 1 <= target <= self.MAX_BATTLE_COUNT:
            raise ValueError(f"战斗场数必须是 1 到 {self.MAX_BATTLE_COUNT} 的整数")
        super().__init__(script_name, env=env)
        self.max_battle_count = target

    def on_run(self) -> None:
        """每次运行先确认超鬼王活动入口；有效事件随当前步骤更新。"""
        super().on_run()
        self._wait_for_activity()

    def _wait_for_activity(self) -> None:
        self._summon_requested = False
        self._victory_seen = False
        self._settlement_counted = False
        self._image_event_match_configs.clear()
        self._register_wanted_quest_events()
        self._register_image_match_event(_ACTIVITY, self._on_activity)

    def before_iteration(self) -> None:
        """截图失败时丢弃上一帧，避免用旧画面点击。"""
        self.image_finder.screenshot_cache = None

    def _trigger_event_from_screenshot_cache(self) -> str | None:
        try:
            return super()._trigger_event_from_screenshot_cache()
        except _ClickCancelled:
            return None

    def bg_left_click(
        self, point: tuple[int, int], x_range: int = DEFAULT_CLICK_RANGE, y_range: int = DEFAULT_CLICK_RANGE,
    ) -> None:
        """发出点击前复查状态，阻止已延迟或已匹配的旧事件操作游戏。"""
        if self._stop_threading_event.is_set() or not self._pause_threading_event.is_set():
            raise _ClickCancelled
        super().bg_left_click(point, x_range=x_range, y_range=y_range)

    def _on_activity(self, _point: tuple[int, int]) -> None:
        point, _ = self.image_finder.bg_find_pic_by_config(_CHALLENGE)
        if point != (-1, -1):
            self._on_challenge(point)
        elif not self._summon_requested:
            point, _ = self.image_finder.bg_find_pic_by_config(_SUMMON)
            if point != (-1, -1):
                self.bg_left_click(point, x_range=0, y_range=0)
                self._summon_requested = True

    def _on_challenge(self, point: tuple[int, int]) -> None:
        self.bg_left_click(point, x_range=0, y_range=0)
        self._image_event_match_configs.remove(_ACTIVITY)
        self._register_battle_end_events()
        self._register_image_match_event(_REWARD, self._on_reward)
        self._register_image_match_event(_BATTLING, self._disable_ready)
        self._register_image_match_event(_READY, self._on_ready)

    def _disable_ready(self, _point: tuple[int, int]) -> None:
        if _READY in self._image_event_match_configs:
            self._image_event_match_configs.remove(_READY)

    def _on_ready(self, point: tuple[int, int]) -> None:
        self.bg_left_click(point, x_range=0, y_range=0)
        self._image_event_match_configs.remove(_READY)

    def _on_battle_victory(self, point: tuple[int, int]) -> None:
        if self._victory_seen or self._settlement_counted:
            self.bg_left_click(point)
            return
        super()._on_battle_victory(point)
        self._victory_seen = True
        self._disable_ready(point)
        self._register_image_match_event(_ACTIVITY, self._on_return)

    def _should_count_battle_end(self, _point: tuple[int, int]) -> bool:
        return not self._settlement_counted

    def _on_battle_end(self, point: tuple[int, int]) -> None:
        super()._on_battle_end(point)
        self._settlement_counted = True
        self._disable_ready(point)
        self._register_image_match_event(_ACTIVITY, self._on_return)

    def _on_reward(self, _point: tuple[int, int]) -> None:
        self._on_battle_end((960, 535))

    def _on_return(self, _point: tuple[int, int]) -> None:
        # 胜利页可能直接回到活动页，已结算的战斗则不再计数。
        if not self._settlement_counted:
            self._cur_battle_count += 1
            self._log_battle_count()
        if self._cur_battle_count < self.max_battle_count:
            self._wait_for_activity()


if __name__ == "__main__":
    SuperDemonBossScript().run()
