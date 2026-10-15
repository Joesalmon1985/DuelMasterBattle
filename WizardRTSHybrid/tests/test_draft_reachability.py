"""Over many seeded draft-only games on the real dealer: every card is dealt, every entity of every era is reachable somewhere in the world, each
seat's first pack holds a card it can use that the era needs, and a sensible drafter ends each era able to build what the era requires."""
import os
import random
import statistics

from wizard_rts import draft
from wizard_rts.content import cards as C
from wizard_rts.world import HybridWorld

CS = C.generate()
SEEDS = range(1, 9)


def smart(pack, held, tribe, era):
    have = set()
    for c in held:
        if CS[c]["era"] == era and C.usable_by(CS[c], tribe):
            have |= C.card_tags(CS[c])
    req = C.REQUIRED[era]

    def key(c):
        cd = CS[c]
        use = C.usable_by(cd, tribe)
        new = [t for t in req if t in C.card_tags(cd) and t not in have] if use else []
        return (min((req.index(t) for t in new), default=99), -len(new), not use, -len(cd["slots"]) if use else 0, c)

    return min(pack, key=key)


def play(seed):
    w = HybridWorld(seed, profile="developer")
    w.ai_enabled = False
    held = {f: set() for f in w.faction_info}
    out = {}
    for era in range(4):
        w.era_index = era
        st = draft.state(w)
        st["round"] = draft.ROUNDS
        draft.deal(w, era)
        dealt = {c for p in st["packs"].values() for c in p}
        first = {f: list(st["packs"][f]) for f in st["ring"]}
        for _ in range(draft.ROUNDS):
            for f in st["ring"]:
                pack = [c for c in st["packs"].get(f, []) if c not in held[f]]
                if pack:
                    pick = smart(pack, held[f], w.faction_info[f]["tribe"], era)
                    st["packs"][f].remove(pick)
                    held[f].add(pick)
            draft.pass_packs(w)
        picked = {c for h in held.values() for c in h if CS[c]["era"] == era}
        ents = {e for c in picked for e in CS[c]["entities"]}
        every = {e for c in CS.values() if c["era"] == era for e in c["entities"]}
        out[era] = {
            "dealt": len(dealt), "missing_entities": len(every - ents),
            "ready": [not C.missing(held[f], w.faction_info[f]["tribe"], era) for f in st["ring"]],
            "first_pack": [any(CS[c]["essential"] and C.usable_by(CS[c], w.faction_info[f]["tribe"]) for c in first[f]) for f in st["ring"]],
        }
    return out


def test_every_entity_of_every_era_is_reachable_and_every_seat_starts_with_an_essential_card():
    games = [play(s) for s in SEEDS]
    for era in range(4):
        assert all(g[era]["dealt"] >= 42 for g in games), era  # the whole era is on the table
        assert all(g[era]["missing_entities"] == 0 for g in games), (era, [g[era]["missing_entities"] for g in games])
        assert all(all(g[era]["first_pack"]) for g in games), era


def test_a_sensible_drafter_is_ready_for_the_era_most_of_the_time():
    games = [play(s) for s in SEEDS]
    floor = {0: 0.95, 1: 0.8, 2: 0.95, 3: 0.95}  # Historic is lower: a repeated tribe's second faction can lose its smithing card to its sibling
    for era, bar in floor.items():
        ready = [r for g in games for r in g[era]["ready"]]
        assert statistics.mean(ready) >= bar, (era, statistics.mean(ready))
