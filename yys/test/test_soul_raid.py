# yys/test/test_soul_raid.py
"""
御魂模块测试用例

测试场景：
1. 验证点击操作被正确记录到 ActionLog
2. 验证 assert_click_at 支持误差范围
3. 完整场景测试：战斗结算界面 -> 点击挑战 -> 验证操作记录
"""
import pytest
from pathlib import Path
from yys.test.environment.mock_environment import MockEnvironment
from yys.test.providers.file_image_provider import FileImageProvider
from yys.test.recorders.action_log import ActionLog

# 测试数据路径
TEST_DATA_BASE = Path(__file__).parent / "test_data" / "scenarios"
SOUL_RAID_EXAMPLE = TEST_DATA_BASE / "soul_raid" / "example"


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

    def test_full_scenario_battle_settlement_to_challenge(self):
        """
        完整场景测试：战斗结算界面 -> 点击挑战 -> 验证操作记录

        测试流程：
        1. 加载"御魂_战斗结算.png"作为当前画面
        2. 模拟脚本识别"挑战"按钮（假设识别到坐标 500, 400）
        3. 执行点击操作
        4. 验证 ActionLog 记录正确
        """
        log = ActionLog()
        env = MockEnvironment(action_log=log)

        # 加载结算界面截图
        settlement_image = SOUL_RAID_EXAMPLE / "御魂_战斗结算.png"
        if settlement_image.exists():
            env.image_provider.set_current_image_from_file(str(settlement_image))

        # 模拟识别到挑战按钮在 (500, 400)
        challenge_button_x = 500
        challenge_button_y = 400

        # 执行点击
        env.left_click(challenge_button_x, challenge_button_y)

        # 验证
        log.assert_click_at(challenge_button_x, challenge_button_y, tolerance=5)
        log.assert_click_count(1, action_type="left_click")

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
