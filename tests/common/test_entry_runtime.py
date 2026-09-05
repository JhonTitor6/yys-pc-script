"""EntryPreparer 入口准备状态机测试（离线 Mock，不依赖游戏窗口）。

产品契约来源（任务 08-08-universal-entry-recovery PRD）：
- AC2：稳定页面启动依次经过准备、验证、就绪，业务运行状态不提前出现；
- AC3：战斗中启动不发送中止输入，等待结算后继续进入入口；
- AC4：3 分钟窗口超时提供继续/转人工/停止，每次继续只延长 3 分钟并产生审计事件；
- AC5：结算关闭不增加业务计数；悬赏封印仅拒绝策略可自动点击；未知弹窗零盲点；
- AC6：导航动作后置验证成功才推进，失败有界重试后升级；
- AC9：准备阶段输入经过 GameEnvironment 并受保险丝保护；
- AC11：未知画面安全失败。
"""
from __future__ import annotations

from typing import Callable, Optional

import pytest

from tests.common.recorders.action_log import ActionLog
from win_util.environment.guarded import RunGuard
from win_util.image import ImageMatchResult
from yys.common.entry_runtime import (
    ENTRY_CAPTURE_FAILED,
    ENTRY_OVERLAY_UNSAFE,
    ENTRY_SCENE_UNKNOWN,
    ENTRY_TRANSITION_FAILED,
    ENTRY_TRANSITION_NOT_FOUND,
    EntryOutcome,
    EntryPreparer,
    EntryPreparationResult,
    SafeOverlayPolicy,
    SceneMode,
    SceneSnapshot,
    TaskEntrySpec,
)


# ==================== 测试替身 ====================

class FakeClock:
    """可控单调时钟。"""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class ScriptedSleep:
    """推进时钟的 sleep 替身；可在指定第 N 次 sleep 时执行钩子（单线程驱动命令）。"""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.count = 0
        self.hooks: list[tuple[int, Callable[[], None]]] = []

    def at(self, sleep_count: int, fn: Callable[[], None]) -> None:
        self.hooks.append((sleep_count, fn))

    def __call__(self, seconds: float) -> None:
        self.clock.advance(seconds)
        self.count += 1
        for count, fn in self.hooks:
            if count == self.count:
                fn()


class ScriptedResolver:
    """按预设序列返回快照的识别器替身。"""

    def __init__(self, snapshots: list[SceneSnapshot]) -> None:
        self.snapshots = list(snapshots)
        self.calls = 0

    def resolve(self, frame) -> SceneSnapshot:
        if not self.snapshots:
            raise AssertionError("识别器序列耗尽，状态机仍在推进")
        self.calls += 1
        return self.snapshots.pop(0)


class LoopResolver:
    """永远返回同一快照的识别器替身。"""

    def __init__(self, snapshot: SceneSnapshot) -> None:
        self.snapshot = snapshot
        self.calls = 0

    def resolve(self, frame) -> SceneSnapshot:
        self.calls += 1
        return self.snapshot


class StubEnv:
    """截图返回占位图、点击记录到 ActionLog 的环境替身。"""

    def __init__(self, log: ActionLog) -> None:
        from PIL import Image
        from tests.common.recorders.action_recorder import ActionRecorder
        self._image = Image.new("RGB", (10, 10))
        self._recorder = ActionRecorder(log)

    def capture_screen(self):
        return self._image

    def left_click(self, x: int, y: int) -> None:
        self._recorder.record_click("left_click", x, y)


class FailingCaptureEnv:
    """截图失败的环境替身（验证 ENTRY_CAPTURE_FAILED）。"""

    def capture_screen(self):
        raise RuntimeError("窗口不可用")

    def left_click(self, x: int, y: int) -> None:
        raise AssertionError("截图失败路径不应发送输入")


class FakeFinder:
    """模板查找替身。"""

    def __init__(self) -> None:
        self.results: dict[str, ImageMatchResult] = {}

    def set(self, path: str, point=(100, 100), similarity: float = 0.9) -> None:
        self.results[path] = ImageMatchResult(point, path, similarity)

    def best_match(self, frame, path: str, *args, **kwargs) -> ImageMatchResult:
        return self.results.get(
            path, ImageMatchResult((-1, -1), path, 0.0)
        )


class FakeSceneManager:
    """路径规划替身。"""

    def __init__(self, path: Optional[list[tuple[str, str, str]]] = None) -> None:
        self.path = path

    def get_shortest_path(self, source: str, target: str):
        if source == target:
            return []
        if self.path is None:
            return None
        return list(self.path)


class StageRecorder:
    """阶段上报记录。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, Optional[dict]]] = []

    def on_stage_change(self, stage: str, detail: Optional[dict] = None) -> None:
        self.events.append((stage, detail))

    @property
    def stages(self) -> list[str]:
        return [s for s, _ in self.events]


# ==================== 构造辅助 ====================

def snapshot(
    base_scene: Optional[str] = None,
    mode: SceneMode = SceneMode.STABLE,
    overlays: tuple[str, ...] = (),
) -> SceneSnapshot:
    return SceneSnapshot(
        base_scene=base_scene,
        overlays=overlays,
        mode=mode,
        confidence=0.9,
        evidence=(),
        stable=mode is SceneMode.STABLE,
    )


def make_spec(
    target: str = "soul_selection",
    stable_obs: int = 2,
    window: float = 180.0,
    obs_interval: float = 1.0,
    stable_interval: float = 0.5,
    policy: Optional[SafeOverlayPolicy] = None,
) -> TaskEntrySpec:
    return TaskEntrySpec(
        target_scene=target,
        stable_observations=stable_obs,
        stable_interval_seconds=stable_interval,
        battle_wait_window_seconds=window,
        observation_interval_seconds=obs_interval,
        safe_overlay_policy=policy or SafeOverlayPolicy(),
    )


def make_preparer(
    env,
    resolver,
    finder: FakeFinder,
    spec: TaskEntrySpec,
    *,
    clock: Optional[FakeClock] = None,
    guard: Optional[RunGuard] = None,
    edge_retries: int = 2,
):
    """构造 EntryPreparer 并返回 (preparer, clock, sleep)。"""
    clock = clock or FakeClock()
    sleep = ScriptedSleep(clock)
    return (
        EntryPreparer(
            env=env,
            resolver=resolver,
            image_finder=finder,
            scene_manager=FakeSceneManager(),
            spec=spec,
            guard=guard,
            monotonic=clock,
            sleep=sleep,
            edge_retries=edge_retries,
            edge_verify_interval_seconds=3.0,
        ),
        clock,
        sleep,
    )


# ==================== AC2：稳定页面启动 ====================

def test_stable_target_directly_reaches_ready() -> None:
    """目标场景已稳定时，经过验证阶段后 READY；业务运行阶段未提前出现。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    # 准备阶段 1 次 + 稳定验证 2 次（stable_observations=2）
    resolver = ScriptedResolver([
        snapshot("soul_selection"),
        snapshot("soul_selection"),
        snapshot("soul_selection"),
    ])
    spec = make_spec(stable_obs=2)
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec)

    recorder = StageRecorder()
    result = preparer.prepare(recorder)

    assert result.outcome is EntryOutcome.READY
    assert "verifying_entry" in recorder.stages
    assert "script_running" not in recorder.stages  # 业务阶段由上层在 READY 后切换
    assert "entry_failed" not in recorder.stages
    log.assert_click_count(0)


def test_stable_observation_interruption_restarts_verification() -> None:
    """稳定验证中途偏离目标场景时，验证计数归零并重新解析。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    # 准备 1 + 验证 3 次命中、第 4 次偏离 home 归零、再准备 1 + 验证 3 次
    resolver = ScriptedResolver([
        snapshot("soul_selection"),
        snapshot("soul_selection"),
        snapshot("soul_selection"),
        snapshot("home"),
        snapshot("soul_selection"),
        snapshot("soul_selection"),
        snapshot("soul_selection"),
        snapshot("soul_selection"),
    ])
    spec = make_spec(stable_obs=3)
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec)

    result = preparer.prepare(StageRecorder())

    assert result.outcome is EntryOutcome.READY
    assert resolver.calls == 8


# ==================== AC3/AC5：战斗等待与结算关闭 ====================

def test_battle_wait_zero_input_then_settlement_dismissed() -> None:
    """战斗中零输入；结算出现后被白名单关闭；随后稳定进入入口。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    finder.set("battle_end.bmp", point=(567, 460))
    policy = SafeOverlayPolicy(settlement_templates=("battle_end.bmp",))
    resolver = ScriptedResolver([
        snapshot(mode=SceneMode.BATTLE),
        snapshot(mode=SceneMode.BATTLE),
        snapshot(mode=SceneMode.SETTLEMENT),
        snapshot("soul_selection"),
        snapshot("soul_selection"),
        snapshot("soul_selection"),
    ])
    spec = make_spec(policy=policy)
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec)

    recorder = StageRecorder()
    result = preparer.prepare(recorder)

    assert result.outcome is EntryOutcome.READY
    assert "waiting_safe_entry" in recorder.stages
    # 战斗阶段零输入，结算阶段恰好 1 次点击（独立结算处理）
    log.assert_click_count(1)
    log.assert_click_at(567, 460)


def test_battle_wait_never_sends_input_until_guard_stops() -> None:
    """长时间战斗等待全程零输入；RunGuard 超时最终截停（保险丝优先）。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    clock = FakeClock()
    guard = RunGuard(timeout_seconds=10, max_actions=30, unknown_limit=3, monotonic=clock)
    resolver = LoopResolver(snapshot(mode=SceneMode.BATTLE))
    spec = make_spec(window=180.0)
    preparer, clock2, sleep = make_preparer(env, resolver, finder, spec, clock=clock, guard=guard)

    result = preparer.prepare(StageRecorder())

    assert result.outcome is EntryOutcome.STOPPED
    assert result.reason == "运行保险丝触发"
    log.assert_click_count(0)


# ==================== AC4：战斗窗口超时与继续等待 ====================

def test_battle_window_timeout_continue_then_manual_takeover() -> None:
    """180 秒窗口到期进入等待用户命令；每次继续只延长 180 秒并记录事件；转人工终结。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    clock = FakeClock()
    resolver = LoopResolver(snapshot(mode=SceneMode.BATTLE))
    spec = make_spec(window=180.0, obs_interval=1.0)
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec, clock=clock)

    # 第 181 次 sleep（首轮超时后的轮询）→ 请求继续等待；
    # 第二次超时后的轮询（第 362 次）→ 请求转人工接管。
    sleep.at(181, preparer.request_continue_waiting)
    sleep.at(362, preparer.request_manual_takeover)

    recorder = StageRecorder()
    result = preparer.prepare(recorder)

    assert result.outcome is EntryOutcome.MANUAL
    assert result.continue_wait_count == 1
    # 两次超时之间的间隔为一个完整 180 秒窗口（每次继续只延长 3 分钟）
    assert 170.0 <= result.battle_wait_seconds <= 190.0
    # 阶段序列：超时两次、continue 事件带计数
    assert recorder.stages.count("waiting_safe_entry_timeout") == 2
    continue_events = [d for s, d in recorder.events if s == "waiting_safe_entry"]
    assert any(
        d is not None and d.get("continue_wait_count") == 1 for d in continue_events
    )
    # 全程零输入（等待期间只观察）
    log.assert_click_count(0)


def test_continue_waiting_extends_exactly_one_window() -> None:
    """继续等待后：90 秒内不再次超时，再 91 秒后第二次超时（窗口精确 180）。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    clock = FakeClock()
    resolver = LoopResolver(snapshot(mode=SceneMode.BATTLE))
    spec = make_spec(window=180.0, obs_interval=1.0)
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec, clock=clock)

    sleep.at(181, preparer.request_continue_waiting)
    # 第二次超时发生在 continue 后约 180 秒（181 + 180 + 少量轮询）
    sleep.at(362, preparer.request_manual_takeover)

    recorder = StageRecorder()
    result = preparer.prepare(recorder)

    assert result.outcome is EntryOutcome.MANUAL
    assert recorder.stages.count("waiting_safe_entry_timeout") == 2
    # 第一次超时在 now=180，continue 在 now≈180.1，第二次超时在 now≈360.2
    assert 350.0 <= clock.now <= 380.0


def test_battle_window_timeout_stop_command() -> None:
    """超时后用户选择停止 → STOPPED 终态。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    clock = FakeClock()
    resolver = LoopResolver(snapshot(mode=SceneMode.BATTLE))
    spec = make_spec(window=180.0, obs_interval=1.0)
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec, clock=clock)

    sleep.at(181, preparer.request_stop)

    result = preparer.prepare(StageRecorder())

    assert result.outcome is EntryOutcome.STOPPED
    log.assert_click_count(0)


# ==================== AC5：悬赏封印与未知弹窗 ====================

def test_wanted_quest_refuse_policy_clicks_confirmed_reject() -> None:
    """配置为拒绝时，仅点击已确认的悬赏封印拒绝模板。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    finder.set("xuanshangfengyin_reject.bmp", point=(500, 300))
    policy = SafeOverlayPolicy(
        refuse_wanted_quests=True,
        wanted_quest_reject_template="xuanshangfengyin_reject.bmp",
    )
    resolver = ScriptedResolver([
        snapshot(overlays=("wanted_quest",)),
        snapshot("soul_selection"),
        snapshot("soul_selection"),
        snapshot("soul_selection"),
    ])
    spec = make_spec(policy=policy)
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec)

    result = preparer.prepare(StageRecorder())

    assert result.outcome is EntryOutcome.READY
    log.assert_click_count(1)
    log.assert_click_at(500, 300)


def test_wanted_quest_accept_policy_manual_no_click() -> None:
    """接受类悬赏策略不允许自动处理 → 转人工失败，零盲点输入。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    policy = SafeOverlayPolicy()  # refuse_wanted_quests=False
    resolver = ScriptedResolver([snapshot(overlays=("wanted_quest",))])
    spec = make_spec(policy=policy)
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec)

    recorder = StageRecorder()
    result = preparer.prepare(recorder)

    assert result.outcome is EntryOutcome.ERROR
    assert result.error_code == ENTRY_OVERLAY_UNSAFE
    assert result.snapshot is not None
    log.assert_click_count(0)


def test_unknown_overlay_manual_no_click() -> None:
    """未知覆盖层（OCR 继续/私有弹窗）不自动处理，零点击。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    resolver = ScriptedResolver([snapshot(overlays=("unknown_popup",))])
    spec = make_spec()
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec)

    result = preparer.prepare(StageRecorder())

    assert result.outcome is EntryOutcome.ERROR
    assert result.error_code == ENTRY_OVERLAY_UNSAFE
    log.assert_click_count(0)


# ==================== AC11：未知画面安全失败 ====================

def test_unknown_scene_bounded_retry_then_fail_zero_input() -> None:
    """未知画面有界重识别后结构化失败，全程零输入。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    resolver = LoopResolver(snapshot(mode=SceneMode.UNKNOWN))
    spec = make_spec()
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec)

    result = preparer.prepare(StageRecorder())

    assert result.outcome is EntryOutcome.ERROR
    assert result.error_code == ENTRY_SCENE_UNKNOWN
    assert result.reason is not None and "无法识别" in result.reason
    # 1 次初始 + UNKNOWN_RESOLVE_ATTEMPTS 次重识别
    assert resolver.calls == 1 + EntryPreparer.UNKNOWN_RESOLVE_ATTEMPTS
    log.assert_click_count(0)


# ==================== AC6：导航后置验证与有界重试 ====================

def test_navigation_verifies_each_edge_before_advancing() -> None:
    """导航逐边执行：点击按钮 → 后置场景验证通过才推进到下一跳。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    finder.set("home_to_exploration.bmp", point=(100, 200))
    finder.set("exploration_to_soul_selection.bmp", point=(300, 400))
    path = [
        ("home", "exploration", "home_to_exploration.bmp"),
        ("exploration", "soul_selection", "exploration_to_soul_selection.bmp"),
    ]
    resolver = ScriptedResolver([
        snapshot("home"),
        snapshot("exploration"),       # 第一跳后置验证
        snapshot("soul_selection"),    # 第二跳后置验证
        snapshot("soul_selection"),    # 稳定验证 1
        snapshot("soul_selection"),    # 稳定验证 2
    ])
    spec = make_spec(stable_obs=2)
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec)
    preparer._scene_manager = FakeSceneManager(path)

    recorder = StageRecorder()
    result = preparer.prepare(recorder)

    assert result.outcome is EntryOutcome.READY
    assert recorder.stages.index("navigating") < recorder.stages.index("verifying_entry")
    log.assert_click_count(2)
    log.assert_click_at(100, 200)
    log.assert_click_at(300, 400)


def test_navigation_edge_failure_bounded_retry_then_error() -> None:
    """导航边后置验证失败时有限重试（retries+1 次），随后升级为结构化错误。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    finder.set("home_to_soul_selection.bmp", point=(100, 200))
    path = [("home", "soul_selection", "home_to_soul_selection.bmp")]
    # 验证 3 次均未到达目标（探索页一次，home 两次）
    resolver = ScriptedResolver([
        snapshot("home"),
        snapshot("exploration"),
        snapshot("home"),
        snapshot("home"),
    ])
    spec = make_spec()
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec, edge_retries=2)
    preparer._scene_manager = FakeSceneManager(path)

    recorder = StageRecorder()
    result = preparer.prepare(recorder)

    assert result.outcome is EntryOutcome.ERROR
    assert result.error_code == ENTRY_TRANSITION_FAILED
    assert "导航边失败" in (result.reason or "")
    # 有界重试：1 次初始 + 2 次重试 = 3 次点击
    log.assert_click_count(3)


def test_navigation_no_path_structured_error() -> None:
    """不存在可达路径时返回 ENTRY_TRANSITION_NOT_FOUND，零输入。"""
    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    resolver = ScriptedResolver([snapshot("home")])
    spec = make_spec()
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec)
    preparer._scene_manager = FakeSceneManager(None)  # 无路径

    result = preparer.prepare(StageRecorder())

    assert result.outcome is EntryOutcome.ERROR
    assert result.error_code == ENTRY_TRANSITION_NOT_FOUND
    log.assert_click_count(0)


# ==================== AC9：保险丝与截图失败 ====================

def test_guard_action_limit_blocks_unknown_retry_clicks() -> None:
    """动作预算耗尽时 GuardedEnvironment 拦截点击，状态机最终由保险丝截停。"""
    from win_util.environment.guarded import GuardedEnvironment

    log = ActionLog()
    env = StubEnv(log)
    finder = FakeFinder()
    finder.set("home_to_soul_selection.bmp", point=(100, 200))
    path = [("home", "soul_selection", "home_to_soul_selection.bmp")]
    resolver = ScriptedResolver([
        snapshot("home"),
        snapshot("home"),
        snapshot("home"),
        snapshot("home"),
    ])
    clock = FakeClock()
    guard = RunGuard(timeout_seconds=60, max_actions=2, unknown_limit=3, monotonic=clock)
    guarded_env = GuardedEnvironment(env, guard, observe_only=True)
    spec = make_spec()
    preparer, clock, sleep = make_preparer(guarded_env, resolver, finder, spec, clock=clock, guard=guard)
    preparer._scene_manager = FakeSceneManager(path)

    result = preparer.prepare(StageRecorder())

    # 动作预算耗尽触发保险丝，以保险丝终态为准（设计 §10）
    assert result.outcome is EntryOutcome.STOPPED
    # 动作预算 2：仅前两次点击进入预算，后续被 guard 拦截；
    # observe_only 下仅记录计划动作，不向真实窗口发送任何输入
    assert len(guarded_env.action_records) == 2
    log.assert_click_count(0)


def test_capture_failure_structured_error() -> None:
    """截图失败产生 ENTRY_CAPTURE_FAILED 与可读原因。"""
    env = FailingCaptureEnv()
    finder = FakeFinder()
    resolver = LoopResolver(snapshot(mode=SceneMode.UNKNOWN))
    spec = make_spec()
    preparer, clock, sleep = make_preparer(env, resolver, finder, spec)

    result = preparer.prepare(StageRecorder())

    assert result.outcome is EntryOutcome.ERROR
    assert result.error_code == ENTRY_CAPTURE_FAILED
    assert result.reason is not None and "窗口不可用" in result.reason




def _real_scene_manager(image_finder):
    """构造注入真实 image_finder 的 SceneManager（避免 Mock 分数进排序）。"""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from win_util.image import to_project_path
    from yys.common.scene_manager import SceneManager

    scene_manager = SceneManager(12345, Mock())
    scene_manager.win_controller = SimpleNamespace(image_finder=image_finder)
    scene_manager.register_scenes_from_directory(
        to_project_path("yys/common/images/scene/"),
        to_project_path("yys/common/images/scene_control/"),
    )
    return scene_manager


def _real_resolver_for_fixture():
    """构造基于生产 matcher 与真实场景注册的识别器。"""
    from win_util.image import ImageFinder
    from yys.common.entry_runtime import ImageSceneStateResolver

    image_finder = ImageFinder(env=None, hwnd=None)
    scene_manager = _real_scene_manager(image_finder)
    spec = TaskEntrySpec(
        target_scene="soul_selection",
        safe_overlay_policy=SafeOverlayPolicy(
            settlement_templates=(
                "yys/images/battle_end.bmp",
                "yys/images/battle_end_1.bmp",
            ),
        ),
    )
    return ImageSceneStateResolver(scene_manager, image_finder, spec), spec


# ==================== 真实帧回放（AC3/AC5 离线部分） ====================

def _imread_unicode(path: str):
    """读取中文路径图片（cv2.imread 不支持非 ASCII 路径）。"""
    import cv2

    import numpy as np
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def test_resolver_classifies_real_soul_raid_frames() -> None:
    """生产 matcher + 确认真实帧：战斗帧 → BATTLE，结算帧 → SETTLEMENT（AC3/AC5）。

    产品契约：battling 模板必须覆盖真实战斗帧且不得匹配结算帧
    （quality-guidelines：长时状态标记需对相邻状态为负样本）。
    """
    import cv2

    import numpy as np
    from unittest.mock import Mock

    from win_util.image import ImageFinder
    from yys.common.entry_runtime import ImageSceneStateResolver

    example_dir = "yys/soul_raid/images/test/example"
    battle_frame = _imread_unicode(f"{example_dir}/御魂_战斗.png")
    settlement_frame = _imread_unicode(f"{example_dir}/御魂_战斗结算.png")
    assert battle_frame is not None and settlement_frame is not None

    image_finder = ImageFinder(env=None, hwnd=None)
    scene_manager = _real_scene_manager(image_finder)
    spec = TaskEntrySpec(
        target_scene="soul_selection",
        safe_overlay_policy=SafeOverlayPolicy(
            settlement_templates=(
                "yys/images/battle_end.bmp",
                "yys/images/battle_end_success.bmp",
                "yys/images/battle_end_loss.bmp",
                "yys/images/battle_end_1.bmp",
                "yys/images/battle_end_2.bmp",
            ),
        ),
    )
    resolver = ImageSceneStateResolver(scene_manager, image_finder, spec)

    battle_snap = resolver.resolve(battle_frame)
    assert battle_snap.mode is SceneMode.BATTLE
    assert battle_snap.base_scene == "battling"
    assert battle_snap.confidence >= 0.8

    settlement_snap = resolver.resolve(settlement_frame)
    assert settlement_snap.mode is SceneMode.SETTLEMENT
    assert settlement_snap.confidence >= 0.8


class FrameEnv:
    """capture_screen 按序返回真实帧的环境替身；耗尽后停留在最后一帧。"""

    def __init__(self, log: ActionLog, frames) -> None:
        from tests.common.recorders.action_recorder import ActionRecorder

        self._frames = list(frames)
        self._recorder = ActionRecorder(log)

    def capture_screen(self):
        if not self._frames:
            return self._last_frame if hasattr(self, "_last_frame") else None
        self._last_frame = self._frames.pop(0)
        return self._last_frame

    def left_click(self, x: int, y: int) -> None:
        self._recorder.record_click("left_click", x, y)


def _queue_frame(images) -> list:
    """把帧文件列表预读为 numpy 数组队列。"""
    return [_imread_unicode(p) for p in images]


def test_replay_entry_fixture_stable_start_reaches_ready() -> None:
    """确认夹具回放：入口稳定帧启动 → 验证通过 → READY（AC11 稳定页闭环）。"""
    resolver, spec = _real_resolver_for_fixture()
    fixture_dir = "tests/fixtures/soul_raid_entry/scenes"
    entry_frame = _imread_unicode(f"{fixture_dir}/entry_stable.png")
    assert entry_frame is not None
    assert resolver.resolve(entry_frame).mode is SceneMode.STABLE

    log = ActionLog()
    env = FrameEnv(log, _queue_frame([
        f"{fixture_dir}/entry_stable.png",
        f"{fixture_dir}/entry_stable.png",
        f"{fixture_dir}/entry_stable.png",
    ]))
    # 使用与识别器一致的入口契约（含结算关闭策略）
    spec2 = spec
    preparer = EntryPreparer(
        env=env,
        resolver=resolver,
        image_finder=resolver._image_finder,
        scene_manager=FakeSceneManager(),
        spec=spec2,
        monotonic=FakeClock(),
        sleep=lambda s: None,
    )

    result = preparer.prepare(StageRecorder())

    assert result.outcome is EntryOutcome.READY
    log.assert_click_count(0)


def test_replay_entry_fixture_battle_start_reaches_ready() -> None:
    """确认夹具回放：战斗中启动 → 等待零输入 → 结算关闭 → 回到入口 → READY（AC3/AC11）。"""
    resolver, spec = _real_resolver_for_fixture()
    fixture_dir = "tests/fixtures/soul_raid_entry/scenes"
    frames = _queue_frame([
        f"{fixture_dir}/battle_early.png",
        f"{fixture_dir}/battle_mid.png",
        f"{fixture_dir}/battle_late.png",
        f"{fixture_dir}/settlement.png",
        f"{fixture_dir}/entry_stable.png",
        f"{fixture_dir}/entry_stable.png",
        f"{fixture_dir}/entry_stable.png",
    ])
    assert resolver.resolve(frames[0]).mode is SceneMode.BATTLE
    assert resolver.resolve(frames[3]).mode is SceneMode.SETTLEMENT

    log = ActionLog()
    env = FrameEnv(log, frames)
    # 使用与识别器一致的入口契约（含结算关闭策略）
    spec2 = spec
    preparer = EntryPreparer(
        env=env,
        resolver=resolver,
        image_finder=resolver._image_finder,
        scene_manager=FakeSceneManager(),
        spec=spec2,
        monotonic=FakeClock(),
        sleep=lambda s: None,
    )

    result = preparer.prepare(StageRecorder())

    assert result.outcome is EntryOutcome.READY
    # 战斗三帧等待零输入；结算关闭 1 次点击；入口验证零输入
    log.assert_click_count(1)


def test_soul_raid_battle_settlement_returns_to_team_ready() -> None:
    """产品契约：御魂战斗中启动，结算关闭后回到组队界面并 READY。"""
    from win_util.image import ImageFinder
    from yys.common.entry_runtime import ImageSceneStateResolver
    from yys.soul_raid.soul_raid_script import SoulRaidScript

    spec = SoulRaidScript.entry_spec
    assert spec is not None
    image_finder = ImageFinder(env=None, hwnd=None)
    scene_manager = _real_scene_manager(image_finder)
    resolver = ImageSceneStateResolver(scene_manager, image_finder, spec)

    battle = "yys/soul_raid/images/test/example/御魂_战斗.png"
    settlement = "yys/soul_raid/images/test/example/御魂_战斗结算.png"
    team = "yys/soul_raid/images/test/example/御魂_组队界面.png"
    frames = _queue_frame([
        battle,
        battle,
        settlement,
        team,
        team,
        team,
    ])
    log = ActionLog()
    env = FrameEnv(log, frames)
    preparer = EntryPreparer(
        env=env,
        resolver=resolver,
        image_finder=image_finder,
        scene_manager=scene_manager,
        spec=spec,
        monotonic=FakeClock(),
        sleep=lambda _seconds: None,
    )

    result = preparer.prepare(StageRecorder())

    assert result.outcome is EntryOutcome.READY
    assert result.snapshot is not None
    assert result.snapshot.base_scene == "soul_selection"
    log.assert_click_count(1)


def test_replay_entry_fixture_battle_then_unknown_fails_safely() -> None:
    """确认夹具回放：战斗后无入口帧可识别 → 有界重识别 → 安全失败（AC11 未知画面）。"""
    import numpy as np

    resolver, spec = _real_resolver_for_fixture()
    fixture_dir = "tests/fixtures/soul_raid_entry/scenes"
    unknown_frame = np.full((640, 1136, 3), 200, dtype=np.uint8)
    frames = _queue_frame([
        f"{fixture_dir}/battle_early.png",
        f"{fixture_dir}/settlement.png",
    ]) + [unknown_frame] * 6

    log = ActionLog()
    env = FrameEnv(log, frames)
    # 使用与识别器一致的入口契约（含结算关闭策略）
    spec2 = spec
    preparer = EntryPreparer(
        env=env,
        resolver=resolver,
        image_finder=resolver._image_finder,
        scene_manager=FakeSceneManager(),
        spec=spec2,
        monotonic=FakeClock(),
        sleep=lambda s: None,
    )

    result = preparer.prepare(StageRecorder())

    assert result.outcome is EntryOutcome.ERROR
    assert result.error_code == ENTRY_SCENE_UNKNOWN
    # 仅结算关闭一次点击；未知画面零盲点输入
    log.assert_click_count(1)


