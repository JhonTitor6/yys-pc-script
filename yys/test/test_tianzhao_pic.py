import unittest

import cv2


class TestTianZhaoPic(unittest.TestCase):
    def test_grey(self):
        big_pic = cv2.imread("yys/images/debug/source/20250923_2108_source.bmp")
        gray_big_pic = cv2.cvtColor(big_pic, cv2.COLOR_BGR2GRAY)
        _, big_bin_pic = cv2.threshold(gray_big_pic, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        cv2.imshow("gray_big_pic", gray_big_pic)

        # 读取模板图片
        template = cv2.imread("yys/images/battle_tianzhao.bmp")
        gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)  # 修复：应使用template而不是big_pic
        _, bin_template = cv2.threshold(gray_template, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        cv2.imshow("gray_template", gray_template)

        # 模板匹配
        result = cv2.matchTemplate(big_pic, template, cv2.TM_CCORR_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        print(max_val)

        # 在图像上圈出匹配区域并显示
        # 获取模板的宽高
        h, w = bin_template.shape[:2]

        # 获取最佳匹配位置的左上角坐标
        top_left = max_loc

        # 计算矩形框的右下角坐标
        bottom_right = (top_left[0] + w, top_left[1] + h)

        # 在原图上绘制矩形框
        cv2.rectangle(big_pic, top_left, bottom_right, (0, 255, 0), 2)

        # 显示结果
        cv2.imshow('Matched Result', big_pic)
        cv2.waitKey(0)  # 等待按键
        cv2.destroyAllWindows()  # 关闭窗口
