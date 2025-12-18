import re
import math
import cv2
from pic_and_color_util import capture_window_region
import easyocr


def _clean_attr_name(name: str) -> str:
    """
    清洗属性名（去掉多余字符）
    """
    return name.replace('^', '').replace(' ', '').strip()


def _extract_number(value: str) -> float:
    """
    提取属性值中的数字，失败返回0.0
    """
    try:
        num_str = re.findall(r"[-+]?\d*\.?\d+", value)
        if num_str:
            return float(num_str[0])
        return 0.0
    except Exception:
        return 0.0


class YysOCR:

    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.reader = easyocr.Reader(['ch_sim', 'en'])
        # 每3计1分的有效属性
        self.attr_rule_3 = ['攻击加成', '速度', '暴击']
        # 每4计1分的有效属性
        self.attr_rule_4 = ['暴击伤害', '效果命中']

    def set_attr_rule_3(self, attr_rule_3):
        self.attr_rule_3 = attr_rule_3

    def set_attr_rule_4(self, attr_rule_4):
        self.attr_rule_4 = attr_rule_4

    def ocr(self, img):
        """
        OCR识别：在放大图像上识别后，把坐标映射回原图坐标系并返回。
        返回格式和 easyocr 一样：[(box, text, conf), ...]，但 box 的点为原图坐标。
        """
        if img is None:
            return []

        h, w = img.shape[:2]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # 放大用于ocr
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

    def calc_score(self, ocr_result, img):
        """
        根据OCR结果计算分数并在图像上标注
        """
        total_score = 0
        results = []

        if not ocr_result or img is None:
            return img, results, total_score

        i = 0
        while i < len(ocr_result) - 1:
            attr_name_raw = ocr_result[i][1]
            attr_value_raw = ocr_result[i + 1][1]

            attr_name = _clean_attr_name(attr_name_raw)
            val = _extract_number(attr_value_raw)

            # 判断是否是已知属性，否则跳过
            if attr_name in self.attr_rule_3:
                score = math.ceil(val / 3)
            elif attr_name in self.attr_rule_4:
                score = math.ceil(val / 4)
            else:
                score = 0

            if score > 0:
                total_score += score

                # 取框位置
                try:
                    box = ocr_result[i][0]
                    x, y = int(box[0][0]), int(box[0][1])
                except Exception:
                    x, y = 0, 0

                results.append((attr_name, val, score, (x, y)))

                # 在图上画分数
                if img is not None:
                    cv2.putText(img, f"{score}", (max(0, x + 100), max(15, y + 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (85, 26, 139), 2)

            i += 2  # 每次跳过一对

        # 总分写在左下角
        if img is not None:
            img = draw_total_score_outside(img, total_score, pad_color=(156, 181, 203))

        return img, results, total_score


def draw_total_score_outside(img, total_score, pad_bottom=40, pad_color=(255, 255, 255)):
    """
    在图像下方增加区域，在区域上画total_score
    :param img: 原始图像
    :param total_score: 总分
    :param pad_bottom: 下方扩展的高度（像素）
    :param pad_color: 扩展区域颜色 (B, G, R)
    :return: 新图像
    """
    h, w = img.shape[:2]

    # 扩展画布：在下方加 pad_bottom 高度的空白
    new_img = cv2.copyMakeBorder(
        img,
        top=0,
        bottom=pad_bottom,
        left=0,
        right=0,
        borderType=cv2.BORDER_CONSTANT,
        value=pad_color  # 白色底
    )

    # 在新区域画文字
    cv2.putText(
        new_img,
        f"total: {total_score}",
        (10, h + int(pad_bottom * 0.7)),  # 新区域位置
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 255),
        2
    )

    return new_img