from __future__ import annotations

from typing import Annotated, Any, Optional, TYPE_CHECKING, TypedDict, get_type_hints

from win_util.event import ImageMatchConfig
from yys.common.event_script_base import YYSBaseScript, _extract_config_meta
from yys.common.script_meta import ConfigMeta, ScriptMeta

if TYPE_CHECKING:
    from tests.common.environment.base import GameEnvironment


class YulingConfig(TypedDict, total=False):
    """御灵脚本的可配置字段。"""
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


class AutoYuling(YYSBaseScript):
    """御灵挂机：循环点击御灵挑战按钮。"""
    SCRIPT_META = ScriptMeta(
        display_name="御灵",
        category="日常",
        config_schema=YulingConfig,
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
        script_name: str = "yuling",
        env: Optional["GameEnvironment"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """初始化御灵脚本。

        Args:
            script_name: 脚本名，默认 "yuling"。
            env: GameEnvironment 实例，用于 Mock 测试时注入。
            config: 配置字典（可选）。
        """
        super().__init__(script_name, config=config, env=env)
        self._register_image_match_event(ImageMatchConfig("yys/yuling/images/yuling_tiaozhan.bmp"), self.bg_left_click)

    def on_run(self):
        """脚本启动钩子（实现抽象基类要求）"""
        super().on_run()


if __name__ == '__main__':
    AutoYuling().set_max_battle_count(150).run()
