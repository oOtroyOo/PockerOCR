"""
手动选择牌型对话框
用于手动选择手牌和牌池，进行牌型分析
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QMessageBox, QGridLayout
from typing import Tuple, List

from Source.ManualChooseDialog.CardButton import CardButton
from Source import defines


class ManualChooseDialog(QDialog):
    """手动选择牌型对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_hand: List[Tuple[str, str]] = []  # 手牌
        self.selected_board: List[Tuple[str, str]] = []  # 牌池

        self.setWindowTitle("手动选择牌型")
        # self.resize(900, 700)

        layout = QVBoxLayout()
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

        confirm_btn = QPushButton("确认分析")
        # confirm_btn.setProperty("startButton", "true")
        confirm_btn.clicked.connect(self.on_confirm)
        button_layout.addWidget(confirm_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def SuitSection(self, suit_code: str):
        symbol, name, color = defines.SUIT_SYMBOLS[suit_code]
        self.suit_code = suit_code
        self.symbol = symbol
        self.card_buttons: dict[Tuple[str, str], CardButton] = {}
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
        pass

    def on_card_selected(self, card, active=True):
        pass

    def on_card_deselected(self, card):
        return self.on_card_selected(card, False)

    def on_confirm(self):
        """确认分析"""
        # 验证手牌
        hand_valid, hand_msg = self.hand_page.validate()
        if not hand_valid:
            QMessageBox.warning(self, "提示", hand_msg)
            return

        # 验证牌池（3-5张）
        board_cards = self.board_page.get_selected_cards()
        if len(board_cards) < 3:
            QMessageBox.warning(self, "提示", "牌池至少需要3张牌才能进行牌型分析！")
            return

        # 检查重复牌（理论上不应该出现，因为页签会互相禁用）
        all_cards = self.hand_page.get_selected_cards() + board_cards
        if len(all_cards) != len(set(all_cards)):
            QMessageBox.warning(self, "警告", "存在重复的牌，请检查选择！")
            return

        self.selected_hand = self.hand_page.get_selected_cards()
        self.selected_board = board_cards

        self.accept()

    def clear_all(self):
        pass

    def get_selected_cards(self) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """获取选中的牌
        Returns:
            (手牌列表, 牌池列表)
        """
        return self.selected_hand, self.selected_board
