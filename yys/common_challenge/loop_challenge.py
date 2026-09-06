from __future__ import annotations

import random
import time
from typing import Annotated, Any, Optional, TYPE_CHECKING, TypedDict, get_type_hints

from win_util.event import ImageMatchConfig
from yys.common.event_script_base import YYSBaseScript, _extract_config_meta
from yys.common.script_meta import ConfigMeta, ScriptMeta

if TYPE_CHECKING:
    from tests.common.environment.base import GameEnvironment


class LoopChallengeConfig(TypedDict, total=False):
    """通用挑战脚本的可配置字段。"""
    max_battle_count: Annotated[int, ConfigMeta(
        default=1782,
        min_value=1,
        max_value=9999,
        field_type="number",
        label="最大战斗次数",
        group="基础",
        help="脚本自动停止前执行的最大战斗次数（1-9999）",
        hot_reloadable=True,
    )]


class LoopChallenge(YYSBaseScript):
    """通用挑战脚本：循环点击挑战按钮。

    特性：每运行 200~300 次战斗后自动休息 1~3 分钟（60~180 秒）。
    - 触发阈值与休息时长每次随机化，避免被检测规律
    - 休息分段 sleep，最长 5 秒内可响应 stop 信号
    """
    SCRIPT_META = ScriptMeta(
        display_name="通用挑战",
        category="日常",
        config_schema=LoopChallengeConfig,
        default_config={"max_battle_count": 1782},
    )

    # 休息触发阈值范围（战斗次数）
    REST_TRIGGER_MIN = 200
    REST_TRIGGER_MAX = 300
    # 休息时长范围（秒）：1~3 分钟
    REST_DURATION_MIN_SEC = 60
    REST_DURATION_MAX_SEC = 180
    # 分段 sleep 长度（秒），控制 stop 响应延迟
    REST_SLEEP_SEGMENT = 5.0

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
        script_name: str = "loop_challenge",
        env: Optional["GameEnvironment"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """初始化通用挑战脚本。

        Args:
            script_name: 脚本名，默认 "loop_challenge"。
            env: GameEnvironment 实例，用于 Mock 测试时注入。
            config: 配置字典（可选）。
        """
        super().__init__(script_name, config=config, env=env)
        self._register_image_match_event(ImageMatchConfig("yys/common_challenge/images/challenge.bmp"), self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/common_challenge/images/region_challenge.bmp"), self.bg_left_click)
        self._register_image_match_event(ImageMatchConfig("yys/common_challenge/images/gained_reward.bmp"), self._on_battle_end)
        self._reset_rest_state()

    def on_run(self):
        """脚本启动钩子（实现抽象基类要求）"""
        super().on_run()

    def _on_battle_end(self, point: tuple):
        """战斗结束处理：累计次数，达到阈值时休息。"""
        super()._on_battle_end((960, 535))
        self._battles_since_rest += 1
        if self._battles_since_rest >= self._rest_every_n:
            self._take_rest()
            self._battles_since_rest = 0
            old_threshold = self._rest_every_n
            self._reset_rest_state()
            self.logger.info(
                f"休息结束，下次触发阈值由 {old_threshold} 更新为 {self._rest_every_n}"
            )

    def _reset_rest_state(self):
        """（重新）随机化休息阈值并清零计数。"""
        self._rest_every_n = random.randint(
            self.REST_TRIGGER_MIN, self.REST_TRIGGER_MAX
        )
        self._battles_since_rest = 0
        self.logger.info(
            f"休息策略已重置：每 {self._rest_every_n} 次战斗休息一次"
        )

    def _take_rest(self):
        """执行休息：随机 1~3 分钟，分段 sleep 以便 stop 立即生效。"""
        duration = random.randint(
            self.REST_DURATION_MIN_SEC,
            self.REST_DURATION_MAX_SEC
        )
        self.logger.info(
            f"已累计 {self._battles_since_rest} 次战斗，开始休息 {duration} 秒"
        )
        elapsed = 0.0
        segment = self.REST_SLEEP_SEGMENT
        while elapsed < duration:
            sleep_time = min(segment, duration - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time
            if self._stop_threading_event.is_set():
                self.logger.info("休息期间收到停止信号，提前结束休息")
                return


if __name__ == '__main__':
    LoopChallenge().set_max_battle_count(1782).run()
