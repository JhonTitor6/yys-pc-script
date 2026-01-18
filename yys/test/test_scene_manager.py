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
        original_images_dir = "images/scene/"
        self.original_exists = os.path.exists
        self.original_listdir = os.listdir
        
        def mock_exists(path):
            if path == "images/scene/":
                return True
            elif path == "images/scene/scene_control/":
                return True
            else:
                return self.original_exists(path)
        
        def mock_listdir(path):
            if path == "images/scene/":
                return ["home.bmp"]
            elif path == "images/scene/scene_control/":
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
    @patch('yys.scene_manager.capture_window_region')
    def test_scene_manager_initialization(self, mock_capture, mock_image_finder):
        """测试场景管理器初始化"""
        # Mock截图函数
        mock_capture.return_value = None
        mock_image_finder.return_value = Mock()
        
        # 创建场景管理器
        manager = SceneManager(self.mock_hwnd)
        
        # 验证场景图构建
        self.assertIn("home", manager.scene_images)
        self.assertEqual(len(manager.scene_transitions), 1)
        self.assertIn(("home", "battle"), manager.scene_transitions)
    
    def test_scene_detection_result(self):
        """测试场景检测结果对象"""
        result = SceneDetectionResult("home","images/scene/home.bmp", (100, 200))
        
        self.assertEqual(result.scene_name, "home")
        self.assertEqual(result.matched_image, "images/scene/home.bmp")
        self.assertEqual(result.position, (100, 200))
        self.assertIn("home", str(result))
    
    def test_is_reachable(self):
        """测试场景可达性"""
        # 这个测试需要先初始化场景管理器，但由于图像依赖，我们测试逻辑
        manager = SceneManager(self.mock_hwnd)
        
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


if __name__ == '__main__':
    unittest.main()