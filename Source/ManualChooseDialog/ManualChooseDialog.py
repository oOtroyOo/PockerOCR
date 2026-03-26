from PyQt5.QtWidgets import QDialog, QLabel, QLayout, QSizePolicy, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QMessageBox, QGridLayout
from typing import Tuple, List
from PyQt5.QtCore import Qt
from Source.ManualChooseDialog.CardButton import CardButton
from Source import defines
import random


class ManualChooseDialog(QDialog):
    """手动选择牌型对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_hand: set[Tuple[str, str]] = set()  # 手牌
        self.selected_board: set[Tuple[str, str]] = set()  # 牌池
        self.card_buttons: dict[Tuple[str, str], CardButton] = {}

        self.setWindowTitle("手动选择牌型")
        # self.resize(900, 700)

        layout = QVBoxLayout()

        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        board_layout = QHBoxLayout()
        board_layout.addStretch(0)
        board_layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        self.hand_card_lables: list[QLabel] = []
        for i in range(2):
            card = self.create_card_label()
            self.hand_card_lables.append(card)
            board_layout.addWidget(card)
        board_layout.addSpacing(30)

        self.board_labels: list[QLabel] = []
        for i in range(5):
            label = self.create_card_label()
            self.board_labels.append(label)
            board_layout.addWidget(label)

        layout.addLayout(board_layout)

        # 说明
        layout_group = QGroupBox("使用鼠标 左键选择手牌，右键选择河牌")
        layout.addWidget(layout_group)

        suits_layout = QHBoxLayout()
        self.suit_sections: List[QGroupBox] = []
        for suit_code in defines.SUIT_SYMBOLS:
            # 根据页签类型设置最大选择数
            section = self.SuitSection(suit_code)
            suits_layout.addWidget(section)
            self.suit_sections.append(section)

        layout_group.setLayout(suits_layout)

        # 快速操作按钮
        quick_layout = QHBoxLayout()
        quick_layout.addStretch()

        clear_btn = QPushButton("清空选择")
        clear_btn.setProperty("editButton", "true")
        clear_btn.clicked.connect(self.clear_all)
        quick_layout.addWidget(clear_btn)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("取消")
        # cancel_btn.setProperty("stopButton", "true")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        random_btn = QPushButton("随机选择")
        # random_btn.setProperty("manualButton", "true")
        random_btn.clicked.connect(self.on_random_btn)
        button_layout.addWidget(random_btn)
        button_layout.addSpacing(20)
        confirm_btn = QPushButton("确认分析")
        # confirm_btn.setProperty("startButton", "true")
        confirm_btn.clicked.connect(self.on_confirm)
        button_layout.addWidget(confirm_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def create_card_label(self):
        """创建卡片标签"""
        label = QLabel("")
        label.setObjectName("cardLabel")
        label.setProperty("handCardActive", "true")
        label.setProperty("handCardInactive", "")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def refresh_card_label(self):
        iter_hands = iter(self.selected_hand)
        iter_boards = iter(self.selected_board)
        for label in self.hand_card_lables:
            try:
                card = next(iter_hands)
                label.setText(defines.cardToStr(card))
                label.setProperty("suitColor", defines.get_suit_color(card[0]))
                style = label.style()
                if style:
                    # style.unpolish(self)
                    style.polish(label)
            except:
                label.setText(None)
        for label in self.board_labels:
            try:
                card = next(iter_boards)
                label.setText(defines.cardToStr(card))
                label.setProperty("suitColor", defines.get_suit_color(card[0]))
                style = label.style()
                if style:
                    # style.unpolish(self)
                    style.polish(label)
            except:
                label.setText(None)

    def SuitSection(self, suit_code: str):
        symbol, name, color = defines.SUIT_SYMBOLS[suit_code]
        self.suit_code = suit_code
        self.symbol = symbol
        box = QGroupBox(name)
        layout = QGridLayout()
        layout.setSpacing(6)

        # 创建该花色的所有牌
        for i, rank in enumerate(defines.all_ranks):
            card_btn = CardButton(suit_code, rank, self)
            row = i // 5
            col = i % 5
            layout.addWidget(card_btn, row, col)
            self.card_buttons[(self.suit_code, rank)] = card_btn
        box.setLayout(layout)
        return box

    def on_random_btn(self):
        all_cards = list(defines.all_cards)
        random.shuffle(all_cards)
        self.selected_board.clear()
        self.selected_hand.clear()
        for i in range(2):
            self.selected_hand.add(all_cards.pop())
        for i in range(5):
            self.selected_board.add(all_cards.pop())

        for card_button in self.card_buttons.values():
            card_button.update_style()
        self.refresh_card_label()
        self.update()

    def on_card_selected(self, card, type: Qt.MouseButton, active=True):
        if type == Qt.MouseButton.LeftButton:
            if card in self.selected_board:
                self.selected_board.remove(card)
            if card in self.selected_hand:
                self.selected_hand.remove(card)
            elif len(self.selected_hand) < 2:
                self.selected_hand.add(card)
        elif type == Qt.MouseButton.RightButton:
            if card in self.selected_hand:
                self.selected_hand.remove(card)
            if card in self.selected_board:
                self.selected_board.remove(card)
            elif len(self.selected_board) < 5:
                self.selected_board.add(card)
        self.refresh_card_label()

    def on_confirm(self):
        if len(self.selected_hand) < 2 or len(self.selected_board) < 3:
            QMessageBox.warning(self, "提示", "至少需要 2张手牌 3张河牌")
            return
        self.accept()

    def clear_all(self):
        pass

    def get_selected_cards(self) -> Tuple[set[Tuple[str, str]], set[Tuple[str, str]]]:
        """获取选中的牌
        Returns:
            (手牌列表, 牌池列表)
        """
        return self.selected_hand, self.selected_board
