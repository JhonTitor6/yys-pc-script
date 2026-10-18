"""官方一键收菜真实帧识别与受保护流程回归。"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Callable

import cv2
import pytest
from PIL import Image

from tests.common.environment.mock_environment import MockEnvironment
from tests.common.providers.file_image_provider import FileImageProvider
from win_util.environment.guarded import GuardedEnvironment, RunGuard
from win_util.image import ImageFinder
from yys.daily_collect import DailyCollectScript


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/daily_collect"


def _frame(name: str) -> Image.Image:
    """读取一张脱敏录制帧。"""
    with Image.open(FIXTURES / name) as image:
        return image.convert("RGB").copy()


class _FrameEnvironment(MockEnvironment):
    """逐帧回放输入并记录脚本点击，不连接真实游戏。"""

    def __init__(self, frames: list[str]) -> None:
        super().__init__(image_provider=FileImageProvider())
        self.frames = deque(_frame(name) for name in frames)
        self.last_frame = _frame(frames[-1])
        self.actions: list[tuple[int, int]] = []
        self.on_click: Callable[[int, int], None] | None = None

    def capture_screen(self) -> Image.Image:
        """返回下一张录制帧；序列耗尽后持续返回末帧。"""
        if self.frames:
            self.last_frame = self.frames.popleft()
        return self.last_frame

    def left_click(self, x: int, y: int) -> None:
        """记录点击坐标。"""
        self.actions.append((x, y))
        if self.on_click is not None:
            self.on_click(x, y)


def _matcher() -> DailyCollectScript:
    """构造只含生产模板匹配器的离线对象。"""
    script = DailyCollectScript.__new__(DailyCollectScript)
    script._images = ROOT / "yys/daily_collect/images"
    script.image_finder = ImageFinder.__new__(ImageFinder)
    return script


def _replay(frames: list[str], *, observe_only: bool = False) -> tuple[DailyCollectScript, _FrameEnvironment]:
    """用真实脱敏帧建立受保护的离线脚本。"""
    env = _FrameEnvironment(frames)
    if observe_only:
        guarded = GuardedEnvironment(env, RunGuard(), observe_only=True)
        script = DailyCollectScript(env=guarded)
    else:
        script = DailyCollectScript(env=env)
    script.POLL_INTERVAL = 0
    return script, env


def test_production_templates_match_real_frames_and_reject_adjacent_pages() -> None:
    # 产品契约来源：只允许真实庭院入口和一键收菜页信号驱动输入。
    script = _matcher()
    home = cv2.imread(str(FIXTURES / "home_start.png"))
    home_end = cv2.imread(str(FIXTURES / "home_end.png"))
    tasks = cv2.imread(str(FIXTURES / "tasks_ready.png"))
    popup = cv2.imread(str(FIXTURES / "claim_success_popup.png"))
    success = cv2.imread(str(FIXTURES / "tasks_success.png"))
    completed = cv2.imread(str(FIXTURES / "tasks_completed.png"))

    assert script._is_home(home)
    assert script._is_home(home_end)
    assert not script._is_home(tasks)
    assert script._is_task_page(tasks)
    assert not script._is_task_page(home)
    assert script._has_success_popup(popup)
    assert not script._has_success_popup(tasks)
    assert script._has_success_evidence(success)
    assert script._has_success_evidence(completed)
    assert not script._has_success_evidence(tasks)


def test_current_sakura_home_skin_is_recognized_only_with_scene_marker() -> None:
    # 产品契约来源：2026-10-18 实机庭院灯笼缩放后旧模板仅有 0.825 相似度。
    script = _matcher()
    home = cv2.imread(str(FIXTURES / "home_sakura_current.png"))
    tasks = cv2.imread(str(FIXTURES / "tasks_ready.png"))

    assert script._home_marker(home) is not None
    assert script._match(home, "home_lantern_sakura") is not None
    assert script._is_home(home)
    assert not script._is_home(tasks)


def test_initial_completed_marker_stops_before_one_click() -> None:
    # 产品契约来源：缺少启动时已完成样本，已有印章不能导致重复领取。
    script, env = _replay([
        "home_start.png", "home_start.png", "tasks_completed.png",
    ])

    with pytest.raises(RuntimeError, match="DAILY_COLLECT_PREEXISTING"):
        script.run()

    assert len(env.actions) == 1
    assert script.get_state_snapshot()["flow_complete"] is False


def test_full_recorded_flow_clicks_each_confirmed_target_once() -> None:
    # 产品契约来源：领取成功后确认结束页；重复页面不重复领取。
    script, env = _replay([
        "home_start.png", "home_start.png", "tasks_ready.png",
        "tasks_ready.png", "tasks_ready.png", "claim_success_popup.png",
        "tasks_success.png", "home_end.png",
    ])

    script.run()

    assert len(env.actions) == 4
    assert 680 <= env.actions[0][0] <= 735 and 345 <= env.actions[0][1] <= 410
    assert 980 <= env.actions[1][0] <= 1090 and 510 <= env.actions[1][1] <= 625
    assert 740 <= env.actions[2][0] <= 800 and 60 <= env.actions[2][1] <= 115
    assert 75 <= env.actions[3][0] <= 130 and 10 <= env.actions[3][1] <= 65
    assert script.get_state_snapshot()["outcome"] == "completed"
    assert script.get_state_snapshot()["flow_complete"] is True


def test_completed_stamp_can_confirm_result_when_popup_frame_is_skipped() -> None:
    # 产品契约来源：录制中的已完成印章是领取后的业务完成信号。
    script, env = _replay([
        "home_start.png", "home_start.png", "tasks_ready.png",
        "tasks_completed.png", "home_end.png",
    ])

    script.run()

    assert len(env.actions) == 3
    assert script.get_state_snapshot()["flow_complete"] is True


def test_unknown_entry_fails_before_any_input() -> None:
    # 产品契约来源：从未识别的页面启动时不猜测入口坐标。
    script, env = _replay(["tasks_ready.png", "tasks_ready.png"])

    with pytest.raises(RuntimeError, match="DAILY_COLLECT_ENTRY"):
        script.run()

    assert env.actions == []
    assert script.get_state_snapshot()["flow_complete"] is False


def test_missing_success_signal_never_retries_one_click() -> None:
    # 产品契约来源：一次一键领取后只等待结果；不确定时失败，不重复消耗。
    script, env = _replay([
        "home_start.png", "home_start.png", "tasks_ready.png", "tasks_ready.png",
    ])
    script.WAIT_TIMEOUT = 0.01

    with pytest.raises(RuntimeError, match="DAILY_COLLECT_TRANSITION"):
        script.run()

    assert len(env.actions) == 2
    assert script.get_state_snapshot()["flow_complete"] is False


def test_stop_and_observe_mode_are_not_successful_returns() -> None:
    # 产品契约来源：停止或观察只记录非完成状态，不将后续步骤当作完成。
    stopped, stopped_env = _replay(["home_start.png", "home_start.png"])
    stopped.stop()
    with pytest.raises(RuntimeError, match="DAILY_COLLECT_STOP"):
        stopped.run()
    assert stopped_env.actions == []
    assert stopped.get_state_snapshot()["flow_complete"] is False

    stopped_mid, stopped_mid_env = _replay([
        "home_start.png", "home_start.png", "tasks_ready.png",
    ])

    def stop_after_collect(_x: int, _y: int) -> None:
        if len(stopped_mid_env.actions) == 2:
            stopped_mid.stop()

    stopped_mid_env.on_click = stop_after_collect
    with pytest.raises(RuntimeError, match="DAILY_COLLECT_STOP"):
        stopped_mid.run()
    assert len(stopped_mid_env.actions) == 2
    assert stopped_mid.get_state_snapshot()["outcome"] == "stopped"
    assert stopped_mid.get_state_snapshot()["flow_complete"] is False

    observing, observing_env = _replay(
        ["home_start.png", "home_start.png"], observe_only=True,
    )
    with pytest.raises(RuntimeError, match="DAILY_COLLECT_OBSERVE"):
        observing.run()
    assert observing_env.actions == []
    assert len(observing._env.action_records) == 1
    assert observing.get_state_snapshot()["flow_complete"] is False
