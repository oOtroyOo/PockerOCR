from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Source.ManualChooseDialog.ManualChooseDialog import ManualChooseDialog  # 仅供类型检查器，不在运行时导入

from PyQt5.QtWidgets import (
    QPushButton,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from Source import defines


class CardButton(QPushButton):
    """单张卡牌按钮"""

    def __init__(self, suit: str | None, rank: int | None, parent: ManualChooseDialog):
        super().__init__(parent)
        self.suit = suit
        self.rank = rank
        self.parentDialog = parent
        if suit and rank:
            self.setCard((suit, rank))

    def setCard(self, card):
        self.card = card
        if self.card:
            # 设置按钮文本
            self.setText(defines.cardToStr(self.card))
        else:
            self.setText("")
        # self.setFont(QFont("Arial", 12, QFont.Bold))
        # self.setFixedSize(50, 70)
        # 更新样式
        self.update_style()

    def update_style(self):
        """更新按钮样式"""
        if self.card is None:
            self.setProperty("suitColor", None)
            self.setProperty("choose", None)
        else:
            self.setProperty("suitColor", defines.SUIT_SYMBOLS[self.card[0]][2])
            if self.card in self.parentDialog.selected_hand:
                self.setProperty("choose", "hand")
            elif self.card in self.parentDialog.selected_board:
                self.setProperty("choose", "board")
            else:
                self.setProperty("choose", None)

        style = self.style()
        if style:
            # style.unpolish(self)
            style.polish(self)
        self.update()

    def mousePressEvent(self, event):
        # print(f"{event.button()}键按下")
        # 左键
        if event.button() == Qt.MouseButton.LeftButton or event.button() == Qt.MouseButton.RightButton:
            if self.card:
                self.parentDialog.on_card_selected(self.card, event.button())
        self.update_style()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # print("左键松开")
            ...
        elif event.button() == Qt.MouseButton.RightButton:
            # print("右键松开")
            ...

        super().mouseReleaseEvent(event)
