"""五星御魂奉纳脚本的离线安全回归。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from tools.sell_five_star_souls import (
    SelectionEvidence,
    SettlementEvidence,
    SoulSellRunner,
    SoulSellStop,
    observe_grid,
    offline_observe,
    verify_selection,
    verify_settlement,
)
from win_util.ocr import CommonOcr


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "soul_sell"


class _NoInputEnvironment:
    """只提供离线截图并记录任何意外输入。"""

    def __init__(self, image: Image.Image) -> None:
        self.image = image
        self.actions: list[tuple[object, ...]] = []

    def capture_screen(self) -> Image.Image:
        return self.image

    def left_click(self, x: int, y: int) -> None:
        self.actions.append(("click", x, y))

    def long_press(self, x: int, y: int, duration: float) -> None:
        self.actions.append(("long_press", x, y, duration))


def _load(name: str) -> Image.Image:
    return Image.open(FIXTURE_DIR / name)


def test_production_star_detector_reads_six_star_fixture() -> None:
    """真实脱敏画面中的六星必须被识别。"""
    observation = observe_grid(_load("step6_sanitized.png"))

    assert len(observation.six_star_cards) == 12
    assert not observation.five_star_cards


def test_production_star_detector_reads_five_star_fixture() -> None:
    """真实脱敏画面中的五星必须被识别。"""
    observation = observe_grid(_load("step7_sanitized.png"))

    assert len(observation.five_star_cards) == 8
    assert not observation.six_star_cards


def test_six_star_stops_before_any_input() -> None:
    """遇到六星且没有五星目标时，执行器必须零输入停机。"""
    env = _NoInputEnvironment(_load("step6_sanitized.png"))
    runner = SoulSellRunner(
        env,
        text_reader=lambda _image: (),
        level_reader=lambda _image: (),
        sleep=lambda _seconds: None,
        require_page_markers=False,
    )

    report = runner.run()

    assert report.stop_reason == "检测到六星，立即停止"
    assert env.actions == []


def test_selection_and_settlement_gold_cross_checks() -> None:
    """预览必须严格匹配五星基础金币，结算允许整倍奖励。"""
    assert verify_selection(SelectionEvidence(200, 200_000)) == 200
    assert verify_settlement(SettlementEvidence(400_000), 200_000) == 400_000

    with pytest.raises(SoulSellStop):
        verify_selection(SelectionEvidence(200, 1_000_000))
    with pytest.raises(SoulSellStop):
        verify_settlement(SettlementEvidence(201_000), 200_000)


def test_random_card_points_are_inside_card_and_unique() -> None:
    """随机卡片点击必须留在安全内框且不重复。"""
    env = _NoInputEnvironment(_load("step7_sanitized.png"))
    runner = SoulSellRunner(
        env,
        text_reader=lambda _image: (),
        level_reader=lambda _image: (),
        sleep=lambda _seconds: None,
    )
    card = observe_grid(env.image).five_star_cards[0]

    points = [runner._random_card_point(card) for _ in range(20)]

    assert len(set(points)) == len(points)
    x, y, width, height = card.rect
    assert all(x + 20 <= px <= x + width - 20 for px, _ in points)
    assert all(y + 25 <= py <= y + height - 20 for _, py in points)


def test_offline_report_records_six_star_stop() -> None:
    """离线命令结果必须保留六星停机证据。"""
    result = offline_observe(
        [FIXTURE_DIR / "step6_sanitized.png", FIXTURE_DIR / "step7_sanitized.png"]
    )

    assert result[0]["six_star_stop"] is True
    assert result[0]["runner_stop_reason"] == "检测到六星，立即停止"
    assert result[0]["runner_input_count"] == 0
    assert result[1]["six_star_stop"] is False


def test_single_selection_uses_visible_check_when_counter_is_unreadable() -> None:
    """产品契约：单件详情关闭后可用唯一蓝勾与千金币交叉核对。"""
    env = _NoInputEnvironment(_load("single_selected_sanitized.png"))
    reader = CommonOcr().ocr
    runner = SoulSellRunner(env, text_reader=reader, level_reader=reader)

    evidence = runner._wait_selection("single")

    assert (evidence.selected_count, evidence.preview_gold) == (1, 1000)


def test_preselected_soul_stops_without_input() -> None:
    """产品契约：恢复运行时不得把前次遗留选择混入下一批。"""
    env = _NoInputEnvironment(_load("single_selected_sanitized.png"))
    reader = CommonOcr().ocr

    report = SoulSellRunner(env, text_reader=reader, level_reader=reader).run()

    assert report.stop_reason == "奉纳前已有选中御魂，停止输入"
    assert env.actions == []
