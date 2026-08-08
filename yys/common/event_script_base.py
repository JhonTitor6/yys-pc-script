# 添加项目根目录到路径，以便导入根目录下的模块
import os
import random
import sys
import time
from abc import ABCMeta, abstractmethod
from enum import IntEnum
from typing import Annotated, Any, Optional, TYPE_CHECKING, get_args, get_origin, get_type_hints

import win32gui
from loguru import logger

from win_util import WinController
from win_util.event import EventBaseScript, Event
from win_util.image import ImageMatchConfig, to_project_path
from yys.common import (
    BATTLE_VICTORY_SLEEP,
    BATTLE_END_SLEEP,
    BATTLE_END_CLICK_SLEEP,
    DEFAULT_CLICK_RANGE,
    BATTLE_END_CLICK_RANGE_X,
    BATTLE_END_CLICK_RANGE_Y,
    OCR_CLICK_RANGE,
)
from yys.common.scene_manager import SceneManager, SceneDetectionResult
from yys.common.script_meta import ConfigMeta

if TYPE_CHECKING:
    from tests.common.environment.base import GameEnvironment

# 获取项目根目录并添加到 sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from yys.common.log_manager import get_logger
except ImportError:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from yys.common.log_manager import get_logger


# ==================== 常量定义 ====================

class WantedQuestAcceptType(IntEnum):
    """悬赏封印接受类型"""
    REFUSE = 0      # 拒绝
    ACCEPT_ALL = 1  # 全部接受
    ACCEPT_GOUGU = 2  # 只接勾协

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
    # win32gui.SetWindowPos(hwnd, None, 0, 0, 1154, 680, win32con.SWP_NOMOVE)

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


def _extract_config_meta(annotated_type: Any) -> Optional[ConfigMeta]:
    """从 `Annotated[T, ConfigMeta(...)]` 中提取 ConfigMeta 实例。

    Args:
        annotated_type: typing.get_type_hints(include_extras=True) 返回的类型。

    Returns:
        提取到的 ConfigMeta；若类型不含 ConfigMeta 则返回 None。
    """
    if get_origin(annotated_type) is not Annotated:  # type: ignore[arg-type]
        return None
    for meta in get_args(annotated_type)[1:]:
        if isinstance(meta, ConfigMeta):
            return meta
    return None


def _validate_config_value(field_name: str, value: Any, meta: ConfigMeta) -> None:
    """根据 ConfigMeta 校验配置值；违反约束时抛 ValueError。"""
    if value is None:
        return
    if meta.field_type == "number":
        if meta.min_value is not None and value < meta.min_value:
            raise ValueError(
                f"配置项 {field_name}={value} 低于最小值 {meta.min_value}"
            )
        if meta.max_value is not None and value > meta.max_value:
            raise ValueError(
                f"配置项 {field_name}={value} 高于最大值 {meta.max_value}"
            )
    elif meta.field_type == "select":
        if meta.options:
            allowed = {opt["value"] for opt in meta.options}
            if value not in allowed:
                raise ValueError(
                    f"配置项 {field_name}={value} 不在可选值 {sorted(allowed)} 内"
                )


class _ABCMetaRelaxDel(ABCMeta):
    """ABCMeta 子类：__delattr__ 对继承属性静默通过。

    Python 默认 `type.__delattr__` 在删除继承属性（不在子类 __dict__ 中的属性）时抛 AttributeError。
    本类放宽此约束：当删除继承属性时不抛错，让后续 SCRIPT_META 查找回退到 None，
    从而触发 _apply_config 的 fail-fast TypeError。
    """
    def __delattr__(cls, name: str) -> None:
        try:
            super().__delattr__(name)
        except AttributeError:
            pass


class YYSBaseScript(EventBaseScript, metaclass=_ABCMetaRelaxDel):
    """
    阴阳师基础脚本类
    封装通用的战斗、悬赏封印、场景管理等逻辑
    """

    # 类级 SCRIPT_META 引用占位（由子类赋值）；仅用于 _apply_config 反向查找
    SCRIPT_META: Any = None

    # 入口场景：脚本启动时必须先到达的场景名。
    # 子类覆盖此属性声明自己需要在哪个场景启动。
    # 为空字符串或 None 时跳过入口跳转（兼容 Kuzunoha 等老脚本）。
    entry_scene: Optional[str] = None

    def __init__(self, script_name: str, config: Optional[dict] = None, env: Optional['GameEnvironment'] = None):
        """初始化阴阳师基础脚本

        Args:
            script_name: 脚本名称
            config: 配置字典（可选）；为 None 时走老路径不应用配置；为非 None 时按 SCRIPT_META.config_schema 校验并注入实例属性
            env: GameEnvironment 实例，用于 Mock 测试时注入（可选）

        Note:
            老调用方式（仅传 script_name 或 env）依然兼容：当 config 为 None 时不调用 _apply_config。
            新调用方式：script_cls(script_name, config={...}, env=env)。
        """
        # 使用统一的日志管理器
        self.logger = get_logger(script_name)
        self.logger.info(f"初始化{script_name}脚本")

        self._env = env

        # 初始化窗口句柄
        if self._env is not None:
            # Mock 环境使用预设的 hwnd
            self.hwnd = self._env.find_window("阴阳师") or 12345
        else:
            self.hwnd = find_window()

        # 初始化 WinController（支持 GameEnvironment 注入）
        if self._env is not None:
            self.win_controller: WinController = WinController(env=self._env)
        else:
            self.win_controller: WinController = WinController(self.hwnd)

        # 调用父类构造函数（依赖注入 image_finder 和 ocr）
        super().__init__(self.win_controller.image_finder, self.win_controller.ocr)

        # 脚本配置
        self.script_name = script_name
        self.script_start_time_mills = int(time.time() * 1000)
        self._cur_battle_count = 0
        self._cur_battle_victory_count = 0
        self.max_battle_count = 103
        self.accept_wq_type: WantedQuestAcceptType = WantedQuestAcceptType.REFUSE

        # 初始化场景管理器
        self.logger.info("初始化场景管理器中...")
        self.scene_manager: SceneManager = SceneManager(self.hwnd, self.win_controller)
        self.scene_manager.register_scenes_from_directory(
            to_project_path("yys/common/images/scene/"),
            to_project_path("yys/common/images/scene_control/")
        )
        self.logger.info("初始化场景管理器完成")

        # 注册战斗结束事件
        self._register_battle_end_events()

        # 注册悬赏封印事件
        self._register_wanted_quest_events()

        # 注册 OCR 点击继续事件
        self._register_ocr_click_continue_event()

        # 应用配置：
        # - 显式传 config 时按传入值合并默认；
        # - 老调用方式（config is None）但子类声明了 SCRIPT_META 时，也基于 default_config 兜底注入，
        #   避免新增的 schema 字段在老路径下变成 AttributeError；
        # - 既无 config 也无 SCRIPT_META：保持父类硬编码初值（兼容 Kuzunoha 等老脚本）。
        script_meta = getattr(self, "SCRIPT_META", None)
        if config is not None:
            self._apply_config(config)
        elif script_meta is not None:
            self._apply_config({})

    def _apply_config(self, config: dict) -> None:
        """根据 SCRIPT_META.config_schema 校验并注入配置到实例属性。

        Args:
            config: 字段名到值的字典。

        行为说明：
            - 优先使用 SCRIPT_META.default_config 作为缺省值；
            - 对每个 config_schema 字段，从 typing.get_type_hints(include_extras=True) 提取 ConfigMeta；
            - 校验 min_value / max_value / options 约束，违反则抛 ValueError；
            - 将最终值以 schema 字段名为 key 写入实例属性（如 self.max_battle_count）。
        """
        script_meta = getattr(self, "SCRIPT_META", None)
        if script_meta is None:
            raise TypeError(
                f"{type(self).__name__} 必须声明 SCRIPT_META 类属性（auto-registry Step 1+2 规范）"
            )

        config_schema = script_meta.config_schema
        defaults = script_meta.default_config or {}

        # 解析 schema 字段的 ConfigMeta
        try:
            hints = get_type_hints(config_schema, include_extras=True)
        except Exception:
            hints = {}

        field_metas: dict[str, ConfigMeta] = {}
        for field_name, annotated_type in hints.items():
            config_meta = _extract_config_meta(annotated_type)
            if config_meta is not None:
                field_metas[field_name] = config_meta

        # 合并 defaults + config
        merged: dict[str, Any] = {}
        for field_name in field_metas.keys():
            if field_name in config:
                merged[field_name] = config[field_name]
            elif field_name in defaults:
                merged[field_name] = defaults[field_name]
            else:
                merged[field_name] = field_metas[field_name].default

        # 校验 + 写入
        for field_name, value in merged.items():
            meta = field_metas.get(field_name)
            if meta is None:
                # 字段不在 schema 中，原样写入（兼容自定义扩展）
                setattr(self, field_name, value)
                continue
            _validate_config_value(field_name, value, meta)
            setattr(self, field_name, value)
        self.logger.debug(f"已应用配置: {list(merged.keys())}")

    def __getattr__(self, name):
        """代理到 win_controller，实现子组件方法的直接访问"""
        if name in ('win_controller', 'logger', 'hwnd', '_env', 'scene_manager'):
            raise AttributeError(name)
        if hasattr(self.win_controller, name):
            return getattr(self.win_controller, name)
        raise AttributeError(name)

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
            ImageMatchConfig(WANTED_QUEST_REJECT_IMAGE, x0=500),
            self._on_wanted_quests_invited
        )
        self._register_ocr_match_event("悬赏封印", self._on_wanted_quests_invited)

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

    def _should_count_battle_end(self, _point: tuple[int, int]) -> bool:
        """判断当前结算画面是否计入战斗次数；默认所有结算画面都计数。"""
        return True

    def _on_battle_end(self, point: tuple):
        """战斗结束（失败/奖励）处理"""
        # 不可去掉。如果不等一会，没点掉导致触发多次的话，会多次触发_cur_battle_count+=1
        time.sleep(BATTLE_END_SLEEP)
        # 使用匹配到的实际位置点击
        self.bg_left_click(point, x_range=BATTLE_END_CLICK_RANGE_X, y_range=BATTLE_END_CLICK_RANGE_Y)
        if self._should_count_battle_end(point):
            self._cur_battle_count += 1
            self._log_battle_count()
        time.sleep(BATTLE_END_CLICK_SLEEP)

    def _log_battle_count(self):
        """记录战斗计数日志"""
        self.logger.success(
            f"战斗完成，已战斗{self._cur_battle_count}/{self.max_battle_count}次，"
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
        self.max_battle_count = max_battle_count
        return self

    def get_state_snapshot(self) -> dict[str, object]:
        """获取脚本当前状态快照，用于 UI 展示和历史记录。"""
        return {
            "script_name": self.script_name,
            "battle_count": self._cur_battle_count,
            "victory_count": self._cur_battle_victory_count,
            "max_battle_count": self.max_battle_count,
        }

    def run(self) -> None:
        """主循环：先做入口场景跳转，再进入父类的主循环逻辑。

        Returns:
            无返回值。跳转失败时直接 return，**不**进入主循环，
            RunManager 会检测到脚本未进入 RUNNING 状态而标记 ERROR。
        """
        if self.entry_scene:
            self.logger.info(f"执行入口场景跳转: {self.entry_scene}")
            if not self.scene_manager.goto_scene(self.entry_scene):
                self.logger.error(f"入口场景跳转失败，停止脚本: {self.entry_scene}")
                self._stop_threading_event.clear()  # 防御性清理，允许重新 run
                return
        super().run()

    @abstractmethod
    def on_run(self):
        """脚本启动时的钩子方法（子类必须实现）"""
        self.logger.info(f"开始运行{self.script_name}脚本")
        self.logger.info(f"目标挂机次数:{self.max_battle_count}")
        self._cur_battle_victory_count = 0
        self._cur_battle_count = 0

    def before_iteration(self):
        """每轮循环前的钩子方法"""
        pass

    def after_iteration(self):
        """每轮循环后的钩子方法"""
        random_sleep(0.05, 0.1)
        if self._cur_battle_count >= self.max_battle_count:
            self.stop()

    def on_scene_detected(self, detection_result: SceneDetectionResult):
        """场景检测回调（子类可覆盖）"""
        pass
