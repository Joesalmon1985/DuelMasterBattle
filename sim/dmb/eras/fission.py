"""Compact fission pairing and successor ownership (C11 / T099)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from sim.dmb.ai.diplomacy import DiplomacyService, REL_NEUTRAL
from sim.dmb.core.types import TypeValidationError
from sim.dmb.eras.planner import rank_theoretical_sites
from sim.dmb.technology.research import TechnologyService
from sim.dmb.world.board import HexBoard


def _board_from_snapshot(snapshot: Any) -> HexBoard:
    raw = (getattr(snapshot, "board", {}) or {}).get("topology") or {}
    if not raw.get("hexes"):
        raise TypeValidationError("fission requires board topology")
    return HexBoard.from_dict(raw)


def node_distance(board: HexBoard, a: str, b: str) -> int:
    if a == b:
        return 0
    return len(board.shortest_path(a, b)) - 1


def within_pair_distance(board: HexBoard, site_a: Mapping[str, Any], site_b: Mapping[str, Any]) -> int:
    return node_distance(board, str(site_a["node_id"]), str(site_b["node_id"]))


def all_pairings(site_ids: Sequence[str]) -> list[tuple[tuple[str, str], tuple[str, str]]]:
    """The three perfect matchings of four sites; pairs and pair-order sorted by ID."""
    ids = sorted(site_ids)
    if len(ids) != 4:
        raise TypeValidationError(f"compact fission pairing requires exactly 4 sites, got {len(ids)}")
    a, b, c, d = ids
    raw = [
        (tuple(sorted((a, b))), tuple(sorted((c, d)))),
        (tuple(sorted((a, c))), tuple(sorted((b, d)))),
        (tuple(sorted((a, d))), tuple(sorted((b, c)))),
    ]
    return [tuple(sorted(pairing)) for pairing in raw]  # type: ignore[misc]


def choose_compact_pairing(
    sites: Sequence[Mapping[str, Any]],
    board: HexBoard,
) -> dict[str, Any]:
    """Minimise summed within-pair graph distances; stable tie by sorted site IDs."""
    by_id = {str(site["settlement_id"]): site for site in sites}
    if len(by_id) != 4:
        raise TypeValidationError("choose_compact_pairing requires four sites")
    candidates: list[tuple[int, tuple[str, ...], tuple[tuple[str, str], tuple[str, str]]]] = []
    for pairing in all_pairings(list(by_id)):
        total = 0
        for pair in pairing:
            total += within_pair_distance(board, by_id[pair[0]], by_id[pair[1]])
        flat = tuple(sorted(sid for pair in pairing for sid in pair))
        candidates.append((total, flat, pairing))
    candidates.sort(key=lambda row: (row[0], row[1], row[2]))
    best_total, _flat, best_pairing = candidates[0]
    return {
        "pairing": [{"cores": list(pair)} for pair in best_pairing],
        "within_pair_distance_sum": best_total,
        "candidates_evaluated": len(candidates),
    }


def top_sites_for_faction(snapshot: Any, faction_id: str, *, limit: int = 4) -> list[dict[str, Any]]:
    ranked = [
        row
        for row in rank_theoretical_sites(snapshot)
        if row.get("faction_id") == faction_id
    ]
    return ranked[:limit]


def assign_nearest_core(
    settlement: Mapping[str, Any],
    cores: Sequence[Mapping[str, Any]],
    board: HexBoard,
) -> str:
    """Nearest successor core by graph distance, then core settlement ID."""
    node_id = str(settlement["node_id"])

    def key(core: Mapping[str, Any]) -> tuple[int, str]:
        return (node_distance(board, node_id, str(core["node_id"])), str(core["settlement_id"]))

    best = sorted(cores, key=key)[0]
    return str(best["successor_faction_id"])


def plan_fission(
    snapshot: Any,
    *,
    parent_faction_id: str,
    successor_faction_ids: Sequence[str],
    split: bool = True,
) -> dict[str, Any]:
    """Pure ownership plan for a survivor split (or non-split dual-core selection).

    Successor IDs must be supplied (reserved block); planner/fission does not allocate.
    """
    board = _board_from_snapshot(snapshot)
    successors = list(successor_faction_ids)
    if split:
        if len(successors) != 2:
            raise TypeValidationError("split requires exactly two successor faction ids")
        sites = top_sites_for_faction(snapshot, parent_faction_id, limit=4)
        if len(sites) < 4:
            raise TypeValidationError(
                f"mandatory compact fission needs 4 sites; parent has {len(sites)}"
            )
        choice = choose_compact_pairing(sites, board)
        core_pairs = []
        for index, pair in enumerate(choice["pairing"]):
            core_pairs.append(
                {
                    "successor_faction_id": successors[index],
                    "core_settlement_ids": list(pair["cores"]),
                    "parent_faction_id": parent_faction_id,
                }
            )
    else:
        if len(successors) != 1:
            raise TypeValidationError("non-split survivor needs one successor id (usually parent)")
        sites = top_sites_for_faction(snapshot, parent_faction_id, limit=2)
        core_pairs = [
            {
                "successor_faction_id": successors[0],
                "core_settlement_ids": [s["settlement_id"] for s in sites],
                "parent_faction_id": parent_faction_id,
            }
        ]
        choice = {"pairing": [{"cores": [s["settlement_id"] for s in sites]}], "within_pair_distance_sum": 0}

    core_lookup: dict[str, dict[str, Any]] = {}
    for pair in core_pairs:
        sid_list = pair["core_settlement_ids"]
        for sid in sid_list:
            settlement = (getattr(snapshot, "settlements", {}) or {}).get(sid) or {}
            core_lookup[sid] = {
                "settlement_id": sid,
                "node_id": settlement.get("node_id"),
                "successor_faction_id": pair["successor_faction_id"],
            }

    settlement_assignments: dict[str, str] = {}
    for sid, settlement in sorted((getattr(snapshot, "settlements", {}) or {}).items()):
        if settlement.get("faction_id") != parent_faction_id:
            continue
        if settlement.get("ruin_only"):
            continue
        if sid in core_lookup:
            settlement_assignments[sid] = core_lookup[sid]["successor_faction_id"]
            continue
        settlement_assignments[sid] = assign_nearest_core(settlement, list(core_lookup.values()), board)

    # Roads: minimum endpoint distance to any core of each successor.
    road_assignments: dict[str, str] = {}
    for rid, road in sorted((getattr(snapshot, "roads", {}) or {}).items()):
        if road.get("faction_id") != parent_faction_id:
            continue
        a = str(road.get("a") or road.get("from") or "")
        b = str(road.get("b") or road.get("to") or "")

        def road_key(succ: str) -> tuple[int, str]:
            cores = [c for c in core_lookup.values() if c["successor_faction_id"] == succ]
            dists = []
            for core in cores:
                dists.append(min(node_distance(board, a, str(core["node_id"])), node_distance(board, b, str(core["node_id"]))))
            return (min(dists) if dists else 10**9, succ)

        road_assignments[rid] = sorted(successors, key=road_key)[0]

    unit_assignments: dict[str, str] = {}
    for uid, unit in sorted((getattr(snapshot, "units", {}) or {}).items()):
        if unit.get("faction_id") != parent_faction_id:
            continue
        home = unit.get("home_settlement_id") or unit.get("settlement_id")
        if home and home in settlement_assignments:
            unit_assignments[uid] = settlement_assignments[home]
            continue
        node_id = str(unit.get("node_id") or "")
        if not node_id:
            unit_assignments[uid] = successors[0]
            continue
        fake = {"node_id": node_id, "settlement_id": f"unit-home:{uid}"}
        unit_assignments[uid] = assign_nearest_core(fake, list(core_lookup.values()), board)

    cart_assignments: dict[str, str] = {}
    for cid, cart in sorted((getattr(snapshot, "carts", {}) or {}).items()):
        owner = cart.get("owner_faction") or cart.get("faction_id")
        if owner != parent_faction_id:
            continue
        home = cart.get("home_settlement_id") or cart.get("settlement_id")
        if home and home in settlement_assignments:
            cart_assignments[cid] = settlement_assignments[home]
            continue
        node_id = str(cart.get("node_id") or "")
        if node_id:
            cart_assignments[cid] = assign_nearest_core(
                {"node_id": node_id}, list(core_lookup.values()), board
            )
        else:
            cart_assignments[cid] = successors[0]

    research_assignments = {succ: parent_faction_id for succ in successors}
    # People are not duplicated — assignment is via settlement/location at commit.
    person_assignments: dict[str, str] = {}
    for pid, person in sorted((getattr(snapshot, "people", {}) or {}).items()):
        if person.get("faction_id") != parent_faction_id:
            continue
        sid = person.get("settlement_id")
        if sid and sid in settlement_assignments:
            person_assignments[pid] = settlement_assignments[sid]
            continue
        node_id = str(person.get("node_id") or "")
        if node_id:
            person_assignments[pid] = assign_nearest_core(
                {"node_id": node_id}, list(core_lookup.values()), board
            )
        else:
            person_assignments[pid] = successors[0]

    return {
        "parent_faction_id": parent_faction_id,
        "split": split,
        "successor_faction_ids": list(successors),
        "core_pairs": core_pairs,
        "pairing_metrics": {
            "within_pair_distance_sum": choice.get("within_pair_distance_sum"),
        },
        "settlement_assignments": settlement_assignments,
        "road_assignments": road_assignments,
        "unit_assignments": unit_assignments,
        "cart_assignments": cart_assignments,
        "research_assignments": research_assignments,
        "person_assignments": person_assignments,
        "sibling_relation": {"status": REL_NEUTRAL, "trade_permitted": True},
    }


@dataclass
class FissionDisposition:
    state: Any

    def apply(self, fission_plan: Mapping[str, Any], *, transition_id: str | None = None) -> dict[str, Any]:
        """Apply ownership reassignment. Does not create Persons. Cargo stays aboard."""
        receipts = self.state.command_receipts.setdefault("era_fission", {})
        key = f"{transition_id or 'transition'}:{fission_plan.get('parent_faction_id')}"
        if key in receipts:
            return {"idempotent": True, "receipt": receipts[key]}

        parent = str(fission_plan["parent_faction_id"])
        successors = list(fission_plan["successor_faction_ids"])
        cargo_before = {
            cid: [dict(lot) for lot in (cart.get("cargo_lots") or [])]
            for cid, cart in self.state.carts.items()
            if cid in (fission_plan.get("cart_assignments") or {})
        }

        # Create successor faction records if missing.
        for succ in successors:
            bucket = self.state.factions.setdefault(
                succ,
                {
                    "id": succ,
                    "status": "active",
                    "parent_faction_id": parent,
                    "lineage": {"parent": parent, "kind": "fission_successor"},
                },
            )
            bucket.setdefault("parent_faction_id", parent)
            bucket["status"] = "active"

        for sid, succ in (fission_plan.get("settlement_assignments") or {}).items():
            settlement = self.state.settlements.get(sid)
            if settlement is None:
                continue
            settlement["faction_id"] = succ
            settlement["fission_parent_faction_id"] = parent

        for bid, building in self.state.buildings.items():
            sid = building.get("settlement_id")
            if sid in (fission_plan.get("settlement_assignments") or {}):
                building["faction_id"] = fission_plan["settlement_assignments"][sid]

        for rid, succ in (fission_plan.get("road_assignments") or {}).items():
            if rid in self.state.roads:
                self.state.roads[rid]["faction_id"] = succ

        for uid, succ in (fission_plan.get("unit_assignments") or {}).items():
            if uid in self.state.units:
                self.state.units[uid]["faction_id"] = succ

        for cid, succ in (fission_plan.get("cart_assignments") or {}).items():
            cart = self.state.carts.get(cid)
            if cart is None:
                continue
            cart["owner_faction"] = succ
            cart["faction_id"] = succ
            # Cargo physically unchanged.
            expected = cargo_before.get(cid) or []
            actual = cart.get("cargo_lots") or []
            if [lot.get("id") for lot in expected] != [lot.get("id") for lot in actual]:
                raise TypeValidationError(f"fission altered cargo aboard {cid}")

        tech = TechnologyService(self.state)
        for succ, source in (fission_plan.get("research_assignments") or {}).items():
            tech.inherit_to_successor(str(source), str(succ))

        for pid, succ in (fission_plan.get("person_assignments") or {}).items():
            person = self.state.people.get(pid)
            if person is None:
                continue
            person["faction_id"] = succ
            # Same person id — never clone.

        dip = DiplomacyService(self.state)
        if len(successors) == 2:
            a, b = successors[0], successors[1]
            # Siblings begin neutral / trade-permitted (default).
            store = dip._store()
            from sim.dmb.ai.diplomacy import _pair_key

            key_rel = _pair_key(a, b)
            store["relations"][key_rel] = {
                "status": REL_NEUTRAL,
                "trade_permitted": True,
                "cause": "fission_siblings",
                "a": a,
                "b": b,
            }
            # Copy external relations from parent toward others.
            for other in list(self.state.factions):
                if other in {parent, a, b}:
                    continue
                rel = dip.relation(parent, other)
                if rel != REL_NEUTRAL:
                    for succ in (a, b):
                        store["relations"][_pair_key(succ, other)] = {
                            "status": rel,
                            "cause": "inherited_from_parent",
                            "a": succ,
                            "b": other,
                        }

        if parent not in successors and parent in self.state.factions:
            self.state.factions[parent]["status"] = "succeeded"
            self.state.factions[parent]["operational"] = False

        people_ids_before = set(self.state.people)
        receipt = {
            "parent_faction_id": parent,
            "successors": successors,
            "core_pairs": list(fission_plan.get("core_pairs") or []),
            "settlement_assignments": dict(fission_plan.get("settlement_assignments") or {}),
            "people_count": len(self.state.people),
            "people_ids_unchanged": people_ids_before == set(self.state.people),
            "sibling_trade_permitted": (
                dip.trade_permitted(successors[0], successors[1]) if len(successors) == 2 else None
            ),
        }
        receipts[key] = receipt
        return {"idempotent": False, "receipt": receipt}
