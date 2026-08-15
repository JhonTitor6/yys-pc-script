from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from ui_backend.events.hub import EventHub
from ui_backend.runs.manager import RunManager
from ui_backend.screenshots import ScreenshotService
from ui_backend.storage.database import Database
from ui_backend.storage.repositories import Storage
from win_util.event import EventBaseScript


def _frame(seed: int) -> np.ndarray:
    values = np.arange(16 * 24 * 3, dtype=np.uint16).reshape(16, 24, 3)
    return ((values + seed) % 255).astype(np.uint8)


def test_three_unknown_frames_capture_once_and_known_frame_rearms(tmp_path: Path) -> None:
    """产品契约：未知/未知/未知/未知/已知/未知/未知/未知只保存两张且不中止脚本。"""
    database = Database(tmp_path / "ui.db")
    database.initialize()
    storage = Storage(database)
    manager = RunManager(
        storage,
        SimpleNamespace(),
        EventHub(),
        ScreenshotService(tmp_path / "user-data"),
    )
    run_id = storage.runs.create(
        script_id="demo",
        source_type=SimpleNamespace(value="manual"),
        config={},
    )
    script = EventBaseScript()
    script.image_finder = SimpleNamespace(screenshot_cache=_frame(1))
    manager._install_unknown_scene_observer(run_id, "demo", script)
    observer = script._recognition_observer
    assert observer is not None

    observer(False)
    observer(False)
    assert manager.screenshot_service.list() == []
    observer(False)
    script.image_finder.screenshot_cache[:] = 0
    observer(False)
    _wait_for_screenshots(manager.screenshot_service, 1)
    assert len(manager.screenshot_service.list()) == 1

    observer(True)
    script.image_finder.screenshot_cache = _frame(2)
    observer(False)
    observer(False)
    observer(False)
    _wait_for_screenshots(manager.screenshot_service, 2)
    assert len(manager.screenshot_service.list()) == 2
    assert script._stop_threading_event.is_set() is False


def _wait_for_screenshots(service: ScreenshotService, count: int) -> None:
    deadline = time.time() + 2
    while time.time() < deadline:
        if len(service.list()) >= count:
            return
        time.sleep(0.01)
    raise AssertionError(f"等待 {count} 张截图超时")
