import time
from enum import Enum
from typing import Optional

from win_util.common_util import random_sleep
from win_util.image import ImageMatchConfig
from win_util.ocr import CommonOcr
from yys.event_script_base import YYSBaseScript


class EnemyType(Enum):
    BOSS = 0 # 首领
    COMMANDER = 1 # 副将
    ELITE = 2 # 精英


class Enemy:
    def __init__(self, enemy_type: EnemyType, reach_damage_quit: int,
                 image_path: str, label_position: tuple[int, int, int, int], has_challenged: bool=False):
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


class Main(YYSBaseScript):
    """
    狭间暗域
    """

    def __init__(self):
        super().__init__("狭间暗域")

        self.cur_enemy: Optional[Enemy] = None  # 当前战斗的敌人类型
        self.cur_scene_index = 0
        self.scene_name_list = ["rifts_shadows_dragon", "rifts_shadows_hakuzosu", "rifts_shadows_panther", "rifts_shadows_peacock"]

        commander_damage_limit = 33700000
        elite_damage_limit = 5000000

        self.enemies = {
            EnemyType.BOSS: [
                Enemy(
                    enemy_type=EnemyType.BOSS,
                    reach_damage_quit=1,
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
        self._register_image_match_event(ImageMatchConfig("yys/images/scene/rifts_shadows_selection.bmp"),
                                         self._on_rifts_shadows_selection)
        self._register_image_match_event(ImageMatchConfig("yys/images/scene/rifts_shadows_enemy_selection.bmp"),
                                         self._on_rifts_shadows_enemy_selection)
        self._register_image_match_event(ImageMatchConfig("yys/rifts_shadows/images/battle_report_button.bmp"),
                                         self._on_battle_report_button)
        # 战斗中
        self._register_image_match_event(ImageMatchConfig("yys/rifts_shadows/images/battle_button.bmp"), self._on_battle_button)
        self._register_image_match_event(ImageMatchConfig("yys/rifts_shadows/images/go_to_button.bmp"), self._on_battle_button)
        self._register_image_match_event(ImageMatchConfig("yys/images/ready.bmp"), self.bg_left_click)

        # 这段必须在最后
        self._register_image_match_event(ImageMatchConfig("yys/images/scene/battling.bmp"), self._on_battling)

    def _on_rifts_shadows_selection(self, point):
        self.scene_manager.goto_scene(self.scene_name_list[self.cur_scene_index])

    def _on_rifts_shadows_enemy_selection(self, point):
        enemy = self.get_first_can_challenge_enemy()
        if enemy is None:
            if self.cur_scene_index >= len(self.scene_name_list):
                self.logger.warning("没有可以打的狭间暗域了")
                return False
            self.win_controller.key_down("esc")
            random_sleep(0.5, 1)
            # 换场景
            self.scene_manager.click_return()
            random_sleep(1, 1.5)
            self.cur_scene_index += 1
            self.scene_manager.goto_scene(self.scene_name_list[self.cur_scene_index])
            # 重置 enemies.has_challenged
            for enemy_type in EnemyType:
                for enemy in self.enemies[enemy_type]:
                    enemy.has_challenged = False
            return False
        positions = enemy.label_and_pic_position
        point = self.win_controller.find_image_with_timeout(enemy.image_path, x0=positions[0], y0=positions[1],
                                                            x1=positions[2], y1=positions[3], timeout=1)
        if point is None or point == (-1, -1):
            return False
        self.bg_left_click((point[0] + 60, point[1]), x_range=5, y_range=5)
        has_killed = False
        for i in range(0, 5):
            if self.ocr.contains_text(self.image_finder.screenshot_cache, "已被击破"):
                has_killed = True
                break
            time.sleep(0.1)
        if has_killed:
            return False
        random_sleep(1, 2)
        # 挑战
        if not self.win_controller.find_and_click("yys/rifts_shadows/images/challenge_button.bmp"):
            return False
        enemy.has_challenged = True
        self.cur_enemy = enemy
        self.challenge_counts[enemy.enemy_type] += 1
        return True

    def _on_battle_report_button(self, point):
        """
        战报
        """
        self.bg_left_click(point)

    def get_first_can_challenge_enemy(self):
        for enemy_type in EnemyType:
            enemies_of_type = self.enemies[enemy_type]
            if self.challenge_counts[enemy_type] >= self.max_challenge_counts[enemy_type]:
                continue
            for enemy in enemies_of_type:
                if enemy.has_challenged:
                    continue
                position = enemy.label_and_pic_position
                ocr_results = self.ocr.find_all_texts(
                    self.image_finder.crop_screenshot_cache(position[0], position[1], position[2], position[3]),
                    similarity_threshold=0.2)
                # TODO: 识别已击破
                if ocr_results is not None:
                    for ocr_text in ocr_results:
                        if "已击破" in ocr_text:
                            enemy.has_challenged = True
                            break
                    if enemy.has_challenged:
                        continue
                return enemy
        return None

    def _on_battle_button(self, point):
        self.bg_left_click(point)

    def _on_battling(self, point):
        # sleep 1s，减轻压力
        time.sleep(1)
        if self.cur_enemy is None:
            return False
        # ocr 检查伤害（识别不是很准）
        ocr_result = self.ocr.find_all_texts(self.image_finder.crop_screenshot_cache(3, 99, 283, 143),
                                             similarity_threshold=0.2, allowlist='0123456789')
        if ocr_result is None or len(ocr_result) != 1:
            return False

        try:
            damage = int(ocr_result[0])
        except Exception:
            damage = 0
        if damage > self.cur_enemy.reach_damage_quit:
            # 退出战斗
            self.win_controller.key_down("esc")
            random_sleep(1, 1.5)
            self.win_controller.key_down("enter")
            self.cur_enemy = None
            return True

    def _on_zhan_dou_wan_cheng_victory(self, point):
        super()._on_zhan_dou_wan_cheng_victory(point)
        self._cur_battle_count += 1
        self.log_battle_count()

    def on_run(self):
        super().on_run()
        self.scene_manager.goto_scene("rifts_shadows_dragon")


if __name__ == '__main__':
    main = Main()
    main.run()
