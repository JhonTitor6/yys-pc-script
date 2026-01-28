import random
import time

from loguru import logger

from yys.common_util import find_window, bg_find_pic, bg_left_click_with_range, random_sleep, try_handle_battle_end
from yys.log_manager import get_logger

"""
鬼兵演武
"""

hwnd = find_window()
# 获取日志记录器
logger = get_logger("guibingyanwu")


def click_tiaozhan():
    point = bg_find_pic(hwnd, "yys/images/guibingyanwu_tiaozhan.png")
    return bg_left_click_with_range(hwnd, point, x_range=20, y_range=20)


def main():
    max_battle_count = 50
    cur_battle_count = 0
    next_sleep_counter = 0
    next_sleep_threshold = random.randint(40, 60)
    while cur_battle_count < max_battle_count:
        click_tiaozhan()
        if try_handle_battle_end(hwnd):
            cur_battle_count += 1
            next_sleep_counter += 1
            logger.success(f"通关次数：{cur_battle_count}")
        random_sleep(1, 2.5)

        # 防封逻辑，打一定场数后，随机休息一段时间
        if next_sleep_counter >= next_sleep_threshold:
            next_sleep_counter = 0
            sleep_duration = random.uniform(30, 60)
            logger.info(f"已完成 {cur_battle_count} 场战斗，随机休息 {sleep_duration:.1f} 秒")
            time.sleep(sleep_duration)
            next_sleep_threshold = random.randint(40, 60)


if __name__ == '__main__':
    main()