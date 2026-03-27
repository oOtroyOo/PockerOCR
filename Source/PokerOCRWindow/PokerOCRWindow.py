"""
扑克OCR应用程序
功能：窗口捕获、间隔扫描、识别手牌和牌池
"""

import Source.defines as defines
from argparse import Namespace
import os
import time
import threading
import cv2
import numpy as np
import requests
from PyQt5.QtWidgets import (
    QLayout,
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
    QApplication,
)
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QUrl
import win32gui
import yaml
import subprocess
import mss

from Source.Model.OCRWorker import OCRWorker
from Source.RegionEditorDialog.RegionEditorDialog import RegionEditorDialog
from Source.Model.CardEvaluator import CardEvaluator
from Source.ManualChooseDialog.ManualChooseDialog import ManualChooseDialog


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
        self.manualChooseDialog = ManualChooseDialog(self)
        # 初始化牌型评估器
        self.hand_evaluator = CardEvaluator(self)
        self.hand_evaluator.evaluation_completed.connect(self.on_evaluation_completed)
        self.hand_evaluator.hand_completed.connect(self.on_hand_completed)

        # 扫描定时器
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.do_single_scan)
        self.is_scanning = False  # 是否正在扫描中
        self.evaluation_pending = False  # 是否有待处理的评估

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
        self.resize(500, 520)

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

        self.manual_btn = QPushButton("👆 自选牌型")
        self.manual_btn.setProperty("manualButton", "true")
        self.manual_btn.clicked.connect(self.manual_choose)
        button_layout.addWidget(self.manual_btn)

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
            self.train_btn.setVisible(True)
        except Exception as e:
            tesseract_status = f"<span style='color: #ff6b6b;'>✗ 未找到，需安装并添加到环境PATH</span>"
            self.train_btn.setVisible(False)
        scroll_area = QScrollArea()
        scroll_area.setMinimumHeight(120)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        info_text = QLabel(
            f"""
<b>引擎状态</b><br>
{tesseract_status}<br>
首次使用需要安装 <a href='https://github.com/tesseract-ocr/tesseract/releases' style='color: #4dabf7; text-decoration: none;'>Tesseract OCR 引擎</a><br><br>
可根据 assets/images 中的样本图片训练自定义模型，以提高识别精确度<br><br>
例如有无法识别的卡牌，使用游戏录像工具截图，并裁剪图片加入训练
"""
        )
        info_text.setWordWrap(True)
        info_text.setOpenExternalLinks(True)
        # info_text.setOpenExternalLinks(False)
        # info_text.linkActivated.connect(self.handle_link)
        info_text.setTextFormat(Qt.TextFormat.RichText)
        info_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(info_text)

        layout.addWidget(scroll_area, 1)
        return layout

    def handle_link(self, link_value):

        try:
            # 从config.yaml获取仓库信息，默认为当前项目
            repo_owner = "tesseract-ocr"
            repo_name = "tesserac"

            # 调用GitHub API获取最新release
            url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            release_data = response.json()

            # 查找exe文件
            exe_url = None
            for asset in release_data.get("assets", []):
                if asset["name"].endswith(".exe"):
                    exe_url = asset["browser_download_url"]
                    break

            if exe_url:
                QDesktopServices.openUrl(exe_url)
            else:
                QMessageBox.warning(self, "提示", "未找到可执行文件(.exe)")

        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "错误", f"网络请求失败: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发生错误: {str(e)}")

    def create_result_panel(self):
        """创建结果显示面板"""
        layout = QVBoxLayout()

        # 牌池区域
        board_group = QGroupBox("牌池")
        board_layout = QHBoxLayout()

        self.board_labels = []
        for i in range(5):
            label = self.create_card_label()
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
            card = self.create_card_label()
            self.hand_card_lables.append(card)
            hand_layout.addWidget(card)
        hand_group.setLayout(hand_layout)
        layout.addWidget(hand_group)

        # 牌型分析显示
        analysis_group = QGroupBox("牌型分析")
        analysis_layout = QVBoxLayout()
        analysis_layout.setSpacing(4)

        # 我的牌型
        self.hand_rank_label = QLabel("我的牌型: --")
        self.hand_rank_label.setObjectName("handRankLabel")
        self.hand_rank_label.setTextFormat(Qt.TextFormat.RichText)
        analysis_layout.addWidget(self.hand_rank_label)

        # 我可能牌型
        analysis_layout.addWidget(QLabel("我可能牌型 (顺子以上)"))
        my_scroll_area = QScrollArea()
        my_scroll_area.setObjectName("possibleScroll")
        my_scroll_area.setMinimumHeight(150)
        my_scroll_area.setWidgetResizable(True)
        my_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        my_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        my_scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.my_possible_label = QLabel()
        self.my_possible_label.setObjectName("possibleLabel")
        self.my_possible_label.setWordWrap(True)
        self.my_possible_label.setTextFormat(Qt.TextFormat.RichText)
        self.my_possible_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        my_scroll_area.setWidget(self.my_possible_label)
        analysis_layout.addWidget(my_scroll_area, 1)

        # 对手可能牌型
        analysis_layout.addWidget(QLabel("对手可能牌型 (顺子以上，比自己大)"))
        opponent_scroll_area = QScrollArea()
        opponent_scroll_area.setObjectName("possibleScroll")
        opponent_scroll_area.setMinimumHeight(150)
        opponent_scroll_area.setWidgetResizable(True)
        opponent_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        opponent_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        opponent_scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.opponent_label = QLabel()
        self.opponent_label.setObjectName("possibleLabel")
        self.opponent_label.setWordWrap(True)
        self.opponent_label.setTextFormat(Qt.TextFormat.RichText)
        self.opponent_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        opponent_scroll_area.setWidget(self.opponent_label)
        analysis_layout.addWidget(opponent_scroll_area, 1)

        analysis_group.setLayout(analysis_layout)
        analysis_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout.addWidget(analysis_group)

        # 上一次结果缓存
        self.last_result_key = None

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

    def create_card_label(self):
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
        self.window_list.sort(key=lambda x: (100 if x[1] in self.config["window_title"] else 0) + (1 if x[2] == "UnityWndClass" else 0),reverse=True)
        isOpen = self.window_combo.currentIndex() < 0
        for hwnd, title, className in self.window_list:
            self.window_combo.addItem(title, hwnd)
            # if isOpen and (title in self.config["window_title"]) and className == "UnityWndClass":
            #     self.window_combo.setCurrentIndex(self.window_combo.count() - 1)

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

        # 开始扫描
        self.is_scanning = True
        # 将窗口置于前端
        win32gui.SetForegroundWindow(self.current_hwnd)
        self.do_single_scan()

    def do_single_scan(self):
        """执行单次扫描"""
        if not self.is_scanning:
            return

        # 创建并启动工作线程
        self.worker = OCRWorker(self.config)
        self.worker.hwnd = self.current_hwnd or 0
        self.worker.signals.result_updated.connect(self.update_result)
        self.worker.signals.error_occurred.connect(self.handle_error)
        self.worker.start()

    def stop_scan(self):
        """停止扫描"""
        self.is_scanning = False
        self.scan_timer.stop()
        self.evaluation_pending = False

        if self.worker:
            self.worker.stop()
            self.worker = None
        # 停止评估
        self.hand_evaluator.stop()

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
        self.last_result_key = None

    def manual_choose(self):
        """手动选择牌型并分析"""

        # 打开手动选择对话框

        if self.manualChooseDialog.exec() == QDialog.DialogCode.Accepted:
            # 获取选中的牌
            hand_cards, board_cards = self.manualChooseDialog.get_selected_cards()
            result = Namespace(hand_cards=list(hand_cards), board_cards=list(board_cards))
            self.last_result_key = None

            QApplication.processEvents()  # 刷新UI

            # 启动牌型评估
            self.evaluation_pending = True
            self.update_result(result)

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

    def on_hand_completed(self, my_hand):
        """牌型评估完成回调"""
        # 更新我的牌型
        self.history_text.append(f"[{my_hand}]")
        self.hand_rank_label.setText(f"我的牌型: {my_hand}")
        QApplication.processEvents()  # 刷新UI

    def on_evaluation_completed(self, my_possible: str, opponent: str, history_text: str):

        # 更新我可能牌型
        self.my_possible_label.setText(my_possible)

        # 更新对手可能牌型
        self.opponent_label.setText(opponent)

        # 添加历史记录
        self.history_text.append(f"{history_text}")

        # 滚动到底部
        scroll_bar = self.history_text.verticalScrollBar()
        if scroll_bar:
            scroll_bar.setValue(scroll_bar.maximum())

        # 评估完成，调度下一次扫描
        self.evaluation_pending = False
        self.schedule_next_scan()

    def schedule_next_scan(self):
        """调度下一次扫描"""
        if self.is_scanning and not self.evaluation_pending:
            interval = self.config.get("scan_interval", 200)
            self.scan_timer.start(interval)

    def closeEvent(self, event):
        """窗口关闭事件，清理资源"""
        # 停止扫描
        self.is_scanning = False
        self.scan_timer.stop()

        # 停止OCR工作线程
        if self.worker:
            self.worker.stop()
            self.worker = None

        # 清理牌型评估器
        if self.hand_evaluator:
            self.hand_evaluator.cleanup()

        event.accept()

    def update_result(self, result):
        """更新识别结果"""

        # print(str(result).replace("Namespace", ""))
        # 更新手牌
        hand_cards = result.hand_cards or []
        for i in range(len(self.hand_card_lables)):
            card_label = self.hand_card_lables[i]

            if len(hand_cards) > i and hand_cards[i] and len(hand_cards[i][0]) > 0 and hand_cards[i][1] is not None and hand_cards[i][1] > 0:
                suit, rank = hand_cards[i]
                rank_str = defines.RANK_NAMES.get(rank, str(rank))
                card_label.setText(f"{defines.charToCard(suit)}{defines.charToCard(rank_str)}")
                card_label.setProperty("handCardActive", "true")
                card_label.setProperty("handCardInactive", "")
                card_label.setProperty("suitColor", defines.get_suit_color(suit))
            else:
                card_label.setText("")
                card_label.setProperty("handCardActive", "")
                card_label.setProperty("handCardInactive", "true")
                card_label.setProperty("suitColor", "")
            self.refresh_style(card_label)

        # 更新牌池
        board_cards = result.board_cards or []
        for i, label in enumerate(self.board_labels):
            if board_cards and i < len(board_cards) and board_cards[i] and len(board_cards[i][0]) > 0 and board_cards[i][1] is not None and board_cards[i][1] > 0:
                suit, rank = board_cards[i]
                rank_str = defines.RANK_NAMES.get(rank, str(rank))
                label.setText(f"{defines.charToCard(suit)}{defines.charToCard(rank_str)}")
                label.setProperty("boardCardActive", "true")
                label.setProperty("boardCardInactive", "")
                label.setProperty("suitColor", defines.get_suit_color(suit))
            else:
                label.setText("")
                label.setProperty("boardCardActive", "")
                label.setProperty("boardCardInactive", "true")
                label.setProperty("suitColor", "")
            self.refresh_style(label)

        if self.is_scanning or self.evaluation_pending:
            # 生成结果 key 用于检测变化
            result_key = str(hand_cards) + str(board_cards)
            result_changed = result_key != self.last_result_key
            self.last_result_key = result_key

            # 计算牌型：结果变化 + 有手牌 + 有3张以上池牌
            valid_hand = len([c for c in hand_cards if c and len(c) >= 2 and c[0] and c[1] is not None and c[1] > 0]) >= 2
            valid_board = len([c for c in board_cards if c and len(c) >= 2 and c[0] and c[1] is not None and c[1] > 0]) >= 3

            if result_changed and valid_hand and valid_board:
                # 显示加载提示
                self.hand_rank_label.setText("正在分析牌型...")
                self.my_possible_label.setText("计算中...")
                self.opponent_label.setText("计算中...")
                # 准备历史记录文本
                hand_str = " | ".join([f"{defines.charToCard(c[0])}{defines.charToCard(defines.RANK_NAMES.get(c[1], str(c[1])))}" if c and len(c) >= 2 and c[0] and c[1] is not None and c[1] > 0 else "??" for c in hand_cards])
                board_str = " ".join([f"{defines.charToCard(c[0])}{defines.charToCard(defines.RANK_NAMES.get(c[1], str(c[1])))}" if c and len(c) >= 2 and c[0] and c[1] is not None and c[1] > 0 else "??" for c in board_cards])

                # 异步评估牌型
                self.evaluation_pending = True
                self.hand_evaluator.start_evaluation(hand_cards, board_cards, f"手牌: {hand_str} | 牌池: {board_str}")
            else:
                # 无需评估，直接调度下一次扫描
                self.schedule_next_scan()

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

    def showEvent(self, event):
        """窗口激活事件"""
        self.refresh_windows()
        event.accept()
