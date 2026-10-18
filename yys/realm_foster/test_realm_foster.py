"""寄养产品契约及真实画面识别回归，不向游戏发送输入。"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import Mock

import cv2
import numpy as np
import pytest
from PIL import Image

from win_util.environment.guarded import GuardedEnvironment, RunGuard
from win_util.image import ImageFinder
from win_util.ocr import CommonOcr
from yys.realm_foster.realm_foster_script import FosterCandidate, RealmFosterScript, _Stopped


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/realm_foster"


def script() -> RealmFosterScript:
    """只构造本模块匹配器，不查找或激活真实窗口。"""
    result = RealmFosterScript.__new__(RealmFosterScript)
    result._images = ROOT / "yys/realm_foster/images"
    result.image_finder = ImageFinder.__new__(ImageFinder)
    result._stars = [cv2.imread(str(result._images / f"{name}_star.png"))
                     for name in ("active", "inactive")]
    result._live_stars = [cv2.imread(str(result._images / f"{name}_star_live.png"))
                          for name in ("active", "inactive")]
    result._stop_threading_event = threading.Event()
    result._run_guard = None
    result.ocr = CommonOcr()
    result.pause_point = Mock()
    result._size = result.SIZE
    return result


@pytest.mark.parametrize("scene,marker", [
    ("home", "home"), ("guild", "guild"), ("realm", "growth_entry"),
    ("growth", "growth"), ("taiko", "friends"), ("confirm", "confirm"),
    ("guild_live", "guild"),
    ("growth_live", "return"),
    ("realm_live", "growth_entry"),
    ("friend_realm_live", "growth_entry"),
])
def test_real_page_markers_reject_unrelated_page(scene: str, marker: str) -> None:
    # 产品契约来源：子任务 AC 真实模板与未知页面不输入。
    runner = script()
    assert runner._match(cv2.imread(str(FIXTURES / f"{scene}.png")), marker) is not None
    other = "taiko" if scene == "home" else "home"
    assert runner._match(cv2.imread(str(FIXTURES / f"{other}.png")), marker) is None


def test_current_sakura_home_requires_both_lantern_and_scene_marker() -> None:
    # 产品契约来源：2026-10-18 实机当前庭院低于旧 home 模板阈值。
    runner = script()
    home = cv2.imread(str(ROOT / "tests/fixtures/realm_foster/home_sakura_current.png"))
    realm = cv2.imread(str(FIXTURES / "realm.png"))
    assert runner._match(home, "home") is not None
    assert runner._match(realm, "home") is None


def test_actual_taiko_has_four_active_stars_and_two_inactive_slots() -> None:
    # 产品契约来源：用户要求按星级从高到低；录制为四亮两灰。
    runner = script()
    image = cv2.imread(str(FIXTURES / "taiko.png"))
    assert runner._star_count(image) == 4
    for stars in range(1, 7):
        changed = image.copy()
        for index in range(6):
            x = 749 + index * 13
            changed[289:304, x:x + 13] = runner._stars[index >= stars]
        assert runner._star_count(changed) == stars
    image[289:304, 775:788] = 0
    with pytest.raises(RuntimeError, match="FOSTER_STARS"):
        runner._star_count(image)


def test_global_priority_includes_cross_region_and_preserves_equal_star_order() -> None:
    # 产品契约来源：用户“好友有两个列表，还有一个跨区；太鼓星级从高到底”。
    candidates = [FosterCandidate("好友", "甲", 4), FosterCandidate("跨区", "乙", 6),
                  FosterCandidate("跨区", "丙", 6)]
    assert RealmFosterScript.choose(candidates) == candidates[1]
    with pytest.raises(RuntimeError, match="FOSTER_NO_TAIKO"):
        RealmFosterScript.choose([])


def test_live_three_star_taiko_is_not_six_stars() -> None:
    # 产品契约来源：2026-10-18 实机三亮三灰；新变体不放宽原有阈值。
    runner = script()
    assert runner._star_count(cv2.imread(str(FIXTURES / "taiko_live_three.png"))) == 3


def test_dark_modal_does_not_enable_entering_friend_realm() -> None:
    # 产品契约来源：未确认可进入按钮，不得输入。
    runner = script()
    frame = cv2.imread(str(FIXTURES / "taiko.png"))
    assert runner._match(frame, "enter") is not None
    assert runner._match((frame.astype(float) * 0.45).astype(np.uint8), "enter") is None


def test_stop_and_observe_never_send_real_input() -> None:
    # 产品契约来源：所有操作经观察模式及停止检查。
    runner = script()
    delegate = Mock()
    runner._env = GuardedEnvironment(delegate, RunGuard(), observe_only=True)
    with pytest.raises(_Stopped):
        runner._click((100, 200))
    delegate.left_click.assert_not_called()
    assert len(runner._env.action_records) == 1
    runner._stop_threading_event.set()
    with pytest.raises(_Stopped):
        runner._click((200, 200))
    assert len(runner._env.action_records) == 1


def test_foster_success_requires_own_slot_countdown_not_friend_countdown() -> None:
    # 产品契约来源：确认点击不算完成，必须看到自己的寄养倒计时。
    runner = script()
    runner.ocr = CommonOcr()
    assert not runner._fostering(cv2.imread(str(FIXTURES / "friend_realm.png")))
    assert runner._fostering(cv2.imread(str(FIXTURES / "success.png")))


def test_capture_error_does_not_return_stale_cached_frame() -> None:
    # 产品契约来源：截图失败必须停止，不能使用 ImageFinder 的旧缓存。
    runner = script()
    runner._env = Mock()
    runner._env.capture_screen.side_effect = RuntimeError("capture failed")
    with pytest.raises(RuntimeError, match="capture failed"):
        runner._read()
    runner._env.capture_screen.side_effect = None
    runner._env.capture_screen.return_value = Image.new("RGB", (500, 500))
    with pytest.raises(RuntimeError, match="FOSTER_CAPTURE"):
        runner._read()


def test_scanner_visits_both_lists_and_keeps_higher_star_on_later_page() -> None:
    # 产品契约来源：用户要求两个好友列表均检查，不能见到首张太鼓就寄养。
    runner = script()
    pages = {
        "好友": [[(320, 220, "甲")], [(320, 220, "乙")]],
        "跨区": [[(320, 220, "丙")]],
    }
    current = ["好友", 0]
    switched: list[str] = []

    def switch(tab: str) -> None:
        switched.append(tab)
        current[:] = [tab, 0]

    def wheel(_delta: int) -> None:
        current[1] = min(int(current[1]) + 1, len(pages[str(current[0])]) - 1)

    frame = cv2.imread(str(FIXTURES / "taiko.png"))
    runner._switch_tab = switch
    runner._top = Mock()
    runner._read = Mock(return_value=frame)
    runner._rows = lambda _: pages[str(current[0])][int(current[1])]
    runner._wheel = wheel
    runner._inspect = lambda name: (frame, {"甲": 3, "乙": 5, "丙": 6}[name])
    candidates = runner._scan("好友") + runner._scan("跨区")
    assert switched == ["好友", "跨区"]
    assert [(item.tab, item.stars) for item in candidates] == [("好友", 3), ("好友", 5), ("跨区", 6)]
    assert runner.choose(candidates).name == "丙"


def test_best_candidate_is_rechecked_before_entering() -> None:
    # 产品契约来源：名单或结界状态变化时不能误进其他好友或低星卡。
    runner = script()
    runner._switch_tab = Mock()
    runner._top = Mock()
    runner._read = Mock(return_value=np.zeros((641, 1138, 3), dtype=np.uint8))
    runner._rows = Mock(return_value=[(320, 220, "甲")])
    runner._inspect = Mock(return_value=(np.zeros((641, 1138, 3), dtype=np.uint8), 3))
    with pytest.raises(RuntimeError, match="FOSTER_CHANGED"):
        runner._revisit(FosterCandidate("好友", "甲", 6))


def test_guild_tree_notice_closes_once_then_requires_unobscured_guild() -> None:
    # 产品契约来源：2026-10-18 实机树木升级通知只能关闭已识别的按钮。
    runner = script()
    notice = cv2.imread(str(FIXTURES / "guild_tree_notice.png"))
    guild = cv2.imread(str(FIXTURES / "guild.png"))
    assert runner._match(notice, "guild_tree_notice") is not None
    assert runner._match(notice, "guild_tree_close") is not None
    assert runner._match(guild, "guild_tree_notice") is None
    runner._read = Mock(side_effect=[notice, guild])
    runner._click = Mock()
    assert runner._wait_guild() is guild
    runner._click.assert_called_once_with(runner._required(notice, "guild_tree_close"))


def test_guild_return_clicks_recognized_arrow_then_confirms_home() -> None:
    # 产品契约来源：2026-10-18 实机阴阳寮 ESC 不返回，须用已识别箭头。
    runner = script()
    guild = cv2.imread(str(FIXTURES / "guild_live.png"))
    home = cv2.imread(str(FIXTURES / "home.png"))
    runner._read = Mock(side_effect=[guild, home, home])
    runner._click = Mock()
    runner._env = Mock()
    runner._return_home()
    runner._click.assert_called_once_with(runner._match(guild, "to_home")
                                         or runner._required(guild, "return"))
    runner._env.key_press.assert_not_called()
