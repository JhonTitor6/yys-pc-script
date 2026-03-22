# tests/common/recorders/scene_recorder.py
"""
场景转换录制器 - 自动生成场景转换映射

在真实游戏环境下运行时，Hook find_and_click，
自动记录 (current_scene, button_name, detected_next_scene) 三元组

使用方式：
1. 创建 SceneTransitionRecorder 实例
2. 调用 hook_into(win_controller) 将其挂载到 win_controller
3. 运行脚本
4. 调用 save_transitions() 保存为 JSON
"""

import json
from pathlib import Path
from typing import Optional, Callable


class SceneTransitionRecorder:
    """
    场景转换录制器

    自动记录场景转换映射，用于生成 scene_transitions JSON 配置

    使用示例：
    ```python
    recorder = SceneTransitionRecorder()

    # 挂载到 win_controller
    recorder.hook_into(win_controller)

    # 运行脚本...
    script.run()

    # 保存转换映射
    recorder.save_transitions("scene_transitions.json")
    ```
    """

    def __init__(self):
        self._transitions: dict = {}
        self._current_scene: Optional[str] = None
        self._original_find_and_click: Optional[Callable] = None
        self._original_set_scene: Optional[Callable] = None

    def hook_into(self, win_controller) -> None:
        """
        将录制器挂载到 win_controller

        拦截 find_and_click 和 scene_manager 的 set_scene 方法来记录转换

        Args:
            win_controller: WinController 实例
        """
        self._current_scene = getattr(win_controller, '_current_scene', None) or "初始场景"

        # 保存原始方法
        self._original_find_and_click = win_controller.find_and_click
        self._original_set_scene = getattr(win_controller, 'set_scene', None)

        # 创建包装器
        def wrapped_find_and_click(image_path, **kwargs):
            result = self._original_find_and_click(image_path, **kwargs)
            # 尝试从 win_controller 获取当前场景
            self._current_scene = getattr(win_controller, '_current_scene', self._current_scene)
            return result

        def wrapped_set_scene(scene_name):
            self.record_transition(scene_name)
            if self._original_set_scene:
                return self._original_set_scene(scene_name)

        # 替换方法
        win_controller.find_and_click = wrapped_find_and_click
        if hasattr(win_controller, 'set_scene'):
            win_controller.set_scene = wrapped_set_scene

    def unhook(self, win_controller) -> None:
        """
        从 win_controller 卸载录制器

        Args:
            win_controller: WinController 实例
        """
        if self._original_find_and_click:
            win_controller.find_and_click = self._original_find_and_click
        if self._original_set_scene and hasattr(win_controller, 'set_scene'):
            win_controller.set_scene = self._original_set_scene

    def record_transition(self, next_scene: str, button_name: str = None) -> None:
        """
        记录一次场景转换

        Args:
            next_scene: 下一场景名称
            button_name: 触发的按钮名称（可选）
        """
        if self._current_scene is None:
            return

        if self._current_scene not in self._transitions:
            self._transitions[self._current_scene] = {}

        # 如果没有指定按钮名称，使用占位符
        if button_name is None:
            button_name = "unknown_button"

        # 记录转换
        self._transitions[self._current_scene][button_name] = next_scene

    def set_current_scene(self, scene_name: str) -> None:
        """
        手动设置当前场景名称

        Args:
            scene_name: 场景名称
        """
        self._current_scene = scene_name

    def save_transitions(self, output_path: str) -> None:
        """
        保存转换映射到文件

        Args:
            output_path: 输出文件路径
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self._transitions, f, ensure_ascii=False, indent=2)

    def load_transitions(self, input_path: str) -> None:
        """
        从文件加载转换映射

        Args:
            input_path: 输入文件路径
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            self._transitions = json.load(f)

    def get_transitions(self) -> dict:
        """
        获取当前所有转换映射

        Returns:
            dict: 转换映射字典
        """
        return self._transitions

    def clear(self) -> None:
        """清空所有记录的转换"""
        self._transitions.clear()
        self._current_scene = None
