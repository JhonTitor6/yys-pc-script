# yys.common.script_meta - 脚本元数据定义
# 提供 ConfigMeta 与 ScriptMeta 两个 dataclass，用于脚本自动注册
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ConfigMeta:
    """单个配置项的元数据，用于前端渲染表单与运行时校验。

    Attributes:
        default: 字段默认值。
        min_value: 数值类型字段的最小值（仅 field_type="number" 时生效）。
        max_value: 数值类型字段的最大值（仅 field_type="number" 时生效）。
        options: 选项列表，每项为 {"value": ..., "label": ...}（仅 field_type="select" 时生效）。
        label: 前端展示的中文名称。
        group: 前端表单分组名，用于将相关字段聚合。
        help: 前端表单的 tooltip 帮助文本。
        unit: 字段单位，用于前端展示。
        sensitive: 是否属于敏感字段，前端展示时应脱敏。
        hot_reloadable: 是否支持热重载；为 True 时 PATCH 端点会立即注入到当前 run 的实例属性。
        field_type: 前端渲染的控件类型，支持 "text" / "number" / "select" / "checkbox"。
    """
    default: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    options: Optional[list[dict[str, Any]]] = None
    label: str = ""
    group: str = "基础"
    help: str = ""
    unit: Optional[str] = None
    sensitive: bool = False
    hot_reloadable: bool = False
    field_type: str = "text"

    def __post_init__(self) -> None:
        valid_types = {"text", "number", "select", "checkbox"}
        if self.field_type not in valid_types:
            raise ValueError(
                f"ConfigMeta.field_type={self.field_type!r} 不在白名单 {valid_types}"
            )


@dataclass(frozen=True)
class ScriptMeta:
    """脚本元数据，挂在每个 YYSBaseScript 子类的 SCRIPT_META 类属性上。

    Attributes:
        display_name: 脚本的中文显示名（用于 GUI 列表与编排界面）。
        category: 脚本分类（如 "日常"、"悬赏" 等，用于 GUI 分组展示）。
        config_schema: TypedDict 类型，字段使用 Annotated[..., ConfigMeta(...)] 标注。
        default_config: 字段名到默认值的映射，键集合应与 config_schema 的字段一致。
        hot_reloadable_set: Step 3 registry 扫描时填充：config_schema 中标 hot_reloadable=True 的字段名集合。
    """
    display_name: str
    category: str
    config_schema: Optional[type]
    default_config: dict[str, Any] = field(default_factory=dict)
    hot_reloadable_set: Optional[frozenset[str]] = None
