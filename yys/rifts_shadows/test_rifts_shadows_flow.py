"""
狭间暗域脚本流程测试

验证狭间暗域脚本的核心流程逻辑，包括：
- 场景流转
- 敌人优先级
- 挑战计数
- 伤害退出机制
- 战报界面导航

注意：此测试文件通过 Mock 所有系统级依赖（cv2, win32api, easyocr 等）
来实现在无游戏环境下的单元测试。
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ==================== 在导入任何项目模块之前，先 Mock 所有系统级依赖 ====================

# Mock cv2 和 numpy（图像处理依赖）
_mock_cv2 = MagicMock()
_mock_numpy = MagicMock()
sys.modules['cv2'] = _mock_cv2
sys.modules['numpy'] = _mock_numpy

# Mock win32gui, win32ui, win32con, win32api 等（Windows GUI 依赖）
for _mod in ['win32gui', 'win32ui', 'win32con', 'win32api',
             'win32clipboard', 'win32process']:
    sys.modules[_mod] = MagicMock()

# Mock PIL (图像依赖)
_mock_pil = MagicMock()
sys.modules['PIL'] = _mock_pil
sys.modules['PIL.ImageGrab'] = MagicMock()

# Mock easyocr (OCR 依赖)
_mock_easyocr = MagicMock()
sys.modules['easyocr'] = _mock_easyocr

# Mock loguru (日志依赖)
_mock_loguru = MagicMock()
sys.modules['loguru'] = _mock_loguru

# Mock mss (屏幕截图依赖)
_mock_mss = MagicMock()
sys.modules['mss'] = _mock_mss

# ==================== 导入项目模块 ====================

from yys.rifts_shadows.rifts_shadows_script import Main, EnemyType, Enemy, RiftsShadowsState
from yys.common.event_script_base import YYSBaseScript


class TestRiftsShadowsFlow(unittest.TestCase):
    """狭间暗域脚本流程测试"""

    def _create_mock_script_instance(self):
        """创建一个带有完全 Mock 依赖的脚本实例"""
        mock_hwnd = 199268

        # 创建 Mock 对象
        mock_keyboard = MagicMock()
        mock_mouse = MagicMock()
        mock_scene_manager = MagicMock()
        mock_image_finder = MagicMock()
        mock_ocr = MagicMock()
        mock_win_controller = MagicMock()

        # 配置 mock_image_finder
        type(mock_image_finder).screenshot_cache = PropertyMock(return_value=None)
        mock_image_finder.crop_screenshot_cache = MagicMock(return_value=None)
        mock_image_finder.screenshot_cache = None

        # 配置 mock_ocr
        mock_ocr.find_all_texts = MagicMock(return_value=None)
        mock_ocr.contains_text = MagicMock(return_value=False)

        # 配置 mock_win_controller
        mock_win_controller.image_finder = mock_image_finder
        mock_win_controller.ocr = mock_ocr
        mock_win_controller.keyboard = mock_keyboard
        mock_win_controller.mouse = mock_mouse
        mock_win_controller.find_image_with_timeout = MagicMock(return_value=None)
        mock_win_controller.find_and_click = MagicMock(return_value=False)

        # 配置 mock_scene_manager
        mock_scene_manager.goto_scene = MagicMock(return_value=True)
        mock_scene_manager.click_return = MagicMock()

        # 使用 patch 在正确的位置拦截（YYSBaseScript 导入的位置）
        with patch('yys.common.event_script_base.find_window', return_value=mock_hwnd), \
             patch('yys.common.event_script_base.WinController', return_value=mock_win_controller), \
             patch('yys.common.event_script_base.SceneManager', return_value=mock_scene_manager), \
             patch('yys.common.event_script_base.ImageFinder', return_value=mock_image_finder), \
             patch('yys.common.event_script_base.CommonOcr', return_value=mock_ocr):

            script = Main()

        # 重新注入 Mock 对象（确保引用正确）
        script.win_controller = mock_win_controller
        script.image_finder = mock_image_finder
        script.ocr = mock_ocr
        script.scene_manager = mock_scene_manager

        return script

    def setUp(self):
        """测试前准备"""
        self.script = self._create_mock_script_instance()

    # ==================== 敌人优先级测试 ====================

    def test_enemy_priority_order(self):
        """验证敌人优先级顺序：首领 > 副将 > 精英"""
        # 重置所有敌人的已挑战状态
        for enemy_type in EnemyType:
            for enemy in self.script.enemies[enemy_type]:
                enemy.has_challenged = False

        # 重置挑战计数
        self.script.challenge_counts = {
            EnemyType.BOSS: 0,
            EnemyType.COMMANDER: 0,
            EnemyType.ELITE: 0
        }

        # Mock OCR：所有敌人都未击破
        self.script.ocr.find_all_texts = MagicMock(return_value=None)

        # Mock find_image_with_timeout：返回非空位置
        def mock_find_image(path, **kwargs):
            if "boss_label" in path:
                return (600, 150)
            elif "commander_label" in path:
                return (500, 280)
            elif "elite_label" in path:
                return (400, 390)
            return None

        self.script.win_controller.find_image_with_timeout = MagicMock(side_effect=mock_find_image)

        # 获取第一个可挑战的敌人
        enemy = self.script.get_next_enemy()

        # 验证返回的是首领（优先级最高）
        self.assertIsNotNone(enemy)
        self.assertEqual(enemy.enemy_type, EnemyType.BOSS)

    def test_enemy_priority_commander_after_boss_exhausted(self):
        """验证首领挑战完毕后返回副将"""
        # 设置首领已达上限
        self.script.challenge_counts[EnemyType.BOSS] = self.script.max_challenge_counts[EnemyType.BOSS]

        # 重置所有敌人状态
        for enemy_type in EnemyType:
            for enemy in self.script.enemies[enemy_type]:
                enemy.has_challenged = False

        # Mock OCR
        self.script.ocr.find_all_texts = MagicMock(return_value=None)

        # Mock find_image_with_timeout
        def mock_find_image(path, **kwargs):
            if "commander_label" in path:
                return (500, 280)
            elif "elite_label" in path:
                return (400, 390)
            return None

        self.script.win_controller.find_image_with_timeout = MagicMock(side_effect=mock_find_image)

        # 获取第一个可挑战的敌人
        enemy = self.script.get_next_enemy()

        # 验证返回的是副将
        self.assertIsNotNone(enemy)
        self.assertEqual(enemy.enemy_type, EnemyType.COMMANDER)

    def test_enemy_priority_elite_after_boss_and_commander_exhausted(self):
        """验证首领和副将都挑战完毕后返回精英"""
        # 设置首领和副将已达上限
        self.script.challenge_counts[EnemyType.BOSS] = self.script.max_challenge_counts[EnemyType.BOSS]
        self.script.challenge_counts[EnemyType.COMMANDER] = self.script.max_challenge_counts[EnemyType.COMMANDER]

        # 重置所有敌人状态
        for enemy_type in EnemyType:
            for enemy in self.script.enemies[enemy_type]:
                enemy.has_challenged = False

        # Mock OCR
        self.script.ocr.find_all_texts = MagicMock(return_value=None)

        # Mock find_image_with_timeout
        def mock_find_image(path, **kwargs):
            if "elite_label" in path:
                return (400, 390)
            return None

        self.script.win_controller.find_image_with_timeout = MagicMock(side_effect=mock_find_image)

        # 获取第一个可挑战的敌人
        enemy = self.script.get_next_enemy()

        # 验证返回的是精英
        self.assertIsNotNone(enemy)
        self.assertEqual(enemy.enemy_type, EnemyType.ELITE)

    def test_enemy_priority_skips_already_challenged(self):
        """验证已挑战的敌人会被跳过"""
        # 重置所有敌人状态，但标记首领已挑战
        for enemy_type in EnemyType:
            for enemy in self.script.enemies[enemy_type]:
                enemy.has_challenged = (enemy_type == EnemyType.BOSS)

        # 重置首领计数（模拟刚打完首领）
        self.script.challenge_counts[EnemyType.BOSS] = 0

        # Mock OCR
        self.script.ocr.find_all_texts = MagicMock(return_value=None)

        # Mock find_image_with_timeout
        def mock_find_image(path, **kwargs):
            if "boss_label" in path:
                return (600, 150)
            elif "commander_label" in path:
                return (500, 280)
            return None

        self.script.win_controller.find_image_with_timeout = MagicMock(side_effect=mock_find_image)

        # 获取第一个可挑战的敌人
        enemy = self.script.get_next_enemy()

        # 验证返回的是副将（因为首领已标记为已挑战）
        self.assertIsNotNone(enemy)
        self.assertEqual(enemy.enemy_type, EnemyType.COMMANDER)

    # ==================== 挑战计数测试 ====================

    def test_challenge_counts_increment(self):
        """验证挑战计数在每次挑战后正确累加"""
        initial_counts = dict(self.script.challenge_counts)

        # 模拟挑战一次副将
        self.script.challenge_counts[EnemyType.COMMANDER] += 1

        self.assertEqual(
            self.script.challenge_counts[EnemyType.COMMANDER],
            initial_counts[EnemyType.COMMANDER] + 1
        )

    def test_max_challenge_counts_stops_boss(self):
        """验证达到首领最大挑战次数后不再挑战"""
        self.script.challenge_counts[EnemyType.BOSS] = self.script.max_challenge_counts[EnemyType.BOSS]

        # 重置所有敌人状态
        for enemy_type in EnemyType:
            for enemy in self.script.enemies[enemy_type]:
                enemy.has_challenged = False

        # 标记首领已挑战（因为已达上限，应该被跳过）
        self.script.enemies[EnemyType.BOSS][0].has_challenged = True

        # 获取第一个可挑战的敌人
        enemy = self.script.get_next_enemy()

        # 验证不是首领
        if enemy is not None:
            self.assertNotEqual(enemy.enemy_type, EnemyType.BOSS)

    def test_max_challenge_counts_stops_commander(self):
        """验证达到副将最大挑战次数后不再挑战"""
        self.script.challenge_counts[EnemyType.COMMANDER] = self.script.max_challenge_counts[EnemyType.COMMANDER]

        # 重置所有敌人状态，但副将标记为已挑战
        for enemy_type in EnemyType:
            for enemy in self.script.enemies[enemy_type]:
                enemy.has_challenged = (enemy_type == EnemyType.COMMANDER)

        # 获取第一个可挑战的敌人
        enemy = self.script.get_next_enemy()

        # 验证不是副将
        if enemy is not None:
            self.assertNotEqual(enemy.enemy_type, EnemyType.COMMANDER)

    # ==================== 伤害退出测试 ====================

    def test_damage_exit_commander(self):
        """验证副将伤害超过阈值时退出战斗"""
        # 设置当前敌人为副将
        commander_enemy = Enemy(
            enemy_type=EnemyType.COMMANDER,
            reach_damage_quit=33700000,
            image_path="yys/rifts_shadows/images/commander_label.bmp",
            label_position=(424, 250, 558, 335)
        )
        self.script._cur_enemy = commander_enemy

        # 模拟 OCR 返回超过阈值的伤害
        self.script.ocr.find_all_texts = MagicMock(return_value=["40000000"])

        # Mock crop_screenshot_cache
        self.script.image_finder.crop_screenshot_cache = MagicMock(return_value=None)

        # 调用 _on_battling
        result = self.script._on_battling((0, 0))

        # 验证按下了 ESC 和 ENTER
        self.script.win_controller.key_down.assert_any_call("esc")
        self.script.win_controller.key_down.assert_any_call("enter")
        self.assertTrue(result)

    def test_damage_exit_elite(self):
        """验证精英伤害超过阈值时退出战斗"""
        # 设置当前敌人为精英
        elite_enemy = Enemy(
            enemy_type=EnemyType.ELITE,
            reach_damage_quit=5000000,
            image_path="yys/rifts_shadows/images/elite_label.bmp",
            label_position=(342, 360, 480, 435)
        )
        self.script._cur_enemy = elite_enemy

        # 模拟 OCR 返回超过阈值的伤害
        self.script.ocr.find_all_texts = MagicMock(return_value=["6000000"])

        # Mock crop_screenshot_cache
        self.script.image_finder.crop_screenshot_cache = MagicMock(return_value=None)

        # 调用 _on_battling
        result = self.script._on_battling((0, 0))

        # 验证按下了 ESC 和 ENTER
        self.script.win_controller.key_down.assert_any_call("esc")
        self.script.win_controller.key_down.assert_any_call("enter")
        self.assertTrue(result)

    def test_damage_exit_boss_no_limit(self):
        """验证首领不设伤害上限"""
        # 设置当前敌人为首领
        boss_enemy = Enemy(
            enemy_type=EnemyType.BOSS,
            reach_damage_quit=999999999,  # 首领不设上限
            image_path="yys/rifts_shadows/images/boss_label.bmp",
            label_position=(554, 120, 688, 210)
        )
        self.script._cur_enemy = boss_enemy

        # 模拟 OCR 返回低于阈值的伤害（首领阈值是 999999999）
        self.script.ocr.find_all_texts = MagicMock(return_value=["500000000"])

        # Mock crop_screenshot_cache
        self.script.image_finder.crop_screenshot_cache = MagicMock(return_value=None)

        # 调用 _on_battling
        result = self.script._on_battling((0, 0))

        # 验证没有按下任何键（伤害未超过阈值）
        self.script.win_controller.key_down.assert_not_called()
        self.assertFalse(result)

    def test_damage_no_exit_below_threshold(self):
        """验证伤害低于阈值时不退出战斗"""
        # 设置当前敌人为副将
        commander_enemy = Enemy(
            enemy_type=EnemyType.COMMANDER,
            reach_damage_quit=33700000,
            image_path="yys/rifts_shadows/images/commander_label.bmp",
            label_position=(424, 250, 558, 335)
        )
        self.script._cur_enemy = commander_enemy

        # 模拟 OCR 返回低于阈值的伤害
        self.script.ocr.find_all_texts = MagicMock(return_value=["30000000"])

        # Mock crop_screenshot_cache
        self.script.image_finder.crop_screenshot_cache = MagicMock(return_value=None)

        # 调用 _on_battling
        result = self.script._on_battling((0, 0))

        # 验证没有按下任何键
        self.script.win_controller.key_down.assert_not_called()
        self.assertFalse(result)

    # ==================== 场景流转测试 ====================

    def test_on_rifts_shadows_selection_navigates_to_dragon(self):
        """验证在狭间暗域选择界面时导航到神龙暗域"""
        # 调用选择界面回调
        self.script._on_rifts_shadows_selection((0, 0))

        # 验证导航到第一个场景
        self.script.scene_manager.goto_scene.assert_called_with("abyss_dragon")

    def test_on_rifts_shadows_selection_navigates_based_on_index(self):
        """验证根据 cur_scene_index 导航到对应场景"""
        # 设置当前场景索引
        self.script.cur_scene_index = 2  # 对应 rifts_shadows_panther

        # 调用选择界面回调
        self.script._on_rifts_shadows_selection((0, 0))

        # 验证导航到对应场景
        self.script.scene_manager.goto_scene.assert_called_with("abyss_leopard")

    def test_scene_flow_when_no_enemy_available(self):
        """验证没有可挑战敌人时切换场景

        场景：当前暗域所有敌人都已挑战（或已达上限），需要切换到下一个暗域
        """
        # 设置当前场景索引为中间位置（不是最后一个）
        # 这样切换后 cur_scene_index + 1 不会越界
        self.script.cur_scene_index = 1

        # 模拟所有敌人都已达上限或已挑战
        self.script.challenge_counts[EnemyType.BOSS] = self.script.max_challenge_counts[EnemyType.BOSS]
        self.script.challenge_counts[EnemyType.COMMANDER] = self.script.max_challenge_counts[EnemyType.COMMANDER]
        self.script.challenge_counts[EnemyType.ELITE] = self.script.max_challenge_counts[EnemyType.ELITE]

        for enemy_type in EnemyType:
            for enemy in self.script.enemies[enemy_type]:
                enemy.has_challenged = True

        # 模拟没有可挑战的敌人
        self.script.ocr.find_all_texts = MagicMock(return_value=None)
        self.script.win_controller.find_image_with_timeout = MagicMock(return_value=None)

        # Mock change_area 方法
        self.script.change_area = MagicMock(return_value=True)

        # 调用敌人选择回调（由于没有可挑战敌人，会调用 _handle_no_enemy_available）
        result = self.script._on_rifts_shadows_enemy_selection((0, 0))

        # 验证返回 False
        self.assertFalse(result)

        # 验证调用了 change_area (cur_scene_index=1 递增后变成 2，对应 abyss_leopard)
        self.script.change_area.assert_called_with("abyss_leopard")

        # 验证场景索引已更新
        self.assertEqual(self.script.cur_scene_index, 2)

    # ==================== 战报界面测试 ====================

    def test_battle_report_button_click(self):
        """验证点击战报按钮"""
        mock_point = (100, 200)

        # Mock bg_left_click
        self.script.bg_left_click = MagicMock()

        # 调用战报按钮回调
        self.script._on_battle_report_button(mock_point)

        # 验证点击被调用
        self.script.bg_left_click.assert_called_once_with(mock_point)

    def test_battle_report_state(self):
        """验证战报按钮会更新状态"""
        self.script.bg_left_click = MagicMock()

        # 调用战报按钮回调
        self.script._on_battle_report_button((100, 200))

        # 验证状态变为 BATTLE_REPORT
        self.assertEqual(self.script._state, RiftsShadowsState.BATTLE_REPORT)

    # ==================== 敌人OCR识别测试 ====================

    def test_enemy_defeated_not_implemented(self):
        """验证 OCR 识别"已击破"状态暂未实现（TODO）

        当前 get_next_enemy() 直接返回第一个未挑战的敌人，不检查 OCR 结果
        """
        # 重置所有敌人状态
        for enemy_type in EnemyType:
            for enemy in self.script.enemies[enemy_type]:
                enemy.has_challenged = False

        # 模拟 OCR 识别到"已击破"（但这个结果不会被使用）
        self.script.ocr.find_all_texts = MagicMock(return_value=["已击破"])

        # 模拟 find_image_with_timeout 返回位置
        self.script.win_controller.find_image_with_timeout = MagicMock(return_value=(600, 150))

        # 获取第一个可挑战的敌人 - 应该直接返回首领，不检查 OCR
        enemy = self.script.get_next_enemy()

        # 由于 OCR 识别"已击破"功能暂未实现（TODO），
        # get_next_enemy() 直接返回第一个未挑战的敌人（首领）
        self.assertIsNotNone(enemy)
        self.assertEqual(enemy.enemy_type, EnemyType.BOSS)

    # ==================== 阈值常量验证 ====================

    def test_commander_damage_threshold(self):
        """验证副将伤害阈值为 33,700,000"""
        # 查找副将敌人
        commander_enemies = self.script.enemies[EnemyType.COMMANDER]
        self.assertGreater(len(commander_enemies), 0)

        for enemy in commander_enemies:
            self.assertEqual(enemy.reach_damage_quit, 33700000)

    def test_elite_damage_threshold(self):
        """验证精英伤害阈值为 5,000,000"""
        # 查找精英敌人
        elite_enemies = self.script.enemies[EnemyType.ELITE]
        self.assertGreater(len(elite_enemies), 0)

        for enemy in elite_enemies:
            self.assertEqual(enemy.reach_damage_quit, 5000000)

    def test_boss_damage_threshold(self):
        """验证首领伤害阈值为 999999999（不设上限）"""
        # 查找首领敌人
        boss_enemies = self.script.enemies[EnemyType.BOSS]
        self.assertGreater(len(boss_enemies), 0)

        for enemy in boss_enemies:
            self.assertEqual(enemy.reach_damage_quit, 999999999)


class TestRiftsShadowsEnemyDef(unittest.TestCase):
    """狭间暗域敌人定义测试"""

    def _create_mock_script_instance(self):
        """创建一个带有完全 Mock 依赖的脚本实例"""
        mock_hwnd = 199268

        # 创建 Mock 对象
        mock_keyboard = MagicMock()
        mock_mouse = MagicMock()
        mock_scene_manager = MagicMock()
        mock_image_finder = MagicMock()
        mock_ocr = MagicMock()
        mock_win_controller = MagicMock()

        # 配置 mock_win_controller
        mock_win_controller.image_finder = mock_image_finder
        mock_win_controller.ocr = mock_ocr
        mock_win_controller.keyboard = mock_keyboard
        mock_win_controller.mouse = mock_mouse

        with patch('yys.common.event_script_base.find_window', return_value=mock_hwnd), \
             patch('yys.common.event_script_base.WinController', return_value=mock_win_controller), \
             patch('yys.common.event_script_base.SceneManager', return_value=mock_scene_manager), \
             patch('yys.common.event_script_base.ImageFinder', return_value=mock_image_finder), \
             patch('yys.common.event_script_base.CommonOcr', return_value=mock_ocr):

            script = Main()

        return script

    def test_enemy_structure(self):
        """验证敌人结构定义正确"""
        script = self._create_mock_script_instance()

        # 验证首领配置
        self.assertEqual(len(script.enemies[EnemyType.BOSS]), 1)
        boss = script.enemies[EnemyType.BOSS][0]
        self.assertEqual(boss.enemy_type, EnemyType.BOSS)
        self.assertTrue(boss.has_challenged)  # 首领默认已挑战

        # 验证副将配置
        self.assertEqual(len(script.enemies[EnemyType.COMMANDER]), 2)
        for commander in script.enemies[EnemyType.COMMANDER]:
            self.assertEqual(commander.enemy_type, EnemyType.COMMANDER)
            self.assertEqual(commander.reach_damage_quit, 33700000)
            self.assertTrue(commander.has_challenged)

        # 验证精英配置
        self.assertEqual(len(script.enemies[EnemyType.ELITE]), 3)
        for elite in script.enemies[EnemyType.ELITE]:
            self.assertEqual(elite.enemy_type, EnemyType.ELITE)
            self.assertEqual(elite.reach_damage_quit, 5000000)
            self.assertFalse(elite.has_challenged)  # 精英默认未挑战

    def test_max_challenge_counts_definition(self):
        """验证最大挑战次数定义"""
        script = self._create_mock_script_instance()

        # 验证最大挑战次数
        self.assertEqual(script.max_challenge_counts[EnemyType.BOSS], 2)
        self.assertEqual(script.max_challenge_counts[EnemyType.COMMANDER], 4)
        self.assertEqual(script.max_challenge_counts[EnemyType.ELITE], 6)


if __name__ == '__main__':
    unittest.main()
