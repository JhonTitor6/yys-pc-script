"""回放夹具合约与生成器测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from yys.common.recording.contracts import (
    RECORDING_SCHEMA_VERSION,
    RecordingEvent,
    RecordingMetadata,
    save_metadata,
    write_events,
)
from yys.common.recording.fixture_builder import (
    REPLAY_FIXTURE_SCHEMA_VERSION,
    ReplayTransition,
    build_candidates,
    build_confirmed_fixture,
    load_replay_fixture,
)


def _create_recording(recording_dir: Path) -> None:
    """创建一份最小合法原始录制。"""
    frames_dir = recording_dir / "frames"
    frames_dir.mkdir(parents=True)
    Image.new("RGB", (100, 80), "red").save(frames_dir / "000001-before.png")
    Image.new("RGB", (100, 80), "green").save(frames_dir / "000001-after.png")
    Image.new("RGB", (100, 80), "blue").save(frames_dir / "000002-before.png")
    save_metadata(
        recording_dir / "metadata.json",
        RecordingMetadata(
            schema_version=RECORDING_SCHEMA_VERSION,
            recording_id="recording-1",
            scenario="realm_raid",
            started_at="2026-07-25T00:00:00+00:00",
            ended_at="2026-07-25T00:00:01+00:00",
            duration_ms=1000,
            window_title="阴阳师",
            client_width=100,
            client_height=80,
            fps=8.0,
            codec="mp4v",
            event_count=1,
            dropped_frame_count=0,
            status="completed",
            stop_reason="user_stop",
        ),
    )
    write_events(
        recording_dir / "events.jsonl",
        [
            RecordingEvent(
                schema_version=RECORDING_SCHEMA_VERSION,
                seq=1,
                elapsed_ms=500,
                kind="mouse",
                action="left_click",
                client_x=20,
                client_y=30,
                normalized_x=20 / 99,
                normalized_y=30 / 79,
                button="left",
            )
        ],
    )


def test_build_candidates_only_writes_review_manifest(tmp_path: Path) -> None:
    """候选阶段只写清单，不复制场景资产。"""
    recording_dir = tmp_path / "recording"
    _create_recording(recording_dir)
    output = tmp_path / "review" / "candidates.json"

    build_candidates(recording_dir, output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["recording_id"] == "recording-1"
    assert payload["candidates"][0]["suggested_region"] == [8, 18, 32, 42]
    assert not (tmp_path / "review" / "scenes").exists()


def test_build_confirmed_fixture_copies_only_selected_frames(tmp_path: Path) -> None:
    """只有确认清单中的场景才会进入夹具目录。"""
    recording_dir = tmp_path / "recording"
    _create_recording(recording_dir)
    confirmation = tmp_path / "confirmation.json"
    confirmation.write_text(
        json.dumps(
            {
                "scenario_id": "realm-raid-main",
                "initial_scene": "home",
                "transitions": [
                    {
                        "event_seq": 1,
                        "from_scene": "home",
                        "to_scene": "barrier_breakthrough",
                        "action": "left_click",
                        "region": [8, 18, 32, 42],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "fixture"

    fixture_path = build_confirmed_fixture(
        recording_dir,
        confirmation,
        output_dir,
    )
    fixture = load_replay_fixture(
        fixture_path,
        fallback_initial_scene="ignored",
    )

    assert fixture.schema_version == REPLAY_FIXTURE_SCHEMA_VERSION
    assert fixture.initial_scene == "home"
    assert fixture.transitions[0].to_scene == "barrier_breakthrough"
    assert fixture.scenes["home"] == "scenes/home.png"
    assert (output_dir / "scenes" / "home.png").exists()
    assert (output_dir / "scenes" / "barrier_breakthrough.png").exists()


def test_build_confirmed_fixture_rejects_unsafe_scene_name(tmp_path: Path) -> None:
    """人工确认的场景名不得把图片写出夹具目录。"""
    recording_dir = tmp_path / "recording"
    _create_recording(recording_dir)
    confirmation = tmp_path / "confirmation.json"
    confirmation.write_text(
        json.dumps(
            {
                "initial_scene": "home",
                "transitions": [
                    {
                        "event_seq": 1,
                        "from_scene": "../../escape",
                        "to_scene": "barrier",
                        "region": [8, 18, 32, 42],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="from_scene"):
        build_confirmed_fixture(
            recording_dir,
            confirmation,
            tmp_path / "fixture",
        )

    assert not (tmp_path / "escape.png").exists()


def test_build_confirmed_fixture_supports_cross_event_scene_selection(
    tmp_path: Path,
) -> None:
    """场景与动作解耦后应能选择下一事件的前帧作为目标状态。"""
    recording_dir = tmp_path / "recording"
    _create_recording(recording_dir)
    confirmation = tmp_path / "confirmation.json"
    confirmation.write_text(
        json.dumps(
            {
                "scenario_id": "cross-event",
                "initial_scene": "home",
                "scenes": [
                    {
                        "name": "home",
                        "event_seq": 1,
                        "frame_phase": "before",
                    },
                    {
                        "name": "barrier",
                        "event_seq": 2,
                        "frame_phase": "before",
                    },
                ],
                "transitions": [
                    {
                        "from_scene": "home",
                        "to_scene": "barrier",
                        "region": [8, 18, 32, 42],
                    }
                ],
                "expected_actions": [
                    {"action": "left_click", "region": [8, 18, 32, 42]}
                ],
            }
        ),
        encoding="utf-8",
    )

    fixture_path = build_confirmed_fixture(
        recording_dir,
        confirmation,
        tmp_path / "fixture",
    )
    fixture = load_replay_fixture(
        fixture_path,
        fallback_initial_scene="ignored",
    )

    barrier = Image.open(tmp_path / "fixture" / "scenes" / "barrier.png")
    assert barrier.getpixel((0, 0)) == (0, 0, 255)
    assert fixture.expected_actions[0].action == "left_click"


def test_build_confirmed_fixture_rejects_scene_source_outside_recording(
    tmp_path: Path,
) -> None:
    """显式场景来源不得越过原始录制目录。"""
    recording_dir = tmp_path / "recording"
    _create_recording(recording_dir)
    confirmation = tmp_path / "confirmation.json"
    confirmation.write_text(
        json.dumps(
            {
                "initial_scene": "home",
                "scenes": [
                    {"name": "home", "source_path": "../outside.png"},
                    {"name": "barrier", "event_seq": 1},
                ],
                "transitions": [
                    {
                        "from_scene": "home",
                        "to_scene": "barrier",
                        "region": [8, 18, 32, 42],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="录制目录内"):
        build_confirmed_fixture(
            recording_dir,
            confirmation,
            tmp_path / "fixture",
        )


def test_load_legacy_button_mapping(tmp_path: Path) -> None:
    """旧版按钮映射必须继续可读。"""
    config = tmp_path / "legacy.json"
    config.write_text(
        json.dumps({"home": {"to_barrier.bmp": "barrier_breakthrough"}}),
        encoding="utf-8",
    )

    fixture = load_replay_fixture(
        config,
        fallback_initial_scene="home",
    )

    assert fixture.transitions[0].button == "to_barrier.bmp"
    assert fixture.transitions[0].to_scene == "barrier_breakthrough"


def test_replay_transition_matches_drag_start_and_end_regions() -> None:
    """拖拽回放必须同时校验起点和终点区域。"""
    transition = ReplayTransition(
        from_scene="home",
        to_scene="daily",
        action="drag",
        region=(8, 18, 32, 42),
        end_region=(40, 50, 64, 74),
    )

    transition.validate((100, 80))

    assert transition.matches_action("home", "drag", 20, 30, 52, 62)
    assert not transition.matches_action("home", "drag", 20, 30, 80, 62)
    assert not transition.matches_action("home", "left_click", 20, 30)
