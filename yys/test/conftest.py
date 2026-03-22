# yys/test/conftest.py
"""pytest 配置文件，提供测试 fixtures"""
import pytest
from pathlib import Path

# 配置测试数据基础路径
TEST_DATA_BASE = Path(__file__).parent / "test_data" / "scenarios"


@pytest.fixture
def example_images_dir() -> Path:
    """示例截图目录"""
    return TEST_DATA_BASE / "soul_raid" / "example"


@pytest.fixture
def mock_env(mock_image_provider) -> "MockEnvironment":
    """Mock 游戏环境 fixture"""
    from yys.test.environment.mock_environment import MockEnvironment
    return MockEnvironment(image_provider=mock_image_provider)


@pytest.fixture
def mock_image_provider() -> "FileImageProvider":
    """Mock 图片提供者 fixture"""
    from yys.test.providers.file_image_provider import FileImageProvider
    return FileImageProvider(base_folder=str(TEST_DATA_BASE))
