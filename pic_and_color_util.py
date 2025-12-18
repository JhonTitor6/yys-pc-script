import os
import os.path
import time
from pathlib import Path
from ctypes import windll

import aircv
import cv2
import mss
import numpy as np
import win32gui
import win32ui
from PIL import ImageGrab

from rgb_hex import *
import my_mouse
from loguru import logger
import config
from typing import List

m = mss.mss()
# 创建调试目录
debug_img_base_dir = Path("images/debug")


def get_pixel_color(x, y):
    '''
    获取指定点的颜色 十六进制FFFFFF str
    :param x: 指定点的横向坐标 int
    :param y: 指定点的纵向坐标 int
    :return: 十六进制FFFFFF str
    '''
    gdi32 = windll.gdi32
    user32 = windll.user32
    hdc = user32.GetDC(None)  # 获取颜色值
    pixel = gdi32.GetPixel(hdc, x, y)  # 提取RGB值
    r = pixel & 0x0000ff
    g = (pixel & 0x00ff00) >> 8
    b = pixel >> 16
    return rgb2hex((r, g, b)).upper()


def find_color(x0, y0, x1, y1, color_hex):
    '''
    0,0,1024,768,"0000FF"
    :param x0: 找色区域左上角x坐标 int
    :param y0: 找色区域左上角y坐标 int
    :param x1: 找色区域右下角x坐标 int
    :param y1: 找色区域右下角y坐标 int
    :param color_hex:"0000FF"
    :return: (0,100) |(-1,-1)
    '''
    color = hex2rgb(color_hex)
    img = pil2np(ImageGrab.grab((x0, y0, x1, y1)))
    for i in range(img.shape[0]):
        for j in range(img.shape[1]):
            if tuple(img[i, j]) == color:
                return x0 + j, y0 + i
    logger.debug("没找到point")
    return -1, -1


def bg_get_pixel_color(hwnd, x, y):
    """
    获取指定窗口客户区中某个像素点的颜色（BBGGRR 格式）

    参数:
        hwnd: 目标窗口句柄
        x, y: 客户区坐标

    返回:
        成功时返回颜色字符串 "BBGGRR"（不带 #）
        失败时返回 None
    """
    try:
        # 获取窗口区域图像（只捕获目标像素点周围 1x1 的区域）
        img, offset_x, offset_y = capture_window_region(hwnd, x, y, x + 1, y + 1)

        # 获取像素颜色（OpenCV 默认 BGR 格式）
        b, g, r = img[0, 0][:3]  # 只取前3个通道（BGR）

        # 格式化为 "BBGGRR"（不带 #）
        bgr_hex = f"{b:02X}{g:02X}{r:02X}"
        return bgr_hex
    except Exception as e:
        logger.exception(f"获取像素颜色失败: {e}")
        return None


def bg_check_pixel_color(hwnd, x, y, expected_color_bgr, similarity=1.0):
    """
    检查指定窗口客户区中某个像素点的颜色是否符合预期（BBGGRR 格式）

    参数:
        hwnd: 目标窗口句柄
        x, y: 客户区坐标
        expected_color_bgr: 预期的颜色值，格式为 "BBGGRR"（不带 #）
        similarity: 颜色相似度 (0~1)，1表示完全匹配

    返回:
        如果颜色匹配返回 True
        否则返回 False
    """
    actual_color = bg_get_pixel_color(hwnd, x, y)
    if not actual_color:
        return False

    # 解析 BBGGRR 颜色

    expected_bgr = hex2rgb(expected_color_bgr)
    actual_bgr = hex2rgb(actual_color)

    # 计算颜色差异（欧几里得距离）
    diff = sum((e - a) ** 2 for e, a in zip(expected_bgr, actual_bgr)) ** 0.5
    max_diff = (3 * (255 ** 2)) ** 0.5  # 最大可能差异

    # 计算相似度 (0~1)
    actual_similarity = 1 - (diff / max_diff)

    return actual_similarity >= similarity


def find_multiple_colors(x0, y0, x1, y1, color_list, similarity=0.8):
    """
    在指定区域内查找多个颜色，支持近似匹配，并返回第一个找到的坐标
    :param x0: 区域左上角x坐标 int
    :param y0: 区域左上角y坐标 int
    :param x1: 区域右下角x坐标 int
    :param y1: 区域右下角y坐标 int
    :param color_list: 颜色列表，格式为 [(dx, dy, (r, g, b)), ...]
    :param similarity: 相似度，0~1之间的小数，默认0.9
    :return: 如果找到则返回第一个匹配的颜色坐标 (x, y)，否则返回 (-1, -1)
    """
    img = ImageGrab.grab((x0, y0, x1, y1))
    img_np = np.array(img)

    max_distance = np.sqrt(3 * (255 ** 2))  # 最大可能的颜色距离
    threshold = max_distance * (1 - similarity)  # 根据相似度计算实际阈值

    for dx, dy, target_color in color_list:
        if dy >= img_np.shape[0] or dx >= img_np.shape[1]:
            continue  # 跳过超出图像范围的点

        pixel_color = img_np[dy, dx]
        distance = np.linalg.norm(pixel_color - np.array(target_color))

        if distance <= threshold:
            return x0 + dx, y0 + dy  # 返回全局坐标

    return -1, -1


def find_pic(x0, y0, x1, y1, small_picture_path, similarity=0.8):
    '''
    区域找图
    :param x0: 找色区域左上角x坐标 int
    :param y0: 找色区域左上角y坐标 int
    :param x1: 找色区域右下角x坐标 int
    :param y1: 找色区域右下角y坐标 int
    :param small_picture_path:目标小图的路径
    :param similarity:相似度,0.95
    :return: (0,100) |(-1,-1)
    '''
    if not os.path.exists(small_picture_path):
        return None
    big = ImageGrab.grab((x0, y0, x1, y1))
    small = cv2.imread(small_picture_path)
    res = aircv.find_template(pil2np(big), small, similarity)
    # {'result': (430.0, 30.5), 'rectangle': ((420, 19), (420, 42), (440, 19), (440, 42)), 'confidence': 1.0}
    return res["result"] if res else (-1, -1)


def bg_find_pic_with_timeout(hwnd, small_picture_path, timeout=5, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8):
    start_time = time.time()
    while time.time() - start_time < timeout:
        point = bg_find_pic(hwnd, small_picture_path, x0, y0, x1, y1, similarity)
        if point is not None and point[0] != -1 and point[1] != -1:
            return point
        time.sleep(0.2)
    return (-1, -1)


def bg_find_pic(hwnd, small_picture_path, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8):
    """
    在指定窗口的客户区范围内查找小图片（增强调试功能）

    参数:
        hwnd: 目标窗口句柄
        small_picture_path: 小图片文件路径
        x0, y0: 客户区搜索区域左上角坐标
        x1, y1: 客户区搜索区域右下角坐标
        similarity: 匹配相似度阈值 (0~1)

    返回:
        成功时返回 (匹配中心x, 匹配中心y)
        失败时返回 (-1, -1)
    """
    if not os.path.exists(small_picture_path):
        raise FileNotFoundError(f"模板图片不存在: {small_picture_path}")

    # 获取窗口区域图像
    search_img = capture_window_region(hwnd, x0, y0, x1, y1)

    # 读取模板图片
    template = cv2.imread(small_picture_path)
    if template is None:
        raise ValueError(f"无法读取模板图片: {small_picture_path}")

    # 模板匹配
    result = cv2.matchTemplate(search_img, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    # 计算中心坐标（相对于客户区）
    h, w = template.shape[:2]
    center_x = x0 + max_loc[0] + w // 2
    center_y = y0 + max_loc[1] + h // 2

    match = max_val >= similarity

    template_name = Path(small_picture_path).stem

    debug_val_threshold = 0.6
    # 调试模式处理
    if config.DEBUG and max_val >= debug_val_threshold:
        write_debug_img(center_x, center_y, h, match, max_loc, max_val, search_img, similarity, template_name, w)

    # 返回结果
    if match:
        if config.DEBUG:
            logger.debug(
            f"[{hwnd}]匹配成功: {template_name} | 位置: ({center_x}, {center_y}) | 相似度: {max_val:.4f} | 阈值: {similarity}")
        return center_x, center_y

    if max_val >= debug_val_threshold:
        if config.DEBUG:
            logger.debug(
                f"[{hwnd}]匹配失败: {template_name} | 位置: ({center_x}, {center_y}) | 相似度: {max_val:.4f} | 阈值: {similarity}")
    return -1, -1


def write_debug_img(center_x, center_y, h, match, max_loc, max_val, search_img, similarity, template_name, w):
    template_dir = debug_img_base_dir / template_name
    template_dir.mkdir(parents=True, exist_ok=True)
    debug_img = search_img.copy()
    border_size = 0
    # 如果图片太小则扩大画布（上下左右各加50像素）
    if debug_img.shape[0] < 100 or debug_img.shape[1] < 100:
        border_size = 50
        debug_img = cv2.copyMakeBorder(
            debug_img,
            top=border_size,
            bottom=border_size,
            left=border_size,
            right=100,  # 右侧多留空间显示文字
            borderType=cv2.BORDER_CONSTANT,
            value=(0, 0, 0))  # 黑色背景
    # 绘制匹配矩形
    cv2.rectangle(
        debug_img,
        (max_loc[0] + border_size, max_loc[1] + border_size),
        (max_loc[0] + border_size + w, max_loc[1] + border_size + h),
        (0, 255, 0),
        1
    )
    # 添加匹配信息
    match_text = f"{max_val:.2f}/{similarity}@({center_x},{center_y})"
    cv2.putText(
        debug_img,
        match_text,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 255, 255),
        1
    )
    # 保存调试图像
    # time_str = time.strftime("%Y%m%d_%H%M%S")
    result_img_prefix = match
    cv2.imwrite(str(template_dir / f"{result_img_prefix}_result.png"), debug_img)


def bg_find_pic_and_click(hwnd, small_picture_path, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8):
    point = bg_find_pic(hwnd, small_picture_path, x0, y0, x1, y1, similarity)
    if config.DEBUG and point is not None and point != (-1, -1):
        logger.success(f"[{hwnd}]点击{small_picture_path}，坐标{point}")
    return my_mouse.bg_left_click(hwnd, point)


class ImageMatchConfig:
    def __init__(self, target_image_path_list: List[str] | str, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8):
        self.target_image_path_list = (
            [target_image_path_list] if isinstance(target_image_path_list, str)
            else target_image_path_list
        )
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.similarity = similarity

    def __hash__(self):
        return hash(tuple(self.target_image_path_list))

    def __eq__(self, other):
        return self.target_image_path_list == other.target_image_path_list

    def __str__(self):
        return f"{self.target_image_path_list} {self.x0} {self.y0} {self.x1} {self.y1} {self.similarity}"


def bg_find_pic_by_config(screenshot, image_match_config: ImageMatchConfig):
    for target_image_path in image_match_config.target_image_path_list:
        point = bg_find_pic_in_screenshot(screenshot, target_image_path,
                                          image_match_config.x0, image_match_config.y0,
                                          image_match_config.x1, image_match_config.y1,
                                          image_match_config.similarity)
        if point is not None and point[0] != -1 and point[1] != -1:
            return point, target_image_path
    return (-1, -1), None


def bg_find_pic_in_screenshot(screenshot, small_picture_path, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8):
    """
    在缓存的截图中查找图片
    """
    if screenshot is None:
        return -1, -1

    if not os.path.exists(small_picture_path):
        raise FileNotFoundError(f"模板图片不存在: {small_picture_path}")

    # 裁剪搜索区域
    search_img = screenshot
    if x0 > 0 or y0 > 0 or x1 < 99999 or y1 < 99999:
        h, w = search_img.shape[:2]
        x1 = min(x1, w)
        y1 = min(y1, h)
        search_img = search_img[y0:y1, x0:x1]

    # 读取模板图片
    template = cv2.imread(small_picture_path)
    if template is None:
        raise ValueError(f"无法读取模板图片: {small_picture_path}")

    # 模板匹配
    result = cv2.matchTemplate(search_img, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    # 计算中心坐标
    h, w = template.shape[:2]
    center_x = x0 + max_loc[0] + w // 2
    center_y = y0 + max_loc[1] + h // 2

    template_name = Path(small_picture_path).stem
    match = max_val >= similarity
    # 调试模式处理
    if config.DEBUG and max_val >= 0.6:
        write_debug_img(center_x, center_y, h, match, max_loc, max_val, search_img, similarity, template_name, w)

    if match:
        if config.DEBUG:
            logger.debug(
                f"在截图中找到图片: {small_picture_path} | 位置: ({center_x}, {center_y}) | 相似度: {max_val:.4f}")
        return center_x, center_y

    return -1, -1


def capture_window_region(hwnd, x0=0, y0=0, x1=99999, y1=99999):
    """
    内部函数：捕获窗口指定区域的图像

    参数:
        hwnd: 窗口句柄
        x0, y0: 区域左上角坐标
        x1, y1: 区域右下角坐标

    返回:
        裁剪后的图像
    """
    # 获取窗口客户区大小，用于截图
    client_rect = win32gui.GetClientRect(hwnd)
    client_width = client_rect[2] - client_rect[0] + 8
    client_height = client_rect[3] - client_rect[1] + 31

    # 调整搜索区域不超过客户区范围，用于二次截图
    x0 = max(x0, client_rect[0]) + 8
    y0 = max(y0, client_rect[1]) + 31
    x1 = min(x1 + 8, client_width)
    y1 = min(y1 + 31, client_height)

    if x0 >= x1 or y0 >= y1:
        raise ValueError(f"无效区域: ({x0}, {y0}) - ({x1}, {y1})")

    # 获取窗口截图
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    save_bitmap = win32ui.CreateBitmap()
    save_bitmap.CreateCompatibleBitmap(mfc_dc, client_width, client_height)
    save_dc.SelectObject(save_bitmap)

    # 截图时考虑窗口边框偏移（Windows 10+通常为8,31）
    # save_dc.BitBlt((0, 0), (client_width, client_height), mfc_dc, (8, 31), win32con.SRCCOPY)
    # 阴阳师不支持BitBlt，改用PrintWindow
    windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

    # 将位图转换为OpenCV格式
    bmp_info = save_bitmap.GetInfo()
    bmp_str = save_bitmap.GetBitmapBits(True)
    img = np.frombuffer(bmp_str, dtype='uint8')
    img.shape = (bmp_info['bmHeight'], bmp_info['bmWidth'], 4)

    # 清理资源
    win32gui.DeleteObject(save_bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)

    img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    # 裁剪指定区域
    search_img = img_bgr[y0:y1, x0:x1]

    if config.DEBUG:
        source_dir = debug_img_base_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M")
        source_img_path = source_dir / f"{timestamp}_source.bmp"
        if not source_img_path.exists():
            cv2.imwrite(str(source_img_path), img)

    return search_img


def pil2np(pil_img):
    '''
    PIL.Image.Image===>numpy.ndarray
    :param pil_img: pil模块的图片数据  PIL.Image.Image
    :return: numpy 支持的narray 数据结构   numpy.ndarray
    '''
    return np.array(pil_img)  # numpy.ndarray
