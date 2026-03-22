import random
import time
from enum import Enum
from typing import Optional

from win_util.image import ImageMatchConfig, to_project_path
from yys.common.event_script_base import YYSBaseScript


def random_sleep(min_val: float, max_val: float) -> None:
    """随机等待一段时间"""
    sleep_seconds = random.uniform(min_val, max_val)
    time.sleep(sleep_seconds)


class EnemyType(Enum):
    BOSS = 0  # 首领
    COMMANDER = 1  # 副将
    ELITE = 2  # 精英


class Enemy:
    def __init__(self, enemy_type: EnemyType, reach_damage_quit: int,
                 image_path: str, label_position: tuple[int, int, int, int], has_challenged: bool = False):
        """

        :param enemy_type:
        :param reach_damage_quit:
        :param image_path:
        :param label_position: 元组：(左上x，左上y，右下x，右下y)
        """
        self.enemy_type = enemy_type
        self.reach_damage_quit = reach_damage_quit
        self.image_path = image_path
        self.label_and_pic_position = label_position
        self.has_challenged = has_challenged


class RiftsShadowsState(Enum):
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

    def __init__(self):
        super().__init__("狭间暗域")

        # 注册狭间暗域专属场景和跳转
        self.scene_manager.register_scenes_from_directory(
            to_project_path("yys/rifts_shadows/images/scene/"),
            to_project_path("yys/rifts_shadows/images/scene_control/")
        )

        # 状态机
        self._state = RiftsShadowsState.SELECTION
        self._cur_enemy: Optional[Enemy] = None  # 当前战斗的敌人
        self._last_damage_check_time = 0.0  # 上次伤害检查时间
        self._damage_check_interval = 0.5  # 伤害检查间隔（秒）

        # 场景索引（4个暗域轮换）
        self.cur_scene_index = 0
        self.scene_name_list = ["abyss_dragon", "abyss_fox", "abyss_leopard", "abyss_peacock"]
        self._current_area: Optional[str] = None  # 当前暗域区域

        # 伤害阈值
        commander_damage_limit = 33700000
        elite_damage_limit = 5000000

        # 敌人配置（固定位置）
        self.enemies = {
            EnemyType.BOSS: [
                Enemy(
                    enemy_type=EnemyType.BOSS,
                    reach_damage_quit=999999999,  # 首领不设上限
                    image_path="yys/rifts_shadows/images/boss_label.bmp",
                    label_position=(554, 120, 688, 210),
                    has_challenged=True
                )
            ],
            EnemyType.COMMANDER: [
                Enemy(
                    enemy_type=EnemyType.COMMANDER,
                    reach_damage_quit=commander_damage_limit,
                    image_path="yys/rifts_shadows/images/commander_label.bmp",
                    label_position=(424, 250, 558, 335),
                    has_challenged=True
                ),
                Enemy(
                    enemy_type=EnemyType.COMMANDER,
                    reach_damage_quit=commander_damage_limit,
                    image_path="yys/rifts_shadows/images/commander_label.bmp",
                    label_position=(700, 250, 833, 335),
                    has_challenged=True
                )
            ],
            EnemyType.ELITE: [
                Enemy(
                    enemy_type=EnemyType.ELITE,
                    reach_damage_quit=elite_damage_limit,
                    image_path="yys/rifts_shadows/images/elite_label.bmp",
                    label_position=(342, 360, 480, 435)
                ),
                Enemy(
                    enemy_type=EnemyType.ELITE,
                    reach_damage_quit=elite_damage_limit,
                    image_path="yys/rifts_shadows/images/elite_label.bmp",
                    label_position=(554, 360, 691, 435)
                ),
                Enemy(
                    enemy_type=EnemyType.ELITE,
                    reach_damage_quit=elite_damage_limit,
                    image_path="yys/rifts_shadows/images/elite_label.bmp",
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
            ImageMatchConfig("yys/rifts_shadows/images/scene/abyss_selection.bmp"),
            self._on_rifts_shadows_selection
        )
        # 敌人选择界面
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/scene/abyss_enemy_selection.bmp"),
            self._on_rifts_shadows_enemy_selection
        )
        # 战报按钮
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/abyss_navigation.bmp"),
            self._on_battle_report_button
        )
        # 战斗按钮
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/battle_button.bmp"),
            self._on_battle_button
        )
        # 前往按钮
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/abyss_goto_enemy.bmp"),
            self._on_go_to_button
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
            self._on_battle_end
        )
        self._register_image_match_event(
            ImageMatchConfig("yys/images/battle_end_loss.bmp"),
            self._on_battle_end
        )
        self._register_image_match_event(
            ImageMatchConfig("yys/images/battle_end.bmp"),
            self._on_battle_end
        )
        # 新增：战报页面标识
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/abyss_map.bmp"),
            self._on_abyss_map
        )
        # 新增：战报退出
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/abyss_map_exit.bmp"),
            self._on_abyss_map_exit
        )
        # 新增：确认框
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/abyss_confirm.bmp"),
            self._on_confirm
        )
        # 新增：等待开始
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/wait_to_start.bmp"),
            self._on_wait_to_start
        )
        # 新增：更换领域
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/change_area.bmp"),
            self._on_change_area
        )

    def _register_battle_report_events(self):
        """注册战报界面相关事件"""
        # 神龙暗域标识
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/dragon_area.bmp"),
            self._on_dragon_area
        )
        # 孔雀暗域标识
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/peacock_area.bmp"),
            self._on_peacock_area
        )
        # 白藏主暗域标识
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/fox_area.bmp"),
            self._on_fox_area
        )
        # 黑豹暗域标识
        self._register_image_match_event(
            ImageMatchConfig("yys/rifts_shadows/images/leopard_area.bmp"),
            self._on_leopard_area
        )

    # ==================== 场景事件处理 ====================

    def _on_rifts_shadows_selection(self, point):
        """狭间暗域主界面"""
        self._state = RiftsShadowsState.SELECTION
        self.scene_manager.goto_scene(self.scene_name_list[self.cur_scene_index])

    def _on_rifts_shadows_enemy_selection(self, point) -> bool:
        """敌人选择界面"""
        self._state = RiftsShadowsState.ENEMY_SELECTION
        enemy = self.get_next_enemy()
        if enemy is None:
            self._handle_no_enemy_available()
            return False
        self._select_enemy(enemy)
        return True

    def _handle_no_enemy_available(self):
        """处理没有可挑战敌人的情况"""
        if self.cur_scene_index >= len(self.scene_name_list):
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
        if not self.win_controller.find_and_click("yys/rifts_shadows/images/abyss_navigation.bmp"):
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
        if not self.win_controller.find_and_click("yys/rifts_shadows/images/abyss_goto_enemy.bmp"):
            self.logger.warning("未找到前往按钮")
            return False

        # 处理跨区域确认框
        random_sleep(0.5, 1)
        self.win_controller.find_and_click("yys/rifts_shadows/images/abyss_confirm.bmp")
        random_sleep(1, 2)

        # 点击挑战按钮
        if not self.win_controller.find_and_click("yys/rifts_shadows/images/abyss_challenge.bmp"):
            self.logger.warning("未找到挑战按钮")
            return False

        # 处理奖励次数上限确认框
        random_sleep(0.5, 1)
        self.win_controller.find_and_click("yys/rifts_shadows/images/abyss_confirm.bmp")

        self.logger.info(f"已开始挑战: {enemy.enemy_type}")
        return True

    def _select_enemy(self, enemy: Enemy):
        """选择敌人并进入战斗"""
        if self.click_enemy_area(enemy):
            enemy.has_challenged = True
            self._cur_enemy = enemy
            self.challenge_counts[enemy.enemy_type] += 1
            self._state = RiftsShadowsState.BATTLE

    def get_next_enemy(self) -> Optional[Enemy]:
        """获取下一个可挑战的敌人（优先级：首领>副将>精英）"""
        for enemy_type in [EnemyType.BOSS, EnemyType.COMMANDER, EnemyType.ELITE]:
            if self.challenge_counts[enemy_type] >= self.max_challenge_counts[enemy_type]:
                continue
            for enemy in self.enemies[enemy_type]:
                if enemy.has_challenged:
                    continue
                # TODO: OCR 识别"已击破"状态，暂留后续优化
                # 目前简化判断，只检查 has_challenged 标志
                return enemy
        return None

    # ==================== 战报界面事件处理 ====================

    def _on_battle_report_button(self, point):
        """点击战报按钮"""
        self._state = RiftsShadowsState.BATTLE_REPORT
        self.bg_left_click(point)

    def _on_battle_report_current(self, point):
        """战报界面 - 当前暗域（有可打目标）"""
        self._state = RiftsShadowsState.BATTLE_REPORT
        self.bg_left_click(point)
        # 点击后应该进入敌人选择界面
        random_sleep(0.5, 1)

    def _on_battle_report_other(self, point):
        """战报界面 - 其他暗域（需切换）"""
        self._state = RiftsShadowsState.BATTLE_REPORT
        self.bg_left_click(point)
        # 切换到其他暗域页签后，会再次检测战报界面
        random_sleep(0.5, 1)

    def _on_abyss_map(self, point):
        """战报页面标识回调"""
        pass  # 静默处理，不干扰主流程

    def _on_abyss_map_exit(self, point):
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

    # ==================== 战斗相关事件处理 ====================

    def _on_battle_button(self, point):
        """战斗按钮"""
        self.bg_left_click(point)

    def _on_go_to_button(self, point):
        """前往按钮"""
        self.bg_left_click(point)

    def _on_battling(self, point):
        """战斗中 - 伤害监控"""
        current_time = time.time()

        # 检查是否在伤害检查间隔内
        if current_time - self._last_damage_check_time < self._damage_check_interval:
            return False

        self._last_damage_check_time = current_time

        if self._cur_enemy is None:
            return False

        # OCR 检查伤害
        current_damage = self._get_current_damage()
        if current_damage > self._cur_enemy.reach_damage_quit:
            self._exit_battle()
            return True

        return False

    def _get_current_damage(self) -> int:
        """OCR 获取当前伤害"""
        ocr_result = self.ocr.find_all_texts(
            self.image_finder.crop_screenshot_cache(3, 99, 283, 143),
            similarity_threshold=0.2,
            allowlist='0123456789'
        )
        if ocr_result is None or len(ocr_result) != 1:
            return 0
        try:
            return int(ocr_result[0])
        except (ValueError, TypeError):
            return 0

    def _exit_battle(self):
        """退出战斗（Esc + Enter）"""
        self.win_controller.key_down("esc")
        random_sleep(0.5, 1)
        self.win_controller.key_down("enter")
        self._cur_enemy = None
        self._state = RiftsShadowsState.BATTLE_REPORT

    def _on_battle_end(self, point):
        """战斗结束"""
        self._state = RiftsShadowsState.BATTLE_END
        self.bg_left_click(point)
        self._cur_enemy = None

    # ==================== OCR 相关（暂留优化） ====================

    def _is_enemy_defeated(self, position: tuple[int, int, int, int]) -> bool:
        """
        OCR 判断敌人是否已击破
        TODO: 暂留后续优化
        """
        ocr_results = self.ocr.find_all_texts(
            self.image_finder.crop_screenshot_cache(*position),
            similarity_threshold=0.2
        )
        if ocr_results is not None:
            for ocr_text in ocr_results:
                if "已击破" in ocr_text:
                    return True
        return False

    def _is_current_tab(self) -> bool:
        """
        OCR 判断是否为当前暗域
        TODO: 暂留后续优化
        """
        # 暂不实现
        return True

    # ==================== 生命周期方法 ====================

    def _on_zhan_dou_wan_cheng_victory(self, point):
        """战斗胜利回调"""
        super()._on_zhan_dou_wan_cheng_victory(point)
        self._cur_battle_count += 1
        self.log_battle_count()

    def goto_abyss_shadows(self) -> bool:
        """
        进入狭间暗域

        流程：主界面 → 神社入口 → 滑到狭间暗域 → 点击进入

        Returns:
            bool: 进入成功返回 True
        """
        # 点击神社入口
        if not self.win_controller.find_and_click("yys/rifts_shadows/images/ryou_shenshe.bmp"):
            self.logger.warning("未找到神社入口")
            return False

        random_sleep(0.5, 1)

        # 滑动到狭间暗域（从神社向右滑，贝塞尔曲线防封）
        self.mouse.bg_swipe(800, 400, 200, 400, steps=20, duration=0.6, curve_factor=0.35)
        random_sleep(1, 1.5)

        # 点击狭间暗域入口
        if not self.win_controller.find_and_click("yys/rifts_shadows/images/abyss_shadows.bmp"):
            self.logger.warning("未找到狭间暗域入口")
            return False

        self.logger.info("已进入狭间暗域")
        return True

    def check_current_area(self) -> Optional[str]:
        """
        检查当前暗域区域

        Returns:
            str or None: 当前区域名称，如 "abyss_dragon"，未识别到返回 None
        """
        area_mappings = [
            ("yys/rifts_shadows/images/dragon_area.bmp", "abyss_dragon"),
            ("yys/rifts_shadows/images/fox_area.bmp", "abyss_fox"),
            ("yys/rifts_shadows/images/leopard_area.bmp", "abyss_leopard"),
            ("yys/rifts_shadows/images/peacock_area.bmp", "abyss_peacock"),
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
        if self.win_controller.find_and_click("yys/rifts_shadows/images/abyss_map_exit.bmp"):
            random_sleep(0.5, 1)

        # 点击更换领域按钮
        if not self.win_controller.find_and_click("yys/rifts_shadows/images/change_area.bmp"):
            self.logger.warning("未找到更换领域按钮")
            return False

        random_sleep(1, 1.5)

        # 选择目标暗域入口
        area_image_map = {
            "abyss_dragon": "yys/rifts_shadows/images/abyss_dragon.bmp",
            "abyss_fox": "yys/rifts_shadows/images/abyss_fox.bmp",
            "abyss_leopard": "yys/rifts_shadows/images/abyss_leopard.bmp",
            "abyss_peacock": "yys/rifts_shadows/images/abyss_peacock.bmp",
        }

        if target_area not in area_image_map:
            self.logger.warning(f"未知区域: {target_area}")
            return False

        if not self.win_controller.find_and_click(area_image_map[target_area]):
            self.logger.warning(f"未找到目标区域入口: {target_area}")
            return False

        self.logger.info(f"已切换到: {target_area}")
        return True

    def on_run(self):
        """启动时调用"""
        super().on_run()
        self.scene_manager.goto_scene("abyss_dragon")


if __name__ == '__main__':
    main = Main()
    main.run()
