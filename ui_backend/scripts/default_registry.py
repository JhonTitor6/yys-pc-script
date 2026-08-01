from __future__ import annotations

from typing import Any

DEFAULT_SCRIPT_ENTRIES: list[dict[str, Any]] = [
    {
        "script_id": "soul_raid",
        "display_name": "御魂",
        "module_path": "yys.soul_raid",
        "class_name": "SoulRaidScript",
        "category": "stable",
        "description": "自动执行御魂副本挑战。",
        "config_schema": [
            {
                "key": "max_battle_count",
                "label": "最大战斗次数",
                "field_type": "number",
                "default": 103,
                "min_value": 1,
                "max_value": 999,
                "hot_reloadable": True,
            },
            {
                "key": "loop_interval",
                "label": "循环间隔",
                "field_type": "number",
                "default": 5,
                "min_value": 0,
                "max_value": 60,
                "hot_reloadable": False,
            },
        ],
    },
    {
        "script_id": "realm_raid",
        "display_name": "结界突破",
        "module_path": "yys.realm_raid",
        "class_name": "RealmRaidScript",
        "category": "stable",
        "description": "自动执行结界突破挑战。",
        "config_schema": [
            {
                "key": "max_battle_count",
                "label": "最大战斗次数",
                "field_type": "number",
                "default": 9,
                "min_value": 1,
                "max_value": 999,
                "hot_reloadable": True,
            }
        ],
    },
    {
        "script_id": "exploration_28",
        "display_name": "探28",
        "module_path": "yys.exploration",
        "class_name": "ExplorationScript",
        "category": "stable",
        "description": "自动执行第二十八章探索。",
        "config_schema": [
            {
                "key": "max_battle_count",
                "label": "最大战斗次数",
                "field_type": "number",
                "default": 200,
                "min_value": 1,
                "max_value": 999,
                "hot_reloadable": True,
            }
        ],
    },
    {
        "script_id": "yuling",
        "display_name": "御灵",
        "module_path": "yys.yuling",
        "class_name": "AutoYuling",
        "category": "stable",
        "description": "自动执行御灵副本挑战。",
        "config_schema": [
            {
                "key": "max_battle_count",
                "label": "最大战斗次数",
                "field_type": "number",
                "default": 50,
                "min_value": 1,
                "max_value": 999,
                "hot_reloadable": True,
            }
        ],
    },
    {
        "script_id": "abyss_shadows",
        "display_name": "狭间暗域",
        "module_path": "yys.abyss_shadows.abyss_shadows_script",
        "class_name": "Main",
        "category": "experimental",
        "description": "自动执行狭间暗域任务。",
        "config_schema": [
            {
                "key": "boss_count",
                "label": "首领次数",
                "field_type": "number",
                "default": 2,
                "min_value": 0,
                "max_value": 99,
                "hot_reloadable": True,
            },
            {
                "key": "boss_damage_limit",
                "label": "首领伤害限制",
                "field_type": "number",
                "default": 1,
                "min_value": 0,
                "max_value": 999999999,
                "hot_reloadable": False,
            },
            {
                "key": "commander_count",
                "label": "将领次数",
                "field_type": "number",
                "default": 4,
                "min_value": 0,
                "max_value": 99,
                "hot_reloadable": True,
            },
            {
                "key": "elite_count",
                "label": "精英次数",
                "field_type": "number",
                "default": 6,
                "min_value": 0,
                "max_value": 99,
                "hot_reloadable": True,
            },
        ],
    },
    # ==================== auto-registry Step 5 新增 4 个 entry ====================
    # 4 个事件驱动脚本在 Step 5 迁移到 SCRIPT_META（详见 yys/<script>/<script>_script.py）。
    # 注：以下 4 个脚本原不在 default_registry.py，Step 5 追加以暴露给 /api/scripts。
    # 现有 5 个 entry 行为不变；schema 字段在反射时优先来自 SCRIPT_META。
    {
        "script_id": "loop_challenge",
        "display_name": "通用挑战",
        "module_path": "yys.common_challenge.loop_challenge",
        "class_name": "LoopChallenge",
        "category": "stable",
        "description": "循环点击挑战按钮（支持每 200~300 次战斗后自动休息 60~180 秒）。",
        "config_schema": [
            {"key": "max_battle_count", "label": "最大战斗次数", "field_type": "number",
             "default": 1782, "min_value": 1, "max_value": 9999, "hot_reloadable": True}
        ],
    },
    {
        "script_id": "douji",
        "display_name": "斗技",
        "module_path": "yys.douji.douji_script",
        "class_name": "DouJi",
        "category": "stable",
        "description": "斗技挂机：自动接受邀请、切到自动战斗、累计战斗次数。",
        "config_schema": [
            {"key": "max_battle_count", "label": "最大战斗次数", "field_type": "number",
             "default": 30, "min_value": 1, "max_value": 999, "hot_reloadable": True}
        ],
    },
    {
        "script_id": "fujiwara",
        "display_name": "藤原道长-传承试炼",
        "module_path": "yys.fujiwara.script_main",
        "class_name": "Main",
        "category": "stable",
        "description": "藤原道长传承试炼：循环点击挑战按钮。",
        "config_schema": [
            {"key": "max_battle_count", "label": "最大战斗次数", "field_type": "number",
             "default": 506, "min_value": 1, "max_value": 9999, "hot_reloadable": True}
        ],
    },
    {
        "script_id": "omoikane",
        "display_name": "思金神",
        "module_path": "yys.omoikane.omoikane_script",
        "class_name": "OmoikaneScript",
        "category": "stable",
        "description": "思金神挂机：循环点击挑战按钮。",
        "config_schema": [
            {"key": "max_battle_count", "label": "最大战斗次数", "field_type": "number",
             "default": 150, "min_value": 1, "max_value": 999, "hot_reloadable": True}
        ],
    },
]
