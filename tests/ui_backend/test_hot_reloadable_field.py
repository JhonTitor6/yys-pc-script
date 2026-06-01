"""Step 4: ConfigField.hot_reloadable 透传链路测试。

覆盖范围：
1. ConfigField 构造时 hot_reloadable 字段默认 True
2. ConfigField 显式传 hot_reloadable=False 也正确存储
3. _parse_field 从 dict 解析 hot_reloadable 字段
4. PATCH /api/scripts/{id}/config 响应含 note 文案（plan §4 B2 决策）
"""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from ui_backend.app import create_app
from ui_backend.models import ConfigField
from ui_backend.scripts.registry import ScriptRegistry


class TestConfigFieldHotReloadable:
    """ConfigField 字段的 hot_reloadable 行为。"""

    def test_default_is_true(self) -> None:
        """ConfigField 未指定 hot_reloadable 时默认 True（frozen dataclass 默认值）。"""
        field = ConfigField(
            key="max_battle_count",
            label="次数",
            field_type="number",
            default=10,
        )
        assert field.hot_reloadable is True

    def test_explicit_false(self) -> None:
        """ConfigField 显式传 hot_reloadable=False 正确存储。"""
        field = ConfigField(
            key="loop_interval",
            label="循环间隔",
            field_type="number",
            default=5,
            hot_reloadable=False,
        )
        assert field.hot_reloadable is False


class TestParseFieldHotReloadable:
    """registry._parse_field 对 hot_reloadable 字段的解析。"""

    def test_parse_field_reads_hot_reloadable(self) -> None:
        """_parse_field 从 dict 正确解析 hot_reloadable 字段（含默认/显式两种）。"""
        registry = ScriptRegistry()
        parser = registry._parse_field  # type: ignore[attr-defined]

        # 默认（缺省 hot_reloadable）：回退到 True
        field_default = parser({
            "key": "alpha",
            "label": "Alpha",
            "field_type": "number",
            "default": 1,
        })
        assert field_default.hot_reloadable is True

        # 显式 False
        field_false = parser({
            "key": "beta",
            "label": "Beta",
            "field_type": "number",
            "default": 2,
            "hot_reloadable": False,
        })
        assert field_false.hot_reloadable is False

        # 显式 True
        field_true = parser({
            "key": "gamma",
            "label": "Gamma",
            "field_type": "number",
            "default": 3,
            "hot_reloadable": True,
        })
        assert field_true.hot_reloadable is True


class TestPatchConfigResponse:
    """PATCH /api/scripts/{id}/config 响应文案（B2 决策）。"""

    def test_patch_response_includes_note(self, tmp_path: Any) -> None:
        """PATCH 成功响应含 status/saved/applied/note 四个字段。"""
        db_path = tmp_path / "test_hot_reloadable.db"
        app = create_app(db_path=str(db_path))
        client = TestClient(app)

        resp = client.patch(
            "/api/scripts/soul_raid/config",
            json={"max_battle_count": 50},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["saved"] is True
        assert body["applied"] is False
        assert "note" in body
        assert isinstance(body["note"], str) and body["note"]
