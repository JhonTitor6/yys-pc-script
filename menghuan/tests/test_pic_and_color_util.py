import unittest

import config
from menghuan.common_util import find_window
from pic_and_color_util import *
from win_util import *
import menghuan.zhuogui


class TestPicAndColorUtil(unittest.TestCase):
    def test_bg_find_pic(self):
        config.DEBUG = True
        res = bg_find_pic(852064, 0, 0, 1920, 1080, r'../images/test2.bmp', 0.7)
        print(res)
        self.assertTrue(res is not None)
        self.assertTrue(res != (-1, -1))

    def test_bg_find_color(self):
        config.DEBUG = True
        hwnd = find_window(window_name="梦幻西游：时空")
        res = bg_get_pixel_color(hwnd, 1371, 112)
        print(res)

    def test_cv_match(self):
        search_img = cv2.imread("images/continue_ghost_hunting_or_not.bmp")
        template = cv2.imread("images/continue_ghost_hunting_or_not.bmp")
        cv2.matchTemplate(search_img, template, cv2.TM_CCOEFF_NORMED)