import os
import re
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Set, TYPE_CHECKING, overload, Any

from loguru import logger

from win_util.image import to_project_path

if TYPE_CHECKING:
    from win_util.controller import WinController


class SceneGraphValidationError(Exception):
    """场景图完整性校验失败。

    在场景注册/建图阶段抛出，携带可定位信息（触发边的按钮文件路径等），
    确保幽灵节点在启动前被发现而不是在运行期静默失败。

    Args:
        message: 人类可读的错误描述。
        button_path: 触发校验失败的跳转按钮图片路径（可定位证据）。
    """

    def __init__(self, message: str, button_path: str = ""):
        super().__init__(message)
        self.message = message
        self.button_path = button_path


class SceneDetectionResult:
    """场景检测结果"""
    
    def __init__(self, scene_name: str, matched_image: str, position: Tuple[int, int], similarity: float = 0.0):
        """
        初始化场景检测结果
        
        Args:
            scene_name: 检测到的场景名称（已归一化的规范名）
            matched_image: 匹配成功的图像路径
            position: 匹配位置（中心点）
            similarity: 匹配相似度（默认 0.0，兼容旧调用）
        """
        self.scene_name = scene_name
        self.matched_image = matched_image
        self.position = position
        self.similarity = similarity
    
    def __str__(self):
        return f"SceneDetectionResult(scene={self.scene_name})"
    
    def __repr__(self):
        return self.__str__()


class SceneManager:
    """
    场景管理器 - 实现场景检测、路径规划和跳转功能

    支持两种注册方式：
    1. 编程式注册：使用 register_scene()、register_transition() 等方法
    2. 目录注册：使用 register_scenes_from_directory() 从指定目录加载场景和跳转

    各业务模块通过 register_scenes_from_directory() 注册自己独有的场景和跳转，
    全局场景（如 home、exploration 等）由 YYSBaseScript 在初始化时统一注册。
    """

    def __init__(self, hwnd: int, win_controller: 'WinController'):
        """
        初始化场景管理器

        Args:
            hwnd: 游戏窗口句柄
            win_controller: Windows 控制器
        """
        self.hwnd = hwnd
        self.win_controller = win_controller

        self.current_scene: Optional[str] = None

        # 场景图存储：{source_scene: {dest_scene: button_image_path}}
        self.scene_graph: Dict[str, Dict[str, str]] = defaultdict(dict)

        # 场景图像映射：{scene_name: [image_paths]}
        self.scene_images: Dict[str, List[str]] = {}

        # 场景跳转按钮映射：{(source, dest): button_image_path}
        self.scene_transitions: Dict[Tuple[str, str], str] = {}
        # 通用跳转按钮：{dest_scene: button_path}
        self.global_transitions: Dict[str, str] = {}

    # 旧文件名 → 规范场景名的显式别名表（产品契约：PRD R1）。
    # 文件名推导出的旧节点名只能通过本表归一化，业务脚本不得自行猜测。
    SCENE_ALIASES: Dict[str, str] = {
        "battle": "battling",
        "chapter_28": "exploration_chapter_28",
        "soul": "soul_selection",
    }

    # 显式声明的外部目标节点：图中允许存在但没有识别图片的跳转目标。
    # 它们由真实资产（scene_control 按钮）推导，当前无对应场景模板；
    # 未声明在此集合中的未知节点会在建图校验时抛出可定位错误。
    EXTERNAL_SCENE_TARGETS: frozenset = frozenset({
        "awakening_materials",
        "regional_demon_boss",
        "spirit_guardian",
    })

    def normalize_scene_name(self, name: str) -> str:
        """将旧场景名归一化为规范名（应用显式别名表）。

        实例方法以便测试通过实例属性覆盖别名表；默认表在类级声明。

        Args:
            name: 原始场景名（来自文件名或调用方）。

        Returns:
            规范场景名；无别名时原样返回。

        Raises:
            SceneGraphValidationError: 别名表存在循环时抛出，避免无限迭代。
        """
        seen: Set[str] = set()
        current = name
        while current in self.SCENE_ALIASES:
            if current in seen:
                chain = " -> ".join(list(seen) + [current])
                raise SceneGraphValidationError(
                    f"场景别名循环: {chain}"
                )
            seen.add(current)
            current = self.SCENE_ALIASES[current]
        return current

    def register_scene(self, name: str, image_paths: List[str]):
        """
        注册场景及其图片（场景名经别名归一化）

        Args:
            name: 场景名称（旧名会被归一化为规范名）
            image_paths: 场景图片路径列表（支持多张图片用于同一场景）
        """
        name = self.normalize_scene_name(name)
        if name not in self.scene_images:
            self.scene_images[name] = []
        self.scene_images[name].extend(image_paths)
        logger.debug(f"注册场景: {name}, 图片: {image_paths}")

    def register_transition(self, from_scene: str, to_scene: str, button_path: str):
        """
        注册场景跳转（端点经别名归一化）

        Args:
            from_scene: 源场景
            to_scene: 目标场景
            button_path: 跳转按钮图片路径
        """
        from_scene = self.normalize_scene_name(from_scene)
        to_scene = self.normalize_scene_name(to_scene)
        self.scene_transitions[(from_scene, to_scene)] = button_path
        self.scene_graph[from_scene][to_scene] = button_path
        logger.debug(f"注册跳转: {from_scene} -> {to_scene}, 按钮: {button_path}")

    def register_global_transition(self, to_scene: str, button_path: str):
        """
        注册通用跳转按钮（从任意场景都可跳转到目标场景，目标名经别名归一化）

        Args:
            to_scene: 目标场景
            button_path: 跳转按钮图片路径
        """
        to_scene = self.normalize_scene_name(to_scene)
        self.global_transitions[to_scene] = button_path
        # 为所有已注册的场景添加通用跳转
        for scene in self.scene_images.keys():
            if to_scene not in self.scene_graph[scene]:
                self.scene_graph[scene][to_scene] = button_path
        logger.debug(f"注册通用跳转: * -> {to_scene}, 按钮: {button_path}")

    def register_scenes_from_directory(self, scene_dir: str, control_dir: str) -> None:
        """
        从指定目录注册场景和跳转

        扫描 scene_dir 下的图片文件，文件名（不含后缀）作为场景名注册。
        扫描 control_dir 下的图片文件，按命名规则解析跳转关系：
          - source_to_dest.bmp：从 source 场景跳转到 dest 场景
          - to_dest.bmp：从任意场景跳转到 dest 场景（通用跳转）

        Args:
            scene_dir: 场景图片目录路径
            control_dir: 场景跳转按钮图片目录路径
        """
        # 注册场景图片
        if os.path.exists(scene_dir):
            for filename in os.listdir(scene_dir):
                if filename.lower().endswith(('.bmp', '.png', '.jpg', '.jpeg')) and filename != "scene_control":
                    scene_name = self.normalize_scene_name(os.path.splitext(filename)[0])
                    image_path = os.path.join(scene_dir, filename)

                    if scene_name not in self.scene_images:
                        self.scene_images[scene_name] = []
                    self.scene_images[scene_name].append(image_path)
                    logger.debug(f"注册场景: {scene_name}, 图片: {image_path}")

        # 注册场景跳转
        if os.path.exists(control_dir):
            for filename in os.listdir(control_dir):
                if not filename.lower().endswith(('.bmp', '.png', '.jpg', '.jpeg')):
                    continue

                button_path = os.path.join(control_dir, filename)

                # source_to_dest 格式
                match = re.match(r'(.+)_to_(.+)\.(bmp|png|jpg|jpeg)', filename)
                if match:
                    source_scene = self.normalize_scene_name(match.group(1))
                    dest_scene = self.normalize_scene_name(match.group(2))
                    self.scene_transitions[(source_scene, dest_scene)] = button_path
                    logger.debug(f"注册场景跳转: {source_scene} -> {dest_scene}")
                    continue

                # to_dest 格式（通用跳转）
                match = re.match(r'to_(.+)\.(bmp|png|jpg|jpeg)', filename)
                if match:
                    dest_scene = self.normalize_scene_name(match.group(1))
                    self.global_transitions[dest_scene] = button_path
                    logger.debug(f"注册通用跳转: * -> {dest_scene}")

        # 重建场景图
        self._build_scene_graph()

    def _build_scene_graph(self):
        """构建场景有向图"""

        # 1. 先构建显式跳转
        for (source, dest), button_path in self.scene_transitions.items():
            self.scene_graph[source][dest] = button_path

        # 2. 展开通用跳转（to_xxx）
        for dest_scene, button_path in self.global_transitions.items():
            for source_scene in self.scene_images.keys():
                # 若已有显式跳转，则跳过
                if dest_scene in self.scene_graph[source_scene]:
                    continue
                self.scene_graph[source_scene][dest_scene] = button_path

        logger.info(f"场景图构建完成，共发现 {len(self.scene_graph)} 个场景节点")
        for source, destinations in self.scene_graph.items():
            logger.debug(f"  {source} -> {list(destinations.keys())}")

        # 图完整性校验：幽灵节点必须在启动前暴露（产品契约：PRD AC1）
        self._validate_scene_graph()

    def _validate_scene_graph(self) -> None:
        """校验场景图完整性：所有边端点必须已注册或是显式外部目标。

        Raises:
            SceneGraphValidationError: 存在未注册源/目标节点时抛出，
                错误信息包含触发边的按钮文件路径以便定位。
        """
        known_scenes = set(self.scene_images.keys())

        for (source, dest), button_path in self.scene_transitions.items():
            if source not in known_scenes:
                raise SceneGraphValidationError(
                    f"跳转边源场景未注册: {source!r}（按钮: {button_path}）",
                    button_path=button_path,
                )
            if dest not in known_scenes and dest not in self.EXTERNAL_SCENE_TARGETS:
                raise SceneGraphValidationError(
                    f"跳转边目标场景未注册且未声明外部目标: {dest!r}（按钮: {button_path}）",
                    button_path=button_path,
                )

        for dest, button_path in self.global_transitions.items():
            if dest not in known_scenes and dest not in self.EXTERNAL_SCENE_TARGETS:
                raise SceneGraphValidationError(
                    f"通用跳转目标未注册且未声明外部目标: {dest!r}（按钮: {button_path}）",
                    button_path=button_path,
                )

    @overload
    def detect_current_scene(self) -> Optional[SceneDetectionResult]:
        """检测当前屏幕所处的场景（使用缓存截图）"""
        ...

    @overload
    def detect_current_scene(self, screenshot) -> Optional[SceneDetectionResult]:
        """检测给定截图所处的场景"""
        ...

    # 最后的实现部分
    def detect_current_scene(self, screenshot: Optional[Any] = None) -> Optional[SceneDetectionResult]:
        # 如果没有传入 screenshot，则使用缓存
        big_img = screenshot if screenshot is not None else self.win_controller.image_finder.screenshot_cache

        # 遍历所有场景及其对应的图像
        for scene_name, image_paths in self.scene_images.items():
            for image_path in image_paths:
                # 注意这里使用的是处理后的 big_img
                pos = self.win_controller.bg_find_pic(big_img, image_path)

                if pos != (-1, -1):
                    self.current_scene = scene_name
                    return SceneDetectionResult(
                        scene_name=scene_name,
                        matched_image=image_path,
                        position=pos
                    )
        return None

    def detect_scene_candidates(self, screenshot: Optional[Any] = None) -> List[SceneDetectionResult]:
        """收集所有场景图片的最佳候选证据，按相似度降序返回（只读，不发送输入）。

        Args:
            screenshot: 待检测截图；为 None 时使用缓存截图。

        Returns:
            全部场景模板的候选识别结果列表（含阈值以下的最佳候选，
            similarity 即 ImageFinder.best_match 返回的相似度），按相似度降序。
        """
        big_img = screenshot if screenshot is not None else self.win_controller.image_finder.screenshot_cache

        results: List[SceneDetectionResult] = []
        for scene_name, image_paths in self.scene_images.items():
            for image_path in image_paths:
                match = self.win_controller.image_finder.best_match(big_img, image_path)
                if match is not None and match.is_found:
                    results.append(SceneDetectionResult(
                        scene_name=scene_name,
                        matched_image=image_path,
                        position=match.point,
                        similarity=match.similarity,
                    ))
        results.sort(key=lambda r: r.similarity, reverse=True)
        return results
    
    def is_reachable(self, source_scene: str, target_scene: str) -> bool:
        """
        检查两个场景是否可达
        
        Args:
            source_scene: 源场景
            target_scene: 目标场景
            
        Returns:
            是否可达
        """
        if source_scene == target_scene:
            return True
        
        # 使用BFS检查可达性
        visited = set()
        queue = deque([source_scene])
        visited.add(source_scene)
        
        while queue:
            current = queue.popleft()
            
            if current == target_scene:
                return True
            
            for neighbor in self.scene_graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        return False
    
    def get_shortest_path(self, source_scene: str, target_scene: str) -> Optional[List[Tuple[str, str, str]]]:
        """
        使用BFS计算从源场景到目标场景的最短路径
        
        Args:
            source_scene: 源场景
            target_scene: 目标场景
            
        Returns:
            路径列表，每个元素为 (from_scene, to_scene, button_path) 元组，如果不可达则返回None
        """
        if source_scene == target_scene:
            return []  # 已在目标场景
        
        if not self.is_reachable(source_scene, target_scene):
            logger.error(f"无法从 {source_scene} 到达 {target_scene}")
            return None
        
        # BFS寻找最短路径
        queue = deque([(source_scene, [])])  # (current_scene, path_to_here)
        visited = {source_scene}
        
        while queue:
            current_scene, path = queue.popleft()
            
            if current_scene == target_scene:
                return path
            
            for next_scene, button_path in self.scene_graph[current_scene].items():
                if next_scene not in visited:
                    visited.add(next_scene)
                    new_path = path + [(current_scene, next_scene, button_path)]
                    queue.append((next_scene, new_path))
        
        return None  # 不应到达此行，因为前面已检查可达性
    
    def goto_scene(self, target_scene: str, timeout: int = 30) -> bool:
        """
        跳转到目标场景
        
        Args:
            target_scene: 目标场景名称
            timeout: 整个跳转过程的超时时间（秒）
            
        Returns:
            是否成功跳转
        """
        logger.info(f"开始跳转到场景: {target_scene}")
        
        # 获取当前场景
        current_detection = self.detect_current_scene()
        if not current_detection:
            logger.error("无法检测当前场景，无法执行跳转")
            return False
        
        current_scene = current_detection.scene_name
        logger.info(f"当前场景: {current_scene}")
        
        if current_scene == target_scene:
            logger.info(f"已在目标场景 {target_scene}")
            return True
        
        # 计算最短路径
        path = self.get_shortest_path(current_scene, target_scene)
        if not path:
            logger.error(f"无法找到从 {current_scene} 到 {target_scene} 的路径")
            return False
        
        logger.info(f"找到跳转路径: {' -> '.join([current_scene] + [step[1] for step in path])}")
        
        start_time = time.time()
        
        # 按路径顺序执行跳转
        for from_scene, to_scene, button_path in path:
            if time.time() - start_time > timeout:
                logger.error("跳转超时")
                return False
            
            logger.info(f"执行跳转: {from_scene} -> {to_scene}")
            
            # 查找跳转按钮并点击
            button_pos = self.win_controller.bg_find_pic_by_cache(button_path)
            if button_pos == (-1, -1):
                logger.error(f"未找到跳转按钮: {button_path}")
                return False
            
            # 点击跳转按钮
            self.win_controller.mouse.bg_left_click_with_range(
                button_pos,
                x_range=5,
                y_range=5,
            )

            # 等待场景切换完成（可适当延时等待动画）
            time.sleep(3.0)

            # 点击后刷新截图缓存，确保检测使用的是最新截图
            self.win_controller.update_screenshot_cache()

            # 重新检测当前场景以确认跳转成功
            new_detection = self.detect_current_scene()
            if not new_detection or new_detection.scene_name != to_scene:
                logger.warning(f"跳转到 {to_scene} 可能失败，当前场景为 {new_detection.scene_name if new_detection else '未知'}")
                # 可以选择重试或继续等待
                time.sleep(1.0)
                new_detection = self.detect_current_scene()
            
            if not new_detection or new_detection.scene_name != to_scene:
                logger.error(f"未能成功跳转到 {to_scene}")
                return False
        
        # 最终确认已到达目标场景
        final_detection = self.detect_current_scene()
        if final_detection and final_detection.scene_name == target_scene:
            logger.success(f"成功跳转到场景: {target_scene}")
            return True
        else:
            logger.error(f"跳转完成后场景检测异常，期望: {target_scene}，实际: {final_detection.scene_name if final_detection else '未知'}")
            return False

    def click_return(self):
        """点击返回按钮"""
        button_pos = self.win_controller.bg_find_pic_by_cache(to_project_path("yys/common/images/scene_control/return.bmp"))
        if button_pos == (-1, -1):
            logger.error("未找到返回按钮")
            return False

        self.win_controller.mouse.bg_left_click_with_range(
            button_pos,
            x_range=5,
            y_range=5,
        )
        return True
    
    def get_available_scenes(self) -> Set[str]:
        """获取所有可用的场景名称"""
        return set(self.scene_images.keys())
    
    def get_scene_connections(self, scene: str) -> Dict[str, str]:
        """获取指定场景的所有连接（可跳转到的场景及按钮路径）"""
        return dict(self.scene_graph.get(scene, {}))
