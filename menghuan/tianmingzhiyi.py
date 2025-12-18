import time

from common_util import *
from my_mouse import *
from pic_and_color_util import *
import config as config
"""
天命之弈
"""
config.DEBUG = True
hwnd = find_window()


def click_ready():
    return bg_find_pic_and_click(hwnd, "images/tianming_ready.bmp")


def click_quit():
    return bg_find_pic_and_click(hwnd, "images/tianming_quit.bmp")


def main():
    while True:
        click_ready()
        time.sleep(1)


if __name__ == '__main__':
    main()
