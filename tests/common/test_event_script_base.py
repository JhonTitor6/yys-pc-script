"""
yys.common.event_script_base 与 yys.common.script_meta 的单元测试。

覆盖：
- ABCMeta 强制子类实现 on_run
- 子类实例化与配置注入路径
- SCRIPT_META 缺失的 fail-fast 行为
- ConfigMeta 的 field_type 白名单校验与 frozen 不变性
"""
from __future__ import annotations

import pytest
from _pytest.monkeypatch import MonkeyPatch
from dataclasses import FrozenInstanceError
from typing import Annotated, TypedDict

from yys.common.event_script_base import YYSBaseScript
from yys.common.script_meta import ConfigMeta, ScriptMeta
from yys.soul_raid.soul_raid_script import SoulRaidScript


# ==================== 辅助：Monkey-patch OCR 初始化 ====================

class _FakeCommonOcr:
    """轻量 OCR 替身，避免测试初始化真实 OCR。"""

    def __init__(self) -> None:
        pass

    def ocr(self, img):
        return []

    def contains_text(self, img, target_text, case_sensitive=False):
        return False

    def find_text_position(self, img, target_text, similarity_threshold=0.3, case_sensitive=False):
        return None

    def find_text_positions(self, img, target_text, similarity_threshold=0.3, case_sensitive=False):
        return []


@pytest.fixture(autouse=True)
def _patch_common_ocr(monkeypatch: MonkeyPatch):
    """每个用例自动 patch 掉真实的 CommonOcr 初始化。"""
    import win_util.controller as controller
    monkeypatch.setattr(controller, "CommonOcr", _FakeCommonOcr)


# ==================== 测试 1: ABCMeta 强制 on_run ====================

def test_yys_base_script_abstract_cannot_instantiate() -> None:
    """YYSBaseScript 是抽象类，未实现 on_run 的子类不能直接实例化。"""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        YYSBaseScript("test", None)


# ==================== 测试 2: SoulRaidScript 子类可正常实例化 ====================

def test_soul_raid_script_instantiate_with_mock_env(mock_env) -> None:
    """已实现 on_run 与 SCRIPT_META 的子类可用 Mock 环境实例化。"""
    script = SoulRaidScript(env=mock_env)
    assert script.script_name == "soul_raid"
    # 未传 config 但 SoulRaidScript 有 SCRIPT_META，会自动 _apply_config({}) 兜底注入；
    # SoulRaidConfig.max_battle_count 默认 103（与父类硬编码初值巧合一致）
    assert script.max_battle_count == 103


# ==================== 测试 2b: 回归保护 - 老路径下 schema 字段也注入默认值 ====================

def test_legacy_invoke_applies_schema_defaults(mock_env) -> None:
    """老路径（config=None）但子类有 SCRIPT_META 时，schema 字段也应有默认值。

    回归保护：commit 07a8768 重构后，RealmRaidScript 直接 RealmRaidScript().run() 时
    quit_3_times_config 缺失导致 AttributeError。修复后应自动从 default_config 注入。
    """
    from yys.realm_raid.realm_raid_script import RealmRaidScript
    script = RealmRaidScript(env=mock_env)
    # quit_3_times_config 来自 RealmRaidConfig.default_config
    assert script.quit_3_times_config is True
    # max_battle_count 来自 RealmRaidConfig.default_config（覆盖父类硬编码 103）
    assert script.max_battle_count == 30


# ==================== 测试 3: _apply_config 空 config（仅 default 生效） ====================

def test_apply_config_empty_config_uses_defaults(mock_env) -> None:
    """空 config 时，所有 schema 字段应回退到 default_config。"""
    script = SoulRaidScript(env=mock_env, config={})
    # default_config: max_battle_count=103, accept_wq_type=0, loop_interval=300
    assert script.max_battle_count == 103
    assert script.accept_wq_type == 0
    assert script.loop_interval == 300


# ==================== 测试 4: _apply_config 部分 config（merge 优先级）===================

def test_apply_config_partial_config_overrides_defaults(mock_env) -> None:
    """传入部分 config 时，未传入字段走 default，传入字段走用户值。"""
    script = SoulRaidScript(env=mock_env, config={"max_battle_count": 250})
    # 用户传入 max_battle_count=250
    assert script.max_battle_count == 250
    # 其余字段走 default
    assert script.accept_wq_type == 0
    assert script.loop_interval == 300


# ==================== 测试 5: _apply_config 校验失败 max_value 越界 ====================

def test_apply_config_max_value_violation_raises(mock_env) -> None:
    """number 字段 max_value 越界时抛 ValueError。"""
    with pytest.raises(ValueError, match="高于最大值"):
        SoulRaidScript(env=mock_env, config={"max_battle_count": 9999})


# ==================== 测试 6: _apply_config 校验失败 options 不在白名单 ====================

def test_apply_config_options_violation_raises(mock_env) -> None:
    """select 字段 value 不在 options 内时抛 ValueError。"""
    with pytest.raises(ValueError, match="不在可选值"):
        SoulRaidScript(env=mock_env, config={"accept_wq_type": 999})


# ==================== 测试 7: _apply_config SCRIPT_META 缺失抛 TypeError ====================

def test_apply_config_missing_script_meta_raises_type_error(mock_env) -> None:
    """未声明 SCRIPT_META 的子类在传 config 时应 fail-fast 抛 TypeError。"""
    class DummyScript(YYSBaseScript):
        def on_run(self) -> None:
            super().on_run()

    # SCRIPT_META 未声明，YYSBaseScript 默认值为 None
    assert DummyScript.SCRIPT_META is None

    with pytest.raises(TypeError, match="必须声明 SCRIPT_META"):
        DummyScript("dummy", config={"x": 1}, env=mock_env)


# ==================== 测试 8: ConfigMeta frozen 不变性 ====================

def test_config_meta_is_frozen() -> None:
    """ConfigMeta 是 frozen dataclass，赋值应抛 FrozenInstanceError。"""
    meta = ConfigMeta(default=10, field_type="number")
    with pytest.raises(FrozenInstanceError):
        meta.field_type = "text"  # type: ignore[misc]


# ==================== 测试 9: ConfigMeta field_type 白名单校验 ====================

def test_config_meta_field_type_whitelist_valid() -> None:
    """field_type 在白名单内时合法。"""
    for t in ("text", "number", "select", "checkbox"):
        meta = ConfigMeta(field_type=t)
        assert meta.field_type == t


def test_config_meta_field_type_whitelist_invalid() -> None:
    """field_type 不在白名单时抛 ValueError。"""
    with pytest.raises(ValueError, match="不在白名单"):
        ConfigMeta(field_type="slide")


# ==================== 补充：ScriptMeta 基础构造与 default_config ====================

def test_script_meta_construction() -> None:
    """ScriptMeta 基础字段构造与默认值（hot_reloadable_set 默认为 None）。"""
    class _Schema(TypedDict, total=False):
        x: Annotated[int, ConfigMeta(default=1, field_type="number")]

    meta = ScriptMeta(
        display_name="测试",
        category="测试分类",
        config_schema=_Schema,
        default_config={"x": 1},
    )
    assert meta.display_name == "测试"
    assert meta.category == "测试分类"
    assert meta.config_schema is _Schema
    assert meta.default_config == {"x": 1}
    assert meta.hot_reloadable_set is None


# ==================== 补充：覆盖 metaclass 放宽 del 的路径 ====================

def test_apply_config_after_del_script_meta_still_raises_type_error(mock_env) -> None:
    """即使子类通过 `del SCRIPT_META` 删除继承属性，_apply_config 仍应 fail-fast 抛 TypeError。

    验证 _ABCMetaRelaxDel 的设计：del 不再抛 AttributeError，但 SCRIPT_META 查找回退到 None。
    """
    class DelScript(YYSBaseScript):
        def on_run(self) -> None:
            super().on_run()

    # del 不应抛 AttributeError（验证 metaclass 放宽生效）
    del DelScript.SCRIPT_META

    # 此时实例化 + 传 config 应触发 fail-fast
    with pytest.raises(TypeError, match="必须声明 SCRIPT_META"):
        DelScript("del_script", config={"x": 1}, env=mock_env)
