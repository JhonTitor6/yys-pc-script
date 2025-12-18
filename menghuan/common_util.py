import win32con
import win32gui
from loguru import logger


def find_window(title_part="梦幻西游：时空"):
    """查找游戏窗口"""
    global hwnd
    hwnd = win32gui.FindWindow(None, title_part)
    if not hwnd:
        logger.error("未找到游戏窗口")
        raise Exception("未找到游戏窗口")

    # 设置窗口大小
    win32gui.SetWindowPos(hwnd, None, 0, 0, 1520, 855, win32con.SWP_SHOWWINDOW | win32con.SWP_NOMOVE)

    # 获取客户区大小
    _, _, width, height = win32gui.GetClientRect(hwnd)
    global client_rect
    client_rect = (0, 0, width, height)

    logger.info(f"窗口句柄: {hwnd}, 客户区大小: {width}x{height}")
    return hwnd


def find_windows(class_name=None, window_title=None):
    """
    查找所有匹配类名和/或窗口标题的窗口

    Args:
        class_name: 窗口类名
        window_title: 窗口标题（支持部分匹配）

    Returns:
        list: 包含(hwnd, 类名, 标题)的元组列表
    """
    windows = []

    def enum_window_proc(hwnd, extra):
        # 检查窗口是否可见
        if not win32gui.IsWindowVisible(hwnd):
            return True

        # 获取类名和标题
        current_class = win32gui.GetClassName(hwnd)
        current_title = win32gui.GetWindowText(hwnd)

        # 匹配条件
        class_match = class_name is None or current_class == class_name
        title_match = window_title is None or window_title in current_title

        if class_match and title_match:
            windows.append((hwnd, current_class, current_title))
        return True

    win32gui.EnumWindows(enum_window_proc, None)
    return windows


if __name__ == '__main__':
    res = find_windows(window_title="梦幻西游：时空")
    print(res)