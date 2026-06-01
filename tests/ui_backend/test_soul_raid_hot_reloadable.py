"""Step 4: soul_raid 端到端 hot_reloadable 透传测试。

覆盖：
1. SoulRaidScript.get_config_schema() 输出 dict 含 hot_reloadable 字段
   - max_battle_count: True（战斗次数热生效）
   - accept_wq_type: False（接受邀请类型启动时读取）
   - loop_interval: False（循环间隔启动时读取）
2. GET /api/scripts 透传 hot_reloadable 到 config_schema 序列化结果
"""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from ui_backend.app import create_app
from yys.soul_raid.soul_raid_script import SoulRaidScript


class TestSoulRaidConfigSchemaHotReloadable:
    """SoulRaidScript.get_config_schema 反射 hot_reloadable。"""

    def test_get_config_schema_contains_hot_reloadable(self) -> None:
        """get_config_schema 输出 dict 含 hot_reloadable 字段且取值符合预期。"""
        schema = SoulRaidScript.get_config_schema()
        by_key = {item["key"]: item for item in schema}

        # 三个字段都必须存在 hot_reloadable
        for key in ("max_battle_count", "accept_wq_type", "loop_interval"):
            assert key in by_key, f"缺少字段: {key}"
            assert "hot_reloadable" in by_key[key], (
                f"{key} 缺少 hot_reloadable 字段"
            )

        # 取值校验
        assert by_key["max_battle_count"]["hot_reloadable"] is True
        assert by_key["accept_wq_type"]["hot_reloadable"] is False
        assert by_key["loop_interval"]["hot_reloadable"] is False


class TestGetScriptsHotReloadable:
    """GET /api/scripts 透传 hot_reloadable 到 API 响应。"""

    def test_get_scripts_soul_raid_hot_reloadable(self, tmp_path: Any) -> None:
        """/api/scripts 返回 soul_raid config_schema 每字段均含 hot_reloadable。"""
        db_path = tmp_path / "test_soul_raid_api.db"
        app = create_app(db_path=str(db_path))
        client = TestClient(app)

        resp = client.get("/api/scripts")
        assert resp.status_code == 200
        scripts = resp.json()
        soul_raid = next(s for s in scripts if s["script_id"] == "soul_raid")
        fields = {f["key"]: f for f in soul_raid["config_schema"]}

        # 三个字段都要透传
        assert "hot_reloadable" in fields["max_battle_count"]
        assert "hot_reloadable" in fields["accept_wq_type"]
        assert "hot_reloadable" in fields["loop_interval"]
        assert fields["max_battle_count"]["hot_reloadable"] is True
        assert fields["accept_wq_type"]["hot_reloadable"] is False
        assert fields["loop_interval"]["hot_reloadable"] is False
