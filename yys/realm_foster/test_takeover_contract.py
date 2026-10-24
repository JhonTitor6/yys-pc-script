"""寄养接管场景矩阵与 D1 安全恢复的产品契约。

真实帧用例只在本地存在录制关键帧时运行（`recordings/` 被 Git 忽略），
其余用例使用现有脱敏夹具或控制流 Mock。
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

from yys.realm_foster.test_realm_foster import FIXTURES, script

ROOT = Path(__file__).resolve().parents[2]
KEYFRAMES = ROOT / "recordings/realm_foster_takeover/keyframes"
LOCAL_ONLY = pytest.mark.skipif(
    not KEYFRAMES.is_dir(), reason="需要本地录制关键帧（不入 Git）",
)


def test_own_growth_page_owns_foster_open_marker() -> None:
    # 产品契约来源：子任务 FA2 交叉负样本——只有本人结界育成页才有
    # 「可寄养式神 +」；好友育成页即使命中 growth 标题也不得当作本人页继续。
    runner = script()
    for name in ("growth.png", "growth_live.png"):
        frame = cv2.imread(str(FIXTURES / name))
        assert frame is not None, name
        assert runner._match(frame, "foster_open") is not None, name
    for name in ("friend_realm.png", "friend_realm_live.png", "success.png"):
        frame = cv2.imread(str(FIXTURES / name))
        assert frame is not None, name
        assert runner._match(frame, "foster_open") is None, name


@pytest.mark.parametrize("scene,name", [
    ("home", "home.png"),
    ("guild", "guild.png"),
    ("realm_own", "realm.png"),
    ("growth_own", "growth.png"),
    ("panel", "taiko.png"),
    ("confirm", "confirm.png"),
    ("growth_friend", "friend_realm.png"),
    ("fostered", "success.png"),
])
def test_classifies_each_supported_start_scene(scene: str, name: str) -> None:
    # 产品契约来源：子任务 FA1——每个支持的起点都能被唯一分类，不要求先回庭院。
    runner = script()
    frame = cv2.imread(str(FIXTURES / name))
    assert frame is not None, name
    assert runner._classify(frame) == scene


def test_confirm_cancel_clicks_cancel_once_then_waits_disappear() -> None:
    # 产品契约来源：子任务 FA4 / D1——来源不明的确认框只点一次取消，
    # 点击位置来自识别结果，不用固定坐标，也不点确定。
    runner = script()
    confirm = cv2.imread(str(FIXTURES / "confirm_live.png"))
    assert runner._classify(confirm) == "confirm"
    expected = runner._match(confirm, "cancel_button")
    assert expected is not None
    runner._click = Mock()
    runner._wait = Mock(return_value=confirm)
    runner._cancel_confirm(confirm)
    runner._click.assert_called_once_with(expected)


def test_takeover_stops_without_input_on_unknown_page() -> None:
    # 产品契约来源：父任务 R5——未知页面没有可验证证据时不盲点、不连续 ESC。
    runner = script()
    frame = np.zeros((641, 1138, 3), dtype=np.uint8)
    runner._read = Mock(return_value=frame)
    runner._classify = Mock(return_value=None)
    runner._match = Mock(return_value=None)
    runner._click = Mock()
    with pytest.raises(RuntimeError, match="FOSTER_TAKEOVER"):
        runner._takeover()
    runner._click.assert_not_called()


def test_takeover_backtracks_from_friend_growth_to_own_growth() -> None:
    # 产品契约来源：子任务 FA4 / D1——从好友育成页沿已识别返回箭头逐级回退，
    # 到本人结界主页后点式神育成，每次只点击识别到的位置。
    runner = script()
    scenes = iter(["growth_friend", None, "realm_own", "growth_own"])
    frame = np.zeros((641, 1138, 3), dtype=np.uint8)
    runner._read = Mock(return_value=frame)
    runner._classify = Mock(side_effect=lambda current: next(scenes, "growth_own"))
    runner._match = Mock(return_value=(40, 40))
    runner._wait = Mock(return_value=frame)
    runner._wait_stable = Mock(return_value=frame)
    clicks: list[tuple[int, int]] = []
    runner._click = lambda point: clicks.append(point)
    assert runner._takeover() is frame
    assert clicks == [(40, 40), (40, 40), (40, 40)]


def test_takeover_returns_already_fostering_without_input() -> None:
    # 产品契约来源：子任务 FA5——已寄养只记录结果并返回，不发送任何点击。
    runner = script()
    frame = cv2.imread(str(FIXTURES / "success.png"))
    runner._read = Mock(return_value=frame)
    runner._click = Mock()
    runner._takeover()
    assert runner._outcome == "already_fostering"
    runner._click.assert_not_called()


@LOCAL_ONLY
def test_real_keyframes_classify_expected_scenes() -> None:
    # 产品契约来源：2026-10-24 三段实机录制；覆盖 FA1/FA2/FA5 的中间场景起点。
    runner = script()
    cases = {
        "success/s01-own-growth-page.png": "growth_own",
        "success/s05-friend-growth-fostered.png": "fostered",
        "cancel/c02-confirm-dialog.png": "confirm",
        "cancel/c04-after-cancel.png": "fostered",
        "cancel/c05-friend-realm-home.png": None,
        "cancel/c06-own-realm-home.png": "realm_own",
        "cross_region/x03-cross-list-selected.png": "panel",
        "cross_region/x05-cross-realm-growth.png": "growth_friend",
    }
    for relative, expected in cases.items():
        frame = cv2.imread(str(KEYFRAMES / relative))
        assert frame is not None, relative
        assert runner._classify(frame) == expected, relative


@LOCAL_ONLY
def test_real_cancel_backtrack_frames_reach_own_growth() -> None:
    # 产品契约来源：子任务 FA4——取消后逐级返回的每一级都能被识别或至少
    # 保留可点击的返回箭头，最终回到本人育成页。
    runner = script()
    sequence = [
        "cancel/c02-confirm-dialog.png",
        "cancel/c04-after-cancel.png",
        "cancel/c05-friend-realm-home.png",
        "cancel/c06-own-realm-home.png",
        "success/s01-own-growth-page.png",
    ]
    scenes: list[str | None] = []
    for relative in sequence:
        frame = cv2.imread(str(KEYFRAMES / relative))
        assert frame is not None, relative
        scenes.append(runner._classify(frame))
        if scenes[-1] is None:
            assert runner._match(frame, "return") is not None, relative
    assert scenes == ["confirm", "fostered", None, "realm_own", "growth_own"]


def test_current_guild_button_variant_is_recognized() -> None:
    # 产品契约来源：2026-10-24 实机阴阳寮 UI 更新，旧模板相似度降到 0.80/0.88；
    # 新版按钮必须被识别，不能靠降低 0.92 阈值或像素差门槛掩盖。
    runner = script()
    frame = cv2.imread(str(FIXTURES / "guild_current.png"))
    assert frame is not None
    assert runner._match(frame, "guild") is not None
