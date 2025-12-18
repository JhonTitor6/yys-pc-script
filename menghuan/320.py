import time

from common_util import *
from pic_and_color_util import *
from my_mouse import *

hwnd = find_window()

def main():
    while True:
        bg_find_pic_and_click(hwnd, "images/task_close.bmp")
        bg_find_pic_and_click(hwnd, "images/team_close.bmp")
        if bg_find_pic_and_click(hwnd, "images/320_skip_ju_qing.bmp", similarity=0.7):
            time.sleep(random.uniform(1, 2))
            click_task()
        if bg_find_pic_and_click(hwnd, "images/320_click_to_continue.bmp", similarity=0.7):
            time.sleep(15)
            click_task()
        if bg_find_pic_and_click(hwnd, "images/320_task_zhan.bmp", similarity=0.7):
            time.sleep(5)
        bg_find_pic_and_click(hwnd, "images/320_dui_hua.bmp", x0=1130, x1=1510, y0=520, y1=700)
        time.sleep(1)


def click_task():
    bg_left_click(hwnd, random.randint(1380, 1390), random.randint(225, 230))
    point = bg_find_pic_with_timeout(hwnd, "images/320_dui_hua.bmp", timeout=7)
    if point is not None and point != (-1, -1):
        bg_left_click(hwnd, point)


if __name__ == '__main__':
    main()