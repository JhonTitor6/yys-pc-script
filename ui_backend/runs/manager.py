from __future__ import annotations

import threading
import traceback
from typing import Any

from ui_backend.events.hub import EventHub
from ui_backend.models import RunRequest, RunStatus
from ui_backend.scripts.registry import ScriptRegistry
from ui_backend.storage.repositories import Storage


class RunManager:
    """管理桌面工作台脚本运行生命周期。"""

    def __init__(
        self,
        storage: Storage,
        registry: ScriptRegistry,
        event_hub: EventHub,
    ) -> None:
        """初始化运行管理器。"""
        self.storage = storage
        self.registry = registry
        self.event_hub = event_hub
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
            )
            self._active_run_id = run_id

        try:
            script_class = self.registry.load_class(request.script_id)
            script = script_class()
            self._apply_config(script, merged_config)
            thread = threading.Thread(
                target=self._run_script,
                args=(run_id, request.script_id, script),
                daemon=True,
            )
            with self._lock:
                self._scripts[run_id] = script
                self._threads[run_id] = thread
                self.storage.runs.update_status(run_id, RunStatus.RUNNING)
                self._append_log(run_id, "INFO", "脚本开始运行")
                self._publish_status(run_id, RunStatus.RUNNING)
                thread.start()
        except Exception:
            traceback_text = traceback.format_exc()
            self.storage.runs.update_status(run_id, RunStatus.ERROR, error_message=traceback_text)
            self._append_log(run_id, "ERROR", traceback_text)
            self._publish_status(run_id, RunStatus.ERROR, error_message=traceback_text)
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
            self.storage.runs.update_status(run_id, RunStatus.PAUSED)
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
            self.storage.runs.update_status(run_id, RunStatus.RUNNING)
            self._append_log(run_id, "INFO", "脚本已恢复")
            self._publish_status(run_id, RunStatus.RUNNING)

    def stop(self, run_id: int, timeout: float = 3.0) -> None:
        """停止当前活动脚本并等待线程退出。"""
        with self._lock:
            script = self._ensure_active(run_id)
            stop = getattr(script, "stop", None)
        if callable(stop):
            stop()
        with self._lock:
            self.storage.runs.update_status(run_id, RunStatus.STOPPED)
            self._append_log(run_id, "INFO", "脚本已停止")
            self._publish_status(run_id, RunStatus.STOPPED)

        if not self.wait(run_id, timeout):
            self._append_log(run_id, "WARNING", "停止超时，线程可能仍在退出中")
            self._clear_active(run_id)

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
        try:
            script.run()
            state = self._snapshot(script)
            self.storage.snapshots.append(run_id, script_id, state)
            self._publish(
                {
                    "type": "state_snapshot",
                    "run_id": run_id,
                    "script_id": script_id,
                    "state": state,
                }
            )
            if self._mark_success_if_not_stopped(run_id):
                self._append_log(run_id, "INFO", "脚本运行完成")
                self._publish_status(run_id, RunStatus.SUCCESS)
        except Exception:
            traceback_text = traceback.format_exc()
            self._append_log(run_id, "ERROR", traceback_text)
            if self._mark_error_if_not_stopped(run_id, traceback_text):
                self._publish_status(run_id, RunStatus.ERROR, error_message=traceback_text)
        finally:
            self._remove_loguru_sink(sink_id)
            self._clear_active(run_id)

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
        state = getter()
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
                        error_message = NULL
                    WHERE id = ? AND status != ?
                    """,
                    (RunStatus.SUCCESS.value, run_id, RunStatus.STOPPED.value),
                )
                return cur.rowcount > 0

    def _mark_error_if_not_stopped(self, run_id: int, error_message: str) -> bool:
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
                        error_message = ?
                    WHERE id = ? AND status != ?
                    """,
                    (
                        RunStatus.ERROR.value,
                        error_message,
                        run_id,
                        RunStatus.STOPPED.value,
                    ),
                )
                return cur.rowcount > 0

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
    ) -> None:
        event: dict[str, Any] = {
            "type": "run_status_changed",
            "run_id": run_id,
            "status": status.value,
        }
        if error_message is not None:
            event["error_message"] = error_message
        self._publish(event)

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
