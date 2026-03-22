import os
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

from yys.scene_manager import SceneManager, SceneDetectionResult


class TestSceneManager(unittest.TestCase):
    def setUp(self):
        # 创建一个模拟的窗口句柄
        self.mock_hwnd = 199268

        # 创建临时目录和测试图像
        self.test_dir = tempfile.mkdtemp()
        self.scene_dir = os.path.join(self.test_dir, "scene")
        self.control_dir = os.path.join(self.test_dir, "scene_control")
        os.makedirs(self.scene_dir, exist_ok=True)
        os.makedirs(self.control_dir, exist_ok=True)

        # 创建一些虚拟图像文件（仅用于测试路径解析）
        self.scene_image = os.path.join(self.scene_dir, "home.bmp")
        with open(self.scene_image, 'w') as f:
            f.write("dummy image content")

        self.transition_image = os.path.join(self.control_dir, "home_to_battle.bmp")
        with open(self.transition_image, 'w') as f:
            f.write("dummy transition image content")

    def tearDown(self):
        # 删除临时目录
        shutil.rmtree(self.test_dir)

    @patch('yys.scene_manager.ImageFinder')
    def test_register_scenes_from_directory(self, mock_image_finder):
        """测试从目录注册场景和跳转"""
        mock_image_finder.return_value = Mock()
        manager = SceneManager(self.mock_hwnd, Mock())

        manager.register_scenes_from_directory(self.scene_dir, self.control_dir)

        # 验证场景被加载
        self.assertIn("home", manager.scene_images)
        self.assertGreater(len(manager.scene_images), 0)
        self.assertGreaterEqual(len(manager.scene_transitions), 0)

    def test_scene_detection_result(self):
        """测试场景检测结果对象"""
        result = SceneDetectionResult("home", "yys/common/images/scene/home.bmp", (100, 200))

        self.assertEqual(result.scene_name, "home")
        self.assertEqual(result.matched_image, "yys/common/images/scene/home.bmp")
        self.assertEqual(result.position, (100, 200))
        self.assertIn("home", str(result))

    def test_is_reachable(self):
        """测试场景可达性"""
        manager = SceneManager(self.mock_hwnd, Mock())

        # 手动设置场景图
        manager.scene_graph = {
            "home": {"battle": "btn1"},
            "battle": {"shop": "btn2"},
            "shop": {}
        }

        # 测试相同场景
        self.assertTrue(manager.is_reachable("home", "home"))

        # 测试直接连接
        self.assertTrue(manager.is_reachable("home", "battle"))

        # 测试间接连接
        self.assertTrue(manager.is_reachable("home", "shop"))

        # 测试不可达场景
        self.assertFalse(manager.is_reachable("shop", "home"))

    @patch('yys.scene_manager.ImageFinder')
    def test_register_scene(self, mock_image_finder):
        """测试注册单个场景"""
        mock_image_finder.return_value = Mock()
        manager = SceneManager(self.mock_hwnd, Mock())

        manager.register_scene("test_scene", ["path/to/test.bmp"])

        self.assertIn("test_scene", manager.scene_images)
        self.assertEqual(manager.scene_images["test_scene"], ["path/to/test.bmp"])

    @patch('yys.scene_manager.ImageFinder')
    def test_register_scene_multiple_images(self, mock_image_finder):
        """测试注册场景时添加多张图片"""
        mock_image_finder.return_value = Mock()
        manager = SceneManager(self.mock_hwnd, Mock())

        manager.register_scene("test_scene", ["path/to/test1.bmp", "path/to/test2.bmp"])

        self.assertIn("test_scene", manager.scene_images)
        self.assertEqual(len(manager.scene_images["test_scene"]), 2)
        self.assertIn("path/to/test1.bmp", manager.scene_images["test_scene"])
        self.assertIn("path/to/test2.bmp", manager.scene_images["test_scene"])

    @patch('yys.scene_manager.ImageFinder')
    def test_register_transition(self, mock_image_finder):
        """测试注册场景跳转"""
        mock_image_finder.return_value = Mock()
        manager = SceneManager(self.mock_hwnd, Mock())

        manager.register_transition("home", "battle", "path/to/btn.bmp")

        self.assertIn(("home", "battle"), manager.scene_transitions)
        self.assertEqual(manager.scene_transitions[("home", "battle")], "path/to/btn.bmp")
        self.assertIn("battle", manager.scene_graph["home"])

    @patch('yys.scene_manager.ImageFinder')
    def test_register_global_transition(self, mock_image_finder):
        """测试注册通用跳转按钮"""
        mock_image_finder.return_value = Mock()
        manager = SceneManager(self.mock_hwnd, Mock())

        manager.register_scene("home", ["path/to/home.bmp"])
        manager.register_scene("battle", ["path/to/battle.bmp"])
        manager.register_global_transition("shop", "path/to/shop_btn.bmp")

        self.assertIn("shop", manager.global_transitions)
        self.assertEqual(manager.global_transitions["shop"], "path/to/shop_btn.bmp")
        # home 和 battle 都应该有到 shop 的通用跳转
        self.assertIn("shop", manager.scene_graph["home"])
        self.assertIn("shop", manager.scene_graph["battle"])

    @patch('yys.scene_manager.ImageFinder')
    def test_empty_initialization(self, mock_image_finder):
        """测试初始化后默认不加载任何场景"""
        mock_image_finder.return_value = Mock()
        manager = SceneManager(self.mock_hwnd, Mock())

        # 默认初始化后不应有任何场景
        self.assertEqual(len(manager.scene_images), 0)
        self.assertEqual(len(manager.scene_transitions), 0)
        self.assertEqual(len(manager.global_transitions), 0)

    @patch('yys.scene_manager.ImageFinder')
    def test_register_then_add_from_directory(self, mock_image_finder):
        """测试编程式注册后可以继续从目录加载"""
        mock_image_finder.return_value = Mock()

        # 先编程式注册
        manager = SceneManager(self.mock_hwnd, Mock())
        manager.register_scene("custom_scene", ["path/to/custom.bmp"])

        # 验证只有自定义场景
        self.assertIn("custom_scene", manager.scene_images)
        self.assertEqual(len(manager.scene_images), 1)

        # 从目录加载
        manager.register_scenes_from_directory(self.scene_dir, self.control_dir)

        # 验证目录中的场景也被加载了
        self.assertIn("home", manager.scene_images)
        self.assertIn("custom_scene", manager.scene_images)

    @patch('yys.scene_manager.ImageFinder')
    def test_register_global_transition_from_directory(self, mock_image_finder):
        """测试从目录加载通用跳转（to_xxx 格式）"""
        mock_image_finder.return_value = Mock()

        # 创建包含 to_xxx 格式的目录
        control_dir = os.path.join(self.test_dir, "control_with_global")
        os.makedirs(control_dir, exist_ok=True)
        to_home_file = os.path.join(control_dir, "to_home.bmp")
        with open(to_home_file, 'w') as f:
            f.write("dummy")

        manager = SceneManager(self.mock_hwnd, Mock())
        manager.register_scene("scene_a", ["path/to/a.bmp"])
        manager.register_scenes_from_directory(self.scene_dir, control_dir)

        # 验证通用跳转被注册
        self.assertIn("home", manager.global_transitions)


if __name__ == '__main__':
    unittest.main()
