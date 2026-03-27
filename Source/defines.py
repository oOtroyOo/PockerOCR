from typing import Any, Optional

# 牌型等级
HAND_RANKS = {1: "高牌", 2: "一对", 3: "两对", 4: "三条", 5: "顺子", 6: "同花", 7: "葫芦", 8: "四条", 9: "同花顺", 10: "皇家同花顺"}

# 牌面值映射
NUMB_ORDER = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14}

NUMB_NAMES = {2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "T", 11: "J", 12: "Q", 13: "K", 14: "A"}

SUIT_SYMBOLS = {"S": ("♠", "黑桃", "black"), "C": ("♣", "梅花", "black"), "H": ("♥", "红桃", "red"), "D": ("♦", "方片", "red")}


# 所有可能的牌 (suit: str, rank: int)
all_suits = [x for x in SUIT_SYMBOLS]
all_ranks = list(NUMB_ORDER.values())  # [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
all_ranks.reverse()  # [14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
all_cards: list[tuple[str, int]] = [(s, r) for s in all_suits for r in all_ranks]


@staticmethod
def get_suit_color(suit):
    return SUIT_SYMBOLS[suit][2]


@staticmethod
def charToCard(c: str | int):
    if c == "S":
        return "♠️"
    elif c == "H":
        return "♥️"
    elif c == "C":
        return "♣️"
    elif c == "D":
        return "♦️"
    elif c == "T" or c == 10:
        return "10"
    if isinstance(c, int):
        return NUMB_NAMES[c]
    return c


@staticmethod
def cardToStr(card: tuple[str, int]):
    if not card or len(card) < 2:
        return "??"
    suit, rank = card
    suit_sym = SUIT_SYMBOLS.get(suit, [])[0]
    rank_name = NUMB_NAMES.get(rank, str(rank))
    return f"{charToCard(suit_sym)}{charToCard(rank_name)}"


