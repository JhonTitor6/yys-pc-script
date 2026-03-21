import random
import time

from loguru import logger
from win_util.image import ImageFinder
from win_util.mouse import bg_left_click_with_range
from yys.event_script_base import find_window, random_sleep
from yys.log_manager import get_logger

"""
契灵探查
"""

hwnd = find_window()
# 获取日志记录器
logger = get_logger("qilingtancha")


def _bg_find_pic(hwnd, small_picture_path, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8):
    finder = ImageFinder(hwnd)
    finder.update_screenshot_cache()
    return finder.bg_find_pic_by_cache(small_picture_path, x0, y0, x1, y1, similarity)


def _try_handle_battle_end(hwnd):
    """处理战斗结束"""
    success_res = _click_battle_success_end(hwnd)
    if success_res:
        time.sleep(1)
    loss_res = _click_battle_end_loss(hwnd)
    _click_suipian(hwnd)
    reward_res = _click_battle_end_1(hwnd) or _click_battle_end_2(hwnd)
    return success_res or loss_res or reward_res, success_res


def _click_battle_success_end(hwnd):
    point = _bg_find_pic(hwnd, "yys/images/battle_end.bmp", similarity=0.8)
    first_click = bg_left_click_with_range(hwnd, point, x_range=200, y_range=50)
    if first_click:
        return first_click
    point = _bg_find_pic(hwnd, "yys/images/battle_end_success.bmp", similarity=0.8)
    second_click = bg_left_click_with_range(hwnd, point, x_range=200, y_range=50)
    return second_click


def _click_battle_end_loss(hwnd):
    point = _bg_find_pic(hwnd, "yys/images/battle_end_loss.bmp", similarity=0.8)
    first_click = bg_left_click_with_range(hwnd, point, x_range=200, y_range=50)
    if first_click:
        random_sleep(0.1, 0.3)
    second_click = bg_left_click_with_range(hwnd, point, x_range=200, y_range=50)
    return first_click or second_click


def _click_suipian(hwnd):
    point = _bg_find_pic(hwnd, "yys/images/suipian.png")
    click_success = bg_left_click_with_range(hwnd, point, x_range=100, y_range=100)
    if click_success:
        random_sleep(1.2, 1.7)
    return click_success


def _click_battle_end_1(hwnd):
    point = _bg_find_pic(hwnd, "yys/images/battle_end_1.bmp", similarity=0.7)
    if point is None or point == (-1, -1):
        return False
    time.sleep(2)
    click_res = bg_left_click_with_range(hwnd, point, x_range=300, y_range=50)
    return click_res


def _click_battle_end_2(hwnd):
    point = _bg_find_pic(hwnd, "yys/images/battle_end_2.bmp", similarity=0.7)
    if point is None or point == (-1, -1):
        return False
    click_res = bg_left_click_with_range(hwnd, point, x_range=300, y_range=50)
    return click_res


def click_tancha():
    point = _bg_find_pic(hwnd, "yys/qilingtancha/images/qiling_tancha.bmp", similarity=0.7)
    bg_left_click_with_range(hwnd, point, x_range=20, y_range=20)


def main():
    max_battle_count = 100
    cur_battle_count = 0
    while cur_battle_count < max_battle_count:
        click_tancha()
        if _try_handle_battle_end(hwnd):
            cur_battle_count += 1
            logger.success(f"通关次数：{cur_battle_count}")
        time.sleep(random.randint(1, 3))


if __name__ == '__main__':
    main()
