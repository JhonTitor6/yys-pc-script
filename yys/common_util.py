import random
import time

import win32gui
from loguru import logger

from win_util.image import ImageFinder
from win_util.mouse import bg_left_click_with_range


# TODO: 重构并删除common_util
def bg_find_pic(hwnd, small_picture_path, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8):
    finder = ImageFinder(hwnd)
    finder.update_screenshot_cache()
    return finder.bg_find_pic_by_cache(small_picture_path, x0, y0, x1, y1, similarity)

def bg_find_pic_with_timeout(hwnd, small_picture_path, timeout=5, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8):
    finder = ImageFinder(hwnd)
    finder.update_screenshot_cache()
    return finder.bg_find_pic_with_timeout(small_picture_path, timeout, x0, y0, x1, y1, similarity)


def find_window(title_part="阴阳师-网易游戏") -> int:
    """查找游戏窗口"""
    global hwnd
    hwnd = win32gui.FindWindow(None, title_part)
    if not hwnd:
        logger.error("未找到游戏窗口")
        raise Exception("未找到游戏窗口")

    # 设置窗口大小
    # win32gui.SetWindowPos(hwnd, None, 0, 0, 1136, 671, win32con.SWP_NOMOVE)

    # 获取客户区大小
    _, _, width, height = win32gui.GetClientRect(hwnd)
    global client_rect
    client_rect = (0, 0, width, height)

    logger.info(f"窗口句柄: {hwnd}, 客户区大小: {width}x{height}")
    return hwnd


def random_sleep(min, max):
    sleep_seconds = random.uniform(min, max)
    # logger.debug(f"等待{sleep_seconds}秒")
    time.sleep(sleep_seconds)


def try_handle_battle_end(hwnd):
    """
    :param hwnd:
    :return: handle_res, is_battle_victory
    """
    success_res = _click_battle_success_end(hwnd)
    if success_res:
        time.sleep(1)
    loss_res = _click_battle_end_loss(hwnd)
    _click_suipian(hwnd)
    reward_res = _click_battle_end_1(hwnd) or _click_battle_end_2(hwnd)
    return success_res or loss_res or reward_res, success_res


def _click_battle_success_end(hwnd):
    point = bg_find_pic(hwnd, "images/battle_end.bmp", similarity=0.8)
    first_click = bg_left_click_with_range(hwnd, point, x_range=200, y_range=50)
    if first_click:
        return first_click
    point = bg_find_pic(hwnd, "images/battle_end_success.bmp", similarity=0.8)
    second_click = bg_left_click_with_range(hwnd, point, x_range=200, y_range=50)
    return second_click


def _click_battle_end_loss(hwnd):
    point = bg_find_pic(hwnd, "images/battle_end_loss.bmp", similarity=0.8)
    first_click = bg_left_click_with_range(hwnd, point, x_range=200, y_range=50)
    if first_click:
        random_sleep(0.1, 0.3)
    second_click = bg_left_click_with_range(hwnd, point, x_range=200, y_range=50)
    return first_click or second_click


def _click_suipian(hwnd):
    point = bg_find_pic(hwnd, "images/suipian.png")
    click_success = bg_left_click_with_range(hwnd, point, x_range=100, y_range=100)
    if click_success:
        random_sleep(1.2, 1.7)
    return click_success


def _click_battle_end_1(hwnd):
    point = bg_find_pic(hwnd, "images/battle_end_1.bmp", similarity=0.7)
    if point is None or point == (-1, -1):
        return False
    time.sleep(2)
    click_res = bg_left_click_with_range(hwnd, point, x_range=300, y_range=50)
    return click_res


def _click_battle_end_2(hwnd):
    point = bg_find_pic(hwnd, "images/battle_end_2.bmp", similarity=0.7)
    if point is None or point == (-1, -1):
        return False
    click_res = bg_left_click_with_range(hwnd, point, x_range=300, y_range=50)
    return click_res


def try_bg_click_pic_with_timeout(hwnd, template_image_path, timeout=3, x0=0, y0=0, x1=99999, y1=99999,
                                  similarity=0.8, x_range=20, y_range=20):
    """
    找图并点击，点击时以图片为中心点进行偏移随机
    """
    point = bg_find_pic_with_timeout(hwnd, template_image_path, x0=x0, y0=y0, x1=x1, y1=y1, timeout=timeout,
                                     similarity=similarity)
    return bg_left_click_with_range(hwnd, point, x_range=x_range, y_range=y_range)


def close_jia_cheng(hwnd):
    point = bg_find_pic(hwnd, "images/jia_cheng.bmp")
    if not bg_left_click_with_range(hwnd, point, x_range=10, y_range=10):
        return False
    random_sleep(0.5, 0.8)
    success_close_count = 0
    loop_count = 0
    while loop_count < 30 and success_close_count < 2:
        loop_count += 1
        point = bg_find_pic(hwnd, "images/jia_cheng_ji_huo_zhong.bmp", similarity=0.9)
        if bg_left_click_with_range(hwnd, point, x_range=6, y_range=8):
            success_close_count += 1
        random_sleep(0.1, 0.3)
    return True
