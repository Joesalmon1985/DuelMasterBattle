"""The shared Pandemic campaign's rules (docs/PLAN_GOD_WORLD_PANDEMIC.md stage 4; decisions D54, D55).

The published core rules of Pandemic (Z-Man Games, 2008; Matt Leacock) adapted to this island: the 80 strategic nodes are the locations and the
109 corridors their links; four threat families; six responders with the six published roles; four actions a turn, then two cards drawn (an
escalation raises the rate, infects the bottom card with three and shuffles the discard back onto the top), the hand limit of seven, then the
infection draw at the rate track's current value; outbreaks spread to every neighbour and a location outbreaks once per chain; twenty-four units a
family and at most three at a location; the campaign is lost at the eighth outbreak, at an exhausted reserve, or when the player deck cannot be
drawn, and won when all four countermeasures are found (five matching cards at a field post, four for the scientist).

The whole state is one JSON-able dict with its own small generator, so a save mid-campaign replays exactly. Everything here is pure: no clock,
no world. `coordinator.py` chooses actions from the public view; `scenario.py` lays the campaign on the board; the world runs the turns."""

from __future__ import annotations

from typing import Any

ROLES = ("medic", "scientist", "researcher", "dispatcher", "operations_expert", "quarantine_specialist")
ROLE_NAMES = {"medic": "Medic", "scientist": "Scientist", "researcher": "Researcher", "dispatcher": "Dispatcher", "operations_expert": "Operations expert",
              "quarantine_specialist": "Quarantine specialist"}
FAMILIES = ("F1", "F2", "F3", "F4")
RATE_TRACK = (2, 2, 2, 3, 3, 4, 4)
ACTIONS_PER_TURN = 4
DRAW_PER_TURN = 2
HAND_LIMIT = 7
UNITS_PER_FAMILY = 24
MAX_AT_LOCATION = 3
LOSE_AT_OUTBREAKS = 8
EPIDEMIC_CARDS = 4
CURE_CARDS = 5
CURE_CARDS_SCIENTIST = 4
START_CARDS = 2  # six responders: two cards each (the published deal for five or more)
EVENTS = ("event:airlift", "event:one_quiet_night", "event:government_grant", "event:resilient_population", "event:forecast")
EVENT_NAMES = {"event:airlift": "Airlift", "event:one_quiet_night": "One quiet night", "event:government_grant": "Government grant",
               "event:resilient_population": "Resilient population", "event:forecast": "Forecast"}
INITIAL_INFECTIONS = (3, 3, 3)  # three locations with three units, three with two, three with one


class IllegalAction(Exception):
    pass


# ------------------------------------------------------------------ the campaign's own generator (saved as one integer)

def _rand(state: dict[str, Any], n: int) -> int:
    state["rng"] = (int(state["rng"]) * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
    return (state["rng"] >> 33) % max(1, n)


def shuffle(state: dict[str, Any], cards: list[str]) -> list[str]:
    out = list(cards)
    for i in range(len(out) - 1, 0, -1):
        j = _rand(state, i + 1)
        out[i], out[j] = out[j], out[i]
    return out


# ------------------------------------------------------------------ construction

def new_campaign(scenario: dict[str, Any], seed: int) -> dict[str, Any]:
    """A campaign laid on the scenario: locations with their family and links, the field posts, six responders at their homes, the decks built,
    the initial nine infections placed, the first responder ready to act. Deterministic in the seed."""
    st: dict[str, Any] = {"seed": int(seed), "rng": (int(seed) * 2654435761 + 97) & 0xFFFFFFFFFFFFFFFF, "locations": {}, "links": {}, "families": {},
                          "responders": [], "player_deck": [], "player_discard": [], "infection_deck": [], "infection_discard": [], "outbreaks": 0,
                          "rate_index": 0, "turn": 0, "turn_count": 0, "actions_left": ACTIONS_PER_TURN, "quiet_night": False, "result": None,
                          "lost_reason": "", "log": [], "last": [], "posts": [], "removed": []}
    for nid, fam in scenario["locations"].items():
        if fam not in FAMILIES:
            raise ValueError(f"unknown family {fam} at {nid}")
        st["locations"][nid] = {"family": fam, "units": {f: 0 for f in FAMILIES}, "post": False}
    for nid, nbrs in scenario["links"].items():
        st["links"][nid] = sorted(nbrs)
    for f in FAMILIES:
        st["families"][f] = {"reserve": UNITS_PER_FAMILY, "cured": False, "eradicated": False}
    for nid in scenario["posts"]:
        st["locations"][nid]["post"] = True
        st["posts"].append(nid)
    for i, r in enumerate(scenario["responders"]):
        if r["role"] not in ROLES:
            raise ValueError(f"unknown role {r['role']}")
        st["responders"].append({"id": r.get("id", f"r{i}"), "role": r["role"], "faction": r.get("faction", ""), "home": r["home"], "location": r["home"], "hand": [],
                                 "prev": r["home"], "path": [r["home"]], "ops_shuttle_used": False})
    # the player deck: location cards and the events dealt out first, then the escalations shuffled into four piles
    cards = sorted(st["locations"]) + list(EVENTS)
    deck = shuffle(st, cards)
    for r in st["responders"]:
        for _ in range(START_CARDS):
            r["hand"].append(deck.pop())
    piles: list[list[str]] = [[] for _ in range(EPIDEMIC_CARDS)]
    for i, c in enumerate(deck):
        piles[i % EPIDEMIC_CARDS].append(c)
    final: list[str] = []
    for pile in piles:
        pile.append("epidemic")
        final.extend(shuffle(st, pile))
    st["player_deck"] = final  # the top is the end of the list
    st["infection_deck"] = shuffle(st, sorted(st["locations"]))
    # the first infections: three cards with three units, three with two, three with one
    for count, n in zip(INITIAL_INFECTIONS, (3, 2, 1)):
        for _ in range(count):
            card = st["infection_deck"].pop()
            st["infection_discard"].append(card)
            _add_units(st, card, st["locations"][card]["family"], n, set(), "initial")
    st["log"].append({"kind": "start", "turn": 0})
    return st


# ------------------------------------------------------------------ queries

def responder(st: dict[str, Any], rid: str) -> dict[str, Any]:
    for r in st["responders"]:
        if r["id"] == rid:
            return r
    raise KeyError(rid)


def current(st: dict[str, Any]) -> dict[str, Any]:
    return st["responders"][int(st["turn"]) % len(st["responders"])]


def rate(st: dict[str, Any]) -> int:
    return RATE_TRACK[min(int(st["rate_index"]), len(RATE_TRACK) - 1)]


def cure_cards_needed(r: dict[str, Any]) -> int:
    return CURE_CARDS_SCIENTIST if r["role"] == "scientist" else CURE_CARDS


def family_of(st: dict[str, Any], card: str) -> str | None:
    loc = st["locations"].get(card)
    return loc["family"] if loc else None


def hand_by_family(st: dict[str, Any], r: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {f: [] for f in FAMILIES}
    for c in r["hand"]:
        fam = family_of(st, c)
        if fam:
            out[fam].append(c)
    return out


def can_cure(st: dict[str, Any], r: dict[str, Any]) -> str | None:
    """The family this responder could cure right now (at a field post with enough matching cards), else None."""
    if not st["locations"][r["location"]]["post"]:
        return None
    by = hand_by_family(st, r)
    for f in FAMILIES:
        if not st["families"][f]["cured"] and len(by[f]) >= cure_cards_needed(r):
            return f
    return None


def units_at(st: dict[str, Any], nid: str) -> int:
    return sum(st["locations"][nid]["units"].values())


def public_view(st: dict[str, Any]) -> dict[str, Any]:
    """What the coordinator may read: everything but the order of the decks (their sizes are public)."""
    return {k: v for k, v in st.items() if k not in ("player_deck", "infection_deck", "rng")} | {"player_deck_size": len(st["player_deck"]), "infection_deck_size": len(st["infection_deck"])}


# ------------------------------------------------------------------ units, outbreaks

def _protected(st: dict[str, Any], nid: str, fam: str) -> bool:
    """The quarantine specialist shields her location and its neighbours; the medic shields a cured family where he stands; an eradicated family
    places nothing."""
    if st["families"][fam]["eradicated"]:
        return True
    for r in st["responders"]:
        if r["role"] == "quarantine_specialist" and (r["location"] == nid or nid in st["links"].get(r["location"], [])):
            return True
        if r["role"] == "medic" and r["location"] == nid and st["families"][fam]["cured"]:
            return True
    return False


def _add_units(st: dict[str, Any], nid: str, fam: str, n: int, chain: set[str], why: str) -> None:
    if _protected(st, nid, fam):
        st["last"].append({"kind": "shielded", "location": nid, "family": fam})
        return
    loc = st["locations"][nid]
    for _ in range(n):
        if loc["units"][fam] >= MAX_AT_LOCATION:
            _outbreak(st, nid, fam, chain)
            return
        if st["families"][fam]["reserve"] <= 0:
            _lose(st, "reserve_exhausted", fam)
            return
        st["families"][fam]["reserve"] -= 1
        loc["units"][fam] += 1
    st["last"].append({"kind": "arrive", "location": nid, "family": fam, "n": n, "why": why})


def _outbreak(st: dict[str, Any], nid: str, fam: str, chain: set[str]) -> None:
    if nid in chain:
        return  # once per location per chain
    chain.add(nid)
    st["outbreaks"] = int(st["outbreaks"]) + 1
    st["last"].append({"kind": "outbreak", "location": nid, "family": fam, "count": int(st["outbreaks"])})
    st["log"].append({"kind": "outbreak", "location": nid, "family": fam, "turn": int(st["turn_count"])})
    if st["outbreaks"] >= LOSE_AT_OUTBREAKS:
        _lose(st, "outbreaks", fam)
        return
    for o in st["links"].get(nid, []):
        if st["result"] is not None:
            return
        _add_units(st, o, fam, 1, chain, "outbreak")


def _lose(st: dict[str, Any], reason: str, fam: str = "") -> None:
    if st["result"] is None:
        st["result"] = "lost"
        st["lost_reason"] = reason
        st["log"].append({"kind": "lost", "reason": reason, "family": fam, "turn": int(st["turn_count"])})


def _check_won(st: dict[str, Any]) -> None:
    if st["result"] is None and all(st["families"][f]["cured"] for f in FAMILIES):
        st["result"] = "won"
        st["log"].append({"kind": "won", "turn": int(st["turn_count"])})


# ------------------------------------------------------------------ actions (each costs one of the four)

def _spend(st: dict[str, Any], r: dict[str, Any]) -> None:
    if st["result"] is not None:
        raise IllegalAction("the campaign is over")
    if r is not current(st):
        raise IllegalAction("not this responder's turn")
    if int(st["actions_left"]) <= 0:
        raise IllegalAction("no actions left")
    st["actions_left"] = int(st["actions_left"]) - 1


def _arrive(st: dict[str, Any], r: dict[str, Any], to: str, how: str) -> None:
    r["prev"] = r["location"]
    r["location"] = to
    r["path"].append(to)
    if r["role"] == "medic":
        for f in FAMILIES:
            if st["families"][f]["cured"] and st["locations"][to]["units"][f] > 0:
                _remove(st, to, f, st["locations"][to]["units"][f])
    st["last"].append({"kind": "move", "responder": r["id"], "to": to, "how": how})


def drive(st: dict[str, Any], r: dict[str, Any], to: str) -> None:
    if to not in st["links"].get(r["location"], []):
        raise IllegalAction(f"{to} is not linked to {r['location']}")
    _spend(st, r)
    _arrive(st, r, to, "drive")


def direct_flight(st: dict[str, Any], r: dict[str, Any], to: str) -> None:
    if to not in r["hand"]:
        raise IllegalAction("direct flight needs the destination's card")
    _spend(st, r)
    r["hand"].remove(to)
    st["player_discard"].append(to)
    _arrive(st, r, to, "direct_flight")


def charter_flight(st: dict[str, Any], r: dict[str, Any], to: str) -> None:
    if r["location"] not in r["hand"]:
        raise IllegalAction("charter flight needs the current location's card")
    _spend(st, r)
    r["hand"].remove(r["location"])
    st["player_discard"].append(r["location"])
    _arrive(st, r, to, "charter_flight")


def shuttle(st: dict[str, Any], r: dict[str, Any], to: str) -> None:
    if not (st["locations"][r["location"]]["post"] and st["locations"][to]["post"]):
        raise IllegalAction("shuttle flights run between field posts")
    _spend(st, r)
    _arrive(st, r, to, "shuttle")


def ops_shuttle(st: dict[str, Any], r: dict[str, Any], to: str, card: str) -> None:
    """The operations expert: from a field post to anywhere, discarding any location card, once a turn."""
    if r["role"] != "operations_expert" or not st["locations"][r["location"]]["post"] or r.get("ops_shuttle_used") or card not in r["hand"] or family_of(st, card) is None:
        raise IllegalAction("ops shuttle not available")
    _spend(st, r)
    r["hand"].remove(card)
    st["player_discard"].append(card)
    r["ops_shuttle_used"] = True
    _arrive(st, r, to, "ops_shuttle")


def _remove(st: dict[str, Any], nid: str, fam: str, n: int) -> None:
    loc = st["locations"][nid]
    n = min(n, loc["units"][fam])
    loc["units"][fam] -= n
    st["families"][fam]["reserve"] += n
    st["last"].append({"kind": "treat", "location": nid, "family": fam, "n": n})
    if st["families"][fam]["cured"] and all(l["units"][fam] == 0 for l in st["locations"].values()):
        st["families"][fam]["eradicated"] = True
        st["log"].append({"kind": "eradicated", "family": fam, "turn": int(st["turn_count"])})


def treat(st: dict[str, Any], r: dict[str, Any], fam: str) -> None:
    loc = st["locations"][r["location"]]
    if loc["units"][fam] <= 0:
        raise IllegalAction("nothing of that family here")
    _spend(st, r)
    n = loc["units"][fam] if (r["role"] == "medic" or st["families"][fam]["cured"]) else 1
    _remove(st, r["location"], fam, n)


def build_post(st: dict[str, Any], r: dict[str, Any]) -> None:
    loc = st["locations"][r["location"]]
    if loc["post"]:
        raise IllegalAction("a field post stands here already")
    if r["role"] != "operations_expert":
        if r["location"] not in r["hand"]:
            raise IllegalAction("building a post needs the location's card")
        _spend(st, r)
        r["hand"].remove(r["location"])
        st["player_discard"].append(r["location"])
    else:
        _spend(st, r)
    loc["post"] = True
    st["posts"].append(r["location"])
    st["last"].append({"kind": "post", "location": r["location"]})


def cure(st: dict[str, Any], r: dict[str, Any], fam: str) -> None:
    if not st["locations"][r["location"]]["post"]:
        raise IllegalAction("a countermeasure is found at a field post")
    if st["families"][fam]["cured"]:
        raise IllegalAction("already cured")
    cards = hand_by_family(st, r)[fam]
    need = cure_cards_needed(r)
    if len(cards) < need:
        raise IllegalAction("not enough matching cards")
    _spend(st, r)
    for c in cards[:need]:
        r["hand"].remove(c)
        st["player_discard"].append(c)
    st["families"][fam]["cured"] = True
    st["log"].append({"kind": "cured", "family": fam, "responder": r["id"], "turn": int(st["turn_count"])})
    st["last"].append({"kind": "cured", "family": fam, "responder": r["id"], "location": r["location"]})
    if all(l["units"][fam] == 0 for l in st["locations"].values()):
        st["families"][fam]["eradicated"] = True
    _check_won(st)


def share(st: dict[str, Any], r: dict[str, Any], other: dict[str, Any], card: str) -> None:
    """Give or take a card between two responders at the same location: the card of that location, or any location card when the giver is the
    researcher. Spends the current responder's action whichever way the card goes."""
    if other is r or other["location"] != r["location"]:
        raise IllegalAction("share needs two responders at the same location")
    giver = r if card in r["hand"] else (other if card in other["hand"] else None)
    if giver is None or family_of(st, card) is None:
        raise IllegalAction("neither holds that location card")
    if giver["role"] != "researcher" and card != r["location"]:
        raise IllegalAction("only the current location's card can be shared")
    taker = other if giver is r else r
    _spend(st, r)
    giver["hand"].remove(card)
    taker["hand"].append(card)
    st["last"].append({"kind": "share", "from": giver["id"], "to": taker["id"], "card": card})


def dispatch(st: dict[str, Any], r: dict[str, Any], pawn: dict[str, Any], to: str) -> None:
    """The dispatcher moves any responder to a location that holds another responder, or drives any responder one link."""
    if r["role"] != "dispatcher":
        raise IllegalAction("only the dispatcher moves others")
    if to in st["links"].get(pawn["location"], []):
        _spend(st, r)
        _arrive(st, pawn, to, "dispatched")
        return
    if any(o["location"] == to for o in st["responders"] if o is not pawn):
        _spend(st, r)
        _arrive(st, pawn, to, "dispatched")
        return
    raise IllegalAction("the dispatcher may move a pawn one link or to another responder")


def pass_turn(st: dict[str, Any], r: dict[str, Any]) -> None:
    if r is not current(st):
        raise IllegalAction("not this responder's turn")
    st["actions_left"] = 0


# ------------------------------------------------------------------ events (free, any time, by whoever holds the card)

def play_event(st: dict[str, Any], holder: dict[str, Any], card: str, **kw: Any) -> None:
    if card not in holder["hand"] or card not in EVENTS:
        raise IllegalAction("no such event in hand")
    if st["result"] is not None:
        raise IllegalAction("the campaign is over")
    if card == "event:airlift":
        pawn = responder(st, kw["pawn"])
        _arrive(st, pawn, kw["to"], "airlift")
    elif card == "event:one_quiet_night":
        st["quiet_night"] = True
    elif card == "event:government_grant":
        loc = st["locations"][kw["location"]]
        if loc["post"]:
            raise IllegalAction("a post stands there")
        loc["post"] = True
        st["posts"].append(kw["location"])
    elif card == "event:resilient_population":
        if kw["remove"] not in st["infection_discard"]:
            raise IllegalAction("that card is not in the infection discard")
        st["infection_discard"].remove(kw["remove"])
        st["removed"].append(kw["remove"])
    elif card == "event:forecast":
        top = st["infection_deck"][-6:]
        order = list(kw["order"])
        if sorted(order) != sorted(top):
            raise IllegalAction("forecast must reorder exactly the top six")
        st["infection_deck"] = st["infection_deck"][:-6] + order  # the last is drawn first
    holder["hand"].remove(card)
    st["player_discard"].append(card)
    st["log"].append({"kind": "event", "card": card, "responder": holder["id"], "turn": int(st["turn_count"])})
    st["last"].append({"kind": "event", "card": card, "responder": holder["id"]})


def forecast_peek(st: dict[str, Any], holder: dict[str, Any]) -> list[str]:
    """The six cards Forecast would show, in draw order; only for a holder of the card (the rules' own look, not a peek)."""
    if "event:forecast" not in holder["hand"]:
        raise IllegalAction("no forecast in hand")
    return list(reversed(st["infection_deck"][-6:]))


# ------------------------------------------------------------------ the end of a turn: draw two, hand limit, infect

def end_turn(st: dict[str, Any], discard_policy=None) -> dict[str, Any]:
    """Draw two (escalations resolve at once), bring the hand to seven (the policy picks the discards, else the least useful by default), then the
    infection draw at the current rate, unless a quiet night was called. Advances to the next responder. Returns what happened."""
    r = current(st)
    st["last"] = []
    if st["result"] is not None:
        return {"result": st["result"]}
    for _ in range(DRAW_PER_TURN):
        if not st["player_deck"]:
            _lose(st, "player_deck_exhausted")
            break
        card = st["player_deck"].pop()
        if card == "epidemic":
            _epidemic(st)
            st["player_discard"].append(card)
        else:
            r["hand"].append(card)
            st["last"].append({"kind": "draw", "responder": r["id"], "card": card})
        if st["result"] is not None:
            break
    if st["result"] is None:
        while len(r["hand"]) > HAND_LIMIT:
            card = discard_policy(st, r) if discard_policy else default_discard(st, r)
            r["hand"].remove(card)
            st["player_discard"].append(card)
            st["last"].append({"kind": "discard", "responder": r["id"], "card": card})
    if st["result"] is None:
        if st["quiet_night"]:
            st["quiet_night"] = False
            st["last"].append({"kind": "quiet_night"})
        else:
            for _ in range(rate(st)):
                if st["result"] is not None or not st["infection_deck"]:
                    break
                card = st["infection_deck"].pop()
                st["infection_discard"].append(card)
                _add_units(st, card, st["locations"][card]["family"], 1, set(), "infect")
    st["turn"] = (int(st["turn"]) + 1) % len(st["responders"])
    st["turn_count"] = int(st["turn_count"]) + 1
    st["actions_left"] = ACTIONS_PER_TURN
    for o in st["responders"]:
        o["ops_shuttle_used"] = False
    nxt = current(st)
    nxt["prev"] = nxt["location"]
    nxt["path"] = [nxt["location"]]
    return {"result": st["result"], "last": list(st["last"])}


def _epidemic(st: dict[str, Any]) -> None:
    st["rate_index"] = min(int(st["rate_index"]) + 1, len(RATE_TRACK) - 1)
    if st["infection_deck"]:
        card = st["infection_deck"].pop(0)  # the bottom card
        st["infection_discard"].append(card)
        st["last"].append({"kind": "epidemic", "location": card})
        st["log"].append({"kind": "epidemic", "location": card, "turn": int(st["turn_count"]), "rate": rate(st)})
        _add_units(st, card, st["locations"][card]["family"], 3, set(), "epidemic")
    # intensify: the discard shuffled and put on TOP of the infection deck
    st["infection_deck"].extend(shuffle(st, st["infection_discard"]))
    st["infection_discard"] = []


def default_discard(st: dict[str, Any], r: dict[str, Any]) -> str:
    """Keep events and the family the responder holds most of; discard a card of the family held least (cured families first)."""
    by = hand_by_family(st, r)
    cands = [(st["families"][f]["cured"], len(by[f]), f) for f in FAMILIES if by[f]]
    if not cands:
        return next(c for c in r["hand"])
    cands.sort(key=lambda t: (not t[0], t[1]))
    return by[cands[0][2]][0]


# ------------------------------------------------------------------ summary

def summary(st: dict[str, Any]) -> dict[str, Any]:
    return {"result": st["result"], "lost_reason": st["lost_reason"], "outbreaks": int(st["outbreaks"]), "rate": rate(st), "rate_index": int(st["rate_index"]),
            "cured": [f for f in FAMILIES if st["families"][f]["cured"]], "eradicated": [f for f in FAMILIES if st["families"][f]["eradicated"]],
            "reserve": {f: int(st["families"][f]["reserve"]) for f in FAMILIES}, "player_deck": len(st["player_deck"]), "infection_deck": len(st["infection_deck"]),
            "turn_count": int(st["turn_count"]), "current": current(st)["id"], "actions_left": int(st["actions_left"]),
            "units_out": {f: sum(l["units"][f] for l in st["locations"].values()) for f in FAMILIES}}
