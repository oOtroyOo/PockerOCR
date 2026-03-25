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
RANK_ORDER = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14}

RANK_NAMES = {2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "T", 11: "J", 12: "Q", 13: "K", 14: "A"}

SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}
# 所有可能的牌
all_suits = ["S", "C", "H", "D"]
all_ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]


class HandResult(NamedTuple):
    """牌型评估结果"""

    name: str  # 牌型名称
    rank: int  # 牌型等级 1-10
    high_card: int  # 最高牌
    kickers: list  # 踢脚牌
    cards: list  # 具体牌组合


class EvaluationResult(NamedTuple):
    """完整评估结果"""

    my_hand: HandResult  # 我的牌型
    my_possible: list[tuple[str, list]]  # 我可能的牌型 [(牌型名, 牌组合), ...]
    opponent_possible: list[tuple[str, list]]  # 对手可能的牌型


def card_to_str(card: tuple) -> str:
    """将牌元组转为字符串 (S, A) -> A♠"""
    if not card or len(card) < 2:
        return "??"
    suit, rank = card
    suit_sym = SUIT_SYMBOLS.get(suit, "?")
    rank_name = RANK_NAMES.get(RANK_ORDER.get(rank, 0), rank)

    return f"<font color={'#ffffff' if (suit =="S" or suit=="C") else '#ff4444'}>{suit_sym}{rank_name}</font>"


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
            # 格式化我的牌型（牌型名 + 关键牌）
            my_hand_str = self._format_hand_name(result.my_hand)

            # 格式化我可能的牌型
            my_possible_str = self._format_possible_hands(result.my_possible)

            # 格式化对手可能的牌型
            opponent_str = self._format_possible_hands(result.opponent_possible)

            self.evaluation_finished.emit(my_hand_str, my_possible_str, opponent_str, history_text)

    def _format_hand_name(self, hand: HandResult) -> str:
        """格式化牌型名称，显示简洁信息"""
        name = hand.name
        high = hand.high_card
        high_name = RANK_NAMES.get(high, "")
        cards_str = cards_to_str(hand.cards)

        # 根据牌型添加详细信息
        if hand.rank == 1:  # 高牌
            return f"{name} {high_name} [{cards_str}]"
        elif hand.rank == 2:  # 一对
            return f"{name} {high_name} [{cards_str}]"
        elif hand.rank == 3:  # 两对
            if hand.kickers and len(hand.kickers) >= 2:
                p1 = RANK_NAMES.get(hand.kickers[0], "")
                p2 = RANK_NAMES.get(hand.kickers[1], "")
                return f"{name} {p1}和{p2} [{cards_str}]"
            return f"{name} [{cards_str}]"
        elif hand.rank == 4:  # 三条
            return f"{name} {high_name} [{cards_str}]"
        elif hand.rank == 5:  # 顺子
            return f"{name} {high_name}高 [{cards_str}]"
        elif hand.rank == 6:  # 同花
            return f"{name} {high_name}高 [{cards_str}]"
        elif hand.rank == 7:  # 葫芦
            return f"{name} {high_name} [{cards_str}]"
        elif hand.rank == 8:  # 四条
            return f"{name} {high_name} [{cards_str}]"
        elif hand.rank == 9:  # 同花顺
            return f"{name} {high_name}高 [{cards_str}]"
        elif hand.rank == 10:  # 皇家同花顺
            return f"{name} [{cards_str}]"

        return f"{name} [{cards_str}]"

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

        return "<br>".join(lines)

    def _full_evaluate(self, hand_cards: list, board_cards: list) -> EvaluationResult:
        """完整评估"""
        # 合并所有牌（过滤空值）
        all_cards = [c for c in hand_cards if c and len(c) >= 2 and c[0] and c[1]] + [c for c in board_cards if c and len(c) >= 2 and c[0] and c[1]]

        # 我的牌型（手牌 + 牌池最佳组合）
        my_hand = self._evaluate_best_hand(all_cards)

        # 获取我可能和对手可能的牌型
        my_possible, opponent_possible = self._get_all_possible_hands(board_cards, hand_cards, my_hand.rank)

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
            cards.sort(key=lambda x: RANK_ORDER.get(x[1], 0), reverse=True)
            return HandResult("皇家同花顺", 10, 14, [], cards)

        # 同花顺
        if is_flush and is_straight:
            cards.sort(key=lambda x: RANK_ORDER.get(x[1], 0), reverse=True)
            return HandResult("同花顺", 9, straight_high, [], cards)

        # 四条
        if count_values == [4, 1]:
            four_rank = [r for r, c in rank_counts.items() if c == 4][0]
            cards.sort(key=lambda x: (1000 + (4 - all_suits.index(x[0]))) if x[1] == four_rank else RANK_ORDER.get(x[1], 0), reverse=True)
            return HandResult("四条", 8, RANK_ORDER.get(four_rank, 0), rank_values, cards)

        # 葫芦
        if count_values == [3, 2]:
            three_rank = [r for r, c in rank_counts.items() if c == 3][0]
            cards.sort(key=lambda x: (1000 + (4 - all_suits.index(x[0]))) if x[1] == three_rank else (RANK_ORDER.get(x[1], 0) * 10 + (4 - all_suits.index(x[0]))), reverse=True)
            return HandResult("葫芦", 7, RANK_ORDER.get(three_rank, 0), rank_values, cards)

        # 同花
        if is_flush:
            cards.sort(key=lambda x: RANK_ORDER.get(x[1], -1), reverse=True)
            return HandResult("同花", 6, rank_values[0], rank_values, cards)

        # 顺子
        if is_straight:
            cards.sort(key=lambda x: RANK_ORDER.get(x[1], -1), reverse=True)
            return HandResult("顺子", 5, straight_high, [], cards)

        # 三条
        if count_values == [3, 1, 1]:
            three_rank = [r for r, c in rank_counts.items() if c == 3][0]
            cards.sort(key=lambda x: (1000 + (4 - all_suits.index(x[0]))) if x[1] == three_rank else (RANK_ORDER.get(x[1], 0) * 10 + (4 - all_suits.index(x[0]))), reverse=True)
            return HandResult("三条", 4, RANK_ORDER.get(three_rank, 0), rank_values, cards)

        # 两对
        if count_values == [2, 2, 1]:
            pairs = sorted([RANK_ORDER.get(r, 0) for r, c in rank_counts.items() if c == 2], reverse=True)
            return HandResult("两对", 3, pairs[0], pairs, cards)

        # 一对
        if count_values == [2, 1, 1, 1]:
            pair_rank = [r for r, c in rank_counts.items() if c == 2][0]
            cards.sort(key=lambda x: (1000 + (4 - all_suits.index(x[0]))) if x[1] == pair_rank else (RANK_ORDER.get(x[1], 0) * 10 + (4 - all_suits.index(x[0]))), reverse=True)
            return HandResult("一对", 2, RANK_ORDER.get(pair_rank, 0), rank_values, cards)

        cards.sort(key=lambda x: RANK_ORDER.get(x[1], 0), reverse=True)
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

    def _get_all_possible_hands(self, board_cards: list, hand_cards: list, my_rank: int) -> tuple[list[tuple[str, list]], list[tuple[str, list]]]:
        """获取所有可能的牌型（我可能 + 对手可能）

        我可能：假设还剩1张河牌未发，计算所有可能达成的牌型（顺子及以上）
        对手可能：基于牌池推断对手可能的牌型（仅显示比我大的）

        Returns:
            (my_possible, opponent_possible)
        """
        # 过滤空值
        board_valid = [c for c in board_cards if c and len(c) >= 2 and c[0] and c[1]]
        hand_valid = [c for c in hand_cards if c and len(c) >= 2 and c[0] and c[1]]

        known_cards = board_valid + hand_valid

        if len(known_cards) < 5:
            return [], []

        # 剩余可用牌（排除已知牌）
        available = []
        for s in all_suits:
            for r in all_ranks:
                card = (s, r)
                if card not in known_cards:
                    available.append(card)

        # ========== 我可能的牌型（还剩1张河牌）==========
        my_possible: dict[str, list] = {}

        if len(known_cards) < 7:
            for river_card in available:
                all_cards = known_cards + [river_card]
                # 从这7张中选5张最佳组合
                for combo in combinations(all_cards, 5):
                    combo_list = list(combo)
                    result = self._evaluate_five_cards(combo_list)

                    # 只统计顺子及以上
                    if result.rank >= 5:
                        if result.name not in my_possible:
                            my_possible[result.name] = []

                        # 去重
                        cards_str = cards_to_str(combo_list)
                        if cards_str not in [cards_to_str(c) for c in my_possible[result.name]]:
                            my_possible[result.name].append(combo_list)
            for name, card_list in my_possible.items():
                card_list.sort(
                    key=lambda cards: sum([(index * 100 + (RANK_ORDER.get(cards[index][1], 0) * 10 + (4 - all_suits.index(cards[index][0])))) for index in range(len(cards))]),
                    reverse=True,
                )

        # ========== 对手可能的牌型（基于牌池+河牌推断）==========
        opponent_possible = {}

        # 策略：遍历河牌，看牌池+河牌能否组成大牌
        # 如果能，则对手用任意两张能补足该牌型的牌即可
        for river_card in available:
            board_with_river = board_valid + [river_card]

            # 从牌池+河牌的7张中选5张，看能组成什么大牌
            for combo in combinations(board_with_river, 5):
                combo_list = list(combo)
                result = self._evaluate_five_cards(combo_list)

                # 只统计比我大的牌型
                if result.rank > my_rank:
                    if result.name not in opponent_possible:
                        opponent_possible[result.name] = []

                    # 检查是否已存在
                    cards_str = cards_to_str(combo_list)
                    if cards_str not in [cards_to_str(c) for c in opponent_possible[result.name]]:
                        # 检查对手能否拿到这个组合（至少2张是未知牌）
                        unknown_in_combo = [c for c in combo_list if c not in board_valid]
                        if len(unknown_in_combo) <= 2:  # 最多需要2张未知牌（对手手牌）
                            opponent_possible[result.name].append(combo_list)

        # 格式化结果
        my_result = []
        for name in sorted(my_possible.keys(), key=lambda x: HAND_RANKS.get(x, 0), reverse=True):
            for cards in my_possible[name][:5]:  # 每种最多5个
                my_result.append((name, cards))

        opponent_result = []
        for name in sorted(opponent_possible.keys(), key=lambda x: HAND_RANKS.get(x, 0), reverse=True):
            for cards in opponent_possible[name][:2]:  # 每种最多2个
                opponent_result.append((name, cards))

        return my_result, opponent_result


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
        self._thread.started.connect(lambda: self._worker.evaluate(hand_cards, board_cards, history_text) if self._worker else None)

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
