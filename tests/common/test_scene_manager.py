import os
import shutil
import tempfile
import unittest
from unittest.mock import Mock

from yys.common.scene_manager import (
    SceneManager,
    SceneDetectionResult,
    SceneGraphValidationError,
)


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

        # battling 已注册场景：home_to_battle.bmp 归一化后指向它（PRD AC1）
        battling_image = os.path.join(self.scene_dir, "battling.bmp")
        with open(battling_image, 'w') as f:
            f.write("dummy battling image content")

        self.transition_image = os.path.join(self.control_dir, "home_to_battle.bmp")
        with open(self.transition_image, 'w') as f:
            f.write("dummy transition image content")

    def tearDown(self):
        # 删除临时目录
        shutil.rmtree(self.test_dir)

    def test_register_scenes_from_directory(self):
        """测试从目录注册场景和跳转"""
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

    def test_register_scene(self):
        """测试注册单个场景"""
        manager = SceneManager(self.mock_hwnd, Mock())

        manager.register_scene("test_scene", ["path/to/test.bmp"])

        self.assertIn("test_scene", manager.scene_images)
        self.assertEqual(manager.scene_images["test_scene"], ["path/to/test.bmp"])

    def test_register_scene_multiple_images(self):
        """测试注册场景时添加多张图片"""
        manager = SceneManager(self.mock_hwnd, Mock())

        manager.register_scene("test_scene", ["path/to/test1.bmp", "path/to/test2.bmp"])

        self.assertIn("test_scene", manager.scene_images)
        self.assertEqual(len(manager.scene_images["test_scene"]), 2)
        self.assertIn("path/to/test1.bmp", manager.scene_images["test_scene"])
        self.assertIn("path/to/test2.bmp", manager.scene_images["test_scene"])

    def test_register_transition(self):
        """测试注册场景跳转（目标经别名归一化，不产生幽灵节点）"""
        # 产品契约：PRD AC1——跳转目标 battle 必须归一化为已注册的 battling。
        manager = SceneManager(self.mock_hwnd, Mock())

        manager.register_transition("home", "battle", "path/to/btn.bmp")

        self.assertIn(("home", "battling"), manager.scene_transitions)
        self.assertEqual(manager.scene_transitions[("home", "battling")], "path/to/btn.bmp")
        self.assertIn("battling", manager.scene_graph["home"])
        self.assertNotIn("battle", manager.scene_graph["home"])

    def test_register_global_transition(self):
        """测试注册通用跳转按钮"""
        manager = SceneManager(self.mock_hwnd, Mock())

        manager.register_scene("home", ["path/to/home.bmp"])
        manager.register_scene("battle", ["path/to/battle.bmp"])
        manager.register_global_transition("shop", "path/to/shop_btn.bmp")

        self.assertIn("shop", manager.global_transitions)
        self.assertEqual(manager.global_transitions["shop"], "path/to/shop_btn.bmp")
        # home 和 battling（battle 归一化后）都应该有到 shop 的通用跳转
        self.assertIn("shop", manager.scene_graph["home"])
        self.assertIn("shop", manager.scene_graph["battling"])

    def test_empty_initialization(self):
        """测试初始化后默认不加载任何场景"""
        manager = SceneManager(self.mock_hwnd, Mock())

        # 默认初始化后不应有任何场景
        self.assertEqual(len(manager.scene_images), 0)
        self.assertEqual(len(manager.scene_transitions), 0)
        self.assertEqual(len(manager.global_transitions), 0)

    def test_register_then_add_from_directory(self):
        """测试编程式注册后可以继续从目录加载"""

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

    def test_register_global_transition_from_directory(self):
        """测试从目录加载通用跳转（to_xxx 格式）"""

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


class TestSceneIdentityNormalization(unittest.TestCase):
    """场景身份归一化与图完整性校验（产品契约：PRD AC1）。

    契约要点：文件名推导出的跳转端点不再静默制造未注册节点；
    未知节点必须在启动前抛出可定位错误。
    """

    def setUp(self):
        self.mock_hwnd = 199268
        self.test_dir = tempfile.mkdtemp()
        self.scene_dir = os.path.join(self.test_dir, "scene")
        self.control_dir = os.path.join(self.test_dir, "scene_control")
        os.makedirs(self.scene_dir, exist_ok=True)
        os.makedirs(self.control_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _make_image(self, directory, filename):
        path = os.path.join(directory, filename)
        with open(path, 'w') as f:
            f.write("dummy")
        return path

    def test_directory_registration_normalizes_ghost_edges(self):
        """目录注册时 battle/chapter_28/soul 归一化为已注册规范节点。"""
        # 场景资产：规范场景已注册；battle/chapter_28/soul 由按钮文件名推导出（幽灵）
        self._make_image(self.scene_dir, "home.bmp")
        self._make_image(self.scene_dir, "battling.bmp")
        self._make_image(self.scene_dir, "exploration_chapter_28.bmp")
        self._make_image(self.scene_dir, "soul_selection.bmp")
        self._make_image(self.control_dir, "home_to_battle.bmp")
        self._make_image(self.control_dir, "home_to_chapter_28.bmp")
        self._make_image(self.control_dir, "to_soul.bmp")

        manager = SceneManager(self.mock_hwnd, Mock())
        manager.register_scenes_from_directory(self.scene_dir, self.control_dir)

        # 归一化后的规范目标存在
        self.assertIn("battling", manager.scene_graph["home"])
        self.assertIn("exploration_chapter_28", manager.scene_graph["home"])
        self.assertIn("soul_selection", manager.scene_graph["home"])
        # 幽灵节点不再出现
        for ghost in ("battle", "chapter_28", "soul"):
            self.assertNotIn(ghost, manager.scene_graph["home"])

    def test_undeclared_edge_target_raises(self):
        """跳转目标未注册且不在外部目标声明时，启动前抛出可定位错误。"""
        self._make_image(self.scene_dir, "home.bmp")
        self._make_image(self.control_dir, "home_to_mystery.bmp")

        manager = SceneManager(self.mock_hwnd, Mock())
        with self.assertRaises(SceneGraphValidationError) as ctx:
            manager.register_scenes_from_directory(self.scene_dir, self.control_dir)
        # 错误信息必须能定位到具体边
        self.assertIn("mystery", str(ctx.exception))
        self.assertIn("home_to_mystery.bmp", str(ctx.exception))

    def test_unregistered_source_raises(self):
        """跳转边源场景未注册时抛出可定位错误。"""
        self._make_image(self.control_dir, "ghost_to_home.bmp")

        manager = SceneManager(self.mock_hwnd, Mock())
        with self.assertRaises(SceneGraphValidationError) as ctx:
            manager.register_scenes_from_directory(self.scene_dir, self.control_dir)
        self.assertIn("ghost", str(ctx.exception))

    def test_alias_cycle_raises(self):
        """别名表存在循环时抛出可定位错误，不得无限循环。"""
        manager = SceneManager(self.mock_hwnd, Mock())
        manager.SCENE_ALIASES = {"a": "b", "b": "a"}

        with self.assertRaises(SceneGraphValidationError) as ctx:
            manager.register_scene("a", ["path/to/a.bmp"])
        self.assertIn("a", str(ctx.exception))
        self.assertIn("b", str(ctx.exception))

    def test_external_targets_allowed(self):
        """显式声明的外部目标节点允许入图，不触发校验错误。"""
        self._make_image(self.scene_dir, "home.bmp")
        self._make_image(self.control_dir, "home_to_awakening_materials.bmp")

        manager = SceneManager(self.mock_hwnd, Mock())
        manager.register_scenes_from_directory(self.scene_dir, self.control_dir)

        self.assertIn("awakening_materials", manager.scene_graph["home"])

    def test_detect_scene_candidates_returns_sorted_evidence(self):
        """候选识别 API 返回按相似度降序的证据且不发送输入。"""
        from tests.common.environment.mock_environment import MockEnvironment
        from tests.common.recorders.action_log import ActionLog

        log = ActionLog()
        env = MockEnvironment(action_log=log)
        manager = SceneManager(env.find_window("阴阳师") or 12345, Mock())

        finder = Mock()
        finder.screenshot_cache = object()
        from win_util.image import ImageMatchResult
        finder.best_match.side_effect = [
            ImageMatchResult((10, 20), "p1.bmp", 0.92),
            ImageMatchResult((-1, -1), "p2.bmp", 0.0),
            ImageMatchResult((30, 40), "p3.bmp", 0.71),
        ]
        manager.win_controller = Mock()
        manager.win_controller.image_finder = finder

        manager.register_scene("home", ["p1.bmp"])
        manager.register_scene("battle", ["p2.bmp"])  # 注册名归一化为 battling
        manager.register_scene("soul", ["p3.bmp"])    # 注册名归一化为 soul_selection

        results = manager.detect_scene_candidates()

        # 按相似度降序，未命中项被排除
        self.assertEqual([r.scene_name for r in results], ["home", "soul_selection"])
        self.assertEqual(results[0].similarity, 0.92)
        self.assertEqual(results[0].position, (10, 20))
        # 识别过程不产生任何鼠标/键盘输入
        log.assert_click_count(0)

    def test_normalize_scene_name(self):
        """归一化入口对非别名名称保持原样。"""
        manager = SceneManager(self.mock_hwnd, Mock())
        self.assertEqual(manager.normalize_scene_name("home"), "home")
        self.assertEqual(manager.normalize_scene_name("battle"), "battling")
        self.assertEqual(manager.normalize_scene_name("soul"), "soul_selection")


if __name__ == '__main__':
    unittest.main()
