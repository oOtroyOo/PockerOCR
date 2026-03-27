from argparse import Namespace
import os
import time
import threading
import cv2
import numpy as np
from PyQt5.QtCore import pyqtSignal, QObject
import pytesseract
import mss
from win32 import win32gui, win32print
from win32.lib import win32con
from win32.win32api import GetSystemMetrics
from Source import defines

screenshot_debug_img = os.path.exists("screenshot")


class WorkerSignals(QObject):
    """工作线程信号"""

    result_updated = pyqtSignal(Namespace)
    error_occurred = pyqtSignal(str)


class OCRWorker(threading.Thread):
    """OCR工作线程"""

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.signals = WorkerSignals()
        self.running = False
        self.hwnd = 0
        self.daemon = True
        # 每次捕获时创建mss实例，避免线程问题

    def run(self):
        """单次扫描"""
        self.running = True
        os.makedirs("screenshot", exist_ok=True)

        time.sleep(0.5)  # 等待窗口切换

        try:
            if self.hwnd and self.running:
                # 捕获窗口
                screenshot = self.capture_window(self.hwnd)
                if screenshot is not None:
                    # 识别手牌和牌池
                    result = self.recognize_cards(screenshot)
                    screenshot = None
                    self.signals.result_updated.emit(result)
        except Exception as e:
            self.signals.error_occurred.emit(f"扫描错误: {str(e)}")

    def capture_window(self, hwnd):
        """捕获窗口截图（使用MSS + DXGI）"""
        try:
            title = win32gui.GetWindowText(hwnd)

            # 获取窗口位置和尺寸
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top

            # 在每次捕获时创建新的mss实例，避免线程问题
            sct = mss.mss()

            # 使用MSS截取指定区域（窗口区域）
            monitor = {"top": top, "left": left, "width": width, "height": height}
            screenshot = sct.grab(monitor)

            # 转换为numpy数组（BGRA格式）
            img0 = np.array(screenshot)
            screenshot = None
            # 转换BGRA到BGR
            img1 = cv2.cvtColor(img0, cv2.COLOR_BGRA2BGR)
            img0 = None
            # 剔除Windows标题栏
            title_bar_height = GetSystemMetrics(win32con.SM_CYCAPTION) + 4
            border_width = GetSystemMetrics(win32con.SM_CXSIZEFRAME) + 4
            border_height = GetSystemMetrics(win32con.SM_CYSIZEFRAME) + 4
            # 调整窗口区域，只截取客户区
            img = img1[title_bar_height + border_height : height - border_height, border_width : width - border_width]
            img1 = None

            # 保存调试图像
            if screenshot_debug_img:
                cv2.imwrite(f"screenshot/screenshot.png", img)

            return img

        except Exception as e:
            self.signals.error_occurred.emit(f"截图错误: {str(e)}")
            return None

    def recognize_cards(self, image):
        """识别手牌和牌池"""
        result = Namespace()

        h, w = image.shape[:2]

        # 识别手牌
        hand1_pos = self.config["hand_cards"]["card1"]
        hand2_pos = self.config["hand_cards"]["card2"]

        card1 = self.crop_and_ocr(image, hand1_pos, "card1")
        card2 = self.crop_and_ocr(image, hand2_pos, "card2")

        result.hand_cards = [
            card1,
            card2,
        ]

        # 识别牌池（支持5张牌）
        board_cards = self.config["board_cards"]

        pos_list = board_cards.get("pos", [0, 0])
        size_list = board_cards.get("size", [0, 0])

        x = int(pos_list[0] * w)
        y = int(pos_list[1] * h)
        area_w = int(size_list[0] * w)
        area_h = int(size_list[1] * h)
        card_width = int(size_list[0] * 0.2 * 0.4 * w)

        # 先裁剪牌池区域
        board_region = image[y : y + area_h, x : x + area_w]

        if screenshot_debug_img:
            cv2.imwrite(f"screenshot/board_region.png", board_region)
        result.board_cards = []
        # 尝试识别5张牌
        for i in range(5):
            card_x = int(area_w * i * 0.2)
            card_img = board_region[:, card_x : card_x + card_width]
            if screenshot_debug_img:
                cv2.imwrite(f"screenshot/board_img_{i+1}.png", card_img)
            card_text = self.ocr_image(card_img)
            card_img = None
            result.board_cards.append(card_text)
        board_region = None
        return result

    def crop_and_ocr(self, image, pos, name):
        """裁剪并OCR识别"""
        # pos 格式: {"pos": [x, y], "size": [w, h], "r": rotation}
        pos_list = pos.get("pos", [0, 0])
        size_list = pos.get("size", [0, 0])
        rotation = pos.get("r", 0)
        h, w = image.shape[:2]
        x = int(pos_list[0] * w)
        y = int(pos_list[1] * h)
        pw = int(size_list[0] * w)
        ph = int(size_list[1] * h)

        # 如果有旋转，先旋转再裁剪
        if rotation != 0:
            # 创建旋转矩阵
            center = (x + pw // 2, y + ph // 2)
            M = cv2.getRotationMatrix2D(center, rotation, 1.0)
            # 旋转图像
            rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            cropped = rotated[y : y + ph, x : x + pw]
        else:
            cropped = image[y : y + ph, x : x + pw]

        # 保存原始图像到本地
        if screenshot_debug_img:
            cv2.imwrite(f"screenshot/capture_{name}.png", cropped)
        return self.ocr_image(cropped)

    def ocr_image(self, image):
        """OCR识别图像，使用本地训练的 poker 模型"""
        try:
            h, w = image.shape[:2]
            delta = 0.65

            # 获取训练数据目录的绝对路径
            tessdata_dir = os.path.abspath("assets/traineddata")

            # 预处理
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # 识别点数
            cropped_num = gray[0 : int(h * delta), 0:w]

            # 二值化
            _, binary = cv2.threshold(cropped_num, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # OCR配置 - 使用本地 poker 模型识别点数
            custom_config_number = f'--tessdata-dir "{tessdata_dir}" --oem {self.config["ocr"]["oem"]} --psm 7 -c tessedit_char_whitelist=AKQJT1023456789'

            text = pytesseract.image_to_string(binary, lang="poker", config=custom_config_number).strip()
            binary = None
            # 识别花色
            cropped_suit = gray[int(h * delta) : h, 0:w]
            gray = None
            _, binary = cv2.threshold(cropped_suit, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # OCR配置 - 使用本地 poker 模型识别花色
            custom_config_suit = f'--tessdata-dir "{tessdata_dir}" --oem {self.config["ocr"]["oem"]} --psm 10 -c tessedit_char_whitelist=SHCD'
            suit = pytesseract.image_to_string(binary, lang="poker", config=custom_config_suit).strip()
            binary = None
            if len(text) == 1 and len(suit) == 1:
                # 将 "10" 转换为 "T" 以匹配 RANK_ORDER
                if text == "0":
                    text = "T"  # OCR 可能将 10 识别为 "0"
                # 将 rank 字符串转换为 int
                rank_int = defines.RANK_ORDER.get(text, 0)
                return (suit, rank_int)
            else:
                if screenshot_debug_img:
                    cv2.imwrite(f"screenshot/cropped_num.png", cropped_num)
                    cv2.imwrite(f"screenshot/cropped_suit.png", cropped_suit)
            cropped_num = None
            cropped_suit = None
            return ("", "")

        except Exception as e:
            self.signals.error_occurred.emit(f"OCR错误: {str(e)}")
            return ""

    def stop(self):
        """停止扫描"""
        self.running = False
