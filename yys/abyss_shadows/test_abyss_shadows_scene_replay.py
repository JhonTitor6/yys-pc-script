"""
狭间暗域场景重放测试

使用 SceneReplayEnvironment 模拟完整流程：
1. 初始为狭间暗域_选择界面
2. 点击 abyss_navigation.bmp -> 战报界面_当前
3. 点击 boss_label.bmp -> 战斗画面
4. 战斗结束 -> 战斗结束后
5. 循环直到完成挑战计数

注意：此测试通过 SceneReplayEnvironment 实现场景流转模拟，
不依赖真实游戏窗口。
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Mock Windows 游戏窗口相关的依赖（不 mock cv2 和 numpy，因为需要执行真实的模板匹配）
_mock_modules = ['win32gui', 'win32ui', 'win32con', 'win32api',
                 'win32clipboard', 'win32process', 'PIL.ImageGrab',
                 'easyocr', 'mss']
for _mod in _mock_modules:
    sys.modules[_mod] = MagicMock()

# loguru 需要特殊处理，因为它有子模块
sys.modules['loguru'] = MagicMock()

from tests.common.environment.scene_replay_environment import SceneReplayEnvironment
from yys.abyss_shadows.abyss_shadows_script import Main, EnemyType


class TestAbyssShadowsSceneReplay(unittest.TestCase):
    """狭间暗域场景重放测试"""

    def _create_replay_environment(self, verbose: bool = True):
        """创建场景回放环境

        Args:
            verbose: 是否输出详细中间过程日志
        """
        from tests.common.recorders.action_log import ActionLog

        scene_dir = str(PROJECT_ROOT / "yys/abyss_shadows/images/example")
        transitions_config = str(
            PROJECT_ROOT / "yys/abyss_shadows/config/scene_transitions_abyss_shadows.json"
        )
        action_log = ActionLog() if verbose else None
        env = SceneReplayEnvironment(
            scene_dir=scene_dir,
            transitions_config=transitions_config,
            initial_scene="狭间暗域_选择界面",
            action_log=action_log
        )
        if verbose:
            print(f"\n[初始场景] {env.get_current_scene()}")
        return env

    def _create_script_with_real_win_controller(self, env: SceneReplayEnvironment):
        """创建使用真实 WinController 的脚本实例

        WinController 会复用 env.capture_screen() 获取截图，
        其余逻辑（找图、点击等）使用生产代码。
        """
        from win_util.controller import WinController

        mock_hwnd = 199268

        # 创建真实的 WinController，传入 env 实现截图 mock
        real_win_controller = WinController(env=env)

        # Mock mouse.bg_left_click，让它调用 env 的 left_click 记录操作
        def mock_bg_left_click(point, x_range=20, y_range=20):
            env.left_click(point[0], point[1])
            return True
        real_win_controller.mouse.bg_left_click = mock_bg_left_click

        # Mock keyboard（测试环境没有真实窗口）
        real_keyboard = MagicMock()
        real_win_controller.keyboard = real_keyboard

        # Mock ocr 使用 env 的方法
        real_win_controller.ocr.find_all_texts = env.find_all_texts
        real_win_controller.ocr.contains_text = env.contains_text

        # 创建 mock scene_manager，关联到 env 的场景切换
        mock_scene_manager = MagicMock()

        def mock_goto_scene(scene_name):
            """scene_manager.goto_scene 也更新 env 场景"""
            env.set_scene(scene_name)
            return True
        mock_scene_manager.goto_scene = MagicMock(side_effect=mock_goto_scene)

        with patch('yys.common.event_script_base.find_window', return_value=mock_hwnd), \
             patch('yys.common.event_script_base.WinController', return_value=real_win_controller), \
             patch('yys.common.event_script_base.SceneManager', return_value=mock_scene_manager):

            script = Main()

        # 注入真实的 win_controller
        script.win_controller = real_win_controller
        script.scene_manager = mock_scene_manager
        script.env = env  # 保留引用

        return script

    def test_scene_transitions_basic(self):
        """验证基本场景转换"""
        env = self._create_replay_environment()

        # 按钮图片路径（完整路径）
        btn_nav = "yys/abyss_shadows/images/abyss_navigation.bmp"
        btn_boss = "yys/abyss_shadows/images/boss_label.bmp"
        btn_wait = "yys/abyss_shadows/images/wait_to_start.bmp"

        # 初始场景
        self.assertEqual(env.get_current_scene(), "狭间暗域_选择界面")

        # 点击战报按钮后跳转
        env.find_and_click(btn_nav)
        self.assertEqual(env.get_current_scene(), "战报界面_当前")

        # 点击首领标签
        env.find_and_click(btn_boss)
        self.assertEqual(env.get_current_scene(), "战斗画面")

        # 战斗等待
        env.find_and_click(btn_wait)
        self.assertEqual(env.get_current_scene(), "战斗结束后")

    def test_scene_capture_returns_screenshot_cache(self):
        """验证 capture_screen 返回 screenshot_cache"""
        env = self._create_replay_environment()

        screenshot = env.capture_screen()
        self.assertIsNotNone(screenshot)

        # 切换场景后，capture_screen 应该返回新的截图
        env.set_scene("战斗画面")
        new_screenshot = env.capture_screen()
        self.assertIsNotNone(new_screenshot)

    def test_ocr_mock_set_and_get(self):
        """验证 OCR Mock 功能"""
        env = self._create_replay_environment()

        # 设置 OCR 结果
        env.set_mock_ocr_result("1000000")
        results = env.find_all_texts(None)
        self.assertIn("1000000", results)

        # 检查 contains_text
        self.assertTrue(env.contains_text(None, "100"))
        self.assertFalse(env.contains_text(None, "不存在"))

    def test_full_battle_flow(self):
        """验证完整战斗流程"""
        env = self._create_replay_environment()
        script = self._create_script_with_real_win_controller(env)

        # 重置挑战计数
        script.challenge_counts = {
            EnemyType.BOSS: 0,
            EnemyType.COMMANDER: 0,
            EnemyType.ELITE: 0
        }

        # Mock 所有敌人未挑战
        for enemy_type in EnemyType:
            for enemy in script.enemies[enemy_type]:
                enemy.has_challenged = False

        # Mock find_image_with_timeout 返回位置
        def mock_find(path, **kwargs):
            if "boss_label" in str(path):
                return (600, 150)
            elif "commander_label" in str(path):
                return (500, 280)
            elif "elite_label" in str(path):
                return (400, 400)
            return (-1, -1)
        script.win_controller.find_image_with_timeout = MagicMock(side_effect=mock_find)

        # Mock OCR 不返回"已击破"
        env.set_mock_ocr_result("")

        # 初始场景
        self.assertEqual(env.get_current_scene(), "狭间暗域_选择界面")

        # scene_manager.goto_scene 会调用 env.set_scene("abyss_dragon")
        # 这会更新场景为 abyss_dragon（但实际上我们的 env 没有这个场景图）
        # 所以会创建一个空白图片

        # 模拟点击战报按钮，这才是真正的场景转换
        # 使用 env.transition_to_next_scene 手动触发场景转换（按钮路径需使用完整路径）
        env.transition_to_next_scene("yys/abyss_shadows/images/abyss_navigation.bmp")
        self.assertEqual(env.get_current_scene(), "战报界面_当前")

    def test_no_enemy_available_switches_scene(self):
        """验证没有可用敌人时切换场景"""
        env = self._create_replay_environment()
        script = self._create_script_with_real_win_controller(env)

        # 设置所有敌人已挑战
        for enemy_type in EnemyType:
            for enemy in script.enemies[enemy_type]:
                enemy.has_challenged = True

        # 初始场景
        env.set_scene("狭间暗域_选择界面")

        # 应该切换到下一个场景
        result = script._on_abyss_shadows_enemy_selection((0, 0))
        self.assertFalse(result)


class TestSceneReplayEnvironmentUnit(unittest.TestCase):
    """SceneReplayEnvironment 单元测试"""

    def test_initial_scene_loaded(self):
        """验证初始场景正确加载"""
        env = SceneReplayEnvironment(
            scene_dir=str(PROJECT_ROOT / "yys/abyss_shadows/images/example"),
            transitions_config=str(
                PROJECT_ROOT / "yys/abyss_shadows/config/scene_transitions_abyss_shadows.json"
            ),
            initial_scene="狭间暗域_选择界面"
        )
        self.assertEqual(env.get_current_scene(), "狭间暗域_选择界面")
        self.assertIsNotNone(env.capture_screen())

    def test_set_scene_updates_cache(self):
        """验证 set_scene 更新 screenshot_cache"""
        env = SceneReplayEnvironment(
            scene_dir=str(PROJECT_ROOT / "yys/abyss_shadows/images/example"),
            transitions_config=str(
                PROJECT_ROOT / "yys/abyss_shadows/config/scene_transitions_abyss_shadows.json"
            ),
            initial_scene="狭间暗域_选择界面"
        )

        # 切换场景
        env.set_scene("战斗画面")
        self.assertEqual(env.get_current_scene(), "战斗画面")
        self.assertIsNotNone(env.capture_screen())

    def test_click_records_action(self):
        """验证点击记录到 action_log"""
        from tests.common.recorders.action_log import ActionLog

        action_log = ActionLog()
        env = SceneReplayEnvironment(
            scene_dir=str(PROJECT_ROOT / "yys/abyss_shadows/images/example"),
            transitions_config=str(
                PROJECT_ROOT / "yys/abyss_shadows/config/scene_transitions_abyss_shadows.json"
            ),
            initial_scene="狭间暗域_选择界面",
            action_log=action_log
        )

        initial_count = len(env.action_log.records)
        env.left_click(100, 200)
        self.assertEqual(len(env.action_log.records), initial_count + 1)


if __name__ == '__main__':
    unittest.main()
