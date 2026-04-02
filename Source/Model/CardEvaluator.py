"""
扑克牌型评估器
异步计算牌型，分析自己和其他玩家可能的牌型
"""

from collections import Counter
from concurrent.futures import as_completed
from itertools import combinations
from typing import NamedTuple
import typing
from PyQt5.QtCore import QObject, pyqtSignal, QThread
import os
from typing import Optional
from Source import defines
from concurrent.futures import ThreadPoolExecutor

MAX_COMBOS = 5000


class HandResult(NamedTuple):
    """牌型评估结果"""

    rank: int  # 牌型等级 1-10
    high_card: int  # 最高牌
    kickers: list  # 踢脚牌
    cards: list[tuple[str, int]]  # 具体牌组合

    def get_rank_name(self):
        return defines.HAND_RANKS.get(self.rank, "")


class EvaluationResult(NamedTuple):
    """完整评估结果"""

    my_hand: HandResult  # 我的牌型
    my_possible: list[tuple[int, list[tuple[str, int]]]]  # 我可能的牌型 [(牌型名, 牌组合), ...]
    opponent_possible: list[tuple[int, list[tuple[str, int]]]]  # 对手可能的牌型


@staticmethod
def cardToStrRichFont(card: tuple[str, int], known: bool):
    if not card or len(card) < 2:
        return "??"
    suit, rank = card
    return f"<font color={"#3F3F3F" if known else ('#ffffff' if (suit =="S" or suit=="C") else '#ff4444')}>{defines.cardToStr(card)}</font>"


def cards_to_str(cards: list, known_cards: Optional[list[tuple[str, int]]] = None) -> str:
    """将牌列表转为字符串"""
    return " ".join(cardToStrRichFont(c, (known_cards and c in known_cards)) for c in cards)


class CardEvaluatorWorker(QObject):
    """牌型评估工作线程"""

    # 评估完成信号 (我的牌型, 我可能牌型, 对手可能牌型, 历史记录)
    evaluation_finished = pyqtSignal(str, str, str)
    hand_finished = pyqtSignal(str)

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
        known_cards = board_cards + hand_cards
        try:
            result = self._full_evaluate(hand_cards, board_cards)

            if self._is_running:
                # 格式化我可能的牌型
                my_possible_str = self._format_possible_hands(result.my_possible, known_cards)

                # 格式化对手可能的牌型
                opponent_str = self._format_possible_hands(result.opponent_possible, known_cards)

                self.evaluation_finished.emit(my_possible_str, opponent_str, history_text)
        except Exception:
            # 发生异常时发送空结果，避免UI卡死
            if self._is_running:
                self.evaluation_finished.emit("评估失败", "无法计算", "无法计算", history_text)

    def _format_hand_name(self, hand: HandResult) -> str:
        """格式化牌型名称，显示简洁信息"""
        name = hand.get_rank_name()
        high = hand.high_card
        high_name = defines.charToCard(hand.high_card)
        cards_str = cards_to_str(hand.cards)

        # 根据牌型添加详细信息
        if hand.rank == 1:  # 高牌
            return f"{name} {high_name} [{cards_str}]"
        elif hand.rank == 2:  # 一对
            return f"{name} {high_name} [{cards_str}]"
        elif hand.rank == 3:  # 两对
            if hand.kickers and len(hand.kickers) >= 2:
                p1 = defines.NUMB_NAMES.get(hand.kickers[0], "")
                p2 = defines.NUMB_NAMES.get(hand.kickers[1], "")
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

    def _format_possible_hands(self, possible: list[tuple[int, list[tuple[str, int]]]], known_cards: list[tuple[str, int]]) -> str:
        """格式化可能牌型列表"""
        if not possible:
            return "无"

        lines = []
        current_rank = None
        for rank, cards in possible:
            if rank != current_rank:
                lines.append(defines.HAND_RANKS.get(rank, None))
                current_rank = rank
            lines.append(f"    {cards_to_str(cards,known_cards)}")

        return "<br>".join(lines)

    def _full_evaluate(self, hand_cards: list, board_cards: list) -> EvaluationResult:
        """完整评估"""
        # 合并所有牌（过滤空值）
        all_cards = [c for c in hand_cards if c and len(c) >= 2 and c[0] and c[1] is not None] + [c for c in board_cards if c and len(c) >= 2 and c[0] and c[1] is not None]

        # 我的牌型（手牌 + 牌池最佳组合）
        my_hand = self._evaluate_best_hand(all_cards)
        # 格式化我的牌型（牌型名 + 关键牌）
        my_hand_str = self._format_hand_name(my_hand)
        self.hand_finished.emit(my_hand_str)
        # 获取我可能和对手可能的牌型
        my_possible, opponent_possible = self._get_all_possible_hands(board_cards, hand_cards, my_hand)

        return EvaluationResult(my_hand, my_possible, opponent_possible)

    def _evaluate_best_hand(self, cards: list[tuple[str, int]]) -> HandResult:
        """从所有牌中找出最佳牌型"""
        # 尝试所有5张牌组合
        best_result = None

        result = self._evaluate_cards_static(cards, False)
        if best_result is None or self._compare_hands(result, best_result) > 0:
            best_result = result

        return best_result or HandResult(1, 0, [], cards[:5])

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

    def _get_all_possible_hands(
        self, board_cards: list, hand_cards: list, my_hand: HandResult
    ) -> tuple[list[tuple[int, list[tuple[str, int]]]], list[tuple[int, list[tuple[str, int]]]]]:
        """获取所有可能的牌型（我可能 + 对手可能）

        我可能：假设还剩1张河牌未发，计算所有可能达成的牌型（顺子及以上）
        对手可能：基于牌池推断对手可能的牌型（仅显示比我大的）

        Returns:
            (my_possible, opponent_possible)
        """
        # 过滤空值
        board_cards = [c for c in board_cards if c and len(c) >= 2 and c[0] and c[1] is not None]
        hand_cards = [c for c in hand_cards if c and len(c) >= 2 and c[0] and c[1] is not None]

        known_cards = board_cards + hand_cards

        if len(known_cards) < 5:
            return [], []

        # 剩余可用牌（排除已知牌）
        available = []
        for s in defines.all_suits:
            for r in defines.all_ranks:
                card = (s, r)
                if card not in known_cards:
                    available.append(card)

        # ========== 我可能的牌型（还剩1张河牌）==========
        my_possible: dict[int, list] = {}

        if len(known_cards) < 7:
            # 使用多线程并行计算我可能的牌型
            my_combos = list(combinations(available, 5 - len(board_cards)))
            my_results = self._parallel_evaluate_combos(my_combos, known_cards, 5, None, is_opponent=False)

            for result in my_results:
                if result.rank not in my_possible:
                    my_possible[result.rank] = []
                cards_str = cards_to_str(result.cards)
                if cards_str not in [cards_to_str(c) for c in my_possible[result.rank]]:
                    my_possible[result.rank].append(result.cards)

            # 排序
            for name, card_list in my_possible.items():
                card_list.sort(
                    key=lambda cards: sum([(index * 100 + (cards[index][1] * 10 + (4 - defines.all_suits.index(cards[index][0])))) for index in range(len(cards))]),
                    reverse=True,
                )

        # ========== 对手可能的牌型（基于牌池+河牌推断）==========
        opponent_possible: dict[int, list] = {}

        # 使用多线程并行计算对手可能的牌型
        opponent_combos = list(combinations(available, 7 - len(board_cards)))
        opponent_results = self._parallel_evaluate_combos(opponent_combos, board_cards, 5, my_hand, is_opponent=True)

        for result in opponent_results:
            if result.rank not in opponent_possible:
                opponent_possible[result.rank] = []

            all_same = False
            for card_list in opponent_possible[result.rank]:
                if len(card_list) == len(result.cards):
                    for index in range(len(card_list)):
                        if card_list[index] == card_list[index]:
                            if index == len(card_list):
                                all_same = True
                            break
            if not all_same:
                opponent_possible[result.rank].append(result.cards)

        # 格式化结果
        my_result = []
        for name in sorted(my_possible.keys(), reverse=True):
            for cards in my_possible[name][:5]:  # 每种最多5个
                my_result.append((name, cards))

        opponent_result = []
        for name in sorted(opponent_possible.keys(), reverse=True):
            for cards in opponent_possible[name][:2]:  # 每种最多2个
                opponent_result.append((name, cards))

        return my_result, opponent_result

    def _parallel_evaluate_combos(self, combos: list, base_cards: list, min_rank: int, my_hand: typing.Optional[HandResult], is_opponent: bool) -> list[HandResult]:
        """评估牌型组合（使用多线程，因为任务粒度小，进程开销更大）

        Args:
            combos: 未知牌组合列表
            base_cards: 基础牌（手牌+牌池 或 仅牌池）
            min_rank: 最小牌型等级
            my_rank: 我的当前牌型等级
            is_opponent: 是否对手计算

        Returns:
            符合条件的牌型结果列表
        """
        results = []

        # 如果组合数量太大，限制处理数量以避免长时间阻塞
        if len(combos) > MAX_COMBOS:
            combos = combos[:MAX_COMBOS]

        # 对于小批量，直接同步执行更快
        if len(combos) < 100:
            return self._evaluate_batch(combos, base_cards, min_rank, my_hand, is_opponent)


        cpu_count = os.cpu_count() or 4
        max_workers = min(4, cpu_count)

        # 将任务分批处理
        batch_size = max(1, len(combos) // max_workers)
        batches = [combos[i : i + batch_size] for i in range(0, len(combos), batch_size)]

        # 使用线程池（对于小任务粒度，线程比进程开销小）
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有批次的任务
            future_to_batch = {executor.submit(self._evaluate_batch, batch, base_cards, min_rank, my_hand, is_opponent): batch for batch in batches}

            # 收集结果
            for future in as_completed(future_to_batch, timeout=10):  # 10秒超时
                try:
                    batch_results = future.result()
                    results.extend(batch_results)
                except Exception:
                    # 处理异常，继续执行
                    pass

        return results

    @staticmethod
    def _evaluate_batch(batch: list[tuple], base_cards: list, min_rank: int, my_hand: typing.Optional[HandResult], is_opponent: bool) -> list[HandResult]:
        """评估一批组合（静态方法，用于多进程）

        Args:
            batch: 一批未知牌组合
            base_cards: 基础牌
            min_rank: 最小牌型等级
            my_rank: 我的当前牌型等级
            is_opponent: 是否对手计算

        Returns:
            该批次中符合条件的牌型结果列表
        """
        batch_results = []
        seen = set()  # 用于去重
        for combo_unknown in batch:
            cards7 = base_cards + list(combo_unknown)

            # 评估牌型
            result = CardEvaluatorWorker._evaluate_cards_static(cards7)
            if not result:
                continue
            # 检查条件
            if result.rank < min_rank:
                continue
            if is_opponent:
                if my_hand:
                    if result.rank < my_hand.rank:
                        continue
                    elif result.rank == my_hand.rank:
                        skip = False
                        for i in range(min(len(my_hand.cards), len(result.cards))):
                            if my_hand.cards[i][1] > result.cards[i][1]:
                                skip = True
                                break
                        if skip:
                            continue

            # 去重检查
            cards_str = " ".join(f"{c[0]}{c[1]}" for c in result.cards)
            if cards_str in seen:
                continue
            seen.add(cards_str)

            batch_results.append(result)

        return batch_results

    @staticmethod
    def _evaluate_cards_static(cards: list[tuple[str, int]], skip_min=False) -> HandResult:
        """
        Args:
            cards: 7张牌的列表

        Returns:
            HandResult 牌型评估结果
        """
        suits = [c[0] for c in cards]
        ranks = [c[1] for c in cards]

        # 统计
        suit_counts = Counter(suits)
        rank_counts = Counter(ranks)

        # 定义排序key函数
        num_sort = lambda x: x[1]  # rank 已经是 int
        suit_sort = lambda x: 4 - defines.all_suits.index(x[0])

        # 四条
        if any([x == 4 for x in rank_counts.values()]):
            four_rank = [r for r, c in rank_counts.items() if c == 4][0]
            cards.sort(key=lambda x: (1000 + suit_sort(x)) if x[1] == four_rank else num_sort(x), reverse=True)
            return HandResult(8, four_rank, ranks, cards[:5])

        cards.sort(key=num_sort, reverse=True)

        # 检查同花
        is_flush = next((x for x in suit_counts if suit_counts[x] >= 5), None)
        flush_cards = None
        flush_high = None
        if is_flush:
            flush_cards = CardEvaluatorWorker._check_flush_static(is_flush, cards)
            if flush_cards:
                flush_high = flush_cards[0][1]
                straight_flush = CardEvaluatorWorker._check_straight_static(flush_cards)
                # 同花顺 (A-2-3-4-5 顺子中 A 作为 1)
                if straight_flush:
                    if len(straight_flush) >= 5:
                        straight_high = straight_flush[0][1]
                        # 皇家同花顺 10
                        return HandResult(10 if straight_high == 14 else 9, straight_high, [], straight_flush[:5])

        # 各种牌型判断
        count_values = sorted(rank_counts.values(), reverse=True)
        three_count = [x == 3 for x in count_values].count(True)
        two_count = [x == 2 for x in count_values].count(True)

        # 葫芦
        if three_count > 0 and (three_count > 1 or two_count > 0):
            three_rank = next(r for r, c in rank_counts.items() if c == 3)
            cards.sort(
                key=lambda x: ((num_sort(x) * 100 * rank_counts[x[1]] + suit_sort(x)) if x[1] in rank_counts else (num_sort(x) * 10 + suit_sort(x))),  # 两个
                reverse=True,
            )  # 撒排
            return HandResult(7, three_rank, ranks, cards[:5])

        # 同花
        if is_flush and flush_cards and flush_high:
            return HandResult(6, flush_high, ranks, flush_cards[:5])

        # 检查顺子 (A-2-3-4-5 顺子中 A 作为 1)
        straight_cards = CardEvaluatorWorker._check_straight_static(cards)
        if straight_cards:
            straight_high = straight_cards[0][1]
            if straight_high and straight_cards:
                return HandResult(5, straight_high, [], straight_cards[:5])

        if skip_min:
            return None  # type: ignore

        # 三条
        if three_count > 0:
            three_rank = [r for r, c in rank_counts.items() if c == 3][0]
            cards.sort(key=lambda x: (1000 + suit_sort(x)) if x[1] == three_rank else (num_sort(x) * 10 + suit_sort(x)), reverse=True)
            return HandResult(4, three_rank, ranks, cards[:5])
        # 两对
        if two_count >= 2:
            pairs = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
            cards.sort(key=lambda x: num_sort(x) * (1000 if num_sort(x) in pairs else 10) + suit_sort(x), reverse=True)
            return HandResult(3, pairs[0], pairs, cards[:5])

        # 一对
        if two_count == 1:
            pair_rank = [r for r, c in rank_counts.items() if c == 2][0]
            cards.sort(key=lambda x: (1000 + suit_sort(x)) if x[1] == pair_rank else (num_sort(x) * 10 + suit_sort(x)), reverse=True)
            return HandResult(2, pair_rank, ranks, cards[:5])

        # 高牌
        return HandResult(1, ranks[0], ranks, cards[:5])

    @staticmethod
    def _check_flush_static(is_flush, cards: list[tuple[str, int]]) -> Optional[list[tuple[str, int]]]:
        result: list[tuple[str, int]] = []
        for card in cards:
            suit = card[0]
            if suit == is_flush:
                result.append(card)
        if len(result) >= 5:
            return result
        return None

    @staticmethod
    def _check_straight_static(cards: list[tuple[str, int]]) -> Optional[list[tuple[str, int]]]:
        """静态方法版本的 _check_straight（用于多进程）

        Args:
            rank_values: 牌面值列表

        Returns:
            (是否顺子, 最高牌)
        """

        # A可以作为1使用 (5-4-3-2-A)
        A = None
        result: list[tuple[str, int]] = []
        for i in range(len(cards) - 3):
            result.clear()
            result.append(cards[i])
            if cards[i][1] == 14 and A is None:
                A = cards[i]
            for j in range(i + 1, len(cards)):
                pre_suit, pre_num = result[-1]
                cur_suit, cur_num = cards[j]
                if cur_num == pre_num:
                    pass
                elif cur_num + 1 == pre_num:
                    result.append(cards[j])
                else:
                    break

            if A and result[-1][1] == 2:
                result.append(A)

            if len(result) >= 5:
                return result

            if not A and i == len(cards) - 4:
                break
        return None


class CardEvaluator(QObject):
    """牌型评估器管理类"""

    # 评估完成信号 (我的牌型, 我可能牌型, 对手可能牌型, 历史记录)
    hand_completed = pyqtSignal(str)
    evaluation_completed = pyqtSignal(str, str, str)

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

        self._worker.hand_finished.connect(lambda my_hand: self.hand_completed.emit(my_hand))
        self._worker.evaluation_finished.connect(self._on_evaluation_finished)

        # 使用函数引用而不是 lambda，避免延迟执行
        def start_work():
            if self._worker and self._is_running:
                self._worker.evaluate(hand_cards, board_cards, history_text)

        self._thread.started.connect(start_work)

        self._is_running = True
        self._thread.start()

    def _on_evaluation_finished(self, my_possible: str, opponent: str, history_text: str):
        """评估完成回调"""
        self.evaluation_completed.emit(my_possible, opponent, history_text)
        self.stop()

    def stop(self):
        """停止评估并清理资源"""
        self._is_running = False

        # 先停止 worker
        if self._worker:
            self._worker.stop()

        # 再停止线程
        if self._thread:
            if self._thread.isRunning():
                self._thread.quit()
                if not self._thread.wait(1000):  # 最多等待1秒
                    self._thread.terminate()
                    self._thread.wait(500)
            self._thread.deleteLater()
            self._thread = None

        # 最后清理 worker
        if self._worker:
            self._worker.deleteLater()
            self._worker = None

    def is_running(self) -> bool:
        """检查是否正在评估"""
        return self._is_running and self._thread is not None and self._thread.isRunning()

    def cleanup(self):
        """清理所有资源"""
        self.stop()
