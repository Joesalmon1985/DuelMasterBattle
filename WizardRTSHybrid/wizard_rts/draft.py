"""Era drafting, 7 Wonders style (plan v2 section 5). Enabled by `world.draft_v2`; otherwise tech.tech_quantum's older offers run.

One seven-round phase opens with each era. Round 0 opens at the era start, round k at +6 game minutes * k. In a round every
faction holds one pack and may pick one card from it (by `tech.draft`, the same command the AI and God Mode already use: the pack is
shown as the faction's `offers`). A faction that has not picked when the round closes gets a deterministic default pick
(`draft_default` event) so the ring never stalls. Packs are then passed to the next faction in the ring, the direction alternating by era.
A pick adds the card to `world.tech[faction]["cards"]`, which is the one gate every placement and unit queue already consults.

Leftover rule (`end_era`): when an era ends early, everyone keeps what they drafted; a faction with at least LEFTOVER_VP current VP
acquires every card left in the pack it holds at that instant, the others lose theirs. The next era then deals a new phase.

Bonus picks never touch circulating packs: a faction whose `bonus_ready` hook says yes gets a hand of three from a separate reserve
deck at the start of a round and keeps one (paper and the scriptorium, plan 5.3, plug in there).
"""

from __future__ import annotations

import random
from typing import Any

from wizard_rts import tech

ROUND_MS = 6 * 60_000
ROUNDS = 7
PACK_SIZE = 7
LEFTOVER_VP = 8
BONUS_HAND = 3
CURRENT_ERA_SHARE = 0.6  # at least this share of a pack comes from the era being opened (older undrafted cards fill the rest)


def enabled(world: Any) -> bool:
    return bool(getattr(world, "draft_v2", False)) and tech.gated(world) and not getattr(world, "nocards", False)


def state(world: Any) -> dict[str, Any]:
    st = world.__dict__.get("draft_state")
    if st is None:
        st = world.draft_state = {"era": -1, "round": ROUNDS, "open_ms": 0, "ring": [], "packs": {}, "chosen": {}, "reserve": [], "bonus": {}, "log": [],
                            "default_picks": 0, "phases": 0, "duplicated_cards": 0}
    return st


def _now(world: Any) -> int:
    return int(world.dmb.clock.get("game_ms", 0))


def _held(world: Any, faction: str) -> set[str]:
    return set(world.tech.get(faction, {}).get("cards", []))


def pickable(world: Any, faction: str, card_id: str) -> bool:
    return card_id in tech.lookup() and card_id not in _held(world, faction)


def active_factions(world: Any) -> list[str]:
    hist = (world.__dict__.get("history") or {}).get("faction", {})
    return [n for n in world.faction_info if hist.get(n, {}).get("state") != "collapsed"]


# ------------------------------------------------------------------ dealing

def deal(world: Any, era: int) -> None:
    """Open the era's phase: shuffle the pool, build one pack per faction, keep a reserve deck for bonus hands."""
    st = state(world)
    ring = active_factions(world)
    rng = random.Random(f"{world.seed}:draft:{era}")
    taken = set().union(*[_held(world, f) for f in ring]) if ring else set()
    cards = tech.pool(world)
    cur = sorted(c for c, v in cards.items() if v["era"] == era and c not in taken)
    old = sorted(c for c, v in cards.items() if v["era"] < era and c not in taken)
    rng.shuffle(cur)
    rng.shuffle(old)
    want_cur = max(1, round(PACK_SIZE * CURRENT_ERA_SHARE + 0.499))
    packs: dict[str, list[str]] = {}
    dup = 0
    # Tribe-balanced dealing: a Widelands building only helps its own tribe, so every pack rotates through the tribes in the ring (plus the
    # tribe-free cards), which gives each seat cards it can use in the first packs it sees and keeps the rest as trade-offs and denial.
    tribes = sorted({world.faction_info[f].get("tribe", "") for f in ring} | {""})

    def queues(cards_: list[str]) -> dict[str, list[str]]:
        q: dict[str, list[str]] = {t: [] for t in tribes}
        q["~other"] = []
        for c in cards_:
            t = pool_cards[c].get("tribe", "")
            q[t if t in q else "~other"].append(c)
        return q

    pool_cards = cards
    qs = {"cur": queues(cur), "old": queues(old)}
    spare: list[str] = []

    def draw(kind: str, prefer: str, wrap: bool) -> str | None:
        nonlocal dup
        q = qs[kind]
        order = [prefer] + [t for t in q if t != prefer]
        for t in order:
            if q[t]:
                return q[t].pop(0)
        if wrap and (cur or old):
            dup += 1
            return (cur + old)[dup % len(cur + old)]
        return None

    for f in ring:
        packs[f] = []
    for turn in range(PACK_SIZE):
        for seat, f in enumerate(ring):
            pack = packs[f]
            prefer = tribes[(seat + turn) % len(tribes)]
            kinds = ("cur", "old") if turn < want_cur else ("old", "cur")
            card = draw(kinds[0], prefer, False) or draw(kinds[1], prefer, False) or draw("cur", prefer, True)
            if card is not None and card not in pack:
                pack.append(card)
    reserve = [c for c in (cur + old) if all(c not in p for p in packs.values())]
    rng.shuffle(reserve)
    st.update(era=era, round=-1, open_ms=_now(world), ring=ring, packs=packs, chosen={f: False for f in ring}, reserve=reserve, bonus={})
    st["phases"] += 1
    st["duplicated_cards"] += dup
    world.events.append({"kind": "draft_phase", "era": tech.ERAS[era], "ring": list(ring), "pack_sizes": {f: len(p) for f, p in packs.items()}, "reserve": len(reserve),
                         "dealt": sorted({c for p in packs.values() for c in p})})
    open_round(world)


def refresh_offers(world: Any, faction: str) -> None:
    """What the faction may pick now: its pack while it has not picked this round, plus an unspent bonus hand."""
    st = state(world)
    s = world.tech.setdefault(faction, tech.new_state())
    offers: list[str] = []
    if not st["chosen"].get(faction):
        offers += [c for c in st["packs"].get(faction, []) if pickable(world, faction, c)]
    offers += [c for c in st["bonus"].get(faction, []) if pickable(world, faction, c)]
    s["offers"] = sorted(set(offers), key=lambda c: (tech.lookup()[c]["era"], c))


def _publish(world: Any, faction: str) -> None:
    st = state(world)
    s = world.tech.setdefault(faction, tech.new_state())
    refresh_offers(world, faction)
    s["round"] = st["round"] + 1
    s["expires_ms"] = st["open_ms"] + ROUND_MS
    s["next_round_ms"] = st["open_ms"] + ROUND_MS
    s.setdefault("history", []).append({"round": s["round"], "at_ms": st["open_ms"], "offered": list(s["offers"]), "picked": "", "eligible": len(s["offers"])})
    del s["history"][:-12]


def open_round(world: Any) -> None:
    st = state(world)
    st["round"] += 1
    st["open_ms"] = _now(world) if st["round"] == 0 else st["open_ms"] + ROUND_MS
    st["chosen"] = {f: False for f in st["ring"]}
    size = max((len(p) for p in st["packs"].values()), default=0)
    for f in st["ring"]:
        if size and not st["packs"].get(f):  # a successor that has no pack yet: one formed from the reserve deck, as long as the others
            st["packs"][f] = [st["reserve"].pop() for _ in range(min(size, len(st["reserve"])))]
        if bonus_ready(world, f) and len(st["reserve"]) >= BONUS_HAND and f not in st["bonus"]:
            hand = [st["reserve"].pop() for _ in range(BONUS_HAND)]
            st["bonus"][f] = hand
            world.events.append({"kind": "draft_bonus_hand", "faction": f, "hand": list(hand)})
        _publish(world, f)
    world.events.append({"kind": "draft_round", "era": tech.ERAS[st["era"]], "round": st["round"] + 1, "offers": {f: list(world.tech[f]["offers"]) for f in st["ring"]}})


PAPER_PER_PICK = 2


def paper_stock(world: Any, faction: str) -> int:
    return sum(int(world.stocks.get(b["id"], {}).get("paper", 0)) for b in world.buildings.values()
               if b["faction_name"] == faction and b["kind"] == "warehouse" and int(b.get("hp", 1)) > 0)


def has_scriptorium(world: Any, faction: str) -> bool:
    return any(b["faction_name"] == faction and b["kind"] == "scriptorium" and b.get("operational") and not b.get("constructing") and int(b.get("hp", 1)) > 0
               for b in world.buildings.values())


def bonus_ready(world: Any, faction: str) -> bool:
    """A working scriptorium and enough paper in the faction's stores (plan 5.3). `world.bonus_hook` overrides it (tests)."""
    hook = world.__dict__.get("bonus_hook")
    if hook is not None:
        return bool(hook(world, faction))
    return has_scriptorium(world, faction) and paper_stock(world, faction) >= PAPER_PER_PICK


def bonus_only(world: Any, faction: str, card_id: str) -> bool:
    """Is this card available only through the faction's bonus hand (not in its pack, or its pack pick is already used)?"""
    st = state(world)
    if card_id not in st["bonus"].get(faction, []):
        return False
    return st["chosen"].get(faction, False) or card_id not in st["packs"].get(faction, [])


def consume_paper(world: Any, faction: str) -> bool:
    """Take the paper for a bonus pick out of the faction's warehouses (ware ledger: counted as consumed)."""
    if "bonus_hook" in world.__dict__:
        return True
    need = PAPER_PER_PICK
    for b in sorted((x for x in world.buildings.values() if x["faction_name"] == faction and x["kind"] == "warehouse"), key=lambda x: x["id"]):
        have = int(world.stocks.get(b["id"], {}).get("paper", 0))
        take = min(have, need)
        if take:
            from wizard_rts.economy import _supply

            _supply(world, b["id"]).remove_wares("paper", take)
            world.stats["consumed_paper"] = world.stats.get("consumed_paper", 0) + take
            need -= take
    return need == 0


def on_pick(world: Any, faction: str, card_id: str) -> None:
    """Called by tech.draft after a successful pick: the card leaves the pack (or the bonus hand) it came from."""
    st = state(world)
    pack = st["packs"].get(faction)
    if pack is not None and card_id in pack and not st["chosen"].get(faction):
        pack.remove(card_id)
        st["chosen"][faction] = True
    else:
        hand = st["bonus"].pop(faction, None)
        if hand and card_id in hand:
            consume_paper(world, faction)
            world.events.append({"kind": "draft_bonus_pick", "faction": faction, "card": card_id, "discarded": [c for c in hand if c != card_id]})
    refresh_offers(world, faction)


def default_pick(world: Any, faction: str) -> str | None:
    s = world.tech[faction]
    return s["offers"][0] if s["offers"] else None


def close_round(world: Any) -> None:
    st = state(world)
    for f in st["ring"]:
        if not st["chosen"].get(f):
            pick = default_pick(world, f)
            if pick is not None:
                st["default_picks"] += 1
                world.events.append({"kind": "draft_default", "faction": f, "card": pick})
                tech.draft(world, f, pick)
        world.tech[f]["offers"] = []
        st["bonus"].pop(f, None)  # an unspent bonus hand goes back unseen: it is simply discarded
    pass_packs(world)


def pass_packs(world: Any) -> None:
    st = state(world)
    ring = st["ring"]
    if not ring:
        return
    step = 1 if st["era"] % 2 == 0 else -1
    old = st["packs"]
    st["packs"] = {ring[(i + step) % len(ring)]: old.get(f, []) for i, f in enumerate(ring)}


def quantum(world: Any) -> None:
    """Called every tick from tech.tech_quantum when drafting v2 is on."""
    st = state(world)
    era = int(getattr(world, "era_index", 0))
    now = _now(world)
    if st["era"] != era:
        if st["era"] >= 0:
            end_era(world, finished=True)
        deal(world, era)
        return
    if st["round"] >= ROUNDS:
        return
    if now >= st["open_ms"] + ROUND_MS:
        close_round(world)
        if st["round"] + 1 >= ROUNDS:
            st["round"] = ROUNDS
            st["packs"] = {f: [] for f in st["ring"]}
            world.events.append({"kind": "draft_phase_complete", "era": tech.ERAS[st["era"]]})
        else:
            open_round(world)


def end_era(world: Any, finished: bool = False) -> None:
    """The era is over. Called with a phase still running, it applies the leftover rule at this instant; a finished phase has nothing left."""
    st = state(world)
    if st["era"] < 0 or st["round"] >= ROUNDS:
        return
    from wizard_rts import vp

    vps = vp.totals(world)
    awarded: dict[str, list[str]] = {}
    lost: dict[str, list[str]] = {}
    for f in st["ring"]:
        left = [c for c in st["packs"].get(f, []) if pickable(world, f, c)]
        if not left:
            continue
        if vps.get(f, 0) >= LEFTOVER_VP and f in world.tech:
            for c in left:
                world.tech[f]["cards"].append(c)
                tech._apply_effect(world, f, tech.lookup()[c])
            awarded[f] = left
        else:
            lost[f] = left
        world.tech[f]["offers"] = []
    st["round"] = ROUNDS
    st["packs"] = {f: [] for f in st["ring"]}
    world.events.append({"kind": "draft_leftovers", "era": tech.ERAS[st["era"]], "round": st.get("round"), "awarded": awarded, "lost": lost, "vp": vps})
    st["log"].append({"era": st["era"], "awarded": awarded, "lost": lost})


# ------------------------------------------------------------------ ring changes

def on_split(world: Any, parent: str, child: str) -> None:
    """The successor sits next to its parent. It takes the parent's pack only if the parent has not yet picked this round; otherwise it
    waits and is dealt a pack formed from the reserve deck when the next round opens. No card is created or lost by the split itself."""
    st = state(world)
    if parent not in st["ring"] or child in st["ring"]:
        return
    st["ring"].insert(st["ring"].index(parent) + 1, child)
    st["packs"][child] = []
    st["chosen"][child] = True
    if st["round"] < ROUNDS and not st["chosen"].get(parent) and st["packs"].get(parent):
        st["packs"][child], st["packs"][parent] = st["packs"][parent], []
        st["chosen"][child], st["chosen"][parent] = False, True
        _publish(world, child)
        refresh_offers(world, parent)
    else:
        refresh_offers(world, child)


def on_collapse(world: Any, faction: str) -> None:
    """A collapsed faction's held pack is discarded and its seat closes."""
    st = state(world)
    if faction in st["ring"]:
        st["ring"].remove(faction)
        st["packs"].pop(faction, None)
        st["chosen"].pop(faction, None)
        world.tech.get(faction, {})["offers"] = []
