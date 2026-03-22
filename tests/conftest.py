# tests/conftest.py
"""pytest 配置文件，提供测试 fixtures"""
import pytest
from pathlib import Path

# 配置测试数据基础路径
TEST_DATA_BASE = Path(__file__).parent / "common" / "images"


@pytest.fixture
def example_images_dir() -> Path:
    """示例截图目录"""
    return Path(__file__).parent.parent / "yys" / "soul_raid" / "images" / "test" / "example"


@pytest.fixture
def mock_env(mock_image_provider) -> "MockEnvironment":
    """Mock 游戏环境 fixture"""
    from tests.common.environment.mock_environment import MockEnvironment
    return MockEnvironment(image_provider=mock_image_provider)


@pytest.fixture
def mock_image_provider() -> "FileImageProvider":
    """Mock 图片提供者 fixture"""
    from tests.common.providers.file_image_provider import FileImageProvider
    return FileImageProvider(base_folder=str(TEST_DATA_BASE))