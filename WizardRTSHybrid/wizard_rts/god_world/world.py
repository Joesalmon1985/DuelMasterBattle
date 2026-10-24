"""`GodWorld`: the one authoritative simulation of the `god_catan_v1` profile, on one clock.

Owns the board, the six factions' five-slot ledger, villages, roads, journeys (road crews, founding expeditions, caravans, bank caravans),
the military quota, the dice, the AI pass and the age transitions. `advance(ms, sequence)` steps whole 100 ms quanta; nothing else moves
the world. Every command validates, reserves on acceptance and consumes exactly once on completion; a rejected command changes nothing."""

from __future__ import annotations

import heapq
import random
from typing import Any

from . import ai as ai_mod
from . import ages, composition, embedding, local_ops, rules
from .board import GodBoard
from .ledger import Ledger

QUANTUM_MS = 100
SCHEMA = 1
VILLAGE_NAMES = ["Ashford", "Brightwater", "Cairnmoor", "Dunhollow", "Elmreach", "Fallowmere", "Greyfen", "Hartswick", "Ivyhold", "Kestrel Bank",
                 "Larkspur", "Mossgate", "Netherby", "Oakhurst", "Pennywell", "Quarrystone", "Rookhaven", "Saltmarsh", "Thornbury", "Underhill",
                 "Vale End", "Wending", "Yarrowfield", "Alderford", "Birchmoor", "Coldstream", "Dapplewood", "Eastmarch", "Foxley", "Gorsebrook",
                 "Hazelden", "Ironcross", "Juniper Rise", "Kingsbarrow", "Lindenhall", "Marrowgate", "Northcote", "Otterburn", "Pikesend", "Redcliff",
                 "Stonewick", "Tarnside", "Upcote", "Westering", "Wolfpool", "Amberly", "Bramblewick", "Crowmarsh", "Dovecote", "Emberstone"]

ACTIVE = ("pending", "building", "operational", "rebuilding")  # statuses that occupy a node
PRODUCING = ("operational",)


class GodWorld:
    profile = rules.PROFILE

    def __init__(self, seed: int = 507, run_id: str | None = None, board: GodBoard | None = None, map_name: str | None = embedding.DEFAULT_MAP) -> None:
        self.seed = int(seed)
        self.run_id = run_id or f"god-{self.seed}"
        self.board = board or GodBoard.generate(self.seed)
        self.map_name = map_name or ""
        self.terrain = None  # the Widelands map grid the island is drawn from (wizard_rts.terrain.TerrainGrid), None in the bare regular layout
        if map_name:
            self._attach_map(map_name)
        self.rng = random.Random(self.seed * 7919 + 3)
        self.cosmetic_seed = self.seed * 104729 + 11  # the viewer's own stream: never the dice
        self.game_ms = 0
        self._carry_ms = 0
        self.clock_sequence = 0
        self.speed = 1
        self.paused = False
        self.age = 1
        self.epoch = 1
        self.phase = "SETUP"  # SETUP, RUNNING, TRANSITIONING
        self.factions: list[dict[str, Any]] = [dict(f, order=i) for i, f in enumerate(rules.factions())]
        self.fids: list[str] = [f["id"] for f in self.factions]
        self.ledger = Ledger(self.fids)
        self.villages: dict[str, dict[str, Any]] = {}
        self.roads: dict[str, dict[str, Any]] = {}
        self.journeys: dict[str, dict[str, Any]] = {}
        self.units: dict[str, dict[str, Any]] = {}
        self.node_reserved: dict[str, dict[str, str]] = {}
        self.events: list[dict[str, Any]] = []
        self.history: dict[str, Any] = {"age_winners": [], "transitions": [], "founded": [], "retired": [], "trades": 0, "bank_trades": 0, "roads": 0, "cities": 0}
        self.counters: dict[str, int] = {"trades": 0, "bank_trades": 0, "declined": 0, "roads": 0, "settlements": 0, "cities": 0, "recruits": 0, "ai_actions": 0}
        order = list(self.fids)
        self.rng.shuffle(order)
        self.setup = {"order": order + list(reversed(order)), "step": 0, "next_ms": rules.timing("setup_step"), "second": {}, "log": []}
        self.next_roll_ms: int | None = None
        self.last_roll: dict[str, Any] | None = None
        self.pulses = 0
        self.pulses_total = 0
        self.progress_pulse = 0  # the pulse count at the last completion (stall diagnostics)
        self.ai: dict[str, dict[str, Any]] = {f: ai_mod.new_state() for f in self.fids}
        self.ai_pass_index = 0
        self.ai_enabled = True  # tests of one rule at a time switch the factions off; the game never does
        self.transition: dict[str, Any] | None = None
        self.final_result: dict[str, Any] | None = None
        self.topology_version = 0
        self._reach_cache: dict[str, tuple[int, dict[str, Any]]] = {}
        self._next_id = 1
        self._next_unit_id = 1  # units have their own counter: recruiting (a presentation function) never shifts a village's or a journey's id
        self._name_index = 0
        self.players: dict[str, Any] = {}  # host.py compatibility: nobody walks in this world
        self.map_size = self.board.shape
        self.visual_state = True
        self.catching_up = False
        self.save_requested: str | None = None  # the host writes a checkpoint when this is set (age boundaries)
        self.pending_completions: list[dict[str, Any]] = []
        self.tree_claims: dict[str, str] = {}  # embedding tree index -> village id working it (local operations)
        self.local_ops_enabled = True  # the living village layer; off only in tests of strategic invariance (it never changes the rules either way)

    def _attach_map(self, map_name: str) -> None:
        """The terrain embedding of this board shape on the named map: the checked-in file, or built now (and not written) when it is missing."""
        from wizard_rts import wl_map

        grid = wl_map.load(map_name)
        emb = embedding.load(map_name)
        if emb is None or emb.get("map_static_hash") != grid.static_hash() or emb.get("shape") != self.board.shape:
            emb = embedding.build(self.board, grid, map_name)
        self.terrain = grid
        self.board.attach_embedding(emb, grid)

    def path_legs(self, path: list[str], ms_per_edge: int, road_flags: list[bool] | None = None) -> list[dict[str, Any]]:
        """Journey legs along the corridors of consecutive nodes: each edge's time is spread over its polyline by length."""
        legs: list[dict[str, Any]] = []
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            eid = self.board.edge(a, b)
            poly = self.board.corridor(eid) if eid else [self.board.node_xy(a), self.board.node_xy(b)]
            if eid and self.board.edge_endpoints[eid][0] != a:
                poly = list(reversed(poly))
            seg = [((poly[k + 1][0] - poly[k][0]) ** 2 + (poly[k + 1][1] - poly[k][1]) ** 2) ** 0.5 for k in range(len(poly) - 1)]
            total = sum(seg) or 1.0
            cum = 0.0
            spent = 0
            for k in range(len(poly) - 1):
                cum += seg[k]
                end_ms = int(ms_per_edge) if k == len(poly) - 2 else int(round(ms_per_edge * cum / total))
                leg_ms = end_ms - spent  # the legs of an edge sum exactly to the edge's declared time: the corridor's shape never changes a journey's length
                spent = end_ms
                legs.append({"a": [round(poly[k][0], 3), round(poly[k][1], 3)], "b": [round(poly[k + 1][0], 3), round(poly[k + 1][1], 3)],
                             "ms": max(0, leg_ms), "node": b if k == len(poly) - 2 else None, "edge": eid,
                             "road": bool(road_flags[i]) if road_flags else True})
        return legs

    # ------------------------------------------------------------------ small helpers
    def new_id(self, prefix: str) -> str:
        self._next_id += 1
        return f"{prefix}{self._next_id}"

    def faction(self, fid: str) -> dict[str, Any]:
        return next(f for f in self.factions if f["id"] == fid)

    def log(self, kind: str, **data: Any) -> dict[str, Any]:
        e = {"kind": kind, "game_ms": int(self.game_ms), "age": int(self.age), **data}
        self.events.append(e)
        if len(self.events) > 400:
            del self.events[: len(self.events) - 400]
        return e

    def next_village_name(self) -> str:
        name = VILLAGE_NAMES[self._name_index % len(VILLAGE_NAMES)]
        rounds = self._name_index // len(VILLAGE_NAMES)
        self._name_index += 1
        return name if rounds == 0 else f"New {name}" if rounds == 1 else f"{name} {rounds + 1}"

    def touch_topology(self) -> None:
        self.topology_version += 1

    # ------------------------------------------------------------------ queries used by rules, AI and the viewer
    def active_village_at(self, node: str) -> dict[str, Any] | None:
        for v in self.villages.values():
            if v["node"] == node and v["status"] in ACTIVE:
                return v
        return None

    def faction_villages(self, fid: str, statuses: tuple[str, ...] = PRODUCING) -> list[dict[str, Any]]:
        return [v for v in self.villages.values() if v["faction"] == fid and v["status"] in statuses]

    def vp(self, fid: str) -> int:
        return sum(rules.vp_for_level(int(v["level"])) for v in self.villages.values() if v["faction"] == fid and v["status"] in ("operational", "rebuilding"))

    def node_free(self, node: str) -> bool:
        """Empty, unreserved, and no neighbour holds an active or reserved site (the distance rule, any faction)."""
        if self.active_village_at(node) is not None or node in self.node_reserved:
            return False
        for o in self.board.adjacency[node]:
            if self.active_village_at(o) is not None or o in self.node_reserved:
                return False
        return True

    def road_at(self, eid: str) -> dict[str, Any] | None:
        r = self.roads.get(eid)
        return r if r is not None and r["status"] in ("building", "complete") else None

    def network_nodes(self, fid: str) -> set[str]:
        """Nodes an own completed road touches, plus own active village nodes."""
        out: set[str] = set()
        for r in self.roads.values():
            if r["faction"] == fid and r["status"] == "complete":
                out.update(self.board.edge_endpoints[r["edge"]])
        for v in self.villages.values():
            if v["faction"] == fid and v["status"] in ("operational", "rebuilding"):
                out.add(v["node"])
        return out

    def node_connects(self, fid: str, node: str) -> bool:
        """May a new road of `fid` start from `node`? Its own completed village stands there, or its own completed road reaches it and nobody else's
        village sits on it. A pending site (settlers still on the road) connects nothing yet."""
        v = self.active_village_at(node)
        if v is not None:
            if v["faction"] != fid:
                return False
            if v["status"] in ("operational", "rebuilding"):
                return True
        return any(r["faction"] == fid and r["status"] == "complete" and node in self.board.edge_endpoints[r["edge"]] for r in self.roads.values())

    def reachable(self, fid: str) -> dict[str, Any]:
        """Nodes reachable from each own active village over own completed roads, never through another faction's village: {node: (from_vid, path)}.
        Cached by topology version."""
        cached = self._reach_cache.get(fid)
        if cached is not None and cached[0] == self.topology_version:
            return cached[1]
        out: dict[str, Any] = {}
        own_edges = {r["edge"] for r in self.roads.values() if r["faction"] == fid and r["status"] == "complete"}
        for v in sorted(self.faction_villages(fid, ("operational", "rebuilding")), key=lambda v: v["id"]):
            start = v["node"]
            prev: dict[str, str | None] = {start: None}
            queue = [start]
            while queue:
                n = queue.pop(0)
                if n != start:
                    other = self.active_village_at(n)
                    if other is not None and other["faction"] != fid:
                        continue
                for eid in self.board.node_edges[n]:
                    if eid not in own_edges:
                        continue
                    o = self.board.other_end(eid, n)
                    if o in prev:
                        continue
                    prev[o] = n
                    queue.append(o)
            for n in prev:
                if n == start or n in out:
                    continue
                path = [n]
                while prev[path[-1]] is not None:
                    path.append(prev[path[-1]])  # type: ignore[arg-type]
                path.reverse()
                out[n] = (v["id"], path)
        self._reach_cache[fid] = (self.topology_version, out)
        return out

    def legal_sites(self, fid: str) -> dict[str, Any]:
        return {n: info for n, info in self.reachable(fid).items() if self.node_free(n) and self.board.node_pips(n) > 0}

    def route_any(self, start: str, goal: str) -> tuple[list[tuple[str, int]], int] | None:
        """Cheapest node path for a caravan: any completed road costs the road time, any other edge the trail time. Returns ([(node, leg_ms)...], total)."""
        road_ms, trail_ms = rules.timing("edge_travel_road"), rules.timing("edge_travel_trail")
        dist = {start: 0}
        prev: dict[str, tuple[str, int]] = {}
        heap = [(0, start)]
        while heap:
            d, n = heapq.heappop(heap)
            if n == goal:
                break
            if d > dist.get(n, 1 << 60):
                continue
            for eid in self.board.node_edges[n]:
                r = self.roads.get(eid)
                cost = road_ms if (r is not None and r["status"] == "complete") else trail_ms
                o = self.board.other_end(eid, n)
                nd = d + cost
                if nd < dist.get(o, 1 << 60):
                    dist[o] = nd
                    prev[o] = (n, cost)
                    heapq.heappush(heap, (nd, o))
        if goal not in dist:
            return None
        legs: list[tuple[str, int]] = []
        n = goal
        while n != start:
            p, c = prev[n]
            legs.append((n, c))
            n = p
        legs.reverse()
        return legs, dist[goal]

    def nearest_village(self, fid: str, from_node: str) -> dict[str, Any] | None:
        best = None
        for v in sorted(self.faction_villages(fid), key=lambda v: v["id"]):
            r = self.route_any(from_node, v["node"])
            if r is None:
                continue
            if best is None or r[1] < best[0]:
                best = (r[1], v)
        return best[1] if best else None

    def active_trades(self, fid: str) -> int:
        return sum(1 for j in self.journeys.values() if j["faction"] == fid and j["type"] in ("caravan", "bank") and j["phase"] != "done")

    # ------------------------------------------------------------------ the clock
    def advance(self, ms: int, sequence: int, snapshot: bool = True, **_kw: Any) -> dict[str, Any]:
        self.clock_sequence = int(sequence)
        quanta = 0
        if not self.paused:
            self._carry_ms += max(0, int(ms)) * max(1, int(self.speed))
            while self._carry_ms >= QUANTUM_MS:
                self._carry_ms -= QUANTUM_MS
                self._quantum()
                quanta += 1
        out = {"status": "ok", "quanta": quanta, "game_ms": int(self.game_ms), "clock_sequence": self.clock_sequence}
        if snapshot:
            from . import snapshot as snap

            out["snapshot"] = snap.snapshot(self, _kw.get("view"))
        return out

    def set_speed(self, scale: int) -> dict[str, Any]:
        if int(scale) not in (1, 2, 4):
            return {"status": "rejected", "reason": "bad_speed"}
        self.speed = int(scale)
        return {"status": "ok", "speed": self.speed}

    def set_paused(self, on: bool) -> dict[str, Any]:
        self.paused = bool(on)
        return {"status": "ok", "paused": self.paused}

    def _quantum(self) -> None:
        self.game_ms += QUANTUM_MS
        if self.phase == "SETUP":
            if self.game_ms >= int(self.setup["next_ms"]):
                self._setup_step()
        self._step_journeys()
        self._step_constructions()
        if self.local_ops_enabled:
            local_ops.step_all(self)
        if self.phase == "TRANSITIONING" and self.transition is not None and self.game_ms >= int(self.transition["ready_ms"]):
            ages.sites_ready(self)
        if self.phase == "RUNNING" and self.next_roll_ms is not None and self.game_ms >= self.next_roll_ms:
            self._roll()
        self._step_military()
        if self.phase == "RUNNING" and self.game_ms % rules.timing("ai_pass") == 0:
            self._ai_pass()
        self._drain_completions()
        self._prune_journeys()

    # ------------------------------------------------------------------ setup: snake placement, a replay of real accepted decisions
    def _setup_step(self) -> None:
        step = int(self.setup["step"])
        order = self.setup["order"]
        if step >= len(order):
            return
        fid = order[step]
        second = step >= len(self.fids)
        node, edge, why = ai_mod.choose_placement(self, fid, second)
        if node is None or edge is None:
            raise RuntimeError(f"setup: no legal placement for {fid} at step {step}")
        if not self.node_free(node) or self.board.node_pips(node) <= 0:
            raise RuntimeError(f"setup: AI chose an illegal node {node}")
        if node not in self.board.edge_endpoints[edge] or self.road_at(edge) is not None:
            raise RuntimeError(f"setup: AI chose an illegal road {edge}")
        v = self._create_village(fid, node, level=1, status="operational")
        self.roads[edge] = {"edge": edge, "faction": fid, "status": "complete", "age": self.age, "started_ms": self.game_ms, "done_ms": self.game_ms, "rid": None, "from_node": node}
        self.touch_topology()
        self.setup["log"].append({"step": step, "faction": fid, "node": node, "edge": edge, "why": why, "village": v["id"]})
        self.log("placed", faction=fid, village=v["id"], node=node, edge=edge, why=why, second=second)
        if second:
            self.setup["second"][fid] = v["id"]
        self.setup["step"] = step + 1
        self.setup["next_ms"] = self.game_ms + rules.timing("setup_step")
        if step + 1 >= len(order):
            for f in self.fids:
                sv = self.villages[self.setup["second"][f]]
                goods: dict[str, int] = {}
                for _h, role, _t in self.board.productive_hexes(sv["node"]):
                    goods[role] = goods.get(role, 0) + 1
                self.ledger.grant(f, goods, "initial")
                self.log("starting_resources", faction=f, village=sv["id"], goods=goods)
            self.phase = "RUNNING"
            self.next_roll_ms = self.game_ms + rules.timing("roll_interval")
            self.log("setup_done", vp={f: self.vp(f) for f in self.fids})

    def _create_village(self, fid: str, node: str, level: int, status: str) -> dict[str, Any]:
        vid = self.new_id("v")
        v = {"id": vid, "node": node, "faction": fid, "name": self.next_village_name(), "level": int(level), "status": status, "age": int(self.age),
             "epoch": int(self.epoch), "founded_ms": int(self.game_ms), "warehouse": f"{vid}:wh", "construction": None, "upgrade": None, "rid": None,
             "ready_ms": int(self.game_ms), "produced": {r: 0 for r in rules.ROLES}, "history": [{"age": int(self.age), "event": "founded", "game_ms": int(self.game_ms)}],
             "next_recruit_ms": int(self.game_ms) + rules.timing("military_interval")}
        self.villages[vid] = v
        if status == "operational":
            self.history["founded"].append({"village": vid, "faction": fid, "age": int(self.age), "game_ms": int(self.game_ms)})
            self.counters["settlements"] += 1
        return v

    # ------------------------------------------------------------------ dice
    def _roll(self) -> None:
        d1, d2 = self.rng.randint(1, 6), self.rng.randint(1, 6)
        total = d1 + d2
        grants: list[dict[str, Any]] = []
        if total != 7:
            for v in sorted(self.villages.values(), key=lambda v: v["id"]):
                if v["status"] not in PRODUCING:
                    continue
                for hid, role, token in self.board.productive_hexes(v["node"]):
                    if token != total:
                        continue
                    n = int(v["level"])
                    self.ledger.grant(v["faction"], {role: n}, "roll")
                    v["produced"][role] = int(v["produced"].get(role, 0)) + n
                    grants.append({"faction": v["faction"], "village": v["id"], "role": role, "n": n, "hex": hid})
        self.pulses += 1
        self.pulses_total += 1
        self.last_roll = {"game_ms": int(self.game_ms), "dice": [d1, d2], "total": total, "grants": grants, "pulse": self.pulses}
        self.next_roll_ms = int(self.next_roll_ms or self.game_ms) + rules.timing("roll_interval")
        self.log("roll", dice=[d1, d2], total=total, grants=len(grants))
        if self.pulses - self.progress_pulse >= rules.limit("stall_pulses") and (self.pulses - self.progress_pulse) % rules.limit("stall_pulses") == 0:
            self.log("stall_diagnostics", pulses_since_progress=self.pulses - self.progress_pulse,
                     factions={f: {"hand": self.ledger.available(f), "vp": self.vp(f), "goal": self.ai[f].get("goal"), "reason": self.ai[f].get("reason"),
                                   "legal_sites": len(self.legal_sites(f)), "trades": self.active_trades(f)} for f in self.fids})

    # ------------------------------------------------------------------ commands
    def _reject(self, reason: str, **extra: Any) -> dict[str, Any]:
        return {"status": "rejected", "reason": reason, **extra}

    def _running(self) -> bool:
        return self.phase == "RUNNING"

    def build_road(self, fid: str, eid: str) -> dict[str, Any]:
        if not self._running():
            return self._reject("not_running")
        if eid not in self.board.edge_endpoints:
            return self._reject("no_such_edge")
        if self.road_at(eid) is not None:
            return self._reject("edge_taken")
        a, b = self.board.edge_endpoints[eid]
        start = a if self.node_connects(fid, a) else (b if self.node_connects(fid, b) else None)
        if start is None:
            return self._reject("not_connected")
        rid = self.ledger.reserve(fid, rules.cost("road"), "road")
        if rid is None:
            return self._reject("cannot_afford")
        self.roads[eid] = {"edge": eid, "faction": fid, "status": "building", "age": int(self.age), "started_ms": int(self.game_ms),
                           "done_ms": int(self.game_ms) + rules.timing("road_build"), "rid": rid, "from_node": start}
        self.log("road_started", faction=fid, edge=eid)
        return {"status": "ok", "edge": eid, "done_ms": self.roads[eid]["done_ms"]}

    def found_settlement(self, fid: str, node: str) -> dict[str, Any]:
        if not self._running():
            return self._reject("not_running")
        if node not in self.board.adjacency:
            return self._reject("no_such_node")
        if not self.node_free(node):
            return self._reject("node_not_free")
        if self.board.node_pips(node) <= 0:
            return self._reject("no_production")
        info = self.reachable(fid).get(node)
        if info is None:
            return self._reject("not_reachable")
        from_vid, path = info
        rid = self.ledger.reserve(fid, rules.cost("settlement"), "settlement")
        if rid is None:
            return self._reject("cannot_afford")
        v = self._create_village(fid, node, level=0, status="pending")
        v["rid"] = rid
        self.node_reserved[node] = {"faction": fid, "village": v["id"]}
        jid = self.new_id("j")
        legs = self.path_legs(path, rules.timing("edge_travel_road"))
        self.journeys[jid] = {"id": jid, "type": "expedition", "faction": fid, "origin": from_vid, "dest_node": node, "village": v["id"], "route": list(path), "legs": legs,
                              "leg": 0, "leg_ms": 0, "phase": "outbound", "rid": rid, "started_ms": int(self.game_ms),
                              "party": [dict(m) for m in rules.data()["expedition_party"]], "supplies": rules.cost("settlement")}
        v["journey"] = jid
        self.log("expedition_departed", faction=fid, village=v["id"], origin=from_vid, node=node, journey=jid, legs=len(legs))
        return {"status": "ok", "village": v["id"], "journey": jid}

    def upgrade_city(self, fid: str, vid: str) -> dict[str, Any]:
        if not self._running():
            return self._reject("not_running")
        v = self.villages.get(vid)
        if v is None or v["faction"] != fid:
            return self._reject("not_yours")
        if v["status"] != "operational" or int(v["level"]) != 1:
            return self._reject("not_a_settlement")
        if v.get("upgrade"):
            return self._reject("already_upgrading")
        rid = self.ledger.reserve(fid, rules.cost("city"), "city")
        if rid is None:
            return self._reject("cannot_afford")
        v["upgrade"] = {"rid": rid, "started_ms": int(self.game_ms), "done_ms": int(self.game_ms) + rules.timing("city_build")}
        self.log("city_started", faction=fid, village=vid)
        return {"status": "ok", "village": vid, "done_ms": v["upgrade"]["done_ms"]}

    def offer_trade(self, fid: str, partner: str, give: dict[str, int], want: dict[str, int]) -> dict[str, Any]:
        if not self._running():
            return self._reject("not_running")
        if partner == fid or partner not in self.fids:
            return self._reject("bad_partner")
        try:
            give = {r: int(n) for r, n in give.items() if int(n) > 0}
            want = {r: int(n) for r, n in want.items() if int(n) > 0}
        except (TypeError, ValueError):
            return self._reject("bad_goods")
        if not give or not want or any(r not in rules.ROLES for r in list(give) + list(want)):
            return self._reject("bad_goods")
        if self.active_trades(fid) >= rules.limit("active_trades_per_faction"):
            return self._reject("too_many_journeys")
        if not self.ledger.can_afford(fid, give):
            return self._reject("cannot_afford")
        if not self.ledger.can_afford(partner, want):
            return self._reject("partner_cannot_afford")
        origin = sorted(self.faction_villages(fid), key=lambda v: v["id"])
        if not origin:
            return self._reject("no_warehouse")
        if not ai_mod.accepts_trade(self, partner, give, want):
            self.counters["declined"] += 1  # counted, not fed: a refused offer is not an event worth the feed
            return self._reject("declined")
        dest = self.nearest_village(partner, origin[0]["node"])
        if dest is None:
            return self._reject("no_route")
        route = self.route_any(origin[0]["node"], dest["node"])
        if route is None:
            return self._reject("no_route")
        jid = self.new_id("j")
        cid = self.ledger.load_cargo(fid, give, jid)
        eid = self.ledger.escrow(partner, want, jid)
        if cid is None or eid is None:  # cannot happen after the checks above, but never leave half a deal
            if cid:
                self.ledger.unload_cargo(cid)
            if eid:
                self.ledger.release_escrow(eid)
            return self._reject("reservation_failed")
        legs = self._legs_from_route(origin[0]["node"], route[0])
        self.journeys[jid] = {"id": jid, "type": "caravan", "faction": fid, "partner": partner, "origin": origin[0]["id"], "dest": dest["id"], "give": give, "want": want,
                              "cargo": cid, "escrow": eid, "legs": legs, "leg": 0, "leg_ms": 0, "phase": "outbound", "exchanged": False, "started_ms": int(self.game_ms),
                              "total_ms": route[1]}
        self.log("caravan_departed", faction=fid, partner=partner, give=give, want=want, journey=jid)
        return {"status": "ok", "journey": jid}

    def bank_trade(self, fid: str, give_role: str, want_role: str) -> dict[str, Any]:
        if not self._running():
            return self._reject("not_running")
        if give_role not in rules.ROLES or want_role not in rules.ROLES or give_role == want_role:
            return self._reject("bad_goods")
        n = int(rules.data()["bank"]["give"])
        if self.active_trades(fid) >= rules.limit("active_trades_per_faction"):
            return self._reject("too_many_journeys")
        origin = sorted(self.faction_villages(fid), key=lambda v: v["id"])
        if not origin:
            return self._reject("no_warehouse")
        jid = self.new_id("j")
        cid = self.ledger.load_cargo(fid, {give_role: n}, jid)
        if cid is None:
            return self._reject("cannot_afford")
        ox, oy = self.board.node_xy(origin[0]["node"])
        bx, by = self.board.coast(origin[0]["node"])
        legs = [{"a": [ox, oy], "b": [bx, by], "ms": rules.timing("bank_leg"), "node": None}]
        self.journeys[jid] = {"id": jid, "type": "bank", "faction": fid, "origin": origin[0]["id"], "give": {give_role: n}, "want": {want_role: int(rules.data()["bank"]["get"])},
                              "cargo": cid, "legs": legs, "leg": 0, "leg_ms": 0, "phase": "outbound", "exchanged": False, "started_ms": int(self.game_ms), "bank_point": [bx, by]}
        self.log("bank_caravan_departed", faction=fid, give=give_role, want=want_role, journey=jid)
        return {"status": "ok", "journey": jid}

    def _legs_from_route(self, start: str, legs: list[tuple[str, int]]) -> list[dict[str, Any]]:
        out = []
        prev = start
        for node, ms in legs:
            r = self.roads.get(self.board.edge(prev, node) or "")
            out += self.path_legs([prev, node], int(ms), [bool(r is not None and r["status"] == "complete")])
            prev = node
        return out

    # ------------------------------------------------------------------ journeys and constructions
    def _step_journeys(self) -> None:
        for jid in sorted(self.journeys):
            j = self.journeys[jid]
            if j["phase"] in ("done", "building"):
                continue
            j["leg_ms"] = int(j["leg_ms"]) + QUANTUM_MS
            while j["phase"] not in ("done", "building") and int(j["leg"]) < len(j["legs"]) and j["leg_ms"] >= int(j["legs"][j["leg"]]["ms"]):
                j["leg_ms"] -= int(j["legs"][j["leg"]]["ms"])
                j["leg"] = int(j["leg"]) + 1
                if j["leg"] >= len(j["legs"]):
                    self._journey_end(j)

    def _prune_journeys(self) -> None:
        for jid in [k for k, j in self.journeys.items() if j["phase"] == "done"]:
            del self.journeys[jid]

    def _journey_end(self, j: dict[str, Any]) -> None:
        kind = j["type"]
        if kind == "expedition":
            v = self.villages[j["village"]]
            v["status"] = "building"
            v["construction"] = {"kind": "warehouse", "started_ms": int(self.game_ms), "done_ms": int(self.game_ms) + rules.timing("warehouse_stage")}
            j["phase"] = "building"
            self.log("expedition_arrived", faction=j["faction"], village=v["id"], node=v["node"])
        elif kind == "caravan":
            if j["phase"] == "outbound":
                if not j["exchanged"]:
                    self.ledger.unload_cargo(j["cargo"], j["partner"])
                    j["cargo"] = self.ledger.escrow_to_cargo(j["escrow"], j["faction"], j["id"])
                    j["escrow"] = None
                    j["exchanged"] = True
                    self.counters["trades"] += 1
                    self.history["trades"] += 1
                    self.log("trade_exchanged", faction=j["faction"], partner=j["partner"], give=j["give"], want=j["want"], journey=j["id"])
                j["legs"] = [{"a": leg["b"], "b": leg["a"], "ms": leg["ms"], "node": None, "road": leg.get("road", False)} for leg in reversed(j["legs"])]
                j["leg"], j["leg_ms"], j["phase"] = 0, 0, "return"
            else:
                self.ledger.unload_cargo(j["cargo"])
                j["cargo"] = None
                j["phase"] = "done"
                self.log("caravan_returned", faction=j["faction"], journey=j["id"])
        elif kind == "bank":
            if j["phase"] == "outbound":
                j["legs"] = [{"a": leg["b"], "b": leg["a"], "ms": leg["ms"], "node": None} for leg in reversed(j["legs"])]
                j["leg"], j["leg_ms"], j["phase"] = 0, 0, "return"
            else:
                if not j["exchanged"]:
                    self.ledger.export_cargo(j["cargo"])
                    self.ledger.grant(j["faction"], j["want"], "bank_import")
                    self.ledger.receipts.append({"kind": "bank", "faction": j["faction"], "gave": j["give"], "got": j["want"], "game_ms": int(self.game_ms), "age": int(self.age)})
                    j["exchanged"] = True
                    j["cargo"] = None
                    self.counters["bank_trades"] += 1
                    self.history["bank_trades"] += 1
                    self.log("bank_trade_done", faction=j["faction"], gave=j["give"], got=j["want"], journey=j["id"])
                j["phase"] = "done"

    def _step_constructions(self) -> None:
        now = self.game_ms
        for eid in sorted(self.roads):
            r = self.roads[eid]
            if r["status"] == "building" and now >= int(r["done_ms"]):
                self.ledger.consume(r["rid"])
                r["rid"] = None
                r["status"] = "complete"
                self.counters["roads"] += 1
                self.history["roads"] += 1
                self.touch_topology()
                self.log("road_complete", faction=r["faction"], edge=eid)
                self._note_progress()
        for vid in sorted(self.villages):
            v = self.villages[vid]
            c = v.get("construction")
            if c and now >= int(c["done_ms"]):
                if c["kind"] == "warehouse":
                    self.ledger.consume(v["rid"])
                    v["rid"] = None
                    v["level"] = 1
                    v["status"] = "operational"
                    v["construction"] = None
                    v["ready_ms"] = now + rules.timing("district_stage")
                    v["next_recruit_ms"] = now + rules.timing("military_interval")
                    self.node_reserved.pop(v["node"], None)
                    j = self.journeys.get(v.get("journey", ""))
                    if j is not None:
                        j["phase"] = "done"
                    v.pop("journey", None)
                    self.history["founded"].append({"village": vid, "faction": v["faction"], "age": int(self.age), "game_ms": int(now)})
                    self.counters["settlements"] += 1
                    self.touch_topology()
                    self.log("village_founded", faction=v["faction"], village=vid, node=v["node"], name=v["name"])
                    self.pending_completions.append({"kind": "settlement", "faction": v["faction"], "village": vid})
                elif c["kind"] == "age":
                    v["construction"] = None
                    v["ready_ms"] = now
            u = v.get("upgrade")
            if u and now >= int(u["done_ms"]):
                self.ledger.consume(u["rid"])
                v["upgrade"] = None
                v["level"] = 2
                v["history"].append({"age": int(self.age), "event": "city", "game_ms": int(now)})
                self.counters["cities"] += 1
                self.history["cities"] += 1
                self.log("city_complete", faction=v["faction"], village=vid, name=v["name"])
                self.pending_completions.append({"kind": "city", "faction": v["faction"], "village": vid})

    def _note_progress(self) -> None:
        self.progress_pulse = self.pulses

    def _drain_completions(self) -> None:
        """VP changes are checked one completion at a time, in order, so the first qualifying completion is the recorded cause (PRD 10.1)."""
        while self.pending_completions:
            done = self.pending_completions.pop(0)
            self._note_progress()
            if self.phase != "RUNNING":
                continue
            fid = done["faction"]
            if self.vp(fid) >= rules.vp_target():
                ages.trigger(self, fid, done)
                self.pending_completions.clear()
                break

    # ------------------------------------------------------------------ military presentation
    def recruit_at(self, v: dict[str, Any], art: str = "", name: str = "") -> bool:
        """One recruit at this village if its garrison quota has room (a presentation unit: no cost, no combat). Shared by the barracks timer of the
        early ages and the ground factory of the last, so the quota is one rule."""
        vid = v["id"]
        quota = rules.limit("garrison_city") if int(v["level"]) >= 2 else rules.limit("garrison_settlement")
        mine = [u for u in self.units.values() if u["village"] == vid and u["status"] == "active" and u["age"] == self.age]
        if len(mine) >= quota:
            return False
        used = {int(u["slot"]) for u in mine}
        slot = next(s for s in range(rules.limit("garrison_city")) if s not in used)
        spec = rules.military_spec(self.age)
        city_unit = spec.get("city_unit") and int(v["level"]) >= 2 and slot % 2 == 1
        self._next_unit_id += 1
        uid = f"u{self._next_unit_id}"
        self.units[uid] = {"id": uid, "village": vid, "faction": v["faction"], "age": int(self.age), "slot": slot, "status": "active",
                           "art": art or (spec["city_unit"] if city_unit else spec["unit"]), "name": name or (spec.get("city_unit_name") if city_unit else spec.get("unit_name", "Soldier")),
                           "recruited_ms": int(self.game_ms)}
        self.counters["recruits"] += 1
        self.log("recruited", faction=v["faction"], village=vid, unit=uid)
        return True

    def _step_military(self) -> None:
        interval = rules.timing("military_interval")
        for vid in sorted(self.villages):
            v = self.villages[vid]
            if v["status"] != "operational" or self.game_ms < int(v.get("ready_ms", 0)):
                continue
            ops = v.get("ops")
            if ops and any(s["kind"] == "factory" for s in ops.get("sites", {}).values()):
                continue  # the ground factory musters this village's units from its ingredients (local_ops._step_factory)
            if self.game_ms < int(v.get("next_recruit_ms", 0)):
                continue
            v["next_recruit_ms"] = int(self.game_ms) + interval
            self.recruit_at(v)

    # ------------------------------------------------------------------ the AI pass
    def _ai_pass(self) -> None:
        if not self.ai_enabled:
            return
        n = len(self.fids)
        start = self.ai_pass_index % n
        self.ai_pass_index += 1
        for k in range(n):
            fid = self.fids[(start + k) % n]
            self.counters["ai_actions"] += ai_mod.decide(self, fid)

    # ------------------------------------------------------------------ ledger and sanity
    def check(self) -> None:
        self.ledger.check()
        nodes = [v["node"] for v in self.villages.values() if v["status"] in ACTIVE]
        if len(nodes) != len(set(nodes)):
            raise ValueError("two active villages on one node")
        for n in nodes:
            for o in self.board.adjacency[n]:
                if o in nodes:
                    raise ValueError(f"adjacent active villages {n} {o}")
        for v in self.villages.values():
            if v["status"] in ACTIVE:
                whs = [w for w in self.villages.values() if w["status"] in ACTIVE and w["node"] == v["node"]]
                if len(whs) != 1:
                    raise ValueError("a node must hold exactly one active warehouse")

    # ------------------------------------------------------------------ save and load
    def to_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "profile": self.profile, "run_id": self.run_id, "seed": self.seed, "map": self.map_name, "cosmetic_seed": self.cosmetic_seed, "game_ms": self.game_ms,
                "carry_ms": self._carry_ms, "clock_sequence": self.clock_sequence, "speed": self.speed, "paused": self.paused, "age": self.age, "epoch": self.epoch,
                "phase": self.phase, "rng": _rng_state(self.rng), "board": self.board.to_dict(), "factions": self.factions, "ledger": self.ledger.to_dict(),
                "villages": self.villages, "roads": self.roads, "journeys": self.journeys, "units": self.units, "node_reserved": self.node_reserved,
                "events": self.events[-200:], "history": self.history, "counters": self.counters, "setup": self.setup, "next_roll_ms": self.next_roll_ms,
                "last_roll": self.last_roll, "pulses": self.pulses, "pulses_total": self.pulses_total, "progress_pulse": self.progress_pulse, "ai": self.ai,
                "ai_pass_index": self.ai_pass_index, "ai_enabled": self.ai_enabled, "tree_claims": self.tree_claims, "local_ops_enabled": self.local_ops_enabled, "transition": self.transition, "final_result": self.final_result, "next_id": self._next_id, "next_unit_id": self._next_unit_id,
                "name_index": self._name_index, "topology_version": self.topology_version, "pending_completions": self.pending_completions}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GodWorld":
        if payload.get("profile") != rules.PROFILE or int(payload.get("schema", 0)) != SCHEMA:
            raise ValueError(f"unsupported God World save: profile {payload.get('profile')!r} schema {payload.get('schema')!r}")
        board = GodBoard.from_dict(payload["board"])
        w = cls(seed=int(payload["seed"]), run_id=str(payload.get("run_id") or f"god-{payload['seed']}"), board=board, map_name=str(payload.get("map", "")) or None)
        w.cosmetic_seed = int(payload.get("cosmetic_seed", w.cosmetic_seed))
        w.game_ms = int(payload["game_ms"])
        w._carry_ms = int(payload.get("carry_ms", 0))
        w.clock_sequence = int(payload.get("clock_sequence", 0))
        w.speed = int(payload.get("speed", 1))
        w.paused = bool(payload.get("paused", False))
        w.age = int(payload["age"])
        w.epoch = int(payload.get("epoch", 1))
        w.phase = str(payload["phase"])
        w.rng = _rng_load(payload["rng"])
        w.factions = [dict(f) for f in payload["factions"]]
        w.fids = [f["id"] for f in w.factions]
        w.ledger = Ledger.from_dict(payload["ledger"])
        w.villages = {k: dict(v) for k, v in payload["villages"].items()}
        w.roads = {k: dict(v) for k, v in payload["roads"].items()}
        w.journeys = {k: dict(v) for k, v in payload.get("journeys", {}).items()}
        w.units = {k: dict(v) for k, v in payload.get("units", {}).items()}
        w.node_reserved = {k: dict(v) for k, v in payload.get("node_reserved", {}).items()}
        w.events = list(payload.get("events", []))
        w.history = dict(payload.get("history", w.history))
        w.counters = dict(payload.get("counters", w.counters))
        w.setup = dict(payload["setup"])
        w.next_roll_ms = payload.get("next_roll_ms")
        w.last_roll = payload.get("last_roll")
        w.pulses = int(payload.get("pulses", 0))
        w.pulses_total = int(payload.get("pulses_total", 0))
        w.progress_pulse = int(payload.get("progress_pulse", 0))
        w.ai = {k: dict(v) for k, v in payload.get("ai", {}).items()} or {f: ai_mod.new_state() for f in w.fids}
        w.ai_pass_index = int(payload.get("ai_pass_index", 0))
        w.ai_enabled = bool(payload.get("ai_enabled", True))
        w.tree_claims = {str(k): str(x) for k, x in payload.get("tree_claims", {}).items()}
        w.local_ops_enabled = bool(payload.get("local_ops_enabled", True))
        w.transition = payload.get("transition")
        w.final_result = payload.get("final_result")
        w._next_id = int(payload.get("next_id", 1))
        w._next_unit_id = int(payload.get("next_unit_id", 1))
        w._name_index = int(payload.get("name_index", 0))
        w.topology_version = int(payload.get("topology_version", 0))
        w.pending_completions = list(payload.get("pending_completions", []))
        # references must resolve
        for v in w.villages.values():
            if v["node"] not in board.adjacency or v["faction"] not in w.fids:
                raise ValueError(f"village {v['id']} references an unknown node or faction")
        for eid, r in w.roads.items():
            if eid not in board.edge_endpoints:
                raise ValueError(f"road on unknown edge {eid}")
        for j in w.journeys.values():
            for key in ("cargo", "escrow"):
                ref = j.get(key)
                if ref and ref not in w.ledger.cargo and ref not in w.ledger.escrows:
                    raise ValueError(f"journey {j['id']} references missing {key} {ref}")
        for n in w.node_reserved:
            if n not in board.adjacency:
                raise ValueError(f"reservation on unknown node {n}")
        if w.transition is not None and w.transition.get("phase") == "TRANSITIONING" and w.phase != "TRANSITIONING":
            raise ValueError("save holds an unfinished transition in a running world")
        w.check()
        return w

    def state_hash(self) -> str:
        import hashlib
        import json

        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _rng_state(rng: random.Random) -> list[Any]:
    v, state, gauss = rng.getstate()
    return [v, list(state), gauss]


def _rng_load(payload: list[Any]) -> random.Random:
    rng = random.Random()
    rng.setstate((int(payload[0]), tuple(int(x) for x in payload[1]), payload[2]))
    return rng
