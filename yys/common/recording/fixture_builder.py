"""从伴随录制生成可审查的场景回放夹具。"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from .contracts import load_events, load_metadata

REPLAY_FIXTURE_SCHEMA_VERSION = 1
_SCENE_NAME_PATTERN = re.compile(r"[\w-]+", re.UNICODE)
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True)
class ReplayTransition:
    """一个由动作或按钮触发的场景转换。"""

    from_scene: str
    to_scene: str
    action: str = "left_click"
    region: Optional[tuple[int, int, int, int]] = None
    end_region: Optional[tuple[int, int, int, int]] = None
    button: Optional[str] = None

    def validate(self, client_size: tuple[int, int]) -> None:
        """校验转换字段和点击区域。"""
        if not self.from_scene or not self.to_scene:
            raise ValueError("场景转换必须包含 from_scene 和 to_scene")
        if self.region is None and self.button is None:
            raise ValueError("场景转换必须至少包含 region 或 button")
        if self.action == "drag" and self.region is None:
            raise ValueError("拖拽转换必须包含起点 region")
        if self.end_region is not None and self.action != "drag":
            raise ValueError("end_region 只能用于拖拽转换")
        if self.region is not None:
            _validate_region(self.region, client_size, "场景转换区域")
        if self.end_region is not None:
            _validate_region(self.end_region, client_size, "场景转换结束区域")

    def matches_click(self, scene: str, x: int, y: int, action: str) -> bool:
        """判断客户区动作是否命中该转换。"""
        return self.matches_action(scene, action, x, y)

    def matches_action(
        self,
        scene: str,
        action: str,
        x: int,
        y: int,
        end_x: Optional[int] = None,
        end_y: Optional[int] = None,
    ) -> bool:
        """判断点击或拖拽动作是否命中该转换。"""
        if self.from_scene != scene or self.action != action or self.region is None:
            return False
        if not _point_in_region(x, y, self.region):
            return False
        if action != "drag" or self.end_region is None:
            return True
        if end_x is None or end_y is None:
            return False
        return _point_in_region(end_x, end_y, self.end_region)


@dataclass(frozen=True)
class ExpectedAction:
    """回放测试期望出现的一个动作。"""

    action: str
    region: Optional[tuple[int, int, int, int]] = None
    key: Optional[str] = None


@dataclass
class ReplayFixture:
    """数据驱动场景回放的统一配置。"""

    schema_version: int
    scenario_id: str
    client_size: tuple[int, int]
    initial_scene: str
    scenes: dict[str, str] = field(default_factory=dict)
    transitions: list[ReplayTransition] = field(default_factory=list)
    expected_actions: list[ExpectedAction] = field(default_factory=list)

    def validate(self) -> None:
        """校验版本、尺寸和所有转换。"""
        if self.schema_version != REPLAY_FIXTURE_SCHEMA_VERSION:
            raise ValueError(f"不支持的回放夹具版本: {self.schema_version}")
        width, height = self.client_size
        if width <= 0 or height <= 0:
            raise ValueError("回放客户区尺寸必须为正数")
        if not self.initial_scene:
            raise ValueError("回放夹具缺少 initial_scene")
        for scene_name, scene_path in self.scenes.items():
            _validate_scene_asset(scene_name, scene_path)
        for transition in self.transitions:
            transition.validate(self.client_size)

    def to_dict(self) -> dict[str, Any]:
        """转换为稳定 JSON 字典。"""
        self.validate()
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "client_size": list(self.client_size),
            "initial_scene": self.initial_scene,
            "scenes": dict(self.scenes),
            "transitions": [
                {
                    key: list(value)
                    if key in {"region", "end_region"} and value is not None
                    else value
                    for key, value in asdict(item).items()
                    if value is not None
                }
                for item in self.transitions
            ],
            "expected_actions": [
                {
                    key: list(value) if key == "region" and value is not None else value
                    for key, value in asdict(item).items()
                    if value is not None
                }
                for item in self.expected_actions
            ],
        }


def load_replay_fixture(
    path: Path,
    *,
    fallback_initial_scene: str,
    fallback_client_size: tuple[int, int] = (1154, 680),
) -> ReplayFixture:
    """读取 v1、现有列表格式或旧版按钮映射格式。"""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("场景转换配置顶层必须是对象")
    if payload.get("schema_version") is not None:
        return _decode_v1_fixture(payload)
    if isinstance(payload.get("transitions"), list):
        return _decode_transition_list(
            payload,
            fallback_initial_scene,
            fallback_client_size,
        )
    return _decode_legacy_mapping(
        payload,
        fallback_initial_scene,
        fallback_client_size,
    )


def save_replay_fixture(path: Path, fixture: ReplayFixture) -> None:
    """保存 v1 回放夹具。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(fixture.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_candidates(recording_dir: Path, output_path: Path) -> Path:
    """按录制事件生成待人工确认的关键帧候选清单。"""
    metadata = load_metadata(recording_dir / "metadata.json")
    events = load_events(
        recording_dir / "events.jsonl",
        (metadata.client_width, metadata.client_height),
    )
    candidates: list[dict[str, Any]] = []
    for event in events:
        before = recording_dir / "frames" / f"{event.seq:06d}-before.png"
        after = recording_dir / "frames" / f"{event.seq:06d}-after.png"
        region = None
        if event.client_x is not None and event.client_y is not None:
            region = _bounded_region(
                event.client_x,
                event.client_y,
                metadata.client_width,
                metadata.client_height,
            )
        candidate = {
            "event_seq": event.seq,
            "elapsed_ms": event.elapsed_ms,
            "action": event.action,
            "key": event.key,
            "before_frame": str(before),
            "after_frame": str(after),
            "suggested_region": region,
            "suggested_from_scene": f"scene_{event.seq:03d}_before",
            "suggested_to_scene": f"scene_{event.seq:03d}_after",
        }
        if event.action == "drag" and event.end_client_x is not None and event.end_client_y is not None:
            candidate["suggested_end_region"] = _bounded_region(
                event.end_client_x,
                event.end_client_y,
                metadata.client_width,
                metadata.client_height,
            )
        candidates.append(candidate)
    payload = {
        "schema_version": REPLAY_FIXTURE_SCHEMA_VERSION,
        "recording_id": metadata.recording_id,
        "scenario": metadata.scenario,
        "client_size": [metadata.client_width, metadata.client_height],
        "candidates": candidates,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def build_confirmed_fixture(
    recording_dir: Path,
    confirmation_path: Path,
    output_dir: Path,
) -> Path:
    """依据人工确认清单复制最小场景图片并生成 v1 夹具。"""
    metadata = load_metadata(recording_dir / "metadata.json")
    confirmation = json.loads(confirmation_path.read_text(encoding="utf-8"))
    if not isinstance(confirmation, dict):
        raise ValueError("确认清单顶层必须是对象")
    selections = confirmation.get("transitions")
    if not isinstance(selections, list) or not selections:
        raise ValueError("确认清单必须包含非空 transitions")
    initial_scene = _decode_scene_name(confirmation["initial_scene"], "initial_scene")

    scenes_dir = output_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    scenes: dict[str, str] = {}
    scene_selections = confirmation.get("scenes")
    if scene_selections is not None:
        if not isinstance(scene_selections, list) or not scene_selections:
            raise ValueError("确认清单 scenes 必须是非空列表")
        for selection in scene_selections:
            if not isinstance(selection, dict):
                raise ValueError("确认清单 scenes 元素必须是对象")
            scene_name = _decode_scene_name(selection["name"], "scenes.name")
            source = _resolve_confirmed_frame(recording_dir, selection)
            _copy_scene_asset(source, scenes_dir, scene_name, scenes)

    transitions: list[ReplayTransition] = []
    for selection in selections:
        if not isinstance(selection, dict):
            raise ValueError("确认清单 transitions 元素必须是对象")
        from_scene = _decode_scene_name(selection["from_scene"], "from_scene")
        to_scene = _decode_scene_name(selection["to_scene"], "to_scene")
        if scene_selections is None:
            event_seq = int(selection["event_seq"])
            before_source = (
                recording_dir / "frames" / f"{event_seq:06d}-before.png"
            )
            after_source = recording_dir / "frames" / f"{event_seq:06d}-after.png"
            _copy_scene_asset(before_source, scenes_dir, from_scene, scenes)
            _copy_scene_asset(after_source, scenes_dir, to_scene, scenes)
        elif from_scene not in scenes or to_scene not in scenes:
            raise ValueError("transitions 引用的场景必须先在 scenes 中确认")
        region = _decode_region(selection.get("region"))
        end_region = _decode_region(selection.get("end_region"))
        transitions.append(
            ReplayTransition(
                from_scene=from_scene,
                to_scene=to_scene,
                action=str(selection.get("action", "left_click")),
                region=region,
                end_region=end_region,
                button=(
                    str(selection["button"])
                    if selection.get("button") is not None
                    else None
                ),
            )
        )
    fixture = ReplayFixture(
        schema_version=REPLAY_FIXTURE_SCHEMA_VERSION,
        scenario_id=str(confirmation.get("scenario_id", metadata.scenario)),
        client_size=(metadata.client_width, metadata.client_height),
        initial_scene=initial_scene,
        scenes=scenes,
        transitions=transitions,
        expected_actions=[
            _decode_expected_action(item)
            for item in _decode_confirmation_list(
                confirmation.get("expected_actions", []),
                "expected_actions",
            )
        ],
    )
    fixture_path = output_dir / "fixture.json"
    save_replay_fixture(fixture_path, fixture)
    return fixture_path


def _resolve_confirmed_frame(
    recording_dir: Path,
    selection: Mapping[str, Any],
) -> Path:
    """把确认场景解析为录制目录内的安全图片路径。"""
    source_path = selection.get("source_path")
    if source_path is not None:
        if not isinstance(source_path, str) or not source_path:
            raise ValueError("scenes.source_path 必须是非空字符串")
        source = (recording_dir / source_path).resolve()
        if not source.is_relative_to(recording_dir.resolve()):
            raise ValueError("scenes.source_path 必须位于录制目录内")
        return source

    event_seq = int(selection["event_seq"])
    frame_phase = str(selection.get("frame_phase", "before"))
    if frame_phase not in {"before", "after"}:
        raise ValueError("scenes.frame_phase 只能是 before 或 after")
    return recording_dir / "frames" / f"{event_seq:06d}-{frame_phase}.png"


def _copy_scene_asset(
    source: Path,
    scenes_dir: Path,
    scene_name: str,
    scenes: dict[str, str],
) -> None:
    """复制一张已经确认的场景图片到最小夹具目录。"""
    if not source.is_file():
        raise FileNotFoundError(f"确认的场景关键帧不存在: {source}")
    target = scenes_dir / f"{scene_name}.png"
    shutil.copy2(source, target)
    scenes[scene_name] = (Path("scenes") / target.name).as_posix()


def _decode_confirmation_list(payload: object, field_name: str) -> list[object]:
    """解码确认清单中的可选对象列表。"""
    if not isinstance(payload, list):
        raise ValueError(f"确认清单 {field_name} 必须是列表")
    return payload


def _decode_v1_fixture(payload: Mapping[str, Any]) -> ReplayFixture:
    scenes_raw = payload.get("scenes", {})
    transitions_raw = payload.get("transitions", [])
    expected_raw = payload.get("expected_actions", [])
    if not isinstance(scenes_raw, dict) or not isinstance(transitions_raw, list):
        raise ValueError("v1 回放夹具 scenes/transitions 类型错误")
    fixture = ReplayFixture(
        schema_version=int(payload["schema_version"]),
        scenario_id=str(payload["scenario_id"]),
        client_size=_decode_size(payload["client_size"]),
        initial_scene=str(payload["initial_scene"]),
        scenes=_decode_scene_assets(scenes_raw),
        transitions=[_decode_transition(item) for item in transitions_raw],
        expected_actions=[_decode_expected_action(item) for item in expected_raw],
    )
    fixture.validate()
    return fixture


def _decode_transition_list(
    payload: Mapping[str, Any],
    initial_scene: str,
    client_size: tuple[int, int],
) -> ReplayFixture:
    scenes_raw = payload.get("scenes", {})
    scenes: dict[str, str] = {}
    if isinstance(scenes_raw, dict):
        for name, value in scenes_raw.items():
            if isinstance(value, list) and value:
                scenes[str(name)] = str(value[0])
            elif isinstance(value, str):
                scenes[str(name)] = value
    transitions = [
        ReplayTransition(
            from_scene=str(item["from"]),
            to_scene=str(item["to"]),
            button=str(item["button"]),
        )
        for item in payload["transitions"]
        if isinstance(item, dict)
    ]
    return ReplayFixture(
        schema_version=REPLAY_FIXTURE_SCHEMA_VERSION,
        scenario_id="legacy-transition-list",
        client_size=client_size,
        initial_scene=initial_scene,
        scenes=scenes,
        transitions=transitions,
    )


def _decode_legacy_mapping(
    payload: Mapping[str, Any],
    initial_scene: str,
    client_size: tuple[int, int],
) -> ReplayFixture:
    transitions: list[ReplayTransition] = []
    for from_scene, mapping in payload.items():
        if str(from_scene).startswith("_") or not isinstance(mapping, dict):
            continue
        for button, to_scene in mapping.items():
            transitions.append(
                ReplayTransition(
                    from_scene=str(from_scene),
                    to_scene=str(to_scene),
                    button=str(button),
                )
            )
    return ReplayFixture(
        schema_version=REPLAY_FIXTURE_SCHEMA_VERSION,
        scenario_id="legacy-mapping",
        client_size=client_size,
        initial_scene=initial_scene,
        transitions=transitions,
    )


def _decode_transition(payload: object) -> ReplayTransition:
    if not isinstance(payload, dict):
        raise ValueError("transitions 元素必须是对象")
    region = _decode_region(payload.get("region"))
    end_region = _decode_region(payload.get("end_region"))
    return ReplayTransition(
        from_scene=str(payload["from_scene"]),
        to_scene=str(payload["to_scene"]),
        action=str(payload.get("action", "left_click")),
        region=region,
        end_region=end_region,
        button=str(payload["button"]) if payload.get("button") else None,
    )


def _decode_expected_action(payload: object) -> ExpectedAction:
    if not isinstance(payload, dict):
        raise ValueError("expected_actions 元素必须是对象")
    region = _decode_region(payload.get("region"))
    return ExpectedAction(
        action=str(payload["action"]),
        region=region,
        key=str(payload["key"]) if payload.get("key") else None,
    )


def _decode_region(payload: object) -> Optional[tuple[int, int, int, int]]:
    if payload is None:
        return None
    if not isinstance(payload, (list, tuple)) or len(payload) != 4:
        raise ValueError("region 必须是四个整数")
    values = [int(value) for value in payload]
    return values[0], values[1], values[2], values[3]


def _decode_size(payload: object) -> tuple[int, int]:
    if not isinstance(payload, list) or len(payload) != 2:
        raise ValueError("client_size 必须是两个整数")
    return int(payload[0]), int(payload[1])


def _decode_scene_name(payload: object, field_name: str) -> str:
    """解码可安全用作场景图片文件名的场景名。"""
    if not isinstance(payload, str) or not payload:
        raise ValueError(f"{field_name} 必须是非空字符串")
    if _SCENE_NAME_PATTERN.fullmatch(payload) is None:
        raise ValueError(f"{field_name} 只能包含文字、数字、下划线或连字符")
    if payload.upper() in _WINDOWS_RESERVED_NAMES:
        raise ValueError(f"{field_name} 不能使用 Windows 保留名称")
    return payload


def _validate_scene_asset(scene_name: object, scene_path: object) -> None:
    """确保 v1 场景图片使用夹具内的相对路径。"""
    if not isinstance(scene_name, str) or not scene_name:
        raise ValueError("scenes 的场景名必须是非空字符串")
    if not isinstance(scene_path, str) or not scene_path:
        raise ValueError(f"场景 {scene_name} 的图片路径必须是非空字符串")
    path = Path(scene_path)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"场景 {scene_name} 的图片路径必须位于夹具目录内")


def _decode_scene_assets(payload: Mapping[object, object]) -> dict[str, str]:
    """严格解码 v1 场景图片映射，不隐式转换字段类型。"""
    scenes: dict[str, str] = {}
    for scene_name, scene_path in payload.items():
        _validate_scene_asset(scene_name, scene_path)
        if not isinstance(scene_name, str) or not isinstance(scene_path, str):
            raise AssertionError("场景图片映射校验后类型不一致")
        scenes[scene_name] = scene_path
    return scenes


def _bounded_region(
    x: int,
    y: int,
    width: int,
    height: int,
    radius: int = 12,
) -> list[int]:
    return [
        max(0, x - radius),
        max(0, y - radius),
        min(width - 1, x + radius),
        min(height - 1, y + radius),
    ]


def _validate_region(
    region: tuple[int, int, int, int],
    client_size: tuple[int, int],
    label: str,
) -> None:
    """校验一个位于客户区内的矩形区域。"""
    x1, y1, x2, y2 = region
    width, height = client_size
    if not (0 <= x1 <= x2 < width and 0 <= y1 <= y2 < height):
        raise ValueError(f"{label}超出客户区: {region}")


def _point_in_region(x: int, y: int, region: tuple[int, int, int, int]) -> bool:
    """判断一个客户区坐标是否位于矩形区域内。"""
    x1, y1, x2, y2 = region
    return x1 <= x <= x2 and y1 <= y <= y2
