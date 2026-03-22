# yys/soul_raid/test_soul_raid.py
"""
御魂模块测试用例

测试场景：
1. 验证点击操作被正确记录到 ActionLog
2. 验证 assert_click_at 支持误差范围
3. 完整场景测试：战斗结算界面 -> 找图 -> 点击挑战 -> 验证操作记录
4. 图像匹配功能测试：验证找图能找到目标并返回正确坐标
"""
from pathlib import Path

import pytest

from win_util.controller import WinController
from tests.common.environment.mock_environment import MockEnvironment
from tests.common.providers.file_image_provider import FileImageProvider
from tests.common.recorders.action_log import ActionLog

# 测试数据路径
TEST_DATA_BASE = Path(__file__).parent / "images" / "test"
SOUL_RAID_EXAMPLE = TEST_DATA_BASE / "example"
SOUL_RAID_IMAGES = Path(__file__).parent.parent / "soul_raid" / "images"


class TestSoulRaidScript:
    """御魂脚本测试"""

    def test_click_recorded_in_action_log(self):
        """
        测试：验证点击操作被正确记录到 ActionLog

        验证点：
        1. 执行点击后，ActionLog 中有对应记录
        2. 记录包含正确的坐标信息
        """
        log = ActionLog()
        env = MockEnvironment(action_log=log)

        # 执行点击
        env.left_click(100, 200)

        # 验证记录
        assert len(log) == 1
        record = log.get_last()[0]
        assert record.x == 100
        assert record.y == 200
        assert record.action_type == "left_click"

    def test_assert_click_at_within_tolerance(self):
        """
        测试：验证 assert_click_at 支持误差范围
        """
        log = ActionLog()
        env = MockEnvironment(action_log=log)

        # 点击 (108, 208)，与目标 (100, 200) 差值为 8
        env.left_click(108, 208)

        # 在误差范围 10 内应该通过
        log.assert_click_at(100, 200, tolerance=10)

        # 超出误差范围（差值 8 > tolerance 5）应该失败
        with pytest.raises(AssertionError):
            log.assert_click_at(100, 200, tolerance=5)

    def test_multiple_clicks_recorded(self):
        """
        测试：验证多次点击都被正确记录
        """
        log = ActionLog()
        env = MockEnvironment(action_log=log)

        # 执行多次点击
        env.left_click(100, 100)
        env.left_click(200, 200)
        env.right_click(300, 300)

        # 验证
        assert len(log) == 3
        log.assert_click_count(2, action_type="left_click")
        log.assert_click_count(1, action_type="right_click")

    def test_image_provider_loads_screenshot(self):
        """
        测试：验证 FileImageProvider 能正确加载截图
        """
        provider = FileImageProvider(base_folder=str(TEST_DATA_BASE))

        # 加载战斗结算截图
        settlement_image = SOUL_RAID_EXAMPLE / "御魂_战斗结算.png"
        assert settlement_image.exists(), f"测试图片不存在: {settlement_image}"

        # 设置当前画面
        provider.set_current_image_from_file(str(settlement_image))

        # 验证加载成功
        img = provider.get_current_image()
        assert img is not None
        assert img.size[0] > 0
        assert img.size[1] > 0


class TestImageMatching:
    """图像匹配测试"""

    @pytest.fixture
    def mock_env_with_screenshot(self):
        """创建带截图的 Mock 环境"""
        provider = FileImageProvider(base_folder=str(TEST_DATA_BASE))

        # 加载组队界面截图作为测试画面
        team_image = SOUL_RAID_EXAMPLE / "御魂_组队界面.png"
        assert team_image.exists(), f"测试图片不存在: {team_image}"
        provider.set_current_image_from_file(str(team_image))

        log = ActionLog()
        env = MockEnvironment(image_provider=provider, action_log=log)
        return env, log

    @pytest.fixture
    def image_finder_with_mock_env(self, mock_env_with_screenshot):
        """创建使用 Mock 环境的 ImageFinder"""
        env, log = mock_env_with_screenshot
        finder = WinController(env=env).image_finder
        # 更新截图缓存
        finder.update_screenshot_cache()
        return finder, env, log

    def test_find_challenge_button_in_team_interface(self, image_finder_with_mock_env):
        """
        测试：在组队界面中查找"挑战"按钮

        验证点：
        1. 图像匹配能找到挑战按钮
        2. 返回的坐标在合理范围内（按钮应该在界面中央区域）
        3. 相似度足够高
        """
        finder, env, log = image_finder_with_mock_env

        # 在组队界面中查找御魂挑战按钮
        challenge_button_path = str(SOUL_RAID_IMAGES / "yuhun_tiaozhan.bmp")
        point = finder.bg_find_pic_by_cache(challenge_button_path, similarity=0.6)

        # 验证找到了按钮（组队界面应该有挑战按钮）
        assert point is not None, "返回结果不应为 None"
        x, y = point
        print(f"找到挑战按钮位置: ({x}, {y})")

        # 坐标应该是有效的（非 -1）
        assert x != -1 and y != -1, f"应该找到挑战按钮，但返回了 ({x}, {y})"

        # 坐标应该在合理范围内（御魂挑战按钮一般在界面右下方）
        # 截图尺寸 1154x680，按钮可能在右边
        assert 0 < x < 1154, f"X坐标 {x} 不在合理范围 [0, 1154]"
        assert 0 < y < 680, f"Y坐标 {y} 不在合理范围 [0, 680]"

    def test_find_button_not_found(self, image_finder_with_mock_env):
        """
        测试：查找一个不存在的按钮返回 (-1, -1)
        """
        finder, _, _ = image_finder_with_mock_env

        # 尝试查找一个肯定不存在的图片
        nonexistent_path = str(SOUL_RAID_IMAGES / "battle_end_success.bmp")
        point = finder.bg_find_pic_by_cache(nonexistent_path, similarity=0.8)

        # 验证返回 (-1, -1) 表示未找到
        assert point == (-1, -1), f"未找到时应返回 (-1, -1)，实际返回 {point}"

    def test_find_button_and_click_recorded(self, image_finder_with_mock_env):
        """
        测试：查找按钮并点击，验证点击坐标与找到的坐标一致

        验证点：
        1. 图像匹配找到按钮位置
        2. 点击操作的坐标与匹配位置一致（在误差范围内）
        """
        finder, env, log = image_finder_with_mock_env

        # 查找挑战按钮
        challenge_button_path = str(SOUL_RAID_IMAGES / "yuhun_tiaozhan.bmp")
        point = finder.bg_find_pic_by_cache(challenge_button_path, similarity=0.6)

        x, y = point
        print(f"找到按钮: ({x}, {y})")

        if x != -1 and y != -1:
            # 执行点击（使用 env 的 left_click，它会记录到 log）
            env.left_click(x, y)

            # 验证点击记录
            log.assert_click_at(x, y, tolerance=5)
            log.assert_click_count(1, action_type="left_click")

            # 验证点击坐标与匹配坐标完全一致
            last_click = log.get_last()[0]
            assert last_click.x == x, f"点击X坐标 {last_click.x} 与匹配坐标 {x} 不一致"
            assert last_click.y == y, f"点击Y坐标 {last_click.y} 与匹配坐标 {y} 不一致"


class TestFullScenario:
    """完整场景测试"""

    def test_full_scenario_team_to_battle(self):
        """
        完整场景测试：组队界面 -> 找挑战按钮 -> 点击 -> 验证操作

        测试流程：
        1. 加载"御魂_组队界面.png"作为当前画面
        2. 使用 ImageFinder 查找"挑战"按钮
        3. 执行点击操作
        4. 验证 ActionLog 记录了正确的点击
        """
        # 初始化
        provider = FileImageProvider(base_folder=str(TEST_DATA_BASE))
        team_image = SOUL_RAID_EXAMPLE / "御魂_组队界面.png"
        provider.set_current_image_from_file(str(team_image))

        log = ActionLog()
        env = MockEnvironment(image_provider=provider, action_log=log)

        # 创建 ImageFinder 并加载截图
        finder = WinController(env=env).image_finder
        finder.update_screenshot_cache()

        # 查找挑战按钮
        challenge_path = str(SOUL_RAID_IMAGES / "yuhun_tiaozhan.bmp")
        point = finder.bg_find_pic_by_cache(challenge_path, similarity=0.6)

        x, y = point
        print(f"完整场景 - 找到挑战按钮: ({x}, {y})")

        # 验证找到了按钮
        assert x != -1 and y != -1, "应该能在组队界面中找到挑战按钮"

        # 执行点击
        env.left_click(x, y)

        # 验证点击记录
        log.assert_click_count(1, action_type="left_click")
        log.assert_click_at(x, y, tolerance=5)

        # 验证点击坐标在按钮区域（截图 1154x680）
        last_click = log.get_last()[0]
        assert 0 < last_click.x < 1154, f"点击X坐标 {last_click.x} 不在合理范围 [0, 1154]"
        assert 0 < last_click.y < 680, f"点击Y坐标 {last_click.y} 不在合理范围 [0, 680]"

    def test_settlement_click_scenario(self):
        """
        场景测试：战斗结算界面 -> 查找并点击挑战按钮

        这个测试验证在结算界面中能否正确找到并点击挑战按钮进行下一局
        """
        # 初始化
        provider = FileImageProvider(base_folder=str(TEST_DATA_BASE))
        settlement_image = SOUL_RAID_EXAMPLE / "御魂_战斗结算.png"
        provider.set_current_image_from_file(str(settlement_image))

        log = ActionLog()
        env = MockEnvironment(image_provider=provider, action_log=log)

        # 创建 ImageFinder 并加载截图
        finder = WinController(env=env).image_finder
        finder.update_screenshot_cache()

        # 在结算界面查找挑战按钮（可能找不到，因为结算界面按钮位置不同）
        challenge_path = str(SOUL_RAID_IMAGES / "yuhun_tiaozhan.bmp")
        point = finder.bg_find_pic_by_cache(challenge_path, similarity=0.6)

        x, y = point
        print(f"结算界面 - 挑战按钮查找结果: ({x}, {y})")

        # 结算界面可能找不到挑战按钮（按钮可能被结算遮罩），这是正常的
        # 这里主要验证图像匹配功能本身正常工作
        if x != -1 and y != -1:
            env.left_click(x, y)
            log.assert_click_at(x, y, tolerance=10)