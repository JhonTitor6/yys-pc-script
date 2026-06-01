from __future__ import annotations

import time
from typing import Annotated, Any, Optional, TYPE_CHECKING, TypedDict, get_type_hints

from win_util.event import ImageMatchConfig, random_sleep
from yys.common import BATTLE_END_SLEEP, BATTLE_END_CLICK_RANGE_X, BATTLE_END_CLICK_RANGE_Y, BATTLE_END_CLICK_SLEEP
from yys.common.event_script_base import YYSBaseScript, _extract_config_meta
from yys.common.script_meta import ConfigMeta, ScriptMeta

if TYPE_CHECKING:
    from tests.common.environment.base import GameEnvironment


class OmoikaneConfig(TypedDict, total=False):
    """思金神脚本的可配置字段。"""
    max_battle_count: Annotated[int, ConfigMeta(
        default=150,
        min_value=1,
        max_value=999,
        field_type="number",
        label="最大战斗次数",
        group="基础",
        help="脚本自动停止前执行的最大战斗次数（1-999）",
        hot_reloadable=True,
    )]


class OmoikaneScript(YYSBaseScript):
    """思金神挂机：循环点击挑战按钮。"""
    SCRIPT_META = ScriptMeta(
        display_name="思金神",
        category="日常",
        config_schema=OmoikaneConfig,
        default_config={"max_battle_count": 150},
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
        script_name: str = "omoikane",
        env: Optional["GameEnvironment"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """初始化思金神脚本。

        Args:
            script_name: 脚本名，默认 "omoikane"。
            env: GameEnvironment 实例，用于 Mock 测试时注入。
            config: 配置字典（可选）。
        """
        super().__init__(script_name, config=config, env=env)
        self._register_image_match_event(ImageMatchConfig("yys/omoikane/images/chanllange.png"), self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_close.bmp"), self.bg_left_click)

    def _on_battle_end(self, point: tuple):
        # 不可去掉。如果不等一会，没点掉导致触发多次的话，会多次触发_cur_battle_count+=1
        time.sleep(BATTLE_END_SLEEP)
        # 使用匹配到的实际位置点击
        self.bg_left_click((995, 540), x_range=BATTLE_END_CLICK_RANGE_X, y_range=BATTLE_END_CLICK_RANGE_Y)
        random_sleep(0.5, 1)
        self.bg_left_click((995, 540), x_range=BATTLE_END_CLICK_RANGE_X, y_range=BATTLE_END_CLICK_RANGE_Y)
        self._cur_battle_count += 1
        self._log_battle_count()
        time.sleep(BATTLE_END_CLICK_SLEEP)

    def on_run(self):
        """脚本启动钩子（实现抽象基类要求）"""
        super().on_run()


if __name__ == '__main__':
    OmoikaneScript().set_max_battle_count(150).run()
