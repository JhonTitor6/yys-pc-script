from __future__ import annotations

import time
from typing import Annotated, Any, Optional, TYPE_CHECKING, TypedDict, get_type_hints

from yys.common.event_script_base import YYSBaseScript, ImageMatchConfig, _extract_config_meta, random_sleep
from yys.common.script_meta import ConfigMeta, ScriptMeta

if TYPE_CHECKING:
    from tests.common.environment.base import GameEnvironment


class DouJiConfig(TypedDict, total=False):
    """斗技脚本的可配置字段。"""
    max_battle_count: Annotated[int, ConfigMeta(
        default=30,
        min_value=1,
        max_value=999,
        field_type="number",
        label="最大战斗次数",
        group="基础",
        help="脚本自动停止前执行的最大战斗次数（1-999）",
        hot_reloadable=True,
    )]


class DouJi(YYSBaseScript):
    """
    斗技挂机
    """
    SCRIPT_META = ScriptMeta(
        display_name="斗技",
        category="日常",
        config_schema=DouJiConfig,
        default_config={"max_battle_count": 30},
    )

    @classmethod
    def get_config_schema(cls) -> list[dict[str, Any]]:
        """从 SCRIPT_META 反射 config_schema 为 wire format list of dict。"""
        meta = cls.SCRIPT_META
        if meta is None or meta.config_schema is None:
            return []
        try:
            hints = get_type_hints(meta.config_schema, include_extras=True)
        except Exception:
            hints = {}
        result: list[dict[str, Any]] = []
        for field_name, annotated_type in hints.items():
            config_meta = _extract_config_meta(annotated_type)
            if config_meta is None:
                continue
            result.append({
                "key": field_name,
                "label": config_meta.label or field_name,
                "field_type": config_meta.field_type,
                "default": config_meta.default,
                "min_value": config_meta.min_value,
                "max_value": config_meta.max_value,
                "options": list(config_meta.options or []),
                "hot_reloadable": config_meta.hot_reloadable,
            })
        return result

    def __init__(
        self,
        script_name: str = "douji",
        env: Optional["GameEnvironment"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """初始化斗技脚本。

        Args:
            script_name: 脚本名，默认 "douji"。
            env: GameEnvironment 实例，用于 Mock 测试时注入。
            config: 配置字典（可选）。
        """
        super().__init__(script_name, config=config, env=env)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/douji_zhan.bmp", similarity=0.7), self._on_douji_zhan)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/change_to_auto_battle.bmp"), self._on_change_to_auto_battle)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/douji_selection_auto_up.bmp", similarity=0.7),
                                         self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/douji_battle_end.bmp"), self._on_battle_end)
        self._register_image_match_event(ImageMatchConfig("yys/images/battle_end_loss.bmp"), self._on_battle_end)
        self._register_image_match_event(ImageMatchConfig("yys/douji/images/douji_battle_end_victory.bmp", similarity=0.6),
                                         self._on_battle_victory)
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_close.bmp", similarity=0.7), self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/images/ready.bmp", similarity=0.7), self.bg_left_click)

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

    def _on_change_to_auto_battle(self, point):
        self.bg_left_click(point)
        random_sleep(3, 4)
        # 标记左四
        self.bg_left_click((746, 361), x_range=5, y_range=5)

    def on_run(self):
        """脚本启动钩子（实现抽象基类要求）"""
        super().on_run()


if __name__ == '__main__':
    DouJi().run()
