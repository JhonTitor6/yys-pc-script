"""soul_raid 真实 __init__ 端到端测试（不 mock soul_raid 自身）。

目的：验证 P7 修复后 SoulRaidScript.__init__ 接受 (script_name, env, config) 签名
（与 base 类 YYSBaseScript 一致），避免 RunManager.start 中
script_class(request.script_id, config=...) 调用再次触发 TypeError。

关键点：
- 真实 import soul_raid（不 patch）
- 真实调用 __init__
- 使用 MockEnvironment 避免真实窗口查找
- 验证构造后 script_name / max_battle_count / accept_wq_type / loop_interval 正确注入
"""
from __future__ import annotations

import inspect

from tests.common.environment.mock_environment import MockEnvironment
from yys.soul_raid.soul_raid_script import SoulRaidScript


class TestSoulRaidRealInit:
    """SoulRaidScript 真实构造测试（不 mock soul_raid 自身）"""

    def test_signature_matches_base_class(self) -> None:
        """验证 SoulRaidScript.__init__ 第一位置参数是 script_name（与 base 一致）。"""
        sig = inspect.signature(SoulRaidScript.__init__)
        params = list(sig.parameters.keys())
        # 第一位置参数（self 之后）必须是 script_name
        assert params[0] == "self"
        assert params[1] == "script_name", (
            f"第一位置参数应是 script_name，实际 {params[1]}"
        )
        # config 必须是命名参数（RunManager 走关键字注入）
        assert "config" in params

    def test_soul_raid_real_init_with_config(self) -> None:
        """真实端到端：soul_raid 接受 (script_name, env, config) 签名（不 mock soul_raid）。"""
        env = MockEnvironment()
        script = SoulRaidScript(
            "soul_raid",
            env=env,
            config={
                "max_battle_count": 50,
                "accept_wq_type": 1,
                "loop_interval": 200,
            },
        )
        assert script.script_name == "soul_raid"
        assert script.max_battle_count == 50
        assert script.accept_wq_type == 1
        assert script.loop_interval == 200

    def test_soul_raid_default_init_still_works(self) -> None:
        """真实端到端：SoulRaidScript() 用默认值构造仍能工作（main() 入口兼容）。"""
        env = MockEnvironment()
        script = SoulRaidScript(env=env)
        # 默认 script_name 是 "soul_raid"
        assert script.script_name == "soul_raid"
        # 默认 max_battle_count 是 base 类写死的 103
        assert script.max_battle_count == 103
