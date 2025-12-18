import unittest
from menghuan.zhuogui import *

config.DEBUG = True


class TestZhuogui(unittest.TestCase):
    def test_click(self):
        check_team_offline(196746)

    def test_click_zhong_kui(self):
        for i in range(5):
            similarity = 0.9 - i * 0.1
            print(similarity)
            res = click_zhong_kui(657662, similarity)
            print(res)

    def test_go_to_zhuo_gui_task(self):
        hwnd = find_window()
        self.assertTrue(go_to_zhuo_gui_task(hwnd))
