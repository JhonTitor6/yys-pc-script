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
        self.images_dir = os.path.join(self.test_dir, "images", "scene")
        self.control_dir = os.path.join(self.images_dir, "scene_control")
        os.makedirs(self.control_dir, exist_ok=True)
        
        # 创建一些虚拟图像文件（仅用于测试路径解析）
        self.scene_image = os.path.join(self.images_dir, "home.bmp")
        with open(self.scene_image, 'w') as f:
            f.write("dummy image content")
        
        self.transition_image = os.path.join(self.control_dir, "home_to_battle.bmp")
        with open(self.transition_image, 'w') as f:
            f.write("dummy transition image content")
        
        # 临时替换图像目录
        original_images_dir = "yys/images/scene/"
        self.original_exists = os.path.exists
        self.original_listdir = os.listdir
        
        def mock_exists(path):
            if path == "yys/images/scene/":
                return True
            elif path == "yys/images/scene/scene_control/":
                return True
            else:
                return self.original_exists(path)
        
        def mock_listdir(path):
            if path == "yys/images/scene/":
                return ["home.bmp"]
            elif path == "yys/images/scene/scene_control/":
                return ["home_to_battle.bmp"]
            else:
                return self.original_listdir(path)
        
        os.path.exists = mock_exists
        os.listdir = mock_listdir
        
    def tearDown(self):
        # 恢复原始函数
        os.path.exists = self.original_exists
        os.listdir = self.original_listdir
        
        # 删除临时目录
        shutil.rmtree(self.test_dir)
    
    @patch('yys.scene_manager.ImageFinder')
    def test_scene_manager_initialization(self, mock_image_finder):
        """测试场景管理器初始化（使用文件系统加载）"""
        mock_image_finder.return_value = Mock()

        # 创建场景管理器，不禁用文件系统加载
        manager = SceneManager(self.mock_hwnd, Mock())

        # 验证场景图构建 - 由于使用真实文件系统，检查是否有场景被加载
        self.assertGreater(len(manager.scene_images), 0)
        self.assertGreaterEqual(len(manager.scene_transitions), 0)
    
    def test_scene_detection_result(self):
        """测试场景检测结果对象"""
        result = SceneDetectionResult("home","yys/images/scene/home.bmp", (100, 200))
        
        self.assertEqual(result.scene_name, "home")
        self.assertEqual(result.matched_image, "yys/images/scene/home.bmp")
        self.assertEqual(result.position, (100, 200))
        self.assertIn("home", str(result))
    
    def test_is_reachable(self):
        """测试场景可达性"""
        # 这个测试需要先初始化场景管理器，但由于图像依赖，我们测试逻辑
        manager = SceneManager(self.mock_hwnd, Mock(), auto_load_from_filesystem=False)

        # 由于没有实际图像，手动设置场景图
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
        manager = SceneManager(self.mock_hwnd, Mock(), auto_load_from_filesystem=False)

        manager.register_scene("test_scene", ["path/to/test.bmp"])

        self.assertIn("test_scene", manager.scene_images)
        self.assertEqual(manager.scene_images["test_scene"], ["path/to/test.bmp"])

    @patch('yys.scene_manager.ImageFinder')
    def test_register_scene_multiple_images(self, mock_image_finder):
        """测试注册场景时添加多张图片"""
        mock_image_finder.return_value = Mock()
        manager = SceneManager(self.mock_hwnd, Mock(), auto_load_from_filesystem=False)

        manager.register_scene("test_scene", ["path/to/test1.bmp", "path/to/test2.bmp"])

        self.assertIn("test_scene", manager.scene_images)
        self.assertEqual(len(manager.scene_images["test_scene"]), 2)
        self.assertIn("path/to/test1.bmp", manager.scene_images["test_scene"])
        self.assertIn("path/to/test2.bmp", manager.scene_images["test_scene"])

    @patch('yys.scene_manager.ImageFinder')
    def test_register_transition(self, mock_image_finder):
        """测试注册场景跳转"""
        mock_image_finder.return_value = Mock()
        manager = SceneManager(self.mock_hwnd, Mock(), auto_load_from_filesystem=False)

        manager.register_transition("home", "battle", "path/to/btn.bmp")

        self.assertIn(("home", "battle"), manager.scene_transitions)
        self.assertEqual(manager.scene_transitions[("home", "battle")], "path/to/btn.bmp")
        self.assertIn("battle", manager.scene_graph["home"])

    @patch('yys.scene_manager.ImageFinder')
    def test_register_global_transition(self, mock_image_finder):
        """测试注册通用跳转按钮"""
        mock_image_finder.return_value = Mock()
        manager = SceneManager(self.mock_hwnd, Mock(), auto_load_from_filesystem=False)

        manager.register_scene("home", ["path/to/home.bmp"])
        manager.register_scene("battle", ["path/to/battle.bmp"])
        manager.register_global_transition("shop", "path/to/shop_btn.bmp")

        self.assertIn("shop", manager.global_transitions)
        self.assertEqual(manager.global_transitions["shop"], "path/to/shop_btn.bmp")
        # home 和 battle 都应该有到 shop 的通用跳转
        self.assertIn("shop", manager.scene_graph["home"])
        self.assertIn("shop", manager.scene_graph["battle"])

    @patch('yys.scene_manager.ImageFinder')
    def test_auto_load_disabled(self, mock_image_finder):
        """测试 auto_load_from_filesystem=False 时不加载文件系统"""
        mock_image_finder.return_value = Mock()
        manager = SceneManager(self.mock_hwnd, Mock(), auto_load_from_filesystem=False)

        # 不应加载任何文件系统中的场景
        self.assertEqual(len(manager.scene_images), 0)
        self.assertEqual(len(manager.scene_transitions), 0)
        self.assertEqual(len(manager.global_transitions), 0)

    @patch('yys.scene_manager.ImageFinder')
    def test_programmatic_then_filesystem(self, mock_image_finder):
        """测试编程式注册后可以继续从文件系统加载"""
        mock_image_finder.return_value = Mock()

        # 先编程式注册
        manager = SceneManager(self.mock_hwnd, Mock(), auto_load_from_filesystem=False)
        manager.register_scene("custom_scene", ["path/to/custom.bmp"])

        # 验证只有自定义场景
        self.assertIn("custom_scene", manager.scene_images)
        self.assertEqual(len(manager.scene_images), 1)

        # 手动调用文件系统加载（模拟之前禁用，现在启用）
        manager._load_scenes_from_filesystem()
        manager._build_scene_graph()

        # 验证文件系统中的场景也被加载了
        self.assertIn("home", manager.scene_images)
        self.assertIn("custom_scene", manager.scene_images)


if __name__ == '__main__':
    unittest.main()