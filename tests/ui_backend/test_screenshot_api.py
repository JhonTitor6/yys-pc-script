from __future__ import annotations

import json
import logging
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import ui_backend.runs.manager as manager_module
from ui_backend.app import create_app
from ui_backend.models import RunSourceType, RunStatus, available_actions_for_run
from ui_backend.screenshots import ScreenshotError, ScreenshotService


def _frame(width: int = 24, height: int = 16) -> np.ndarray:
    x = np.arange(width, dtype=np.uint8)
    y = np.arange(height, dtype=np.uint8)[:, None]
    return np.dstack(((x + y) % 255, np.broadcast_to(x, (height, width)), np.broadcast_to(y, (height, width))))


def _png(width: int, height: int) -> bytes:
    output = BytesIO()
    Image.fromarray(_frame(width, height)[:, :, ::-1], "RGB").save(output, format="PNG")
    return output.getvalue()


def _client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            db_path=tmp_path / "ui.db",
            user_data_dir=tmp_path / "user-data",
        )
    )


def test_library_crop_delete_and_restart_contract(tmp_path: Path) -> None:
    """产品契约：PNG/JSON 永久保存，裁剪独立，删除不级联运行证据。"""
    client = _client(tmp_path)
    service = client.app.state.screenshots
    run_id = client.app.state.storage.runs.create(
        script_id="demo",
        source_type=RunSourceType.MANUAL,
        config={},
    )
    full = service.save_full(
        _frame(),
        trigger="manual",
        run_id=run_id,
        script_id="demo",
        stage="script_running",
    )
    client.app.state.run_manager.record_saved_screenshot(full, "测试运行截图")

    listing = client.get("/api/screenshots")
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == full["id"]
    assert listing.json()[0]["available"] is True
    assert client.get(f"/api/screenshots/{full['id']}/content").content.startswith(b"\x89PNG")

    crop = client.post(
        f"/api/screenshots/{full['id']}/crops",
        content=_png(7, 5),
        headers={"Content-Type": "image/png"},
    )
    assert crop.status_code == 200
    assert crop.json()["kind"] == "crop"
    assert crop.json()["source_id"] == full["id"]
    assert (crop.json()["width"], crop.json()["height"]) == (7, 5)

    restarted = ScreenshotService(tmp_path / "user-data")
    assert {item["id"] for item in restarted.list()} == {full["id"], crop.json()["id"]}

    evidence_before = client.app.state.storage.evidence.list_by_run(run_id)
    deleted = client.delete(f"/api/screenshots/{full['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/api/screenshots/{full['id']}/content").status_code == 404
    evidence_after = client.app.state.storage.evidence.list_by_run(run_id)
    assert evidence_after[0]["id"] == evidence_before[0]["id"]
    assert evidence_after[0]["path"] == evidence_before[0]["path"]
    assert evidence_after[0]["available"] is False
    assert client.get(f"/api/screenshots/{crop.json()['id']}/content").status_code == 200


def test_invalid_full_frames_and_crops_create_no_records(tmp_path: Path) -> None:
    service = ScreenshotService(tmp_path / "user-data")
    with pytest.raises(ScreenshotError, match="近似纯色"):
        service.save_full(np.zeros((10, 10, 3), dtype=np.uint8), trigger="manual")
    assert service.list() == []

    full = service.save_full(_frame(), trigger="manual")
    client = _client(tmp_path)
    client.app.state.screenshots = service
    assert client.post(f"/api/screenshots/{full['id']}/crops", content=b"").status_code == 400
    assert client.post(f"/api/screenshots/{full['id']}/crops", content=b"bad").status_code == 400
    assert client.post(
        f"/api/screenshots/{full['id']}/crops",
        content=_png(full["width"] + 1, 2),
    ).status_code == 400
    assert [item["kind"] for item in service.list()] == ["full"]


def test_library_rejects_tampered_metadata_content_and_id(tmp_path: Path) -> None:
    """产品契约：列表和读取都不接受伪路径、篡改尺寸或损坏 PNG。"""
    service = ScreenshotService(tmp_path / "user-data")
    saved = service.save_full(_frame(), trigger="manual")
    metadata_path = next((tmp_path / "user-data" / "screenshots").glob("*/*.json"))
    image_path = metadata_path.with_suffix(".png")

    image_path.write_bytes(b"not-a-png")
    assert service.get(saved["id"])["available"] is False
    with pytest.raises(ScreenshotError, match="已删除或不可用"):
        service.content_path(saved["id"])

    image_path.write_bytes(_png(saved["width"], saved["height"]))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["width"] += 1
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    assert service.get(saved["id"])["available"] is False
    with pytest.raises(ScreenshotError, match="截图 ID 无效"):
        service.get("../outside")


def test_idle_manual_capture_uses_background_window_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FakeWindowsEnvironment:
        def __init__(self, *, hwnd: int | None, window_title: str, capture_mode: str) -> None:
            assert hwnd is None
            assert window_title == "阴阳师"
            assert capture_mode == "print_window"
            calls.append("construct")

        def capture_screen(self) -> Image.Image:
            calls.append("capture")
            return Image.fromarray(_frame()[:, :, ::-1], "RGB")

    monkeypatch.setattr(manager_module, "WindowsEnvironment", FakeWindowsEnvironment)
    response = _client(tmp_path).post("/api/screenshots/capture")
    assert response.status_code == 200
    assert calls == ["construct", "capture"]
    assert response.json()["restore_required"] is False


def test_idle_manual_capture_failure_does_not_require_gui_restore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """产品契约：空闲后台捕获失败不得要求 GUI 回焦。"""

    class FailingWindowsEnvironment:
        def __init__(self, *, hwnd: int | None, window_title: str, capture_mode: str) -> None:
            assert hwnd is None
            assert window_title == "阴阳师"
            assert capture_mode == "print_window"

        def capture_screen(self) -> Image.Image:
            raise RuntimeError("后台截图失败")

    monkeypatch.setattr(manager_module, "WindowsEnvironment", FailingWindowsEnvironment)
    response = _client(tmp_path).post("/api/screenshots/capture")
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "message": "后台截图失败",
        "restore_required": False,
    }


def test_idle_manual_capture_logs_unexpected_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """手动截图异常必须保留后端日志和完整 traceback。"""

    class FailingWindowsEnvironment:
        def __init__(self, *, hwnd: int | None, window_title: str, capture_mode: str) -> None:
            assert hwnd is None
            assert window_title == "阴阳师"
            assert capture_mode == "print_window"

        def capture_screen(self) -> Image.Image:
            raise RuntimeError("后台截图失败")

    monkeypatch.setattr(manager_module, "WindowsEnvironment", FailingWindowsEnvironment)
    with caplog.at_level(logging.ERROR, logger="ui_backend.runs.manager"):
        response = _client(tmp_path).post("/api/screenshots/capture")

    assert response.status_code == 409
    assert "手动截图发生未处理异常" in caplog.text
    assert "Traceback (most recent call last)" in caplog.text
    assert "后台截图失败" in caplog.text


def test_idle_manual_capture_fails_when_game_window_handle_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """产品契约：点击截图时找不到阴阳师句柄不得捕获其他桌面内容。"""

    class MissingWindowsEnvironment:
        def __init__(self, *, hwnd: int | None, window_title: str, capture_mode: str) -> None:
            assert hwnd is None
            assert window_title == "阴阳师"
            assert capture_mode == "print_window"
            raise RuntimeError("未找到标题包含 '阴阳师' 的游戏窗口")

    monkeypatch.setattr(manager_module, "WindowsEnvironment", MissingWindowsEnvironment)
    response = _client(tmp_path).post("/api/screenshots/capture")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "message": "未找到标题包含 '阴阳师' 的游戏窗口",
        "restore_required": False,
    }


def test_running_manual_capture_only_copies_cache_and_preserves_run_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path)
    manager = client.app.state.run_manager
    storage = client.app.state.storage
    run_id = storage.runs.create(
        script_id="demo",
        source_type=RunSourceType.MANUAL,
        config={},
    )
    actions = available_actions_for_run(RunStatus.RUNNING, "script_running")
    storage.runs.update_status(
        run_id,
        RunStatus.RUNNING,
        stage="script_running",
        available_actions=actions,
    )

    class HandleProbeEnvironment:
        def __init__(self, *, hwnd: int | None, window_title: str) -> None:
            assert hwnd is None
            assert window_title == "阴阳师"

        def activate_window(self) -> None:
            raise AssertionError("运行中禁止激活游戏窗口")

        def capture_screen(self) -> Image.Image:
            raise AssertionError("运行中禁止前台捕获")

    monkeypatch.setattr(manager_module, "WindowsEnvironment", HandleProbeEnvironment)

    class RunningScript:
        def __init__(self) -> None:
            self.image_finder = SimpleNamespace(screenshot_cache=_frame())

        def capture_screenshot(self) -> None:
            raise AssertionError("运行中禁止主动捕获")

    script = RunningScript()
    with manager._lock:
        manager._active_run_id = run_id
        manager._scripts[run_id] = script
    before = storage.runs.get(run_id)
    response = client.post("/api/screenshots/capture")
    after = storage.runs.get(run_id)

    assert response.status_code == 200
    assert response.json()["run_id"] == run_id
    assert response.json()["restore_required"] is False
    assert script.image_finder.screenshot_cache is not None
    assert after["status"] == before["status"]
    assert after["stage"] == before["stage"]
    assert after["available_actions"] == before["available_actions"]
    assert storage.evidence.list_by_run(run_id)[0]["capture_error"] is None
