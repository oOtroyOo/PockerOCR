"""
扑克OCR应用程序
功能：窗口捕获、间隔扫描、识别手牌和牌池
"""

import os
import sys
import time
import threading
import cv2
from cv2.typing import MatLike
import numpy as np
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QSpinBox,
    QTextEdit,
    QGroupBox,
    QGridLayout,
    QFrame,
    QFileDialog,
    QMessageBox,
    QDialog,
    QSlider,
    QDoubleSpinBox,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QRectF, QPointF
from PyQt5.QtGui import QPolygonF
from PyQt5.QtGui import QImage, QPixmap, QFont, QPainter, QPen, QBrush, QColor
import win32gui
import win32ui
import win32con
from PIL import Image
import pytesseract
import yaml
import subprocess
import pywintypes
import pygetwindow
import mss
import typing

screenshot_debug_img = os.path.exists('screenshot')


class RegionEditorDialog(QDialog):
    """区域编辑对话框"""

    def __init__(self, parent, image, current_config, region_key, region_name):
        super().__init__(parent)
        h, w = image.shape[:2]

        # 转换为QPixmap
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        qt_image = QImage(rgb_image.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self.pixmap = QPixmap.fromImage(qt_image)
        self.current_config = current_config or {}
        self.region_key = region_key
        self.region_name = region_name
        self.region = self.get_current_region()
        self.init_ui()
        self.update_preview()

    def get_current_region(self) -> dict[str, typing.Any]:
        """获取当前区域配置"""
        # 格式: {"pos": [x, y], "size": [w, h], "r": rotation}
        if self.region_key == "card1":
            return self.current_config.get("hand_cards", {}).get("card1", {})
        elif self.region_key == "card2":
            return self.current_config.get("hand_cards", {}).get("card2", {})
        elif self.region_key == "board":
            return self.current_config.get("board_cards", {})
        return {}

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"区域编辑 - {self.region_name}")
        # self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        # self.setMinimumSize(600, 500)
        # self.resize(self.pixmap.width(), self.pixmap.height())
        layout = QVBoxLayout()

        # 图片预览
        self.image_label = ClickableLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.image_label.setMinimumSize(580, 400)
        self.image_label.resize(self.pixmap.width(), self.pixmap.height())
        self.image_label.parent_dialog = self
        self.image_label.set_click_callback(self.on_image_click)
        self.image_label.set_release_callback(self.on_image_release)
        layout.addWidget(self.image_label)

        # 控制面板
        control_layout = QHBoxLayout()

        # 旋转滑块
        control_layout.addWidget(QLabel("旋转角度:"))
        self.rotation_slider = QSlider(Qt.Orientation.Horizontal)
        self.rotation_slider.setRange(-45, 45)
        self.rotation_slider.setValue(int(self.region["r"]))
        self.rotation_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.rotation_slider.setTickInterval(5)
        self.rotation_slider.valueChanged.connect(self.on_rotation_changed)
        control_layout.addWidget(self.rotation_slider)

        self.rotation_label = QLabel(f"{self.region['r']}°")
        control_layout.addWidget(self.rotation_label)

        # 区域尺寸控制
        control_layout.addWidget(QLabel("宽度:"))
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.01, 0.99)
        self.width_spin.setSingleStep(0.01)
        self.width_spin.setValue(self.region["w"])
        self.width_spin.valueChanged.connect(self.on_region_changed)
        control_layout.addWidget(self.width_spin)

        control_layout.addWidget(QLabel("高度:"))
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(0.01, 0.99)
        self.height_spin.setSingleStep(0.01)
        self.height_spin.setValue(self.region["h"])
        self.height_spin.valueChanged.connect(self.on_region_changed)
        control_layout.addWidget(self.height_spin)

        layout.addLayout(control_layout)

        # 按钮布局
        button_layout = QHBoxLayout()

        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self.reset_region)
        button_layout.addWidget(reset_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_region)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def update_preview(self):
        """更新预览"""
        if self.pixmap is None:
            return

        # 缩放到显示尺寸，保持宽高比
        scaled_pixmap = self.pixmap.scaled(self.image_label.width(), self.image_label.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        # 计算缩放后的实际尺寸和偏移量（居中显示）
        scaled_w = scaled_pixmap.width()
        scaled_h = scaled_pixmap.height()
        self.image_label.image_offset_x = (self.image_label.width() - scaled_w) // 2
        self.image_label.image_offset_y = (self.image_label.height() - scaled_h) // 2

        # 绘制区域框
        painter = QPainter(scaled_pixmap)

        # 绘制虚线框（已有区域，带旋转）
        x = int(self.region.get("pos", {})[0] * scaled_w)
        y = int(self.region.get("pos", {})[1] * scaled_h)
        rw = int(self.region.get("size", {})[0] * scaled_w)
        rh = int(self.region.get("size", {})[0] * scaled_h)
        rotation = self.region["r"]

        pen = QPen(QColor("#2196F3"), 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        if rotation != 0:
            # 绘制旋转后的矩形
            self.draw_rotated_rect(painter, x, y, rw, rh, rotation)
        else:
            # 绘制普通矩形
            painter.drawRect(x, y, rw, rh)

        # 绘制实线框（用户框选区域或拖拽区域）
        if hasattr(self, "user_region") and self.user_region:
            ux, uy, uw, uh = self.user_region
            ux = int(ux * scaled_w)
            uy = int(uy * scaled_h)
            uw = int(uw * scaled_w)
            uh = int(uh * scaled_h)
            pen.setStyle(Qt.PenStyle.SolidLine)
            pen.setColor(QColor("#f44336"))
            pen.setWidth(3)
            painter.setPen(pen)

            if rotation != 0:
                # 绘制旋转后的矩形
                self.draw_rotated_rect(painter, ux, uy, uw, uh, rotation)
            else:
                # 绘制普通矩形
                painter.drawRect(ux, uy, uw, uh)
        elif self.image_label.is_dragging and self.image_label.start_pos and self.image_label.current_pos:
            # 绘制拖拽框
            start = self.image_label.start_pos
            current = self.image_label.current_pos
            offset_x = self.image_label.image_offset_x
            offset_y = self.image_label.image_offset_y

            # 确保在图片范围内
            x1 = max(offset_x, min(start.x(), current.x()))
            y1 = max(offset_y, min(start.y(), current.y()))
            x2 = min(offset_x + scaled_w, max(start.x(), current.x()))
            y2 = min(offset_y + scaled_h, max(start.y(), current.y()))

            rw = max(0, x2 - x1)
            rh = max(0, y2 - y1)

            if rw > 0 and rh > 0:
                pen.setStyle(Qt.PenStyle.SolidLine)
                pen.setColor(QColor("#4CAF50"))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(x1 - offset_x, y1 - offset_y, rw, rh)

        painter.end()

        self.image_label.setPixmap(scaled_pixmap)

    def draw_rotated_rect(self, painter, x, y, w, h, angle):
        """绘制旋转的矩形"""
        import math

        # 将角度转换为弧度
        angle_rad = math.radians(angle)

        # 矩形的中心点
        center_x = x + w / 2
        center_y = y + h / 2

        # 计算旋转后的四个角点
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        # 相对于中心的四个角点（未旋转）
        corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]

        # 旋转并平移回实际位置
        polygon_points = []
        for cx, cy in corners:
            rx = cx * cos_a - cy * sin_a + center_x
            ry = cx * sin_a + cy * cos_a + center_y
            polygon_points.append(QPointF(rx, ry))

        painter.drawPolygon(QPolygonF(polygon_points))

    def on_image_click(self, event):
        """处理图片点击（开始框选区域）"""
        if self.pixmap is None:
            return

        # 获取点击位置
        label_pos = event.pos()
        pixmap = self.image_label.pixmap()
        if not pixmap:
            return

        # 获取缩放后的图片尺寸和偏移量
        scaled_w = pixmap.width()
        scaled_h = pixmap.height()
        offset_x = self.image_label.image_offset_x
        offset_y = self.image_label.image_offset_y

        # 检查点击是否在图片范围内
        if label_pos.x() < offset_x or label_pos.x() >= offset_x + scaled_w:
            return
        if label_pos.y() < offset_y or label_pos.y() >= offset_y + scaled_h:
            return

    def on_image_release(self, event):
        """处理图片释放（完成框选区域）"""
        if self.pixmap is None:
            return

        # 获取释放位置
        label_pos = event.pos()
        pixmap = self.image_label.pixmap()
        if not pixmap:
            return

        # 获取缩放后的图片尺寸和偏移量
        scaled_w = pixmap.width()
        scaled_h = pixmap.height()
        offset_x = self.image_label.image_offset_x
        offset_y = self.image_label.image_offset_y

        # 拖拽完成，更新区域
        start = self.image_label.start_pos
        current = label_pos

        if start and current:
            # 确保在图片范围内
            x1 = max(offset_x, min(start.x(), current.x()))
            y1 = max(offset_y, min(start.y(), current.y()))
            x2 = min(offset_x + scaled_w, max(start.x(), current.x()))
            y2 = min(offset_y + scaled_h, max(start.y(), current.y()))

            rw = max(0, x2 - x1)
            rh = max(0, y2 - y1)

            # 转换为缩放图坐标
            scaled_x = x1 - offset_x
            scaled_y = y1 - offset_y
            scaled_w_region = rw
            scaled_h_region = rh

            # 转换为百分比
            x = max(0, min(1, (scaled_x / scaled_w)))
            y = max(0, min(1, (scaled_y / scaled_h)))
            region_w_percent = max(0.01, min(0.5, (scaled_w_region / scaled_w)))
            region_h_percent = max(0.01, min(0.5, (scaled_h_region / scaled_h)))

            # 更新用户框选区域
            self.user_region = (x, y, region_w_percent, region_h_percent)

            # 更新配置区域
            self.region["x"] = x
            self.region["y"] = y
            self.region["w"] = region_w_percent
            self.region["h"] = region_h_percent
            self.width_spin.setValue(region_w_percent)
            self.height_spin.setValue(region_h_percent)

            self.update_preview()

    def on_rotation_changed(self):
        """旋转角度改变"""
        rotation = self.rotation_slider.value()
        self.region["r"] = rotation
        self.rotation_label.setText(f"{rotation}°")
        self.update_preview()

    def on_region_changed(self):
        """区域尺寸改变"""
        self.region["w"] = self.width_spin.value()
        self.region["h"] = self.height_spin.value()
        self.update_preview()

    def reset_region(self):
        """重置区域"""
        self.region = self.get_current_region()
        self.rotation_slider.setValue(int(self.region["r"]))
        self.width_spin.setValue(self.region["w"])
        self.height_spin.setValue(self.region["h"])
        if hasattr(self, "user_region"):
            del self.user_region
        self.update_preview()

    def save_region(self):
        """保存区域"""
        # 转换为配置文件格式 {"pos": [x, y], "size": [w, h], "r": rotation}
        region_dict = {
            "pos": [round(self.region["x"], 2), round(self.region["y"], 2)],
            "size": [round(self.region["w"], 2), round(self.region["h"], 2)],
            "r": round(self.region["r"], 2),
        }
        if self.region_key == "card1":
            if "hand_cards" not in self.current_config:
                self.current_config["hand_cards"] = {}
            self.current_config["hand_cards"]["card1"] = region_dict
        elif self.region_key == "card2":
            if "hand_cards" not in self.current_config:
                self.current_config["hand_cards"] = {}
            self.current_config["hand_cards"]["card2"] = region_dict
        elif self.region_key == "board":
            self.current_config["board_cards"] = region_dict

        self.accept()

    def get_updated_config(self):
        """获取更新后的配置"""
        return self.current_config


class ClickableLabel(QLabel):
    """可点击的标签，用于区域选择"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent_dialog = None
        self.start_pos = None
        self.current_pos = None
        self.is_dragging = False
        self.click_callback = None
        self.release_callback = None
        self.image_offset_x = 0
        self.image_offset_y = 0

    def set_click_callback(self, callback):
        """设置点击回调函数"""
        self.click_callback = callback

    def set_release_callback(self, callback):
        """设置释放回调函数"""
        self.release_callback = callback

    @property
    def parent_dialog(self):
        """获取父对话框"""
        return self._parent_dialog

    @parent_dialog.setter
    def parent_dialog(self, value):
        """设置父对话框"""
        self._parent_dialog = value

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        self.start_pos = event.pos()
        self.current_pos = event.pos()
        self.is_dragging = True
        if self.click_callback:
            self.click_callback(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        self.current_pos = event.pos()
        if self._parent_dialog and self.is_dragging:
            self._parent_dialog.update_preview()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        was_dragging = self.is_dragging
        self.is_dragging = False
        if was_dragging and self.release_callback:
            self.release_callback(event)


class WorkerSignals(QObject):
    """工作线程信号"""

    result_updated = pyqtSignal(dict)
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
        """运行扫描循环"""
        self.running = True
        os.makedirs("screenshot", exist_ok=True)
        # 将窗口置于前端
        win32gui.SetForegroundWindow(self.hwnd)
        time.sleep(0.5)  # 等待窗口切换

        while self.running:
            try:
                if self.hwnd:
                    # 捕获窗口
                    screenshot = self.capture_window(self.hwnd)
                    if screenshot is not None:
                        # 识别手牌和牌池
                        result = self.recognize_cards(screenshot)
                        self.signals.result_updated.emit(result)

                # 间隔
                time.sleep(self.config["scan_interval"] / 1000.0)

            except Exception as e:
                self.signals.error_occurred.emit(f"扫描错误: {str(e)}")
                time.sleep(1)

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
            img = np.array(screenshot)

            # 转换BGRA到BGR
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # 保存调试图像
            if screenshot_debug_img:
                cv2.imwrite(f"screenshot/screenshot.png", img)

            return img

        except Exception as e:
            self.signals.error_occurred.emit(f"截图错误: {str(e)}")
            return None

    def recognize_cards(self, image):
        """识别手牌和牌池"""
        result = {"hand_cards": [], "board_cards": [], "timestamp": time.strftime("%H:%M:%S")}

        h, w = image.shape[:2]

        # 识别手牌
        hand1_pos = self.config["hand_cards"]["card1"]
        hand2_pos = self.config["hand_cards"]["card2"]

        card1 = self.crop_and_ocr(image, hand1_pos, w, h)
        card2 = self.crop_and_ocr(image, hand2_pos, w, h)

        result["hand_cards"] = [card1, card2]

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
        # 尝试识别5张牌
        for i in range(5):
            card_x = int(area_w * i * 0.2)
            card_img = board_region[:, card_x : card_x + card_width]
            if screenshot_debug_img:
                cv2.imwrite(f"screenshot/board_img_{i+1}.png", card_img)
            card_text = self.ocr_image(card_img)
            result["board_cards"].append(card_text)

        return result

    def crop_and_ocr(self, image, pos, w, h):
        """裁剪并OCR识别"""
        # pos 格式: {"pos": [x, y], "size": [w, h], "r": rotation}
        pos_list = pos.get("pos", [0, 0])
        size_list = pos.get("size", [0, 0])
        rotation = pos.get("r", 0)

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
            cv2.imwrite(f"screenshot/capture_{pos_list}.png", cropped)
        return self.ocr_image(cropped)

    def ocr_image(self, image):
        """OCR识别图像"""
        try:
            h, w = image.shape[:2]
            delta = 0.63
            # 预处理
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            cropped = gray[0 : int(h * delta * 1.04), 0:w]
            if screenshot_debug_img:
                cv2.imwrite(f"screenshot/cropped_number.png", cropped)
            # 二值化
            _, binary = cv2.threshold(cropped, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            # OCR配置 - 只识别点数字符
            custom_config_number = f'--oem {self.config["ocr"]["oem"]} --psm 7 -c tessedit_char_whitelist=AKQJT1023456789'

            # 识别
            text = pytesseract.image_to_string(binary, config=custom_config_number).strip()

            cropped = gray[int(h * delta * 0.98) : h, 0:w]
            if screenshot_debug_img:
                cv2.imwrite(f"screenshot/cropped_suit.png", cropped)

            # OCR配置 - 只识别花色字符
            custom_config_suit = f'--oem {self.config["ocr"]["oem"]} --psm 8 -c tessedit_char_whitelist=♠♣♥♦'
            suit = pytesseract.image_to_string(binary, config=custom_config_suit).strip()

            # 清理结果
            return (suit, text)

        except Exception as e:
            self.signals.error_occurred.emit(f"OCR错误: {str(e)}")
            return ""

    def stop(self):
        """停止扫描"""
        self.running = False


class PokerOCRWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        self.worker = None
        self.window_list = []
        self.current_hwnd = None
        self.init_ui()

    def load_config(self):
        """加载配置文件"""
        try:
            with open("config.yaml", "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            # 返回默认配置
            raise

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("扑克OCR识别系统")
        self.setGeometry(100, 100, 900, 700)

        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # 标题
        title_label = QLabel("扑克OCR识别系统")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Arial", 20, QFont.Bold))
        main_layout.addWidget(title_label)

        # 分割布局
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        # 左侧控制面板
        control_panel = self.create_control_panel()
        content_layout.addWidget(control_panel, 1)

        # 右侧结果显示面板
        result_panel = self.create_result_panel()
        content_layout.addWidget(result_panel, 2)

        # 状态栏
        st_bar = self.statusBar()
        if st_bar:
            st_bar.showMessage("准备就绪")

    def create_control_panel(self):
        """创建控制面板"""
        panel = QGroupBox("控制面板")
        layout = QVBoxLayout()

        # 窗口选择
        window_group = QGroupBox("窗口选择")
        window_layout = QVBoxLayout()

        self.window_combo = QComboBox()
        self.window_combo.setMinimumHeight(40)
        refresh_btn = QPushButton("刷新窗口列表")
        refresh_btn.clicked.connect(self.refresh_windows)
        window_layout.addWidget(refresh_btn)
        window_layout.addWidget(QLabel("选择捕获窗口:"))
        window_layout.addWidget(self.window_combo)

        window_group.setLayout(window_layout)
        layout.addWidget(window_group)

        # 扫描设置
        scan_group = QGroupBox("扫描设置")
        scan_layout = QVBoxLayout()

        scan_layout.addWidget(QLabel("扫描间隔 (毫秒):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(100, 10000)
        self.interval_spin.setValue(self.config["scan_interval"])
        self.interval_spin.setSuffix(" ms")
        scan_layout.addWidget(self.interval_spin)

        scan_group.setLayout(scan_layout)
        layout.addWidget(scan_group)

        # 编辑区域
        edit_group = QGroupBox("编辑区域")
        edit_layout = QVBoxLayout()

        self.hand1_btn = QPushButton("选择手牌1")
        self.hand1_btn.clicked.connect(lambda: self.open_region_editor("card1", "手牌1"))
        edit_layout.addWidget(self.hand1_btn)

        self.hand2_btn = QPushButton("选择手牌2")
        self.hand2_btn.clicked.connect(lambda: self.open_region_editor("card2", "手牌2"))
        edit_layout.addWidget(self.hand2_btn)

        self.board_btn = QPushButton("选择卡池")
        self.board_btn.clicked.connect(lambda: self.open_region_editor("board", "卡池"))
        edit_layout.addWidget(self.board_btn)

        edit_group.setLayout(edit_layout)
        layout.addWidget(edit_group)

        # 控制按钮
        button_layout = QVBoxLayout()

        self.start_btn = QPushButton("开始扫描")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """
        )
        self.start_btn.clicked.connect(self.start_scan)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止扫描")
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #f44336;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """
        )
        self.stop_btn.clicked.connect(self.stop_scan)
        button_layout.addWidget(self.stop_btn)

        layout.addLayout(button_layout)

        # 配置说明
        info_group = QGroupBox("使用说明")
        info_layout = QVBoxLayout()
        info_text = QLabel(
            """
1. 选择要捕获的扑克窗口
2. 设置扫描间隔
3. 点击"开始扫描"
4. 系统将持续识别手牌和牌池
5. 结果实时显示在右侧

注意：首次使用需要安装
        """
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        link_label = QLabel("<a href='https://github.com/tesseract-ocr/tesseract'>Tesseract OCR引擎</a>")
        link_label.setOpenExternalLinks(True)
        info_layout.addWidget(link_label)
        try:
            tesseract_version = subprocess.check_output(["tesseract", "--version"], encoding="utf8").strip().splitlines()[0]
            info_layout.addWidget(QLabel(f"Tesseract版本: {tesseract_version}"))
        except Exception as e:
            info_layout.addWidget(QLabel(f"并且添加到环境PATH"))
            not_install = QLabel(f"Tesseract OCR引擎 未找到\n{e}")
            not_install.setStyleSheet("color: red;")
            info_layout.addWidget(not_install)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        layout.addStretch()
        panel.setLayout(layout)
        return panel

    def create_result_panel(self):
        """创建结果显示面板"""
        panel = QGroupBox("识别结果")
        layout = QVBoxLayout()

        # 时间戳
        self.timestamp_label = QLabel("时间: --:--:--")
        self.timestamp_label.setFont(QFont("Arial", 12, QFont.Bold))
        self.timestamp_label.setStyleSheet("color: #666;")
        layout.addWidget(self.timestamp_label)

        # 牌池区域
        board_group = QGroupBox("牌池 (Board Cards)")
        board_layout = QHBoxLayout()

        self.board_labels = []
        for i in range(5):
            label = self.create_card_label(f"牌池 {i+1}")
            self.board_labels.append(label)
            board_layout.addWidget(label)

        board_group.setLayout(board_layout)
        layout.addWidget(board_group)

        # 手牌区域
        hand_group = QGroupBox("手牌 (Hole Cards)")
        hand_layout = QHBoxLayout()

        self.card1_label = self.create_card_label("手牌 1")
        self.card2_label = self.create_card_label("手牌 2")

        hand_layout.addWidget(self.card1_label)
        hand_layout.addWidget(self.card2_label)
        hand_group.setLayout(hand_layout)
        layout.addWidget(hand_group)

        # 历史记录
        history_group = QGroupBox("历史记录")
        history_layout = QVBoxLayout()

        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setMaximumHeight(150)
        history_layout.addWidget(self.history_text)

        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        panel.setLayout(layout)
        return panel

    def create_card_label(self, title):
        """创建卡片标签"""
        label = QLabel("")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumSize(80, 120)
        label.setStyleSheet(
            """
            QLabel {
                background-color: #f0f0f0;
                border: 2px solid #ccc;
                border-radius: 10px;
                font-size: 18px;
                font-weight: bold;
                color: #333;
            }
        """
        )
        return label

    def refresh_windows(self):
        """刷新窗口列表"""
        self.window_combo.clear()
        self.window_list = []

        def enum_windows(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    self.window_list.append((hwnd, title))

        win32gui.EnumWindows(enum_windows, None)

        # 排序并添加到下拉框
        self.window_list.sort(key=lambda x: x[1])
        first = self.window_combo.currentIndex() < 0
        for hwnd, title in self.window_list:
            self.window_combo.addItem(title, hwnd)
            if first and title in self.config["window_title"]:
                self.window_combo.setCurrentIndex(self.window_combo.count() - 1)

        st_bar = self.statusBar()
        if st_bar:
            st_bar.showMessage(f"找到 {len(self.window_list)} 个窗口")

    def start_scan(self):
        """开始扫描"""
        if self.window_combo.count() == 0:
            QMessageBox.warning(self, "警告", "请先刷新并选择窗口")
            return

        # 获取选中的窗口
        current_index = self.window_combo.currentIndex()
        if current_index < 0:
            QMessageBox.warning(self, "警告", "请选择一个窗口")
            return

        self.current_hwnd = self.window_combo.itemData(current_index)

        # 更新配置
        self.config["scan_interval"] = self.interval_spin.value()

        # 创建并启动工作线程
        self.worker = OCRWorker(self.config)
        self.worker.hwnd = self.current_hwnd
        self.worker.signals.result_updated.connect(self.update_result)
        self.worker.signals.error_occurred.connect(self.handle_error)
        self.worker.start()

        # 更新UI状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.window_combo.setEnabled(False)
        self.interval_spin.setEnabled(False)
        self.hand1_btn.setEnabled(False)
        self.hand2_btn.setEnabled(False)
        self.board_btn.setEnabled(False)
        st_bar = self.statusBar()
        if st_bar:
            st_bar.showMessage("扫描中...")

    def stop_scan(self):
        """停止扫描"""
        if self.worker:
            self.worker.stop()
            self.worker = None

        # 更新UI状态
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.window_combo.setEnabled(True)
        self.interval_spin.setEnabled(True)
        self.hand1_btn.setEnabled(True)
        self.hand2_btn.setEnabled(True)
        self.board_btn.setEnabled(True)
        st_bar = self.statusBar()
        if st_bar:
            st_bar.showMessage("扫描已停止")

    def update_result(self, result):
        """更新识别结果"""
        # 更新时间戳
        self.timestamp_label.setText(f'时间: {result["timestamp"]}')

        # 更新手牌
        hand_cards = result.get("hand_cards", [])
        if len(hand_cards) >= 1:
            if hand_cards[0]:
                self.card1_label.setText(f"{hand_cards[0][0]}{hand_cards[0][1]}")
            else:
                self.card1_label.setText("")

        if len(hand_cards) >= 2:
            if hand_cards[1]:
                self.card2_label.setText(f"{hand_cards[1][0]}{hand_cards[1][1]}")
            else:
                self.card2_label.setText("")

        # 更新牌池
        board_cards = result.get("board_cards", [])
        for i, label in enumerate(self.board_labels):
            if i < len(board_cards) and board_cards[i]:
                label.setText(f"{board_cards[i][0]}{board_cards[i][1]}")
                label.setStyleSheet(
                    """
                    QLabel {
                        background-color: #e3f2fd;
                        border: 2px solid #2196F3;
                        border-radius: 10px;
                        font-size: 18px;
                        font-weight: bold;
                        color: #1565C0;
                    }
                """
                )
            else:
                label.setText("")
                label.setStyleSheet(
                    """
                    QLabel {
                        background-color: #f0f0f0;
                        border: 2px solid #ccc;
                        border-radius: 10px;
                        font-size: 18px;
                        font-weight: bold;
                        color: #333;
                    }
                """
                )

        # 添加历史记录
        hand_str = " | ".join([f"{c[0]}{c[1]}" if c else "??" for c in hand_cards])
        board_str = " ".join([f"{c[0]}{c[1]}" if c else "??" for c in board_cards])
        history_line = f'{result["timestamp"]} - 手牌: {hand_str} | 牌池: {board_str}'
        self.history_text.append(history_line)

        # 限制历史记录数量
        scroll_bar = self.history_text.verticalScrollBar()
        if scroll_bar:
            scroll_bar.setValue(scroll_bar.maximum())

    def handle_error(self, error_msg):
        """处理错误"""
        st_bar = self.statusBar()
        if st_bar:
            st_bar.showMessage(f"错误: {error_msg}")
        self.history_text.append(f"[错误] {error_msg}")

    def open_region_editor(self, region_key, region_name):
        """打开区域编辑器"""
        # 获取选中的窗口
        current_index = self.window_combo.currentIndex()
        if current_index < 0:
            QMessageBox.warning(self, "警告", "请先选择一个窗口")
            return

        hwnd = self.window_combo.itemData(current_index)

        # 将窗口置于前端
        try:
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.5)  # 等待窗口切换
        except Exception as e:
            QMessageBox.warning(self, "警告", f"无法置顶窗口: {str(e)}")
            return

        # 截图
        screenshot = self.capture_window(hwnd)
        if screenshot is None:
            QMessageBox.warning(self, "警告", "截图失败")
            return

        # 打开编辑对话框
        dialog = RegionEditorDialog(self, screenshot, self.config, region_key, region_name)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 保存配置
            updated_config = dialog.get_updated_config()
            self.save_config(updated_config)
            self.config = updated_config
            QMessageBox.information(self, "成功", f"{region_name}区域已保存")
        else:
            QMessageBox.information(self, "提示", "已取消区域编辑")

    def capture_window(self, hwnd):
        """捕获窗口截图"""
        try:
            # 获取窗口位置和尺寸
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top

            # 使用MSS截取
            sct = mss.mss()
            monitor = {"top": top, "left": left, "width": width, "height": height}
            screenshot = sct.grab(monitor)

            # 转换为numpy数组
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            return img

        except Exception as e:
            print(f"截图错误: {str(e)}")
            return None

    def save_config(self, config):
        """保存配置到文件"""
        try:
            with open("config.yaml", "w", encoding="utf-8") as f:
                yaml.safe_dump(config, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            QMessageBox.warning(self, "警告", f"保存配置失败: {str(e)}")

    def closeEvent(self, event):
        """关闭事件"""
        if self.worker:
            self.worker.stop()
        event.accept()

    def showEvent(self, event):
        """窗口激活事件"""
        self.refresh_windows()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = PokerOCRWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
