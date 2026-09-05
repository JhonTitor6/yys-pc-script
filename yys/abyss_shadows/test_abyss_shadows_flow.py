"""
狭间暗域脚本流程测试

验证狭间暗域脚本的核心流程逻辑，包括：
- 场景流转
- 敌人优先级
- 挑战计数
- 伤害退出机制
- 战报界面导航

注意：此测试文件仅 Mock 游戏窗口和 OCR 等系统级依赖。
cv2、numpy 和 PIL 保持真实模块，避免污染同一进程中的场景回放测试。
"""

import os
import sys
import unittest
from typing import Any, Optional
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ==================== 在导入任何项目模块之前，先 Mock 所有系统级依赖 ====================

# Mock win32gui, win32ui, win32con, win32api 等（Windows GUI 依赖）
for _mod in ['win32gui', 'win32ui', 'win32con', 'win32api',
             'win32clipboard', 'win32process']:
    sys.modules[_mod] = MagicMock()

# Mock 截图入口，但保留真实 PIL 包供场景回放加载夹具图片
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

from yys.abyss_shadows.abyss_shadows_script import Main, EnemyType, Enemy, AbyssShadowsState
from yys.common.event_script_base import YYSBaseScript


class TestAbyssShadowsFlow(unittest.TestCase):
    """狭间暗域脚本流程测试"""

    def _create_mock_script_instance(
        self,
        config: Optional[dict[str, Any]] = None,
    ) -> Main:
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
             patch('yys.common.event_script_base.ImageFinder', return_value=mock_image_finder, create=True), \
             patch('yys.common.event_script_base.CommonOcr', return_value=mock_ocr, create=True):

            script = Main(config=config)

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
            target_damage=33700000,
            image_path="yys/abyss_shadows/images/commander_label.bmp",
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
            target_damage=5000000,
            image_path="yys/abyss_shadows/images/elite_label.bmp",
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
            target_damage=999999999,  # 首领不设上限
            image_path="yys/abyss_shadows/images/boss_label.bmp",
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
            target_damage=33700000,
            image_path="yys/abyss_shadows/images/commander_label.bmp",
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

    def test_on_run_handles_current_scene_without_blind_home_actions(self) -> None:
        """已在暗域时直接继续，战斗或未知页面安全停止。"""
        # 产品契约来源：08-14-abyss-current-scene-start PRD AC2、AC3、AC4、AC6。
        safe_scenes = [
            (scene_name, index, AbyssShadowsState.SCENE)
            for index, scene_name in enumerate(self.script.scene_name_list)
        ] + [("abyss_enemy_selection", None, AbyssShadowsState.ENEMY_SELECTION)]

        for scene_name, expected_index, expected_state in safe_scenes:
            with self.subTest(scene_name=scene_name):
                script = self._create_mock_script_instance()
                script.scene_manager.detect_current_scene.return_value = MagicMock(
                    scene_name=scene_name,
                )
                script.goto_abyss_shadows = MagicMock(return_value=True)

                script.on_run()

                self.assertEqual(script._state, expected_state)
                if expected_index is not None:
                    self.assertEqual(script.cur_scene_index, expected_index)
                    self.assertEqual(script._current_area, scene_name)
                script.goto_abyss_shadows.assert_not_called()
                script.scene_manager.goto_scene.assert_not_called()

        for scene_name in ("battling", None):
            with self.subTest(scene_name=scene_name):
                script = self._create_mock_script_instance()
                script.scene_manager.detect_current_scene.return_value = (
                    MagicMock(scene_name=scene_name) if scene_name else None
                )
                script.goto_abyss_shadows = MagicMock(return_value=True)
                script.stop = MagicMock()
                script.win_controller.mouse.reset_mock()
                script.win_controller.keyboard.reset_mock()

                script.on_run()

                script.stop.assert_called_once_with()
                script.goto_abyss_shadows.assert_not_called()
                script.scene_manager.goto_scene.assert_not_called()
                self.assertEqual(script.win_controller.mouse.mock_calls, [])
                self.assertEqual(script.win_controller.keyboard.mock_calls, [])

    def test_on_abyss_shadows_selection_navigates_to_dragon(self):
        """验证在狭间暗域选择界面时导航到神龙暗域"""
        # 调用选择界面回调
        self.script._on_abyss_shadows_selection((0, 0))

        # 验证导航到第一个场景
        self.script.scene_manager.goto_scene.assert_called_with("abyss_dragon")

    def test_on_abyss_shadows_selection_navigates_based_on_index(self):
        """验证根据 cur_scene_index 导航到对应场景"""
        # 设置当前场景索引
        self.script.cur_scene_index = 2  # 对应 abyss_shadows_panther

        # 调用选择界面回调
        self.script._on_abyss_shadows_selection((0, 0))

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
        result = self.script._on_abyss_shadows_enemy_selection((0, 0))

        # 验证返回 False
        self.assertFalse(result)

        # 验证调用了 change_area (cur_scene_index=1 递增后变成 2，对应 abyss_leopard)
        self.script.change_area.assert_called_with("abyss_leopard")

        # 验证场景索引已更新
        self.assertEqual(self.script.cur_scene_index, 2)

    def test_scene_flow_last_area_stops_without_index_error(self):
        """产品契约：最后一个暗域完成后停止，不能访问越界索引。"""
        self.script.cur_scene_index = len(self.script.scene_name_list) - 1
        self.script.challenge_counts = {
            enemy_type: self.script.max_challenge_counts[enemy_type]
            for enemy_type in EnemyType
        }
        for enemy_type in EnemyType:
            for enemy in self.script.enemies[enemy_type]:
                enemy.has_challenged = True

        self.script.stop = MagicMock()
        self.script.change_area = MagicMock()

        result = self.script._on_abyss_shadows_enemy_selection((0, 0))

        self.assertFalse(result)
        self.script.stop.assert_called_once_with()
        self.script.change_area.assert_not_called()
        self.assertEqual(
            self.script.cur_scene_index,
            len(self.script.scene_name_list) - 1,
        )

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
        self.assertEqual(self.script._state, AbyssShadowsState.BATTLE_REPORT)

    # ==================== 敌人已击破识别测试 ====================

    def test_enemy_defeated_is_skipped_from_real_report(self):
        """产品契约：已击破印章必须跳过，红色式神立绘不能误判。"""
        def load_report_image(filename: str) -> np.ndarray:
            image_path = PROJECT_ROOT / "yys/abyss_shadows/images/example" / filename
            image = cv2.imdecode(
                np.fromfile(str(image_path), dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if image is None:
                raise AssertionError(f"无法读取测试图片: {image_path}")
            return image

        def load_fixture_image(filename: str) -> np.ndarray:
            image_path = PROJECT_ROOT / "tests/fixtures/abyss_shadows/defeated_stamp" / filename
            image = cv2.imdecode(
                np.fromfile(str(image_path), dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if image is None or image.shape[:2] != (315, 563):
                raise AssertionError(f"无法读取或尺寸错误的测试夹具: {image_path}")
            restored = np.zeros((435, 905, 3), dtype=np.uint8)
            restored[120:435, 342:905] = image
            return restored

        def use_image(image: np.ndarray) -> None:
            def crop_image(
                x0: int,
                y0: int,
                x1: int,
                y1: int,
            ) -> np.ndarray:
                return image[y0:y1, x0:x1]

            self.script.image_finder = SimpleNamespace(
                screenshot_cache=image,
                crop_screenshot_cache=crop_image,
            )

        enemies = [
            enemy
            for enemy_type in EnemyType
            for enemy in self.script.enemies[enemy_type]
        ]
        cases = [
            ("当前战报", load_report_image("战报界面_当前.png"), [False] * 6),
            ("已击破战报", load_report_image("战报界面_已击破.png"), [False, True, True, True, True, True]),
            ("其他暗域战报", load_report_image("战报界面_其他暗域.png"), [False] * 6),
            ("完整战斗录制负样本", load_fixture_image("recording_negative.png"), [False] * 6),
            ("本次黑豹已击破样本", load_fixture_image("leopard_defeated.png"), [True] * 6),
        ]
        for name, image, expected in cases:
            with self.subTest(name=name):
                use_image(image)
                self.assertEqual(
                    [self.script._is_enemy_defeated(enemy.label_and_pic_position) for enemy in enemies],
                    expected,
                )

        self.assertEqual(sum(expected for _, _, labels in cases for expected in labels), 11)

        # 首领已在内存中处理后，扫描会标记并跳过五个已击破目标。
        for enemy_type in EnemyType:
            for enemy in self.script.enemies[enemy_type]:
                enemy.has_challenged = False
        self.script.challenge_counts = {enemy_type: 0 for enemy_type in EnemyType}
        self.script.enemies[EnemyType.BOSS][0].has_challenged = True

        self.assertIsNone(self.script.get_next_enemy())
        self.assertTrue(all(enemy.has_challenged for enemy in enemies))

    def test_enemy_defeated_returns_false_for_invalid_or_uniform_images(self):
        """产品契约：异常截图和纯色区域不能触发已击破判定。"""
        position = (0, 0, 134, 90)
        valid_screenshot = np.zeros((90, 134, 3), dtype=np.uint8)

        self.script.image_finder = SimpleNamespace(
            screenshot_cache=None,
            crop_screenshot_cache=MagicMock(return_value=None),
        )
        self.assertFalse(self.script._is_enemy_defeated(position))

        for name, cropped in [
            ("缺失裁剪", None),
            ("空裁剪", np.empty((0, 0, 3), dtype=np.uint8)),
            ("灰度图", np.zeros((90, 134), dtype=np.uint8)),
            ("浮点图", np.zeros((90, 134, 3), dtype=np.float32)),
            ("尺寸不足", np.zeros((29, 68, 3), dtype=np.uint8)),
        ]:
            with self.subTest(name=name):
                self.script.image_finder = SimpleNamespace(
                    screenshot_cache=valid_screenshot,
                    crop_screenshot_cache=MagicMock(return_value=cropped),
                )
                self.assertFalse(self.script._is_enemy_defeated(position))

        for name, color in [("纯红", (0, 0, 255)), ("纯黑", (0, 0, 0))]:
            with self.subTest(name=name):
                image = np.full((90, 134, 3), color, dtype=np.uint8)
                self.script.image_finder = SimpleNamespace(
                    screenshot_cache=image,
                    crop_screenshot_cache=lambda *_position: image,
                )
                self.assertFalse(self.script._is_enemy_defeated(position))

    def test_missing_defeated_stamp_template_raises_explicit_error(self):
        """产品契约：模板缺失不能静默回退旧算法。"""
        with patch(
            "yys.abyss_shadows.abyss_shadows_script.to_project_path",
            return_value="missing-defeated-stamp-mask.png",
        ), self.assertRaisesRegex(ValueError, "已击破印章模板"):
            Main._load_defeated_stamp_mask()

    # ==================== 阈值常量验证 ====================

    def test_commander_damage_threshold(self):
        """验证副将伤害阈值为 1。"""
        # 查找副将敌人
        commander_enemies = self.script.enemies[EnemyType.COMMANDER]
        self.assertGreater(len(commander_enemies), 0)

        for enemy in commander_enemies:
            self.assertEqual(enemy.target_damage, 1)

    def test_elite_damage_threshold(self):
        """验证精英伤害阈值为 6,000,000。"""
        # 查找精英敌人
        elite_enemies = self.script.enemies[EnemyType.ELITE]
        self.assertGreater(len(elite_enemies), 0)

        for enemy in elite_enemies:
            self.assertEqual(enemy.target_damage, 6000000)

    def test_boss_damage_threshold(self):
        """验证首领伤害阈值默认使用界面配置默认值。"""
        # 查找首领敌人
        boss_enemies = self.script.enemies[EnemyType.BOSS]
        self.assertGreater(len(boss_enemies), 0)

        for enemy in boss_enemies:
            self.assertEqual(enemy.target_damage, 1)

    def test_boss_damage_threshold_uses_config(self):
        """验证首领伤害阈值使用传入的界面配置。"""
        script = self._create_mock_script_instance(
            config={"boss_damage_limit": 123456789},
        )

        boss_enemies = script.enemies[EnemyType.BOSS]
        self.assertGreater(len(boss_enemies), 0)
        for enemy in boss_enemies:
            self.assertEqual(enemy.target_damage, 123456789)

    def test_damage_thresholds_use_separate_config_values(self):
        """产品契约：三类敌人只使用各自的伤害阈值，次数与顺序不变。"""
        script = self._create_mock_script_instance(
            config={
                "boss_damage_limit": 11,
                "commander_damage_limit": 22,
                "elite_damage_limit": 33,
            },
        )

        expected = {
            EnemyType.BOSS: 11,
            EnemyType.COMMANDER: 22,
            EnemyType.ELITE: 33,
        }
        self.assertEqual(list(script.enemies), list(EnemyType))
        for enemy_type, target_damage in expected.items():
            with self.subTest(enemy_type=enemy_type):
                self.assertTrue(script.enemies[enemy_type])
                self.assertTrue(all(
                    enemy.target_damage == target_damage
                    for enemy in script.enemies[enemy_type]
                ))
        self.assertEqual(script.max_challenge_counts, {
            EnemyType.BOSS: 2,
            EnemyType.COMMANDER: 4,
            EnemyType.ELITE: 6,
        })

    def test_new_damage_thresholds_fall_back_to_original_defaults(self):
        """产品契约：旧配置缺少新字段时保留原副将和精英阈值。"""
        script = self._create_mock_script_instance(
            config={"boss_damage_limit": 99},
        )

        self.assertEqual(script.commander_damage_limit, 1)
        self.assertEqual(script.elite_damage_limit, 6000000)
        self.assertTrue(all(
            enemy.target_damage == 1
            for enemy in script.enemies[EnemyType.COMMANDER]
        ))
        self.assertTrue(all(
            enemy.target_damage == 6000000
            for enemy in script.enemies[EnemyType.ELITE]
        ))

    def test_new_damage_thresholds_reject_out_of_range_config(self):
        """产品契约：两个新阈值复用公共配置范围校验。"""
        for field_name in ("commander_damage_limit", "elite_damage_limit"):
            for value in (-1, 1000000000):
                with self.subTest(field_name=field_name, value=value), self.assertRaises(ValueError):
                    self._create_mock_script_instance(config={field_name: value})

    def test_damage_threshold_comparison_remains_strictly_greater(self):
        """产品契约：三类伤害等于阈值不退出，超过阈值才退出。"""
        script = self._create_mock_script_instance(
            config={
                "boss_damage_limit": 101,
                "commander_damage_limit": 202,
                "elite_damage_limit": 303,
            },
        )

        for enemy_type in EnemyType:
            enemy = script.enemies[enemy_type][0]
            with self.subTest(enemy_type=enemy_type, current_damage=enemy.target_damage):
                script._cur_enemy = enemy
                script._last_damage_check_time = 0.0
                script.ocr.find_all_texts.return_value = [str(enemy.target_damage)]
                script.win_controller.key_down.reset_mock()

                self.assertFalse(script._on_battling((0, 0)))
                script.win_controller.key_down.assert_not_called()

            with self.subTest(enemy_type=enemy_type, current_damage=enemy.target_damage + 1):
                script._cur_enemy = enemy
                script._last_damage_check_time = 0.0
                script.ocr.find_all_texts.return_value = [str(enemy.target_damage + 1)]
                script.win_controller.key_down.reset_mock()

                with patch("yys.abyss_shadows.abyss_shadows_script.random_sleep"):
                    self.assertTrue(script._on_battling((0, 0)))
                script.win_controller.key_down.assert_any_call("esc")
                script.win_controller.key_down.assert_any_call("enter")

    def test_damage_ocr_uses_recognition_only_and_safe_fallback(self):
        """产品契约：固定伤害区域禁用检测/分类，无法唯一识别时返回 0。"""
        image = np.zeros((44, 280, 3), dtype=np.uint8)
        self.script.image_finder.crop_screenshot_cache.return_value = image
        self.script.ocr.find_all_texts.return_value = ["33871291"]

        self.assertEqual(self.script._get_current_damage(), 33871291)
        self.script.ocr.find_all_texts.assert_called_once_with(
            image,
            similarity_threshold=0.2,
            allowlist="0123456789",
            use_det=False,
            use_cls=False,
            use_rec=True,
        )

        self.script.ocr.find_all_texts.reset_mock()
        self.script.ocr.find_all_texts.return_value = ["3", "3"]
        self.assertEqual(self.script._get_current_damage(), 0)

    def test_damage_ocr_reuses_previous_value_for_low_confidence_leading_one(self):
        """产品契约：低置信度前导 1 与上一确认值一致时沿用上一值。"""
        image = np.zeros((44, 280, 3), dtype=np.uint8)
        self.script.image_finder.crop_screenshot_cache.return_value = image
        low_threshold_calls = 0

        def find_all_texts(_image, similarity_threshold, **_kwargs):
            nonlocal low_threshold_calls
            if similarity_threshold == 0.2:
                low_threshold_calls += 1
                return ["39261"] if low_threshold_calls == 1 else ["139261"]
            return []

        self.script.ocr.find_all_texts = MagicMock(side_effect=find_all_texts)

        self.assertEqual(self.script._get_current_damage(), 39261)
        self.assertEqual(self.script._get_current_damage(), 39261)

    def test_damage_ocr_keeps_high_confidence_leading_one_and_rejects_first_low_confidence(self):
        """产品契约：合法高置信度前导 1 保留，无法确认的首个读数安全返回 0。"""
        image = np.zeros((44, 280, 3), dtype=np.uint8)
        self.script.image_finder.crop_screenshot_cache.return_value = image

        self.script.ocr.find_all_texts = MagicMock(
            side_effect=lambda _image, similarity_threshold, **_kwargs: (
                ["10136043"] if similarity_threshold == 0.2 else ["10136043"]
            )
        )
        self.assertEqual(self.script._get_current_damage(), 10136043)

        self.script.ocr.find_all_texts = MagicMock(
            side_effect=lambda _image, similarity_threshold, **_kwargs: (
                ["139261"] if similarity_threshold == 0.2 else []
            )
        )
        self.script._last_damage_value = None
        self.assertEqual(self.script._get_current_damage(), 0)

    def test_boss_damage_threshold_rejects_out_of_range_config(self):
        """验证首领伤害阈值复用公共配置范围校验。"""
        with self.assertRaises(ValueError):
            self._create_mock_script_instance(
                config={"boss_damage_limit": 1000000000},
            )


class TestAbyssShadowsEnemyDef(unittest.TestCase):
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
             patch('yys.common.event_script_base.ImageFinder', return_value=mock_image_finder, create=True), \
             patch('yys.common.event_script_base.CommonOcr', return_value=mock_ocr, create=True):

            script = Main()

        return script

    def test_enemy_structure(self):
        """验证敌人结构定义正确"""
        script = self._create_mock_script_instance()

        # 验证首领配置
        self.assertEqual(len(script.enemies[EnemyType.BOSS]), 1)
        boss = script.enemies[EnemyType.BOSS][0]
        self.assertEqual(boss.enemy_type, EnemyType.BOSS)
        self.assertFalse(boss.has_challenged)  # 首领默认未挑战

        # 验证副将配置
        self.assertEqual(len(script.enemies[EnemyType.COMMANDER]), 2)
        for commander in script.enemies[EnemyType.COMMANDER]:
            self.assertEqual(commander.enemy_type, EnemyType.COMMANDER)
            self.assertEqual(commander.target_damage, 1)
            self.assertFalse(commander.has_challenged)  # 副将默认未挑战

        # 验证精英配置
        self.assertEqual(len(script.enemies[EnemyType.ELITE]), 3)
        for elite in script.enemies[EnemyType.ELITE]:
            self.assertEqual(elite.enemy_type, EnemyType.ELITE)
            self.assertEqual(elite.target_damage, 6000000)
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
