# yys.common.operations - 公共操作方法封装
# 提供图像查找、点击等操作的统一封装

from dataclasses import dataclass
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from win_util.controller import WinController


@dataclass
class OperationResult:
    """操作结果"""
    success: bool
    position: Optional[Tuple[int, int]] = None
    message: str = ""


class ImageOperations:
    """图像相关操作封装"""

    def __init__(self, controller: 'WinController'):
        """
        初始化图像操作封装

        :param controller: WinController 实例
        """
        self._controller = controller

    def find_image(
        self,
        image_path: str,
        timeout: int = 0,
        similarity: float = 0.8
    ) -> OperationResult:
        """
        查找图片

        :param image_path: 图片路径
        :param timeout: 超时时间（秒），0 表示不设置超时
        :param similarity: 相似度阈值
        :return: OperationResult，包含成功状态和位置
        """
        if timeout > 0:
            point = self._controller.find_image_with_timeout(
                image_path, timeout=timeout, similarity=similarity
            )
        else:
            point = self._controller.find_image(
                image_path, similarity=similarity
            )

        if point and point != (-1, -1):
            return OperationResult(success=True, position=point)
        return OperationResult(success=False, message="未找到目标")

    def find_and_click(
        self,
        image_path: str,
        timeout: int = 0,
        x_range: int = 20,
        y_range: int = 20,
        similarity: float = 0.8
    ) -> OperationResult:
        """
        查找图片并点击

        注意：默认的 x_range/y_range 使用字面值 20，而不是 ClickRange.DEFAULT。
        这是为了避免 operations 模块与 battle 模块的常量产生耦合。
        ClickRange.DEFAULT 的值也是 20，所以行为是一致的。

        :param image_path: 图片路径
        :param timeout: 超时时间（秒），0 表示不设置超时
        :param x_range: X轴随机偏移范围，默认 20
        :param y_range: Y轴随机偏移范围，默认 20
        :param similarity: 相似度阈值
        :return: OperationResult，包含成功状态和位置
        """
        result = self.find_image(image_path, timeout, similarity)
        if result.success and result.position:
            self._controller.mouse.bg_left_click(
                result.position, x_range=x_range, y_range=y_range
            )
        return result

    def wait_for_image(
        self,
        image_path: str,
        timeout: int = 10,
        similarity: float = 0.8
    ) -> OperationResult:
        """
        等待图片出现

        此方法委托给 WinController.find_image_with_timeout()，该方法在超时时间内
        持续重试查找图片，而不是只尝试一次。

        :param image_path: 图片路径
        :param timeout: 超时时间（秒），默认 10 秒
        :param similarity: 相似度阈值
        :return: OperationResult，包含成功状态和位置
        """
        return self.find_image(image_path, timeout, similarity)
