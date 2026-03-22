# tests/common/environment/scene_replay_environment.py
"""场景回放环境 - 基于状态机的场景流转测试环境"""

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from .mock_environment import MockEnvironment

logger = logging.getLogger(__name__)


class SceneReplayEnvironment(MockEnvironment):
    """场景回放环境 - 通过场景状态机控制进行测试回放

    继承自 MockEnvironment，但通过场景配置实现场景流转：
    - 维护当前场景截图
    - 根据点击查找场景转换并更新场景
    """

    def __init__(
        self,
        scene_dir: str,
        transitions_config: str,
        initial_scene: str,
        action_log=None
    ):
        """初始化场景回放环境

        Args:
            scene_dir: 场景图片目录
            transitions_config: 场景转换配置文件 (JSON)
            initial_scene: 初始场景名称
            action_log: 可选的操作日志记录器
        """
        super().__init__(action_log=action_log)
        self._scene_dir = Path(scene_dir)
        self._transitions_config = Path(transitions_config)
        self._current_scene: str = initial_scene
        self._screenshot_cache: Optional[Image.Image] = None

        # Mock OCR 结果配置
        self._mock_ocr_results: dict = {}

        # 加载场景转换配置
        self._load_transitions()

        # 加载初始场景
        self.set_scene(initial_scene)

    def _load_transitions(self) -> None:
        """从 JSON 文件加载场景转换配置"""
        if not self._transitions_config.exists():
            raise FileNotFoundError(f"场景转换配置文件不存在: {self._transitions_config}")

        with open(self._transitions_config, "r", encoding="utf-8") as f:
            self._transitions = json.load(f)

    def set_scene(self, scene_name: str) -> None:
        """设置当前场景，加载对应场景图片

        Args:
            scene_name: 场景名称（对应 scene_dir 下的图片文件名，不含扩展名）
        """
        self._current_scene = scene_name

        # 查找场景图片
        scene_path = self._find_scene_image(scene_name)
        if scene_path and scene_path.exists():
            self._screenshot_cache = Image.open(scene_path)
        else:
            # 如果找不到场景图片，创建一个空白图片
            self._screenshot_cache = Image.new("RGB", (1154, 680), color=(0, 0, 0))

    def _find_scene_image(self, scene_name: str) -> Optional[Path]:
        """查找场景图片路径

        Args:
            scene_name: 场景名称

        Returns:
            场景图片路径，如果不存在返回 None
        """
        # 尝试多种扩展名
        for ext in [".png", ".bmp", ".jpg", ".jpeg"]:
            path = self._scene_dir / f"{scene_name}{ext}"
            if path.exists():
                return path
        return None

    def capture_screen(self) -> Image.Image:
        """截取当前游戏画面

        Returns:
            当前场景截图
        """
        if self._screenshot_cache is None:
            raise RuntimeError("场景截图未初始化，请先调用 set_scene")
        return self._screenshot_cache

    def bg_find_pic(self, image_path: str, x0: int = 0, y0: int = 0, x1: int = 0, y1: int = 0, similarity: float = 0.8) -> Tuple[int, int]:
        """查找图片位置（Mock 实现）

        Args:
            image_path: 要查找的图片路径
            x0: 查找区域左上角x坐标
            y0: 查找区域左上角y坐标
            x1: 查找区域右下角x坐标
            y1: 查找区域右下角y坐标
            similarity: 相似度阈值（此 Mock 实现忽略）

        Returns:
            始终返回 (0, 0) 表示找到
        """
        return (0, 0)

    def bg_left_click(self, point: tuple, x_range: int = 20, y_range: int = 20) -> bool:
        """左键点击后进行场景转换

        匹配真实 WinController.mouse.bg_left_click 接口：
        bg_left_click(point, x_range=20, y_range=20) -> bool

        记录点击后，根据当前场景的配置查找场景转换，
        如果找到则切换到对应场景。

        Args:
            point: 点击位置 (x, y)
            x_range: 点击随机范围x轴
            y_range: 点击随机范围y轴

        Returns:
            bool: 是否成功执行转换
        """
        # 记录点击
        self.left_click(point[0], point[1])

        # 查找场景转换
        transitioned = self._transition_to_next_scene()

        return transitioned if transitioned is not None else True

    def find_and_click(self, image_path: str, x0: int = 0, y0: int = 0, x1: int = 99999, y1: int = 99999,
                      similarity: float = 0.8, x_range: int = 20, y_range: int = 20, timeout=None) -> bool:
        """查找图片并点击

        匹配真实 WinController.find_and_click 接口

        Args:
            image_path: 要查找并点击的图片路径
            x0: 查找区域左上角x坐标
            y0: 查找区域左上角y坐标
            x1: 查找区域右下角x坐标
            y1: 查找区域右下角y坐标
            similarity: 相似度阈值
            x_range: 点击随机范围x轴
            y_range: 点击随机范围y轴
            timeout: 超时时间（此 Mock 实现忽略）

        Returns:
            bool: 是否成功找到并点击
        """
        # bg_find_pic 总是返回 (0, 0) 表示找到
        pos = self.bg_find_pic(image_path, x0, y0, x1, y1, similarity)

        if pos != (-1, -1):
            # 执行点击并进行场景转换
            return self.bg_left_click(pos, x_range, y_range)

        return False

    def _transition_to_next_scene(self, image_path: str = None) -> Optional[bool]:
        """根据当前场景的配置转换到下一个场景

        Returns:
            bool: 是否成功转换，None 表示没有配置转换
        """
        # 从配置中查找转换目标
        # JSON 结构: {"scene_name": {"button_image": "next_scene"}, ...}

        if self._current_scene not in self._transitions:
            return None

        scene_transitions = self._transitions[self._current_scene]
        if not scene_transitions:
            return None

        # 遍历当前场景的所有按钮映射
        for button_image, next_scene in scene_transitions.items():
            if next_scene:
                self.set_scene(next_scene)
                logger.debug(f"场景转换: {self._current_scene} -> {next_scene}")
                return True

        # 没有找到有效转换
        logger.warning(f"场景 {self._current_scene} 的转换配置为空或无效")
        return None

    def get_current_scene(self) -> str:
        """获取当前场景名称

        Returns:
            当前场景名称
        """
        return self._current_scene

    # ==================== OCR Mock 支持 ====================

    def set_mock_ocr_result(self, text: str, key: str = "default") -> None:
        """设置 Mock OCR 返回结果

        Args:
            text: 要返回的 OCR 文本
            key: 结果的标识键（用于区分不同位置的 OCR）
        """
        self._mock_ocr_results[key] = text

    def find_all_texts(self, image, similarity_threshold: float = 0.5, **kwargs) -> list:
        """Mock OCR 查找文本

        匹配 YYSBaseScript.ocr.find_all_texts 接口

        Args:
            image: 要识别的图片
            similarity_threshold: 相似度阈值
            **kwargs: 其他参数

        Returns:
            list: Mock OCR 结果列表
        """
        # 返回配置的 OCR 结果
        if "default" in self._mock_ocr_results:
            return [self._mock_ocr_results["default"]]
        return []

    def contains_text(self, image, target_text: str, similarity_threshold: float = 0.5, **kwargs) -> bool:
        """Mock OCR 检查是否包含指定文本

        匹配 YYSBaseScript.ocr.contains_text 接口

        Args:
            image: 要识别的图片
            target_text: 要查找的文本
            similarity_threshold: 相似度阈值
            **kwargs: 其他参数

        Returns:
            bool: 是否包含指定文本
        """
        if "default" in self._mock_ocr_results:
            return target_text in self._mock_ocr_results["default"]
        return False
