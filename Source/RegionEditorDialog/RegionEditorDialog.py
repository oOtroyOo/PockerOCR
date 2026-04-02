import cv2
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QDialog, QSlider, QDoubleSpinBox, QFormLayout, QGroupBox  # 新增  # 新增
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPolygonF
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor
import typing


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
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # 图片预览
        self.image_label = ClickableLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.image_label.setMinimumSize(580, 400)
        self.image_label.resize(self.pixmap.width(), self.pixmap.height())
        self.image_label.parent_dialog = self
        self.image_label.set_click_callback(self.on_image_click)
        self.image_label.set_release_callback(self.on_image_release)
        layout.addWidget(self.image_label)

        # 控制面板分组
        control_group = QGroupBox("区域参数")
        form_layout = QFormLayout()
        form_layout.setContentsMargins(8, 8, 8, 8)
        form_layout.setSpacing(8)

        # 区域尺寸控制
        self.x_spin = QDoubleSpinBox()
        self.x_spin.setDecimals(4)
        self.x_spin.setRange(0.001, 0.999)
        self.x_spin.setSingleStep(0.001)
        self.x_spin.setValue(self.region.get("pos", [0, 0])[0])
        self.x_spin.valueChanged.connect(self.on_region_changed)
        form_layout.addRow(QLabel("X中心:"), self.x_spin)

        self.y_spin = QDoubleSpinBox()
        self.y_spin.setDecimals(4)
        self.y_spin.setRange(0.001, 0.999)
        self.y_spin.setSingleStep(0.001)
        self.y_spin.setValue(self.region.get("pos", [0, 0])[1])
        self.y_spin.valueChanged.connect(self.on_region_changed)
        form_layout.addRow(QLabel("Y中心:"), self.y_spin)

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setDecimals(4)
        self.width_spin.setRange(0.001, 0.999)
        self.width_spin.setSingleStep(0.001)
        self.width_spin.setValue(self.region.get("size", [0, 0])[0])
        self.width_spin.valueChanged.connect(self.on_region_changed)
        form_layout.addRow(QLabel("宽度:"), self.width_spin)

        self.height_spin = QDoubleSpinBox()
        self.height_spin.setDecimals(4)
        self.height_spin.setRange(0.001, 0.999)
        self.height_spin.setSingleStep(0.001)
        self.height_spin.setValue(self.region.get("size", [0, 0])[1])
        self.height_spin.valueChanged.connect(self.on_region_changed)
        form_layout.addRow(QLabel("高度:"), self.height_spin)

        # 旋转滑块
        if self.region.get("r", None):
            self.rotation_slider = QSlider(Qt.Orientation.Horizontal)
            self.rotation_slider.setRange(-45, 45)
            self.rotation_slider.setValue(int(self.region["r"]))
            self.rotation_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            self.rotation_slider.setTickInterval(5)
            self.rotation_slider.valueChanged.connect(self.on_rotation_changed)
            self.rotation_label = QLabel(f"{self.region['r']}°")
            rot_layout = QHBoxLayout()
            rot_layout.addWidget(self.rotation_slider)
            rot_layout.addWidget(self.rotation_label)
            form_layout.addRow(QLabel("旋转角度:"), rot_layout)
        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self.reset_region)
        button_layout.addWidget(reset_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save_region)
        button_layout.addWidget(save_btn)
        form_layout.addItem(button_layout)
        control_group.setLayout(form_layout)
        layout.addWidget(control_group)

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

        # 居中对齐：pos为中心点，size为宽高
        cx = int(self.region.get("pos", {})[0] * scaled_w)
        cy = int(self.region.get("pos", {})[1] * scaled_h)
        rw = int(self.region.get("size", {})[0] * scaled_w)
        rh = int(self.region.get("size", {})[1] * scaled_h)
        rotation = self.region.get("r", 0)

        pen = QPen(QColor("#2196F3"), 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        if rotation != 0:
            self.draw_rotated_rect_center(painter, cx, cy, rw, rh, rotation)
        else:
            painter.drawRect(cx - rw // 2, cy - rh // 2, rw, rh)

        # 绘制实线框（用户框选区域或拖拽区域）
        if hasattr(self, "user_region") and self.user_region:
            ucx, ucy, urw, urh = self.user_region
            ucx = int(ucx * scaled_w)
            ucy = int(ucy * scaled_h)
            urw = int(urw * scaled_w)
            urh = int(urh * scaled_h)
            pen.setStyle(Qt.PenStyle.SolidLine)
            pen.setColor(QColor("#f44336"))
            pen.setWidth(3)
            painter.setPen(pen)

            if rotation != 0:
                self.draw_rotated_rect_center(painter, ucx, ucy, urw, urh, rotation)
            else:
                painter.drawRect(ucx - urw // 2, ucy - urh // 2, urw, urh)
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
            cx = (x1 + x2) // 2 - offset_x
            cy = (y1 + y2) // 2 - offset_y

            if rw > 0 and rh > 0:
                pen.setStyle(Qt.PenStyle.SolidLine)
                pen.setColor(QColor("#4CAF50"))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(cx - rw // 2, cy - rh // 2, rw, rh)

        painter.end()

        self.image_label.setPixmap(scaled_pixmap)

    def draw_rotated_rect_center(self, painter, cx, cy, w, h, angle):
        """以中心点绘制旋转的矩形"""
        import math

        angle_rad = math.radians(angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        # 四个角点相对于中心
        corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
        polygon_points = []
        for dx, dy in corners:
            rx = dx * cos_a - dy * sin_a + cx
            ry = dx * sin_a + dy * cos_a + cy
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

            # 居中对齐：计算中心点
            cx = (x1 + x2) / 2 - offset_x
            cy = (y1 + y2) / 2 - offset_y

            # 转换为百分比
            cx_percent = max(0, min(1, cx / scaled_w))
            cy_percent = max(0, min(1, cy / scaled_h))
            region_w_percent = max(0.01, min(0.5, (rw / scaled_w)))
            region_h_percent = max(0.01, min(0.5, (rh / scaled_h)))

            # 更新用户框选区域
            self.user_region = (cx_percent, cy_percent, region_w_percent, region_h_percent)

            # 更新配置区域
            self.region["pos"] = [cx_percent, cy_percent]
            self.region["size"] = [region_w_percent, region_h_percent]
            self.x_spin.setValue(cx_percent)
            self.y_spin.setValue(cy_percent)
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
        self.region["size"] = [self.width_spin.value(), self.height_spin.value()]
        self.region["pos"] = [self.x_spin.value(), self.y_spin.value()]
        self.update_preview()

    def reset_region(self):
        """重置区域"""
        self.region = self.get_current_region()
        if hasattr(self, "rotation_slider") and "r" in self.region:
            self.rotation_slider.setValue(int(self.region["r"]))
        self.x_spin.setValue(self.region.get("pos", [0, 0])[0])
        self.y_spin.setValue(self.region.get("pos", [0, 0])[1])
        self.width_spin.setValue(self.region.get("size", [0, 0])[0])
        self.height_spin.setValue(self.region.get("size", [0, 0])[1])
        if hasattr(self, "user_region"):
            del self.user_region
        self.update_preview()

    def save_region(self):
        """保存区域"""
        # 转换为配置文件格式 {"pos": [x, y], "size": [w, h], "r": rotation}
        region_dict = {
            "pos": [round(self.region["pos"][0], 3), round(self.region["pos"][1], 3)],
            "size": [round(self.region["size"][0], 3), round(self.region["size"][1], 3)],
        }
        if "r" in self.region:
            region_dict["r"] = round(self.region["r"], 2)
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
