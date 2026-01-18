import os
import re
import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Set, overload, Any

from loguru import logger

from win_util.image import ImageFinder


class SceneDetectionResult:
    """场景检测结果"""
    
    def __init__(self, scene_name: str, matched_image: str, position: Tuple[int, int]):
        """
        初始化场景检测结果
        
        Args:
            scene_name: 检测到的场景名称
            matched_image: 匹配成功的图像路径
        """
        self.scene_name = scene_name
        self.matched_image = matched_image
        self.position = position
    
    def __str__(self):
        return f"SceneDetectionResult(scene={self.scene_name})"
    
    def __repr__(self):
        return self.__str__()


class SceneManager:
    """场景管理器 - 实现场景检测、路径规划和跳转功能"""
    
    def __init__(self, hwnd: int, image_finder: ImageFinder):
        """
        初始化场景管理器
        
        Args:
            hwnd: 游戏窗口句柄
        """
        self.hwnd = hwnd
        self.image_finder = image_finder

        # TODO: 将具体scene编写到代码枚举
        self.current_scene = None
        
        # 场景图存储：{source_scene: {dest_scene: button_image_path}}
        self.scene_graph: Dict[str, Dict[str, str]] = defaultdict(dict)
        
        # 场景图像映射：{scene_name: [image_paths]}
        self.scene_images: Dict[str, List[str]] = {}
        
        # 场景跳转按钮映射：{(source, dest): button_image_path}
        self.scene_transitions: Dict[Tuple[str, str], str] = {}
        # 通用跳转按钮：{dest_scene: button_path}
        self.global_transitions: Dict[str, str] = {}
        
        # 加载场景资源
        self._load_scenes()
        self._build_scene_graph()
    
    def _load_scenes(self):
        """加载所有场景图片和跳转按钮"""
        # 构建场景图片映射
        scene_dir = "images/scene/"
        control_dir = "images/scene/scene_control/"
        
        # 检查并创建目录
        os.makedirs(scene_dir, exist_ok=True)
        os.makedirs(control_dir, exist_ok=True)
        
        # 遍历场景目录下的图片文件
        if os.path.exists(scene_dir):
            for filename in os.listdir(scene_dir):
                if filename.lower().endswith(('.bmp', '.png', '.jpg', '.jpeg')) and filename != "scene_control":
                    # 提取场景名（文件名，不含后缀）
                    scene_name = os.path.splitext(filename)[0]
                    image_path = os.path.join(scene_dir, filename)
                    
                    if scene_name not in self.scene_images:
                        self.scene_images[scene_name] = []
                    self.scene_images[scene_name].append(image_path)

        # 构建场景跳转映射
        if os.path.exists(control_dir):
            for filename in os.listdir(control_dir):
                if not filename.lower().endswith(('.bmp', '.png', '.jpg', '.jpeg')):
                    continue

                button_path = os.path.join(control_dir, filename)

                # 1. source_to_dest
                match = re.match(r'(.+)_to_(.+)\.(bmp|png|jpg|jpeg)', filename)
                if match:
                    source_scene = match.group(1)
                    dest_scene = match.group(2)
                    self.scene_transitions[(source_scene, dest_scene)] = button_path
                    logger.debug(f"发现场景跳转: {source_scene} -> {dest_scene}")
                    continue

                # 2. to_dest（通用跳转）
                match = re.match(r'to_(.+)\.(bmp|png|jpg|jpeg)', filename)
                if match:
                    dest_scene = match.group(1)
                    self.global_transitions[dest_scene] = button_path
                    logger.debug(f"发现通用跳转: * -> {dest_scene}")

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
                # TODO: source -> dest 支持多条路径
                self.scene_graph[source_scene][dest_scene] = button_path

        logger.info(f"场景图构建完成，共发现 {len(self.scene_graph)} 个场景节点")
        for source, destinations in self.scene_graph.items():
            logger.debug(f"  {source} -> {list(destinations.keys())}")

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
        big_img = screenshot if screenshot is not None else self.image_finder.screenshot_cache

        # 遍历所有场景及其对应的图像
        for scene_name, image_paths in self.scene_images.items():
            for image_path in image_paths:
                # 注意这里使用的是处理后的 big_img
                pos = self.image_finder.bg_find_pic(big_img, image_path)

                if pos != (-1, -1):
                    self.current_scene = scene_name
                    return SceneDetectionResult(
                        scene_name=scene_name,
                        matched_image=image_path,
                        position=pos
                    )
        return None
    
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
            button_pos = self.image_finder.bg_find_pic_by_cache(button_path)
            if button_pos == (-1, -1):
                logger.error(f"未找到跳转按钮: {button_path}")
                return False
            
            # 点击跳转按钮
            from .mouse import bg_left_click_with_range
            bg_left_click_with_range(self.hwnd, button_pos, x_range=5, y_range=5)
            
            # 等待场景切换完成（可适当延时等待动画）
            time.sleep(1.0)
            
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
    
    def get_available_scenes(self) -> Set[str]:
        """获取所有可用的场景名称"""
        return set(self.scene_images.keys())
    
    def get_scene_connections(self, scene: str) -> Dict[str, str]:
        """获取指定场景的所有连接（可跳转到的场景及按钮路径）"""
        return dict(self.scene_graph.get(scene, {}))