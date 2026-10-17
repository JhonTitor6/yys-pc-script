"""安全奉纳未锁定、未装备的五星御魂。

默认只做离线识别。真实运行必须显式传入 ``--execute``，且所有输入都经由
``GameEnvironment``；本模块不使用视觉代理逐批判图。
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Callable, Iterable, Protocol, Sequence

import cv2
import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 奉纳页在当前客户端的客户区坐标。检测会按截图尺寸等比缩放。
REFERENCE_SIZE = (1138, 641)
CARD_LEFTS = (76, 181, 286, 391)
CARD_TOPS = (211, 323, 434, 545)
CARD_SIZE = (95, 101)
STAR_ROI = (14, 72, 85, 98)
MAX_BATCH_SIZE = 200
GOLD_PER_FIVE_STAR = 1000
SELECTION_COUNT_ROI = (710, 351, 815, 473)
SELECTION_GOLD_ROI = (779, 505, 879, 549)
SETTLEMENT_ROI = (330, 220, 805, 440)
DEFAULT_LONG_PRESS_SECONDS = 1.5


class SoulSellStop(RuntimeError):
    """识别或交叉核对失败时的安全停机。"""


class TextReader(Protocol):
    """返回 OCR 结果 ``(box, text, confidence)``。"""

    def __call__(self, image: np.ndarray) -> Iterable[tuple[object, str, float]]:
        ...


class ProtectionReader(Protocol):
    """读取卡片是否有锁定或方案占用标记。"""

    def __call__(self, image: np.ndarray) -> tuple[bool | None, bool | None]:
        ...


@dataclass(frozen=True)
class CardObservation:
    """一张可见御魂卡片的程序化识别结果。"""

    row: int
    column: int
    rect: tuple[int, int, int, int]
    stars: int | None
    enhancement_level: int | None = None
    selected: bool | None = None
    locked: bool | None = None
    in_plan: bool | None = None

    @property
    def center(self) -> tuple[int, int]:
        """返回卡片中心点。"""
        x, y, width, height = self.rect
        return x + width // 2, y + height // 2

    @property
    def protected(self) -> bool:
        """返回是否已明确识别为锁定或方案占用。"""
        return self.locked is True or self.in_plan is True


@dataclass(frozen=True)
class GridObservation:
    """奉纳页当前画面的卡片识别结果。"""

    cards: tuple[CardObservation, ...]

    @property
    def five_star_cards(self) -> tuple[CardObservation, ...]:
        """返回可确认是五星且当前未显示为已选中的卡片。"""
        return tuple(
            card
            for card in self.cards
            if card.stars == 5 and card.selected is not True
        )

    @property
    def six_star_cards(self) -> tuple[CardObservation, ...]:
        """返回可确认是六星的可见卡片。"""
        return tuple(card for card in self.cards if card.stars == 6)

    @property
    def unknown_cards(self) -> tuple[CardObservation, ...]:
        """返回星级无法可靠识别的卡片。"""
        return tuple(card for card in self.cards if card.stars is None)


@dataclass(frozen=True)
class SelectionEvidence:
    """奉纳预览页的数量和基础金币证据。"""

    selected_count: int | None
    preview_gold: int | None
    texts: tuple[str, ...] = ()


@dataclass(frozen=True)
class SettlementEvidence:
    """结算遮罩中的金币证据。"""

    reward_gold: int | None
    texts: tuple[str, ...] = ()


@dataclass
class SellReport:
    """一次运行的可审阅结果。"""

    sold_count: int = 0
    batch_count: int = 0
    stop_reason: str | None = None
    kept_reasons: list[str] = field(default_factory=list)
    batches: list[dict[str, int | str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """转换为稳定的 JSON 结构。"""
        return asdict(self)


def _frame_to_bgr(frame: Image.Image | np.ndarray) -> np.ndarray:
    """把 PIL RGB 或 ndarray 统一为 BGR。"""
    if isinstance(frame, Image.Image):
        return cv2.cvtColor(np.asarray(frame.convert("RGB")), cv2.COLOR_RGB2BGR)
    if not isinstance(frame, np.ndarray) or frame.ndim not in (2, 3):
        raise ValueError("截图必须是 PIL.Image 或 numpy.ndarray")
    if frame.ndim == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    if frame.shape[2] != 3:
        raise ValueError("截图必须包含三个颜色通道")
    return frame


def _scaled_rect(
    row: int,
    column: int,
    frame_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    """按当前客户区尺寸缩放奉纳页卡片矩形。"""
    width, height = frame_size
    scale_x = width / REFERENCE_SIZE[0]
    scale_y = height / REFERENCE_SIZE[1]
    x = round(CARD_LEFTS[column] * scale_x)
    y = round(CARD_TOPS[row] * scale_y)
    right = round((CARD_LEFTS[column] + CARD_SIZE[0]) * scale_x)
    bottom = round((CARD_TOPS[row] + CARD_SIZE[1]) * scale_y)
    return x, y, right - x, bottom - y


def detect_star_count(frame: Image.Image | np.ndarray, rect: tuple[int, int, int, int]) -> int | None:
    """在一张卡片底部识别橙色星形数量，失败返回 ``None``。

    星形是固定尺寸的橙色连通域；底部边框和卡片上的其它图案会被形状过滤。
    """
    bgr = _frame_to_bgr(frame)
    x, y, width, height = rect
    rx0, ry0, rx1, ry1 = STAR_ROI
    x0, y0 = x + rx0, y + ry0
    x1, y1 = x + rx1, y + ry1
    if x0 < 0 or y0 < 0 or x1 > bgr.shape[1] or y1 > bgr.shape[0]:
        return None
    if width < CARD_SIZE[0] * 0.8 or height < CARD_SIZE[1] * 0.8:
        return None
    hsv = cv2.cvtColor(bgr[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    mask = (
        (hsv[:, :, 0] <= 25)
        & (hsv[:, :, 1] >= 170)
        & (hsv[:, :, 2] >= 100)
    ).astype(np.uint8)
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    count = 0
    for _left, top, item_width, item_height, area in stats[1:]:
        if top < 8:
            continue
        if 8 <= item_width <= 13 and 12 <= item_height <= 18 and 70 <= area <= 140:
            count += 1
    return count if 1 <= count <= 6 else None


def _detect_selected(bgr: np.ndarray, rect: tuple[int, int, int, int]) -> bool | None:
    """用卡片边框的蓝色覆盖层判断是否已选中。"""
    x, y, width, height = rect
    if x < 0 or y < 0 or x + width > bgr.shape[1] or y + height > bgr.shape[0]:
        return None
    border = np.concatenate(
        (
            bgr[y : y + 5, x : x + width].reshape(-1, 3),
            bgr[y + height - 5 : y + height, x : x + width].reshape(-1, 3),
            bgr[y : y + height, x : x + 5].reshape(-1, 3),
            bgr[y : y + height, x + width - 5 : x + width].reshape(-1, 3),
        ),
        axis=0,
    )
    hsv = cv2.cvtColor(border.reshape(1, -1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    blue = (
        (hsv[:, 0] >= 85)
        & (hsv[:, 0] <= 125)
        & (hsv[:, 1] >= 55)
        & (hsv[:, 2] >= 70)
    )
    ratio = float(np.mean(blue))
    return ratio >= 0.20


def _normalise_digits(text: str) -> str:
    """只保留 OCR 结果中的阿拉伯数字。"""
    return "".join(re.findall(r"\d", text))


def _read_numbers(
    frame: Image.Image | np.ndarray,
    roi: tuple[int, int, int, int],
    text_reader: TextReader,
) -> tuple[tuple[int, ...], tuple[str, ...]]:
    """读取一个 ROI 中的数字并保留原始 OCR 文本。"""
    bgr = _frame_to_bgr(frame)
    x0, y0, x1, y1 = roi
    x1 = min(x1, bgr.shape[1])
    y1 = min(y1, bgr.shape[0])
    if x0 >= x1 or y0 >= y1:
        return (), ()
    values: list[int] = []
    texts: list[str] = []
    for _, text, confidence in text_reader(bgr[y0:y1, x0:x1]):
        if confidence < 0.80:
            continue
        texts.append(str(text))
        digits = _normalise_digits(str(text))
        if digits:
            values.append(int(digits))
    return tuple(values), tuple(texts)


def parse_level(texts: Iterable[str]) -> int | None:
    """从卡片左上角 OCR 文本中解析 ``+0`` 到 ``+15``。"""
    for text in texts:
        match = re.search(r"\+\s*(\d{1,2})", text)
        if match is None:
            continue
        level = int(match.group(1))
        if 0 <= level <= 15:
            return level
    return None


def is_fengna_page(
    frame: Image.Image | np.ndarray,
    text_reader: TextReader,
) -> bool:
    """用奉纳页的固定中文控件确认页面和筛选状态。"""
    bgr = _frame_to_bgr(frame)
    header = bgr[70 : min(205, bgr.shape[0]), 0 : min(520, bgr.shape[1])]
    texts = [
        str(text)
        for _, text, confidence in text_reader(header)
        if confidence >= 0.80
    ]
    if not any("全部" in text for text in texts) or not any(
        "星级升序" in text for text in texts
    ):
        return False
    if bgr.shape[0] <= 101 or bgr.shape[1] <= 130:
        return False
    # “全部”选中时左锚点为深色，右侧“已弃置”未选中；反向则是错误页。
    all_anchor = bgr[101, 26]
    discarded_anchor = bgr[101, 130]
    return int(discarded_anchor[2]) - int(all_anchor[2]) >= 50


def detect_card_protection(
    card: np.ndarray,
    text_reader: TextReader | None = None,
) -> tuple[bool | None, bool | None]:
    """识别卡片锁标记和“方案中”文字，无法确认时返回 ``None``。

    蓝色菱形锁标记是结构化视觉证据；方案状态要求 OCR 在卡片本身读到“方案”。
    任何一种证据不足都不会被当作安全卡片。
    """
    if card.ndim != 3 or card.shape[2] != 3:
        return None, None
    height, width = card.shape[:2]
    if width < 80 or height < 70:
        return None, None
    region = card[0 : min(70, height), max(0, width - 35) : width]
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    mask = (
        (hsv[:, :, 0] >= 85)
        & (hsv[:, :, 0] <= 125)
        & (hsv[:, :, 1] >= 80)
        & (hsv[:, :, 2] >= 70)
    ).astype(np.uint8)
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    locked = any(
        item_width >= 15
        and item_height >= 15
        and area >= 120
        for _, _, item_width, item_height, area in stats[1:]
    )
    in_plan: bool | None = None
    if text_reader is not None:
        texts = [
            str(text)
            for _, text, confidence in text_reader(card)
            if confidence >= 0.80
        ]
        if any("方案" in text or "预设" in text for text in texts):
            in_plan = True
        elif texts:
            in_plan = False
    return locked, in_plan


def observe_grid(
    frame: Image.Image | np.ndarray,
    *,
    level_reader: TextReader | None = None,
    protection_reader: ProtectionReader | None = None,
) -> GridObservation:
    """识别当前奉纳页中完整可见卡片的星级。"""
    bgr = _frame_to_bgr(frame)
    frame_size = (bgr.shape[1], bgr.shape[0])
    cards: list[CardObservation] = []
    for row, _ in enumerate(CARD_TOPS):
        for column, _ in enumerate(CARD_LEFTS):
            rect = _scaled_rect(row, column, frame_size)
            x, y, width, height = rect
            if x + width > bgr.shape[1] or y + height > bgr.shape[0]:
                continue
            level = None
            locked = None
            in_plan = None
            if level_reader is not None:
                level_texts = level_reader(bgr[y : y + 28, x : x + 48])
                level = parse_level(text for _, text, _ in level_texts)
            if protection_reader is not None:
                locked, in_plan = protection_reader(bgr[y : y + height, x : x + width])
            cards.append(
                CardObservation(
                    row=row,
                    column=column,
                    rect=rect,
                    stars=detect_star_count(bgr, rect),
                    enhancement_level=level,
                    selected=_detect_selected(bgr, rect),
                    locked=locked,
                    in_plan=in_plan,
                )
            )
    return GridObservation(tuple(cards))


def read_selection_evidence(
    frame: Image.Image | np.ndarray,
    text_reader: TextReader,
) -> SelectionEvidence:
    """读取奉纳预览中的选中件数和基础金币。"""
    counts, count_texts = _read_numbers(frame, SELECTION_COUNT_ROI, text_reader)
    golds, gold_texts = _read_numbers(frame, SELECTION_GOLD_ROI, text_reader)
    count = next((value for value in counts if 0 <= value <= MAX_BATCH_SIZE), None)
    gold = next((value for value in golds if value >= 0), None)
    return SelectionEvidence(count, gold, count_texts + gold_texts)


def read_settlement_evidence(
    frame: Image.Image | np.ndarray,
    text_reader: TextReader,
) -> SettlementEvidence:
    """读取结算遮罩中的奖励金币。"""
    values, texts = _read_numbers(frame, SETTLEMENT_ROI, text_reader)
    reward = max(values, default=None)
    return SettlementEvidence(reward, texts)


def verify_selection(evidence: SelectionEvidence) -> int:
    """核对预览件数和五星基础金币，失败立即停机。"""
    count = evidence.selected_count
    gold = evidence.preview_gold
    if count is None or gold is None:
        raise SoulSellStop("奉纳前无法可靠识别选中数量或预览金币")
    if not 1 <= count <= MAX_BATCH_SIZE:
        raise SoulSellStop(f"选中数量超出安全范围: {count}")
    expected = count * GOLD_PER_FIVE_STAR
    if gold != expected:
        raise SoulSellStop(
            f"预览金币不符合五星基础金币: 数量={count}, 预期={expected}, 实际={gold}"
        )
    return count


def verify_settlement(evidence: SettlementEvidence, expected_base_gold: int) -> int:
    """核对结算奖励是五星基础金币的正整数倍。"""
    reward = evidence.reward_gold
    if reward is None or expected_base_gold <= 0:
        raise SoulSellStop("结算金币无法可靠识别")
    if reward < expected_base_gold or reward % expected_base_gold != 0:
        raise SoulSellStop(
            f"结算金币不符合预期: 基础={expected_base_gold}, 实际={reward}"
        )
    return reward


class _InputEnvironment(Protocol):
    """奉纳脚本所需的最小环境能力。"""

    def capture_screen(self) -> Image.Image:
        ...

    def left_click(self, x: int, y: int) -> None:
        ...

    def long_press(self, x: int, y: int, duration: float) -> None:
        ...


class SoulSellRunner:
    """按识别结果分批奉纳五星御魂。"""

    def __init__(
        self,
        env: _InputEnvironment,
        *,
        text_reader: TextReader | None = None,
        level_reader: TextReader | None = None,
        protection_reader: ProtectionReader | None = None,
        rng: random.Random | None = None,
        sleep: Callable[[float], None] = time.sleep,
        long_press_seconds: float = DEFAULT_LONG_PRESS_SECONDS,
        selection_timeout: float = 8.0,
        settlement_timeout: float = 12.0,
        max_batches: int = 1000,
        require_page_markers: bool = True,
        allow_batch: bool = False,
    ) -> None:
        if long_press_seconds <= 0 or selection_timeout <= 0 or settlement_timeout <= 0:
            raise ValueError("等待和长按时长必须为正数")
        if max_batches <= 0:
            raise ValueError("max_batches 必须为正数")
        self.env = env
        self.text_reader = text_reader or self._default_text_reader()
        self.level_reader = level_reader or self.text_reader
        self.protection_reader = protection_reader or (
            lambda card: detect_card_protection(card, self.text_reader)
        )
        self.rng = rng or random.Random()
        self.sleep = sleep
        self.long_press_seconds = long_press_seconds
        self.selection_timeout = selection_timeout
        self.settlement_timeout = settlement_timeout
        self.max_batches = max_batches
        self.require_page_markers = require_page_markers
        self.allow_batch = allow_batch
        self._used_points: list[tuple[int, int]] = []

    @staticmethod
    def _default_text_reader() -> TextReader:
        """延迟创建既有 OCR 后端，离线星级识别不加载 OCR。"""
        from win_util.ocr import CommonOcr

        reader = CommonOcr()
        return reader.ocr

    def run(self) -> SellReport:
        """持续奉纳直到没有可确认的五星或触发安全停机。"""
        report = SellReport()
        blocked_cards: set[tuple[int, int]] = set()
        for _ in range(self.max_batches):
            try:
                self._check_guard()
                frame = self.env.capture_screen()
                self._validate_frame_size(frame)
                if self.require_page_markers:
                    if not is_fengna_page(frame, self.text_reader):
                        report.stop_reason = "未确认奉纳页、全部页和星级升序状态，停止输入"
                        report.kept_reasons.append("页面状态无法可靠识别")
                        return report
                observation = observe_grid(frame)
            except SoulSellStop as exc:
                report.stop_reason = str(exc)
                return report
            if not any(card.stars in (1, 2, 3, 4, 5, 6) for card in observation.cards):
                report.stop_reason = "未识别到奉纳页卡片，停止输入"
                report.kept_reasons.append("页面或截图状态无法可靠识别")
                return report
            initial_selection = read_selection_evidence(frame, self.text_reader)
            if (
                (self.require_page_markers and initial_selection.preview_gold is None)
                or initial_selection.preview_gold not in (None, 0)
                or any(card.selected for card in observation.cards)
            ):
                report.stop_reason = "奉纳前已有选中御魂，停止输入"
                return report
            bgr = _frame_to_bgr(frame)
            inspected_five: list[CardObservation] = []
            target = None
            for card in observation.five_star_cards:
                x, y, width, height = card.rect
                level_texts = self.level_reader(bgr[y : y + 28, x : x + 48])
                level = parse_level(text for _, text, _ in level_texts)
                locked, in_plan = self.protection_reader(bgr[y : y + height, x : x + width])
                inspected = replace(
                    card, enhancement_level=level, locked=locked, in_plan=in_plan
                )
                inspected_five.append(inspected)
                if (
                    target is None
                    and (card.row, card.column) not in blocked_cards
                    and locked is False
                    and in_plan is False
                ):
                    target = inspected
                    if not self.allow_batch:
                        break
            if target is None:
                protected_five = tuple(
                    card
                    for card in inspected_five
                    if card.protected
                    or card.locked is not False
                    or card.in_plan is not False
                )
                if protected_five:
                    report.kept_reasons.append(
                        f"保留锁定、方案占用或状态未知的五星: {len(protected_five)} 件"
                    )
                if observation.six_star_cards:
                    report.stop_reason = "检测到六星，立即停止"
                elif observation.unknown_cards:
                    report.stop_reason = "存在无法可靠识别星级的御魂，停止并保留"
                    report.kept_reasons.append("星级无法可靠识别")
                else:
                    report.stop_reason = "没有剩余可确认的五星御魂"
                return report
            target_index = next(
                i for i, card in enumerate(observation.cards)
                if (card.row, card.column) == (target.row, target.column)
            )
            if any(
                card.stars == 6
                for card in observation.cards[:target_index]
            ):
                report.stop_reason = "五星目标前检测到六星，立即停止"
                return report
            if any(
                card.stars is None
                for card in observation.cards[:target_index]
            ):
                report.stop_reason = "五星目标前存在无法识别的御魂，停止输入"
                report.kept_reasons.append("前置卡片星级无法可靠识别")
                return report
            batch_safe = all(
                card.locked is False
                and card.in_plan is False
                and not (
                    card.enhancement_level is not None
                    and card.enhancement_level > 0
                )
                for card in inspected_five
            )
            mode = "batch" if self.allow_batch and batch_safe else "single"
            if target.enhancement_level is not None and target.enhancement_level > 0:
                mode = "single"
            try:
                if mode == "single":
                    self._select_one(target)
                    self._close_card_detail()
                else:
                    self._select_batch(target)
                evidence = self._wait_selection(mode)
                try:
                    count = verify_selection(evidence)
                except SoulSellStop:
                    if mode == "single" and evidence.selected_count == 0 and evidence.preview_gold == 0:
                        blocked_cards.add((target.row, target.column))
                        report.kept_reasons.append(
                            f"保留第{target.row + 1}行第{target.column + 1}列：未能选中，可能锁定、装备或方案占用"
                        )
                        continue
                    raise
                self._click_button()
                settlement = self._wait_settlement(count * GOLD_PER_FIVE_STAR)
                reward = verify_settlement(settlement, count * GOLD_PER_FIVE_STAR)
                self._dismiss_settlement(count * GOLD_PER_FIVE_STAR)
            except SoulSellStop as exc:
                report.stop_reason = str(exc)
                if mode == "single":
                    report.kept_reasons.append("单件选择失败，可能已锁定、装备或方案占用")
                return report
            report.sold_count += count
            report.batch_count += 1
            report.batches.append({"mode": mode, "count": count, "reward_gold": reward})
        report.stop_reason = f"达到批次上限: {self.max_batches}"
        return report

    def _select_batch(self, target: CardObservation) -> None:
        """在已确认五星卡片内部随机长按。"""
        self._long_press_card(target)

    def _select_one(self, target: CardObservation) -> None:
        """单独选择已强化五星；锁定或方案占用会在数量核对时安全停机。"""
        self._click_card(target)

    def _close_card_detail(self) -> None:
        """关闭单件点击后的详情浮层，保留已选中状态。"""
        self.sleep(0.5)
        self.env.left_click(*self._unique_in_bounds(930, 970, 460, 500))
        self._check_guard()
        self.sleep(0.5)

    def _long_press_card(self, card: CardObservation) -> None:
        point = self._random_card_point(card)
        self.env.long_press(*point, self.long_press_seconds)
        self._check_guard()

    def _click_card(self, card: CardObservation) -> None:
        self.env.left_click(*self._random_card_point(card))
        self._check_guard()

    def _random_card_point(self, card: CardObservation) -> tuple[int, int]:
        x, y, width, height = card.rect
        return self._unique_in_bounds(
            x + 20,
            x + width - 20,
            y + 25,
            y + height - 20,
        )

    def _click_button(self) -> None:
        self.env.left_click(*self._unique_in_bounds(752, 802, 578, 600))
        self._check_guard()

    def _dismiss_settlement(self, expected_base_gold: int) -> None:
        self.env.left_click(*self._unique_in_bounds(895, 935, 505, 535))
        self._check_guard()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            self._check_guard()
            frame = self.env.capture_screen()
            self._validate_frame_size(frame)
            reward = read_settlement_evidence(frame, self.text_reader).reward_gold
            if not (
                reward is not None
                and reward >= expected_base_gold
                and reward % expected_base_gold == 0
            ):
                observation = observe_grid(
                    frame,
                    level_reader=self.level_reader,
                    protection_reader=self.protection_reader,
                )
                if observation.cards:
                    return
            self.sleep(0.2)
        raise SoulSellStop("点击关闭后结算遮罩未在限定时间内消失")

    @staticmethod
    def _validate_frame_size(frame: Image.Image | np.ndarray) -> None:
        """输入前确认客户区尺寸与已校准安全坐标一致。"""
        if isinstance(frame, Image.Image):
            size = frame.size
        elif isinstance(frame, np.ndarray) and frame.ndim >= 2:
            size = (int(frame.shape[1]), int(frame.shape[0]))
        else:
            raise SoulSellStop("截图类型无法识别，停止输入")
        if size != REFERENCE_SIZE:
            raise SoulSellStop(f"客户区尺寸未校准: {size}, 预期={REFERENCE_SIZE}")

    def _wait_selection(self, mode: str) -> SelectionEvidence:
        deadline = time.monotonic() + self.selection_timeout
        last = SelectionEvidence(None, None)
        while time.monotonic() < deadline:
            self._check_guard()
            frame = self.env.capture_screen()
            self._validate_frame_size(frame)
            last = read_selection_evidence(frame, self.text_reader)
            if mode == "single" and last.selected_count is None:
                selected_cards = [card for card in observe_grid(frame).cards if card.selected]
                if len(selected_cards) == 1:
                    last = SelectionEvidence(1, last.preview_gold, last.texts)
            if last.selected_count is not None and last.preview_gold is not None:
                return last
            self.sleep(0.15)
        raise SoulSellStop(f"奉纳预览核对超时: {last}")

    def _wait_settlement(self, expected_base_gold: int) -> SettlementEvidence:
        deadline = time.monotonic() + self.settlement_timeout
        last = SettlementEvidence(None)
        while time.monotonic() < deadline:
            self._check_guard()
            frame = self.env.capture_screen()
            self._validate_frame_size(frame)
            last = read_settlement_evidence(frame, self.text_reader)
            if (
                last.reward_gold is not None
                and last.reward_gold >= expected_base_gold
                and last.reward_gold % expected_base_gold == 0
            ):
                return last
            self.sleep(0.2)
        raise SoulSellStop(f"奉纳结算核对超时: {last}")

    def _unique_in_bounds(
        self,
        min_x: int,
        max_x: int,
        min_y: int,
        max_y: int,
    ) -> tuple[int, int]:
        for _ in range(100):
            point = (
                self.rng.randint(min_x, max_x),
                self.rng.randint(min_y, max_y),
            )
            if point not in self._used_points:
                self._used_points.append(point)
                if len(self._used_points) > 64:
                    self._used_points.pop(0)
                return point
        raise SoulSellStop("随机点击无法生成不重复的安全坐标")

    def _check_guard(self) -> None:
        guard = getattr(self.env, "guard", None)
        if guard is not None and getattr(guard, "is_stopped", False):
            raise SoulSellStop(f"运行保险丝已停止: {guard.stop_reason}")


def offline_observe(paths: Sequence[Path]) -> list[dict[str, object]]:
    """离线识别截图，并对六星样本给出停机结论。"""
    results: list[dict[str, object]] = []
    for path in paths:
        with Image.open(path) as image:
            frame = image.copy()
            observation = observe_grid(frame)
        six_seen = bool(observation.six_star_cards)
        item: dict[str, object] = {
            "path": str(path),
            "five_star_count": len(observation.five_star_cards),
            "six_star_count": len(observation.six_star_cards),
            "unknown_count": len(observation.unknown_cards),
            "six_star_stop": six_seen and not observation.five_star_cards,
        }
        if six_seen and not observation.five_star_cards:
            probe = _OfflineProbeEnvironment(frame)
            report = SoulSellRunner(
                probe,
                text_reader=lambda _image: (),
                level_reader=lambda _image: (),
                sleep=lambda _seconds: None,
                require_page_markers=False,
            ).run()
            item["runner_stop_reason"] = report.stop_reason
            item["runner_input_count"] = len(probe.actions)
        results.append(item)
    return results


class _OfflineProbeEnvironment:
    """离线六星保护探针，输入只记录不发送。"""

    def __init__(self, frame: Image.Image) -> None:
        self.frame = frame
        self.actions: list[tuple[object, ...]] = []

    def capture_screen(self) -> Image.Image:
        return self.frame

    def left_click(self, x: int, y: int) -> None:
        self.actions.append(("click", x, y))

    def long_press(self, x: int, y: int, duration: float) -> None:
        self.actions.append(("long_press", x, y, duration))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", nargs="+", type=Path, help="只读识别指定截图")
    parser.add_argument("--execute", action="store_true", help="显式执行真实游戏输入")
    parser.add_argument("--window-title", default="阴阳师")
    parser.add_argument("--confirmation-phrase", help="真实运行确认短语：RUN sell_five_star_souls")
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    parser.add_argument("--max-actions", type=int, default=4000)
    parser.add_argument("--max-batches", type=int, default=1000, help="本次最多处理的批次数")
    parser.add_argument(
        "--allow-batch",
        action="store_true",
        help="在每张可见五星的锁定/方案状态均已确认时启用最多200件长按批次",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口。"""
    args = _build_parser().parse_args(argv)
    if args.offline:
        print(json.dumps(offline_observe(args.offline), ensure_ascii=False, indent=2))
        return 0
    if not args.execute:
        raise SystemExit("默认只读；请传入 --offline 截图或显式 --execute")
    expected_confirmation = "RUN sell_five_star_souls"
    if args.confirmation_phrase != expected_confirmation:
        print(f"确认短语不匹配，未启动；需要 {expected_confirmation}", file=sys.stderr)
        return 2
    from win_util.environment.windows import WindowsEnvironment
    from win_util.environment.guarded import GuardedEnvironment, RunGuard
    from yys.common.recording.win32_input import WindowsInputMonitor

    real_env = WindowsEnvironment(window_title=args.window_title, capture_mode="print_window")
    guard = RunGuard(timeout_seconds=args.timeout_seconds, max_actions=args.max_actions)
    env = GuardedEnvironment(real_env, guard, observe_only=False)

    def stop_on_input(_reason: str) -> None:
        guard.request_emergency_stop()

    monitor = WindowsInputMonitor(
        hwnd=real_env.hwnd,
        on_mouse=lambda *_args: None,
        on_keyboard=lambda *_args: None,
        on_stop=stop_on_input,
    )
    try:
        monitor.start()
        report = SoulSellRunner(
            env,
            require_page_markers=True,
            allow_batch=args.allow_batch,
            max_batches=args.max_batches,
        ).run()
    finally:
        monitor.stop()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.stop_reason == "没有剩余可确认的五星御魂" else 1


if __name__ == "__main__":
    raise SystemExit(main())
