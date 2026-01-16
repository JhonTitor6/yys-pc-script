from yys.common_util import *
from loguru import logger

"""
觉醒材料
"""

hwnd = find_window()
# 配置loguru日志
logger.add(
    "logs/juexingcailiao/{time:YYYY-MM-DD}.log",  # 按日期分割日志文件
    rotation="00:00",  # 每天午夜创建新日志
    retention="7 days",  # 保留7天日志
    encoding="utf-8",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
)


def click_tiaozhan():
    point = bg_find_pic(hwnd, "images/juexing_tiaozhan.bmp", similarity=0.7)
    bg_left_click_with_range(hwnd, point, x_range=10, y_range=10)


def main():
    max_battle_count = input_max_battle_count()
    cur_battle_count = 0
    while cur_battle_count < max_battle_count:
        click_tiaozhan()
        if try_handle_battle_end(hwnd):
            cur_battle_count += 1
            logger.success(f"通关次数：{cur_battle_count}")
        time.sleep(random.randint(1, 3))

    do_script_end()


if __name__ == '__main__':
    main()
