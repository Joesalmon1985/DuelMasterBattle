"""Trick-taking shared by Knock-out Whist and Oh Hell: dealing, following suit, who takes the trick, and the villagers' simple play."""

from __future__ import annotations

from typing import Any

from wizard_rts.minigames import cards

SUIT_NAMES = {"s": "spades", "h": "hearts", "d": "diamonds", "c": "clubs"}


def deal(rng: Any, players: int, n: int) -> tuple[list[list[str]], list[str]]:
    d = cards.deck(rng)
    hands = [sorted(d[i * n:(i + 1) * n], key=lambda c: (c[1], cards.rank_value(c))) for i in range(players)]
    return hands, d[players * n:]


def legal(hand: list[str], trick: list[list[Any]], trump: str) -> list[str]:
    """Follow the led suit when able; otherwise anything."""
    if not trick:
        return list(hand)
    led = trick[0][1][1]
    follow = [c for c in hand if c[1] == led]
    return follow or list(hand)


def winner(trick: list[list[Any]], trump: str) -> int:
    """The seat that takes the trick: the highest trump, else the highest card of the led suit."""
    led = trick[0][1][1]

    def strength(card: str) -> tuple[int, int]:
        if card[1] == trump:
            return (2, cards.rank_value(card))
        if card[1] == led:
            return (1, cards.rank_value(card))
        return (0, cards.rank_value(card))

    best = max(trick, key=lambda sc: strength(sc[1]))
    return int(best[0])


def would_win(card: str, trick: list[list[Any]], trump: str) -> bool:
    return winner(trick + [[99, card]], trump) == 99


def bot_play(hand: list[str], trick: list[list[Any]], trump: str, want_win: bool) -> str:
    """Lead the highest card (a trump last); follow with the cheapest winner when a win is wanted, else the lowest card."""
    options = legal(hand, trick, trump)
    by_rank = sorted(options, key=lambda c: (c[1] == trump, cards.rank_value(c)))
    if not trick:
        if want_win:
            non_trump = [c for c in by_rank if c[1] != trump]
            return (non_trump or by_rank)[-1]
        return by_rank[0]
    winners = [c for c in by_rank if would_win(c, trick, trump)]
    if want_win and winners:
        return winners[0]
    losers = [c for c in by_rank if c not in winners]
    return (losers or by_rank)[0]


def bot_trumps(hand: list[str]) -> str:
    counts = {s: sum(1 for c in hand if c[1] == s) for s in "shdc"}
    return max("shdc", key=lambda s: (counts[s], sum(cards.rank_value(c) for c in hand if c[1] == s)))


def likely_tricks(hand: list[str], trump: str) -> int:
    """A rough count for a bid: every trump above a nine, aces and kings in the other suits."""
    n = 0
    for c in hand:
        v = cards.rank_value(c)
        if c[1] == trump and v >= 10:
            n += 1
        elif c[1] != trump and v >= 13:
            n += 1
    return n
