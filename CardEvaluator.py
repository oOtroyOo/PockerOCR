"""
扑克牌型评估器
异步计算牌型，分析自己和其他玩家可能的牌型
"""

from collections import Counter
from itertools import combinations
from typing import NamedTuple
from PyQt5.QtCore import QObject, pyqtSignal, QThread


# 牌型等级
HAND_RANKS = {
    "高牌": 1,
    "一对": 2,
    "两对": 3,
    "三条": 4,
    "顺子": 5,
    "同花": 6,
    "葫芦": 7,
    "四条": 8,
    "同花顺": 9,
    "皇家同花顺": 10,
}

# 牌面值映射
RANK_ORDER = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "8": 8, "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14
}

RANK_NAMES = {
    2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7",
    8: "8", 9: "9", 10: "T", 11: "J", 12: "Q", 13: "K", 14: "A"
}

SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}


class HandResult(NamedTuple):
    """牌型评估结果"""
    name: str           # 牌型名称
    rank: int           # 牌型等级 1-10
    high_card: int      # 最高牌
    kickers: list       # 踢脚牌
    cards: list         # 具体牌组合


class EvaluationResult(NamedTuple):
    """完整评估结果"""
    my_hand: HandResult                     # 我的牌型
    my_possible: list[tuple[str, list]]     # 我可能的牌型 [(牌型名, 牌组合), ...]
    opponent_possible: list[tuple[str, list]]  # 对手可能的牌型


def card_to_str(card: tuple) -> str:
    """将牌元组转为字符串 (S, A) -> A♠"""
    if not card or len(card) < 2:
        return "??"
    suit, rank = card
    suit_sym = SUIT_SYMBOLS.get(suit, "?")
    rank_name = RANK_NAMES.get(RANK_ORDER.get(rank, 0), rank)
    return f"{rank_name}{suit_sym}"


def cards_to_str(cards: list) -> str:
    """将牌列表转为字符串"""
    return " ".join(card_to_str(c) for c in cards)


class CardEvaluatorWorker(QObject):
    """牌型评估工作线程"""
    
    # 评估完成信号 (我的牌型, 我可能牌型, 对手可能牌型, 历史记录)
    evaluation_finished = pyqtSignal(str, str, str, str)
    
    def __init__(self):
        super().__init__()
        self._is_running = True
    
    def stop(self):
        """停止工作线程"""
        self._is_running = False
    
    def evaluate(self, hand_cards: list, board_cards: list, history_text: str):
        """评估牌型"""
        if not self._is_running:
            return
        
        result = self._full_evaluate(hand_cards, board_cards)
        
        if self._is_running:
            # 格式化我的牌型
            my_hand_str = f"{result.my_hand.name} {cards_to_str(result.my_hand.cards)}"
            
            # 格式化我可能的牌型
            my_possible_str = self._format_possible_hands(result.my_possible)
            
            # 格式化对手可能的牌型
            opponent_str = self._format_possible_hands(result.opponent_possible)
            
            self.evaluation_finished.emit(my_hand_str, my_possible_str, opponent_str, history_text)
    
    def _format_possible_hands(self, possible: list[tuple[str, list]]) -> str:
        """格式化可能牌型列表"""
        if not possible:
            return "无"
        
        lines = []
        current_name = None
        for name, cards in possible:
            if name != current_name:
                lines.append(f"{name}")
                current_name = name
            lines.append(f"    {cards_to_str(cards)}")
        
        return "\n".join(lines)
    
    def _full_evaluate(self, hand_cards: list, board_cards: list) -> EvaluationResult:
        """完整评估"""
        # 合并所有牌
        all_cards = [c for c in hand_cards if c] + [c for c in board_cards if c]
        
        # 我的牌型（手牌 + 牌池最佳组合）
        my_hand = self._evaluate_best_hand(all_cards)
        
        # 我可能的牌型（顺子及以上）
        my_possible = self._get_possible_hands(all_cards, min_rank=5)
        
        # 对手可能的牌型（基于牌池推断）
        opponent_possible = self._get_opponent_possible(board_cards, hand_cards)
        
        return EvaluationResult(my_hand, my_possible, opponent_possible)
    
    def _evaluate_best_hand(self, cards: list) -> HandResult:
        """从所有牌中找出最佳牌型"""
        if len(cards) < 5:
            return HandResult("高牌", 1, 0, [], cards)
        
        # 尝试所有5张牌组合
        best_result = None
        for combo in combinations(cards, 5):
            combo_list = list(combo)
            result = self._evaluate_five_cards(combo_list)
            if best_result is None or self._compare_hands(result, best_result) > 0:
                best_result = result
        
        return best_result or HandResult("高牌", 1, 0, [], cards[:5])
    
    def _evaluate_five_cards(self, cards: list) -> HandResult:
        """评估5张牌的牌型"""
        suits = [c[0] for c in cards]
        ranks = [c[1] for c in cards]
        rank_values = sorted([RANK_ORDER.get(r, 0) for r in ranks], reverse=True)
        
        # 统计
        suit_counts = Counter(suits)
        rank_counts = Counter(ranks)
        
        # 检查同花
        is_flush = len(suit_counts) == 1
        
        # 检查顺子
        is_straight, straight_high = self._check_straight(rank_values)
        
        # 各种牌型判断
        count_values = sorted(rank_counts.values(), reverse=True)
        
        # 皇家同花顺
        if is_flush and is_straight and straight_high == 14:
            return HandResult("皇家同花顺", 10, 14, [], cards)
        
        # 同花顺
        if is_flush and is_straight:
            return HandResult("同花顺", 9, straight_high, [], cards)
        
        # 四条
        if count_values == [4, 1]:
            four_rank = [r for r, c in rank_counts.items() if c == 4][0]
            return HandResult("四条", 8, RANK_ORDER.get(four_rank, 0), rank_values, cards)
        
        # 葫芦
        if count_values == [3, 2]:
            three_rank = [r for r, c in rank_counts.items() if c == 3][0]
            return HandResult("葫芦", 7, RANK_ORDER.get(three_rank, 0), rank_values, cards)
        
        # 同花
        if is_flush:
            return HandResult("同花", 6, rank_values[0], rank_values, cards)
        
        # 顺子
        if is_straight:
            return HandResult("顺子", 5, straight_high, [], cards)
        
        # 三条
        if count_values == [3, 1, 1]:
            three_rank = [r for r, c in rank_counts.items() if c == 3][0]
            return HandResult("三条", 4, RANK_ORDER.get(three_rank, 0), rank_values, cards)
        
        # 两对
        if count_values == [2, 2, 1]:
            pairs = sorted([RANK_ORDER.get(r, 0) for r, c in rank_counts.items() if c == 2], reverse=True)
            return HandResult("两对", 3, pairs[0], pairs, cards)
        
        # 一对
        if count_values == [2, 1, 1, 1]:
            pair_rank = [r for r, c in rank_counts.items() if c == 2][0]
            return HandResult("一对", 2, RANK_ORDER.get(pair_rank, 0), rank_values, cards)
        
        # 高牌
        return HandResult("高牌", 1, rank_values[0], rank_values, cards)
    
    def _check_straight(self, rank_values: list) -> tuple[bool, int]:
        """检查是否为顺子，返回 (是否顺子, 最高牌)"""
        unique_sorted = sorted(set(rank_values), reverse=True)
        
        # A可以作为1使用 (A-2-3-4-5)
        if 14 in unique_sorted:
            unique_sorted.append(1)
        
        for i in range(len(unique_sorted) - 4):
            consecutive = True
            for j in range(4):
                if unique_sorted[i + j] - unique_sorted[i + j + 1] != 1:
                    consecutive = False
                    break
            if consecutive:
                return True, unique_sorted[i]
        
        return False, 0
    
    def _compare_hands(self, h1: HandResult, h2: HandResult) -> int:
        """比较两个牌型，返回 >0 表示 h1 更大"""
        if h1.rank != h2.rank:
            return h1.rank - h2.rank
        
        # 相同牌型比较高牌
        if h1.high_card != h2.high_card:
            return h1.high_card - h2.high_card
        
        # 比较踢脚牌
        for k1, k2 in zip(h1.kickers, h2.kickers):
            if k1 != k2:
                return k1 - k2
        
        return 0
    
    def _get_possible_hands(self, cards: list, min_rank: int = 5) -> list[tuple[str, list]]:
        """获取所有可能的牌型（顺子及以上）"""
        if len(cards) < 5:
            return []
        
        possible = {}  # {牌型名: [牌组合列表]}
        
        for combo in combinations(cards, 5):
            combo_list = list(combo)
            result = self._evaluate_five_cards(combo_list)
            
            if result.rank >= min_rank:
                if result.name not in possible:
                    possible[result.name] = []
                
                # 去重：检查是否已存在相同牌组合
                cards_str = cards_to_str(combo_list)
                if cards_str not in [cards_to_str(c) for c in possible[result.name]]:
                    possible[result.name].append(combo_list)
        
        # 按牌型等级排序
        result = []
        for name in sorted(possible.keys(), key=lambda x: HAND_RANKS.get(x, 0), reverse=True):
            for cards in possible[name]:
                result.append((name, cards))
        
        return result
    
    def _get_opponent_possible(self, board_cards: list, my_cards: list) -> list[tuple[str, list]]:
        """获取对手可能的牌型（基于牌池推断）"""
        board_valid = [c for c in board_cards if c]
        my_cards_valid = [c for c in my_cards if c]
        
        if len(board_valid) < 3:
            return []
        
        # 已知牌（不可用于对手）
        known_cards = set(board_valid + my_cards_valid)
        
        # 所有牌
        all_suits = ["S", "H", "D", "C"]
        all_ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
        
        # 对手可用牌（排除已知牌）
        available = []
        for s in all_suits:
            for r in all_ranks:
                card = (s, r)
                if card not in known_cards:
                    available.append(card)
        
        possible = {}  # {牌型名: [牌组合列表]}
        
        # 对手手牌 + 牌池 的组合
        for hand_combo in combinations(available, 2):
            all_opponent = list(hand_combo) + board_valid
            
            for combo in combinations(all_opponent, 5):
                combo_list = list(combo)
                result = self._evaluate_five_cards(combo_list)
                
                # 只统计顺子及以上
                if result.rank >= 5:
                    if result.name not in possible:
                        possible[result.name] = []
                    
                    cards_str = cards_to_str(combo_list)
                    if cards_str not in [cards_to_str(c) for c in possible[result.name]]:
                        possible[result.name].append(combo_list)
        
        # 按牌型等级排序，每种牌型最多显示3个
        result = []
        for name in sorted(possible.keys(), key=lambda x: HAND_RANKS.get(x, 0), reverse=True):
            for cards in possible[name][:3]:  # 每种牌型最多3个示例
                result.append((name, cards))
        
        return result


class CardEvaluator(QObject):
    """牌型评估器管理类"""
    
    # 评估完成信号 (我的牌型, 我可能牌型, 对手可能牌型, 历史记录)
    evaluation_completed = pyqtSignal(str, str, str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: CardEvaluatorWorker | None = None
        self._is_running = False
    
    def start_evaluation(self, hand_cards: list, board_cards: list, history_text: str):
        """开始异步评估"""
        self.stop()
        
        self._thread = QThread(self)
        self._worker = CardEvaluatorWorker()
        self._worker.moveToThread(self._thread)
        
        self._worker.evaluation_finished.connect(self._on_evaluation_finished)
        self._thread.started.connect(
            lambda: self._worker.evaluate(hand_cards, board_cards, history_text) if self._worker else None
        )
        
        self._is_running = True
        self._thread.start()
    
    def _on_evaluation_finished(self, my_hand: str, my_possible: str, opponent: str, history_text: str):
        """评估完成回调"""
        self.evaluation_completed.emit(my_hand, my_possible, opponent, history_text)
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
                self._thread.wait(500)
            self._thread.deleteLater()
            self._thread = None
    
    def is_running(self) -> bool:
        """检查是否正在评估"""
        return self._is_running and self._thread is not None and self._thread.isRunning()
    
    def cleanup(self):
        """清理所有资源"""
        self.stop()
