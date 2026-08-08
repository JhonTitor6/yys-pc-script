from __future__ import annotations

from typing import Annotated, Any, Optional, TYPE_CHECKING, TypedDict, get_type_hints

from win_util.image import ImageMatchConfig
from yys.common.entry_runtime import SafeOverlayPolicy, TaskEntrySpec
from yys.common.event_script_base import YYSBaseScript, _extract_config_meta
from yys.common.script_meta import ConfigMeta, ScriptMeta

if TYPE_CHECKING:
    from tests.common.environment.base import GameEnvironment


class SoulRaidConfig(TypedDict, total=False):
    """御魂脚本的可配置字段（D-2 形式：TypedDict + Annotated[..., ConfigMeta(...)])。"""
    max_battle_count: Annotated[int, ConfigMeta(
        default=103,
        min_value=1,
        max_value=999,
        field_type="number",
        label="最大战斗次数",
        group="基础",
        help="脚本自动停止前执行的最大战斗次数（1-999）",
        hot_reloadable=True,
    )]
    accept_wq_type: Annotated[int, ConfigMeta(
        default=0,
        options=[{"value": 0, "label": "拒绝"}, {"value": 1, "label": "全部接受"}, {"value": 2, "label": "只接勾协"}],
        field_type="select",
        label="悬赏封印",
        group="基础",
        help="检测到悬赏封印邀请时的处理策略",
        hot_reloadable=False,
    )]
    loop_interval: Annotated[int, ConfigMeta(
        default=300,
        min_value=50,
        max_value=5000,
        field_type="number",
        label="循环间隔(ms)",
        group="高级",
        help="两次战斗之间的额外等待时间（毫秒），仅在下一次启动生效",
        hot_reloadable=False,
    )]


class SoulRaidScript(YYSBaseScript):
    """
    御魂挂机
    """
    SCRIPT_META = ScriptMeta(
        display_name="御魂",
        category="日常",
        config_schema=SoulRaidConfig,
        default_config={
            "max_battle_count": 103,
            "accept_wq_type": 0,
            "loop_interval": 300,
        },
    )
    # 新入口契约：御魂作为首个试点，从任意可识别页面安全进入御魂选择界面
    # （任务 08-08-universal-entry-recovery；旧 entry_scene 声明已废弃）
    entry_spec: Optional[TaskEntrySpec] = TaskEntrySpec(
        target_scene="soul_selection",
        safe_overlay_policy=SafeOverlayPolicy(
            settlement_templates=(
                "yys/images/battle_end_success.bmp",
                "yys/images/battle_end.bmp",
                "yys/images/battle_end_loss.bmp",
                "yys/images/battle_end_1.bmp",
                "yys/images/battle_end_2.bmp",
            ),
            refuse_wanted_quests=True,
            wanted_quest_reject_template="yys/images/xuanshangfengyin_reject.bmp",
        ),
    )
    # 旧入口场景声明（已废弃，保留注释说明迁移过程）
    # entry_scene: Optional[str] = "soul_selection"

    @classmethod
    def get_config_schema(cls) -> list[dict[str, Any]]:
        """从 SCRIPT_META 反射 config_schema 为 wire format list of dict。

        Returns:
            list[dict]: 每个 dict 含 key/label/field_type/default/min_value/max_value/options。
                         与 ui_backend.models.ConfigField 字段命名一致。
        """
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
                "description": config_meta.help,
                "unit": config_meta.unit,
                "sensitive": config_meta.sensitive,
            })
        return result

    def __init__(
        self,
        script_name: str = "soul_raid",
        env: Optional["GameEnvironment"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """初始化御魂脚本，支持测试环境注入与配置注入。

        Args:
            script_name: 脚本名，默认 "soul_raid"（与 SCRIPT_META.display_name 一致）。
            env: GameEnvironment 实例，用于 Mock 测试时注入。
            config: 配置字典（可选）；为 None 时走老路径不应用配置。

        Note:
            签名与 base 类 (script_name, config, env) 保持一致（仅顺序调整为
            script_name 在最前以兼容 RunManager 的 script_class(request.script_id, config=...) 调用）。
        """
        super().__init__(script_name, config=config, env=env)
        # 注册御魂挑战按钮事件
        self._register_image_match_event(ImageMatchConfig("yys/soul_raid/images/yuhun_tiaozhan.bmp"), self._on_yuhun_tiaozhan)
        # 注册锁定接受邀请事件
        self._register_image_match_event(ImageMatchConfig("yys/soul_raid/images/lock_accept_invitation.bmp"), self._on_lock_accept_invitation)

    def on_run(self) -> None:
        """脚本启动钩子（实现抽象基类要求）。"""
        super().on_run()

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
