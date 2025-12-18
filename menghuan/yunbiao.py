from common_util import *
from pic_and_color_util import *


def click_yun_biao(hwnd):
    return bg_find_pic_and_click(hwnd, "images/yun_biao.bmp") or bg_find_pic_and_click(hwnd, "images/yun_biao2.bmp")


def main():
    logger.info("开始运行")
    windows = find_windows(window_title="梦幻西游：时空")
    logger.info(windows)
    while True:
        for window in windows:
            hwnd, class_name, window_title = window
            if click_yun_biao(hwnd):
                time.sleep(1)
            bg_find_pic_and_click(hwnd, "images/confirm.bmp", similarity=0.8)
            bg_find_pic_and_click(hwnd, "images/mijing_jin_ru_zhan_dou.bmp", similarity=0.8)
        time.sleep(0.2)


if __name__ == '__main__':
    main()