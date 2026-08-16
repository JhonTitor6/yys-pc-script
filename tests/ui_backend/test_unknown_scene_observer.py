from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pytest
from PIL import Image

from ui_backend.events.hub import EventHub
from ui_backend.models import RunSourceType
from ui_backend.runs.manager import (
    UNKNOWN_SCENE_SCREENSHOT_GRACE_SECONDS,
    RunManager,
)
from ui_backend.screenshots import ScreenshotService
from ui_backend.storage.database import Database
from ui_backend.storage.repositories import Storage


class FakeClock:
    """可手动推进的单调时钟，用于按时间触发观察器。"""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class FakeImageFinder:
    def __init__(self) -> None:
        self.screenshot_cache = FakeCache()


class FakeCache:
    def copy(self) -> Image.Image:
        # 噪声图，满足 validate_capture_frame 的非空、非纯色要求。
        return Image.fromarray(
            np.random.randint(0, 256, (120, 160, 3), dtype=np.uint8)
        )


class FakeScript:
    def __init__(self) -> None:
        self.image_finder = FakeImageFinder()
        self.observer: Callable[[bool], None] | None = None

    def set_recognition_observer(
        self, observer: Callable[[bool], None] | None
    ) -> None:
        self.observer = observer


def create_manager(tmp_path: Path) -> RunManager:
    db = Database(tmp_path / "ui.db")
    db.initialize()
    return RunManager(
        storage=Storage(db),
        registry=object(),
        event_hub=EventHub(),
        screenshot_service=ScreenshotService(tmp_path / "userdata"),
    )


def install_observer(
    manager: RunManager,
    clock: FakeClock,
    script: FakeScript | None = None,
) -> tuple[int, Callable[[bool], None]]:
    """创建真实 run 记录并安装观察器，返回 (run_id, observe)。"""
    run_id = manager.storage.runs.create(
        "fake", RunSourceType.MANUAL, {"max_battle_count": 1}
    )
    script = script or FakeScript()
    manager._install_unknown_scene_observer(
        run_id=run_id, script_id="fake", script=script, monotonic=clock
    )
    assert script.observer is not None
    return run_id, script.observer


def wait_for_unknown_scene_events(manager: RunManager, count: int) -> list[dict[str, Any]]:
    """等待后台保存线程产生指定数量的 unknown_scene 截图事件。"""
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        events = [
            event
            for event in manager.event_hub.recent_events()
            if event.get("type") == "screenshot_saved"
            and event.get("screenshot", {}).get("trigger") == "unknown_scene"
        ]
        if len(events) >= count:
            return events
        time.sleep(0.01)
    raise AssertionError(f"等待 {count} 张未知场景截图事件超时")


def test_unknown_scene_under_grace_seconds_does_not_screenshot(tmp_path: Path) -> None:
    manager = create_manager(tmp_path)
    clock = FakeClock()
    run_id, observe = install_observer(manager, clock)

    observe(False)  # t=0
    clock.advance(UNKNOWN_SCENE_SCREENSHOT_GRACE_SECONDS - 0.1)
    observe(False)

    time.sleep(0.1)
    assert not [
        event
        for event in manager.event_hub.recent_events()
        if event.get("type") == "screenshot_saved"
    ]
    assert manager.storage.evidence.list_by_run(run_id) == []


def test_unknown_scene_reaching_grace_seconds_screenshots_once(tmp_path: Path) -> None:
    manager = create_manager(tmp_path)
    clock = FakeClock()
    run_id, observe = install_observer(manager, clock)

    observe(False)  # t=0
    clock.advance(UNKNOWN_SCENE_SCREENSHOT_GRACE_SECONDS)
    observe(False)  # t=10 首次达到阈值 → 触发一次
    clock.advance(UNKNOWN_SCENE_SCREENSHOT_GRACE_SECONDS * 2)
    observe(False)  # 同一段内继续未知 → 不再截

    events = wait_for_unknown_scene_events(manager, 1)
    evidence = manager.storage.evidence.list_by_run(run_id)
    assert len(evidence) == 1
    assert evidence[0]["description"] == "持续未识别到注册事件"
    assert evidence[0]["capture_error"] is None
    assert events[0]["screenshot"]["trigger"] == "unknown_scene"


def test_unknown_scene_observer_resets_after_recognized(tmp_path: Path) -> None:
    """识别成功后重置：下一段未知满阈值可再次截图。"""
    manager = create_manager(tmp_path)
    clock = FakeClock()
    run_id, observe = install_observer(manager, clock)

    observe(False)
    clock.advance(UNKNOWN_SCENE_SCREENSHOT_GRACE_SECONDS)
    observe(False)  # 第一段 → 截图 1
    observe(True)  # 识别恢复，重置
    clock.advance(UNKNOWN_SCENE_SCREENSHOT_GRACE_SECONDS)
    observe(False)  # 第二段开始计时
    clock.advance(UNKNOWN_SCENE_SCREENSHOT_GRACE_SECONDS)
    observe(False)  # 第二段满阈值 → 截图 2

    wait_for_unknown_scene_events(manager, 2)
    assert len(manager.storage.evidence.list_by_run(run_id)) == 2
