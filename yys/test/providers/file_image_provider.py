# yys/test/providers/file_image_provider.py
from PIL import Image
from pathlib import Path
import os


class FileImageProvider:
    """从本地文件加载图片的实现，用于 Mock 测试环境"""

    def __init__(self, base_folder: str = "yys/test/test_data/scenarios"):
        self._current_image: Image.Image | None = None
        self._base_folder = Path(base_folder)

    def get_current_image(self) -> Image.Image:
        """获取当前游戏画面"""
        if self._current_image is None:
            raise RuntimeError("No image set. Call set_current_image_from_file first.")
        return self._current_image

    def load_image(self, path: str) -> Image.Image:
        """加载指定路径的图片"""
        full_path = self._base_folder / path if not os.path.isabs(path) else Path(path)
        return Image.open(full_path)

    def set_current_image_from_file(self, file_path: str) -> None:
        """设置当前画面为指定文件"""
        self._current_image = Image.open(file_path)

    def list_available_images(self, folder: str) -> list[str]:
        """列出可用场景图片"""
        folder_path = self._base_folder / folder
        if not folder_path.exists():
            return []
        return [str(p.relative_to(self._base_folder)) for p in folder_path.rglob("*.png")]