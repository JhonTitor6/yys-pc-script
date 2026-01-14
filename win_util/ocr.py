import cv2
import easyocr
from loguru import logger

class CommonOcr:
    def __init__(self, lang_list=['ch_sim', 'en'], gpu=True, **kwargs):
        """
        初始化OCR阅读器

        Args:
            lang_list: 语言列表，默认为['ch_sim', 'en']
            gpu: 是否使用GPU，默认True
            **kwargs: 其他传递给easyocr.Reader的参数
        """
        self.reader: easyocr.Reader = easyocr.Reader(lang_list, gpu=gpu, **kwargs)

    def ocr(self, img):
        """
        识别图像中的文本，返回原生结果

        Args:
            img: 输入图像

        Returns:
            OCR结果列表，格式与easyocr一致：[(box, text, conf), ...]
        """
        if img is None:
            return []

        h, w = img.shape[:2]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 放大用于OCR
        fx, fy = 2.0, 2.0
        gray_resized = cv2.resize(gray, None, fx=fx, fy=fy, interpolation=cv2.INTER_CUBIC)
        _, thresh = cv2.threshold(gray_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        ocr_results = self.reader.readtext(thresh)

        # 计算缩放系数（更稳健：根据实际尺寸算）
        rh, rw = thresh.shape[:2]
        scale_x = rw / float(w)
        scale_y = rh / float(h)

        scaled_results = []
        for box, text, conf in ocr_results:
            # box 是四个点 [[x1,y1], [x2,y2], ...]
            new_box = []
            for (px, py) in box:
                # px, py 来自放大图，需要映射回原图
                nx = int(round(px / scale_x))
                ny = int(round(py / scale_y))
                new_box.append([nx, ny])
            scaled_results.append((new_box, text, conf))

        return scaled_results

    def contains_text(self, img, target_text, case_sensitive=False):
        """
        根据OCR结果判断目标文本是否出现在图像中

        Args:
            img: 输入图像
            target_text: 目标文本，支持字符串或字符串列表
            case_sensitive: 是否区分大小写，默认False

        Returns:
            bool: 如果目标文本出现在图像中则返回True，否则返回False
        """
        ocr_results = self.ocr(img)

        # 获取OCR识别的所有文本
        detected_texts = [text for _, text, _ in ocr_results]

        logger.debug(f"检测到的文本：{detected_texts}")

        # 统一处理大小写
        if not case_sensitive:
            detected_texts = [text.lower() for text in detected_texts]
            if isinstance(target_text, str):
                target_text = target_text.lower()
            else:
                target_text = [t.lower() for t in target_text]

        # 判断目标文本是否存在于检测到的文本中
        if isinstance(target_text, str):
            # 单个文本查找
            for text in detected_texts:
                if target_text in text:
                    return True
        else:
            # 多个文本查找，只要有一个匹配就返回True
            for target in target_text:
                for text in detected_texts:
                    if target in text:
                        return True

        return False

    def find_text_position(self, img, target_text, case_sensitive=False):
        """
        查找目标文本在图像中的位置

        Args:
            img: 输入图像
            target_text: 目标文本
            case_sensitive: 是否区分大小写，默认False

        Returns:
            list: 包含目标文本的位置信息列表，格式为 [(box, text, conf), ...]
        """
        ocr_results = self.ocr(img)

        found_positions = []

        for box, text, conf in ocr_results:
            compare_text = text if case_sensitive else text.lower()
            compare_target = target_text if case_sensitive else target_text.lower()

            if compare_target in compare_text:
                found_positions.append((box, text, conf))

        return found_positions

    def set_reader(self, reader: easyocr.Reader):
        self.reader = reader

    def get_reader(self) -> easyocr.Reader:
        """
        返回原生的easyocr.Reader对象，供外部直接调用原生方法
        """
        return self.reader
