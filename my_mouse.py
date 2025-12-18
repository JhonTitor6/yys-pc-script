import win32api
import win32con
import random
from loguru import logger


def left_click(*position):
    """
    模拟鼠标左键点击（自动处理浮点数坐标）
    :param x: 点击的x坐标（支持int/float）
    :param y: 点击的y坐标（支持int/float）
    :param delay: 点击后的延迟时间(秒)
    """
    if position is None or (len(position) == 1 and position[0] is None):
        return False

    # 解析坐标参数
    if len(position) == 1 and isinstance(position[0], (tuple, list)):
        # 传入的是元组/列表形式 (x,y)
        x, y = position[0]
    elif len(position) == 2:
        # 传入的是x,y两个参数
        x, y = position
    else:
        raise ValueError("坐标参数格式错误，请使用(x,y)或x,y两种形式")

    # 确保坐标为整数
    x_pos = int(round(x))
    y_pos = int(round(y))

    win32api.SetCursorPos((x_pos, y_pos))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x_pos, y_pos, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x_pos, y_pos, 0, 0)

    return True


def bg_left_click(hwnd, *point):
    """
        后台模拟鼠标左键点击

        支持两种传参方式：
        1. 传入x和y坐标：bg_left_click(hwnd, x, y)
        2. 传入坐标元组：bg_left_click(hwnd, (x, y))

        :param hwnd: 窗口句柄
        :param point: 坐标参数，可以是(x, y)或单独的x,y
        :return: 操作是否成功
        """
    if point is None or (len(point) == 1 and point[0] is None):
        return False

    # 解析坐标参数
    if len(point) == 1 and isinstance(point[0], (tuple, list)):
        # 传入的是元组/列表形式 (x,y)
        x, y = point[0]
    elif len(point) == 2:
        # 传入的是x,y两个参数
        x, y = point
    else:
        raise ValueError("坐标参数格式错误，请使用(x,y)或x,y两种形式")

    # 确保坐标为整数
    x_pos = int(round(x))
    y_pos = int(round(y))

    if x_pos < 0 or y_pos < 0:
        return False

    long_position = win32api.MAKELONG(x_pos, y_pos)  # 模拟鼠标指针 传送到指定坐标
    win32api.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, long_position)  # 模拟鼠标按下
    win32api.SendMessage(hwnd, win32con.WM_LBUTTONUP, win32con.MK_LBUTTON, long_position)  # 模拟鼠标弹起

    return True


def bg_left_click_with_range(hwnd, point, x_range=20, y_range=20):
    """
    在指定点周围随机范围内左键点击

    参数:
        hwnd: 窗口句柄
        point: 基准点坐标 (x, y)
        range: 随机范围半径（默认10像素）
    """
    if point and point != (-1, -1):
        x = random.randint(point[0] - x_range, point[0] + x_range)
        y = random.randint(point[1] - y_range, point[1] + y_range)
        logger.debug(f"在基准点 {point} 周围随机点击: x={x}, y={y}")
        return bg_left_click(hwnd, x, y)
    return False
