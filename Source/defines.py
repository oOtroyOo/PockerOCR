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

SUIT_SYMBOLS = {"S": ("♠", "黑桃", "black"), "C": ("♣", "梅花", "black"), "H": ("♥", "红桃", "red"), "D": ("♦", "方片", "red")}


# 所有可能的牌
all_suits = [x for x in SUIT_SYMBOLS]
all_ranks = [x for x in RANK_ORDER]
all_ranks.reverse()


@staticmethod
def charToCard(c: str):
    if c == "S":
        return "♠️"
    elif c == "H":
        return "♥️"
    elif c == "C":
        return "♣️"
    elif c == "D":
        return "♦️"
    elif c == "T":
        return "10"
    return c


@staticmethod
def cardToStr(card: tuple[str, str]):
    if not card or len(card) < 2:
        return "??"
    suit, rank = card
    suit_sym = SUIT_SYMBOLS.get(suit, [])[0]
    rank_name = RANK_NAMES.get(RANK_ORDER.get(rank, 0), rank)
    return f"{charToCard(suit_sym)}{charToCard(rank_name)}"


@staticmethod
def cardToStrRichFont(card: tuple[str, str]):
    suit, rank = card
    return f"<font color={'#ffffff' if (suit =="S" or suit=="C") else '#ff4444'}>{cardToStr(card)}</font>"
