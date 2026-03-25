"""
扑克OCR应用程序
功能：窗口捕获、间隔扫描、识别手牌和牌池
"""

import os
import time
import threading
import cv2
import numpy as np
from PyQt5.QtWidgets import (
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
    QMessageBox,
    QDialog,
    QSizePolicy,
    QScrollArea,
)
from PyQt5.QtCore import Qt, pyqtSignal
import win32gui
import yaml
import subprocess
import mss

from OCRWorker import OCRWorker
from RegionEditorDialog import RegionEditorDialog


class PokerOCRWindow(QMainWindow):
    """主窗口"""

    # 定义信号
    training_finished = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        # 连接训练完成信号
        self.training_finished.connect(self.on_training_finished)
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
        self.resize(720, 520)
        self.move(100, 100)

        # 中心部件
        central_widget = QWidget()
        central_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 8, 8, 8)
        central_widget.setLayout(main_layout)

        # 标题
        title_label = QLabel("♠️♥️扑克OCR♣️♦️")
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        main_layout.addWidget(title_label)

        # 分割布局
        content_layout = QHBoxLayout()
        content_layout.setSpacing(8)
        main_layout.addLayout(content_layout, 1)

        # 左侧控制面板
        control_container = QWidget()
        control_container.setMaximumWidth(190)
        control_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        control_panel = self.create_control_panel()
        control_container.setLayout(control_panel)
        content_layout.addWidget(control_container, 0)

        # 右侧结果显示面板
        result_panel = self.create_result_panel()
        content_layout.addLayout(result_panel, 1)

        # 状态栏
        st_bar = self.statusBar()
        if st_bar:
            st_bar.showMessage("准备就绪")

    def refresh_style(self, widget):
        """刷新控件样式，使属性选择器生效"""
        style = widget.style()
        if style:
            style.unpolish(widget)
            style.polish(widget)

    def create_control_panel(self):
        """创建控制面板"""
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        # 窗口选择
        window_group = QGroupBox("窗口选择")
        window_layout = QVBoxLayout()

        self.window_combo = QComboBox()
        # self.window_combo.setMinimumHeight(24)
        refresh_btn = QPushButton("刷新窗口列表")
        refresh_btn.clicked.connect(self.refresh_windows)
        window_layout.addWidget(refresh_btn)
        window_layout.addWidget(QLabel("选择捕获窗口:"))
        window_layout.addWidget(self.window_combo)

        window_group.setLayout(window_layout)
        window_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(window_group)

        # 扫描设置
        scan_group = QGroupBox("扫描间隔设置")
        scan_layout = QVBoxLayout()

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(100, 10000)
        self.interval_spin.setValue(self.config["scan_interval"])
        self.interval_spin.setSuffix(" ms")
        scan_layout.addWidget(self.interval_spin)

        scan_group.setLayout(scan_layout)
        scan_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(scan_group)

        # 编辑区域
        edit_group = QGroupBox("编辑区域")
        edit_layout = QHBoxLayout()
        edit_layout.setSpacing(4)

        self.hand1_btn = QPushButton("手牌1")
        self.hand1_btn.setProperty("editButton", "true")
        self.hand1_btn.clicked.connect(lambda: self.open_region_editor("card1", "手牌1"))
        edit_layout.addWidget(self.hand1_btn)

        self.hand2_btn = QPushButton("手牌2")
        self.hand2_btn.setProperty("editButton", "true")
        self.hand2_btn.clicked.connect(lambda: self.open_region_editor("card2", "手牌2"))
        edit_layout.addWidget(self.hand2_btn)

        self.board_btn = QPushButton("卡池")
        self.board_btn.setProperty("editButton", "true")
        self.board_btn.clicked.connect(lambda: self.open_region_editor("board", "卡池"))
        edit_layout.addWidget(self.board_btn)

        edit_group.setLayout(edit_layout)
        edit_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(edit_group)

        # 控制按钮
        button_widget = QWidget()
        button_layout = QVBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(4)

        self.start_btn = QPushButton("▶ 开始")
        self.start_btn.setProperty("startButton", "true")
        self.start_btn.clicked.connect(self.start_scan)
        self.start_btn.setVisible(os.path.exists("assets/traineddata/poker.traineddata"))
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setProperty("stopButton", "true")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setVisible(os.path.exists("assets/traineddata/poker.traineddata"))
        self.stop_btn.clicked.connect(self.stop_scan)
        button_layout.addWidget(self.stop_btn)

        # 训练按钮
        self.train_btn = QPushButton("🎯 训练")
        self.train_btn.setProperty("trainButton", "true")
        self.train_btn.clicked.connect(self.run_training)
        button_layout.addWidget(self.train_btn)

        button_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(button_widget)

        # 配置说明
        # 获取 Tesseract 版本信息
        try:
            tesseract_version = subprocess.check_output(["tesseract", "--version"], encoding="utf8").strip().splitlines()[0]
            tesseract_status = f"<span style='color: #00d4aa;'>✓ {tesseract_version}</span>"
        except Exception as e:
            tesseract_status = f"<span style='color: #ff6b6b;'>✗ 未找到，需安装并添加到环境PATH</span>"
        scroll_area = QScrollArea()
        scroll_area.setMinimumHeight(120)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        info_text = QLabel(
            f"""
<b>引擎状态</b><br>
{tesseract_status}<br>
首次使用需要安装 <a href='https://github.com/tesseract-ocr/tesseract' style='color: #4dabf7; text-decoration: none;'>Tesseract OCR 引擎</a><br><br>
可根据 assets/images 中的样本图片训练自定义模型，以提高识别精确度<br><br>
例如有无法识别的卡牌，使用游戏录像工具截图，并裁剪图片加入训练
"""
        )
        info_text.setWordWrap(True)
        info_text.setOpenExternalLinks(True)
        info_text.setTextFormat(Qt.TextFormat.RichText)
        info_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(info_text)

        layout.addWidget(scroll_area, 1)
        return layout

    def create_result_panel(self):
        """创建结果显示面板"""
        layout = QVBoxLayout()

        # 牌池区域
        board_group = QGroupBox("牌池")
        board_layout = QHBoxLayout()

        self.board_labels = []
        for i in range(5):
            label = self.create_card_label(f"牌池 {i+1}")
            self.board_labels.append(label)
            board_layout.addWidget(label)

        board_group.setLayout(board_layout)
        board_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(board_group)

        # 手牌区域
        hand_group = QGroupBox("手牌")
        hand_layout = QHBoxLayout()

        self.hand_card_lables = []
        for i in range(2):
            card = self.create_card_label(f"手牌 {i+1}")
            self.hand_card_lables.append(card)
            hand_layout.addWidget(card)
        hand_group.setLayout(hand_layout)
        hand_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(hand_group)

        # 历史记录
        history_group = QGroupBox("程序输出")
        history_layout = QVBoxLayout()

        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        history_layout.addWidget(self.history_text)

        history_group.setLayout(history_layout)
        history_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(history_group, 1)

        return layout

    def create_card_label(self, title):
        """创建卡片标签"""
        label = QLabel("")
        label.setObjectName("cardLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def refresh_windows(self):
        """刷新窗口列表"""
        self.window_combo.clear()
        self.window_list = []

        def enum_windows(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    className = win32gui.GetClassName(hwnd)
                    self.window_list.append((hwnd, title, className))

        win32gui.EnumWindows(enum_windows, None)

        # 排序并添加到下拉框
        self.window_list.sort(key=lambda x: x[1])
        isOpen = self.window_combo.currentIndex() < 0
        for hwnd, title, className in self.window_list:
            self.window_combo.addItem(title, hwnd)
            if isOpen and (title in self.config["window_title"]) and className == "UnityWndClass":
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

    def run_training(self):
        """运行Tesseract模型训练"""
        from trainer import train_tesseract_model, create_config_files
        import shutil

        # 确认对话框
        reply = QMessageBox.question(
            self, "确认训练", "将根据 assets/images 中的图像训练 Tesseract 模型。\n训练可能需要几分钟，是否继续?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # 禁用训练按钮
        self.train_btn.setEnabled(False)
        self.train_btn.setText("训练中...")

        st_bar = self.statusBar()
        if st_bar:
            st_bar.showMessage("开始训练模型...")

        # 在后台线程运行训练
        def training_thread():
            success = False
            message = ""
            try:
                create_config_files()
                success = train_tesseract_model()

                # 清理临时训练目录
                training_dir = "assets/training"
                if os.path.exists(training_dir):
                    shutil.rmtree(training_dir)

                message = "训练成功" if success else "训练失败"
            except Exception as e:
                success = False
                message = f"训练出错: {str(e)}"

            # 发射信号到主线程更新UI
            self.training_finished.emit(success, message)

        thread = threading.Thread(target=training_thread, daemon=True)
        thread.start()

    def on_training_finished(self, success: bool, message: str):
        """训练完成的回调"""
        # 恢复按钮状态
        self.train_btn.setEnabled(True)
        self.train_btn.setText("训练模型")

        # 更新日志
        self.history_text.append("\n" + "=" * 60)
        if success:
            self.history_text.append("训练成功!")
            self.history_text.append("模型文件: assets/traineddata/poker.traineddata")
            self.history_text.append("请重启应用程序以使用新模型")
            QMessageBox.information(self, "训练完成", "模型训练成功!\n请重启应用程序以使用新模型。")
            self.start_btn.setVisible(os.path.exists("assets/traineddata/poker.traineddata"))
            self.stop_btn.setVisible(os.path.exists("assets/traineddata/poker.traineddata"))

        else:
            self.history_text.append(message)
            QMessageBox.warning(self, "训练失败", message)

        # 更新状态栏
        st_bar = self.statusBar()
        if st_bar:
            st_bar.showMessage(message)

    def cardToText(self, c: str):
        if c == "S":
            return "♠️"
        elif c == "H":
            return "♥️"
        elif c == "C":
            return "♣️"
        elif c == "D":
            return "♦️"
        elif c == "T":
            return "10"
        return c

    def get_suit_color(self, suit: str) -> str:
        """获取花色颜色类别: black(黑桃/梅花) 或 red(红桃/方片)"""
        if suit in ("H", "D"):  # 红桃、方片
            return "red"
        return "black"  # 黑桃、梅花或其他

    def update_result(self, result):
        """更新识别结果"""

        # 更新手牌
        hand_cards = result.hand_cards
        if hand_cards:
            for i in range(len(self.hand_card_lables)):
                card_label = self.hand_card_lables[i]

                if len(hand_cards) > i:
                    suit, rank = hand_cards[i]
                    card_label.setText(f"{self.cardToText(suit)}{self.cardToText(rank)}")
                    card_label.setProperty("handCardActive", "true")
                    card_label.setProperty("handCardInactive", "")
                    card_label.setProperty("suitColor", self.get_suit_color(suit))
                else:
                    card_label.setText("")
                    card_label.setProperty("handCardActive", "")
                    card_label.setProperty("handCardInactive", "true")
                    card_label.setProperty("suitColor", "")
                self.refresh_style(card_label)

        # 更新牌池
        board_cards = result.board_cards
        for i, label in enumerate(self.board_labels):
            if board_cards and i < len(board_cards) and board_cards[i]:
                suit, rank = board_cards[i]
                label.setText(f"{self.cardToText(suit)}{self.cardToText(rank)}")
                label.setProperty("boardCardActive", "true")
                label.setProperty("boardCardInactive", "")
                label.setProperty("suitColor", self.get_suit_color(suit))
            else:
                label.setText("")
                label.setProperty("boardCardActive", "")
                label.setProperty("boardCardInactive", "true")
                label.setProperty("suitColor", "")
            self.refresh_style(label)

        # 添加历史记录
        hand_str = " | ".join([f"{self.cardToText(c[0])}{self.cardToText(c[1])}" if c else "??" for c in hand_cards])
        board_str = " ".join([f"{self.cardToText(c[0])}{self.cardToText(c[1])}" if c else "??" for c in board_cards])
        history_line = f"手牌: {hand_str} | 牌池: {board_str}"
        if False:
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
