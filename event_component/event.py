import time
from abc import abstractmethod, ABC

from loguru import logger
from win_util.image import ImageFinder, ImageMatchConfig
from my_mouse import bg_left_click_with_range
from yys.util.yys_ocr import YysOCR


def bg_find_pic_by_config(screenshot, image_match_config: ImageMatchConfig) -> tuple:
    # 由于ImageFinder构造函数需要hwnd，我们创建一个临时实例并调用静态方法
    # 但这里我们直接使用静态方法
    for target_image_path in image_match_config.target_image_path_list:
        point = ImageFinder.bg_find_pic_in_screenshot(screenshot, target_image_path,
                                          image_match_config.x0, image_match_config.y0,
                                          image_match_config.x1, image_match_config.y1,
                                          image_match_config.similarity)
        if point is not None and point[0] != -1 and point[1] != -1:
            return point, target_image_path
    return (-1, -1), None

def capture_window_region(hwnd, x0=0, y0=0, x1=99999, y1=99999):
    from pic_and_color_util import capture_window_region as original_capture_window_region
    return original_capture_window_region(hwnd, x0, y0, x1, y1)

class Event:
    def __init__(self, event_name):
        self.name = event_name

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return self.name


unknown = Event("unknown")


class EventManager:
    def __init__(self):
        self.event_handler_map = {}

    def register_event_handler(self, event: Event, callback):
        self.event_handler_map[event] = callback

    def trigger_event(self, event: Event | str, data=None, debug_log=True):
        event = Event(event) if isinstance(event, str) else event
        if debug_log:
            logger.debug(f"触发事件 [{event}]")
        if event in self.event_handler_map:
            callback = self.event_handler_map[event]
            if callback is None and debug_log:
                logger.debug(f"触发事件 [{event}] 回调为空")
                return
            callback_str = type(callback.__self__).__name__ + "." + callback.__name__
            if debug_log:
                logger.debug(f"触发事件 [{event}] 回调 [{callback_str}]")
            callback(data)


class AutoImageEventScript(ABC):
    def __init__(self):
        super().__init__()

        self.screenshot_cache = None

        self._event_manager = EventManager()
        self.yys_ocr = YysOCR()
        self._image_event_match_configs: [ImageMatchConfig] = []
        self._ocr_event_keywords: [str] = []
        self.hwnd = self._find_window()

    def _register_image_match_event(self, image_event_match_config: ImageMatchConfig, callback):
        if image_event_match_config in self._image_event_match_configs:
            self._image_event_match_configs.remove(image_event_match_config)
        self._image_event_match_configs.append(image_event_match_config)
        for target_image_path in image_event_match_config.target_image_path_list:
            self._event_manager.register_event_handler(Event(target_image_path), callback)
            
    def _register_ocr_match_event(self, keyword: str, callback):
        if keyword in self._ocr_event_keywords:
            self._ocr_event_keywords.remove(keyword)
        self._ocr_event_keywords.append(keyword)
        self._event_manager.register_event_handler(Event(keyword), callback)

    def bg_left_click(self, point, x_range=20, y_range=20):
        bg_left_click_with_range(self.hwnd, point, x_range=x_range, y_range=y_range)

    def _trigger_event_from_screenshot_cache(self):
        # 图片
        for image_match_config in self._image_event_match_configs:
            res = bg_find_pic_by_config(self.screenshot_cache, image_match_config)
            point = res[0]
            if point is not None and point != (-1, -1):
                time.sleep(0.1)
                image_path = res[1]
                self._event_manager.trigger_event(image_path, point)
                return
        # ocr
        for keyword in self._ocr_event_keywords:
            ocr_result = self.yys_ocr.ocr(self.screenshot_cache)
            if keyword in ocr_result:
                self._event_manager.trigger_event(keyword, ocr_result)
                return
        self._event_manager.trigger_event(unknown, debug_log=False)

    def _update_screenshot_cache(self):
        self.screenshot_cache = capture_window_region(self.hwnd)

    def run(self):
        while True:
            self._update_screenshot_cache()
            self._trigger_event_from_screenshot_cache()
            time.sleep(0.2)

    @abstractmethod
    def _find_window(self) -> str:
        pass