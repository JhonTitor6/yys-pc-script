# tests/common/recorders/record_replay.py
"""
录制与回放工具

功能：
1. 录制模式：保存游戏画面和操作到 test_data/scenarios
2. 回放模式：从 test_data/scenarios 加载场景并重放操作
"""
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional
from PIL import Image


@dataclass
class RecordedAction:
    """录制动作数据类"""
    action_type: str
    x: int
    y: int
    timestamp: float
    extra: dict

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'RecordedAction':
        """从字典创建"""
        return cls(**data)


class ScenarioRecorder:
    """场景录制器"""

    def __init__(self, output_dir: str = "yys/soul_raid/images/test"):
        """
        初始化录制器

        :param output_dir: 输出目录
        """
        self._output_dir = Path(output_dir)
        self._actions: List[RecordedAction] = []
        self._start_time: Optional[float] = None

    def start_recording(self) -> None:
        """开始录制"""
        self._start_time = time.time()
        self._actions.clear()

    def record_action(self, action_type: str, x: int, y: int, **extra) -> None:
        """
        录制一个动作

        :param action_type: 动作类型
        :param x: x坐标
        :param y: y坐标
        :param extra: 额外参数
        """
        if self._start_time is None:
            raise RuntimeError("请先调用 start_recording() 开始录制")
        self._actions.append(RecordedAction(
            action_type=action_type,
            x=x,
            y=y,
            timestamp=time.time() - self._start_time,
            extra=extra
        ))

    def save_scenario(self, scenario_name: str, screenshot: Image.Image) -> Path:
        """
        保存场景截图和操作记录

        :param scenario_name: 场景名称（如 "soul_raid/battle_01"）
        :param screenshot: 截图
        :return: 场景目录路径
        """
        scenario_dir = self._output_dir / scenario_name
        scenario_dir.mkdir(parents=True, exist_ok=True)

        # 保存截图
        screenshot_path = scenario_dir / "screenshot.png"
        screenshot.save(screenshot_path)

        # 保存操作记录
        actions_path = scenario_dir / "actions.json"
        with open(actions_path, "w", encoding="utf-8") as f:
            json.dump([a.to_dict() for a in self._actions], f, ensure_ascii=False, indent=2)

        return scenario_dir

    @staticmethod
    def load_scenario(scenario_name: str, base_dir: str = "yys/soul_raid/images/test") -> tuple[Image.Image, List[RecordedAction]]:
        """
        加载场景截图和操作记录

        :param scenario_name: 场景名称
        :param base_dir: 基础目录
        :return: (截图, 动作列表) 元组
        """
        scenario_dir = Path(base_dir) / scenario_name

        screenshot = Image.open(scenario_dir / "screenshot.png")

        with open(scenario_dir / "actions.json", "r", encoding="utf-8") as f:
            actions_data = json.load(f)

        actions = [RecordedAction.from_dict(a) for a in actions_data]
        return screenshot, actions

    @staticmethod
    def list_scenarios(base_dir: str = "yys/soul_raid/images/test") -> List[str]:
        """
        列出所有可用场景

        :param base_dir: 基础目录
        :return: 场景名称列表
        """
        base_path = Path(base_dir)
        if not base_path.exists():
            return []
        scenarios = []
        for action_json in base_path.rglob("actions.json"):
            scenario = action_json.parent.relative_to(base_path)
            scenarios.append(str(scenario))
        return sorted(scenarios)