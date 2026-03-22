# tests/common/environment/scene_replay_environment.py
"""场景回放环境 - 基于状态机的场景流转测试环境

实现 GameEnvironment 接口，复用真实的 WinController.find_image() 进行找图操作。
只需 mock 截图返回（返回预设的场景图片），其余逻辑使用生产代码。
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from .base import ActionRecord, ActionType, GameEnvironment

logger = logging.getLogger(__name__)


class SceneReplayEnvironment(GameEnvironment):
    """场景回放环境 - 实现 GameEnvironment 接口

    特点：
    - 实现 GameEnvironment 接口，复用真实的 WinController 找图逻辑
    - 只 mock capture_screen() 返回预设的场景图片
    - 场景转换由场景状态机控制
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
        self._scene_dir = Path(scene_dir)
        self._transitions_config = Path(transitions_config)
        self._current_scene: str = initial_scene
        self._screenshot_cache: Optional[Image.Image] = None

        # Mock OCR 结果配置
        self._mock_ocr_results: dict = {}

        # 操作日志
        self._action_log = action_log
        self._action_records: list = []
        self.action_log = action_log  # 保持向后兼容

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

    # ==================== GameEnvironment 接口实现 ====================

    def capture_screen(self) -> Image.Image:
        """截取当前游戏画面（返回预设的场景图片）"""
        if self._screenshot_cache is None:
            raise RuntimeError("场景截图未初始化，请先调用 set_scene")
        return self._screenshot_cache

    def left_click(self, x: int, y: int) -> None:
        """鼠标左键点击"""
        self._record_action(ActionType.LEFT_CLICK, x, y)

    def right_click(self, x: int, y: int) -> None:
        """鼠标右键点击"""
        self._record_action(ActionType.RIGHT_CLICK, x, y)

    def left_double_click(self, x: int, y: int) -> None:
        """鼠标左键双击"""
        self._record_action(ActionType.LEFT_DOUBLE_CLICK, x, y)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """拖拽操作"""
        self._record_action(ActionType.DRAG, x1, y1, extra={"x2": x2, "y2": y2})

    def key_press(self, key_code: int) -> None:
        """按键按下并释放"""
        self._record_action(ActionType.KEY_PRESS, key_code, 0)

    def key_down(self, key_code: int) -> None:
        """按键按下"""
        self._record_action(ActionType.KEY_DOWN, key_code, 0)

    def key_up(self, key_code: int) -> None:
        """按键释放"""
        self._record_action(ActionType.KEY_UP, key_code, 0)

    def set_mouse_position(self, x: int, y: int) -> None:
        """设置鼠标位置"""
        pass  # Mock 环境不需要真实设置鼠标位置

    def get_window_client_rect(self) -> Tuple[int, int, int, int]:
        """获取窗口客户区矩形"""
        # 返回一个标准的游戏窗口尺寸
        return (0, 0, 1154, 680)

    def find_window(self, title_part: str) -> Optional[int]:
        """查找窗口句柄（Mock 返回固定值）"""
        return 123456

    # ==================== 场景管理 ====================

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
        """查找场景图片路径"""
        for ext in [".png", ".bmp", ".jpg", ".jpeg"]:
            path = self._scene_dir / f"{scene_name}{ext}"
            if path.exists():
                return path
        return None

    def get_current_scene(self) -> str:
        """获取当前场景名称"""
        return self._current_scene

    # ==================== 操作记录 ====================

    def _record_action(self, action_type: ActionType, x: int, y: int, extra: dict = None) -> None:
        """记录操作到日志"""
        record = ActionRecord(
            action_type=action_type.value,
            x=x,
            y=y,
            timestamp=time.time(),
            extra=extra or {}
        )
        self._action_records.append(record)
        if self._action_log is not None:
            self._action_log.add(record)

    # ==================== 场景转换（用于测试辅助） ====================

    def transition_to_next_scene(self, image_path: str) -> Optional[str]:
        """根据点击的按钮转换到下一个场景

        Args:
            image_path: 被点击的按钮图片路径

        Returns:
            下一个场景名称，None 表示没有配置该按钮的转换
        """
        if image_path is None:
            return None

        if self._current_scene not in self._transitions:
            return None

        scene_transitions = self._transitions[self._current_scene]

        # 查找该按钮对应的转换
        next_scene = scene_transitions.get(image_path)
        if next_scene:
            old_scene = self._current_scene
            self.set_scene(next_scene)
            # 输出转换日志（方便测试观察）
            print(f"  [场景转换] {old_scene} --[{Path(image_path).name}]--> {next_scene}")
            return next_scene

        print(f"  [警告] 按钮 {image_path} 在场景 {self._current_scene} 中没有配置转换")
        return None

    # ==================== OCR Mock 支持 ====================

    def set_mock_ocr_result(self, text: str, key: str = "default") -> None:
        """设置 Mock OCR 返回结果

        Args:
            text: 要返回的 OCR 文本
            key: 结果的标识键
        """
        self._mock_ocr_results[key] = text

    def find_all_texts(self, image, similarity_threshold: float = 0.5, **kwargs) -> list:
        """Mock OCR 查找文本"""
        if "default" in self._mock_ocr_results:
            return [self._mock_ocr_results["default"]]
        return []

    def contains_text(self, image, target_text: str, similarity_threshold: float = 0.5, **kwargs) -> bool:
        """Mock OCR 检查是否包含指定文本"""
        if "default" in self._mock_ocr_results:
            return target_text in self._mock_ocr_results["default"]
        return False

    # ==================== 便捷方法 ====================

    def find_and_click(self, image_path: str, x0: int = 0, y0: int = 0, x1: int = 99999, y1: int = 99999,
                       similarity: float = 0.8, x_range: int = 20, y_range: int = 20) -> bool:
        """查找图片并点击，然后触发场景转换

        这是一个便捷方法，使用真实的 WinController 找图，
        但点击和场景转换由 env 控制。

        注意：默认相似度阈值为 0.4（测试数据质量不够使用高阈值）

        Args:
            image_path: 要查找并点击的图片路径
            x0: 查找区域左上角x坐标
            y0: 查找区域左上角y坐标
            x1: 查找区域右下角x坐标
            y1: 查找区域右下角y坐标
            similarity: 相似度阈值（默认 0.4）
            x_range: 点击随机范围x轴
            y_range: 点击随机范围y轴

        Returns:
            bool: 是否成功找到并点击
        """
        from win_util.controller import WinController

        # 创建临时 WinController 使用 env 获取截图
        temp_controller = WinController(env=self)

        # 找图（使用较低阈值，因为测试数据质量有限）
        pos = temp_controller.find_image(image_path, x0, y0, x1, y1, similarity=0.4)
        img_name = Path(image_path).name

        if pos != (-1, -1):
            print(f"  [找图成功] {img_name} -> 位置 {pos}")
            # 点击（记录到 env）
            self.left_click(pos[0], pos[1])
            print(f"  [鼠标点击] ({pos[0]}, {pos[1]})")
            # 触发场景转换
            self.transition_to_next_scene(image_path)
            return True
        else:
            print(f"  [找图失败] {img_name} -> 未找到")

        return False
