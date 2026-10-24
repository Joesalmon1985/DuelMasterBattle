"""The readable heuristic faction AI (PRD 9): placement by expected production and diversity, then a bounded decision pass every game second
through the same validated commands a developer would use. Every wait records a reason. No learned policy yet; `POLICY` is the seam a later
controller plugs into (same action space, same legal-command API)."""

from __future__ import annotations

from typing import Any, Callable

from . import rules

TRADE_COOLDOWN_MS = 6000
ROAD_LOOKAHEAD = 3  # roads toward a target are only started when the target is this close
TARGET_PATIENCE_MS = 90_000


def new_state() -> dict[str, Any]:
    return {"goal": "", "reason": "", "plan": "", "target_node": None, "target_since_ms": 0, "trade_cooldown_until": 0, "last_action": ""}


# ------------------------------------------------------------------ placement

def node_roles(world, node: str) -> list[str]:
    return [role for _h, role, _t in world.board.productive_hexes(node)]


def placement_score(world, fid: str, node: str, owned_roles: set[str]) -> float:
    board = world.board
    pips = board.node_pips(node)
    if pips <= 0:
        return -1e9
    score = 3.0 * pips
    roles = set(node_roles(world, node))
    for role in roles - owned_roles:
        score += {"WOOD": 2.0, "BRICK": 2.0, "WHEAT": 1.6, "ORE": 1.6, "SHEEP": 1.0}[role]
    if len(roles) == 1:
        score -= 2.0
    # room to grow: legal free nodes two steps away
    frontier = 0
    for mid in board.adjacency[node]:
        for far in board.adjacency[mid]:
            if far != node and far not in board.adjacency[node] and world.node_free(far) and board.node_pips(far) > 0:
                frontier += 1
    score += 0.4 * frontier
    if board.is_boundary(node) and len(board.node_hexes[node]) == 1:
        score -= 3.0
    return score


def choose_placement(world, fid: str, second: bool) -> tuple[str | None, str | None, str]:
    board = world.board
    owned: set[str] = set()
    for v in world.faction_villages(fid):
        owned.update(node_roles(world, v["node"]))
    best = None
    for node in board.nodes:
        if not world.node_free(node):
            continue
        s = placement_score(world, fid, node, owned)
        if s <= -1e8:
            continue
        if best is None or s > best[0] or (s == best[0] and node < best[1]):
            best = (s, node)
    if best is None:
        return None, None, "no legal node"
    node = best[1]
    # the road: toward the most valuable free node two steps on
    best_edge = None
    for eid in board.node_edges[node]:
        if world.road_at(eid) is not None:
            continue
        mid = board.other_end(eid, node)
        value = 0.0
        for far in board.adjacency[mid]:
            if far != node and world.node_free(far):
                value = max(value, float(board.node_pips(far)))
        value += 0.1 * board.node_pips(mid)
        if best_edge is None or value > best_edge[0] or (value == best_edge[0] and eid < best_edge[1]):
            best_edge = (value, eid)
    if best_edge is None:
        return None, None, "no free edge"
    why = f"{'second' if second else 'first'} site: {board.node_pips(node)} pips, roles {'/'.join(sorted(set(node_roles(world, node))))}, score {best[0]:.1f}"
    return node, best_edge[1], why


# ------------------------------------------------------------------ plans, needs and surplus

def _need(hand: dict[str, int], cost: dict[str, int]) -> dict[str, int]:
    return {r: n - hand.get(r, 0) for r, n in cost.items() if n - hand.get(r, 0) > 0}


def city_candidates(world, fid: str) -> list[dict[str, Any]]:
    out = [v for v in world.faction_villages(fid) if int(v["level"]) == 1 and not v.get("upgrade")]
    out.sort(key=lambda v: (-world.board.node_pips(v["node"]), v["id"]))
    return out


def frontier_targets(world, fid: str) -> list[tuple[float, str, list[str]]]:
    """Free legal nodes within ROAD_LOOKAHEAD unbuilt edges of the faction's network, with the edge path from the network: (score, node, edges)."""
    board = world.board
    network = world.network_nodes(fid)
    if not network:
        return []
    owned: set[str] = set()
    for v in world.faction_villages(fid):
        owned.update(node_roles(world, v["node"]))
    # BFS over edges that are free or already ours, from every network node, counting only edges that still need building
    best_path: dict[str, tuple[int, list[str]]] = {}
    frontier: list[tuple[int, str, list[str]]] = [(0, n, []) for n in sorted(network)]
    seen: dict[str, int] = {n: 0 for n in network}
    while frontier:
        cost, node, path = frontier.pop(0)
        for eid in board.node_edges[node]:
            r = world.roads.get(eid)
            if r is not None and r["status"] in ("building", "complete") and r["faction"] != fid:
                continue  # somebody else's road
            o = board.other_end(eid, node)
            ov = world.active_village_at(o)
            if ov is not None and ov["faction"] != fid:
                continue  # cannot pass through another faction's village
            # only an own COMPLETED road carries expansion; an own road still building, or a historical one of an earlier age, must be (re)built
            need = 0 if (r is not None and r["faction"] == fid and r["status"] == "complete") else 1
            ncost = cost + need
            if ncost > ROAD_LOOKAHEAD or seen.get(o, 99) <= ncost:
                continue
            seen[o] = ncost
            npath = path + ([eid] if need else [])
            if world.node_free(o) and board.node_pips(o) > 0 and ncost > 0:
                if o not in best_path or best_path[o][0] > ncost:
                    best_path[o] = (ncost, npath)
            frontier.append((ncost, o, npath))
    out = []
    for node, (ncost, path) in best_path.items():
        s = placement_score(world, fid, node, owned) - 4.0 * ncost
        out.append((s, node, path))
    out.sort(key=lambda t: (-t[0], t[1]))
    return out


def plan_for(world, fid: str) -> tuple[str, dict[str, int], str]:
    """What the faction is saving for next: ("city"|"settle"|"road"|"save", cost, note)."""
    hand = world.ledger.available(fid)
    sites = world.legal_sites(fid)
    cities = city_candidates(world, fid)
    targets = frontier_targets(world, fid)
    st = world.ai[fid]
    if sites:
        if cities and hand.get("ORE", 0) + hand.get("WHEAT", 0) >= 4 and len(_need(hand, rules.cost("city"))) <= 1:
            return "city", rules.cost("city"), "a city is nearly paid for"
        return "settle", rules.cost("settlement"), f"a legal site is reachable ({len(sites)})"
    if targets:
        if cities and len(_need(hand, rules.cost("city"))) == 0:
            return "city", rules.cost("city"), "a city is affordable now"
        return "road", rules.cost("road"), f"road toward {targets[0][1]}"
    if cities:
        return "city", rules.cost("city"), "no legal frontier: saving for cities"
    st["reason"] = "nothing left to build this age"
    return "save", {}, "every village is a city and no frontier remains"


def surplus(hand: dict[str, int], cost: dict[str, int]) -> dict[str, int]:
    return {r: hand[r] - cost.get(r, 0) for r in rules.ROLES if hand[r] - cost.get(r, 0) > 0}


def accepts_trade(world, pid: str, give: dict[str, int], want: dict[str, int]) -> bool:
    """`give` is what the partner would receive, `want` what it would hand over. It must help the partner's own plan or its surplus policy."""
    hand = world.ledger.available(pid)
    _plan, cost, _note = plan_for(world, pid)
    keep = dict(cost)
    for r, n in want.items():
        if hand.get(r, 0) - n < keep.get(r, 0):
            return False  # it would give away what its own plan needs
    need = _need(hand, cost)
    helps = any(r in need for r in give) or any(hand.get(r, 0) < 2 for r in give)
    fair = sum(give.values()) >= sum(want.values())
    return helps and fair


# ------------------------------------------------------------------ the decision pass

def decide(world, fid: str) -> int:
    """Up to `ai_actions_per_pass` accepted commands; the recorded goal and reason explain the wait."""
    st = world.ai[fid]
    acted = 0
    limit = rules.limit("ai_actions_per_pass")
    led = world.ledger
    for _ in range(limit):
        hand = led.available(fid)
        # 1. an affordable, useful city
        cities = city_candidates(world, fid)
        if cities and led.can_afford(fid, rules.cost("city")) and not any(v.get("upgrade") for v in world.faction_villages(fid)):
            r = world.upgrade_city(fid, cities[0]["id"])
            if r["status"] == "ok":
                acted += 1
                st.update(goal=f"raise {cities[0]['name']} to a city", reason="", last_action="city")
                continue
        # 2. found at a reachable legal node
        sites = world.legal_sites(fid)
        if sites and led.can_afford(fid, rules.cost("settlement")) and not any(v["status"] == "pending" for v in world.faction_villages(fid, ("pending",))):
            owned: set[str] = set()
            for v in world.faction_villages(fid):
                owned.update(node_roles(world, v["node"]))
            node = max(sorted(sites), key=lambda n: placement_score(world, fid, n, owned))
            r = world.found_settlement(fid, node)
            if r["status"] == "ok":
                acted += 1
                st.update(goal=f"found a settlement at {node}", reason="", last_action="settle", target_node=None)
                continue
        # 3. the next road toward a target
        targets = frontier_targets(world, fid)
        if targets and not sites:
            keep = st.get("target_node")
            chosen = next((t for t in targets if t[1] == keep), None)
            if chosen is None or world.game_ms - int(st.get("target_since_ms", 0)) > TARGET_PATIENCE_MS and targets[0][1] != keep:
                chosen = targets[0]
                st["target_node"], st["target_since_ms"] = chosen[1], int(world.game_ms)
            building = any(r["faction"] == fid and r["status"] == "building" for r in world.roads.values())
            if not building and chosen[2] and led.can_afford(fid, rules.cost("road")):
                # keep settlement money when the only road left would complete the way and a settlement is not yet affordable afterwards: roads first anyway,
                # a site unreachable is worth nothing
                r = world.build_road(fid, chosen[2][0])
                if r["status"] == "ok":
                    acted += 1
                    st.update(goal=f"road toward {chosen[1]} ({len(chosen[2])} to go)", reason="", last_action="road")
                    continue
        # 4. trade for the plan's missing resource
        plan, cost, note = plan_for(world, fid)
        st["plan"] = plan
        need = _need(hand, cost)
        if need and world.game_ms >= int(st.get("trade_cooldown_until", 0)) and world.active_trades(fid) < rules.limit("active_trades_per_faction"):
            spare = surplus(hand, cost)
            if spare:
                give_role = max(sorted(spare), key=lambda r: spare[r])
                want_role = sorted(need)[0]
                offered = False
                for pid in sorted(world.fids):
                    if pid == fid or world.ledger.available(pid).get(want_role, 0) < 1:
                        continue
                    r = world.offer_trade(fid, pid, {give_role: 1}, {want_role: 1})
                    st["trade_cooldown_until"] = int(world.game_ms) + TRADE_COOLDOWN_MS
                    if r["status"] == "ok":
                        acted += 1
                        offered = True
                        st.update(goal=f"{plan}: trading {give_role.lower()} for {want_role.lower()} with {pid}", reason="", last_action="trade")
                        break
                if offered:
                    continue
                bankable = [r for r in sorted(spare) if spare[r] >= int(rules.data()["bank"]["give"])]
                if bankable:
                    r = world.bank_trade(fid, bankable[0], want_role)
                    st["trade_cooldown_until"] = int(world.game_ms) + TRADE_COOLDOWN_MS
                    if r["status"] == "ok":
                        acted += 1
                        st.update(goal=f"{plan}: bank trade {bankable[0].lower()} for {want_role.lower()}", reason="", last_action="bank")
                        continue
        # nothing to do now: say why
        if need:
            st["reason"] = f"waiting for {', '.join(f'{n} {r.lower()}' for r, n in sorted(need.items()))} ({note})"
        elif any(v.get("upgrade") for v in world.faction_villages(fid)):
            st["reason"] = "a city is under construction"
        elif any(j["faction"] == fid and j["type"] == "expedition" for j in world.journeys.values()):
            st["reason"] = "an expedition is on the road"
        elif any(r["faction"] == fid and r["status"] == "building" for r in world.roads.values()):
            st["reason"] = "a road is under construction"
        elif plan == "save":
            st["reason"] = "nothing left to build this age"
        else:
            st["reason"] = note
        st["goal"] = st.get("goal") or plan
        break
    return acted


POLICY: Callable[[Any, str], int] = decide  # the adapter a learned controller replaces later (same legal-command API)
