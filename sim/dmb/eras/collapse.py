"""Multi-faction collapse selection and inert ruin disposition (C11 / T098)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping

from sim.dmb.construction.scoring import ScoreService
from sim.dmb.eras.planner import faction_theoretical_capacity
from sim.dmb.industry import fraction
from sim.dmb.logistics.stock import CATAN_NS, INDUSTRIAL_NS, StockLedger
from sim.dmb.people.registry import PeopleService


def select_collapse_factions(
    scores: Mapping[str, int],
    capacities: Mapping[str, Fraction | str | Mapping[str, str]],
    *,
    winner_faction_id: str,
    sole_era_starter: bool = False,
    entered_faction_ids: list[str] | None = None,
) -> tuple[list[str], dict[str, str]]:
    """Pure collapse selection: all <5 VP + exactly one lowest remaining scorer.

    Tie-break among equal VP: lower theoretical capacity, then faction ID.
    Protect the sole remaining winner after <5 collapses (and sole-era starters).
    """
    if sole_era_starter:
        return [], {}

    universe = list(entered_faction_ids) if entered_faction_ids is not None else sorted(scores)
    if not universe:
        universe = sorted(scores)

    def cap(fid: str) -> Fraction:
        raw = capacities.get(fid, Fraction())
        if isinstance(raw, Fraction):
            return raw
        return fraction(raw)

    below = sorted(fid for fid in universe if int(scores.get(fid, 0)) < 5)
    reasons = {fid: "below_5_vp" for fid in below}
    remaining = [fid for fid in universe if fid not in below]

    if len(remaining) <= 1:
        # Only the winner (or nobody) left at/above threshold — protect sole survivor.
        return below, reasons

    # Exactly one lowest among remaining (may include the winner when others survive).
    lowest = sorted(
        remaining,
        key=lambda fid: (int(scores.get(fid, 0)), cap(fid), str(fid)),
    )[0]
    if lowest == winner_faction_id and len(remaining) == 1:
        return below, reasons

    reasons[lowest] = "lowest_remaining_scorer"
    return below + [lowest], reasons


def capacities_by_faction(snapshot: Any) -> dict[str, Fraction]:
    out: dict[str, Fraction] = {}
    factions = set(getattr(snapshot, "factions", {}) or {})
    for settlement in (getattr(snapshot, "settlements", {}) or {}).values():
        fid = settlement.get("faction_id")
        if fid:
            factions.add(str(fid))
    for fid in factions:
        out[str(fid)] = faction_theoretical_capacity(snapshot, str(fid))
    return out


@dataclass
class CollapseDisposition:
    state: Any

    def apply(
        self,
        collapse_faction_ids: list[str],
        *,
        reasons: Mapping[str, str] | None = None,
        transition_id: str | None = None,
    ) -> dict[str, Any]:
        """Retire operational assets for collapsed factions; keep living civilians displaced."""
        reasons = dict(reasons or {})
        receipts = self.state.command_receipts.setdefault("era_collapse", {})
        applied: list[dict[str, Any]] = []
        for faction_id in sorted(set(collapse_faction_ids)):
            receipt_key = f"{transition_id or 'transition'}:{faction_id}"
            if receipt_key in receipts:
                applied.append({"faction_id": faction_id, "idempotent": True, "receipt": receipts[receipt_key]})
                continue
            result = self._collapse_one(faction_id, reason=reasons.get(faction_id, "collapsed"))
            receipts[receipt_key] = result
            applied.append(result)
        return {"collapsed": applied, "receipt_keys": sorted(receipts)}

    def _collapse_one(self, faction_id: str, *, reason: str) -> dict[str, Any]:
        people = PeopleService(self.state)
        ledger = StockLedger(self.state)
        settlement_ids = [
            sid
            for sid, rec in self.state.settlements.items()
            if rec.get("faction_id") == faction_id and not rec.get("ruin_only")
        ]
        ruined: list[str] = []
        stock_losses: list[dict[str, Any]] = []
        displaced: list[str] = []
        disbanded_units: list[str] = []
        retired_roads: list[str] = []
        destroyed_carts: list[str] = []

        for sid in settlement_ids:
            ruined.append(self._ruin_settlement(sid, faction_id=faction_id, reason=reason))
            for person_id, person in list(self.state.people.items()):
                if not person.get("alive", True) or person.get("status") == "dead":
                    continue
                # Civilians at the settlement / employed there become displaced.
                at_site = person.get("settlement_id") == sid or person.get("node_id") == self.state.settlements[sid].get(
                    "node_id"
                )
                workplace = person.get("workplace_id")
                workplace_here = False
                if workplace and workplace in self.state.buildings:
                    workplace_here = self.state.buildings[workplace].get("settlement_id") == sid
                faction_member = person.get("faction_id") == faction_id
                if (at_site or workplace_here or faction_member) and person.get("role") != "soldier":
                    # Soldiers handled via unit disband; linked person stays alive displaced.
                    if person.get("unit_id") and person.get("role") == "soldier":
                        continue
                    if person.get("status") != "displaced":
                        people.displace(person_id, reason=f"faction_collapse:{faction_id}")
                        displaced.append(person_id)
                    person["faction_id"] = None
                    person["collapsed_faction_id"] = faction_id

            # Buildings → inert presentation (not ghost operational buildings).
            for bid, building in list(self.state.buildings.items()):
                if building.get("settlement_id") != sid and building.get("faction_id") != faction_id:
                    continue
                if building.get("settlement_id") not in (sid, None) and building.get("settlement_id") != sid:
                    if building.get("faction_id") != faction_id:
                        continue
                if building.get("settlement_id") == sid or (
                    building.get("faction_id") == faction_id and building.get("node_id")
                    == self.state.settlements[sid].get("node_id")
                ):
                    self._inert_building(building)
                    if building.get("slot_kind") == "warehouse" or str(
                        building.get("def_id") or building.get("definition_id") or ""
                    ).endswith("warehouse"):
                        loss = self._retire_store(ledger, building["id"], cause_id=f"collapse:{faction_id}:{bid}")
                        if loss:
                            stock_losses.append(loss)

        # Roads: clear ownership (no road capacity from ruins).
        for rid, road in list(self.state.roads.items()):
            if road.get("faction_id") == faction_id:
                road["faction_id"] = None
                road["collapsed_owner"] = faction_id
                road["operational"] = False
                retired_roads.append(rid)

        # Military disband — units gone; linked Persons remain alive as displaced civilians.
        for uid, unit in list(self.state.units.items()):
            if unit.get("faction_id") != faction_id:
                continue
            person_id = unit.get("person_id")
            unit["status"] = "disbanded"
            unit["alive"] = False
            unit["faction_id"] = None
            unit["disband_reason"] = f"faction_collapse:{faction_id}"
            disbanded_units.append(uid)
            if person_id and person_id in self.state.people:
                person = self.state.people[person_id]
                if person.get("alive", True) and person.get("status") != "dead":
                    people.displace(person_id, reason=f"unit_disbanded:{uid}")
                    person["faction_id"] = None
                    person["collapsed_faction_id"] = faction_id
                    person["unit_id"] = None
                    if person_id not in displaced:
                        displaced.append(person_id)

        for fid, formation in list(self.state.formations.items()):
            if formation.get("faction_id") == faction_id:
                formation["status"] = "disbanded"
                formation["faction_id"] = None

        for cid, cart in list(self.state.carts.items()):
            if cart.get("owner_faction") != faction_id and cart.get("faction_id") != faction_id:
                continue
            goods: dict[str, int] = {}
            for lot in list(cart.get("cargo_lots") or []):
                if lot.get("status") != "aboard":
                    continue
                good = str(lot["good_id"])
                goods[good] = goods.get(good, 0) + int(lot["quantity"])
            loss = ledger.record_loss(
                goods or {"_empty": 0},
                cart_id=cid,
                cause_id=f"collapse-cart:{faction_id}:{cid}",
                source=f"cart:{cid}",
            )
            stock_losses.append(loss)
            cart["owner_faction"] = None
            cart["faction_id"] = None
            cart["status"] = "destroyed"
            destroyed_carts.append(cid)

        faction = self.state.factions.get(faction_id)
        if faction is not None:
            faction["status"] = "collapsed"
            faction["collapse_reason"] = reason
            faction["operational"] = False

        return {
            "faction_id": faction_id,
            "reason": reason,
            "ruined_settlements": ruined,
            "displaced_people": sorted(set(displaced)),
            "disbanded_units": disbanded_units,
            "retired_roads": retired_roads,
            "destroyed_carts": destroyed_carts,
            "stock_losses": stock_losses,
            "idempotent": False,
        }

    def _ruin_settlement(self, settlement_id: str, *, faction_id: str, reason: str) -> str:
        settlement = self.state.settlements[settlement_id]
        settlement["status"] = "inert"
        settlement["ruin_only"] = True
        settlement["operational"] = False
        settlement["legacy"] = False
        settlement["upgraded"] = False
        settlement["collision"] = False
        settlement["blocks_placement"] = False
        settlement["road_capacity"] = 0
        settlement["site_reservation"] = False
        settlement["loot"] = []
        settlement["vp"] = 0
        settlement["faction_id_before_collapse"] = faction_id
        settlement["faction_id"] = None
        settlement["collapse_reason"] = reason
        settlement["inert_ruin"] = True
        return settlement_id

    def _inert_building(self, building: dict[str, Any]) -> None:
        building["status"] = "inert_ruin"
        building["active"] = False
        building["owned"] = False
        building["faction_id"] = None
        building["collision"] = False
        building["usable_capacity"] = 0.0
        building["loot"] = []
        building["ruin_only"] = True

    def _retire_store(self, ledger: StockLedger, building_id: str, *, cause_id: str) -> dict[str, Any] | None:
        store_id = f"store:{building_id}"
        store = self.state.stocks.get(store_id)
        if not store:
            return None
        loss_goods: dict[str, int] = {}
        for ns_name in (CATAN_NS, INDUSTRIAL_NS):
            ns = store.get(ns_name)
            if not isinstance(ns, dict):
                continue
            for good, entry in ns.items():
                if not isinstance(entry, dict):
                    continue
                qty = int(entry.get("available", 0)) + int(entry.get("reserved", 0)) + int(entry.get("escrow", 0))
                if qty > 0:
                    loss_goods[good] = loss_goods.get(good, 0) + qty
                    entry["available"] = 0
                    entry["reserved"] = 0
                    entry["escrow"] = 0
        if not loss_goods:
            return None
        return ledger.record_loss(loss_goods, cause_id=cause_id, source=store_id)


def plan_collapse_fields(snapshot: Any, trigger: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Compute collapse fields for an EraTransitionPlan without mutating state."""
    if hasattr(trigger, "to_dict"):
        trig = trigger.to_dict()
    else:
        trig = dict(trigger)
    winner = str(trig.get("winner_faction_id") or "")
    scores = dict(trig.get("scores_at_trigger") or {}) or ScoreService(snapshot).scores()
    caps = capacities_by_faction(snapshot)
    clock = getattr(snapshot, "clock", {}) or {}
    era_meta = (getattr(snapshot, "board", {}) or {}).get("era") or {}
    started = list(
        clock.get("started_faction_ids")
        or era_meta.get("started_faction_ids")
        or sorted(scores)
    )
    sole = bool(clock.get("sole_era_starter") or era_meta.get("sole_era_starter"))
    if not sole and len(started) == 1:
        sole = True
    collapsed, reasons = select_collapse_factions(
        scores,
        caps,
        winner_faction_id=winner,
        sole_era_starter=sole,
        entered_faction_ids=started,
    )
    survivors = sorted(fid for fid in started if fid not in collapsed)
    return {
        "collapse_faction_ids": collapsed,
        "collapse_reasons": reasons,
        "survivor_faction_ids": survivors,
        "faction_theoretical_capacities": {
            fid: str(caps.get(fid, Fraction())) for fid in sorted(caps)
        },
    }
