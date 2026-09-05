from __future__ import annotations

import time
from enum import Enum
from numbers import Real
from typing import Annotated, Any, Optional, TYPE_CHECKING, TypedDict, get_type_hints

import cv2
import numpy as np

from win_util.image import ImageMatchConfig, to_project_path
from yys.common.event_script_base import YYSBaseScript, _extract_config_meta, random_sleep
from yys.common.script_meta import ConfigMeta, ScriptMeta

if TYPE_CHECKING:
    from tests.common.environment.base import GameEnvironment


_DEFEATED_RED_RANGES: tuple[
    tuple[tuple[int, int, int], tuple[int, int, int]], ...
] = (
    ((0, 100, 80), (10, 255, 255)),
    ((170, 100, 80), (179, 255, 255)),
)
_DEFEATED_STAMP_MASK_PATH = "yys/abyss_shadows/images/defeated_stamp_mask.png"
_DEFEATED_STAMP_SIZE: tuple[int, int] = (30, 68)
_DEFEATED_STAMP_THRESHOLD: float = 0.50


class AbyssShadowsConfig(TypedDict, total=False):
    """狭间暗域脚本的可配置字段。"""
    boss_count: Annotated[int, ConfigMeta(
        default=2,
        min_value=0,
        max_value=99,
        field_type="number",
        label="首领次数",
        group="基础",
        help="每个暗域首领挑战次数（0-99）",
        hot_reloadable=True,
    )]
    boss_damage_limit: Annotated[int, ConfigMeta(
        default=1,
        min_value=0,
        max_value=999999999,
        field_type="number",
        label="首领伤害限制",
        group="基础",
        help="首领战斗伤害超过该值时退出（0-999999999）",
    )]
    commander_count: Annotated[int, ConfigMeta(
        default=4,
        min_value=0,
        max_value=99,
        field_type="number",
        label="副将次数",
        group="基础",
        help="每个暗域副将挑战次数（0-99）",
        hot_reloadable=True,
    )]
    commander_damage_limit: Annotated[int, ConfigMeta(
        default=1,
        min_value=0,
        max_value=999999999,
        field_type="number",
        label="副将伤害限制",
        group="基础",
        help="副将战斗伤害超过该值时退出（0-999999999）",
        hot_reloadable=False,
    )]
    elite_count: Annotated[int, ConfigMeta(
        default=6,
        min_value=0,
        max_value=99,
        field_type="number",
        label="精英次数",
        group="基础",
        help="每个暗域精英挑战次数（0-99）",
        hot_reloadable=True,
    )]
    elite_damage_limit: Annotated[int, ConfigMeta(
        default=6000000,
        min_value=0,
        max_value=999999999,
        field_type="number",
        label="精英伤害限制",
        group="基础",
        help="精英战斗伤害超过该值时退出（0-999999999）",
        hot_reloadable=False,
    )]


class EnemyType(Enum):
    BOSS = 0  # 首领
    COMMANDER = 1  # 副将
    ELITE = 2  # 精英


class Enemy:
    def __init__(self, enemy_type: EnemyType, target_damage: int,
                 image_path: str, label_position: tuple[int, int, int, int], has_challenged: bool = False):
        """

        :param enemy_type:
        :param target_damage:
        :param image_path:
        :param label_position: 元组：(左上x，左上y，右下x，右下y)
        """
        self.enemy_type: EnemyType = enemy_type
        self.target_damage: int = target_damage
        self.image_path: str = image_path
        self.label_and_pic_position: tuple[int, int, int, int] = label_position
        self.has_challenged: bool = has_challenged


class AbyssShadowsState(Enum):
    """狭间暗域状态机"""
    SELECTION = "selection"  # 狭间暗域主界面
    SCENE = "scene"  # 暗域场景（神龙/白藏主/豹袭/孔雀）
    ENEMY_SELECTION = "enemy_selection"  # 敌人选择界面
    BATTLE_REPORT = "battle_report"  # 战报界面（核心中枢）
    BATTLE = "battle"  # 战斗中
    BATTLE_END = "battle_end"  # 战斗结束


class Main(YYSBaseScript):
    """
    狭间暗域
    TODO: 未实际验证

    以战报界面为核心导航中枢的自动化脚本
    完成 2 首领、4 副将、6 精英的挑战
    """
    SCRIPT_META = ScriptMeta(
        display_name="狭间暗域",
        category="副本",
        config_schema=AbyssShadowsConfig,
        default_config={
            "boss_count": 2,
            "boss_damage_limit": 1,
            "commander_count": 4,
            "commander_damage_limit": 1,
            "elite_count": 6,
            "elite_damage_limit": 6000000,
        },
    )
    # 入口包含 Home 界面拖拽，不能直接交给只支持按钮 BFS 的 entry_scene。
    # on_run() 会执行录制确认过的 Home → 日常 → 狭间暗域入口流程。

    _ENTRY_HOME_TO_DAILY_IMAGE: str = "yys/abyss_shadows/images/scene_control/home_to_daily.bmp"
    _ENTRY_DAILY_IMAGE: str = "yys/abyss_shadows/images/scene/daily.bmp"
    _ENTRY_DAILY_TO_ABYSS_IMAGE: str = (
        "yys/abyss_shadows/images/scene_control/daily_to_abyss_selection.bmp"
    )
    _ENTRY_ABYSS_SELECTION_IMAGE: str = "yys/abyss_shadows/images/scene/abyss_selection.bmp"
    _ENTRY_IMAGE_SIMILARITY: float = 0.8
    _ENTRY_IMAGE_TIMEOUT: float = 10.0
    _ENTRY_HOME_CLICK_OFFSET: tuple[int, int] = (0, 0)
    # 卡片模板命中点加偏移后落在“参加”按钮，而不是卡片主体。
    _ENTRY_ABYSS_JOIN_OFFSET: tuple[int, int] = (114, 18)
    # 最新 1136x640 证据中，点击“参加”后弹窗“前往”按钮中心。
    _ENTRY_ABYSS_FORWARD_POINT: tuple[float, float] = (566 / 1136, 459 / 640)

    # 录制事件中的客户区坐标归一化结果：
    # 1. Home 横向拖拽，露出左侧入口图标；
    # 2. 日常列表纵向拖拽，露出完整的狭间暗域卡片。
    _ENTRY_HOME_SWIPE: tuple[tuple[float, float], tuple[float, float]] = (
        (565 / 1148, 316 / 647),
        (940 / 1148, 316 / 647),
    )
    _ENTRY_DAILY_SWIPE: tuple[tuple[float, float], tuple[float, float]] = (
        (679 / 1148, 384 / 647),
        (682 / 1148, 228 / 647),
    )

    @classmethod
    def get_config_schema(cls) -> list[dict[str, Any]]:
        """从 SCRIPT_META 反射 config_schema 为 wire format list of dict。"""
        meta = cls.SCRIPT_META
        if meta is None or meta.config_schema is None:
            return []
        try:
            hints = get_type_hints(meta.config_schema, include_extras=True)
        except Exception:
            hints = {}
        result: list[dict[str, Any]] = []
        for field_name, annotated_type in hints.items():
            config_meta = _extract_config_meta(annotated_type)
            if config_meta is None:
                continue
            result.append({
                "key": field_name,
                "label": config_meta.label or field_name,
                "field_type": config_meta.field_type,
                "default": config_meta.default,
                "min_value": config_meta.min_value,
                "max_value": config_meta.max_value,
                "options": list(config_meta.options or []),
                "hot_reloadable": config_meta.hot_reloadable,
                "description": config_meta.help,
                "unit": config_meta.unit,
                "sensitive": config_meta.sensitive,
            })
        return result

    def __init__(
        self,
        script_name: str = "abyss_shadows",
        env: Optional["GameEnvironment"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """初始化狭间暗域脚本。

        Args:
            script_name: 脚本名，默认 "abyss_shadows"。
            env: GameEnvironment 实例，用于 Mock 测试时注入。
            config: 配置字典（可选）。
        """
        super().__init__(script_name, config=config, env=env)
        self._defeated_stamp_mask = self._load_defeated_stamp_mask()

        # 注册狭间暗域专属场景和跳转
        self.scene_manager.register_scenes_from_directory(
            to_project_path("yys/abyss_shadows/images/scene/"),
            to_project_path("yys/abyss_shadows/images/scene_control/")
        )

        # 状态机
        self._state = AbyssShadowsState.SELECTION
        self._cur_enemy: Optional[Enemy] = None  # 当前战斗的敌人
        self._last_damage_check_time = 0.0  # 上次伤害检查时间
        self._damage_check_interval = 0.5  # 伤害检查间隔（秒）
        self._last_damage_value: Optional[int] = None  # 上一次确认的伤害值
        self._damage_history_enemy: Optional[Enemy] = None  # 伤害值所属战斗

        # 场景索引（4个暗域轮换）
        self.cur_scene_index = 0
        self.scene_name_list = ["abyss_dragon", "abyss_fox", "abyss_leopard", "abyss_peacock"]
        self._current_area: Optional[str] = None  # 当前暗域区域

        # 敌人配置（固定位置）
        self.enemies = {
            EnemyType.BOSS: [
                Enemy(
                    enemy_type=EnemyType.BOSS,
                    target_damage=self.boss_damage_limit,
                    image_path="yys/abyss_shadows/images/boss_label.bmp",
                    label_position=(554, 120, 688, 210),
                    has_challenged=False
                )
            ],
            EnemyType.COMMANDER: [
                Enemy(
                    enemy_type=EnemyType.COMMANDER,
                    target_damage=self.commander_damage_limit,
                    image_path="yys/abyss_shadows/images/commander_label.bmp",
                    label_position=(424, 250, 558, 335),
                    has_challenged=False
                ),
                Enemy(
                    enemy_type=EnemyType.COMMANDER,
                    target_damage=self.commander_damage_limit,
                    image_path="yys/abyss_shadows/images/commander_label.bmp",
                    label_position=(700, 250, 833, 335),
                    has_challenged=False
                )
            ],
            EnemyType.ELITE: [
                Enemy(
                    enemy_type=EnemyType.ELITE,
                    target_damage=self.elite_damage_limit,
                    image_path="yys/abyss_shadows/images/elite_label.bmp",
                    label_position=(342, 360, 480, 435),
                    has_challenged=False
                ),
                Enemy(
                    enemy_type=EnemyType.ELITE,
                    target_damage=self.elite_damage_limit,
                    image_path="yys/abyss_shadows/images/elite_label.bmp",
                    label_position=(554, 360, 691, 435)
                ),
                Enemy(
                    enemy_type=EnemyType.ELITE,
                    target_damage=self.elite_damage_limit,
                    image_path="yys/abyss_shadows/images/elite_label.bmp",
                    label_position=(766, 360, 905, 435)
                )
            ]
        }

        # 挑战计数
        self.challenge_counts = {
            EnemyType.BOSS: 0,
            EnemyType.COMMANDER: 0,
            EnemyType.ELITE: 0
        }
        self.max_challenge_counts = {
            EnemyType.BOSS: 2,
            EnemyType.COMMANDER: 4,
            EnemyType.ELITE: 6
        }

        # 注册基础事件
        self._register_base_events()
        # 注册战报相关事件
        self._register_battle_report_events()

    def _register_base_events(self):
        """注册基础场景事件"""
        # 狭间暗域主界面
        self._register_image_match_event(
            ImageMatchConfig("yys/abyss_shadows/images/scene/abyss_selection.bmp"),
            self._on_abyss_shadows_selection
        )
        # 敌人选择界面
        self._register_image_match_event(
            ImageMatchConfig("yys/abyss_shadows/images/scene/abyss_enemy_selection.bmp"),
            self._on_abyss_shadows_enemy_selection
        )
        # 战报按钮
        self._register_image_match_event(
            ImageMatchConfig("yys/abyss_shadows/images/abyss_navigation.bmp"),
            self._on_battle_report_button
        )
        # 准备完成
        self._register_image_match_event(
            ImageMatchConfig("yys/images/ready.bmp"),
            self.bg_left_click
        )
        # 战斗中
        self._register_image_match_event(
            ImageMatchConfig("yys/common/images/scene/battling.bmp"),
            self._on_battling
        )
        # 战斗结束（胜利/失败/奖励）
        self._register_image_match_event(
            ImageMatchConfig("yys/images/battle_end_success.bmp"),
            self._on_battle_victory
        )
        self._register_image_match_event(
            ImageMatchConfig("yys/images/battle_end_loss.bmp"),
            self._on_battle_end
        )
        self._register_image_match_event(
            ImageMatchConfig("yys/images/battle_end.bmp"),
            self._on_battle_end
        )
        # 新增：等待开始
        self._register_image_match_event(
            ImageMatchConfig("yys/abyss_shadows/images/wait_to_start.bmp"),
            self._on_wait_to_start
        )
        # 新增：更换领域
        self._register_image_match_event(
            ImageMatchConfig("yys/abyss_shadows/images/change_area.bmp"),
            self._on_change_area
        )

    def _register_battle_report_events(self):
        """注册战报界面相关事件"""

    # ==================== 场景事件处理 ====================

    def _on_abyss_shadows_selection(self, point):
        """狭间暗域主界面"""
        self._state = AbyssShadowsState.SELECTION
        self.scene_manager.goto_scene(self.scene_name_list[self.cur_scene_index])

    def _on_abyss_shadows_enemy_selection(self, point) -> bool:
        """敌人选择界面"""
        self._state = AbyssShadowsState.ENEMY_SELECTION
        enemy = self.get_next_enemy()
        if enemy is None:
            self._handle_no_enemy_available()
            return False
        self._select_enemy(enemy)
        return True

    def _handle_no_enemy_available(self):
        """处理没有可挑战敌人的情况"""
        if self.cur_scene_index >= len(self.scene_name_list) - 1:
            self.logger.warning("所有狭间暗域都已挑战完毕")
            self.stop()
            return

        # 切换到下一个暗域场景
        self.cur_scene_index += 1
        next_area = self.scene_name_list[self.cur_scene_index]

        self.logger.info(f"切换到下一个区域: {next_area}")
        self.change_area(next_area)

        # 重置 enemies.has_challenged
        self._reset_enemies_challenge_status()

    def _reset_enemies_challenge_status(self):
        """重置所有敌人的已挑战状态"""
        for enemy_type in EnemyType:
            for enemy in self.enemies[enemy_type]:
                enemy.has_challenged = False

    def click_enemy_area(self, enemy: Enemy) -> bool:
        """
        点击敌人区域，进入战斗

        流程：点击战报 → 点击敌人区域 → 点击前往 → 处理确认 → 点击挑战

        Args:
            enemy: 敌人对象

        Returns:
            bool: 进入战斗成功返回 True
        """
        # 点击战报按钮
        if not self.win_controller.find_and_click("yys/abyss_shadows/images/abyss_navigation.bmp"):
            self.logger.warning("未找到战报按钮")
            return False

        random_sleep(0.5, 1)

        # 点击敌人区域
        positions = enemy.label_and_pic_position
        point = self.win_controller.find_image_with_timeout(
            enemy.image_path,
            x0=positions[0], y0=positions[1],
            x1=positions[2], y1=positions[3],
            timeout=2
        )
        if point is None or point == (-1, -1):
            self.logger.warning(f"未找到敌人: {enemy.enemy_type}")
            return False

        # 点击敌人头像（带偏移）
        self.bg_left_click((point[0] + 60, point[1]), x_range=5, y_range=5)
        random_sleep(1, 2)

        # 点击前往按钮
        if self.win_controller.find_and_click("yys/abyss_shadows/images/abyss_goto_enemy.bmp", timeout=1):
            # 处理跨区域确认框
            random_sleep(0.5, 1)
            self.win_controller.find_and_click("yys/abyss_shadows/images/confirm.bmp")
            random_sleep(3, 5)

        # 点击挑战按钮
        if not self.win_controller.find_and_click("yys/abyss_shadows/images/battle_button.bmp", timeout=3):
            self.logger.warning("未找到挑战按钮")
            return False

        # 处理奖励次数上限确认框
        random_sleep(0.5, 1)
        self.win_controller.find_and_click("yys/abyss_shadows/images/confirm.bmp")

        self.logger.info(f"开始挑战: {enemy.enemy_type}")
        return True

    def _select_enemy(self, enemy: Enemy):
        """选择敌人并进入战斗"""
        if enemy is None:
            return
        if self.click_enemy_area(enemy):
            self.logger.info(f"挑战: {enemy.enemy_type}")
            enemy.has_challenged = True
            self._cur_enemy = enemy
            self.challenge_counts[enemy.enemy_type] += 1
            self._state = AbyssShadowsState.BATTLE

    def get_next_enemy(self) -> Optional[Enemy]:
        """获取下一个可挑战的敌人（优先级：首领>副将>精英）"""
        for enemy_type in [EnemyType.BOSS, EnemyType.COMMANDER, EnemyType.ELITE]:
            if self.challenge_counts[enemy_type] >= self.max_challenge_counts[enemy_type]:
                continue
            for enemy in self.enemies[enemy_type]:
                if enemy.has_challenged:
                    continue
                if self._is_enemy_defeated(enemy.label_and_pic_position):
                    enemy.has_challenged = True
                    continue
                return enemy
        return None

    # ==================== 战报界面事件处理 ====================

    def _on_battle_report_button(self, point):
        """点击战报按钮"""
        self._state = AbyssShadowsState.BATTLE_REPORT
        self.bg_left_click(point)

    def _on_battle_report_current(self, point):
        """战报界面 - 当前暗域（有可打目标）"""
        self._state = AbyssShadowsState.BATTLE_REPORT
        self.bg_left_click(point)
        # 点击后应该进入敌人选择界面
        random_sleep(0.5, 1)

    def _on_battle_report_other(self, point):
        """战报界面 - 其他暗域（需切换）"""
        self._state = AbyssShadowsState.BATTLE_REPORT
        self.bg_left_click(point)
        # 切换到其他暗域页签后，会再次检测战报界面
        random_sleep(0.5, 1)

    # ==================== 战斗相关事件处理 ====================

    def _on_battling(self, point):
        """战斗中 - 伤害监控"""
        current_time = time.time()

        # 检查是否在伤害检查间隔内
        if current_time - self._last_damage_check_time < self._damage_check_interval:
            return False

        self._last_damage_check_time = current_time

        target_damage: int = 20000000
        if self._cur_enemy is not None:
            target_damage = self._cur_enemy.target_damage

        # OCR 检查伤害
        current_damage = self._get_current_damage()
        self.logger.debug(f"current_damage: {current_damage}, target_damage: {target_damage}")
        if current_damage > target_damage:
            self._exit_battle()
            return True

        return False

    def _get_current_damage(self) -> int:
        """OCR 获取当前伤害"""
        if self._damage_history_enemy is not self._cur_enemy:
            self._last_damage_value = None
            self._damage_history_enemy = self._cur_enemy

        damage_image = self.image_finder.crop_screenshot_cache(3, 99, 283, 143)
        ocr_result = self.ocr.find_all_texts(
            damage_image,
            similarity_threshold=0.2,
            allowlist='0123456789',
            use_det=False,
            use_cls=False,
            use_rec=True,
        )
        if ocr_result is None or len(ocr_result) != 1:
            return 0
        raw_text = str(ocr_result[0])
        if not raw_text.isdigit():
            return 0

        damage_text = raw_text
        if raw_text.startswith("1"):
            verified_result = self.ocr.find_all_texts(
                damage_image,
                similarity_threshold=0.95,
                allowlist='0123456789',
                use_det=False,
                use_cls=False,
                use_rec=True,
            )
            verified_text = (
                str(verified_result[0])
                if verified_result is not None and len(verified_result) == 1
                else None
            )
            if verified_text != raw_text:
                previous_text = (
                    str(self._last_damage_value)
                    if self._last_damage_value is not None
                    else ""
                )
                if previous_text and raw_text[1:] == previous_text:
                    damage_text = previous_text
                else:
                    return 0
        try:
            current_damage = int(damage_text)
        except (ValueError, TypeError):
            return 0
        self._last_damage_value = current_damage
        return current_damage

    def _exit_battle(self):
        """退出战斗（Esc + Enter）"""
        self.win_controller.key_down("esc")
        random_sleep(0.5, 1)
        self.win_controller.key_down("enter")
        self._cur_enemy = None
        self._state = AbyssShadowsState.BATTLE_REPORT

    def _on_battle_end(self, point):
        """战斗结束"""
        self._state = AbyssShadowsState.BATTLE_END
        self.bg_left_click(point)
        self._cur_enemy = None

    # ==================== 已击破识别 ====================

    @staticmethod
    def _load_defeated_stamp_mask() -> np.ndarray:
        """加载并校验狭间暗域已击破印章模板。"""
        template_path = to_project_path(_DEFEATED_STAMP_MASK_PATH)
        try:
            template = cv2.imdecode(
                np.fromfile(template_path, dtype=np.uint8),
                cv2.IMREAD_GRAYSCALE,
            )
        except (OSError, cv2.error) as error:
            raise ValueError(f"无法加载狭间暗域已击破印章模板：{template_path}") from error

        if (
            template is None
            or template.ndim != 2
            or template.dtype != np.uint8
            or template.shape != _DEFEATED_STAMP_SIZE
            or template.std() == 0
        ):
            raise ValueError(f"狭间暗域已击破印章模板无效：{template_path}")
        return template

    def _is_enemy_defeated(self, position: tuple[int, int, int, int]) -> bool:
        """检测敌人头像中央的红色“已击破”印章。"""
        image_finder = getattr(self, "image_finder", None)
        if image_finder is None or getattr(image_finder, "screenshot_cache", None) is None:
            return False

        try:
            cropped = image_finder.crop_screenshot_cache(*position)
        except (AttributeError, TypeError, ValueError):
            return False
        if cropped is None:
            return False

        image = np.asarray(cropped)
        if image.size == 0 or image.ndim != 3 or image.shape[2] != 3:
            return False

        crop_height, crop_width = image.shape[:2]
        template_height, template_width = self._defeated_stamp_mask.shape
        if (
            crop_height < template_height
            or crop_width < template_width
            or image.dtype != np.uint8
        ):
            return False

        try:
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        except cv2.error:
            return False

        red_mask = np.zeros((crop_height, crop_width), dtype=np.uint8)
        for lower, upper in _DEFEATED_RED_RANGES:
            red_mask |= cv2.inRange(hsv, lower, upper)

        try:
            result = cv2.matchTemplate(
                red_mask,
                self._defeated_stamp_mask,
                cv2.TM_CCOEFF_NORMED,
            )
            if result.size == 0:
                return False
            _, score, _, _ = cv2.minMaxLoc(result)
        except cv2.error:
            return False
        return bool(np.isfinite(score) and score >= _DEFEATED_STAMP_THRESHOLD)

    def _is_current_tab(self) -> bool:
        """
        OCR 判断是否为当前暗域
        TODO: 暂不实现
        """
        # 暂不实现
        return True

    # ==================== 生命周期方法 ====================

    def _on_battle_victory(self, point):
        """战斗胜利回调"""
        super()._on_battle_victory(point)
        self._cur_battle_count += 1
        self._log_battle_count()
        self._cur_enemy = None

    @staticmethod
    def _is_valid_point(point: object) -> bool:
        """判断找图结果是否为有效客户区坐标。"""
        if not isinstance(point, (tuple, list)) or len(point) != 2:
            return False
        return all(isinstance(value, Real) for value in point) and point != (-1, -1)

    def _entry_client_size(self) -> tuple[int, int]:
        """获取录制入口动作使用的客户区尺寸。"""
        if self._env is not None:
            try:
                left, top, right, bottom = self._env.get_window_client_rect()
                width, height = right - left, bottom - top
                if width > 0 and height > 0:
                    return width, height
            except (AttributeError, TypeError, ValueError):
                pass

        screenshot_cache = getattr(self.image_finder, "screenshot_cache", None)
        shape = getattr(screenshot_cache, "shape", None)
        if shape is not None and len(shape) >= 2:
            height, width = int(shape[0]), int(shape[1])
            if width > 0 and height > 0:
                return width, height

        # 录制时的客户区为 1148x647；1154x680 是项目既有默认窗口尺寸，
        # 用作真实窗口截图尚未初始化时的保守回退值。
        return 1154, 680

    def _entry_swipe(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> bool:
        """按客户区比例执行录制中的拖拽，并刷新截图缓存。"""
        width, height = self._entry_client_size()
        start_point = (round(width * start[0]), round(height * start[1]))
        end_point = (round(width * end[0]), round(height * end[1]))
        result = self.mouse.bg_swipe(
            start_point[0],
            start_point[1],
            end_point[0],
            end_point[1],
            steps=20,
            duration=0.6,
            curve_factor=0.35,
        )
        self.win_controller.update_screenshot_cache()
        return bool(result)

    def _entry_find_and_click(
        self,
        image_path: str,
        timeout: float,
        click_offset: tuple[int, int] = (0, 0),
    ) -> bool:
        """通过模板匹配找到入口控件并点击，不使用固定点击坐标。"""
        point = self.win_controller.find_image_with_timeout(
            image_path,
            timeout=timeout,
            similarity=self._ENTRY_IMAGE_SIMILARITY,
        )
        if not self._is_valid_point(point):
            self.logger.warning(f"未找到入口控件: {image_path}")
            return False

        click_point = (
            int(point[0]) + click_offset[0],
            int(point[1]) + click_offset[1],
        )
        return bool(self.mouse.bg_left_click(click_point, x_range=5, y_range=5))

    def _entry_wait_for_image(self, image_path: str, timeout: float) -> bool:
        """等待入口场景模板出现。"""
        point = self.win_controller.find_image_with_timeout(
            image_path,
            timeout=timeout,
            similarity=self._ENTRY_IMAGE_SIMILARITY,
        )
        return self._is_valid_point(point)

    def _is_abyss_selection_visible(self) -> bool:
        """判断当前是否已经位于狭间暗域选择界面。"""
        self.win_controller.update_screenshot_cache()
        point = self.win_controller.find_image(
            self._ENTRY_ABYSS_SELECTION_IMAGE,
            similarity=self._ENTRY_IMAGE_SIMILARITY,
        )
        return self._is_valid_point(point)

    def goto_abyss_shadows(self) -> bool:
        """
        进入狭间暗域

        流程：Home 横向拖拽 → 动态入口图标 → 日常列表纵向拖拽 →
        动态狭间暗域卡片。

        狭间暗域卡片位置会随日常列表滚动而变化，必须通过模板匹配点击。
        本方法只负责进入“狭间暗域”选择界面；选择具体暗域由 SceneManager
        继续使用对应的动态场景控制图完成。

        Returns:
            bool: 进入成功返回 True
        """
        if self._is_abyss_selection_visible():
            return True

        # 录制事件 1：Home 横向拖拽，露出入口图标。
        if not self._entry_swipe(*self._ENTRY_HOME_SWIPE):
            self.logger.warning("Home 入口横向拖拽失败")
            return False

        # 录制事件 2：入口图标位置不固定，使用模板匹配点击。
        if not self._entry_find_and_click(
            self._ENTRY_HOME_TO_DAILY_IMAGE,
            timeout=self._ENTRY_IMAGE_TIMEOUT,
            click_offset=self._ENTRY_HOME_CLICK_OFFSET,
        ):
            self.logger.warning("未找到日常入口图标")
            return False

        # 等待“日常”面板稳定后，再执行录制事件 3 的纵向拖拽。
        if not self._entry_wait_for_image(
            self._ENTRY_DAILY_IMAGE,
            timeout=self._ENTRY_IMAGE_TIMEOUT,
        ):
            self.logger.warning("点击日常入口后未进入日常面板")
            return False

        if not self._entry_swipe(*self._ENTRY_DAILY_SWIPE):
            self.logger.warning("日常列表纵向拖拽失败")
            return False

        # 录制事件 4：狭间暗域卡片位置随列表滚动变化，使用卡片模板匹配点击。
        if not self._entry_find_and_click(
            self._ENTRY_DAILY_TO_ABYSS_IMAGE,
            timeout=self._ENTRY_IMAGE_TIMEOUT,
            click_offset=self._ENTRY_ABYSS_JOIN_OFFSET,
        ):
            self.logger.warning("未找到狭间暗域卡片")
            return False

        # “参加”可能直接进入选择页，也可能先弹出详情框；后者继续点击“前往”。
        if not self._is_abyss_selection_visible():
            random_sleep(0.5, 1.0)
            if not self._is_abyss_selection_visible():
                width, height = self._entry_client_size()
                forward_point = (
                    round(width * self._ENTRY_ABYSS_FORWARD_POINT[0]),
                    round(height * self._ENTRY_ABYSS_FORWARD_POINT[1]),
                )
                if not self.mouse.bg_left_click(
                    forward_point,
                    x_range=5,
                    y_range=5,
                ):
                    self.logger.warning("点击狭间暗域“前往”按钮失败")
                    return False

        if not self._entry_wait_for_image(
            self._ENTRY_ABYSS_SELECTION_IMAGE,
            timeout=self._ENTRY_IMAGE_TIMEOUT,
        ):
            self.logger.warning("点击狭间暗域卡片后未进入选择界面")
            return False

        self.logger.info("已进入狭间暗域选择界面")
        return True

    def check_current_area(self) -> Optional[str]:
        """
        检查当前暗域区域

        Returns:
            str or None: 当前区域名称，如 "abyss_dragon"，未识别到返回 None
        """
        area_mappings = [
            ("yys/abyss_shadows/images/dragon_area.bmp", "abyss_dragon"),
            ("yys/abyss_shadows/images/fox_area.bmp", "abyss_fox"),
            ("yys/abyss_shadows/images/leopard_area.bmp", "abyss_leopard"),
            ("yys/abyss_shadows/images/peacock_area.bmp", "abyss_peacock"),
        ]

        for image_path, area_name in area_mappings:
            point = self.win_controller.find_image_with_timeout(image_path, timeout=1)
            if point and point != (-1, -1):
                self.logger.info(f"当前区域: {area_name}")
                return area_name

        return None

    def change_area(self, target_area: str) -> bool:
        """
        切换到目标暗域区域

        Args:
            target_area: 目标区域名称，如 "abyss_peacock"

        Returns:
            bool: 切换成功返回 True
        """
        self.logger.info(f"切换到目标区域: {target_area}")

        # 确保不在战报界面 - 点击退出按钮
        if self.win_controller.find_and_click("yys/abyss_shadows/images/map_exit.bmp"):
            random_sleep(0.5, 1)

        # 点击更换领域按钮
        if not self.win_controller.find_and_click("yys/abyss_shadows/images/change_area.bmp", timeout=1):
            self.logger.warning("未找到更换领域按钮")
            return False

        random_sleep(1, 1.5)

        # 选择目标暗域入口
        area_image_map = {
            "abyss_dragon": "yys/abyss_shadows/images/scene_control/abyss_selection_to_abyss_dragon.bmp",
            "abyss_fox": "yys/abyss_shadows/images/scene_control/abyss_selection_to_abyss_fox.bmp",
            "abyss_leopard": "yys/abyss_shadows/images/scene_control/abyss_selection_to_abyss_leopard.bmp",
            "abyss_peacock": "yys/abyss_shadows/images/scene_control/abyss_selection_to_abyss_peacock.bmp",
        }

        if target_area not in area_image_map:
            self.logger.warning(f"未知区域: {target_area}")
            return False

        # FIXME: 未找到目标区域入口: abyss_fox，可以尝试其他狭间
        if not self.win_controller.find_and_click(area_image_map[target_area], timeout=1):
            self.logger.warning(f"未找到目标区域入口: {target_area}")
            return False

        self.logger.info(f"已切换到: {target_area}")
        return True

    def _on_map(self, point):
        """战报页面标识回调"""
        pass  # 静默处理，不干扰主流程

    def _on_map_exit(self, point):
        """战报退出按钮回调"""
        self.bg_left_click(point)

    def _on_confirm(self, point):
        """确认框回调"""
        self.bg_left_click(point)

    def _on_wait_to_start(self, point):
        """等待开始回调"""
        pass  # 静默等待

    def _on_change_area(self, point):
        """更换领域按钮回调"""
        self.bg_left_click(point)

    def _on_dragon_area(self, point):
        """神龙暗域标识回调"""
        self._current_area = "abyss_dragon"

    def _on_peacock_area(self, point):
        """孔雀暗域标识回调"""
        self._current_area = "abyss_peacock"

    def _on_fox_area(self, point):
        """白藏主暗域标识回调"""
        self._current_area = "abyss_fox"

    def _on_leopard_area(self, point):
        """黑豹暗域标识回调"""
        self._current_area = "abyss_leopard"


    def on_run(self) -> None:
        """启动时调用"""
        super().on_run()
        self.win_controller.update_screenshot_cache()
        detection = self.scene_manager.detect_current_scene()
        current_scene = detection.scene_name if detection is not None else None

        if current_scene in self.scene_name_list:
            self.cur_scene_index = self.scene_name_list.index(current_scene)
            self._current_area = current_scene
            self._state = AbyssShadowsState.SCENE
            self.logger.info(f"已在狭间暗域区域: {current_scene}")
            return

        if current_scene == "abyss_enemy_selection":
            self._state = AbyssShadowsState.ENEMY_SELECTION
            self.logger.info("已在狭间暗域敌人选择界面")
            return

        if current_scene == "battling":
            self.logger.error("当前处于战斗中，请等待战斗安全结束后重试")
            self.stop()
            return

        if current_scene not in {"home", "abyss_selection"}:
            self.logger.error(f"无法从当前场景启动狭间暗域: {current_scene or 'unknown'}")
            self.stop()
            return

        if current_scene == "home" and not self.goto_abyss_shadows():
            self.logger.error("未能从 Home 进入狭间暗域，停止脚本")
            self.stop()
            return
        if not self.scene_manager.goto_scene("abyss_dragon"):
            self.logger.error("未能进入神龙暗域，停止脚本")
            self.stop()


if __name__ == '__main__':
    main = Main()
    main.run()
    # main.change_area(main.scene_name_list[3])
