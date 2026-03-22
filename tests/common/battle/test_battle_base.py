# tests.common.battle.test_battle_base - 战斗基类测试

import pytest
from unittest.mock import Mock, MagicMock
from yys.common.battle.base import BattleFlow
from yys.common.battle.hooks import BattleHooks
from yys.common.constants import BattleEndType, ImageSimilarity, ClickRange
from yys.common.operations import ImageOperations, OperationResult


class MockBattleHooks(BattleHooks):
    """Mock 战斗钩子实现"""

    def __init__(self):
        self.challenge_found_called = False
        self.challenge_clicked_called = False
        self.should_continue_value = True
        self.call_count = 0
        self.battle_end_called = False
        self.victory_called = False
        self.defeat_called = False
        self.last_end_type = None

    def on_challenge_found(self, position):
        self.challenge_found_called = True

    def on_challenge_clicked(self):
        self.challenge_clicked_called = True

    def on_battle_start(self):
        pass

    def on_battle_end(self, end_type):
        self.battle_end_called = True
        self.last_end_type = end_type

    def on_victory(self):
        self.victory_called = True

    def on_defeat(self):
        self.defeat_called = True

    def should_continue(self):
        self.call_count += 1
        if self.call_count > 3:
            self.should_continue_value = False
        return self.should_continue_value


@pytest.fixture
def mock_operations():
    """创建 Mock ImageOperations"""
    ops = Mock(spec=ImageOperations)
    ops.wait_for_image = Mock()
    ops.find_and_click = Mock()
    ops.find_image = Mock()
    return ops


def test_battle_flow_initialization(mock_operations):
    """测试 BattleFlow 初始化"""
    hooks = MockBattleHooks()
    flow = BattleFlow(
        script_name="test",
        challenge_image="test.bmp",
        operations=mock_operations,
        hooks=hooks,
        max_battle_count=10
    )

    assert flow.script_name == "test"
    assert flow.challenge_image == "test.bmp"
    assert flow.max_battle_count == 10
    assert flow.current_battle_count == 0
    assert flow.current_victory_count == 0


def test_battle_flow_wait_challenge_calls_hook(mock_operations):
    """测试 _wait_challenge 调用钩子"""
    hooks = MockBattleHooks()
    ops = mock_operations

    # 模拟挑战按钮出现
    ops.wait_for_image.return_value = OperationResult(
        success=True, position=(100, 200)
    )

    flow = BattleFlow(
        script_name="test",
        challenge_image="test.bmp",
        operations=ops,
        hooks=hooks,
        max_battle_count=3
    )

    flow._wait_challenge()
    assert hooks.challenge_found_called is True


def test_battle_flow_click_challenge_calls_hook(mock_operations):
    """测试 _click_challenge 调用钩子"""
    hooks = MockBattleHooks()
    ops = mock_operations

    # 模拟点击成功
    ops.find_and_click.return_value = OperationResult(
        success=True, position=(100, 200)
    )

    flow = BattleFlow(
        script_name="test",
        challenge_image="test.bmp",
        operations=ops,
        hooks=hooks,
        max_battle_count=3
    )

    flow._click_challenge()
    assert hooks.challenge_clicked_called is True


def test_battle_flow_handle_victory(mock_operations):
    """测试战斗胜利处理"""
    hooks = MockBattleHooks()
    ops = mock_operations

    flow = BattleFlow(
        script_name="test",
        challenge_image="test.bmp",
        operations=ops,
        hooks=hooks,
        max_battle_count=3
    )

    flow._handle_battle_end(BattleEndType.VICTORY)

    assert hooks.battle_end_called is True
    assert hooks.victory_called is True
    assert hooks.defeat_called is False
    assert flow.current_victory_count == 1
    assert flow.current_battle_count == 1


def test_battle_flow_handle_defeat(mock_operations):
    """测试战斗失败处理"""
    hooks = MockBattleHooks()
    ops = mock_operations

    flow = BattleFlow(
        script_name="test",
        challenge_image="test.bmp",
        operations=ops,
        hooks=hooks,
        max_battle_count=3
    )

    flow._handle_battle_end(BattleEndType.DEFEAT)

    assert hooks.battle_end_called is True
    assert hooks.defeat_called is True
    assert hooks.victory_called is False
    assert flow.current_victory_count == 0
    assert flow.current_battle_count == 1


def test_battle_flow_poll_battle_end_victory(mock_operations):
    """测试轮询检测战斗结束 - 胜利"""
    hooks = MockBattleHooks()
    ops = mock_operations

    flow = BattleFlow(
        script_name="test",
        challenge_image="test.bmp",
        operations=ops,
        hooks=hooks,
        max_battle_count=3
    )

    # 设置战斗结束配置
    flow.BATTLE_END_CONFIGS = [
        {'image': 'victory.bmp', 'type': 'victory'},
        {'image': 'defeat.bmp', 'type': 'defeat'},
    ]

    # 模拟先找到胜利图片
    call_count = [0]

    def mock_find_image(img_path, **kwargs):
        call_count[0] += 1
        if 'victory.bmp' in img_path:
            return OperationResult(success=True, position=(100, 200))
        return OperationResult(success=False)

    ops.find_image.side_effect = mock_find_image

    end_type = flow._poll_battle_end(max_wait_seconds=5)
    assert end_type == BattleEndType.VICTORY


def test_battle_flow_poll_battle_end_defeat(mock_operations):
    """测试轮询检测战斗结束 - 失败"""
    hooks = MockBattleHooks()
    ops = mock_operations

    flow = BattleFlow(
        script_name="test",
        challenge_image="test.bmp",
        operations=ops,
        hooks=hooks,
        max_battle_count=3
    )

    # 设置战斗结束配置
    flow.BATTLE_END_CONFIGS = [
        {'image': 'victory.bmp', 'type': 'victory'},
        {'image': 'defeat.bmp', 'type': 'defeat'},
    ]

    def mock_find_image(img_path, **kwargs):
        if 'defeat.bmp' in img_path:
            return OperationResult(success=True, position=(100, 200))
        return OperationResult(success=False)

    ops.find_image.side_effect = mock_find_image

    end_type = flow._poll_battle_end(max_wait_seconds=5)
    assert end_type == BattleEndType.DEFEAT


def test_battle_flow_battle_end_configs_default_empty(mock_operations):
    """测试默认 BATTLE_END_CONFIGS 为空"""
    hooks = MockBattleHooks()
    flow = BattleFlow(
        script_name="test",
        challenge_image="test.bmp",
        operations=mock_operations,
        hooks=hooks,
        max_battle_count=3
    )

    assert flow.BATTLE_END_CONFIGS == []
