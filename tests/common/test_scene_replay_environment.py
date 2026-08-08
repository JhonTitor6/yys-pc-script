"""数据驱动场景回放环境测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from tests.common.environment.scene_replay_environment import SceneReplayEnvironment
from tests.common.recorders.action_log import ActionLog


def test_click_region_drives_scene_transition(tmp_path: Path) -> None:
    """点击转换应完全来自 v1 夹具，而不是代码硬编码。"""
    scenes = tmp_path / "scenes"
    scenes.mkdir()
    Image.new("RGB", (100, 80), "red").save(scenes / "home.png")
    Image.new("RGB", (100, 80), "green").save(scenes / "barrier.png")
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scenario_id": "test",
                "client_size": [100, 80],
                "initial_scene": "home",
                "scenes": {
                    "home": "scenes/home.png",
                    "barrier": "scenes/barrier.png",
                },
                "transitions": [
                    {
                        "from_scene": "home",
                        "to_scene": "barrier",
                        "action": "left_click",
                        "region": [10, 10, 20, 20],
                    }
                ],
                "expected_actions": [],
            }
        ),
        encoding="utf-8",
    )
    log = ActionLog()
    env = SceneReplayEnvironment(
        scene_dir=str(scenes),
        transitions_config=str(fixture),
        initial_scene="home",
        action_log=log,
    )

    env.left_click(15, 15)

    assert env.get_current_scene() == "barrier"
    assert env.get_window_client_rect() == (0, 0, 100, 80)
    log.assert_click_at(15, 15, tolerance=0)


def test_button_transition_remains_compatible(tmp_path: Path) -> None:
    """按钮图片转换接口应兼容旧调用者。"""
    scene_dir = tmp_path / "scenes"
    scene_dir.mkdir()
    Image.new("RGB", (100, 80), "red").save(scene_dir / "home.png")
    Image.new("RGB", (100, 80), "green").save(scene_dir / "barrier.png")
    config = tmp_path / "legacy.json"
    config.write_text(
        json.dumps({"home": {"path/to/button.bmp": "barrier"}}),
        encoding="utf-8",
    )
    env = SceneReplayEnvironment(
        scene_dir=str(scene_dir),
        transitions_config=str(config),
        initial_scene="home",
    )

    result = env.transition_to_next_scene("another/path/button.bmp")

    assert result == "barrier"
    assert env.get_current_scene() == "barrier"


def test_home_to_realm_raid_chain_is_data_driven(tmp_path: Path) -> None:
    """庭院到探索再到结界突破应能完全由夹具转换描述驱动。"""
    scenes = tmp_path / "scenes"
    scenes.mkdir()
    for name, color in [
        ("home", "red"),
        ("exploration", "green"),
        ("barrier_breakthrough", "blue"),
    ]:
        Image.new("RGB", (100, 80), color).save(scenes / f"{name}.png")
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scenario_id": "realm_raid_entry",
                "client_size": [100, 80],
                "initial_scene": "home",
                "scenes": {
                    name: f"scenes/{name}.png"
                    for name in ["home", "exploration", "barrier_breakthrough"]
                },
                "transitions": [
                    {
                        "from_scene": "home",
                        "to_scene": "exploration",
                        "action": "left_click",
                        "region": [10, 10, 20, 20],
                    },
                    {
                        "from_scene": "exploration",
                        "to_scene": "barrier_breakthrough",
                        "action": "left_click",
                        "region": [30, 30, 40, 40],
                    },
                ],
                "expected_actions": [],
            }
        ),
        encoding="utf-8",
    )
    env = SceneReplayEnvironment(
        scene_dir=str(scenes),
        transitions_config=str(fixture),
        initial_scene="home",
        action_log=ActionLog(),
    )

    env.left_click(15, 15)
    env.left_click(35, 35)

    assert env.get_current_scene() == "barrier_breakthrough"
    assert len(env.action_log) == 2


def test_drag_region_drives_scene_transition(tmp_path: Path) -> None:
    """拖拽转换应由夹具中的起止区域驱动，并只记录一个逻辑动作。"""
    scenes = tmp_path / "scenes"
    scenes.mkdir()
    Image.new("RGB", (100, 80), "red").save(scenes / "home.png")
    Image.new("RGB", (100, 80), "green").save(scenes / "daily.png")
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scenario_id": "drag-entry",
                "client_size": [100, 80],
                "initial_scene": "home",
                "scenes": {
                    "home": "scenes/home.png",
                    "daily": "scenes/daily.png",
                },
                "transitions": [
                    {
                        "from_scene": "home",
                        "to_scene": "daily",
                        "action": "drag",
                        "region": [10, 10, 20, 20],
                        "end_region": [70, 50, 80, 60],
                    }
                ],
                "expected_actions": [],
            }
        ),
        encoding="utf-8",
    )
    log = ActionLog()
    env = SceneReplayEnvironment(
        scene_dir=str(scenes),
        transitions_config=str(fixture),
        initial_scene="home",
        action_log=log,
    )

    env.drag(15, 15, 75, 55)

    assert env.get_current_scene() == "daily"
    assert len(log) == 1
    assert log.records[0].extra == {"x2": 75, "y2": 55}


def test_v1_fixture_rejects_scene_path_outside_fixture(tmp_path: Path) -> None:
    """v1 场景图片不得通过上级目录读取夹具外文件。"""
    Image.new("RGB", (100, 80), "red").save(tmp_path / "outside.png")
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    fixture = fixture_dir / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scenario_id": "unsafe",
                "client_size": [100, 80],
                "initial_scene": "home",
                "scenes": {"home": "../outside.png"},
                "transitions": [],
                "expected_actions": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="夹具目录内"):
        SceneReplayEnvironment(
            scene_dir=str(fixture_dir / "scenes"),
            transitions_config=str(fixture),
            initial_scene="home",
        )


def test_missing_scene_uses_fixture_client_size(tmp_path: Path) -> None:
    """缺失场景的空白画面应遵循夹具客户区尺寸。"""
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "scenario_id": "blank",
                "client_size": [37, 29],
                "initial_scene": "missing",
                "scenes": {},
                "transitions": [],
                "expected_actions": [],
            }
        ),
        encoding="utf-8",
    )

    env = SceneReplayEnvironment(
        scene_dir=str(tmp_path / "scenes"),
        transitions_config=str(fixture),
        initial_scene="missing",
    )

    assert env.capture_screen().size == (37, 29)


def test_legacy_absolute_scene_path_is_allowed_inside_scene_dir(tmp_path: Path) -> None:
    """旧夹具的绝对图片路径仅在显式场景目录内保持兼容。"""
    scene_dir = tmp_path / "scenes"
    scene_dir.mkdir()
    scene_path = scene_dir / "actual.png"
    Image.new("RGB", (41, 31), "blue").save(scene_path)
    fixture = tmp_path / "legacy.json"
    fixture.write_text(
        json.dumps(
            {
                "scenes": {"alias": [str(scene_path)]},
                "transitions": [],
            }
        ),
        encoding="utf-8",
    )

    env = SceneReplayEnvironment(
        scene_dir=str(scene_dir),
        transitions_config=str(fixture),
        initial_scene="alias",
    )

    assert env.capture_screen().size == (41, 31)
