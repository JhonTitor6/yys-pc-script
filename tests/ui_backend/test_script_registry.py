from __future__ import annotations

import logging
import ast
from pathlib import Path

import pytest
from pytest import LogCaptureFixture, MonkeyPatch

from ui_backend.models import ScriptCategory
from ui_backend.scripts.registry import ScriptRegistry


def test_registered_scripts_are_in_packaging_module_list() -> None:
    """产品契约：脚本列表中的动态模块在打包清单中存在，避免开发可用而发行版缺失。"""
    tree = ast.parse((Path(__file__).resolve().parents[2] / "build_backend.spec").read_text(encoding="utf-8"))
    modules = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "YYS_MODULES" for target in node.targets))
    assert {item.module_path for item in ScriptRegistry().list_scripts()} <= set(modules)


def test_daily_scripts_are_independent_experimental_definitions() -> None:
    """产品契约：寄养和逢魔独立运行；未实测和缺录制时保留实验分类。"""
    registry = ScriptRegistry()
    assert registry.load_class("realm_foster").__name__ == "RealmFosterScript"
    assert registry.load_class("fengmo").__name__ == "FengmoScript"
    for script_id in ("realm_foster", "fengmo", "daily_collect", "soul_soil", "daily_activity_rewards"):
        assert registry.get(script_id).category == ScriptCategory.EXPERIMENTAL
    assert registry.get("fengmo").default_config == {"lineup_group": "逢魔", "lineup_name": "通用"}
    assert registry.get("soul_soil").default_config == {
        "max_battle_count": 10, "lineup_group": "御魂", "lineup_name": "魂土",
    }


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


def test_regional_demon_boss_is_fixed_single_run_definition() -> None:
    """地域鬼王不向 GUI 暴露结界突破的次数或重试配置。"""
    definition = ScriptRegistry().get("regional_demon_boss")

    assert definition.display_name == "地域鬼王"
    assert definition.category == ScriptCategory.STABLE
    assert definition.config_schema == []
    assert definition.default_config == {}


def test_default_registry_does_not_import_script_modules(
    monkeypatch: MonkeyPatch,
) -> None:
    """默认 entries 也会尝试反射 SCRIPT_META（auto-registry Step 3 设计）。

    5 个走老路径的子类无 get_config_schema() → 反射失败 → 走 entries fallback。
    soul_raid 有 get_config_schema() → 反射成功 → 覆盖 entry 的手写 schema。
    即便 import_module 失败，registry 仍能 list 全部脚本（fallback 路径）。
    """
    imported_modules: list[str] = []

    def raise_on_import(module_path: str) -> object:
        imported_modules.append(module_path)
        raise RuntimeError(f"反射阶段导入失败: {module_path}")

    monkeypatch.setattr(
        "ui_backend.scripts.registry.import_module",
        raise_on_import,
    )

    scripts = ScriptRegistry().list_scripts()

    script_ids = {item.script_id for item in scripts}
    # 所有默认条目都尝试反射；失败时仍保留独立日常脚本。
    assert "yys.soul_raid" in imported_modules
    assert "yys.realm_raid" in imported_modules
    # 即便全部反射失败，registry 仍能 list 全部脚本（走 entries fallback）
    assert script_ids == {
        "soul_raid", "realm_raid", "exploration_28", "yuling", "abyss_shadows",
        "loop_challenge", "douji", "fujiwara", "omoikane", "regional_demon_boss",
        "realm_foster", "fengmo", "daily_collect", "soul_soil", "daily_activity_rewards",
    }
    # fallback 时，soul_raid 仍使用 entry 手写的 max_battle_count=103（无 accept_wq_type）
    soul_raid = next(item for item in scripts if item.script_id == "soul_raid")
    keys = {field.key for field in soul_raid.config_schema}
    assert "max_battle_count" in keys
    assert "accept_wq_type" not in keys  # fallback 路径无 accept_wq_type

    abyss_shadows = next(
        item for item in scripts if item.script_id == "abyss_shadows"
    )
    abyss_keys = {field.key for field in abyss_shadows.config_schema}
    assert {
        "boss_damage_limit",
        "commander_damage_limit",
        "elite_damage_limit",
    } <= abyss_keys
    damage_limits = {
        field.key: field
        for field in abyss_shadows.config_schema
        if field.key.endswith("_damage_limit")
    }
    expected = {
        "boss_damage_limit": ("首领伤害限制", 1),
        "commander_damage_limit": ("副将伤害限制", 1),
        "elite_damage_limit": ("精英伤害限制", 6000000),
    }
    for key, (label, default) in expected.items():
        field = damage_limits[key]
        assert field.label == label
        assert field.default == default
        assert field.min_value == 0
        assert field.max_value == 999999999
        assert field.hot_reloadable is False


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


# ==================== auto-registry Step 3 新增 case ====================


def test_default_registry_soul_raid_uses_script_meta_reflection() -> None:
    """soul_raid 走 SCRIPT_META 反射路径：config_schema 来自 SCRIPT_META。

    验证点：
    - 含 max_battle_count/accept_wq_type/loop_interval 三字段
    - 字段来自 SCRIPT_META 反射（field_type="number"/"select"）
    - default_config 来自 SCRIPT_META.default_config
    """
    registry = ScriptRegistry()
    soul_raid = registry.get("soul_raid")

    fields = {field.key: field for field in soul_raid.config_schema}
    # 3 字段都来自 SCRIPT_META 反射（default_registry.py 手写只有 2 字段）
    assert set(fields.keys()) == {"max_battle_count", "accept_wq_type", "loop_interval"}
    assert fields["max_battle_count"].field_type == "number"
    assert fields["accept_wq_type"].field_type == "select"
    assert fields["loop_interval"].field_type == "number"
    # accept_wq_type 的 options 来自 SCRIPT_META 反射（3 个值）
    assert len(fields["accept_wq_type"].options) == 3
    # default_config 来自 SCRIPT_META.default_config
    assert soul_raid.default_config == {
        "max_battle_count": 103,
        "accept_wq_type": 0,
        "loop_interval": 300,
    }


def test_abyss_shadows_exposes_separate_damage_limits() -> None:
    """产品契约：狭间暗域通过 SCRIPT_META 暴露三类独立伤害阈值。"""
    abyss_shadows = ScriptRegistry().get("abyss_shadows")
    fields = {field.key: field for field in abyss_shadows.config_schema}

    expected = {
        "boss_damage_limit": ("首领伤害限制", 1),
        "commander_damage_limit": ("副将伤害限制", 1),
        "elite_damage_limit": ("精英伤害限制", 6000000),
    }
    for key, (label, default) in expected.items():
        field = fields[key]
        assert abyss_shadows.default_config[key] == default
        assert field.label == label
        assert field.field_type == "number"
        assert field.min_value == 0
        assert field.max_value == 999999999
        assert field.hot_reloadable is False


def test_default_registry_migrated_scripts_use_script_meta_reflection() -> None:
    """Step 5：realm_raid/exploration/yuling/abyss_shadows 已迁移到 SCRIPT_META。

    验证点：
    - 它们都通过 SCRIPT_META 反射返回 config_schema（不再走 entries fallback）
    - 字段数与 SCRIPT_META 定义一致
    """
    registry = ScriptRegistry()

    # realm_raid（SCRIPT_META 含 max_battle_count + quit_3_times_config）
    realm_raid = registry.get("realm_raid")
    keys = {field.key for field in realm_raid.config_schema}
    assert keys == {"max_battle_count", "quit_3_times_config"}
    assert realm_raid.default_config["max_battle_count"] == 30
    assert realm_raid.default_config["quit_3_times_config"] is True

    # exploration（SCRIPT_META 含 max_battle_count，默认 244）
    exploration_28 = registry.get("exploration_28")
    keys = {field.key for field in exploration_28.config_schema}
    assert keys == {"max_battle_count"}
    assert exploration_28.default_config["max_battle_count"] == 244

    # yuling（SCRIPT_META 含 max_battle_count，默认 150）
    yuling = registry.get("yuling")
    keys = {field.key for field in yuling.config_schema}
    assert keys == {"max_battle_count"}
    assert yuling.default_config["max_battle_count"] == 150

    # abyss_shadows（次数配置 + 三类独立伤害限制）
    abyss_shadows = registry.get("abyss_shadows")
    keys = {field.key for field in abyss_shadows.config_schema}
    assert keys == {
        "boss_count",
        "boss_damage_limit",
        "commander_count",
        "commander_damage_limit",
        "elite_count",
        "elite_damage_limit",
    }
    assert abyss_shadows.default_config == {
        "boss_count": 2,
        "boss_damage_limit": 1,
        "commander_count": 4,
        "commander_damage_limit": 1,
        "elite_count": 6,
        "elite_damage_limit": 6000000,
    }

    boss_damage_limit = next(
        field
        for field in abyss_shadows.config_schema
        if field.key == "boss_damage_limit"
    )
    assert boss_damage_limit.label == "首领伤害限制"
    assert boss_damage_limit.min_value == 0
    assert boss_damage_limit.max_value == 999999999


def test_default_registry_reflection_failure_falls_back_to_entries(
    monkeypatch: MonkeyPatch,
) -> None:
    """反射（import_module 或 get_config_schema）失败时回退到 entries。

    验证点：
    - monkeypatch 让 soul_raid 导入抛错 → 反射失败
    - soul_raid 仍能 list，使用 default_registry.py 的手写 config_schema
    - 不抛异常（fallback 路径不阻塞 list_scripts）
    """
    def raise_on_import(module_path: str) -> object:
        raise RuntimeError("反射阶段导入失败")

    monkeypatch.setattr(
        "ui_backend.scripts.registry.import_module",
        raise_on_import,
    )

    # 即便反射全部失败，新增日常脚本仍在默认列表中。
    scripts = ScriptRegistry().list_scripts()
    script_ids = {item.script_id for item in scripts}
    assert script_ids == {
        "soul_raid", "realm_raid", "exploration_28", "yuling", "abyss_shadows",
        "loop_challenge", "douji", "fujiwara", "omoikane", "regional_demon_boss",
        "realm_foster", "fengmo", "daily_collect", "soul_soil", "daily_activity_rewards",
    }

    # soul_raid 走 fallback（无 accept_wq_type）
    soul_raid = next(item for item in scripts if item.script_id == "soul_raid")
    keys = {field.key for field in soul_raid.config_schema}
    assert keys == {"max_battle_count", "loop_interval"}  # 仅 default_registry.py 手写的 2 字段
