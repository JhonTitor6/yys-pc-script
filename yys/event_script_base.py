# 添加项目根目录到路径，以便导入根目录下的模块
import os
import sys
import time

from scene_manager import SceneManager, SceneDetectionResult
from win_util.event import EventBaseScript, Event
from win_util.image import ImageFinder
from win_util.image import ImageMatchConfig
from win_util.keyboard import KeyboardController
from win_util.mouse import bg_left_click_with_range, MouseController
from yys.common_util import find_window, random_sleep

# 获取项目根目录并添加到 sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from yys.log_manager import get_logger
except ImportError:
    # 如果直接导入失败，尝试添加到路径后再导入
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from yys.log_manager import get_logger

SCENE_DETECTED_EVENT = Event('scene_detected')
"""
事件驱动
"""

SCENE_DETECTED_EVENT = Event('scene_detected')
"""
事件驱动
"""


class YYSBaseScript(EventBaseScript):
    def __init__(self, script_name):
        # 使用统一的日志管理器
        self.logger = get_logger(script_name)
        self.logger.info(f"初始化{script_name}脚本")
        super().__init__()
        self.script_name = script_name
        self.script_start_time_mills = int(time.time() * 1000)
        self._cur_battle_count = 0
        self._cur_battle_victory_count = 0
        self._max_battle_count = 203
        self.accept_wq_type = 0  # 接收悬赏封印类型：0-拒绝，1-全部接受，TODO：2-只接收勾协

        self.mouse = MouseController(self.hwnd)
        self.keyboard = KeyboardController(self.hwnd)
        self.logger.info("初始化图片匹配中...")
        self.image_finder: ImageFinder = ImageFinder(self.hwnd)
        self.logger.info("初始化图片匹配完成")

        # 初始化场景管理器
        self.logger.info("初始化场景管理器中...")
        self.scene_manager: SceneManager = SceneManager(self.hwnd, self.image_finder)
        self.logger.info("初始化场景管理器完成")

        # self._event_manager.register_event_handler(SCENE_DETECTED_EVENT, self.on_scene_detected)

        self._register_image_match_event(ImageMatchConfig(["images/battle_end_success.bmp", "images/battle_end.bmp"]),
                                         self._on_zhan_dou_wan_cheng_victory)
        self._register_image_match_event(ImageMatchConfig(["images/battle_end_loss.bmp"]), self._on_zhan_dou_wan_cheng)
        self._register_image_match_event(ImageMatchConfig(["images/battle_end_1.bmp", "images/battle_end_2.bmp"]),
                                         self._on_zhan_dou_wan_cheng)
        # self._register_image_match_event(ImageMatchConfig("images/xuanshangfengyin_reject.bmp"), self.bg_left_click)
        # 注册ocr事件
        self._register_ocr_match_event("悬赏封印", self._on_wanted_quests_invited)
        self._register_ocr_match_event("点击屏幕继续", self._on_ocr_click_screen_continue)

    def _find_window(self) -> int:
        return find_window()

    def _on_zhan_dou_wan_cheng_victory(self, point):
        self.bg_left_click(point)
        self._cur_battle_victory_count += 1

    def _on_zhan_dou_wan_cheng(self, point):
        # 不可去掉。如果不等一会，没点掉导致触发多次的话，会多次触发_cur_battle_count+=1
        time.sleep(2)
        point = (1000, 400)
        bg_left_click_with_range(self.hwnd, point, x_range=30, y_range=50)
        self._cur_battle_count += 1
        self.log_battle_count()
        time.sleep(0.5)

    def log_battle_count(self):
        self.logger.success(
            f"战斗完成，已战斗{self._cur_battle_count}/{self._max_battle_count}次，胜利{self._cur_battle_victory_count}次")

    def _on_ocr_click_screen_continue(self, ocr_result):
        self.logger.debug(ocr_result)
        self.bg_left_click((567, 460))

    def set_max_battle_count(self, max_battle_count: int):
        self._max_battle_count = max_battle_count
        return self

    def on_run(self):
        self.logger.info(f"开始运行{self.script_name}脚本")
        self.script_start_time_mills = int(time.time() * 1000)
        self._cur_battle_victory_count = 0
        self._cur_battle_count = 0

    def before_iteration(self):
        pass
        # res = self.scene_manager.detect_current_scene()
        # if res:
        #     self._event_manager.trigger_event(SCENE_DETECTED_EVENT, res)

    def after_iteration(self):
        random_sleep(0.05, 0.1)
        if self._cur_battle_count >= self._max_battle_count:
            self.stop()

    def on_scene_detected(self, detection_result: SceneDetectionResult):
        pass


    def _on_wanted_quests_invited(self, point):
        match self.accept_wq_type:
            case 0:
                point = self.image_finder.bg_find_pic_by_cache("images/xuanshangfengyin_reject.bmp")
                self.bg_left_click(point)
            case 1:
                point = self.image_finder.bg_find_pic_by_cache("images/xuanshangfengyin_accept.bmp")
                self.bg_left_click(point)

