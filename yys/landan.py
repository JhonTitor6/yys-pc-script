from common_util import *


def main():
    hwnd = find_window()
    count = 0
    while (True):
        # 点击继续养成
        bg_left_click_with_range(hwnd, (629, 549))
        random_sleep(0.3, 0.7)
        # 点击确认
        if bg_left_click_with_range(hwnd, (782, 580)):
            count += 1
            logger.success(f"已完成{count}次")
        random_sleep(2.5, 3)


if __name__ == '__main__':
    main()
