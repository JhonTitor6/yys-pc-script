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
            },
            {
                "key": "loop_interval",
                "label": "循环间隔",
                "field_type": "number",
                "default": 5,
                "min_value": 0,
                "max_value": 60,
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
            },
            {
                "key": "commander_count",
                "label": "将领次数",
                "field_type": "number",
                "default": 4,
                "min_value": 0,
                "max_value": 99,
            },
            {
                "key": "elite_count",
                "label": "精英次数",
                "field_type": "number",
                "default": 6,
                "min_value": 0,
                "max_value": 99,
            },
        ],
    },
]
