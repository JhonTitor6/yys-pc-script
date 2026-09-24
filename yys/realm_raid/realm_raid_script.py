from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Optional, TYPE_CHECKING, TypedDict, get_type_hints

import cv2

# 仅在本脚本作为 __main__ 进程运行时生效：在父类 from-import 之前修改包级属性，
# 让 YYSBaseScript 的 BATTLE_END_CLICK_SLEEP 绑定为 3。其他独立脚本进程不受影响。
import yys.common as _yys_common
from win_util.image import ImageMatchConfig

_yys_common.BATTLE_END_CLICK_SLEEP = 3

from yys.common.event_script_base import YYSBaseScript, _extract_config_meta, random_sleep  # noqa: E402
from yys.common.script_meta import ConfigMeta, ScriptMeta  # noqa: E402

if TYPE_CHECKING:
    from tests.common.environment.base import GameEnvironment

"""
结界突破脚本，使用事件驱动模式
"""


@dataclass(frozen=True)
class RealmTarget:
    """单个结界目标及其在九宫格中的位置。"""

    row: int
    col: int
    point: tuple[int, int]


@dataclass
class RealmRaidRoundState:
    """当前九宫格的执行状态。"""

    generation: int = 1
    victory_count_at_start: int = 0
    quit_three_completed: bool = False
    attempted_cells: set[tuple[int, int]] = field(default_factory=set)
    current_cell: Optional[tuple[int, int]] = None
    no_target_observations: int = 0
    retry_count: int = 0


class RealmRaidStopReason(str, Enum):
    """结界突破主动停机原因。"""

    TICKET_NOT_ENOUGH = "ticket_not_enough"
    RETRY_FAILED = "retry_failed"
    BATTLE_NOT_READY = "battle_not_ready"
    REFRESH_FAILED = "refresh_failed"
    REFRESH_RESULT_EMPTY = "refresh_result_empty"
    NO_ATTACKABLE_TARGET = "no_attackable_target"
    MAX_BATTLE_COUNT = "max_battle_count"


class RealmRaidConfig(TypedDict, total=False):
    """结界突破脚本的可配置字段。"""
    max_battle_count: Annotated[int, ConfigMeta(
        default=30,
        min_value=1,
        max_value=99,
        field_type="number",
        label="最大战斗次数",
        group="基础",
        help="脚本自动停止前执行的最大战斗次数（1-99）",
        hot_reloadable=True,
    )]
    quit_3_times_config: Annotated[bool, ConfigMeta(
        default=True,
        field_type="checkbox",
        label="首次退3次",
        group="高级",
        help="打第一个结界时是否先退出3次再挑战",
        hot_reloadable=False,
    )]


class RealmRaidScript(YYSBaseScript):
    """结界突破脚本：循环攻击可攻击的结界。"""
    BATTLE_TRANSITION_GRACE_SECONDS = 12.0
    BATTLE_SETTLEMENT_GRACE_SECONDS = 5.0
    # 可攻击但已尝试结界的最多重试次数（点击未生效进入不了挑战时重试）
    MAX_TARGET_RETRY_COUNT = 3
    SCRIPT_META = ScriptMeta(
        display_name="结界突破",
        category="日常",
        config_schema=RealmRaidConfig,
        default_config={"max_battle_count": 30, "quit_3_times_config": True},
    )
    # 入口场景：结界突破界面
    entry_scene: Optional[str] = "barrier_breakthrough"

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
        script_name: str = "realm_raid",
        env: Optional["GameEnvironment"] = None,
        config: Optional[dict] = None,
    ) -> None:
        """初始化结界突破脚本。

        Args:
            script_name: 脚本名，默认 "realm_raid"。
            env: GameEnvironment 实例，用于 Mock 测试时注入。
            config: 配置字典（可选）。
        """
        super().__init__(script_name, config=config, env=env)

        self.attackable_barrier_list: list[RealmTarget] = []
        self.round_state = RealmRaidRoundState()
        self.stop_reason: Optional[RealmRaidStopReason] = None
        self._battle_result_armed = False

        # 注册结界突破特定的图像匹配事件
        self._register_image_match_event(ImageMatchConfig("yys/realm_raid/images/realm_raid_not_enough.bmp", similarity=0.85),
                                         self._on_ticket_not_enough)
        # 注册挑战相关的事件
        self._register_image_match_event(ImageMatchConfig("yys/realm_raid/images/realm_raid_jingong.bmp"), self._on_attack) 
        self._register_image_match_event(ImageMatchConfig("yys/realm_raid/images/realm_raid_user_realm.bmp"),
                                         self._on_attackable_barrier)
        self._register_image_match_event(
            ImageMatchConfig(
                "yys/realm_raid/images/realm_raid_battling.bmp",
                x0=0,
                y0=520,
                x1=130,
                y1=640,
            ),
            self._on_battling,
        )
        # 检测是不是没有可以挑战的了
        self._register_image_match_event(ImageMatchConfig("yys/common/images/scene/barrier_breakthrough.bmp"),
                                         self.on_scene_barrier_breakthrough)

    def _on_ticket_not_enough(self, _point: tuple[int, int]) -> None:
        """突破券不足时立即停止，避免事件被重复触发。"""
        self.max_battle_count = self._cur_battle_count
        self._stop_with_reason(RealmRaidStopReason.TICKET_NOT_ENOUGH)

    def _on_attackable_barrier(self, _point: tuple[int, int]) -> None:
        """按从左到右、从上到下的顺序选择本轮尚未尝试的目标。"""
        # 点击前刷新截图缓存，避免基于陈旧画面定位
        self.win_controller.update_screenshot_cache()
        self.attackable_barrier_list = self.get_all_attackable_barrier()
        if self._is_automatic_new_round(self.attackable_barrier_list):
            self.logger.info("检测到攻略记录归零，开始自动换组后的新九宫格")
            self._start_new_round()
        target = next(
            (
                candidate
                for candidate in self.attackable_barrier_list
                if (candidate.row, candidate.col) not in self.round_state.attempted_cells
            ),
            None,
        )
        if target is None:
            if not self.attackable_barrier_list:
                self.round_state.no_target_observations += 1
                self.logger.info("当前九宫格没有可攻击的结界")
                if self.round_state.no_target_observations >= 3:
                    self._stop_with_reason(RealmRaidStopReason.NO_ATTACKABLE_TARGET)
                return
            # 有结界可攻击但均已尝试过：多半是上次点击未生效（未进入挑战），限次重试
            if self.round_state.retry_count >= self.MAX_TARGET_RETRY_COUNT:
                self._stop_with_reason(RealmRaidStopReason.NO_ATTACKABLE_TARGET)
                return
            target = self.attackable_barrier_list[0]
            self.round_state.retry_count += 1
            self.logger.info(
                f"可攻击结界均已尝试，重试第{self.round_state.retry_count}/"
                f"{self.MAX_TARGET_RETRY_COUNT}次"
            )
        else:
            self.round_state.no_target_observations = 0
            self.round_state.retry_count = 0
        cell = (target.row, target.col)
        self.round_state.current_cell = cell
        self.round_state.attempted_cells.add(cell)
        self.bg_left_click(target.point, x_range=5, y_range=5)
        random_sleep(1, 1.3)

    def get_all_attackable_barrier(self) -> list[RealmTarget]:
        """按行优先顺序获取所有可以挑战的结界。"""
        POSITION_1 = 125, 120, 425, 245

        x0_1, y0_1, x1_1, y1_1 = POSITION_1

        col_offset_x = 300
        row_offset_y = 120

        all_realms: list[RealmTarget] = []
        for row in range(3):
            for col in range(3):
                x0 = x0_1 + col * col_offset_x
                y0 = y0_1 + row * row_offset_y
                x1 = x1_1 + col * col_offset_x
                y1 = y1_1 + row * row_offset_y

                point = self.image_finder.bg_find_pic_by_cache(
                    "yys/realm_raid/images/realm_raid_user_realm.bmp",
                    x0=x0, y0=y0, x1=x1, y1=y1
                )
                self.logger.debug(f"第{row + 1}行第{col + 1}列的结界: ({x0}, {y0}, {x1}, {y1}) 坐标: {point}")
                if point is not None and point != (-1, -1):
                    all_realms.append(RealmTarget(row=row, col=col, point=point))

        self.logger.debug(f"找到{len(all_realms)}个结界")
        return all_realms

    def _is_automatic_new_round(self, visible_targets: list[RealmTarget]) -> bool:
        """依据胜场增长和攻略记录归零识别游戏自动换组。"""
        if not self.round_state.attempted_cells:
            return False
        if self._cur_battle_victory_count <= self.round_state.victory_count_at_start:
            return False
        point = self.image_finder.bg_find_pic_by_cache(
            "yys/realm_raid/images/realm_raid_record_zero.bmp",
            x0=0,
            y0=480,
            x1=280,
            y1=620,
        )
        if point is None or point == (-1, -1):
            return False
        return len(visible_targets) == 9

    def _on_attack(self, point: tuple[int, int]) -> None:
        """点击进攻；每个新九宫格只执行一次退三次流程。"""
        self._battle_result_armed = True
        self.bg_left_click(point, x_range=10, y_range=10)
        if not self.quit_3_times_config or self.round_state.quit_three_completed:
            self._allow_battle_transition()
            time.sleep(5)
            return
        if self.quit_3_times():
            self.round_state.quit_three_completed = True
            self._allow_battle_transition()

    def _on_battling(self, _point: tuple[int, int]) -> None:
        """确认战斗仍在进行，并为随后的结算动画保留短暂宽限。"""
        self._battle_result_armed = True
        if self._run_guard is not None:
            self._run_guard.allow_unknown_for(
                self.BATTLE_SETTLEMENT_GRACE_SECONDS,
            )

    def _should_count_battle_end(self, _point: tuple[int, int]) -> bool:
        """只把与本轮真实战斗关联的首个结算画面计入次数。"""
        if not self._battle_result_armed:
            self.logger.debug("忽略未关联战斗的奖励结算画面")
            return False
        self._battle_result_armed = False
        return True

    def _allow_battle_transition(self) -> None:
        """真实运行时容忍进攻后的短暂加载动画。"""
        if self._run_guard is not None:
            self._run_guard.allow_unknown_for(
                self.BATTLE_TRANSITION_GRACE_SECONDS,
            )

    def quit_3_times(self) -> bool:
        """执行三次退出并再次挑战；任一步失败都会安全停机。"""
        self.logger.info("准备退3次...")
        for i in range(0, 3):
            battle_point = self.image_finder.bg_find_pic_with_timeout(
                "yys/realm_raid/images/realm_raid_battling.bmp",
                timeout=self.BATTLE_TRANSITION_GRACE_SECONDS,
                x0=0, y0=520, x1=130, y1=640,
            )
            if battle_point is None or battle_point == (-1, -1):
                self._stop_with_reason(RealmRaidStopReason.BATTLE_NOT_READY)
                return False
            self.logger.info(f"退出第{i + 1}次")
            self.keyboard.bg_press_key('ESC')
            random_sleep(0.05, 0.2)
            self.keyboard.bg_press_key('ENTER')
            random_sleep(2, 3)
            self.logger.info("准备点击【再次挑战】")
            retry_clicked = self.win_controller.find_and_click(
                "yys/realm_raid/images/realm_raid_retry.bmp",
                timeout=5,
            )
            if not retry_clicked:
                self._stop_with_reason(RealmRaidStopReason.RETRY_FAILED)
                return False
            random_sleep(1, 2)
            self.logger.info("检查【今日不再提醒】")
            silence_point = self.image_finder.bg_find_pic_with_timeout("yys/realm_raid/images/realm_raid_retry_silence.bmp", timeout=2)
            if silence_point is not None and silence_point != (-1, -1):
                self.logger.info("点击【今日不再提醒】")
                random_sleep(1, 2)
                self.bg_left_click((494, 317), x_range=10, y_range=10)
                random_sleep(0.2, 0.6)
                self.bg_left_click((672, 379), y_range=10)
        self.logger.info("完成退3次")
        return True

    def on_scene_barrier_breakthrough(self, _point: tuple[int, int]) -> None:
        """在结界突破主界面检查是否需要刷新。"""
        self.refresh_if_no_attackable_barrier()

    def refresh_if_no_attackable_barrier(self) -> bool:
        """没有可挑战目标时刷新，并在新目标确认后开始下一轮。"""
        realm_list = self.image_finder.bg_find_pic_all_by_cache("yys/realm_raid/images/realm_raid_user_realm.bmp")
        if len(realm_list) > 0:
            return False

        self.logger.info("没有可以打的结界了，准备刷新")
        refresh_clicked = self.win_controller.find_and_click(
            "yys/realm_raid/images/realm_raid_refresh.bmp",
            x_range=10,
            y_range=10,
            timeout=1,
        )
        if not refresh_clicked:
            self._stop_with_reason(RealmRaidStopReason.REFRESH_FAILED)
            return False
        random_sleep(1, 1.5)

        self.win_controller.update_screenshot_cache()
        confirm_clicked = self.win_controller.find_and_click(
            "yys/realm_raid/images/realm_raid_refresh_confirm.bmp",
            x_range=10,
            y_range=10,
            timeout=1,
        )
        if not confirm_clicked:
            self._stop_with_reason(RealmRaidStopReason.REFRESH_FAILED)
            return False
        random_sleep(1, 1.5)

        self.win_controller.update_screenshot_cache()
        refreshed_targets = self.get_all_attackable_barrier()
        if not refreshed_targets:
            self._stop_with_reason(RealmRaidStopReason.REFRESH_RESULT_EMPTY)
            return False
        self.attackable_barrier_list = refreshed_targets
        self._start_new_round()
        self.logger.info("刷新完成")
        return True

    def _start_new_round(self) -> None:
        """手动刷新或自动换组成功后重置九宫格级状态。"""
        self.round_state = RealmRaidRoundState(
            generation=self.round_state.generation + 1,
            victory_count_at_start=self._cur_battle_victory_count,
        )

    def _stop_with_reason(self, reason: RealmRaidStopReason) -> None:
        """记录可诊断的原因并停止脚本。"""
        self.stop_reason = reason
        self.logger.warning(f"结界突破停止: {reason.value}")
        if reason in {RealmRaidStopReason.RETRY_FAILED, RealmRaidStopReason.BATTLE_NOT_READY}:
            try:
                frame = self.image_finder.screenshot_cache
                if frame is not None:
                    path = Path(tempfile.gettempdir()) / "yys" / "realm_raid" / "last_failure.png"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if cv2.imwrite(str(path), frame):
                        self.logger.warning(f"失败画面已保存: {path}")
                    else:
                        self.logger.warning(f"失败画面保存失败: {path}")
                else:
                    self.logger.warning("失败画面不可用：截图缓存为空")
            except Exception:
                self.logger.exception("保存结界突破失败画面时出错")
        self.stop()

    def get_state_snapshot(self) -> dict[str, object]:
        """返回包含九宫格进度和停机原因的状态快照。"""
        snapshot = super().get_state_snapshot()
        snapshot.update({
            "round_generation": self.round_state.generation,
            "round_victory_count_at_start": self.round_state.victory_count_at_start,
            "quit_three_completed": self.round_state.quit_three_completed,
            "attempted_target_count": len(self.round_state.attempted_cells),
            "retry_count": self.round_state.retry_count,
            "current_cell": self.round_state.current_cell,
            "no_target_observations": self.round_state.no_target_observations,
            "stop_reason": self.stop_reason.value if self.stop_reason else None,
        })
        return snapshot

    def on_run(self) -> None:
        """初始化本次运行状态；入口场景由父类统一跳转。"""
        super().on_run()
        self.attackable_barrier_list = []
        self.round_state = RealmRaidRoundState()
        self.stop_reason = None
        self._battle_result_armed = False

    def after_iteration(self) -> None:
        """胜利次数达到目标后停止，失败不推进 RealmRaid 达标条件。"""
        random_sleep(0.05, 0.1)
        if (
            self._cur_battle_victory_count >= self.max_battle_count
            and self.stop_reason is None
        ):
            self._stop_with_reason(RealmRaidStopReason.MAX_BATTLE_COUNT)


if __name__ == '__main__':
    RealmRaidScript().run()
