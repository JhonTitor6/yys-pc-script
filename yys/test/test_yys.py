import time
import unittest

import cv2

from win_util.image import ImageFinder
from yys.common_util import find_window
from yys.util.yys_yu_hun_ocr import YysYuHunOCR


class TestYYS(unittest.TestCase):
    def setUp(self):
        super().__init__()
        self.hwnd = find_window()
        self.yys_ocr = YysYuHunOCR()
        self.image_finder = ImageFinder(self.hwnd)

    def test_ocr(self):
        start = int(time.time() * 1000)
        while True:
            # img = capture_window_region(self.hwnd, 260, 119, 858, 285)
            img = cv2.imread("images/debug/source/test.bmp")
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
