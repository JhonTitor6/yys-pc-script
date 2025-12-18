import unittest
from yys.common_util import find_window
from pic_and_color_util import *
from win_util import ocr


class TestYYS(unittest.TestCase):
    def setUp(self):
        super().__init__()
        self.hwnd = find_window()
        self.yys_ocr = ocr.YysOCR(self.hwnd)

    def test_ocr(self):
        start = int(time.time() * 1000)

        result, img = self.yys_ocr.ocr(capture_window_region(self.hwnd, 555, 176, 825, 324))
        print(int(time.time() * 1000) - start)
        print(result)

    def test_yuhun(self):
        while True:
            result, img = self.yys_ocr.ocr(capture_window_region(self.hwnd, 555, 176, 825, 324))
            result_img, results, total_score = self.yys_ocr.calc_score(result, img)

            # 显示结果（可选）
            cv2.imshow("Score", result_img)
            cv2.setWindowProperty("Score", cv2.WND_PROP_TOPMOST, 1)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cv2.destroyAllWindows()