from __future__ import annotations

from pathlib import Path

from ui_backend.models import RunSourceType, RunStatus
from ui_backend.storage.database import Database
from ui_backend.storage.repositories import Storage


def test_storage_creates_workflow_run_log_and_snapshot(tmp_path: Path) -> None:
    db = Database(tmp_path / "ui.db")
    db.initialize()
    storage = Storage(db)

    workflow_id = storage.workflows.create(
        name="日常",
        group_name="默认",
        enabled=True,
        trigger_type="manual",
        trigger_config={},
        failure_policy="stop_workflow",
    )
    step_id = storage.workflow_steps.create(
        workflow_id=workflow_id,
        sort_order=1,
        step_type="run_script",
        script_id="soul_raid",
        config={"max_battle_count": 103},
        condition={},
        retry_count=0,
    )
    run_id = storage.runs.create(
        script_id="soul_raid",
        source_type=RunSourceType.WORKFLOW,
        config={"max_battle_count": 103},
        workflow_id=workflow_id,
        workflow_step_id=step_id,
    )

    storage.runs.update_status(run_id, RunStatus.RUNNING)
    storage.logs.append(run_id, "INFO", "开始运行")
    storage.snapshots.append(run_id, "soul_raid", {"battle_count": 1})

    run = storage.runs.get(run_id)
    assert run is not None
    assert run["status"] == "running"
    assert run["workflow_id"] == workflow_id
    assert storage.logs.list_by_run(run_id)[0]["message"] == "开始运行"
    assert storage.snapshots.latest_by_run(run_id)["state"]["battle_count"] == 1


def test_snapshot_latest_returns_none_when_run_has_no_snapshot(tmp_path: Path) -> None:
    db = Database(tmp_path / "ui.db")
    db.initialize()
    storage = Storage(db)

    run_id = storage.runs.create(
        script_id="soul_raid",
        source_type=RunSourceType.MANUAL,
        config={"max_battle_count": 103},
    )

    assert storage.snapshots.latest_by_run(run_id) is None


def test_run_status_timestamps_are_not_overwritten(tmp_path: Path) -> None:
    db = Database(tmp_path / "ui.db")
    db.initialize()
    storage = Storage(db)
    started_at = "2026-05-31 01:02:03"
    ended_at = "2026-05-31 04:05:06"

    run_id = storage.runs.create(
        script_id="soul_raid",
        source_type=RunSourceType.MANUAL,
        config={"max_battle_count": 103},
    )

    storage.runs.update_status(run_id, RunStatus.RUNNING)
    with db.connect() as conn:
        conn.execute("UPDATE runs SET started_at = ? WHERE id = ?", (started_at, run_id))

    storage.runs.update_status(run_id, RunStatus.RUNNING)

    run = storage.runs.get(run_id)
    assert run is not None
    assert run["started_at"] == started_at

    storage.runs.update_status(run_id, RunStatus.SUCCESS)
    with db.connect() as conn:
        conn.execute("UPDATE runs SET ended_at = ? WHERE id = ?", (ended_at, run_id))

    storage.runs.update_status(run_id, RunStatus.ERROR, error_message="失败")

    run = storage.runs.get(run_id)
    assert run is not None
    assert run["ended_at"] == ended_at


def test_run_repository_marks_unfinished_runs_as_error(tmp_path: Path) -> None:
    db = Database(tmp_path / "ui.db")
    db.initialize()
    storage = Storage(db)
    message = "后端重启，未完成运行已终止"

    running_id = storage.runs.create(
        script_id="soul_raid",
        source_type=RunSourceType.MANUAL,
        config={},
    )
    paused_id = storage.runs.create(
        script_id="realm_raid",
        source_type=RunSourceType.MANUAL,
        config={},
    )
    success_id = storage.runs.create(
        script_id="douji",
        source_type=RunSourceType.MANUAL,
        config={},
    )
    storage.runs.update_status(running_id, RunStatus.RUNNING)
    storage.runs.update_status(paused_id, RunStatus.PAUSED)
    storage.runs.update_status(success_id, RunStatus.SUCCESS)

    changed_count = storage.runs.mark_unfinished_as_error(message)

    assert changed_count == 2
    assert storage.runs.current() is None
    running = storage.runs.get(running_id)
    paused = storage.runs.get(paused_id)
    success = storage.runs.get(success_id)
    assert running is not None
    assert paused is not None
    assert success is not None
    assert running["status"] == RunStatus.ERROR.value
    assert paused["status"] == RunStatus.ERROR.value
    assert running["error_message"] == message
    assert paused["error_message"] == message
    assert success["status"] == RunStatus.SUCCESS.value
