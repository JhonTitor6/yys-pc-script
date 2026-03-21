import time
import unittest

import cv2
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
            img = cv2.imread("yys/images/debug/source/test.bmp")
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
