import unittest
from my_mouse import *
from pic_and_color_util import *
from win_util import *


class TestMyMouse(unittest.TestCase):
    def test_click(self):
        hwnd = find_window(window_name="梦幻西游：时空")
        bg_left_click(hwnd, 1371, 112)