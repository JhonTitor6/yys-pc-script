"""单人魂土的截图契约、计数与安全回归。"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from tests.common.environment.mock_environment import MockEnvironment
from tests.common.providers.file_image_provider import FileImageProvider
from win_util.environment import GuardedEnvironment, RunGuard
from win_util.image import ImageFinder
from win_util.ocr import CommonOcr
from yys.soul_soil import SoulSoilScript
from yys.common.lineup import LineupSwitcher

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _ROOT / "tests" / "fixtures" / "soul_soil"
_IMAGES = Path(__file__).resolve().parent / "images"
_FINDER = object.__new__(ImageFinder)


@pytest.fixture(scope="module")
def ocr() -> CommonOcr:
    """复用项目 OCR 后端核验录制页面的真实文字位置。"""
    return CommonOcr()


def _image(name: str) -> np.ndarray:
    image = cv2.imread(str(_FIXTURES / name))
    assert image is not None
    return image


def _script(
    image_name: str = "home.jpg", *, observe_only: bool = False,
) -> tuple[SoulSoilScript, GuardedEnvironment]:
    provider = FileImageProvider()
    provider.set_current_image_from_file(str(_FIXTURES / image_name))
    delegate = MockEnvironment(image_provider=provider)
    guard = RunGuard(timeout_seconds=2400, max_actions=1000, unknown_limit=3)
    env = GuardedEnvironment(delegate, guard, observe_only=observe_only)
    script = SoulSoilScript(env=env)
    return script, env


def _score(
    template_name: str, fixture_name: str,
    region: tuple[int, int, int, int] | None = None,
) -> float:
    path = str(_IMAGES / template_name)
    args = region or (0, 0, 99999, 99999)
    return _FINDER.best_match(_image(fixture_name), path, *args).similarity


def test_metadata_exports_three_requested_defaults() -> None:
    """产品契约：注册表读取到单人魂土 ID 和三个公开配置默认值。"""
    schema = {field["key"]: field["default"] for field in SoulSoilScript.get_config_schema()}

    assert schema == {
        "max_battle_count": 10,
        "lineup_group": "御魂",
        "lineup_name": "魂土",
    }
    assert SoulSoilScript.SCRIPT_META.default_config == schema


def test_current_sakura_home_and_moved_lantern_are_recognized() -> None:
    """产品契约：庭院灯笼随镜头移动，必须全客户区定位且拒绝单人准备页。"""
    script, _ = _script()
    frame = cv2.imread(str(_ROOT / "tests/fixtures/lineup_switch/skins/home_day_current.png"))
    assert script._is_home(frame)
    lantern = cv2.imread("yys/common/images/scene/home/home_sakura_lantern.png")
    height, width = lantern.shape[:2]
    shifted = np.zeros_like(frame)
    shifted[200:200 + height, 800:800 + width] = lantern
    assert script._is_home(shifted)
    assert not script._is_home(_image("solo_lobby.jpg"))


def test_production_templates_match_only_their_recorded_pages() -> None:
    """产品契约：菜单卡、悲鸣关卡、准备页和奖励页各有独立真实帧证据。"""
    assert _score("yuhun_mode_card.png", "yuhun_modes.jpg", (0, 45, 300, 580)) >= 0.90
    assert _score("yuhun_mode_card.png", "soul_soil.jpg", (0, 45, 300, 580)) < 0.80
    assert _score("soul_stage_title.png", "soul_soil.jpg", (760, 65, 1136, 230)) >= 0.90
    assert _score("soul_stage_title.png", "floor_other.jpg", (760, 65, 1136, 230)) < 0.80
    assert _score("solo_lobby_ready.png", "solo_lobby.jpg", (900, 430, 1136, 640)) >= 0.90
    assert _score("solo_lobby_ready.png", "soul_soil.jpg", (900, 430, 1136, 640)) < 0.80
    assert _score("lobby_selected_row.png", "lobby_preset_soul_group.jpg",
                  (140, 180, 640, 350)) >= 0.90
    assert _score("lobby_selected_row.png", "solo_lobby.jpg", (140, 180, 640, 350)) < 0.80
    assert _score("treasure_title.png", "treasure.jpg", (200, 100, 900, 250)) >= 0.90
    assert _score("treasure_title.png", "settlement.jpg", (200, 100, 900, 250)) < 0.80


def test_existing_navigation_controls_match_the_recorded_screens() -> None:
    """产品契约：庭院探索、探索御魂和页面返回都点实际识别到的控件。"""
    assert _FINDER.best_match(
        _image("home.jpg"), "yys/common/images/scene/home.bmp",
    ).similarity >= 0.80
    assert _FINDER.best_match(
        _image("exploration.jpg"), "yys/common/images/scene/home.bmp",
    ).similarity < 0.80
    assert _FINDER.best_match(
        _image("home.jpg"), "yys/common/images/scene_control/home_to_exploration.bmp",
    ).similarity >= 0.80
    assert _FINDER.best_match(
        _image("exploration.jpg"), "yys/common/images/scene_control/exploration_to_soul.bmp",
    ).similarity >= 0.80
    assert _FINDER.best_match(
        _image("shikigami_presets.jpg"), "yys/common/images/scene_control/return.bmp",
    ).similarity >= 0.80
    assert _FINDER.best_match(
        _image("soul_soil.jpg"), "yys/common/images/scene_control/to_home.bmp",
    ).similarity >= 0.80
    assert _FINDER.best_match(
        _image("settlement.jpg"), "yys/images/battle_end_1.bmp",
    ).similarity >= 0.80
    assert _FINDER.best_match(
        _image("battle.jpg"), "yys/images/battle_end_1.bmp",
    ).similarity < 0.80


def test_clipped_name_is_not_a_duplicate_and_real_duplicates_are_rejected(ocr: CommonOcr) -> None:
    """产品契约：用户纠正只有首行是魂土；截断的魂王不能当同名魂土。"""
    switcher = LineupSwitcher(MockEnvironment(), ocr=ocr)
    labels = switcher._labels(_image("shikigami_presets.jpg"), "lineups")
    assert switcher._unique(labels, "魂土") == (533, 135)
    assert switcher._unique(labels, "魂王") is not None
    with pytest.raises(RuntimeError, match="同屏出现多个同名目标"):
        switcher._unique(
            [(1, 10, "魂土", 1.0), (1, 20, "魂土", 1.0)], "魂土",
        )


def test_banshee_selection_and_solo_challenge_are_distinct() -> None:
    """产品契约：悲鸣高亮且“挑战”和“组队”并列时，只选择单人挑战。"""
    script, _ = _script("home.jpg")
    other = _image("floor_other.jpg")
    solo = _image("soul_soil.jpg")

    assert not script._is_soul_soil_selected(other)
    assert script._is_soul_soil_selected(solo)
    challenge = script._unique_text(solo, "挑战", (980, 500, 1136, 610))
    team = script._unique_text(solo, "组队", (790, 500, 980, 610))
    assert challenge is not None and team is not None
    assert challenge[0] > team[0]


def test_lobby_requires_yuhun_group_and_highlighted_soul_soil_row() -> None:
    """产品契约：只在单人准备页选择御魂组中已高亮的首个魂土队伍。"""
    script, env = _script("home.jpg")
    frame = _image("lobby_preset_soul_group.jpg")
    other_group = _image("lobby_preset_other_group.jpg")

    group = script._unique_text(frame, "御魂", (20, 190, 160, 610))
    assert group is not None and script._lobby_group_selected(frame, group)
    assert not script._lobby_group_selected(other_group, group)
    assert script._is_lobby_preset(frame)
    assert script._select_lobby_lineup(frame) is frame
    assert env.action_records == []
    assert script._is_lobby(_image("solo_lobby.jpg"))
    assert not script._is_lobby(_image("soul_soil.jpg"))
    assert len(script._text_points(frame, "魂土", (170, 195, 620, 270))) == 1


def test_registered_battle_marker_sends_no_input() -> None:
    """产品契约：录制的战斗页只刷新 RunGuard 识别态，不发送点击。"""
    script, env = _script("battle.jpg")

    script._read()

    assert script._last_triggered_event == "yys/common/images/scene/battling.bmp"
    assert env.action_records == []


def test_result_count_is_idempotent_and_stops_at_configured_limit() -> None:
    """产品契约：重复结算不重复计数，达到目标后不得启动下一场。"""
    script, _ = _script()
    script.max_battle_count = 2
    script._battle_started = True
    assert script._record_battle()
    assert not script._record_battle()
    assert script._cur_battle_count == 1
    script._battle_counted = False
    assert script._record_battle()
    assert not script._can_start_next_battle()
    script.stop()
    assert not script._can_start_next_battle()


def test_observe_mode_and_wrong_entry_send_no_input() -> None:
    """产品契约：观察/未知入口都不能推进，也不能把未运行报告为完成。"""
    observing, observe_env = _script("home.jpg", observe_only=True)
    with pytest.raises(RuntimeError, match="SOUL_SOIL_OBSERVE"):
        observing.run()
    assert observing.get_state_snapshot()["stage"] == "observing"
    assert not observing.get_state_snapshot()["flow_complete"]
    assert observe_env.action_records == []

    wrong_page, wrong_env = _script("exploration.jpg")
    with pytest.raises(RuntimeError, match="SOUL_SOIL_ENTRY"):
        wrong_page.run()
    assert wrong_env.action_records == []


def test_home_exit_confirmation_is_cancelled_with_escape() -> None:
    """产品契约：回庭院遇到“确认离开”只发 ESC，并重新识别庭院。"""
    script, env = _script()

    class ExitPromptOcr:
        """为未录制的退出弹窗提供一次确认文字，随后模拟其消失。"""

        def __init__(self) -> None:
            self.calls = 0

        def find_all_text_positions(
            self, _image: np.ndarray, _threshold: float = 0.85,
        ) -> list[tuple[int, int, str, float]]:
            self.calls += 1
            if self.calls == 1:
                return [(500, 250, "确认离开吗", 0.99), (500, 420, "取消", 0.99),
                        (620, 420, "确定", 0.99)]
            return []

    setattr(script, "ocr", ExitPromptOcr())
    script._return_to_home()

    assert script._is_home(_image("home.jpg"))
    assert [(record.action_type, record.extra.get("key_code"))
            for record in env.action_records] == [("key_press", 27)]


def test_real_presets_return_uses_existing_shared_matcher(monkeypatch: pytest.MonkeyPatch) -> None:
    """产品契约：式神录应用预设后能识别返回按钮并回庭院，不能调用不存在的匹配函数。"""
    provider = FileImageProvider()
    provider.set_current_image_from_file(str(_FIXTURES / "shikigami_presets.jpg"))
    delegate = MockEnvironment(image_provider=provider)
    original = delegate.left_click

    def click(x: int, y: int) -> None:
        original(x, y)
        provider.set_current_image_from_file(str(_FIXTURES / "home.jpg"))

    monkeypatch.setattr(delegate, "left_click", click)
    script = SoulSoilScript(env=delegate)
    script._return_to_home(from_lineup=True)
    assert len(script._env.action_records) == 1
    assert script._is_home(script._read())
