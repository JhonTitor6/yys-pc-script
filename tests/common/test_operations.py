# tests.common.test_operations - 操作模块测试

import pytest
from unittest.mock import Mock, MagicMock
from yys.common.operations import ImageOperations, OperationResult


@pytest.fixture
def mock_controller():
    """创建 Mock WinController"""
    controller = Mock()
    controller.find_image_with_timeout = Mock(return_value=(100, 200))
    controller.find_image = Mock(return_value=(100, 200))
    controller.mouse.bg_left_click = Mock()
    return controller


def test_find_image_success(mock_controller):
    """测试 find_image 成功查找"""
    ops = ImageOperations(mock_controller)
    result = ops.find_image("test.bmp", timeout=5, similarity=0.8)
    assert result.success is True
    assert result.position == (100, 200)
    mock_controller.find_image_with_timeout.assert_called_once_with(
        "test.bmp", timeout=5, similarity=0.8
    )


def test_find_image_not_found(mock_controller):
    """测试 find_image 未找到图片"""
    mock_controller.find_image.return_value = (-1, -1)
    ops = ImageOperations(mock_controller)
    result = ops.find_image("test.bmp")
    assert result.success is False
    assert result.position is None


def test_find_image_not_found_with_timeout(mock_controller):
    """测试 find_image 未找到图片（带超时）"""
    mock_controller.find_image_with_timeout.return_value = (-1, -1)
    ops = ImageOperations(mock_controller)
    result = ops.find_image("test.bmp", timeout=5)
    assert result.success is False
    assert result.position is None
    mock_controller.find_image_with_timeout.assert_called_once_with(
        "test.bmp", timeout=5, similarity=0.8
    )


def test_find_and_click(mock_controller):
    """测试 find_and_click 查找并点击"""
    ops = ImageOperations(mock_controller)
    result = ops.find_and_click("test.bmp", x_range=10, y_range=10)
    assert result.success is True
    mock_controller.mouse.bg_left_click.assert_called_once()


def test_find_and_click_not_found(mock_controller):
    """测试 find_and_click 未找到图片时不点击"""
    mock_controller.find_image.return_value = (-1, -1)
    ops = ImageOperations(mock_controller)
    result = ops.find_and_click("test.bmp", x_range=10, y_range=10)
    assert result.success is False
    mock_controller.mouse.bg_left_click.assert_not_called()


def test_wait_for_image(mock_controller):
    """测试 wait_for_image 方法"""
    ops = ImageOperations(mock_controller)
    result = ops.wait_for_image("test.bmp", timeout=10, similarity=0.9)
    assert result.success is True
    assert result.position == (100, 200)


def test_operation_result_dataclass():
    """测试 OperationResult 数据类"""
    result = OperationResult(success=True, position=(150, 250), message="找到目标")
    assert result.success is True
    assert result.position == (150, 250)
    assert result.message == "找到目标"


def test_operation_result_default_values():
    """测试 OperationResult 默认值"""
    result = OperationResult(success=False)
    assert result.success is False
    assert result.position is None
    assert result.message == ""
