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

    def __init__(self, suit: str, rank: str, parent: ManualChooseDialog):
        super().__init__(parent)
        self.suit = suit
        self.rank = rank
        self.card = (suit, rank)
        self.dialog = parent
        # 设置按钮文本
        self.setText(f"{defines.SUIT_SYMBOLS[suit][0]}{rank}")
        # self.setFont(QFont("Arial", 12, QFont.Bold))
        # self.setFixedSize(50, 70)
        # 更新样式
        self.update_style()

    def update_style(self):
        """更新按钮样式"""
        self.setProperty("suitColor", defines.SUIT_SYMBOLS[self.suit][2])

    def set_selected(self, selected: bool):
        """设置选中状态"""
        self.update_style()

    def set_disabled(self, disabled: bool):
        """设置禁用状态（已被其他页签选中）"""
        self.disabled_state = disabled
        if disabled:
            self.setChecked(False)
            self.selected = False
        self.update_style()
        self.setEnabled(not disabled)

    def mousePressEvent(self, event):
        # 左键
        if event.button() == Qt.MouseButton.LeftButton:
            self.setProperty("selected", "hand")
            print("左键按下")
        elif event.button() == Qt.MouseButton.RightButton:
            self.setProperty("selected", "board")
            print("右键按下")
            # 右键默认不触发 clicked，你可以自己发信号/执行逻辑
        elif event.button() == Qt.MouseButton.MiddleButton:
            print("中键按下")
        self.update_style()
        # super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            print("左键松开")
        elif event.button() == Qt.MouseButton.RightButton:
            print("右键松开")

        super().mouseReleaseEvent(event)
