"""基于真实页面识别的单次结界寄养，不按录制坐标时间线回放。"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from win_util.environment.base import GameEnvironment
from win_util.environment.guarded import GuardedEnvironment, RunGuard
from win_util.environment.windows import WindowsEnvironment
from win_util.image import to_project_path
from yys.common.event_script_base import YYSBaseScript
from yys.common.script_meta import ScriptMeta


class _Stopped(Exception):
    """用户停止或观察完当前一步。"""


@dataclass(frozen=True)
class FosterCandidate:
    """一个已核验可进入的太鼓候选；同星级保留扫描顺序。"""

    tab: str
    name: str
    stars: int


class RealmFosterScript(YYSBaseScript):
    """扫描好友和跨区太鼓，按星级选择并寄养左边第一个式神。"""

    SCRIPT_META = ScriptMeta("结界寄养", "日常", None, {})
    SIZE = (1138, 641)
    MAX_SCROLLS = 40

    def __init__(
        self, script_name: str = "realm_foster", config: dict | None = None,
        env: GameEnvironment | None = None,
    ) -> None:
        """复用现有环境、OCR 和保险丝；普通运行同样限制动作和总时长。"""
        actual = env if env is not None else WindowsEnvironment()
        guard = actual.guard if isinstance(actual, GuardedEnvironment) else RunGuard(
            timeout_seconds=300, max_actions=600, unknown_limit=3,
        )
        guarded = actual if isinstance(actual, GuardedEnvironment) else GuardedEnvironment(
            actual, guard, observe_only=False,
        )
        super().__init__(script_name, config=config, env=guarded)
        self.set_run_guard(guard)
        self._size = self.SIZE
        self._stage = "initial"
        self._outcome = "pending"
        self._selected: FosterCandidate | None = None
        self._images = Path(to_project_path("yys/realm_foster/images"))
        self._stars = [cv2.imread(str(self._images / f"{name}_star.png"))
                       for name in ("active", "inactive")]
        self._live_stars = [cv2.imread(str(self._images / f"{name}_star_live.png"))
                            for name in ("active", "inactive")]
        if any(image is None for image in self._stars + self._live_stars):
            raise ValueError("寄养星级模板缺失")

    def on_run(self) -> None:
        """重置本轮结果，不启用通用战斗输入。"""
        super().on_run()
        self._stage, self._outcome = "initial", "pending"
        self._selected = None

    def get_state_snapshot(self) -> dict[str, object]:
        """公开业务结果；寄养不改变战斗次数。"""
        return {**super().get_state_snapshot(), "stage": self._stage,
                "outcome": self._outcome,
                "selected_stars": self._selected.stars if self._selected else None}

    def run(self) -> None:
        """完成一次寄养；只有成功或已在寄养并返回庭院才正常结束。"""
        self.on_run()
        try:
            frame = self._read()
            if self._match(frame, "home") is None:
                raise RuntimeError("[FOSTER_ENTRY] 请从庭院启动寄养")
            point = self._match(frame, "home_menu")
            if point is None:
                expand = self.image_finder.best_match(
                    frame, "yys/common/images/lineup/home_menu_collapsed_night.png",
                )
                if expand.similarity < 0.90:
                    raise RuntimeError("[FOSTER_ENTRY] 未确认庭院菜单展开按钮")
                self._click(expand.point)
                frame = self._wait(lambda f: self._match(f, "home_menu") is not None)
                point = self._match(frame, "home_menu")
            if point is None:
                raise RuntimeError("[FOSTER_ENTRY] 未确认阴阳寮入口")
            self._click(point)
            frame = self._wait_guild()
            self._click(self._required(frame, "guild"))
            frame = self._wait(lambda f: self._match(f, "growth_entry") is not None)
            self._click(self._required(frame, "growth_entry"))
            frame = self._wait(lambda f: self._match(f, "growth") is not None)
            if self._fostering(frame):
                self._outcome = "already_fostering"
            else:
                self._click(self._required(frame, "foster_open"))
                self._wait(self._panel)
                self._stage = "scanning"
                candidates = self._scan("好友") + self._scan("跨区")
                self._selected = self.choose(candidates)
                frame = self._revisit(self._selected)
                self._click(self._required(frame, "enter"))
                frame = self._wait(lambda f: not self._panel(f)
                                   and self._match(f, "growth_entry") is not None)
                self._click(self._required(frame, "growth_entry"))
                frame = self._wait(lambda f: self._match(f, "growth") is not None)
                # 产品规则是左边第一个，不额外筛选白蛋、等级或固定式神。
                self._click((178, 515))
                frame = self._wait(lambda f: self._match(f, "confirm") is not None)
                self._stage = "confirming"
                self._click(self._required(frame, "confirm_button"))
                self._wait(lambda f: self._match(f, "confirm") is None
                           and self._fostering(f))
                self._outcome = "fostered"
            self._return_home()
            self._stage = "done"
        except _Stopped:
            return
        except Exception:
            self._stage, self._outcome = "failed", "failed"
            raise

    @staticmethod
    def choose(candidates: list[FosterCandidate]) -> FosterCandidate:
        """跨两个列表按星级从高到低选太鼓；同星级取先出现者。"""
        if not candidates:
            raise RuntimeError("[FOSTER_NO_TAIKO] 两个列表均无已确认可用太鼓")
        return max(candidates, key=lambda candidate: candidate.stars)

    def _wait_guild(self) -> np.ndarray:
        """关闭实机已确认的树木升级通知，未知弹窗仍停止。"""
        frame = self._wait(lambda f: self._match(f, "guild") is not None
                           or self._match(f, "guild_tree_notice") is not None)
        if self._match(frame, "guild_tree_notice") is not None:
            self._click(self._required(frame, "guild_tree_close"))
            frame = self._wait(lambda f: self._match(f, "guild_tree_notice") is None
                               and self._match(f, "guild") is not None)
        return frame

    def _check(self) -> None:
        self.pause_point()
        if self._stop_threading_event.is_set():
            self._stage, self._outcome = "stopped", "stopped"
            raise _Stopped()
        if self._run_guard is not None and not self._run_guard.before_iteration():
            raise RuntimeError("[FOSTER_GUARD] 寄养保险丝已停止")

    def _read(self) -> np.ndarray:
        self._check()
        image = self._env.capture_screen().convert("RGB")
        self._size = image.size
        if image.width < 500 or abs(image.width / image.height - self.SIZE[0] / self.SIZE[1]) > 0.03:
            raise RuntimeError("[FOSTER_CAPTURE] 客户区尺寸或比例未校准")
        frame = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        self.image_finder.screenshot_cache = frame
        return cv2.resize(frame, self.SIZE)

    def _click(self, point: tuple[int, int]) -> None:
        self._check()
        self._env.left_click(*self._point(point))
        if self._run_guard is not None:
            self._run_guard.allow_unknown_for(8)
        if self._env.observe_only:
            self._stage, self._outcome = "observing", "observing"
            raise _Stopped()

    def _point(self, point: tuple[int, int]) -> tuple[int, int]:
        return (round(point[0] * self._size[0] / self.SIZE[0]),
                round(point[1] * self._size[1] / self.SIZE[1]))

    def _match(self, frame: np.ndarray, name: str) -> tuple[int, int] | None:
        if name == "return":
            growth = self._match(frame, "growth_return")
            if growth is not None:
                return growth
        if name == "home" and self._match(frame, "home_sakura_lantern") is not None:
            marker = self.image_finder.best_match(
                frame, to_project_path("yys/common/images/scene/home.bmp"),
            )
            if marker.similarity >= 0.72:
                return marker.point
        if name == "guild":
            current = self._match(frame, "guild_live")
            if current is not None:
                return current
        if name == "growth_entry" and self._match(frame, "return") is not None:
            labels = self._labels(frame, (170, 200, 910, 440))
            points = [(x, y) for x, y, text in labels if text == "式神育成"]
            if len(points) == 1 and any(text in ("结界防守", "结界卡") for _, _, text in labels):
                return points[0]
        path = (Path(to_project_path(f"yys/common/images/scene_control/{name}.bmp"))
                if name in ("return", "to_home") else self._images / f"{name}.png")
        result = self.image_finder.best_match(frame, str(path))
        if result.similarity < 0.92:
            return None
        template = cv2.imread(str(path))
        h, w = template.shape[:2]
        x, y = result.point
        patch = frame[y - h // 2:y - h // 2 + h, x - w // 2:x - w // 2 + w]
        if patch.shape != template.shape or float(cv2.absdiff(patch, template).mean()) > 22:
            return None
        return result.point

    def _required(self, frame: np.ndarray, name: str) -> tuple[int, int]:
        point = self._match(frame, name)
        if point is None:
            raise RuntimeError(f"[FOSTER_TARGET] 未确认寄养控件：{name}")
        return point

    def _wait(self, predicate: Callable[[np.ndarray], bool]) -> np.ndarray:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            frame = self._read()
            known = predicate(frame)
            if self._run_guard is not None:
                self._run_guard.note_iteration(known)
            if known:
                return frame
            self._stop_threading_event.wait(0.2)
        raise RuntimeError("[FOSTER_TRANSITION] 寄养页面转场未确认，未重复输入")

    def _labels(
        self, frame: np.ndarray, roi: tuple[int, int, int, int],
    ) -> list[tuple[int, int, str]]:
        x0, y0, x1, y1 = roi
        return [(x + x0, y + y0, "".join(text.split())) for x, y, text, _ in
                self.ocr.find_all_text_positions(frame[y0:y1, x0:x1], 0.90)]

    def _panel(self, frame: np.ndarray) -> bool:
        return self._match(frame, "friends") is not None

    def _rows(self, frame: np.ndarray) -> list[tuple[int, int, str]]:
        if not self._panel(frame):
            raise RuntimeError("[FOSTER_LIST] 好友寄养面板未确认")
        rows = sorted((item for item in self._labels(frame, (289, 166, 470, 542))
                       if not item[2].startswith(("[", "【"))), key=lambda item: item[1])
        if not rows or len({name for _, _, name in rows}) != len(rows):
            raise RuntimeError("[FOSTER_NAMES] 好友名称缺失或重名，不能确定目标")
        return rows

    def _switch_tab(self, tab: str) -> None:
        frame = self._read()
        if not self._panel(frame):
            raise RuntimeError("[FOSTER_LIST] 不能在未知页面切换列表")
        labels = [item for item in self._labels(frame, (190, 85, 399, 142)) if item[2] == tab]
        if len(labels) != 1:
            raise RuntimeError(f"[FOSTER_TAB] 无法唯一识别{tab}标签")
        self._click(labels[0][:2])
        # 两个标签同属已录弹窗；必须确认选中背景，不能把旧好友列表当跨区结果。
        x = 200 if tab == "好友" else 305
        self._wait(lambda f: self._panel(f) and
                   float(f[91:96, x:x + 10].mean()) > 180)

    def _wheel(self, delta: int) -> None:
        self._check()
        self._env.wheel(*self._point((430, 390)), delta)
        self._stop_threading_event.wait(0.3)

    def _top(self) -> None:
        previous = None
        unchanged = 0
        for _ in range(self.MAX_SCROLLS):
            names = tuple(name for _, _, name in self._rows(self._read()))
            unchanged = unchanged + 1 if names == previous else 0
            if unchanged >= 2:
                return
            previous = names
            self._wheel(120)
        raise RuntimeError("[FOSTER_SCROLL] 未确认好友列表顶部")

    def _inspect(self, name: str) -> tuple[np.ndarray, int | None]:
        frame = self._read()
        rows = [item for item in self._rows(frame) if item[2] == name]
        if len(rows) != 1:
            raise RuntimeError("[FOSTER_CHANGED] 候选好友已不可见")
        self._click(rows[0][:2])
        y = rows[0][1]
        def selected(f: np.ndarray) -> bool:
            if not self._panel(f):
                return False
            edge = cv2.cvtColor(f[max(166, y - 35):min(542, y + 35), 188:197], cv2.COLOR_BGR2HSV)
            return int(cv2.countNonZero(cv2.inRange(edge, (125, 100, 120), (165, 255, 255)))) > 30
        frame = self._wait(selected)
        labels = self._labels(frame, (736, 312, 834, 349))
        if not labels:
            raise RuntimeError("[FOSTER_CARD] 卡片类型无法识别")
        if not any(text == "太鼓" for _, _, text in labels):
            return frame, None
        return frame, self._star_count(frame)

    def _star_count(self, frame: np.ndarray) -> int:
        """逐格区分亮勾玉和灰勾玉，拒绝模糊槽位和不连续星级。"""
        active, inactive = self._stars
        live_active, live_inactive = self._live_stars
        values: list[bool] = []
        for index in range(6):
            x = 749 + 13 * index
            slot = frame[289:304, x:x + 13]
            hsv = cv2.cvtColor(slot, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, (12, 120, 150), (40, 255, 255))
            expected = cv2.inRange(cv2.cvtColor(active, cv2.COLOR_BGR2HSV),
                                   (12, 120, 150), (40, 255, 255))
            live_expected = cv2.inRange(cv2.cvtColor(live_active, cv2.COLOR_BGR2HSV),
                                        (12, 120, 150), (40, 255, 255))
            score = max(float(cv2.matchTemplate(mask, reference, cv2.TM_CCOEFF_NORMED)[0, 0])
                        for reference in (expected, live_expected))
            if score >= 0.70:
                values.append(True)
            elif min(float(cv2.absdiff(slot, reference).mean())
                     for reference in (inactive, live_inactive)) < 30:
                values.append(False)
            else:
                raise RuntimeError("[FOSTER_STARS] 太鼓星级无法可靠识别")
        stars = sum(values)
        if not stars or values != [True] * stars + [False] * (6 - stars):
            raise RuntimeError("[FOSTER_STARS] 太鼓星级槽位不连续")
        return stars

    def _scan(self, tab: str) -> list[FosterCandidate]:
        self._switch_tab(tab)
        self._top()
        candidates: list[FosterCandidate] = []
        seen: set[str] = set()
        previous = None
        unchanged = 0
        for _ in range(self.MAX_SCROLLS):
            frame = self._read()
            rows = self._rows(frame)
            signature = tuple(name for _, _, name in rows)
            unchanged = unchanged + 1 if signature == previous else 0
            if unchanged >= 2:
                return candidates
            for _, _, name in rows:
                if name in seen:
                    continue
                seen.add(name)
                current, stars = self._inspect(name)
                if stars is not None and self._match(current, "enter") is not None:
                    candidates.append(FosterCandidate(tab, name, stars))
            previous = signature
            self._wheel(-120)
        raise RuntimeError("[FOSTER_SCROLL] 好友列表超出扫描预算，不能保证星级优先")

    def _revisit(self, candidate: FosterCandidate) -> np.ndarray:
        self._switch_tab(candidate.tab)
        self._top()
        previous = None
        for _ in range(self.MAX_SCROLLS):
            rows = self._rows(self._read())
            names = tuple(name for _, _, name in rows)
            if candidate.name in names:
                frame, stars = self._inspect(candidate.name)
                if stars != candidate.stars or self._match(frame, "enter") is None:
                    raise RuntimeError("[FOSTER_CHANGED] 最佳太鼓已改变或不可进入")
                return frame
            if names == previous:
                break
            previous = names
            self._wheel(-120)
        raise RuntimeError("[FOSTER_CHANGED] 最佳太鼓好友已不可见")

    def _fostering(self, frame: np.ndarray) -> bool:
        if self._match(frame, "growth") is None or self._panel(frame):
            return False
        return any(re.fullmatch(r"\d{2}:\d{2}:\d{2}", text) for _, _, text in
                   self._labels(frame, (1000, 100, 1115, 141)))

    def _return_home(self) -> None:
        self._stage = "returning_home"
        for _ in range(4):
            frame = self._wait(lambda f: any(self._match(f, name) is not None
                                            for name in ("home", "growth", "growth_entry", "guild")))
            if self._match(frame, "home") is not None:
                return
            if not any(self._match(frame, name) is not None for name in
                       ("growth", "growth_entry", "guild")) or self._panel(frame):
                raise RuntimeError("[FOSTER_RETURN] 未确认可安全返回的页面")
            state = next(name for name in ("growth", "growth_entry", "guild")
                         if self._match(frame, name) is not None)
            self._click(self._match(frame, "to_home") or self._required(frame, "return"))
            self._wait(lambda f: self._match(f, state) is None and any(
                self._match(f, name) is not None
                for name in ("home", "growth", "growth_entry", "guild")))
        if self._match(self._read(), "home") is None:
            raise RuntimeError("[FOSTER_RETURN] 寄养后未确认回到庭院")
