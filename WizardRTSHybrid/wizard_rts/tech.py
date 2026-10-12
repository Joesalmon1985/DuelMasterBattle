"""Campaign profiles and tech-card drafting (D02, D13, D15, D16; S05, S06).

A *profile* decides how a world starts and what may be commanded:
  campaign       primitive start, kinds locked until a card unlocks them, no God/training commands from the client
  developer      the same primitive start and the same locks, but God Mode and training commands are accepted
  test_showcase  the fully equipped six-faction start the earlier tests and headed scripts use; nothing is locked
  test_minimal   one faction and a warehouse; nothing is locked

Every placement and unit-queue path (player, AI, agents, tribe fallbacks) calls `kind_allowed` / `unit_allowed` through
`construction.check_placement` / `queue_unit`, so a locked kind cannot be built by any command. Drafting is part of the
one simulation: offers are a deterministic function of (seed, faction, round), choices are logged events.
"""

from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).with_name("data") / "tech_cards.json"
DRAFT_INTERVAL_MS = 4 * 60_000  # S05 revised 12 Oct 2026 (was 15 min: a 9-card era took over 2 hours); tunable per world (world.draft_interval_ms)
OFFER_WINDOW_MS = 3 * 60_000  # how long an open offer stays selectable (world.offer_window_ms); it lapses unchosen after that
OFFER_SIZE = 7  # owner: a pack of up to seven; fewer when fewer cards are eligible (never padded)
RESTRICTED = ("_deeper", "_deep")  # Widelands deep mines need a card that names the suffix (deep_mining), not just "mine"
ERAS = ("prehistoric", "historic", "modern", "dystopian")

PROFILES: dict[str, dict[str, bool]] = {
    "campaign": {"gated": True, "god": False, "primitive_start": True},
    "developer": {"gated": True, "god": True, "primitive_start": True},
    "test_showcase": {"gated": False, "god": True, "primitive_start": False},
    "test_minimal": {"gated": False, "god": True, "primitive_start": False},
}


@lru_cache(maxsize=1)
def _data() -> dict[str, Any]:
    return json.loads(DATA.read_text())


def cards() -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in _data()["cards"]}


def primitive() -> dict[str, Any]:
    return _data()["primitive"]


def profile_flags(profile: str) -> dict[str, bool]:
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; one of {sorted(PROFILES)}")
    return PROFILES[profile]


def gated(world: Any) -> bool:
    return PROFILES[world.profile]["gated"]


def god_allowed(world: Any) -> bool:
    return PROFILES[world.profile]["god"]


def init_world(world: Any) -> None:
    """Per-faction tech state, created once the factions exist."""
    world.tech = {}
    for name in world.faction_info:
        world.tech[name] = new_state()


def new_state() -> dict[str, Any]:
    return {"cards": [], "offers": [], "round": 0, "next_round_ms": 0, "expires_ms": 0, "history": [], "lapsed": 0}


def _state(world: Any, faction: str) -> dict[str, Any] | None:
    return getattr(world, "tech", {}).get(faction)


# Plan v2 P2 "foundation set": what a faction needs to feed itself and found more settlements without any card. Used only in
# the `nocards` test mode until the content graph (P3) makes the foundation a first-class, compiled set.
FOUNDATION_KINDS = ("tavern",)
FOUNDATION_UNITS = ("settlers",)
FOUNDATION_PATTERNS = ("tavern", "inn")


def unlocked_kinds(world: Any, faction: str) -> set[str]:
    out = set(primitive()["kinds"])
    if getattr(world, "nocards", False):
        out.update(FOUNDATION_KINDS)
    st = _state(world, faction)
    if st:
        for cid in st["cards"]:
            out.update(cards()[cid]["kinds"])
    return out


def unlocked_units(world: Any, faction: str) -> set[str]:
    out = set(primitive()["units"])
    if getattr(world, "nocards", False):
        out.update(FOUNDATION_UNITS)
    st = _state(world, faction)
    if st:
        for cid in st["cards"]:
            out.update(cards()[cid]["units"])
    return out


def _patterns(world: Any, faction: str) -> list[str]:
    out = list(primitive()["wl_patterns"])
    if getattr(world, "nocards", False):
        out.extend(FOUNDATION_PATTERNS)
    st = _state(world, faction)
    if st:
        for cid in st["cards"]:
            out.extend(cards()[cid]["wl_patterns"])
    return out


def kind_allowed(world: Any, faction: str, kind: str) -> bool:
    if not gated(world):
        return True
    if kind.startswith("wl:"):
        name = kind[3:]
        pats = _patterns(world, faction)
        for suffix in RESTRICTED:
            if suffix in name:
                return any(suffix in p for p in pats)
        return any(p in name for p in pats)
    return kind in unlocked_kinds(world, faction)


def unit_allowed(world: Any, faction: str, unit_kind: str) -> bool:
    return not gated(world) or unit_kind in unlocked_units(world, faction)


def _working(world: Any, faction: str, kinds: list[str]) -> bool:
    if not kinds:
        return True
    return any(b["faction_name"] == faction and b["kind"] in kinds and b.get("operational", True) and not b.get("constructing")
               and int(b.get("hp", 1)) > 0 for b in world.buildings.values())


def draftable(world: Any, faction: str) -> list[str]:
    """Card ids this faction could be offered now (S06): era reached, prerequisite cards drafted, physical prerequisite working."""
    st = _state(world, faction)
    if st is None:
        return []
    have = set(st["cards"])
    out = []
    for cid, c in sorted(cards().items()):
        if cid in have or c["era"] > getattr(world, "era_index", 0):
            continue
        if not all(r in have for r in c["requires_cards"]):
            continue
        if not _working(world, faction, c["requires_working"]):
            continue
        out.append(cid)
    return out


def tech_quantum(world: Any) -> None:
    """Open a draft round per faction every `draft_interval_ms` (S05). An offer stays selectable for `offer_window_ms`, then lapses
    (logged); a new round replaces whatever is still open."""
    if not gated(world) or getattr(world, "nocards", False):  # nocards: the plan v2 "no-card civilisation" test mode, drafting off
        return
    now = int(world.dmb.clock.get("game_ms", 0))
    for name in list(world.faction_info):
        st = world.tech.setdefault(name, new_state())
        for k, v in new_state().items():
            st.setdefault(k, v)
        if st["offers"] and now >= st["expires_ms"]:
            _lapse(world, name, st, "window_closed")
        if now < st["next_round_ms"]:
            continue
        if st["offers"]:
            _lapse(world, name, st, "next_round")
        pool = draftable(world, name)
        rng = random.Random(f"{world.seed}:{name}:{st['round']}")
        rng.shuffle(pool)
        st["offers"] = sorted(pool[:OFFER_SIZE], key=lambda c: (cards()[c]["era"], c))
        st["round"] += 1
        st["next_round_ms"] = now + int(getattr(world, "draft_interval_ms", DRAFT_INTERVAL_MS))
        st["expires_ms"] = now + min(int(getattr(world, "offer_window_ms", OFFER_WINDOW_MS)), int(getattr(world, "draft_interval_ms", DRAFT_INTERVAL_MS)))
        st["history"].append({"round": st["round"], "at_ms": now, "offered": list(st["offers"]), "picked": "", "eligible": len(pool)})
        del st["history"][:-12]
        world.events.append({"kind": "draft_offer", "faction": name, "round": st["round"], "offers": list(st["offers"]), "eligible": len(pool),
                             "expires_ms": st["expires_ms"]})


def _lapse(world: Any, name: str, st: dict, why: str) -> None:
    st["lapsed"] = int(st.get("lapsed", 0)) + 1
    world.events.append({"kind": "draft_lapsed", "faction": name, "round": st["round"], "offers": list(st["offers"]), "why": why})
    st["offers"] = []


def draft(world: Any, faction: str, card_id: str) -> dict[str, Any]:
    st = _state(world, faction)
    if st is None:
        return {"status": "rejected", "reason": "unknown_faction"}
    if card_id not in st["offers"]:
        return {"status": "rejected", "reason": "not_offered"}
    # the physical prerequisite is checked again at the moment of choice: a smithy destroyed since the offer withdraws it
    c = cards()[card_id]
    if not _working(world, faction, c["requires_working"]):
        return {"status": "rejected", "reason": "prerequisite_lost"}
    st["cards"].append(card_id)
    rejected = [x for x in st["offers"] if x != card_id]
    st["offers"] = []
    if st.get("history"):
        st["history"][-1]["picked"] = card_id
    _apply_effect(world, faction, c)
    world.events.append({"kind": "card_drafted", "faction": faction, "card": card_id, "round": st["round"], "rejected": rejected,
                         "unlocks": {"kinds": list(c["kinds"]), "units": list(c["units"]), "wl_patterns": list(c["wl_patterns"])}})
    return {"status": "ok", "card": card_id, "unlocks": {"kinds": c["kinds"], "units": c["units"]}}


def _apply_effect(world: Any, faction: str, c: dict) -> None:
    """A card's non-content modifier (data `effect`). Arcologies widen every command centre's territory now and later."""
    eff = c.get("effect") or {}
    bonus = int(eff.get("territory_bonus", 0))
    if bonus:
        from wizard_rts import territory

        for cc in territory.command_centers(world, faction):
            cc["territory"] = territory.radius_of(cc) + bonus


def territory_bonus(world: Any, faction: str) -> int:
    st = _state(world, faction)
    if not st:
        return 0
    return sum(int((cards()[cid].get("effect") or {}).get("territory_bonus", 0)) for cid in st["cards"] if cid in cards())


def card_info(card_id: str) -> dict[str, Any]:
    """What the draft panel shows for a card: era, explanation, what it unlocks and what it needs."""
    c = cards()[card_id]
    return {"id": card_id, "name": c["name"], "era": ERAS[c["era"]], "summary": c.get("summary", ""), "kinds": list(c["kinds"]),
            "units": list(c["units"]), "wl_patterns": list(c["wl_patterns"]), "requires_cards": [cards()[r]["name"] for r in c["requires_cards"]],
            "requires_working": list(c["requires_working"]), "effect": dict(c.get("effect") or {})}


def catalogue() -> dict[str, list[dict[str, Any]]]:
    """Every card by era (the inspectable catalogue of P1.5)."""
    out: dict[str, list[dict[str, Any]]] = {e: [] for e in ERAS}
    for cid, c in sorted(cards().items(), key=lambda kv: (kv[1]["era"], kv[0])):
        out[ERAS[c["era"]]].append(card_info(cid))
    return out


def grant(world: Any, faction: str, card_id: str) -> dict[str, Any]:
    """Developer fixture: add a card (and its prerequisite cards) without a draft. Rejected unless the profile allows God commands."""
    if not god_allowed(world):
        return {"status": "rejected", "reason": "god_mode_disabled"}
    st = _state(world, faction)
    if st is None or card_id not in cards():
        return {"status": "rejected", "reason": "unknown_card"}
    for cid in cards()[card_id]["requires_cards"] + [card_id]:
        if cid not in st["cards"]:
            if cid != card_id:
                grant(world, faction, cid)
            else:
                st["cards"].append(cid)
                world.events.append({"kind": "card_granted", "faction": faction, "card": cid})
    return {"status": "ok"}


def ai_pick(world: Any, faction: str) -> str | None:
    """The AI's planner: draft the first offered card in the order its economy needs them (cheapest chain first), no randomness."""
    st = _state(world, faction)
    if not st or not st["offers"]:
        return None
    order = ["dmb.card.mining", "dmb.card.farming", "dmb.card.smelting", "dmb.card.cookery", "dmb.card.metalwork",
             "dmb.card.drill_tactics", "dmb.card.fortification", "dmb.card.motor_pool", "dmb.card.seafaring", "dmb.card.submarines"]
    for cid in order:
        if cid in st["offers"]:
            return cid
    return st["offers"][0]


def snapshot(world: Any) -> dict[str, Any]:
    now = int(world.dmb.clock.get("game_ms", 0))
    out = {"profile": world.profile, "gated": gated(world), "god": god_allowed(world), "offer_size": OFFER_SIZE,
           "interval_ms": int(getattr(world, "draft_interval_ms", DRAFT_INTERVAL_MS)), "window_ms": int(getattr(world, "offer_window_ms", OFFER_WINDOW_MS)),
           "factions": {}}
    for n, s in getattr(world, "tech", {}).items():
        last = s.get("history", [])[-1] if s.get("history") else {}
        out["factions"][n] = {"cards": list(s["cards"]), "offers": list(s["offers"]), "round": s["round"], "next_round_ms": s["next_round_ms"],
                              "next_round_in_ms": max(0, s["next_round_ms"] - now), "expires_ms": s.get("expires_ms", 0),
                              "expires_in_ms": max(0, s.get("expires_ms", 0) - now) if s["offers"] else 0,
                              "offer_names": {c: cards()[c]["name"] for c in s["offers"]}, "last_pick": last.get("picked", ""),
                              "lapsed": int(s.get("lapsed", 0)), "eligible": int(last.get("eligible", 0))}
    return out


def on_era_change(world: Any) -> None:
    """S05: every faction gets one extra draft round on each era change (the next round opens at the next tick)."""
    for st in getattr(world, "tech", {}).values():
        st["next_round_ms"] = 0
