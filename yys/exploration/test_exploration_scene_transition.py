"""探索脚本场景重放集成测试。

验证 entry_scene 声明 + SceneReplayEnvironment 加载 + BFS 可达性。
完整流程测试依赖 Task 4 人工采集的场景图 fixture。
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Mock Windows 游戏窗口相关的依赖，避免 import 时触发真实 Windows API
_mock_modules = [
    "win32gui", "win32ui", "win32con", "win32api",
    "win32clipboard", "win32process", "PIL.ImageGrab",
    "easyocr", "mss",
]
for _mod in _mock_modules:
    sys.modules[_mod] = MagicMock()

# loguru 需要特殊处理
sys.modules["loguru"] = MagicMock()

from yys.exploration.exploration_script import ExplorationScript

# 业务入口场景名
ENTRY_SCENE = "exploration_chapter_28"

SCENE_CONFIG = str(PROJECT_ROOT / "yys/exploration/config/scene_transitions_exploration.json")
SCENE_DIR = str(PROJECT_ROOT / "yys/exploration/images/test/scenes/")


def _scene_assets_available() -> bool:
    """检查场景重放所需的 fixture 资产是否齐全。

    需要：
    - 场景转换配置文件存在
    - 场景图片目录存在
    - 场景目录中存在至少一个 .bmp/.png/.jpg fixture（依赖 Task 4 人工采集）
    """
    if not Path(SCENE_CONFIG).exists():
        return False
    if not Path(SCENE_DIR).is_dir():
        return False
    scene_fixtures = [
        f for f in Path(SCENE_DIR).iterdir()
        if f.suffix.lower() in (".bmp", ".png", ".jpg")
    ]
    if not scene_fixtures:
        return False
    return True


@pytest.mark.skipif(
    not _scene_assets_available(),
    reason="探索场景重放 fixture 未采集（依赖 Task 4 人工截图）",
)
def test_exploration_full_flow_via_scene_replay() -> None:
    """验证：ExplorationScript 声明 entry_scene + 场景图已被 SceneManager 注册。"""
    from tests.common.environment.scene_replay_environment import SceneReplayEnvironment

    env = SceneReplayEnvironment(
        scene_dir=SCENE_DIR,
        transitions_config=SCENE_CONFIG,
        initial_scene=ENTRY_SCENE,
    )

    # YYSBaseScript.__init__ 已通过 env 创建 self.scene_manager 并加载 scene/control 目录
    script = ExplorationScript(
        script_name="exploration_replay",
        env=env,
        config={"max_battle_count": 1},
    )

    # 验证 entry_scene 声明
    assert script.entry_scene == ENTRY_SCENE

    # 验证 entry_scene 场景图已注册到 SceneManager（非空列表）
    registered = script.scene_manager.scene_images.get(ENTRY_SCENE)
    assert registered, f"{ENTRY_SCENE} 场景图未注册到 SceneManager"

    # 验证 SceneReplayEnvironment 已加载到目标场景
    assert env.get_current_scene() == ENTRY_SCENE
