"""
扑克牌型评估器
异步计算牌型，避免阻塞UI
"""

from collections import Counter
from PyQt5.QtCore import QObject, pyqtSignal, QThread


class CardEvaluatorWorker(QObject):
    """牌型评估工作线程"""
    
    # 评估完成信号
    evaluation_finished = pyqtSignal(str, str)  # (牌型, 历史记录文本)
    
    def __init__(self):
        super().__init__()
        self._is_running = True
    
    def stop(self):
        """停止工作线程"""
        self._is_running = False
    
    def evaluate(self, hand_cards: list, board_cards: list, history_text: str):
        """
        评估牌型
        :param hand_cards: 手牌列表 [(花色, 点数), ...]
        :param board_cards: 牌池列表 [(花色, 点数), ...]
        :param history_text: 用于历史记录的文本
        """
        if not self._is_running:
            return
        
        hand_rank = self._evaluate_hand(hand_cards, board_cards)
        
        if self._is_running:
            self.evaluation_finished.emit(hand_rank, history_text)
    
    def _evaluate_hand(self, hand_cards: list, board_cards: list) -> str:
        """
        评估扑克牌型
        返回牌型名称，如 "同花顺"、"四条" 等
        """
        # 合并手牌和牌池
        all_cards = [c for c in hand_cards if c] + [c for c in board_cards if c]
        if len(all_cards) < 5:
            return "--"
        
        # 牌面值映射（用于排序和比较）
        rank_order = {
            "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
            "8": 8, "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14
        }
        
        # 提取花色和点数
        suits = [c[0] for c in all_cards]
        ranks = [c[1] for c in all_cards]
        rank_values = [rank_order.get(r, 0) for r in ranks]
        
        # 统计
        suit_counts = Counter(suits)
        rank_counts = Counter(ranks)
        
        # 检查同花（5张以上同花色）
        flush_suit = None
        for suit, count in suit_counts.items():
            if count >= 5:
                flush_suit = suit
                break
        
        # 检查顺子
        def find_straight(values: list) -> int:
            """找到最大顺子，返回最高牌点数，0表示无顺子"""
            unique_sorted = sorted(set(values), reverse=True)
            # A可以当1用
            if 14 in unique_sorted:
                unique_sorted.append(1)
            for i in range(len(unique_sorted) - 4):
                consecutive = True
                for j in range(4):
                    if unique_sorted[i + j] - unique_sorted[i + j + 1] != 1:
                        consecutive = False
                        break
                if consecutive:
                    return unique_sorted[i]
            return 0
        
        straight_high = find_straight(rank_values)
        
        # 同花顺检查
        if flush_suit:
            flush_cards = [c for c in all_cards if c[0] == flush_suit]
            flush_values = [rank_order.get(c[1], 0) for c in flush_cards]
            flush_straight_high = find_straight(flush_values)
            if flush_straight_high:
                # 皇家同花顺（A高同花顺）
                if flush_straight_high == 14:
                    return "皇家同花顺"
                return "同花顺"
        
        # 四条
        if 4 in rank_counts.values():
            return "四条"
        
        # 葫芦（三条+一对）
        has_three = 3 in rank_counts.values()
        has_pair = 2 in rank_counts.values()
        pairs_count = list(rank_counts.values()).count(2)
        if has_three and (has_pair or pairs_count >= 2):
            return "葫芦"
        
        # 同花
        if flush_suit:
            return "同花"
        
        # 顺子
        if straight_high:
            return "顺子"
        
        # 三条
        if has_three:
            return "三条"
        
        # 两对
        if pairs_count >= 2:
            return "两对"
        
        # 一对
        if has_pair:
            return "一对"
        
        return "高牌"


class CardEvaluator(QObject):
    """
    牌型评估器管理类
    负责创建和管理评估线程
    """
    
    # 评估完成信号
    evaluation_completed = pyqtSignal(str, str)  # (牌型, 历史记录文本)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: CardEvaluatorWorker | None = None
        self._is_running = False
    
    def start_evaluation(self, hand_cards: list, board_cards: list, history_text: str):
        """
        开始异步评估
        :param hand_cards: 手牌列表
        :param board_cards: 牌池列表
        :param history_text: 历史记录文本
        """
        # 如果有正在进行的评估，先停止
        self.stop()
        
        # 创建新线程
        self._thread = QThread(self)
        self._worker = CardEvaluatorWorker()
        self._worker.moveToThread(self._thread)
        
        # 连接信号
        self._worker.evaluation_finished.connect(self._on_evaluation_finished)
        self._thread.started.connect(
            lambda: self._worker.evaluate(hand_cards, board_cards, history_text) if self._worker else None
        )
        
        # 启动线程
        self._is_running = True
        self._thread.start()
    
    def _on_evaluation_finished(self, hand_rank: str, history_text: str):
        """评估完成回调"""
        self.evaluation_completed.emit(hand_rank, history_text)
        # 完成后自动停止线程
        self.stop()
    
    def stop(self):
        """停止评估并清理资源"""
        self._is_running = False
        
        if self._worker:
            self._worker.stop()
            self._worker.deleteLater()
            self._worker = None
        
        if self._thread:
            if self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(500)  # 等待最多500ms
            self._thread.deleteLater()
            self._thread = None
    
    def is_running(self) -> bool:
        """检查是否正在评估"""
        return self._is_running and self._thread is not None and self._thread.isRunning()
    
    def cleanup(self):
        """清理所有资源"""
        self.stop()
