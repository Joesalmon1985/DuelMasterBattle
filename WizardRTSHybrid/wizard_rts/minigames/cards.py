"""A standard 52-card deck and the poker hand ranking the card games share. A card is a two-character string: rank then suit ("As", "Td", "7c")."""

from __future__ import annotations

import random
from collections import Counter
from itertools import combinations
from typing import Any

RANKS = "23456789TJQKA"
SUITS = "shdc"
RANK_NAMES = {"T": "10", "J": "J", "Q": "Q", "K": "K", "A": "A"}
CATEGORY_NAMES = ["high card", "a pair", "two pair", "three of a kind", "a straight", "a flush", "a full house", "four of a kind", "a straight flush"]


def deck(rng: random.Random) -> list[str]:
    d = [r + s for r in RANKS for s in SUITS]
    rng.shuffle(d)
    return d


def rank_value(card: str) -> int:
    """2..14 (an ace is 14; straights treat it as 1 as well)."""
    return RANKS.index(card[0]) + 2


def card_item(card: str, **extra: Any) -> dict[str, Any]:
    """A card as the client's card widget draws it."""
    return {"id": card, "rank": RANK_NAMES.get(card[0], card[0]), "suit": card[1], **extra}


def card_text(card: str) -> str:
    return RANK_NAMES.get(card[0], card[0]) + {"s": " of spades", "h": " of hearts", "d": " of diamonds", "c": " of clubs"}[card[1]]


def rank5(cards: list[str]) -> tuple:
    """The poker rank of exactly five cards: a tuple that compares correctly (category, then the kickers high to low)."""
    vals = sorted((rank_value(c) for c in cards), reverse=True)
    suits = {c[1] for c in cards}
    counts = Counter(vals)
    by_count = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    flush = len(suits) == 1
    uniq = sorted(set(vals), reverse=True)
    straight_high = 0
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight_high = uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:
            straight_high = 5  # the wheel
    if straight_high and flush:
        return (8, straight_high)
    if by_count[0][1] == 4:
        return (7, by_count[0][0], by_count[1][0])
    if by_count[0][1] == 3 and by_count[1][1] == 2:
        return (6, by_count[0][0], by_count[1][0])
    if flush:
        return (5, *vals)
    if straight_high:
        return (4, straight_high)
    if by_count[0][1] == 3:
        return (3, by_count[0][0], *[v for v in vals if v != by_count[0][0]])
    if by_count[0][1] == 2 and by_count[1][1] == 2:
        return (2, by_count[0][0], by_count[1][0], by_count[2][0])
    if by_count[0][1] == 2:
        return (1, by_count[0][0], *[v for v in vals if v != by_count[0][0]])
    return (0, *vals)


def best_of(cards: list[str]) -> tuple:
    """The best five-card rank among any number of cards (seven in Hold'em)."""
    if len(cards) <= 5:
        return rank5(cards)
    return max(rank5(list(c)) for c in combinations(cards, 5))


def category_name(rank: tuple) -> str:
    return CATEGORY_NAMES[int(rank[0])]
