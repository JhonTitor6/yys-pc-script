from __future__ import annotations

import logging

import pytest
from pytest import LogCaptureFixture, MonkeyPatch

from ui_backend.models import ScriptCategory
from ui_backend.scripts.registry import ScriptRegistry


class ScriptWithSchema:
    """用于验证类内 schema 优先级的脚本。"""

    @classmethod
    def get_config_schema(cls) -> list[dict[str, object]]:
        return [
            {
                "key": "max_battle_count",
                "label": "类内次数",
                "field_type": "number",
                "default": 12,
                "min_value": 1,
                "max_value": 999,
            }
        ]


class ScriptWithInvalidSchema:
    """用于验证非法类内 schema 会抛出错误的脚本。"""

    @classmethod
    def get_config_schema(cls) -> dict[str, object]:
        return {"key": "max_battle_count"}


def test_registry_lists_stable_and_experimental_scripts() -> None:
    registry = ScriptRegistry()

    scripts = registry.list_scripts()
    script_ids = {item.script_id for item in scripts}

    assert "soul_raid" in script_ids
    assert "abyss_shadows" in script_ids
    assert registry.get("soul_raid").category == ScriptCategory.STABLE
    assert registry.get("abyss_shadows").category == ScriptCategory.EXPERIMENTAL


def test_default_registry_does_not_import_script_modules(
    monkeypatch: MonkeyPatch,
) -> None:
    imported_modules: list[str] = []

    def record_import(module_path: str) -> object:
        imported_modules.append(module_path)
        raise AssertionError(f"不应导入脚本模块: {module_path}")

    monkeypatch.setattr(
        "ui_backend.scripts.registry.import_module",
        record_import,
    )

    scripts = ScriptRegistry().list_scripts()

    assert {item.script_id for item in scripts}
    assert imported_modules == []


def test_class_schema_overrides_registry_schema() -> None:
    registry = ScriptRegistry(
        entries=[
            {
                "script_id": "custom",
                "display_name": "自定义",
                "module_path": "tests.ui_backend.test_script_registry",
                "class_name": "ScriptWithSchema",
                "category": "stable",
                "description": "测试脚本",
                "config_schema": [
                    {
                        "key": "max_battle_count",
                        "label": "注册表次数",
                        "field_type": "number",
                        "default": 99,
                    }
                ],
            }
        ]
    )

    definition = registry.get("custom")

    assert definition.config_schema[0].label == "类内次数"
    assert definition.default_config["max_battle_count"] == 12


def test_import_runtime_error_falls_back_to_registry_schema(
    monkeypatch: MonkeyPatch,
    caplog: LogCaptureFixture,
) -> None:
    def raise_runtime_error(module_path: str) -> object:
        raise RuntimeError("导入副作用失败")

    caplog.set_level(logging.WARNING, logger="ui_backend.scripts.registry")
    monkeypatch.setattr(
        "ui_backend.scripts.registry.import_module",
        raise_runtime_error,
    )

    registry = ScriptRegistry(
        entries=[
            {
                "script_id": "custom",
                "display_name": "自定义",
                "module_path": "tests.ui_backend.test_script_registry",
                "class_name": "ScriptWithSchema",
                "category": "stable",
                "description": "测试脚本",
                "config_schema": [
                    {
                        "key": "max_battle_count",
                        "label": "注册表次数",
                        "field_type": "number",
                        "default": 99,
                    }
                ],
            }
        ]
    )

    definition = registry.get("custom")

    assert definition.config_schema[0].label == "注册表次数"
    assert definition.default_config["max_battle_count"] == 99
    assert "custom" in caplog.text
    assert "导入副作用失败" in caplog.text


def test_invalid_class_schema_raises_type_error() -> None:
    with pytest.raises(TypeError, match="get_config_schema 必须返回 list"):
        ScriptRegistry(
            entries=[
                {
                    "script_id": "custom",
                    "display_name": "自定义",
                    "module_path": "tests.ui_backend.test_script_registry",
                    "class_name": "ScriptWithInvalidSchema",
                    "category": "stable",
                    "description": "测试脚本",
                    "config_schema": [
                        {
                            "key": "max_battle_count",
                            "label": "注册表次数",
                            "field_type": "number",
                            "default": 99,
                        }
                    ],
                }
            ]
        )
