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
    MAX_TAKEOVER_STEPS = 12
    MAX_TAKEOVER_RETURNS = 3

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
        """完成一次寄养；从任意已识别场景接管，成功或已寄养并回庭院才正常结束。"""
        self.on_run()
        try:
            frame = self._takeover()
            if self._outcome == "already_fostering":
                self._return_home()
                self._stage = "done"
                return
            if not self._panel(frame):
                frame = self._open_list(frame)
            self._foster(frame)
            self._return_home()
            self._stage = "done"
        except _Stopped:
            return
        except Exception:
            self._stage, self._outcome = "failed", "failed"
            raise

    def _classify(self, frame: np.ndarray) -> str | None:
        """识别当前画面；覆盖层优先，无法唯一确认时返回 None。"""
        if self._match(frame, "confirm") is not None:
            return "confirm"
        if self._panel(frame):
            return "panel"
        if self._match(frame, "growth") is not None:
            if self._fostering(frame):
                return "fostered"
            return ("growth_own" if self._match(frame, "foster_open") is not None
                    else "growth_friend")
        if self._match(frame, "growth_entry") is not None:
            return "realm_own"
        if self._match(frame, "guild") is not None:
            return "guild"
        if self._match(frame, "home") is not None:
            return "home"
        return None

    def _takeover(self) -> np.ndarray:
        """从当前画面推进到本人育成页或寄养面板，不假定前序步骤已执行。"""
        returns = 0
        for _ in range(self.MAX_TAKEOVER_STEPS):
            frame = self._read()
            scene = self._classify(frame)
            self.logger.info(f"[FOSTER_TAKEOVER] 场景={scene} 已返回={returns}")
            if scene in ("panel", "growth_own"):
                return frame
            if scene == "fostered":
                self._outcome = "already_fostering"
                return frame
            if scene == "confirm":
                self._cancel_confirm(frame)
                continue
            if scene == "home":
                frame = self._open_home_menu(frame)
                point = self._required(frame, "home_menu")
                self.logger.info(f"[FOSTER_ENTRY] 阴阳寮入口={point}")
                self._click(point)
                self._wait_guild()
                continue
            if scene == "guild":
                self._click(self._required(frame, "guild"))
                frame = self._wait(lambda f: self._match(f, "growth_entry") is not None)
                self._click(self._required(frame, "growth_entry"))
                self._wait(lambda f: self._match(f, "growth") is not None)
                continue
            if scene == "realm_own":
                self._click(self._required(frame, "growth_entry"))
                self._wait(lambda f: self._match(f, "growth") is not None)
                continue
            # 好友育成页与未分类页面：只沿已识别返回箭头逐级回退，次数有界。
            point = self._match(frame, "return")
            if point is not None and returns < self.MAX_TAKEOVER_RETURNS:
                returns += 1
                self.logger.info(
                    f"[FOSTER_TAKEOVER] 逐级返回 {returns}/{self.MAX_TAKEOVER_RETURNS}"
                )
                self._click(point)
                self._wait_stable()
                continue
            raise RuntimeError(f"[FOSTER_TAKEOVER] 无法从当前画面安全接管：{scene}")
        raise RuntimeError("[FOSTER_TAKEOVER] 接管步数超出预算")

    def _open_home_menu(self, frame: np.ndarray) -> np.ndarray:
        """展开庭院菜单；菜单已展开时直接复用当前帧。"""
        if self._match(frame, "home_menu") is not None:
            return frame
        from yys.common.lineup import LineupSwitcher

        self.logger.info("[FOSTER_ENTRY] 未识别到阴阳寮图标，先点菜单展开按钮")
        expand_point = LineupSwitcher(
            self._env, ocr=self.ocr,
        ).home_menu_expand_point(frame, home_verified=True)
        if expand_point is None:
            raise RuntimeError("[FOSTER_ENTRY] 未确认庭院菜单展开按钮")
        self.logger.info(f"[FOSTER_ENTRY] 菜单展开按钮={expand_point}")
        self._click(expand_point)
        return self._wait(lambda f: self._match(f, "home_menu") is not None)

    def _cancel_confirm(self, frame: np.ndarray) -> None:
        """按 D1 取消来源不明的确认框；只发送一次，等待弹窗消失。"""
        point = self._required(frame, "cancel_button")
        self.logger.info(f"[FOSTER_CANCEL] 取消确认框={point}")
        self._click(point)
        self._wait(lambda f: self._match(f, "confirm") is None)

    def _open_list(self, frame: np.ndarray) -> np.ndarray:
        """从本人育成页打开寄养面板。"""
        self._click(self._required(frame, "foster_open"))
        return self._wait(self._panel)

    def _foster(self, frame: np.ndarray) -> None:
        """扫描两个列表、复验候选并确认寄养；已寄养时只记录结果。"""
        if self._fostering(frame):
            self._outcome = "already_fostering"
            return
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

    def _wait_stable(self) -> np.ndarray:
        """连续两次读到同一场景才认为转场稳定，避免对过渡帧重复输入。"""
        deadline = time.monotonic() + 12
        previous: tuple[str | None, bool] | None = None
        while time.monotonic() < deadline:
            frame = self._read()
            signature = (self._classify(frame), self._match(frame, "return") is not None)
            if signature == previous and (signature[0] is not None or signature[1]):
                return frame
            previous = signature
            self._stop_threading_event.wait(0.3)
        raise RuntimeError("[FOSTER_TRANSITION] 寄养页面转场未确认，未重复输入")

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
        """点击逻辑坐标，并记录实际落点用于复现误点。"""
        self._check()
        clicked = self._point(point)
        self.logger.info(
            f"[FOSTER_CLICK] 阶段={self._stage} 逻辑坐标={point} 实际坐标={clicked}"
        )
        self._env.left_click(*clicked)
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
            # 旧版与 2026-10-24 实机新版结界按钮外观不同，逐个尝试已知变体。
            for alternative in ("guild_live", "guild_v2"):
                current = self._match(frame, alternative)
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
            self._log_miss(name, result.similarity, result.point)
            return None
        template = cv2.imread(str(path))
        h, w = template.shape[:2]
        x, y = result.point
        patch = frame[y - h // 2:y - h // 2 + h, x - w // 2:x - w // 2 + w]
        difference = (float("inf") if patch.shape != template.shape
                      else float(cv2.absdiff(patch, template).mean()))
        if difference > 22:
            self.logger.debug(
                f"[FOSTER_MATCH] {name} 相似度={result.similarity:.3f} 但像素差={difference:.1f} "
                f"超限 候选={result.point}"
            )
            return None
        self.logger.debug(
            f"[FOSTER_MATCH] {name} 命中 相似度={result.similarity:.3f} 坐标={result.point} "
            f"像素差={difference:.1f}"
        )
        return result.point

    def _log_miss(self, name: str, similarity: float, point: tuple[int, int]) -> None:
        """限流记录未命中候选，避免等待页面时每轮重复刷屏。"""
        misses: dict[str, float] = self.__dict__.setdefault("_match_misses", {})
        previous = misses.get(name)
        if similarity >= 0.70 and (previous is None or abs(previous - similarity) >= 0.05):
            misses[name] = similarity
            self.logger.debug(
                f"[FOSTER_MATCH] {name} 未命中 相似度={similarity:.3f} 最佳候选={point}"
            )

    def _required(self, frame: np.ndarray, name: str) -> tuple[int, int]:
        point = self._match(frame, name)
        if point is None:
            raise RuntimeError(f"[FOSTER_TARGET] 未确认寄养控件：{name}")
        return point

    def _wait(self, predicate: Callable[[np.ndarray], bool]) -> np.ndarray:
        """等待目标页面；出现任何非预期弹窗时先点掉关闭按钮。"""
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            frame = self._read()
            close = self._match(frame, "popup_close")
            if close is not None and self._close_popup(close):
                continue
            known = predicate(frame)
            if self._run_guard is not None:
                self._run_guard.note_iteration(known)
            if known:
                return frame
            self._stop_threading_event.wait(0.2)
        raise RuntimeError("[FOSTER_TRANSITION] 寄养页面转场未确认，未重复输入")

    def _close_popup(self, point: tuple[int, int]) -> bool:
        """点掉意外弹窗的关闭按钮；同一位置最多点两次，避免关闭失败时空点。"""
        attempts: dict[tuple[int, int], int] = self.__dict__.setdefault(
            "_popup_close_attempts", {}
        )
        count = attempts.get(point, 0)
        if count >= 2:
            return False
        attempts[point] = count + 1
        self.logger.info(f"[FOSTER_POPUP] 识别到弹窗关闭按钮={point}，先关闭")
        self._click(point)
        self._stop_threading_event.wait(0.4)
        return True

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
        """逐级返回庭院；只点击已识别的返回控件，每次重新分类。"""
        self._stage = "returning_home"
        for _ in range(6):
            frame = self._read()
            if self._classify(frame) == "home":
                return
            point = self._match(frame, "to_home") or self._match(frame, "return")
            if point is None:
                frame = self._wait_stable()
                if self._classify(frame) == "home":
                    return
                point = self._match(frame, "to_home") or self._match(frame, "return")
                if point is None:
                    raise RuntimeError("[FOSTER_RETURN] 未确认可安全返回的页面")
            self._click(point)
            self._wait_stable()
        if self._classify(self._read()) != "home":
            raise RuntimeError("[FOSTER_RETURN] 寄养后未确认回到庭院")
