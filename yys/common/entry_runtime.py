"""通用入口准备与恢复运行时（EntryPreparer）。

产品契约：任务 `08-08-universal-entry-recovery` 的 PRD R2-R6 与设计 §4、§6。
职责边界：
- 业务脚本只声明 TaskEntrySpec，不自行实现"从任意页面回入口"的流程；
- 未知画面禁止盲点恢复，所有动作必须有识别前置与可验证后置；
- 战斗期间只观察和等待，不发送中止战斗的输入；
- 所有输入经过注入的 GameEnvironment 并受 RunGuard 预算约束；
- 每个入口阶段通过 EntryReporter 上报，供 RunManager/GUI 展示。

本模块不依赖真实窗口：截图/输入走注入环境，识别器（SceneStateResolver）、
按钮查找（ImageFinder）与时钟均可注入，离线测试用 stub 驱动完整状态机。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Protocol, Tuple

import numpy as np

from win_util.environment.base import GameEnvironment
from win_util.environment.guarded import RunGuard
from win_util.image import ImageMatchResult


# ==================== 错误码 ====================

#: 场景图完整性校验失败（幽灵节点/未知端点）
ENTRY_GRAPH_INVALID = "ENTRY_GRAPH_INVALID"
#: 当前画面无法可靠识别（含重识别仍未知）
ENTRY_SCENE_UNKNOWN = "ENTRY_SCENE_UNKNOWN"
#: 战斗安全等待超时（由上层决定继续等待/转人工/停止）
ENTRY_BATTLE_WAIT_TIMEOUT = "ENTRY_BATTLE_WAIT_TIMEOUT"
#: 出现不允许自动处理的弹窗/覆盖层（接受类悬赏、OCR 继续、未知弹窗）
ENTRY_OVERLAY_UNSAFE = "ENTRY_OVERLAY_UNSAFE"
#: 从当前场景到目标入口不存在路径
ENTRY_TRANSITION_NOT_FOUND = "ENTRY_TRANSITION_NOT_FOUND"
#: 导航边执行失败（有界重试后仍未到达后置场景）
ENTRY_TRANSITION_FAILED = "ENTRY_TRANSITION_FAILED"
#: 入口稳定验证未通过
ENTRY_TARGET_UNSTABLE = "ENTRY_TARGET_UNSTABLE"
#: 截图失败
ENTRY_CAPTURE_FAILED = "ENTRY_CAPTURE_FAILED"


class SceneMode(str, Enum):
    """一次截图解析出的画面模式（设计 §4.1）。"""

    STABLE = "stable"          # 可作为导航节点的稳定页面
    TRANSITION = "transition"  # 已知短暂过渡，不执行新动作
    BATTLE = "battle"          # 战斗进行中，只等待和观察
    SETTLEMENT = "settlement"  # 已确认结算，可执行白名单关闭动作
    UNKNOWN = "unknown"        # 无可靠识别


class TransitionRisk(str, Enum):
    """导航边风险等级；首个 MVP 只允许 SAFE。"""

    SAFE = "safe"


class EntryOutcome(str, Enum):
    """入口准备结果终态。"""

    READY = "ready"        # 入口验证稳定，可以进入业务运行
    MANUAL = "manual"      # 转人工接管（当前 run 终结，释放执行槽）
    STOPPED = "stopped"    # 用户停止或保险丝触发
    ERROR = "error"        # 结构化失败（带 error_code 与证据）


@dataclass(frozen=True)
class RecognitionEvidence:
    """单个模板的识别证据（设计 §4.1）。"""

    target_id: str
    image_path: str
    similarity: float
    position: Optional[Tuple[int, int]]
    matched: bool


@dataclass(frozen=True)
class SceneSnapshot:
    """一次截图的基础场景、覆盖层、模式、置信度、证据与稳定性。"""

    base_scene: Optional[str]
    overlays: Tuple[str, ...]
    mode: SceneMode
    confidence: float
    evidence: Tuple[RecognitionEvidence, ...]
    stable: bool


@dataclass(frozen=True)
class SafeOverlayPolicy:
    """入口准备阶段允许自动处理的覆盖层白名单。

    - 结算关闭使用独立模板，绝不调用增加业务战斗/胜利计数的回调；
    - 悬赏封印仅当 refuse_wanted_quests=True（业务配置为拒绝）时
      允许点击已确认的拒绝按钮；其余策略一律转人工。
    """

    settlement_templates: Tuple[str, ...] = ()
    refuse_wanted_quests: bool = False
    wanted_quest_reject_template: Optional[str] = None


@dataclass(frozen=True)
class TaskEntrySpec:
    """业务脚本声明的入口需求与恢复策略（设计 §4.2）。"""

    target_scene: str
    stable_observations: int = 2
    stable_interval_seconds: float = 0.5
    battle_wait_window_seconds: float = 180.0
    observation_interval_seconds: float = 1.0
    safe_overlay_policy: SafeOverlayPolicy = field(default_factory=SafeOverlayPolicy)


@dataclass(frozen=True)
class Transition:
    """一条导航边；动作成功 = 目标场景通过稳定验证（设计 §4.3）。"""

    source: str
    target: str
    action_image: str
    timeout_seconds: float
    retries: int
    risk: TransitionRisk


@dataclass(frozen=True)
class EntryPreparationResult:
    """入口准备结果：终态、阶段、错误码与证据。"""

    outcome: EntryOutcome
    stage: str
    error_code: Optional[str] = None
    reason: Optional[str] = None
    snapshot: Optional[SceneSnapshot] = None
    battle_wait_seconds: float = 0.0
    continue_wait_count: int = 0


class EntryReporter(Protocol):
    """入口阶段上报接口（由 RunManager 实现）。"""

    def on_stage_change(self, stage: str, detail: Optional[dict] = None) -> None:
        """阶段变化回调。"""


class EntryPreparationError(Exception):
    """入口准备失败（结构化），携带完整 EntryPreparationResult。

    业务脚本 run() 兼容包装在准备失败时抛出本异常，
    使 RunManager 能区分“入口失败”与“业务运行异常”。
    """

    def __init__(self, result: "EntryPreparationResult"):
        super().__init__(
            f"[{result.error_code or 'ENTRY_FAILED'}] {result.reason or '入口准备失败'}"
        )
        self.result = result


class NoopReporter:
    """不输出的阶段上报（默认实现）。"""

    def on_stage_change(self, stage: str, detail: Optional[dict] = None) -> None:
        pass


class SceneStateResolver(Protocol):
    """从一帧截图解析 SceneSnapshot 的识别器（必须只读，不发送输入）。"""

    def resolve(self, frame) -> SceneSnapshot:
        """解析当前帧。"""


class ImageSceneStateResolver:
    """基于模板匹配的生产识别器：帧 → SceneSnapshot（只读）。

    判定优先级：悬赏封印覆盖层 → 结算模板 → 战斗模板 → 基础场景候选。
    - 结算/战斗由显式模板判定（结算优先，战斗模板质量由真实帧回归保障）；
    - 基础场景使用 SceneManager.detect_scene_candidates 的最佳候选，
      高于阈值判定 STABLE，否则 UNKNOWN（confidence 保留最高候选分数）。
    """

    def __init__(
        self,
        scene_manager,
        image_finder,
        spec: TaskEntrySpec,
        threshold: float = 0.8,
    ) -> None:
        """创建识别器。

        Args:
            scene_manager: 场景管理器（提供场景模板与候选识别）。
            image_finder: 模板查找器（best_match，只读）。
            spec: 入口契约（目标场景与覆盖层策略）。
            threshold: 判定命中的相似度阈值。
        """
        self._scene_manager = scene_manager
        self._image_finder = image_finder
        self._spec = spec
        self._threshold = threshold

    def resolve(self, frame) -> SceneSnapshot:
        """解析一帧为 SceneSnapshot。"""
        img = np.array(frame) if not isinstance(frame, np.ndarray) else frame
        evidence: List[RecognitionEvidence] = []
        overlays: List[str] = []
        policy = self._spec.safe_overlay_policy

        # 1) 悬赏封印覆盖层（仅声明拒绝模板时检查）
        if policy.wanted_quest_reject_template:
            reject_ev = self._match(
                img, "wanted_quest", policy.wanted_quest_reject_template
            )
            evidence.append(reject_ev)
            if reject_ev.matched:
                overlays.append("wanted_quest")

        # 2) 结算模板（白名单关闭候选）
        settlement_ev = self._best_match_any(
            img, "settlement", policy.settlement_templates
        )
        if settlement_ev is not None:
            evidence.append(settlement_ev)
            if settlement_ev.matched:
                return SceneSnapshot(
                    base_scene=None,
                    overlays=tuple(overlays),
                    mode=SceneMode.SETTLEMENT,
                    confidence=settlement_ev.similarity,
                    evidence=tuple(evidence),
                    stable=False,
                )

        # 3) 战斗模板（battling 场景图片，须由真实帧覆盖早/中/晚）
        battle_ev = self._best_match_any(
            img, "battle", self._scene_manager.scene_images.get("battling", [])
        )
        if battle_ev is not None and battle_ev.matched:
            evidence.append(battle_ev)
            return SceneSnapshot(
                base_scene="battling",
                overlays=tuple(overlays),
                mode=SceneMode.BATTLE,
                confidence=battle_ev.similarity,
                evidence=tuple(evidence),
                stable=False,
            )

        # 4) 基础场景候选（含阈值以下的最佳候选作为证据）
        candidates = self._scene_manager.detect_scene_candidates(img)
        for candidate in candidates[:5]:
            evidence.append(
                RecognitionEvidence(
                    target_id=candidate.scene_name,
                    image_path=candidate.matched_image,
                    similarity=candidate.similarity,
                    position=candidate.position,
                    matched=candidate.similarity >= self._threshold,
                )
            )
        if not candidates:
            return SceneSnapshot(
                base_scene=None,
                overlays=tuple(overlays),
                mode=SceneMode.UNKNOWN,
                confidence=0.0,
                evidence=tuple(evidence),
                stable=False,
            )
        top = candidates[0]
        if top.similarity >= self._threshold:
            return SceneSnapshot(
                base_scene=top.scene_name,
                overlays=tuple(overlays),
                mode=SceneMode.STABLE,
                confidence=top.similarity,
                evidence=tuple(evidence),
                stable=True,
            )
        return SceneSnapshot(
            base_scene=None,
            overlays=tuple(overlays),
            mode=SceneMode.UNKNOWN,
            confidence=top.similarity,
            evidence=tuple(evidence),
            stable=False,
        )

    def _match(self, img, target_id: str, image_path: str) -> RecognitionEvidence:
        """单个模板匹配证据。"""
        result: Optional[ImageMatchResult] = self._image_finder.best_match(
            img, image_path
        )
        if result is None or not result.is_found:
            return RecognitionEvidence(target_id, image_path, 0.0, None, False)
        return RecognitionEvidence(
            target_id,
            image_path,
            result.similarity,
            result.point,
            result.similarity >= self._threshold,
        )

    def _best_match_any(
        self, img, target_id: str, image_paths: Tuple[str, ...]
    ) -> Optional[RecognitionEvidence]:
        """多模板中取最高相似度证据；无模板时返回 None。"""
        if not image_paths:
            return None
        best: Optional[RecognitionEvidence] = None
        for image_path in image_paths:
            evidence = self._match(img, target_id, image_path)
            if best is None or evidence.similarity > best.similarity:
                best = evidence
        return best


class EntryPreparer:
    """入口准备状态机（设计 §6）。

    阶段流转：
      PREPARING → resolve_state
        ├─ 稳定目标 → VERIFYING_ENTRY
        ├─ 安全覆盖层 → 处理后回 PREPARING
        ├─ 战斗 → WAITING_SAFE_ENTRY
        ├─ 结算 → 白名单关闭后回 PREPARING
        ├─ 已知稳定页 → NAVIGATING
        └─ 未知 → 有界重识别 → ERROR/MANUAL

      WAITING_SAFE_ENTRY：只观察；180 秒窗口到期 → WAITING_SAFE_ENTRY_TIMEOUT
      WAITING_SAFE_ENTRY_TIMEOUT：continue_waiting → 新窗口；manual → MANUAL；stop → STOPPED
      NAVIGATING：逐边执行，后置验证通过才推进；失败有界重试后升级
      VERIFYING_ENTRY：连续稳定观察达标 → READY

    安全边界：
      - 战斗观察与稳定性验证不消耗动作预算，但检查紧急停止与总限制；
      - 延长战斗窗口只延长阶段截止时间，不修改总限制/动作数/未知计数；
      - 未知画面不产生任何输入。
    """

    #: 未知画面有界重识别次数
    UNKNOWN_RESOLVE_ATTEMPTS = 3
    #: 等待用户命令时的轮询间隔（秒）
    COMMAND_POLL_INTERVAL_SECONDS = 0.1

    def __init__(
        self,
        *,
        env: GameEnvironment,
        resolver: SceneStateResolver,
        image_finder,
        scene_manager,
        spec: TaskEntrySpec,
        guard: Optional[RunGuard] = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        edge_retries: int = 2,
        edge_verify_interval_seconds: float = 3.0,
    ) -> None:
        """创建入口准备器。

        Args:
            env: 注入的游戏环境（截图与全部输入的唯一通道）。
            resolver: 帧 → SceneSnapshot 识别器（只读）。
            image_finder: 按钮/模板查找器（best_match，只读）。
            scene_manager: 场景图（路径规划）。
            spec: 业务脚本声明的入口契约。
            guard: 运行保险丝（可空；为空时不做预算/超时/紧急停止检查）。
            monotonic: 单调时钟（测试注入可控时钟）。
            sleep: 等待函数（测试注入可推进时钟的 stub）。
            edge_retries: 每条导航边的有界重试次数。
            edge_verify_interval_seconds: 导航后置验证的等待间隔。
        """
        if spec.battle_wait_window_seconds <= 0:
            raise ValueError("battle_wait_window_seconds 必须为正数")
        self._env = env
        self._resolver = resolver
        self._image_finder = image_finder
        self._scene_manager = scene_manager
        self._spec = spec
        self._guard = guard
        self._monotonic = monotonic
        self._sleep = sleep
        self._edge_retries = edge_retries
        self._edge_verify_interval_seconds = edge_verify_interval_seconds

        self._pending_command: Optional[str] = None
        self._battle_window_deadline: float = 0.0
        self._battle_wait_seconds: float = 0.0
        self._continue_wait_count: int = 0
        self._unknown_count: int = 0
        self._stable_count: int = 0
        self._last_snapshot: Optional[SceneSnapshot] = None
        self._last_frame = None
        self._error_code: Optional[str] = None
        self._error_reason: Optional[str] = None
        self._report: EntryReporter

    # ==================== 外部命令（由 RunManager 线程调用） ====================

    def request_continue_waiting(self) -> None:
        """请求继续等待一个战斗窗口（仅 WAITING_SAFE_ENTRY_TIMEOUT 生效）。"""
        self._pending_command = "continue"

    def request_manual_takeover(self) -> None:
        """请求转人工接管。"""
        self._pending_command = "manual"

    def request_stop(self) -> None:
        """请求停止（等价于用户停止）。"""
        self._pending_command = "stop"

    # ==================== 主流程 ====================

    def prepare(self, reporter: EntryReporter) -> EntryPreparationResult:
        """运行入口准备状态机直至终态。

        Args:
            reporter: 阶段上报回调。

        Returns:
            EntryPreparationResult：READY/MANUAL/STOPPED/ERROR 之一。
        """
        self._report = reporter
        self._report.on_stage_change("preparing")
        return self._run_state_machine()

    def _run_state_machine(self) -> EntryPreparationResult:
        state = "preparing"
        while True:
            if self._guard is not None and self._guard.is_stopped:
                return self._result(
                    EntryOutcome.STOPPED,
                    state,
                    reason="运行保险丝触发",
                )
            if state == "preparing":
                state = self._step_preparing()
            elif state == "waiting_safe_entry":
                state = self._step_waiting_battle()
            elif state == "waiting_safe_entry_timeout":
                state = self._step_waiting_timeout()
            elif state == "navigating":
                state = self._step_navigating()
            elif state == "verifying_entry":
                state = self._step_verifying()
            elif state == "ready":
                return self._result(EntryOutcome.READY, "ready")
            elif state == "manual":
                return self._result(EntryOutcome.MANUAL, "manual_takeover")
            elif state == "stopped":
                return self._result(EntryOutcome.STOPPED, "stopped")
            else:
                # ERROR 终态：带 error_code 与最后证据
                return self._result(EntryOutcome.ERROR, "entry_failed")

    # ==================== 状态步骤 ====================

    def _step_preparing(self) -> str:
        snapshot = self._resolve_or_fail()
        if snapshot is None:
            return "error"
        self._last_snapshot = snapshot

        if "wanted_quest" in snapshot.overlays:
            return self._step_wanted_quest(snapshot)
        if snapshot.overlays:
            return self._fail(
                ENTRY_OVERLAY_UNSAFE,
                f"不支持的覆盖层，不点击推测位置: {snapshot.overlays}",
            )
        if snapshot.mode is SceneMode.STABLE:
            if snapshot.base_scene == self._spec.target_scene:
                self._stable_count = 0
                self._report.on_stage_change("verifying_entry")
                return "verifying_entry"
            self._stable_count = 0
            self._report.on_stage_change("navigating")
            return "navigating"
        if snapshot.mode is SceneMode.BATTLE:
            self._battle_wait_seconds = 0.0
            self._battle_window_deadline = (
                self._monotonic() + self._spec.battle_wait_window_seconds
            )
            self._report.on_stage_change("waiting_safe_entry")
            return "waiting_safe_entry"
        if snapshot.mode is SceneMode.SETTLEMENT:
            self._dismiss_settlement(snapshot)
            self._sleep(self._spec.observation_interval_seconds)
            return "preparing"
        if snapshot.mode is SceneMode.TRANSITION:
            self._sleep(self._spec.observation_interval_seconds)
            return "preparing"
        if "wanted_quest" in snapshot.overlays:
            return self._step_wanted_quest(snapshot)
        return self._step_unknown("preparing")

    def _step_waiting_battle(self) -> str:
        """战斗等待：只观察，不发送任何输入。"""
        self._battle_wait_seconds = self._monotonic() - (
            self._battle_window_deadline - self._spec.battle_wait_window_seconds
        )
        if self._monotonic() >= self._battle_window_deadline:
            self._report.on_stage_change("waiting_safe_entry_timeout")
            return "waiting_safe_entry_timeout"

        snapshot = self._resolve_or_fail()
        if snapshot is None:
            return "error"
        self._last_snapshot = snapshot

        if snapshot.mode is SceneMode.BATTLE:
            self._sleep(self._spec.observation_interval_seconds)
            return "waiting_safe_entry"
        if snapshot.mode is SceneMode.SETTLEMENT:
            self._dismiss_settlement(snapshot)
            self._sleep(self._spec.observation_interval_seconds)
            return "preparing"
        if snapshot.mode is SceneMode.STABLE:
            return "preparing"
        if snapshot.mode is SceneMode.TRANSITION:
            self._sleep(self._spec.observation_interval_seconds)
            return "waiting_safe_entry"
        if "wanted_quest" in snapshot.overlays:
            return self._step_wanted_quest(snapshot)
        if snapshot.overlays:
            return self._fail(
                ENTRY_OVERLAY_UNSAFE,
                f"不支持的覆盖层，不点击推测位置: {snapshot.overlays}",
            )
        # 未知：有界重识别；连续未知由 RunGuard 的 unknown_limit 兜底
        return self._step_unknown("waiting_safe_entry")

    def _step_waiting_timeout(self) -> str:
        """战斗窗口超时：等待用户命令（继续等待/转人工/停止）。"""
        while True:
            if self._guard is not None and self._guard.is_stopped:
                return "stopped"
            command = self._take_command()
            if command == "continue":
                self._continue_wait_count += 1
                self._battle_window_deadline = (
                    self._monotonic() + self._spec.battle_wait_window_seconds
                )
                self._report.on_stage_change(
                    "waiting_safe_entry",
                    {"continue_wait_count": self._continue_wait_count},
                )
                return "waiting_safe_entry"
            if command == "manual":
                return "manual"
            if command == "stop":
                return "stopped"
            self._sleep(self.COMMAND_POLL_INTERVAL_SECONDS)

    def _step_navigating(self) -> str:
        """按场景图路径逐边导航；每条边后置验证通过才推进。"""
        assert (
            self._last_snapshot is not None
            and self._last_snapshot.base_scene is not None
        )
        current = self._last_snapshot.base_scene
        path = self._scene_manager.get_shortest_path(current, self._spec.target_scene)
        if path is None:
            return self._fail(
                ENTRY_TRANSITION_NOT_FOUND,
                f"不存在从 {current} 到 {self._spec.target_scene} 的路径",
            )

        transitions = [
            Transition(
                source=src,
                target=dst,
                action_image=button,
                timeout_seconds=self._edge_verify_interval_seconds,
                retries=self._edge_retries,
                risk=TransitionRisk.SAFE,
            )
            for src, dst, button in path
        ]
        for edge in transitions:
            if not self._execute_edge(edge):
                return self._fail(
                    ENTRY_TRANSITION_FAILED,
                    f"导航边失败: {edge.source} -> {edge.target}",
                )
            self._sleep(self._edge_verify_interval_seconds)

        self._stable_count = 0
        self._report.on_stage_change("verifying_entry")
        return "verifying_entry"

    def _step_verifying(self) -> str:
        """入口稳定验证：连续 stable_observations 次命中目标场景。"""
        snapshot = self._resolve_or_fail()
        if snapshot is None:
            return "error"
        self._last_snapshot = snapshot

        if (
            snapshot.mode is SceneMode.STABLE
            and snapshot.base_scene == self._spec.target_scene
        ):
            self._stable_count += 1
            if self._stable_count >= self._spec.stable_observations:
                return "ready"
            self._sleep(self._spec.stable_interval_seconds)
            return "verifying_entry"
        if snapshot.mode is SceneMode.BATTLE:
            self._battle_wait_seconds = 0.0
            self._battle_window_deadline = (
                self._monotonic() + self._spec.battle_wait_window_seconds
            )
            self._report.on_stage_change("waiting_safe_entry")
            return "waiting_safe_entry"
        if snapshot.mode is SceneMode.SETTLEMENT:
            self._dismiss_settlement(snapshot)
            self._sleep(self._spec.observation_interval_seconds)
            return "preparing"
        # 偏离目标或未知：回到准备阶段重新解析
        self._stable_count = 0
        return "preparing"

    # ==================== 局部动作 ====================

    def _step_wanted_quest(self, snapshot: SceneSnapshot) -> str:
        """悬赏封印覆盖层：仅配置为拒绝时点击已确认的拒绝模板。"""
        policy = self._spec.safe_overlay_policy
        if (
            not policy.refuse_wanted_quests
            or policy.wanted_quest_reject_template is None
        ):
            return self._fail(
                ENTRY_OVERLAY_UNSAFE,
                "悬赏封印策略不允许自动处理（接受类或未配置拒绝模板）",
            )
        match = self._find_template(policy.wanted_quest_reject_template)
        if match is None or not match.is_found:
            return self._fail(
                ENTRY_OVERLAY_UNSAFE,
                "未确认悬赏封印拒绝按钮位置，不点击推测坐标",
            )
        self._click_env(match.point)
        self._sleep(self._spec.observation_interval_seconds)
        return "preparing"

    def _dismiss_settlement(self, snapshot: SceneSnapshot) -> None:
        """关闭已确认的战斗结算（独立处理，不触碰业务计数）。"""
        for template in self._spec.safe_overlay_policy.settlement_templates:
            match = self._find_template(template)
            if match is not None and match.is_found:
                self._click_env(match.point)
                return

    def _step_unknown(self, current_state: str) -> str:
        """未知画面有界重识别；超出上限后结构化失败，零输入。"""
        self._unknown_count += 1
        if self._unknown_count > self.UNKNOWN_RESOLVE_ATTEMPTS:
            return self._fail(
                ENTRY_SCENE_UNKNOWN,
                f"连续 {self._unknown_count} 次无法识别当前画面",
            )
        self._sleep(self._spec.observation_interval_seconds)
        return current_state

    def _execute_edge(self, edge: Transition) -> bool:
        """执行一条导航边：找按钮 → 点击 → 后置验证，有界重试。"""
        for _attempt in range(edge.retries + 1):
            if self._guard is not None and self._guard.is_stopped:
                return False
            match = self._find_template(edge.action_image)
            if match is None or not match.is_found:
                self._sleep(self._edge_verify_interval_seconds)
                continue
            self._click_env(match.point)
            self._sleep(self._edge_verify_interval_seconds)
            if self._verify_after_edge(edge.target):
                return True
        return False

    def _verify_after_edge(self, target_scene: str) -> bool:
        """验证跳转后的后置场景是否为目标场景（等价于入口稳定验证）。"""
        snapshot = self._resolve_or_fail()
        if snapshot is None:
            return False
        self._last_snapshot = snapshot
        return (
            snapshot.mode is SceneMode.STABLE
            and snapshot.base_scene == target_scene
        )

    # ==================== 基础设施 ====================

    def _resolve_or_fail(self) -> Optional[SceneSnapshot]:
        """截图并识别；截图/识别失败返回 None（上层转 ENTRY_CAPTURE_FAILED）。"""
        try:
            frame = self._env.capture_screen()
            self._last_frame = frame
            return self._resolver.resolve(frame)
        except Exception as exc:  # noqa: BLE001 - 截图失败是产品级错误路径
            self._fail(
                ENTRY_CAPTURE_FAILED,
                f"截图或识别失败: {exc}",
            )
            return None

    def _find_template(
        self, template_path: str, threshold: float = 0.8
    ) -> Optional[ImageMatchResult]:
        """查找模板位置；低于命中阈值视为未命中（只读，不发送输入）。"""
        frame = self._last_frame
        if frame is None:
            return None
        img = np.array(frame) if not isinstance(frame, np.ndarray) else frame
        result = self._image_finder.best_match(img, template_path)
        if result is None or not result.is_found or result.similarity < threshold:
            return None
        return result

    def _click_env(self, point: Tuple[int, int]) -> None:
        """通过注入环境点击（GuardedEnvironment 负责动作预算与观察记录）。"""
        self._env.left_click(point[0], point[1])

    def _take_command(self) -> Optional[str]:
        command = self._pending_command
        self._pending_command = None
        return command

    def _fail(self, error_code: str, reason: str) -> str:
        """记录失败并上报 entry_failed 阶段。"""
        self._error_code = error_code
        self._error_reason = reason
        self._report.on_stage_change(
            "entry_failed",
            {"error_code": error_code, "reason": reason},
        )
        return "error"

    def _result(
        self,
        outcome: EntryOutcome,
        stage: str,
        reason: Optional[str] = None,
    ) -> EntryPreparationResult:
        return EntryPreparationResult(
            outcome=outcome,
            stage=stage,
            error_code=self._error_code,
            reason=reason or self._error_reason,
            snapshot=self._last_snapshot,
            battle_wait_seconds=self._battle_wait_seconds,
            continue_wait_count=self._continue_wait_count,
        )
