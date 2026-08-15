from __future__ import annotations

import inspect
import json
import threading
import time
import traceback
from typing import Any

from ui_backend.events.hub import EventHub
from ui_backend.models import (
    RunRequest,
    RunSourceType,
    RunStatus,
    available_actions_for_run,
    available_actions_for_status,
)
from ui_backend.scripts.registry import ScriptRegistry
from ui_backend.screenshots import ScreenshotError, ScreenshotService
from ui_backend.storage.repositories import Storage
from win_util.environment.windows import WindowsEnvironment
from yys.common.entry_runtime import EntryOutcome, EntryPreparationError


class _RunStageReporter:
    """把 EntryPreparer 的阶段上报写入 storage 与事件流。

    终态阶段（entry_failed）由 RunManager 统一处理，此处只透传进行中阶段。
    """

    def __init__(self, manager: "RunManager", run_id: int) -> None:
        self._manager = manager
        self._run_id = run_id

    def on_stage_change(self, stage: str, detail: dict | None = None) -> None:
        if stage == "entry_failed":
            return
        self._manager.storage.runs.update_observation(
            self._run_id, stage=stage
        )
        self._manager._publish(
            {
                "type": "run_stage_changed",
                "run_id": self._run_id,
                "stage": stage,
                "detail": detail or {},
            }
        )
        self._manager._publish_run_snapshot(self._run_id)


class RunManager:
    """管理桌面工作台脚本运行生命周期。"""

    def __init__(
        self,
        storage: Storage,
        registry: ScriptRegistry,
        event_hub: EventHub,
        screenshot_service: ScreenshotService | None = None,
    ) -> None:
        """初始化运行管理器。"""
        self.storage = storage
        self.registry = registry
        self.event_hub = event_hub
        self.screenshot_service = screenshot_service or ScreenshotService(None)
        self._lock = threading.Lock()
        self._active_run_id: int | None = None
        self._scripts: dict[int, Any] = {}
        self._threads: dict[int, threading.Thread] = {}

    def start(self, request: RunRequest) -> int:
        """启动脚本运行，并返回运行记录 ID。"""
        with self._lock:
            if self._active_run_id is not None:
                raise RuntimeError("已有脚本正在运行")

            registry_default = self.registry.get(request.script_id).default_config or {}
            user_config = self.storage.script_user_configs.get(request.script_id) or {}
            merged_config = {**registry_default, **user_config, **request.config}

            run_id = self.storage.runs.create(
                script_id=request.script_id,
                source_type=request.source_type,
                config=merged_config,
                workflow_id=request.workflow_id,
                workflow_step_id=request.workflow_step_id,
                task_id=request.task_id or request.script_id,
                step_id=request.step_id or request.workflow_step_id,
                action_id=request.action_id,
                retry_count=request.retry_count,
                parent_run_id=request.parent_run_id,
            )
            self._active_run_id = run_id

        script: Any | None = None
        try:
            script_class = self.registry.load_class(request.script_id)
            # 检测脚本类是否接受 config 关键字参数：soul_raid 走新构造注入（auto-registry Step 3）
            # 5 个走老路径的子类（douji/omoikane/yuling/loop_challenge/script_main 等）无 config 参数 → 老路径
            sig = inspect.signature(script_class)
            if "config" in sig.parameters or any(
                p.kind is inspect.Parameter.VAR_KEYWORD
                for p in sig.parameters.values()
            ):
                # 新签名：构造注入
                script = script_class(request.script_id, config=merged_config)
            else:
                # 老签名：实例化 + setter（保留 _apply_config 作 fallback）
                script = script_class()
                self._apply_config(script, merged_config)
            self._install_unknown_scene_observer(run_id, request.script_id, script)
            thread = threading.Thread(
                target=self._run_script,
                args=(run_id, request.script_id, script),
                daemon=True,
            )
            with self._lock:
                self._scripts[run_id] = script
                self._threads[run_id] = thread
                # 新入口契约脚本从 preparing 阶段开始；旧脚本保持 script_running
                if getattr(script, "entry_spec", None) is not None:
                    start_stage = "preparing"
                else:
                    start_stage = "script_running"
                self.storage.runs.update_status(
                    run_id,
                    RunStatus.RUNNING,
                    stage=start_stage,
                    available_actions=available_actions_for_run(
                        RunStatus.RUNNING, start_stage
                    ),
                    progress=self._progress_from_state(self._snapshot(script)),
                )
                self._append_log(run_id, "INFO", "脚本开始运行")
                self._publish_status(run_id, RunStatus.RUNNING)
                self._publish_run_snapshot(run_id)
                thread.start()
        except Exception:
            traceback_text = traceback.format_exc()
            evidence = self._capture_failure_evidence(
                run_id,
                script,
                "脚本启动阶段无法捕获当前画面",
                "script_error",
                "start_failed",
            )
            self.storage.runs.update_status(
                run_id,
                RunStatus.ERROR,
                error_message=traceback_text,
                error_code="SCRIPT_START_FAILED",
                stage="start_failed",
                available_actions=available_actions_for_status(RunStatus.ERROR),
            )
            self._append_log(run_id, "ERROR", traceback_text)
            self._publish_status(
                run_id,
                RunStatus.ERROR,
                error_message=traceback_text,
                error_code="SCRIPT_START_FAILED",
                evidence=evidence,
            )
            self._clear_active(run_id)
            raise
        return run_id

    def pause(self, run_id: int) -> None:
        """暂停当前活动脚本。"""
        with self._lock:
            script = self._ensure_active(run_id)
            pause = getattr(script, "pause", None)
        if callable(pause):
            pause()
        with self._lock:
            if self._active_run_id != run_id:
                return
            self.storage.runs.update_status(
                run_id,
                RunStatus.PAUSED,
                stage="paused",
            )
            self._append_log(run_id, "INFO", "脚本已暂停")
            self._publish_status(run_id, RunStatus.PAUSED)

    def resume(self, run_id: int) -> None:
        """恢复当前活动脚本。"""
        with self._lock:
            script = self._ensure_active(run_id)
            resume = getattr(script, "resume", None)
        if callable(resume):
            resume()
        with self._lock:
            if self._active_run_id != run_id:
                return
            self.storage.runs.update_status(
                run_id,
                RunStatus.RUNNING,
                stage="script_running",
            )
            self._append_log(run_id, "INFO", "脚本已恢复")
            self._publish_status(run_id, RunStatus.RUNNING)

    def stop(self, run_id: int, timeout: float = 3.0) -> None:
        """停止当前活动脚本并等待线程退出。"""
        with self._lock:
            if self._active_run_id != run_id:
                run = self.storage.runs.get(run_id)
                if run is not None and run.get("status") == RunStatus.ERROR.value:
                    self.storage.runs.update_status(
                        run_id,
                        RunStatus.STOPPED,
                        stage="stopped_after_error",
                    )
                    self._append_log(run_id, "INFO", "失败运行已标记为停止")
                    self._publish_status(run_id, RunStatus.STOPPED)
                    return
                raise RuntimeError("运行记录不是当前活动脚本")
            script = self._ensure_active(run_id)
            stop = getattr(script, "stop", None)
        if callable(stop):
            stop()
        with self._lock:
            self.storage.runs.update_status(
                run_id,
                RunStatus.STOPPED,
                stage="stopping",
            )
            self._append_log(run_id, "INFO", "脚本已停止")
            self._publish_status(run_id, RunStatus.STOPPED)

        if not self.wait(run_id, timeout):
            evidence = self._capture_failure_evidence(
                run_id,
                script,
                "停止超时，记录停止时的当前画面",
                "stop_timeout",
                "stop_timeout",
            )
            self.storage.runs.update_status(
                run_id,
                RunStatus.STOPPED,
                error_code="STOP_TIMEOUT",
                stage="stop_timeout",
            )
            self._append_log(run_id, "WARNING", "停止超时，线程可能仍在退出中")
            self._publish_status(
                run_id,
                RunStatus.STOPPED,
                error_code="STOP_TIMEOUT",
                evidence=evidence,
            )
            self._clear_active(run_id)

    def retry(self, run_id: int) -> int:
        """重试失败或人工接管的运行，返回新 run ID（关联重试）。

        人工接管的 run 通过“重新识别并重试”创建关联新 run（AC12）：
        新 run 复制脚本配置与工作流上下文，parent_run_id 指向原 run。
        """
        with self._lock:
            if self._active_run_id is not None:
                raise RuntimeError("已有脚本正在运行")
            run = self.storage.runs.get(run_id)
        if run is None:
            raise KeyError(f"未知运行记录: {run_id}")
        if run.get("status") not in (RunStatus.ERROR.value, RunStatus.MANUAL.value):
            raise RuntimeError("只有失败或人工接管的运行可以重试")
        request = RunRequest(
            script_id=str(run["script_id"]),
            config=dict(run.get("config", {})),
            source_type=RunSourceType(str(run["source_type"])),
            workflow_id=run.get("workflow_id"),
            workflow_step_id=run.get("workflow_step_id"),
            task_id=run.get("task_id"),
            step_id=run.get("step_id"),
            action_id=run.get("action_id"),
            retry_count=int(run.get("retry_count") or 0) + 1,
            parent_run_id=run_id,
        )
        self._append_log(run_id, "INFO", "已请求重试")
        self._publish(
            {
                "type": "run_recovery_requested",
                "run_id": run_id,
                "action": "retry",
            }
        )
        return self.start(request)

    def continue_waiting(self, run_id: int) -> None:
        """战斗安全等待超时后，请求继续等待一个 3 分钟窗口（AC4）。

        Raises:
            RuntimeError: 非等待超时阶段或没有活动准备器。
        """
        with self._lock:
            if self._active_run_id != run_id:
                raise RuntimeError("运行记录不是当前活动脚本")
            run = self.storage.runs.get(run_id)
            if (
                run is None
                or run.get("status") != RunStatus.RUNNING.value
                or run.get("stage") != "waiting_safe_entry_timeout"
            ):
                raise RuntimeError("仅战斗等待超时阶段可以继续等待")
            script = self._scripts.get(run_id)
        if script is None or not callable(getattr(script, "request_entry_command", None)):
            raise RuntimeError("脚本当前不接受继续等待命令")
        if not script.request_entry_command("continue_waiting"):
            raise RuntimeError("脚本当前不接受继续等待命令")
        self._append_log(run_id, "INFO", "用户选择继续等待 3 分钟")
        self._publish(
            {
                "type": "run_stage_command",
                "run_id": run_id,
                "action": "continue_waiting",
            }
        )

    def skip(self, run_id: int) -> None:
        """将失败运行标记为跳过，并发布审计事件。"""
        self._mark_recovery_terminal(run_id, RunStatus.SKIPPED, "skip", "失败运行已跳过")

    def manual_takeover(self, run_id: int) -> None:
        """转人工接管：等待超时阶段直接请求，失败运行走既有恢复路径。"""
        with self._lock:
            active = self._active_run_id == run_id
            if active:
                run = self.storage.runs.get(run_id)
                if (
                    run is not None
                    and run.get("status") == RunStatus.RUNNING.value
                    and run.get("stage") == "waiting_safe_entry_timeout"
                ):
                    script = self._scripts.get(run_id)
                else:
                    raise RuntimeError("活动运行当前不接受人工接管")
            else:
                script = None
        if active and script is not None:
            if not callable(getattr(script, "request_entry_command", None)):
                raise RuntimeError("脚本当前不接受人工接管命令")
            if not script.request_entry_command("manual_takeover"):
                raise RuntimeError("脚本当前不接受人工接管命令")
            self._append_log(run_id, "INFO", "用户请求人工接管，正在终结当前运行")
            self._publish(
                {
                    "type": "run_stage_command",
                    "run_id": run_id,
                    "action": "manual_takeover",
                }
            )
            return
        # 既有行为：失败运行标记为人工接管
        self._mark_recovery_terminal(
            run_id,
            RunStatus.MANUAL,
            "manual_takeover",
            "已转入人工接管",
        )

    def _mark_recovery_terminal(
        self,
        run_id: int,
        status: RunStatus,
        action: str,
        message: str,
    ) -> None:
        """完成失败运行的非重试恢复动作。"""
        with self._lock:
            if self._active_run_id == run_id:
                raise RuntimeError("活动运行不能直接执行该恢复动作")
            run = self.storage.runs.get(run_id)
            if run is None:
                raise KeyError(f"未知运行记录: {run_id}")
            if run.get("status") != RunStatus.ERROR.value:
                raise RuntimeError("只有失败运行可以执行恢复动作")
            self.storage.runs.update_status(run_id, status, stage=action)
            self._append_log(run_id, "INFO", message)
            self._publish_status(run_id, status)
            self._publish(
                {
                    "type": "run_recovery_completed",
                    "run_id": run_id,
                    "action": action,
                    "status": status.value,
                }
            )

    def wait(self, run_id: int, timeout: float | None = None) -> bool:
        """等待指定运行线程退出，找不到线程时返回 True。"""
        with self._lock:
            thread = self._threads.get(run_id)
        if thread is None:
            return True
        thread.join(timeout)
        return not thread.is_alive()

    def current_run_id(self) -> int | None:
        """返回当前活动运行 ID。"""
        with self._lock:
            return self._active_run_id

    def run_status(self, run_id: int) -> str | None:
        """查询指定运行记录的当前状态。"""
        run = self.storage.runs.get(run_id)
        if run is None:
            return None
        status = run.get("status")
        if not isinstance(status, str):
            return None
        return status

    def _run_script(self, run_id: int, script_id: str, script: Any) -> None:
        sink_id = self._install_loguru_sink(run_id)
        stop_event = threading.Event()
        snapshot_thread = self._start_snapshot_pusher(run_id, script_id, script, stop_event)
        try:
            if getattr(script, "entry_spec", None) is not None:
                # 新入口契约：先准备，READY 后才进入业务运行（设计 §8.1）
                self._run_with_entry_preparation(run_id, script_id, script)
                return
            script.run()
            self._record_state_snapshot(run_id, script_id, script)
            if self._mark_success_if_not_stopped(run_id):
                if self.storage.runs.get(run_id).get("status") == RunStatus.SUCCESS.value:
                    self._append_log(run_id, "INFO", "脚本运行完成")
                    self._publish_status(run_id, RunStatus.SUCCESS)
        except EntryPreparationError as exc:
            self._finish_entry_preparation_error(run_id, script, exc.result)
        except Exception:
            traceback_text = traceback.format_exc()
            state = self._record_state_snapshot(run_id, script_id, script)
            evidence = self._capture_failure_evidence(
                run_id,
                script,
                "脚本异常时捕获当前画面",
                "script_error",
                "script_failed",
            )
            self._append_log(run_id, "ERROR", traceback_text)
            if self._mark_error_if_not_stopped(
                run_id,
                traceback_text,
                state=state,
                evidence=evidence,
            ):
                current = self.storage.runs.get(run_id)
                if current is not None and current.get("status") == RunStatus.ERROR.value:
                    self._publish_status(
                        run_id,
                        RunStatus.ERROR,
                        error_message=traceback_text,
                        error_code="SCRIPT_EXCEPTION",
                        evidence=evidence,
                    )
        finally:
            stop_event.set()
            if snapshot_thread is not None:
                snapshot_thread.join(timeout=2.0)
            self._remove_loguru_sink(sink_id)
            self._clear_active(run_id)

    def _run_with_entry_preparation(
        self, run_id: int, script_id: str, script: Any
    ) -> None:
        """新入口契约运行路径：prepare → READY → 业务运行（设计 §8.1）。

        入口失败/人工接管/停止分别写入对应终态，绝不写业务成功。
        """
        result = script.prepare_entry(_RunStageReporter(self, run_id))

        if result.outcome is EntryOutcome.READY:
            self.storage.runs.update_status(
                run_id,
                RunStatus.RUNNING,
                stage="script_running",
                available_actions=available_actions_for_run(
                    RunStatus.RUNNING, "script_running"
                ),
            )
            self._append_log(run_id, "INFO", "入口准备完成，进入业务运行")
            self._publish_run_snapshot(run_id)
            script.run_business()
            self._record_state_snapshot(run_id, script_id, script)
            if self._mark_success_if_not_stopped(run_id):
                if self.storage.runs.get(run_id).get("status") == RunStatus.SUCCESS.value:
                    self._append_log(run_id, "INFO", "脚本运行完成")
                    self._publish_status(run_id, RunStatus.SUCCESS)
            return

        if result.outcome is EntryOutcome.MANUAL:
            self._mark_entry_terminal(
                run_id,
                RunStatus.MANUAL,
                "manual_takeover",
                result.reason or "入口准备期间已转入人工接管",
            )
            return
        if result.outcome is EntryOutcome.STOPPED:
            self._mark_entry_terminal(
                run_id,
                RunStatus.STOPPED,
                "stopped",
                result.reason or "入口准备期间已停止",
            )
            return
        # error：结构化入口失败，带错误码与证据
        self._finish_entry_preparation_error(run_id, script, result)

    def _finish_entry_preparation_error(
        self, run_id: int, script: Any, result: Any
    ) -> None:
        """入口准备失败终态：error/entry_failed + 稳定错误码 + 证据。"""
        error_code = result.error_code or "ENTRY_FAILED"
        reason = result.reason or "入口准备失败"
        evidence = self._capture_failure_evidence(
            run_id,
            script,
            f"入口准备失败: {error_code}",
            "entry_error",
            "entry_failed",
        )
        self._append_log(run_id, "ERROR", f"[{error_code}] {reason}")
        if self._mark_entry_error_if_not_stopped(run_id, reason, error_code, evidence):
            self._publish_status(
                run_id,
                RunStatus.ERROR,
                error_message=reason,
                error_code=error_code,
                evidence=evidence,
            )

    def _mark_entry_terminal(
        self,
        run_id: int,
        status: RunStatus,
        stage: str,
        message: str,
    ) -> None:
        """入口准备终态（manual/stopped）：终态与活动槽释放作为同一操作。"""
        with self._lock:
            current = self.storage.runs.get(run_id)
            if current is not None and current.get("status") in {
                RunStatus.STOPPED.value,
                RunStatus.MANUAL.value,
            }:
                # 命令路径可能已先写入终态（stop() 等），不覆盖
                return
            self.storage.runs.update_status(
                run_id,
                status,
                stage=stage,
                available_actions=available_actions_for_run(status, stage),
            )
            self._append_log(run_id, "INFO", message)
            if self._active_run_id == run_id:
                self._active_run_id = None
        self._publish_status(run_id, status)

    def _mark_entry_error_if_not_stopped(
        self,
        run_id: int,
        error_message: str,
        error_code: str,
        evidence: dict[str, Any],
    ) -> bool:
        """写入 error/entry_failed 终态；已被停止时返回 False。"""
        with self._lock:
            current = self.storage.runs.get(run_id)
            if current is None or current.get("status") == RunStatus.STOPPED.value:
                return False
            self.storage.runs.update_status(
                run_id,
                RunStatus.ERROR,
                error_message=error_message,
                error_code=error_code,
                stage="entry_failed",
                available_actions=available_actions_for_run(
                    RunStatus.ERROR, "entry_failed"
                ),
            )
            self.storage.runs.set_latest_evidence(run_id, evidence)
            if self._active_run_id == run_id:
                self._active_run_id = None
            return True

    def _start_snapshot_pusher(
        self,
        run_id: int,
        script_id: str,
        script: Any,
        stop_event: threading.Event,
        interval: float = 1.0,
    ) -> threading.Thread | None:
        """启动后台线程，周期性推送 state_snapshot，使 UI 可观察战斗计数等实时进度。"""
        if not callable(getattr(script, "get_state_snapshot", None)):
            return None
        # 用列表保存 [state]，避免在闭包内重复调用 _snapshot
        holder: list[dict[str, Any]] = [{}]

        def _pusher() -> None:
            try:
                while not stop_event.wait(interval):
                    try:
                        holder[0] = self._snapshot(script) or {}
                    except Exception:
                        # 业务脚本在某些时机短暂异常时不应让 pusher 退出
                        continue
                    state = holder[0]
                    if not state:
                        continue
                    self.storage.runs.update_observation(
                        run_id,
                        stage="script_running",
                        progress=self._progress_from_state(state),
                    )
                    try:
                        self._publish(
                            {
                                "type": "state_snapshot",
                                "run_id": run_id,
                                "script_id": script_id,
                                "state": state,
                            }
                        )
                    except Exception:
                        # 推送失败不应让 pusher 退出，下一轮再试
                        continue
            except Exception:
                # 守护线程内任何未预期异常吞掉
                return

        thread = threading.Thread(target=_pusher, daemon=True)
        thread.start()
        return thread

    def _record_state_snapshot(
        self,
        run_id: int,
        script_id: str,
        script: Any,
    ) -> dict[str, Any]:
        """保存并发布一次脚本状态快照。"""
        try:
            state = self._snapshot(script)
            progress = self._progress_from_state(state)
            self.storage.snapshots.append(run_id, script_id, state)
            self.storage.runs.update_observation(
                run_id,
                stage="script_running",
                progress=progress,
            )
            self._publish(
                {
                    "type": "state_snapshot",
                    "run_id": run_id,
                    "script_id": script_id,
                    "state": state,
                    "progress": progress,
                }
            )
        except Exception:
            # 业务异常收尾阶段不能因快照失败而丢失原始错误。
            state = {}
        return state

    def _progress_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """从通用脚本状态推导统一进度字段。"""
        current = state.get("battle_count", state.get("current_battle_count"))
        total = state.get("max_battle_count")
        if not isinstance(current, (int, float)):
            return {}
        result: dict[str, Any] = {"current": current}
        if isinstance(total, (int, float)) and total > 0:
            result["total"] = total
            result["percent"] = round(min(100.0, max(0.0, current / total * 100)), 1)
        return result

    def _install_loguru_sink(self, run_id: int) -> int:
        """安装一个 loguru sink，把业务脚本的日志桥接到 storage 与 event_hub。"""
        from loguru import logger

        def _sink(message: "Any") -> None:
            """loguru sink 回调。必须非阻塞，并吞掉一切异常以避免影响业务。"""
            record = message.record
            level_name = record["level"].name
            text = record["message"]
            # 当调用 logger.exception() 时，loguru 会把异常信息放在 record["exception"]
            exc_info = record.get("exception")
            if exc_info is not None:
                try:
                    tb_str = "".join(
                        traceback.format_exception(
                            exc_info.type, exc_info.value, exc_info.traceback
                        )
                    )
                    text = f"{text}\n{tb_str}"
                except Exception:
                    # traceback 拼接失败时，保留原始 message 即可
                    pass
            # 落库（异常吞掉，避免 sink 自身抛错）
            try:
                self.storage.logs.append(run_id, level_name, text)
            except Exception:
                pass
            # 推送给前端（event_hub 的 publish_from_thread 已是线程安全的非阻塞入队）
            try:
                self._publish_log(run_id, level_name, text)
            except Exception:
                pass

        return logger.add(_sink, level="DEBUG", format="{message}")

    def _remove_loguru_sink(self, sink_id: int) -> None:
        """移除安装的 loguru sink。已不存在时静默忽略。"""
        from loguru import logger

        try:
            logger.remove(sink_id)
        except ValueError:
            pass

    def _apply_config(self, script: Any, config: dict[str, Any]) -> None:
        max_battle_count = config.get("max_battle_count")
        setter = getattr(script, "set_max_battle_count", None)
        if max_battle_count is not None and callable(setter):
            setter(int(max_battle_count))

    def _snapshot(self, script: Any) -> dict[str, Any]:
        getter = getattr(script, "get_state_snapshot", None)
        if not callable(getter):
            return {}
        try:
            state = getter()
        except Exception:
            return {}
        if not isinstance(state, dict):
            return {}
        return state

    def _mark_success_if_not_stopped(self, run_id: int) -> bool:
        with self._lock:
            run = self.storage.runs.get(run_id)
            if run is None or run["status"] == RunStatus.STOPPED.value:
                return False
            with self.storage.db.connect() as conn:
                cur = conn.execute(
                    """
                    UPDATE runs
                    SET status = ?,
                        ended_at = COALESCE(ended_at, CURRENT_TIMESTAMP),
                        error_code = NULL,
                        error_message = NULL,
                        stage = ?,
                        available_actions_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status != ?
                    """,
                    (
                        RunStatus.SUCCESS.value,
                        "completed",
                        "[]",
                        run_id,
                        RunStatus.STOPPED.value,
                    ),
                )
                changed = cur.rowcount > 0
                if changed and self._active_run_id == run_id:
                    self._active_run_id = None
                return changed

    def _mark_error_if_not_stopped(
        self,
        run_id: int,
        error_message: str,
        state: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> bool:
        with self._lock:
            run = self.storage.runs.get(run_id)
            if run is None or run["status"] == RunStatus.STOPPED.value:
                return False
            with self.storage.db.connect() as conn:
                cur = conn.execute(
                    """
                    UPDATE runs
                    SET status = ?,
                        ended_at = COALESCE(ended_at, CURRENT_TIMESTAMP),
                        error_code = ?,
                        error_message = ?,
                        stage = ?,
                        progress_json = ?,
                        available_actions_json = ?,
                        latest_evidence_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status != ?
                    """,
                    (
                        RunStatus.ERROR.value,
                        "SCRIPT_EXCEPTION",
                        error_message,
                        "script_failed",
                        json.dumps(
                            self._progress_from_state(state or {}),
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            available_actions_for_status(RunStatus.ERROR),
                            ensure_ascii=False,
                        ),
                        json.dumps(evidence, ensure_ascii=False) if evidence else None,
                        run_id,
                        RunStatus.STOPPED.value,
                    ),
                )
                changed = cur.rowcount > 0
                if changed and self._active_run_id == run_id:
                    self._active_run_id = None
                return changed

    def _ensure_active(self, run_id: int) -> Any:
        if self._active_run_id != run_id:
            raise RuntimeError("运行记录不是当前活动脚本")
        script = self._scripts.get(run_id)
        if script is None:
            raise RuntimeError("脚本尚未准备就绪")
        return script

    def _clear_active(self, run_id: int) -> None:
        with self._lock:
            self._threads.pop(run_id, None)
            self._scripts.pop(run_id, None)
            if self._active_run_id == run_id:
                self._active_run_id = None

    def _publish_status(
        self,
        run_id: int,
        status: RunStatus,
        error_message: str | None = None,
        error_code: str | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "type": "run_status_changed",
            "run_id": run_id,
            "status": status.value,
        }
        if error_message is not None:
            event["error_message"] = error_message
        if error_code is not None:
            event["error_code"] = error_code
        if evidence is not None:
            event["evidence"] = evidence
        self._publish(event)
        self._publish_run_snapshot(run_id)

    def _publish_run_snapshot(self, run_id: int) -> None:
        """发布 API 与 WebSocket 共用的规范化运行快照。"""
        run = self.storage.runs.get(run_id)
        if run is None:
            return
        run["latest_snapshot"] = self.storage.snapshots.latest_by_run(run_id)
        run["evidence"] = self.storage.evidence.list_by_run(run_id)
        self._publish({"type": "run_snapshot", "snapshot": run, "run_id": run_id})

    def _capture_failure_evidence(
        self,
        run_id: int,
        script: Any | None,
        description: str,
        trigger: str,
        stage: str,
    ) -> dict[str, Any]:
        """尽力保存当前截图，并始终记录证据捕获结果。"""
        capture_error: str | None = None
        saved_path: str | None = None
        screenshot_id: str | None = None
        try:
            run = self.storage.runs.get(run_id) or {}
            frame = self._copy_script_screenshot(script)
            saved = self.screenshot_service.save_full(
                frame,
                trigger=trigger,
                run_id=run_id,
                script_id=str(run.get("script_id") or "") or None,
                stage=stage,
            )
            screenshot_id = str(saved["id"])
            saved_path = str(self.screenshot_service.content_path(screenshot_id).resolve())
            self._publish({"type": "screenshot_saved", "screenshot": saved, "run_id": run_id})
        except Exception as exc:
            capture_error = str(exc)

        evidence_id = self.storage.evidence.append(
            run_id,
            kind="screenshot",
            path=saved_path,
            description=description,
            capture_error=capture_error,
        )
        evidence = {
            "id": evidence_id,
            "run_id": run_id,
            "kind": "screenshot",
            "path": saved_path,
            "screenshot_id": screenshot_id,
            "description": description,
            "capture_error": capture_error,
        }
        self.storage.runs.set_latest_evidence(run_id, evidence)
        return evidence

    def _copy_script_screenshot(self, script: Any | None) -> Any:
        """只复制脚本当前缓存，不刷新、不捕获也不回退前台。"""
        if script is None:
            raise RuntimeError("脚本没有可用的截图缓存")
        finder = getattr(script, "image_finder", None)
        if finder is None:
            controller = getattr(script, "win_controller", None)
            finder = getattr(controller, "image_finder", None)
        cache = getattr(finder, "screenshot_cache", None)
        if cache is None or not callable(getattr(cache, "copy", None)):
            raise RuntimeError("脚本没有可用的截图缓存")
        return cache.copy()

    def capture_manual_screenshot(self) -> dict[str, Any]:
        """手动捕获：活动运行复制缓存，空闲时才激活并截取游戏客户区。"""
        restore_required = False
        try:
            with self._lock:
                run_id = self._active_run_id
                script = self._scripts.get(run_id) if run_id is not None else None
                run = self.storage.runs.get(run_id) if run_id is not None else None
                if run_id is not None:
                    # 点击时重新解析句柄；运行中仍只复制缓存，避免抢焦点和刷新画面。
                    WindowsEnvironment(hwnd=None, window_title="阴阳师")
                    frame = self._copy_script_screenshot(script)
                else:
                    # 捕获完成前占住活动槽，避免新 run 在前台截图期间启动。
                    restore_required = True
                    environment = WindowsEnvironment(
                        hwnd=None,
                        window_title="阴阳师",
                        capture_mode="foreground",
                    )
                    environment.activate_window()
                    time.sleep(0.5)
                    frame = environment.capture_screen()
            saved = self.screenshot_service.save_full(
                frame,
                trigger="manual",
                run_id=run_id,
                script_id=str(run.get("script_id") or "") if run else None,
                stage=str(run.get("stage") or "") if run else None,
            )
            self.record_saved_screenshot(saved, "手动保存当前运行画面")
            return {**saved, "restore_required": restore_required}
        except ScreenshotError as exc:
            raise ScreenshotError(
                exc.detail,
                exc.status_code,
                restore_required=restore_required,
            ) from exc
        except Exception as exc:
            raise ScreenshotError(
                str(exc),
                409,
                restore_required=restore_required,
            ) from exc

    def record_saved_screenshot(
        self,
        screenshot: dict[str, Any],
        description: str,
    ) -> None:
        """发布截图事件，并在关联运行存在时追加证据。"""
        run_id = screenshot.get("run_id")
        if isinstance(run_id, int):
            self._append_screenshot_evidence(run_id, screenshot, description)
            self._publish_run_snapshot(run_id)
        self._publish({"type": "screenshot_saved", "screenshot": screenshot, "run_id": run_id})

    def _install_unknown_scene_observer(
        self,
        run_id: int,
        script_id: str,
        script: Any,
    ) -> None:
        """为事件脚本安装三轮未知、每段一次的截图观察器。"""
        setter = getattr(script, "set_recognition_observer", None)
        if not callable(setter):
            return
        consecutive_unknown = 0
        captured_for_episode = False

        def observe(recognized: bool) -> None:
            nonlocal consecutive_unknown, captured_for_episode
            if recognized:
                consecutive_unknown = 0
                captured_for_episode = False
                return
            consecutive_unknown += 1
            if consecutive_unknown != 3 or captured_for_episode:
                return
            captured_for_episode = True
            try:
                frame = self._copy_script_screenshot(script)
            except Exception as exc:
                threading.Thread(
                    target=self._append_capture_error,
                    args=(run_id, "连续三轮未识别场景", str(exc)),
                    daemon=True,
                ).start()
                return
            threading.Thread(
                target=self._save_unknown_scene,
                args=(run_id, script_id, frame),
                daemon=True,
            ).start()

        setter(observe)

    def _save_unknown_scene(
        self,
        run_id: int,
        script_id: str,
        frame: Any,
    ) -> None:
        try:
            saved = self.screenshot_service.save_full(
                frame,
                trigger="unknown_scene",
                run_id=run_id,
                script_id=script_id,
                stage="script_running",
            )
            self.record_saved_screenshot(saved, "连续三轮未识别到注册事件")
        except Exception as exc:
            self._append_capture_error(run_id, "连续三轮未识别场景", str(exc))

    def _append_screenshot_evidence(
        self,
        run_id: int,
        screenshot: dict[str, Any],
        description: str,
    ) -> dict[str, Any]:
        path = str(self.screenshot_service.content_path(str(screenshot["id"])).resolve())
        evidence_id = self.storage.evidence.append(
            run_id,
            kind="screenshot",
            path=path,
            description=description,
        )
        evidence = {
            "id": evidence_id,
            "run_id": run_id,
            "kind": "screenshot",
            "path": path,
            "screenshot_id": screenshot["id"],
            "description": description,
            "capture_error": None,
        }
        self.storage.runs.set_latest_evidence(run_id, evidence)
        return evidence

    def _append_capture_error(self, run_id: int, description: str, error: str) -> None:
        evidence_id = self.storage.evidence.append(
            run_id,
            kind="screenshot",
            description=description,
            capture_error=error,
        )
        evidence = {
            "id": evidence_id,
            "run_id": run_id,
            "kind": "screenshot",
            "path": None,
            "description": description,
            "capture_error": error,
        }
        self.storage.runs.set_latest_evidence(run_id, evidence)
        self._publish_run_snapshot(run_id)

    def _publish_log(self, run_id: int, level: str, message: str) -> None:
        self._publish(
            {
                "type": "log",
                "run_id": run_id,
                "level": level,
                "message": message,
            }
        )

    def _publish(self, event: dict[str, Any]) -> None:
        self.event_hub.publish_from_thread(event)

    def _append_log(self, run_id: int, level: str, message: str) -> None:
        self.storage.logs.append(run_id, level, message)
        self._publish_log(run_id, level, message)
