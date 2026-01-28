import random
import time

from loguru import logger

from yys.common_util import find_window, bg_find_pic, bg_left_click_with_range, try_handle_battle_end
from yys.log_manager import get_logger

"""
业原火
"""

hwnd = find_window()
# 获取日志记录器
logger = get_logger("yeyuanhuo")


def click_tiaozhan():
    point = bg_find_pic(hwnd, "yys/images/yeyuanhuo_tiaozhan.bmp", similarity=0.7)
    bg_left_click_with_range(hwnd, point, x_range=20, y_range=20)


def main():
    max_battle_count = 100
    cur_battle_count = 0
    while cur_battle_count < max_battle_count:
        click_tiaozhan()
        if try_handle_battle_end(hwnd):
            cur_battle_count += 1
            logger.success(f"通关次数：{cur_battle_count}")
        time.sleep(random.randint(1, 3))


if __name__ == '__main__':
    main()
