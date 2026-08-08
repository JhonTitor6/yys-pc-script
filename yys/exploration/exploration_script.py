from __future__ import annotations

import random
import time
from typing import Annotated, Any, Optional, TYPE_CHECKING, TypedDict, get_type_hints

from win_util.mouse import bg_left_click, bg_left_click_with_range
from yys.common.event_script_base import YYSBaseScript, ImageMatchConfig, _extract_config_meta, random_sleep
from yys.common.script_meta import ConfigMeta, ScriptMeta

if TYPE_CHECKING:
    from tests.common.environment.base import GameEnvironment


class ExplorationConfig(TypedDict, total=False):
    """探索脚本的可配置字段。"""
    max_battle_count: Annotated[int, ConfigMeta(
        default=244,
        min_value=1,
        max_value=9999,
        field_type="number",
        label="最大战斗次数",
        group="基础",
        help="脚本自动停止前执行的最大战斗次数（1-9999）",
        hot_reloadable=True,
    )]


class ExplorationScript(YYSBaseScript):
    """探索脚本：循环执行探索副本。"""
    SCRIPT_META = ScriptMeta(
        display_name="探索",
        category="日常",
        config_schema=ExplorationConfig,
        default_config={"max_battle_count": 244},
    )
    # 入口场景：探索地图-28 章已选中状态
    entry_scene: Optional[str] = "exploration_chapter_28"

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
        script_name: str = "exploration",
        env: Optional["GameEnvironment"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """初始化探索脚本。

        Args:
            script_name: 脚本名，默认 "exploration"。
            env: GameEnvironment 实例，用于 Mock 测试时注入。
            config: 配置字典（可选）。
        """
        super().__init__(script_name, config=config, env=env)
        self.logger.info("初始化探索脚本")

        # 没找到怪次数
        self.idle_count = 0

        # TODO: 图片匹配增加 场景（多个） 条件，当在某些场景下才进行匹配
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_boss_tiaozhan.bmp"),
                                         self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_tiaozhan.bmp"),
                                         self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_boss_success_reward.bmp"),
                                         self._on_tansuo_boss_success_reward)
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_bao_xiang.bmp"),
                                         self._on_tansuo_bao_xiang)
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_bao_xiang_2.bmp"),
                                         self._on_tansuo_bao_xiang)
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_kunnan.bmp"),
                                         self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_tansuo.bmp"),
                                         self._on_tansuo_entering)
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_28.bmp"),
                                         self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/exploration/images/exploration_she_zhi.bmp"),
                                         self._on_tansuo_idle)
        self._register_image_match_event(ImageMatchConfig("yys/common/images/temp_sui_pian.bmp"), self.bg_left_click)

        self.logger.info("探索脚本初始化完成")

    def _on_battle_end(self, point):
        """战斗结束处理"""
        super()._on_battle_end(point)
        random_sleep(1, 3)
        script_run_minutes = int((int(time.time() * 1000) - self.script_start_time_mills) / 1000 / 60)
        if script_run_minutes > 0 and script_run_minutes % 26 == 0:
            self.logger.info(f"已运行{script_run_minutes}分钟，随机休眠1-3分钟...")
            random_sleep(60, 180)

    def _on_tansuo_boss_success_reward(self, point):
        bg_left_click_with_range(self.hwnd, point, x_range=20, y_range=20)
        random_sleep(1, 1.6)
        bg_left_click(self.hwnd, random.randint(960, 1030), random.randint(450, 510))

    def _on_tansuo_bao_xiang(self, point):
        random_sleep(1, 2)
        tansuo_close_point = self.image_finder.bg_find_pic_by_cache("yys/exploration/images/exploration_close.bmp")
        if tansuo_close_point is not None and tansuo_close_point != (-1, -1):
            bg_left_click(self.hwnd, tansuo_close_point[0], tansuo_close_point[1])
        random_sleep(1, 1.6)
        bg_left_click_with_range(self.hwnd, point)

    def _on_tansuo_entering(self, point):
        self.bg_left_click(point)
        time.sleep(0.5)
        self.image_finder.update_screenshot_cache()
        if self.ocr.contains_text(self.image_finder.screenshot_cache, "己达本日上限"):
            self.stop()

    def _on_tansuo_idle(self, point):
        self.idle_count += 1
        if self.idle_count >= 3:
            self.idle_count = 0
            # 向右移动
            self.mouse.bg_left_click_with_range((1000, 490))
            self.logger.debug("没有找到挑战按钮，往右移动...")
            random_sleep(1, 3)

    def on_run(self):
        super().on_run()
        self.idle_count = 0
        self.scene_manager.goto_scene("exploration")


if __name__ == '__main__':
    script = ExplorationScript()
    script.set_max_battle_count(244)
    script.run()
