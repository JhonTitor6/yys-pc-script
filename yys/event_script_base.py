# 添加项目根目录到路径，以便导入根目录下的模块
import os
import sys
import time
import random
from enum import IntEnum

import win32con
import win32gui
from loguru import logger

from win_util import WinController
from win_util.event import EventBaseScript, Event
from win_util.image import ImageMatchConfig, ImageFinder
from win_util.mouse import bg_left_click_with_range
from win_util.ocr import CommonOcr
from yys.scene_manager import SceneManager, SceneDetectionResult

# 获取项目根目录并添加到 sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from yys.log_manager import get_logger
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from yys.log_manager import get_logger


# ==================== 常量定义 ====================

class WantedQuestAcceptType(IntEnum):
    """悬赏封印接受类型"""
    REFUSE = 0      # 拒绝
    ACCEPT_ALL = 1  # 全部接受
    ACCEPT_GOUGU = 2  # 只接勾协


# 战斗相关常量
BATTLE_SLEEP_SHORT = 0.5      # 短等待
BATTLE_SLEEP_MEDIUM = 1.0     # 中等等待
BATTLE_SLEEP_LONG = 2.0       # 长等待
BATTLE_VICTORY_SLEEP = 1.0    # 胜利后等待
BATTLE_END_SLEEP = 2.0        # 战斗结束等待
BATTLE_END_CLICK_SLEEP = 0.5  # 点击后等待

# 点击偏移范围
DEFAULT_CLICK_RANGE = 20      # 默认点击偏移
BATTLE_END_CLICK_RANGE_X = 30 # 战斗结束点击X偏移
BATTLE_END_CLICK_RANGE_Y = 50 # 战斗结束点击Y偏移
OCR_CLICK_RANGE = 10           # OCR点击偏移

# 战斗结束图片
BATTLE_END_SUCCESS_IMAGES = ["yys/images/battle_end_success.bmp", "yys/images/battle_end.bmp"]
BATTLE_END_LOSS_IMAGES = ["yys/images/battle_end_loss.bmp"]
BATTLE_END_OTHER_IMAGES = ["yys/images/battle_end_1.bmp", "yys/images/battle_end_2.bmp"]
WANTED_QUEST_REJECT_IMAGE = "yys/images/xuanshangfengyin_reject.bmp"
WANTED_QUEST_ACCEPT_IMAGE = "yys/images/xuanshangfengyin_accept.bmp"

# OCR 点击屏幕继续
OCR_CLICK_SCREEN_CONTINUE = "点击屏幕继续"


# ==================== 工具函数 ====================

def find_window(title_part: str = "阴阳师-网易游戏") -> int:
    """查找游戏窗口"""
    hwnd = win32gui.FindWindow(None, title_part)
    if not hwnd:
        logger.error("未找到游戏窗口")
        raise Exception("未找到游戏窗口")

    # 设置窗口大小
    win32gui.SetWindowPos(hwnd, None, 0, 0, 1154, 680, win32con.SWP_NOMOVE)

    # 获取客户区大小
    _, _, width, height = win32gui.GetClientRect(hwnd)

    logger.info(f"窗口句柄: {hwnd}, 客户区大小: {width}x{height}")
    return hwnd


def random_sleep(min_val: float, max_val: float):
    """随机等待一段时间"""
    sleep_seconds = random.uniform(min_val, max_val)
    time.sleep(sleep_seconds)


# 场景检测事件
SCENE_DETECTED_EVENT = Event('scene_detected')


class YYSBaseScript(EventBaseScript):
    """
    阴阳师基础脚本类
    封装通用的战斗、悬赏封印、场景管理等逻辑
    """

    def __init__(self, script_name: str):
        # 使用统一的日志管理器
        self.logger = get_logger(script_name)
        self.logger.info(f"初始化{script_name}脚本")

        # 初始化窗口句柄
        self.hwnd = find_window()

        # 初始化 WinController（统一管理 image_finder, keyboard, mouse, ocr）
        self.win_controller: WinController = WinController(self.hwnd)
        self.image_finder: ImageFinder = self.win_controller.image_finder
        self.keyboard = self.win_controller.keyboard
        self.mouse = self.win_controller.mouse
        self.ocr: CommonOcr = self.win_controller.ocr

        # 调用父类构造函数（依赖注入 image_finder 和 ocr）
        super().__init__(self.image_finder, self.ocr)

        # 脚本配置
        self.script_name = script_name
        self.script_start_time_mills = int(time.time() * 1000)
        self._cur_battle_count = 0
        self._cur_battle_victory_count = 0
        self._max_battle_count = 103
        self.accept_wq_type: WantedQuestAcceptType = WantedQuestAcceptType.REFUSE

        # 初始化场景管理器
        self.logger.info("初始化场景管理器中...")
        self.scene_manager: SceneManager = SceneManager(self.hwnd, self.image_finder)
        self.logger.info("初始化场景管理器完成")

        # 注册战斗结束事件
        self._register_battle_end_events()

        # 注册悬赏封印事件
        self._register_wanted_quest_events()

        # 注册 OCR 点击继续事件
        self._register_ocr_click_continue_event()

    def _register_battle_end_events(self):
        """注册战斗结束相关的图像匹配事件"""
        self._register_image_match_event(
            ImageMatchConfig(BATTLE_END_SUCCESS_IMAGES),
            self._on_battle_victory
        )
        self._register_image_match_event(
            ImageMatchConfig(BATTLE_END_LOSS_IMAGES),
            self._on_battle_end
        )
        self._register_image_match_event(
            ImageMatchConfig(BATTLE_END_OTHER_IMAGES),
            self._on_battle_end
        )

    def _register_wanted_quest_events(self):
        """注册悬赏封印相关的事件"""
        self._register_image_match_event(
            ImageMatchConfig(WANTED_QUEST_REJECT_IMAGE),
            self._on_wanted_quests_invited
        )
        # TODO: 支持只接收勾协（accept_wq_type = 2）
        # self._register_ocr_match_event("悬赏封印", self._on_wanted_quests_invited)

    def _register_ocr_click_continue_event(self):
        """注册 OCR 点击屏幕继续事件"""
        self._register_ocr_match_event(
            OCR_CLICK_SCREEN_CONTINUE,
            self._on_ocr_click_screen_continue
        )

    def bg_left_click(self, point: tuple, x_range: int = DEFAULT_CLICK_RANGE, y_range: int = DEFAULT_CLICK_RANGE):
        """后台左键点击（带随机偏移）

        Args:
            point: 目标坐标 (x, y)
            x_range: X轴随机偏移范围
            y_range: Y轴随机偏移范围
        """
        self.mouse.bg_left_click_with_range(point, x_range=x_range, y_range=y_range)

    def _on_battle_victory(self, point: tuple):
        """战斗胜利处理"""
        self.bg_left_click(point)
        self._cur_battle_victory_count += 1
        time.sleep(BATTLE_VICTORY_SLEEP)

    def _on_battle_end(self, point: tuple):
        """战斗结束（失败/奖励）处理"""
        # 不可去掉。如果不等一会，没点掉导致触发多次的话，会多次触发_cur_battle_count+=1
        time.sleep(BATTLE_END_SLEEP)
        # 使用匹配到的实际位置点击
        self.bg_left_click(point, x_range=BATTLE_END_CLICK_RANGE_X, y_range=BATTLE_END_CLICK_RANGE_Y)
        self._cur_battle_count += 1
        self._log_battle_count()
        time.sleep(BATTLE_END_CLICK_SLEEP)

    def _log_battle_count(self):
        """记录战斗计数日志"""
        self.logger.success(
            f"战斗完成，已战斗{self._cur_battle_count}/{self._max_battle_count}次，"
            f"胜利{self._cur_battle_victory_count}次"
        )

    def _on_ocr_click_screen_continue(self, ocr_result):
        """OCR 检测到点击屏幕继续"""
        self.logger.debug(ocr_result)
        self.bg_left_click((567, 460), x_range=OCR_CLICK_RANGE, y_range=OCR_CLICK_RANGE)

    def _on_wanted_quests_invited(self, point: tuple):
        """悬赏封印邀请处理"""
        match self.accept_wq_type:
            case WantedQuestAcceptType.REFUSE:
                reject_point = self.image_finder.bg_find_pic_by_cache(WANTED_QUEST_REJECT_IMAGE)
                if reject_point and reject_point != (-1, -1):
                    self.bg_left_click(reject_point)
            case WantedQuestAcceptType.ACCEPT_ALL:
                accept_point = self.image_finder.bg_find_pic_by_cache(WANTED_QUEST_ACCEPT_IMAGE)
                if accept_point and accept_point != (-1, -1):
                    self.bg_left_click(accept_point)
            case WantedQuestAcceptType.ACCEPT_GOUGU:
                # TODO: 实现勾协检测 - 需要 OCR 识别"勾协"或"契约"文字
                # 目前先接受所有，然后在战斗开始时检测是否为勾协，不是则退出
                accept_point = self.image_finder.bg_find_pic_by_cache(WANTED_QUEST_ACCEPT_IMAGE)
                if accept_point and accept_point != (-1, -1):
                    self.logger.info("检测到勾协邀请，接受")
                    self.bg_left_click(accept_point)
            case _:
                # 默认拒绝
                reject_point = self.image_finder.bg_find_pic_by_cache(WANTED_QUEST_REJECT_IMAGE)
                if reject_point and reject_point != (-1, -1):
                    self.bg_left_click(reject_point)

    def set_max_battle_count(self, max_battle_count: int) -> 'YYSBaseScript':
        """设置最大战斗次数（支持链式调用）"""
        self._max_battle_count = max_battle_count
        return self

    def on_run(self):
        """脚本启动时的钩子方法"""
        self.logger.info(f"开始运行{self.script_name}脚本")
        self.logger.info(f"目标挂机次数:{self._max_battle_count}")
        self._cur_battle_victory_count = 0
        self._cur_battle_count = 0

    def before_iteration(self):
        """每轮循环前的钩子方法"""
        pass

    def after_iteration(self):
        """每轮循环后的钩子方法"""
        random_sleep(0.05, 0.1)
        if self._cur_battle_count >= self._max_battle_count:
            self.stop()

    def on_scene_detected(self, detection_result: SceneDetectionResult):
        """场景检测回调（子类可覆盖）"""
        pass
