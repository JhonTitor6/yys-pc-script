from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

from ui_backend.events.hub import EventHub
from ui_backend.models import RunRequest, RunStatus
from ui_backend.runs.manager import RunManager
from ui_backend.storage.database import Database
from ui_backend.storage.repositories import Storage
from win_util.event import EventBaseScript


class FakeScript:
    def __init__(self) -> None:
        self.max_battle_count = 1
        self.battle_count = 0
        self.paused = False
        self.stopped = False

    def set_max_battle_count(self, max_battle_count: int) -> None:
        self.max_battle_count = max_battle_count

    def run(self) -> None:
        while self.battle_count < self.max_battle_count and not self.stopped:
            if self.paused:
                time.sleep(0.01)
                continue
            self.battle_count += 1
            time.sleep(0.01)

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def stop(self) -> None:
        self.stopped = True

    def get_state_snapshot(self) -> dict[str, Any]:
        return {"battle_count": self.battle_count}


class FakeRegistry:
    def __init__(self, scripts: dict[str, type] | None = None) -> None:
        self.scripts = {"fake": FakeScript}
        if scripts is not None:
            self.scripts.update(scripts)

    def load_class(self, script_id: str) -> type:
        try:
            return self.scripts[script_id]
        except KeyError as exc:
            raise KeyError(script_id) from exc

    def get(self, script_id: str) -> Any:
        """返回一个轻量的脚本定义占位，仅提供 default_config 属性。"""
        return type("FakeScriptDefinition", (), {"default_config": {}})()


def create_run_manager(tmp_path: Path, registry: FakeRegistry | None = None) -> RunManager:
    db = Database(tmp_path / "ui.db")
    db.initialize()
    storage = Storage(db)
    return RunManager(storage=storage, registry=registry or FakeRegistry(), event_hub=EventHub())


@pytest.fixture
def run_manager(tmp_path: Path) -> RunManager:
    return create_run_manager(tmp_path)


def test_run_manager_allows_only_one_active_run(run_manager: RunManager) -> None:
    first_id = run_manager.start(RunRequest(script_id="fake", config={"max_battle_count": 20}))

    with pytest.raises(RuntimeError, match="已有脚本正在运行"):
        run_manager.start(RunRequest(script_id="fake", config={"max_battle_count": 1}))

    run_manager.stop(first_id)


def test_run_manager_finishes_and_saves_snapshot(run_manager: RunManager) -> None:
    run_id = run_manager.start(RunRequest(script_id="fake", config={"max_battle_count": 2}))

    run_manager.wait(run_id, timeout=1.0)

    run = run_manager.storage.runs.get(run_id)
    assert run is not None
    assert run["status"] == RunStatus.SUCCESS.value
    snapshot = run_manager.storage.snapshots.latest_by_run(run_id)
    assert snapshot is not None
    assert snapshot["state"]["battle_count"] == 2


def test_run_manager_publishes_state_snapshot_event(run_manager: RunManager) -> None:
    run_id = run_manager.start(RunRequest(script_id="fake", config={"max_battle_count": 1}))

    run_manager.wait(run_id, timeout=1.0)

    events = run_manager.event_hub.recent_events()
    assert any(event["type"] == "state_snapshot" for event in events)


def test_stop_does_not_call_script_stop_while_holding_manager_lock(tmp_path: Path) -> None:
    manager_ref: dict[str, RunManager] = {}

    class LockCheckingScript:
        def __init__(self) -> None:
            self.stopped = False

        def run(self) -> None:
            while not self.stopped:
                time.sleep(0.01)

        def stop(self) -> None:
            manager_ref["manager"].current_run_id()
            self.stopped = True

        def get_state_snapshot(self) -> dict[str, Any]:
            return {"stopped": self.stopped}

    manager = create_run_manager(tmp_path, FakeRegistry({"lock_check": LockCheckingScript}))
    manager_ref["manager"] = manager
    run_id = manager.start(RunRequest(script_id="lock_check", config={}))
    stopped = threading.Event()
    errors: list[BaseException] = []

    def call_stop() -> None:
        try:
            manager.stop(run_id, timeout=0.5)
        except BaseException as exc:
            errors.append(exc)
        finally:
            stopped.set()

    thread = threading.Thread(target=call_stop, daemon=True)
    thread.start()
    thread.join(0.2)

    assert errors == []
    assert stopped.is_set()


def test_stopped_run_exception_keeps_stopped_status_and_logs_traceback(tmp_path: Path) -> None:
    class StopThenRaiseScript:
        def __init__(self) -> None:
            self.stopped = False

        def run(self) -> None:
            while not self.stopped:
                time.sleep(0.01)
            raise RuntimeError("停止后异常")

        def stop(self) -> None:
            self.stopped = True

    manager = create_run_manager(tmp_path, FakeRegistry({"stop_raise": StopThenRaiseScript}))

    run_id = manager.start(RunRequest(script_id="stop_raise", config={}))
    manager.stop(run_id, timeout=1.0)

    run = manager.storage.runs.get(run_id)
    logs = manager.storage.logs.list_by_run(run_id)
    assert run is not None
    assert run["status"] == RunStatus.STOPPED.value
    assert any("Traceback" in log["message"] and "RuntimeError" in log["message"] for log in logs)


def test_stop_logs_warning_when_thread_does_not_exit_before_timeout(tmp_path: Path) -> None:
    class NeverExitScript:
        def run(self) -> None:
            while True:
                time.sleep(0.01)

        def stop(self) -> None:
            return None

    manager = create_run_manager(tmp_path, FakeRegistry({"never_exit": NeverExitScript}))

    run_id = manager.start(RunRequest(script_id="never_exit", config={}))
    manager.stop(run_id, timeout=0.01)

    logs = manager.storage.logs.list_by_run(run_id)
    events = manager.event_hub.recent_events()
    assert any(log["level"] == "WARNING" and "超时" in log["message"] for log in logs)
    assert any(
        event["type"] == "log"
        and event["level"] == "WARNING"
        and "超时" in event["message"]
        for event in events
    )


def test_stop_wakes_paused_event_script_and_releases_active_slot(tmp_path: Path) -> None:
    paused = threading.Event()

    class PausedEventScript(EventBaseScript):
        def run(self) -> None:
            self.pause()
            paused.set()
            self.pause_point()

    manager = create_run_manager(tmp_path, FakeRegistry({"paused_event": PausedEventScript}))

    run_id = manager.start(RunRequest(script_id="paused_event", config={}))
    assert paused.wait(timeout=1.0)
    manager.stop(run_id, timeout=0.5)

    assert manager.current_run_id() is None
    next_id = manager.start(RunRequest(script_id="fake", config={"max_battle_count": 1}))
    assert manager.wait(next_id, timeout=1.0)


def test_stop_after_pause_point_does_not_run_extra_iteration(tmp_path: Path) -> None:
    paused = threading.Event()
    before_iteration_called = threading.Event()

    class PausedLoopScript(EventBaseScript):
        def on_run(self) -> None:
            self.pause()
            paused.set()

        def before_iteration(self) -> None:
            before_iteration_called.set()

    manager = create_run_manager(tmp_path, FakeRegistry({"paused_loop": PausedLoopScript}))

    run_id = manager.start(RunRequest(script_id="paused_loop", config={}))
    assert paused.wait(timeout=1.0)
    manager.stop(run_id, timeout=0.5)

    assert not before_iteration_called.is_set()


def test_start_failure_marks_run_error_and_clears_slot(tmp_path: Path) -> None:
    class ConstructorRaisesScript:
        def __init__(self) -> None:
            raise RuntimeError("构造失败")

    manager = create_run_manager(tmp_path, FakeRegistry({"broken": ConstructorRaisesScript}))

    with pytest.raises(RuntimeError, match="构造失败"):
        manager.start(RunRequest(script_id="broken", config={}))

    with manager.storage.db.connect() as conn:
        run = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()

    assert run is not None
    assert run["status"] == RunStatus.ERROR.value
    assert "Traceback" in run["error_message"]
    assert manager.current_run_id() is None
    next_id = manager.start(RunRequest(script_id="fake", config={"max_battle_count": 1}))
    manager.wait(next_id, timeout=1.0)


def test_stop_during_startup_reports_script_not_ready_without_key_error(tmp_path: Path) -> None:
    loading_started = threading.Event()
    allow_return = threading.Event()

    class BlockingScript:
        def __init__(self) -> None:
            self.stopped = False

        def run(self) -> None:
            while not self.stopped:
                time.sleep(0.01)

        def stop(self) -> None:
            self.stopped = True

    class SlowRegistry(FakeRegistry):
        def load_class(self, script_id: str) -> type:
            loading_started.set()
            allow_return.wait(timeout=1.0)
            return BlockingScript

    manager = create_run_manager(tmp_path, SlowRegistry())
    started_run_ids: list[int] = []
    start_errors: list[BaseException] = []

    def start_script() -> None:
        try:
            started_run_ids.append(manager.start(RunRequest(script_id="slow", config={})))
        except BaseException as exc:
            start_errors.append(exc)

    start_thread = threading.Thread(target=start_script, daemon=True)
    start_thread.start()
    assert loading_started.wait(timeout=1.0)

    try:
        with pytest.raises(RuntimeError, match="脚本尚未准备就绪"):
            manager.stop(1, timeout=0.01)
        with pytest.raises(RuntimeError, match="已有脚本正在运行"):
            manager.start(RunRequest(script_id="fake", config={"max_battle_count": 1}))
    finally:
        allow_return.set()
        start_thread.join(timeout=1.0)
        if started_run_ids:
            manager.stop(started_run_ids[0], timeout=1.0)

    assert start_errors == []


def test_stop_status_is_not_overwritten_by_late_success(
    run_manager: RunManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_get = run_manager.storage.runs.get
    race_triggered = False

    def get_with_stop_race(run_id: int) -> dict[str, Any] | None:
        nonlocal race_triggered
        run = original_get(run_id)
        if not race_triggered and run is not None and run["status"] == RunStatus.RUNNING.value:
            race_triggered = True
            run_manager.storage.runs.update_status(run_id, RunStatus.STOPPED)
        return run

    monkeypatch.setattr(run_manager.storage.runs, "get", get_with_stop_race)

    run_id = run_manager.start(RunRequest(script_id="fake", config={"max_battle_count": 1}))
    run_manager.wait(run_id, timeout=1.0)

    run = original_get(run_id)

    assert run is not None
    assert race_triggered
    assert run["status"] == RunStatus.STOPPED.value
