from menghuan.common_util import find_window
from pic_and_color_util import *
from menghuan.log_config import init
import config

'''
挖宝
'''

config.DEBUG = True

def click_use(hwnd):
    return bg_find_pic_and_click(hwnd, "images/use.bmp", similarity=0.7)


def click_team_close(hwnd):
    """点击队伍关闭按钮"""
    return bg_find_pic_and_click(hwnd, "images/team_close.bmp", 1000, 100, 1300, 300, 0.7)

def main():
    init()
    hwnd = find_window()
    while True:
        click_team_close(hwnd)
        time.sleep(1)
        click_use(hwnd)


if __name__ == '__main__':
    main()
