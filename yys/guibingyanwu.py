from yys.common_util import *
from loguru import logger

from yys.common_util import get_max_battle_count

"""
鬼兵演武
"""

hwnd = find_window()
# 配置loguru日志
logger.add(
    "logs/guibingyanwu/{time:YYYY-MM-DD}.log",  # 按日期分割日志文件
    rotation="00:00",  # 每天午夜创建新日志
    retention="7 days",  # 保留7天日志
    encoding="utf-8",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
)


def click_tiaozhan():
    point = bg_find_pic(hwnd, "images/guibingyanwu_tiaozhan.png")
    return bg_left_click_with_range(hwnd, point, x_range=20, y_range=20)


def main():
    max_battle_count = get_max_battle_count()
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
    do_script_end()


if __name__ == '__main__':
    main()
