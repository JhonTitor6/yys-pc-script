"""按分组和名称应用式神录的队伍预设，供各业务脚本复用。"""

from __future__ import annotations

import math
import time
from typing import Callable

import cv2
import numpy as np

from win_util.environment.base import GameEnvironment
from win_util.environment.guarded import GuardedEnvironment, RunGuard
from win_util.image import to_project_path
from win_util.ocr import CommonOcr

_SIZE = (1136, 640)
_REGIONS = {
    "home_entry": (920, 525, 1090, 625),
    "shikigami": (70, 0, 205, 53),
    "preset": (293, 59, 377, 112),
    "preset_panel": (635, 65, 795, 119),
    "groups": (966, 78, 1107, 560),
    "lineups": (504, 123, 754, 556),
    "dialog": (375, 255, 765, 315),
    "confirm": (593, 355, 752, 414),
    "gained_reward": (300, 130, 850, 300),
    "toast": (430, 151, 722, 245),
}
_CONFIRM_TEXT = "即将为全队式神更换预设御魂"
_SUCCESS_TEXT = "装备御魂成功"


def _name(text: str) -> str:
    """只消除排版空白，不把相似名称或子串视为同一阵容。"""
    return "".join(text.split())


class LineupSwitcher:
    """一次调用完成队伍预设应用；成功后停留在预设页。

    env 承担所有截图和输入，可传入 GuardedEnvironment 或测试环境。
    checkpoint 在每次截图/输入前调用，调用方可在此处理暂停和停止。
    名称不存在、画面未知、同屏重名或结果未证实时抛 RuntimeError；
    特别是确认应用后的异常，不应自动重试。每个并发调用应使用独立实例。
    """

    def __init__(
        self, env: GameEnvironment, *, ocr: CommonOcr | None = None,
        checkpoint: Callable[[], None] | None = None,
    ) -> None:
        self.env = env
        self.ocr = ocr if ocr is not None else CommonOcr()
        self.checkpoint = checkpoint
        self._templates: dict[str, np.ndarray] = {}
        for name in ("home_entry", "shikigami", "shikigami_preset", "preset_panel", "apply"):
            path = to_project_path(f"yys/common/images/lineup/{name}.png")
            template = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if template is None or float(template.std()) < 1:
                raise ValueError(f"阵容识别模板无效：{path}")
            self._templates[name] = template
        reward_path = to_project_path("yys/common_challenge/images/gained_reward.bmp")
        reward_template = cv2.imdecode(
            np.fromfile(reward_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE
        )
        if reward_template is None or float(reward_template.std()) < 1:
            raise ValueError(f"获得奖励模板无效：{reward_path}")
        self._templates["gained_reward"] = reward_template
        self._client_size = _SIZE
        self._guard: RunGuard | None = None

    def switch(
        self, group_name: str, lineup_name: str, *,
        timeout_seconds: float = 60.0, max_scrolls: int = 30,
    ) -> None:
        """分别按分组全名、阵容全名查找并应用预设，只有见到成功提示才返回。"""
        if not isinstance(group_name, str) or not _name(group_name):
            raise ValueError("分组名不能为空")
        if not isinstance(lineup_name, str) or not _name(lineup_name):
            raise ValueError("阵容名不能为空")
        if type(max_scrolls) is not int or max_scrolls <= 0:
            raise ValueError("max_scrolls 必须是正整数")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须是有限正数")
        self._guard = RunGuard(timeout_seconds=timeout_seconds, max_actions=4 * max_scrolls + 10)
        self._open_presets()
        self._find_name("groups", group_name, max_scrolls)
        image = self._read()
        group = self._text_point(image, "groups", group_name)
        if not self._panel(image) or group is None:
            raise RuntimeError("选择前目标分组已不可见")
        if not self._group_selected(image, group):
            self._click(group)
        self._wait_for(lambda image: self._selected_group(image, group_name), "分组未选中")
        self._find_name("lineups", lineup_name, max_scrolls, group_name)
        # 先等旧提示消失，避免上一次操作的成功提示被当成本次结果。
        self._wait_for(lambda image: self._text_point(image, "toast", _SUCCESS_TEXT) is None, "旧成功提示未消失")
        image = self._read()
        if not self._selected_group(image, group_name):
            raise RuntimeError("应用前目标分组已改变")
        lineup = self._unique(self._labels(image, "lineups"), lineup_name)
        action = self._apply_point(image, lineup) if lineup is not None else None
        if action is None:
            raise RuntimeError("应用前目标阵容或同行应用按钮已不可见")
        self._click(action)
        image = self._wait_for(
            lambda frame: self._text_point(frame, "dialog", _CONFIRM_TEXT) is not None,
            "未出现预设御魂确认弹窗",
        )
        confirm = self._text_point(image, "confirm", "确定")
        if confirm is None:
            raise RuntimeError("确认弹窗缺少明确的确定按钮")
        self._click(confirm)
        self._wait_for(
            lambda frame: self._panel(frame) and self._text_point(frame, "toast", _SUCCESS_TEXT) is not None,
            "已发送应用确认，但未证实装备御魂成功；结果不确定，请勿自动重试",
        )

    def _check(self) -> None:
        if self.checkpoint is not None:
            self.checkpoint()
        if self._guard is not None and self._guard.is_stopped:
            raise RuntimeError(f"阵容切换已停止：{self._guard.stop_reason.value}")
        if isinstance(self.env, GuardedEnvironment) and self.env.guard.is_stopped:
            raise RuntimeError(f"调用方已停止：{self.env.guard.stop_reason.value}")

    def _read(self) -> np.ndarray:
        self._check()
        image = self.env.capture_screen().convert("RGB")
        self._client_size = image.size
        if image.width <= 0 or image.height <= 0:
            raise RuntimeError("客户区截图为空")
        frame = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        return cv2.resize(frame, _SIZE, interpolation=cv2.INTER_AREA)

    def _point(self, point: tuple[int, int]) -> tuple[int, int]:
        return (
            round(point[0] * self._client_size[0] / _SIZE[0]),
            round(point[1] * self._client_size[1] / _SIZE[1]),
        )

    def _click(self, point: tuple[int, int]) -> None:
        self._check()
        if self._guard is None or not self._guard.allow_action():
            raise RuntimeError("阵容切换动作预算耗尽")
        self.env.left_click(*self._point(point))

    def _wheel(self, region: str, delta: int) -> None:
        self._check()
        if self._guard is None or not self._guard.allow_action():
            raise RuntimeError("阵容切换动作预算耗尽")
        left, top, right, bottom = _REGIONS[region]
        self.env.wheel(*self._point(((left + right) // 2, (top + bottom) // 2)), delta)
        time.sleep(0.25)

    def _match(
        self, image: np.ndarray, name: str, region: tuple[int, int, int, int] | None = None,
    ) -> tuple[int, int] | None:
        left, top, right, bottom = region or _REGIONS[name]
        area = cv2.cvtColor(image[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
        template = self._templates[name]
        height, width = template.shape
        if area.shape[0] < height or area.shape[1] < width:
            return None
        _, score, _, location = cv2.minMaxLoc(cv2.matchTemplate(area, template, cv2.TM_CCOEFF_NORMED))
        x, y = location
        patch = area[y:y + height, x:x + width]
        # 模态遮罩仍可能有很高相关性，亮度差用于拒绝遮罩后的底层控件。
        if score < 0.90 or float(cv2.absdiff(patch, template).mean()) > 25:
            return None
        return left + x + width // 2, top + y + height // 2

    def _panel(self, image: np.ndarray) -> bool:
        return self._heading(image) and self._match(image, "preset_panel") is not None

    def _heading(self, image: np.ndarray) -> bool:
        return any(
            self._match(image, name, _REGIONS["shikigami"]) is not None
            for name in ("shikigami", "shikigami_preset")
        )

    def _labels(self, image: np.ndarray, region: str) -> list[tuple[int, int, str, float]]:
        left, top, right, bottom = _REGIONS[region]
        return [
            (x + left, y + top, text, confidence)
            for x, y, text, confidence in self.ocr.find_all_text_positions(image[top:bottom, left:right], 0.85)
        ]

    @staticmethod
    def _unique(labels: list[tuple[int, int, str, float]], target: str) -> tuple[int, int] | None:
        found = [(x, y) for x, y, text, _ in labels if _name(text) == _name(target)]
        if len(found) > 1:
            raise RuntimeError(f"同屏出现多个同名目标：{target}")
        return found[0] if found else None

    def _text_point(self, image: np.ndarray, region: str, text: str) -> tuple[int, int] | None:
        return self._unique(self._labels(image, region), text)

    def _apply_point(self, image: np.ndarray, name_point: tuple[int, int]) -> tuple[int, int] | None:
        y = name_point[1]
        if not 139 <= y <= 539:
            return None
        return self._match(image, "apply", (858, max(123, y - 21), 907, min(556, y + 22)))

    @staticmethod
    def _group_selected(image: np.ndarray, point: tuple[int, int]) -> bool:
        y = point[1]
        hsv = cv2.cvtColor(image[max(78, y - 16):min(560, y + 16), 979:1092], cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (15, 100, 150), (40, 255, 255))
        return bool(mask.size and np.count_nonzero(mask) / mask.size > 0.20)

    def _selected_group(self, image: np.ndarray, group_name: str) -> bool:
        if not self._panel(image):
            return False
        point = self._text_point(image, "groups", group_name)
        return point is not None and self._group_selected(image, point)

    def _wait_for(
        self, predicate: Callable[[np.ndarray], bool], failure: str,
    ) -> np.ndarray:
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            image = self._read()
            if predicate(image):
                self._check()
                return image
            time.sleep(0.10)
        raise RuntimeError(failure)

    def _open_presets(self) -> None:
        image = self._read()
        if self._match(image, "gained_reward") is not None:
            self._click((960, 535))
            image = self._wait_for(
                lambda frame: self._match(frame, "gained_reward") is None,
                "获得奖励遮罩点击后未消失，未重复点击",
            )
        if self._panel(image):
            return
        if not self._heading(image):
            entry = self._match(image, "home_entry")
            if entry is None:
                raise RuntimeError("当前不是已验证的庭院、式神录或预设页，未发送输入")
            self._click(entry)
            image = self._wait_for(self._heading, "未到达式神录")
        preset = self._text_point(image, "preset", "预设")
        if preset is None:
            raise RuntimeError("式神录中未识别到预设入口")
        self._click(preset)
        self._wait_for(self._panel, "未打开队伍预设")

    def _find_name(
        self, region: str, target: str, max_scrolls: int, group_name: str | None = None,
    ) -> tuple[int, int]:
        for delta in (120, -120):
            previous: tuple[tuple[str, int], ...] | None = None
            unchanged = 0
            for scroll_index in range(max_scrolls + 1):
                image = self._read()
                if not self._panel(image):
                    raise RuntimeError("查找期间预设页不可见，已停止输入")
                if group_name is not None and not self._selected_group(image, group_name):
                    raise RuntimeError("查找阵容期间目标分组已改变")
                labels = self._labels(image, region)
                if not labels:
                    raise RuntimeError("列表中未识别到名称，不能据此判定滚动边界")
                point = self._unique(labels, target)
                if point is not None:
                    if region == "groups" or self._apply_point(image, point) is not None:
                        return point
                signature = tuple(sorted((_name(text), round(y / 8)) for _, y, text, _ in labels))
                unchanged = unchanged + 1 if signature == previous else 0
                if unchanged >= 2:
                    break
                if scroll_index == max_scrolls:
                    raise RuntimeError(f"查找 {target} 达到滚动次数上限")
                previous = signature
                self._wheel(region, delta)
        raise RuntimeError(f"未找到{'分组' if region == 'groups' else '阵容'}：{target}")
