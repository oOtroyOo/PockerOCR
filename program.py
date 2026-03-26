"""
扑克OCR应用程序
功能：窗口捕获、间隔扫描、识别手牌和牌池
"""

import os
import sys
from PyQt5.QtWidgets import (
    QApplication,
)

from Source.PokerOCRWindow.PokerOCRWindow import PokerOCRWindow


def load_stylesheet(app, qss_file_path="styles/style.qss"):
    """从 QSS 文件加载样式表"""
    try:
        # 获取脚本所在目录的绝对路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(script_dir, qss_file_path)

        with open(full_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
        print(f"样式表已加载: {full_path}")
    except FileNotFoundError:
        print(f"样式文件不存在: {qss_file_path}")
    except Exception as e:
        print(f"加载样式失败: {e}")


def main():
    app = QApplication(sys.argv)
    load_stylesheet(app)  # 加载外部样式表
    window = PokerOCRWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
