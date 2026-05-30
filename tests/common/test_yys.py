import time
import unittest
from typing import Any

import cv2
from pytest import MonkeyPatch
import win32con
import win32gui


class TestYYS(unittest.TestCase):
    def setUp(self):
        super().__init__()
        # self.hwnd = find_window()
        # self.yys_ocr = YysYuHunOCR()
        # self.image_finder = ImageFinder(self.hwnd)

    def test_find_window(self, title_part="阴阳师-网易游戏") -> int:
        """查找游戏窗口"""
        global hwnd
        hwnd = win32gui.FindWindow(None, title_part)
        if not hwnd:
            raise Exception("未找到游戏窗口")

        # 设置窗口大小
        win32gui.SetWindowPos(hwnd, None, 0, 0, 1154, 680, win32con.SWP_NOMOVE)

        # 获取客户区大小
        _, _, width, height = win32gui.GetClientRect(hwnd)

        print(f"窗口句柄: {hwnd}, 客户区大小: {width}x{height}")

    def test_ocr(self):
        start = int(time.time() * 1000)
        while True:
            # img = capture_window_region(self.hwnd, 260, 119, 858, 285)
            img = cv2.imread("tests/common/images/test.bmp")
            result = self.yys_ocr.ocr(img)
            print(int(time.time() * 1000) - start)
            print(result)
            time.sleep(1)
            break

    def test_yuhun(self):
        while True:
            img = self.image_finder.update_screenshot_cache()
            result = self.yys_ocr.ocr(img)
            result_img, results, total_score = self.yys_ocr.calc_score(result, img)

            # 显示结果（可选）
            cv2.imshow("Score", result_img)
            cv2.setWindowProperty("Score", cv2.WND_PROP_TOPMOST, 1)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cv2.destroyAllWindows()


def test_base_script_state_snapshot(mock_env: object, monkeypatch: MonkeyPatch) -> None:
    import win_util.controller as controller
    from yys.soul_raid.soul_raid_script import SoulRaidScript

    fake_ocr_init_count = 0

    class FakeCommonOcr:
        """轻量 OCR 替身，避免状态快照测试初始化真实 OCR。"""

        def __init__(self) -> None:
            nonlocal fake_ocr_init_count
            fake_ocr_init_count += 1

        def ocr(self, img: Any) -> list[Any]:
            """返回空 OCR 结果。"""
            return []

        def contains_text(self, img: Any, target_text: str, case_sensitive: bool = False) -> bool:
            """判断图片中是否包含文本。"""
            return False

        def find_text_position(
            self,
            img: Any,
            target_text: str,
            similarity_threshold: float = 0.3,
            case_sensitive: bool = False,
        ) -> None:
            """查找文本位置。"""
            return None

        def find_text_positions(
            self,
            img: Any,
            target_text: str,
            similarity_threshold: float = 0.3,
            case_sensitive: bool = False,
        ) -> list[Any]:
            """查找所有文本位置。"""
            return []

    monkeypatch.setattr(controller, "CommonOcr", FakeCommonOcr)

    script = SoulRaidScript(env=mock_env)
    script.set_max_battle_count(10)
    script._cur_battle_count = 3
    script._cur_battle_victory_count = 2

    snapshot = script.get_state_snapshot()

    assert fake_ocr_init_count == 1
    assert snapshot["script_name"] == "soul_raid"
    assert snapshot["battle_count"] == 3
    assert snapshot["victory_count"] == 2
    assert snapshot["max_battle_count"] == 10
