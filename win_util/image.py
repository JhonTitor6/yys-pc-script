import os
import time
from pathlib import Path
from ctypes import windll
from typing import List, Tuple, Union

import cv2
import numpy as np
import win32gui
import win32ui
from PIL import ImageGrab
from loguru import logger

import my_mouse
import config as config
from rgb_hex import rgb2hex, hex2rgb

debug_img_base_dir = Path("images/debug")


class ScreenCapture:
    """窗口截图和区域截图封装"""

    def __init__(self, hwnd: int):
        self.hwnd = hwnd

    def capture_window_region(self, x0=0, y0=0, x1=99999, y1=99999) -> np.ndarray:
        """捕获窗口指定区域"""
        client_rect = win32gui.GetClientRect(self.hwnd)
        client_width = client_rect[2] - client_rect[0] + 8
        client_height = client_rect[3] - client_rect[1] + 31

        x0 = max(x0, client_rect[0]) + 8
        y0 = max(y0, client_rect[1]) + 31
        x1 = min(x1 + 8, client_width)
        y1 = min(y1 + 31, client_height)

        if x0 >= x1 or y0 >= y1:
            raise ValueError(f"无效区域: ({x0}, {y0}) - ({x1}, {y1})")

        hwnd_dc = win32gui.GetWindowDC(self.hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, client_width, client_height)
        save_dc.SelectObject(save_bitmap)

        windll.user32.PrintWindow(self.hwnd, save_dc.GetSafeHdc(), 2)

        bmp_info = save_bitmap.GetInfo()
        bmp_str = save_bitmap.GetBitmapBits(True)
        img = np.frombuffer(bmp_str, dtype='uint8').reshape(
            (bmp_info['bmHeight'], bmp_info['bmWidth'], 4)
        )

        win32gui.DeleteObject(save_bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, hwnd_dc)

        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        search_img = img_bgr[y0:y1, x0:x1]

        if config.DEBUG:
            source_dir = debug_img_base_dir / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            source_img_path = source_dir / f"{timestamp}_source.bmp"
            if not source_img_path.exists():
                cv2.imwrite(str(source_img_path), img)

        return search_img

    @staticmethod
    def pil2np(pil_img) -> np.ndarray:
        return np.array(pil_img)


class ColorDetector:
    """颜色检测和匹配"""

    @staticmethod
    def get_pixel_color(x: int, y: int) -> str:
        gdi32 = windll.gdi32
        user32 = windll.user32
        hdc = user32.GetDC(None)
        pixel = gdi32.GetPixel(hdc, x, y)
        r = pixel & 0x0000ff
        g = (pixel & 0x00ff00) >> 8
        b = pixel >> 16
        return rgb2hex((r, g, b)).upper()

    @staticmethod
    def find_color(x0: int, y0: int, x1: int, y1: int, color_hex: str) -> Tuple[int, int]:
        color = hex2rgb(color_hex)
        img = np.array(ImageGrab.grab((x0, y0, x1, y1)))
        for i in range(img.shape[0]):
            for j in range(img.shape[1]):
                if tuple(img[i, j]) == color:
                    return x0 + j, y0 + i
        logger.debug("没找到point")
        return -1, -1

    @staticmethod
    def bg_get_pixel_color(hwnd: int, x: int, y: int) -> Union[str, None]:
        try:
            screen = ScreenCapture(hwnd).capture_window_region(x, y, x + 1, y + 1)
            b, g, r = screen[0, 0][:3]
            return f"{b:02X}{g:02X}{r:02X}"
        except Exception as e:
            logger.exception(f"获取像素颜色失败: {e}")
            return None

    @staticmethod
    def bg_check_pixel_color(hwnd: int, x: int, y: int, expected_color_bgr: str, similarity=1.0) -> bool:
        actual_color = ColorDetector.bg_get_pixel_color(hwnd, x, y)
        if not actual_color:
            return False
        expected_bgr = hex2rgb(expected_color_bgr)
        actual_bgr = hex2rgb(actual_color)
        diff = sum((e - a) ** 2 for e, a in zip(expected_bgr, actual_bgr)) ** 0.5
        max_diff = (3 * (255 ** 2)) ** 0.5
        actual_similarity = 1 - (diff / max_diff)
        return actual_similarity >= similarity


class ImageMatchConfig:
    """多模板匹配配置"""

    def __init__(self, target_image_path_list: Union[List[str], str],
                 x0=0, y0=0, x1=99999, y1=99999, similarity=0.8):
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


class ImageFinder:
    """模板匹配、找图、点击封装，支持截图缓存"""

    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self.capture = ScreenCapture(hwnd)
        self.screenshot = None  # 截图缓存

    def update_screenshot(self, x0=0, y0=0, x1=99999, y1=99999):
        """更新截图缓存"""
        self.screenshot = self.capture.capture_window_region(x0, y0, x1, y1)

    def bg_find_pic_in_cache(self, small_picture_path, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8) -> Tuple[int, int]:
        """在缓存截图中匹配图片"""
        if self.screenshot is None:
            logger.warning("截图缓存为空，请先调用 update_screenshot()")
            return -1, -1
        return self.bg_find_pic_in_screenshot(self.screenshot, small_picture_path, x0, y0, x1, y1, similarity)

    def bg_find_pic_by_config_in_cache(self, image_match_config: ImageMatchConfig):
        """使用缓存截图匹配多模板"""
        if self.screenshot is None:
            logger.warning("截图缓存为空，请先调用 update_screenshot()")
            return (-1, -1), None
        for target_image_path in image_match_config.target_image_path_list:
            point = self.bg_find_pic_in_screenshot(
                self.screenshot,
                target_image_path,
                image_match_config.x0,
                image_match_config.y0,
                image_match_config.x1,
                image_match_config.y1,
                image_match_config.similarity
            )
            if point != (-1, -1):
                return point, target_image_path
        return (-1, -1), None

    def bg_find_pic(self, small_picture_path, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8) -> Tuple[int, int]:
        """直接截图匹配图片"""
        search_img = self.capture.capture_window_region(x0, y0, x1, y1)
        return self.bg_find_pic_in_screenshot(search_img, small_picture_path, x0, y0, x1, y1, similarity)

    def bg_find_pic_and_click(self, small_picture_path, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8):
        point = self.bg_find_pic(small_picture_path, x0, y0, x1, y1, similarity)
        if config.DEBUG and point != (-1, -1):
            logger.success(f"点击{small_picture_path}，坐标{point}")
        return my_mouse.bg_left_click(self.hwnd, point)

    @staticmethod
    def bg_find_pic_in_screenshot(screenshot, small_picture_path, x0=0, y0=0, x1=99999, y1=99999, similarity=0.8):
        """在给定截图中匹配图片"""
        if screenshot is None or not os.path.exists(small_picture_path):
            return -1, -1

        search_img = screenshot
        if x0 > 0 or y0 > 0 or x1 < 99999 or y1 < 99999:
            h, w = search_img.shape[:2]
            x1 = min(x1, w)
            y1 = min(y1, h)
            search_img = search_img[y0:y1, x0:x1]

        template = cv2.imread(small_picture_path)
        if template is None:
            raise ValueError(f"无法读取模板图片: {small_picture_path}")

        result = cv2.matchTemplate(search_img, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        h, w = template.shape[:2]
        center_x = x0 + max_loc[0] + w // 2
        center_y = y0 + max_loc[1] + h // 2

        match = max_val >= similarity

        # 调试模式保存图片
        if config.DEBUG and max_val >= 0.6:
            template_name = Path(small_picture_path).stem
            template_dir = debug_img_base_dir / template_name
            template_dir.mkdir(parents=True, exist_ok=True)
            debug_img = search_img.copy()
            cv2.rectangle(debug_img, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 255, 0), 1)
            match_text = f"{max_val:.2f}/{similarity}@({center_x},{center_y})"
            cv2.putText(debug_img, match_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.imwrite(str(template_dir / f"{match}_result.png"), debug_img)

        if match:
            logger.debug(f"匹配成功: {Path(small_picture_path).stem} | 位置: ({center_x},{center_y}) | 相似度: {max_val:.4f}")
            return center_x, center_y
        return -1, -1
