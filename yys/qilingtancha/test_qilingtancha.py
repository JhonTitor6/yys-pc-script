from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from ui_backend.app import create_app
from win_util.image import ImageFinder, ScreenCapture
from win_util.mouse import MouseController
from yys.qilingtancha import qilingtancha_script as script


def test_tancha_captures_and_matches_using_hwnd(monkeypatch: MonkeyPatch) -> None:
    template = cv2.imread(str(Path(__file__).parent / "images" / "qiling_tancha.bmp"))
    assert template is not None
    height, width = template.shape[:2]
    frame = np.zeros((641, 1138, 3), dtype=np.uint8)
    frame[200:200 + height, 300:300 + width] = template

    def capture(capture_target: ScreenCapture) -> np.ndarray:
        assert capture_target.hwnd == 123
        return frame

    click = Mock(return_value=True)
    monkeypatch.setattr(script, "find_window", lambda: 123)
    monkeypatch.setattr(ScreenCapture, "capture_window_region", capture)
    monkeypatch.setattr(MouseController, "bg_left_click_with_range", click)

    instance = script.QilingTanchaScript()
    assert instance.get_state_snapshot()["max_battle_count"] == 100
    instance._trigger_event_from_screenshot_cache()

    click.assert_called_once_with((300 + width // 2, 200 + height // 2), x_range=20, y_range=20)


@pytest.mark.parametrize("target", [0, 1000, 1.5, True, "3", None])
def test_invalid_win_target_is_rejected_before_window_access(target: object, monkeypatch: MonkeyPatch) -> None:
    """产品契约：目标胜场必须是有效整数，错误配置不能启动游戏操作。"""
    find_window = Mock()
    monkeypatch.setattr(script, "find_window", find_window)

    with pytest.raises(ValueError, match="目标胜场必须是 1 到 999 的整数"):
        script.QilingTanchaScript(config={"max_battle_count": target})

    find_window.assert_not_called()


def test_workbench_runs_and_stops_tancha(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """产品契约：保存或启动时可指定目标胜场，末场奖励清理后完成。"""
    phases = [
        "", "battling.bmp", "battle_end_loss.bmp", "battle_end_1.bmp", "qiling_tancha.bmp",
        "battle_end_success.bmp", "battle_end_success.bmp", "battle_end_2.bmp", "qiling_tancha.bmp",
        "battle_end.bmp", "suipian.png", "battle_end_1.bmp", "qiling_tancha.bmp",
    ]
    frames = iter(range(len(phases)))

    def capture(_capture_target: ScreenCapture) -> np.ndarray:
        return np.full((1, 1, 3), next(frames, 0), dtype=np.uint8)

    def match(finder: ImageFinder, path: str, *_args: object) -> tuple[int, int]:
        frame = finder.screenshot_cache
        assert frame is not None
        index = int(frame[0, 0, 0])
        return (index, 100) if Path(path).name == phases[index] else (-1, -1)

    click = Mock(return_value=True)
    monkeypatch.setattr(script, "find_window", lambda: 123)
    monkeypatch.setattr(ScreenCapture, "capture_window_region", capture)
    monkeypatch.setattr(ImageFinder, "bg_find_pic_by_cache", match)
    monkeypatch.setattr(MouseController, "bg_left_click_with_range", click)
    monkeypatch.setattr(script.QilingTanchaScript, "after_iteration", lambda self: None)
    monkeypatch.setattr(script, "BATTLE_VICTORY_SLEEP", 0)
    monkeypatch.setattr(script, "BATTLE_END_SLEEP", 0)
    app = create_app(db_path=tmp_path / "workbench.db")

    with TestClient(app) as client:
        scripts = client.get("/api/scripts").json()
        definition = next(item for item in scripts if item["script_id"] == "qilingtancha")
        assert definition["display_name"] == "契灵探查"
        assert definition["default_config"] == {"max_battle_count": 100}
        field, = definition["config_schema"]
        assert field["key"] == "max_battle_count"
        assert field["label"] == "目标胜场"
        assert field["field_type"] == "number"
        assert (field["min_value"], field["max_value"], field["hot_reloadable"]) == (1, 999, False)
        saved = client.patch("/api/scripts/qilingtancha/config", json={"max_battle_count": 3})
        assert saved.json()["saved"] is True

        started = client.post("/api/runs/start", json={"script_id": "qilingtancha", "config": {"max_battle_count": 2}})
        run_id = started.json()["id"]
        assert app.state.run_manager.wait(run_id, timeout=6.0)
        finished = client.get(f"/api/runs/{run_id}").json()
        assert finished["status"] == "success"
        assert finished["progress"] == {"current": 2, "total": 2, "percent": 100.0}
        assert [call.args[0][0] for call in click.call_args_list] == list(range(2, 12))

        run_id = client.post("/api/runs/start", json={"script_id": "qilingtancha"}).json()["id"]
        running = client.get(f"/api/runs/{run_id}").json()
        assert running["progress"] == {"current": 0, "total": 3, "percent": 0.0}
        assert client.post(f"/api/runs/{run_id}/pause").is_success
        assert client.post(f"/api/runs/{run_id}/resume").is_success
        assert client.post(f"/api/runs/{run_id}/stop").is_success
        assert client.get(f"/api/runs/{run_id}").json()["status"] == "stopped"
        assert click.call_count == 10
