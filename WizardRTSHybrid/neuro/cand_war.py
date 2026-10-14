"""H5 (military orders) and H7 (trade and aid) candidates (neuro/candidates.py)."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from neuro import schema as S
from neuro.cand_base import Candidate, feat
from wizard_rts import diplomacy, regions, tech, trade

SQUAD_LINK = 6  # idle armed units within this many tiles of each other form one squad (single-link clustering)
MAX_SQUADS = 4
MAX_ENEMY_TARGETS = 4
MAX_NEST_TARGETS = 2
ENEMY_REACH = 120
NEST_REACH = 80
MAX_TRADE = 48
RESERVE = 12  # wares of a group kept at home before the rest counts as surplus
GIVE_CAP = 14
AID_GIVE = {"ration": 4, "water": 4}
WANT_WARE = {0: "ration", 1: "log", 2: "granite", 3: "iron", 4: "cloth"}  # the common ware asked for in each group (group 5, industrial, is never asked for)


class WarCandidates:
    world: Any
    faction: str
    observer: Any

    # ------------------------------------------------------------------------------------------------------------------------ H5
    @staticmethod
    def squads(fr: Any, armed_rows: list[int]) -> list[list[int]]:
        """Single-link clusters (SQUAD_LINK tiles) of the given own-unit rows, deterministic: rows sorted by unit id, clusters by their lowest row."""
        left = sorted(armed_rows)
        out: list[list[int]] = []
        while left:
            seed = left.pop(0)
            group, frontier = [seed], [seed]
            while frontier:
                a = fr.own_u[frontier.pop()]
                near = [r for r in left if max(abs(fr.own_u[r]["tx"] - a["tx"]), abs(fr.own_u[r]["ty"] - a["ty"])) <= SQUAD_LINK]
                for r in near:
                    left.remove(r)
                    group.append(r)
                    frontier.append(r)
            out.append(sorted(group))
        return out

    def military(self, obs: Any) -> list[Candidate]:
        """(squad, target) orders. A squad is a cluster of idle armed units; targets are the enemy buildings of factions at war that the faction remembers, blight nests
        it has seen, its own settlements with enemies in sight (defend) and its own centres (rally). The order is an attack-move of the whole squad to the target."""
        fr = obs.extra["frame"]
        w, me = fr.world, fr.me
        free = [i for i, u in enumerate(fr.own_u) if obs.u_armed[i] and u.get("status") in ("idle", "waiting_route", "moving", "ordered") and not u.get("deploying_ms")
                and (u.get("order") or {}).get("kind") != "attack"]
        groups = self.squads(fr, free) if free else []
        strength = [sum(self.observer.strength(fr.own_u[r]) for r in g) for g in groups]
        order = sorted(range(len(groups)), key=lambda k: (-strength[k], groups[k][0]))[:MAX_SQUADS]
        enemy_b = [m for m in fr.known_b if diplomacy.state_of(w, me, m["faction_name"]) == "war"]
        nests = list(self.observer.nest_memory.items())
        threatened = [j for j in range(len(obs.s_ids)) if obs.s_raw[j, S.N2_RAW.index("enemy_strength")] > 0]
        out: list[Candidate] = []
        s_n2 = {n: i for i, n in enumerate(S.N2_RAW)}
        for k in order:
            rows = groups[k]
            sid = fr.own_u[rows[0]]["id"]
            cx = sum(fr.own_u[r]["tx"] for r in rows) / len(rows)
            cy = sum(fr.own_u[r]["ty"] for r in rows) / len(rows)
            ids = [fr.own_u[r]["id"] for r in rows]
            ev = np.array([[u["tx"], u["ty"]] for u in fr.eu], dtype=np.float64).reshape(-1, 2)

            def ratio(tile: tuple[int, int]) -> float:
                near = float(fr.e_str[np.abs(ev - tile).max(axis=1) <= 12].sum()) if len(ev) else 0.0
                return strength[k] / (strength[k] + near + 1.0)

            def add(kind: str, tile: tuple[int, int], key_id: str, t_hp: float, kind_row: int, target_b: int, **fields: float) -> None:
                d = math.hypot(tile[0] - cx, tile[1] - cy)
                f = feat("H5", distance=min(d, 200.0) / 200.0, force_ratio=ratio(tile), **fields)
                row = np.zeros(len(S.N1_RAW), dtype=np.float32)
                row[S.N1_RAW.index("hp")] = t_hp
                row[S.N1_RAW.index("operational")] = 1.0
                dc = float(np.abs(fr.cc_xy - tile).max(axis=1).min()) if len(fr.cc_xy) else 340.0
                row[S.N1_RAW.index("dist_centre")] = min(dc, 340.0) / 34.0
                out.append(Candidate("H5", {"op": "move", "units": ids, "tx": int(tile[0]), "ty": int(tile[1]), "attack_move": True}, f, ("H5", kind, key_id, sid, len(rows)),
                                     {"squad": list(rows), "target_kind": kind_row, "target_n1": row, "target_b": target_b, "tile": tile}))

            near = sorted(((math.hypot(m["tile"][0] - cx, m["tile"][1] - cy), m["id"], m) for m in enemy_b), key=lambda t: (t[0], t[1]))
            for d, bid, m in [t for t in near if t[0] <= ENEMY_REACH][:MAX_ENEMY_TARGETS]:
                add("enemy_building", tuple(m["tile"]), bid, float(m["hp"]), fr.idx.get(m["kind"], 0), -1, t_enemy_building=1.0)
            nn = sorted(((math.hypot(m["tile"][0] - cx, m["tile"][1] - cy), nid, m) for nid, m in nests), key=lambda t: (t[0], t[1]))
            for d, nid, m in [t for t in nn if t[0] <= NEST_REACH][:MAX_NEST_TARGETS]:
                add("nest", tuple(m["tile"]), nid, float(m["hp"]), fr.idx.get("blight_nest", 0), -1, t_nest=1.0, is_nest=1.0)
            for j in threatened[:2]:
                cc = fr.standing[j]
                add("defend", (cc["tx"], cc["ty"] + 3), cc["id"], 1.0, fr.idx.get("warehouse", 0), obs.b_ids.index(cc["id"]) if cc["id"] in obs.b_ids else -1, t_defend=1.0)
            if fr.standing:
                cc = min(fr.standing, key=lambda c: (math.hypot(c["tx"] - cx, c["ty"] - cy), c["id"]))
                if math.hypot(cc["tx"] - cx, cc["ty"] - cy) > 8:
                    add("rally", (cc["tx"], cc["ty"] + 4), cc["id"], 1.0, fr.idx.get("warehouse", 0), obs.b_ids.index(cc["id"]) if cc["id"] in obs.b_ids else -1, t_rally=1.0)
        out += self.extra_orders(obs, fr, [groups[k] for k in order], enemy_b)
        return out

    # ------------------------------------------------------------------------------------------------------------------------ H7
    def trade(self, obs: Any) -> list[Candidate]:
        """(own post, partner post, give group, want group) caravans and aid caravans. Partners are the warehouses the faction remembers whose owner it is not
        in recent conflict with; the give side is a surplus ware at the post, the want side a common ware of the wanted group. The partner's own stock is not
        known, so the simulator may refuse (`partner_cannot_supply`): that is by design."""
        fr = obs.extra["frame"]
        w, me = fr.world, fr.me
        if not tech.unit_allowed(w, me, "caravan"):
            return []
        posts = sorted((b for b in fr.own_b if trade.is_post(b)), key=lambda b: (-sum(w.stocks.get(b["id"], {}).values()), b["id"]))[:2]
        partners = [m for m in fr.known_b if m["kind"] == "warehouse" and not trade.hostile(w, me, m["faction_name"])]
        if not posts or not partners:
            return []
        from neuro import features as F

        stock = self.observer.own_stock(fr)
        group_stock = np.zeros(S.N_GROUPS)
        for ware, n in stock.items():
            g = F.group_of(ware)
            if g is not None:
                group_stock[g] += n
        gives = [g for g in np.argsort(-group_stock, kind="stable") if group_stock[g] - RESERVE >= 6][:3]
        wants = [h for h in np.argsort(group_stock, kind="stable") if h in WANT_WARE][:3]
        n13 = {n: i for i, n in enumerate(S.N13_SLOT)}
        pos = {n: i for i, n in enumerate(S.N10_RAW)}
        vp_gap = float(obs.n10_raw[pos["vp_gap"]])
        out: list[Candidate] = []
        idx = {b["id"]: i for i, b in enumerate(fr.own_b)}
        for post in posts:
            st = w.stocks.get(post["id"], {})
            if any(int(st.get(g, 0)) < n for g, n in trade.CARAVAN_COST.items()):
                continue
            for m in sorted(partners, key=lambda m: (m["id"])):
                slot = obs.n13_factions.index(m["faction_name"]) if m["faction_name"] in obs.n13_factions else -1
                srow = obs.n13_slots[slot] if slot >= 0 else np.zeros(len(S.N13_SLOT), dtype=np.float32)
                d = max(abs(m["tile"][0] - post["tx"]), abs(m["tile"][1] - post["ty"]))
                base = dict(distance=min(d, 200) / 200.0, partner_pressure=float(srow[n13["their_pressure"]]), partner_vp_gap=float(srow[n13["their_vp"]]) - vp_gap,
                            already_trading=float(srow[n13["trades_done"]] > 0))
                for g in gives:
                    ware_g = max((k for k in st if F.group_of(k) == g and int(st[k]) > 0), key=lambda k: (int(st[k]), k), default=None)
                    if ware_g is None:
                        continue
                    n_give = min(GIVE_CAP, int(st[ware_g]) - 6 - int(trade.CARAVAN_COST.get(ware_g, 0)))
                    if n_give < 2:
                        continue
                    for h in wants:
                        if h == g:
                            continue
                        ware_h = WANT_WARE[int(h)]
                        n_want = int(trade.ware_value(ware_g) * n_give * 0.8 / trade.ware_value(ware_h))
                        if n_want < 1:
                            continue
                        n_want = min(n_want, 8)
                        f = feat("H7", surplus=(group_stock[g] - RESERVE) / 50.0, deficit=(RESERVE - group_stock[h]) / 50.0 if group_stock[h] < RESERVE else 0.0, **base,
                                 **{f"give_{S.GROUP_NAMES[g]}": 1.0, f"want_{S.GROUP_NAMES[h]}": 1.0})
                        out.append(Candidate("H7", {"op": "trade", "building": post["id"], "partner": m["id"], "give": {ware_g: n_give}, "want": {ware_h: n_want}}, f,
                                             ("H7", post["id"], m["id"], ware_g, ware_h), {"post": idx[post["id"]], "slot": slot}))
                if base["partner_pressure"] > 0 and all(int(st.get(k, 0)) >= n + trade.CARAVAN_COST.get(k, 0) + 2 for k, n in AID_GIVE.items()):
                    out.append(Candidate("H7", {"op": "trade", "building": post["id"], "partner": m["id"], "give": dict(AID_GIVE), "want": {"log": 1}}, feat("H7", **base, is_aid=1.0),
                                         ("H7", post["id"], m["id"], "aid"), {"post": idx[post["id"]], "slot": slot}))
                if len(out) >= MAX_TRADE:
                    return out[:MAX_TRADE]
        return out
