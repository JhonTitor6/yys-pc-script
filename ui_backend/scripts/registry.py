from __future__ import annotations

import logging
from importlib import import_module
from typing import Any, Literal, cast

from ui_backend.models import ConfigField, ScriptCategory, ScriptDefinition
from ui_backend.scripts.default_registry import DEFAULT_SCRIPT_ENTRIES

FieldType = Literal["number", "text", "select", "boolean"]
logger = logging.getLogger(__name__)


class ScriptRegistry:
    """脚本定义注册表。"""

    def __init__(self, entries: list[dict[str, object]] | None = None) -> None:
        """初始化注册表，可传入自定义脚本条目。"""
        self._using_default_entries = entries is None
        self._entries = entries if entries is not None else DEFAULT_SCRIPT_ENTRIES
        self._definitions = self._load_definitions()

    def list_scripts(self) -> list[ScriptDefinition]:
        """返回按注册顺序排列的脚本定义列表。"""
        return list(self._definitions.values())

    def get(self, script_id: str) -> ScriptDefinition:
        """按脚本 ID 获取脚本定义。"""
        try:
            return self._definitions[script_id]
        except KeyError as exc:
            raise KeyError(f"未知脚本: {script_id}") from exc

    def load_class(self, script_id: str) -> type:
        """导入并返回脚本类。"""
        definition = self.get(script_id)
        module = import_module(definition.module_path)
        script_class = getattr(module, definition.class_name)
        if not isinstance(script_class, type):
            raise TypeError(f"脚本对象不是类: {script_id}")
        return script_class

    def _load_definitions(self) -> dict[str, ScriptDefinition]:
        definitions: dict[str, ScriptDefinition] = {}
        for entry in self._entries:
            schema_items = self._schema_items_for(entry)
            fields = [self._parse_field(item) for item in schema_items]
            script_id = str(entry["script_id"])
            definitions[script_id] = ScriptDefinition(
                script_id=script_id,
                display_name=str(entry["display_name"]),
                module_path=str(entry["module_path"]),
                class_name=str(entry["class_name"]),
                category=ScriptCategory(str(entry["category"])),
                description=str(entry["description"]),
                config_schema=fields,
                default_config={field.key: field.default for field in fields},
            )
        return definitions

    def _schema_items_for(self, entry: dict[str, object]) -> list[dict[str, Any]]:
        reflected = self._schema_from_class(entry)
        if reflected:
            return reflected
        return cast(list[dict[str, Any]], entry["config_schema"])

    def _schema_from_class(
        self, entry: dict[str, object]
    ) -> list[dict[str, Any]] | None:
        try:
            module = import_module(str(entry["module_path"]))
            script_class = getattr(module, str(entry["class_name"]))
        except Exception as exc:
            logger.warning(
                "脚本 %s 导入类内 schema 失败，回退到注册表配置: %s",
                entry.get("script_id", "<unknown>"),
                exc,
            )
            return None

        schema_getter = getattr(script_class, "get_config_schema", None)
        if schema_getter is None:
            return None

        schema = schema_getter()
        if not isinstance(schema, list):
            raise TypeError("get_config_schema 必须返回 list")
        return cast(list[dict[str, Any]], schema)

    def _parse_field(self, item: dict[str, Any]) -> ConfigField:
        return ConfigField(
            key=str(item["key"]),
            label=str(item["label"]),
            field_type=cast(FieldType, item["field_type"]),
            default=item.get("default"),
            min_value=cast(int | float | None, item.get("min_value")),
            max_value=cast(int | float | None, item.get("max_value")),
            options=cast(list[dict[str, Any]], item.get("options", [])),
            hot_reloadable=cast(bool, item.get("hot_reloadable", True)),
        )
