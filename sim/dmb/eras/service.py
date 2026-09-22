"""Atomic era transition service (C11 / T104)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from sim.dmb.construction.scoring import ScoreService, VP_THRESHOLD
from sim.dmb.core.types import TypeValidationError
from sim.dmb.eras.collapse import CollapseDisposition, plan_collapse_fields
from sim.dmb.eras.continuity import ContinuityService
from sim.dmb.eras.fission import FissionDisposition, plan_fission
from sim.dmb.eras.planner import (
    EraTransitionPlan,
    EraTransitionPlanner,
    TransitionTrigger,
    validate_plan_freshness,
)
from sim.dmb.eras.safeguards import mark_mandatory_fission, plan_undersized_mandatory_split, sole_era_starter_ids
from sim.dmb.eras.upgrades import CoreUpgradeService, mark_legacy_sites
from sim.dmb.hazards.service import CatastropheService
from sim.dmb.industry import fraction_wire
from sim.dmb.technology.draft import DraftService
from sim.dmb.time.turns import TurnScheduler


def _freeze_clocks(state: Any) -> dict[str, Any]:
    clock = state.clock
    tokens = dict(clock.get("pause_tokens") or {})
    tokens["era_transition"] = True
    clock["pause_tokens"] = tokens
    clock["era_transition_frozen"] = True
    # Freeze leases: mark active leases as frozen for revalidation after commit.
    frozen = []
    for lid, lease in list((state.leases or {}).items()):
        if lease.get("status") in {"active", "open", None} or lease.get("active", True):
            lease["frozen_for_era_transition"] = True
            lease["status"] = lease.get("status") or "frozen"
            frozen.append(lid)
    return {"pause_tokens": tokens, "frozen_leases": frozen}


def _hazard_rollover(state: Any, *, next_era: str) -> dict[str, Any]:
    cat = state.hazards.setdefault("catastrophe", {})
    before_cubes = deepcopy(cat.get("cubes") or {})
    # Reset era escalation/counter; preserve cube type/cause/active.
    cat["era_completed_rounds"] = 0
    cat["escalation"] = 0
    cat["era_start_turn"] = int(state.clock.get("turn", 0))
    cat["era_id"] = next_era
    # Do not delete or duplicate cubes.
    for cube in (cat.get("cubes") or {}).values():
        cube["era_rollover"] = next_era
    return {
        "cubes_preserved": sorted(before_cubes.keys()),
        "era_completed_rounds": 0,
        "era_id": next_era,
    }


def _rebind_historic_industry(state: Any, settlement_id: str) -> dict[str, Any]:
    """Ensure upgraded Historic core has a working cross-terrain production chain."""
    from sim.dmb.industry.layers import ResourceLayerService
    from sim.dmb.industry.primary import PrimaryChannel
    from sim.dmb.industry.routes import FactoryRoute, ProcessorBinding
    from sim.dmb.industry.service import IndustryService
    from sim.dmb.eras.upgrades import load_historic_core_config

    settlement = state.settlements.get(settlement_id) or {}
    node_id = str(settlement.get("node_id") or "")
    cfg = load_historic_core_config()
    terrain_map = cfg.get("terrain_industrial") or {}
    industry = IndustryService(state)
    layers = ResourceLayerService(state.industry)

    primaries = [
        b
        for b in state.buildings.values()
        if b.get("settlement_id") == settlement_id and str(b.get("slot_kind") or "") == "primary"
    ]
    processors = [
        b
        for b in state.buildings.values()
        if b.get("settlement_id") == settlement_id and str(b.get("slot_kind") or "") == "processor"
    ]
    factories = sorted(
        [
            b
            for b in state.buildings.values()
            if b.get("settlement_id") == settlement_id and str(b.get("slot_kind") or "") == "factory"
        ],
        key=lambda b: int(b.get("slot_index") or 0),
    )
    if not primaries or not processors or not factories:
        return {"status": "insufficient_slots", "settlement_id": settlement_id}

    # Resolve touching hex terrains.
    node_hexes = (state.board or {}).get("node_hexes") or {}
    hex_terrain = (state.board or {}).get("hex_terrain") or {}
    touching = list(node_hexes.get(node_id) or [])
    by_terrain: dict[str, list[str]] = {}
    for hid in touching:
        terrain = str(hex_terrain.get(hid) or "")
        if terrain:
            by_terrain.setdefault(terrain, []).append(hid)

    channel_by_resource: dict[str, str] = {}
    bound_terrains: list[str] = []
    for i, primary in enumerate(sorted(primaries, key=lambda b: str(b["id"]))):
        terrains = sorted(by_terrain.keys())
        if not terrains:
            continue
        terrain = terrains[i % len(terrains)]
        hid = by_terrain[terrain][0]
        meta = terrain_map.get(terrain) or {}
        renew = meta.get("renewable")
        finite = meta.get("finite")
        primary["terrain"] = terrain
        primary["hex_id"] = hid
        primary["era"] = "historic"
        if renew:
            rid, label = renew[0], renew[1]
            primary["label"] = primary.get("label") or f"{label} workings"
            primary["resource_name"] = label
            layer = layers.create_layer(hid, rid, "historic", int(state.clock.get("cycle") or 0), finite=False)
            ch = PrimaryChannel(
                f"channel:{primary['id']}:renewable",
                str(primary["id"]),
                node_id,
                terrain,
                "historic",
                int(state.clock.get("cycle") or 0),
                rid,
                layer.layer_id,
                False,
                Fraction(1, 10),
                True,
            )
            industry.install_channel(ch)
            channel_by_resource[rid] = ch.channel_id
            bound_terrains.append(terrain)
        if finite:
            rid, label = finite[0], finite[1]
            layer = layers.create_layer(hid, rid, "historic", int(state.clock.get("cycle") or 0), finite=True)
            ch = PrimaryChannel(
                f"channel:{primary['id']}:finite",
                str(primary["id"]),
                node_id,
                terrain,
                "historic",
                int(state.clock.get("cycle") or 0),
                rid,
                layer.layer_id,
                True,
                Fraction(1, 10),
                True,
            )
            industry.install_channel(ch)
            channel_by_resource.setdefault(rid, ch.channel_id)

    # Prefer full-catalogue Historic recipes; fall back to MVP subset wiring.
    from sim.dmb.content.catalogue import recipes_for_era

    recipe = None
    for prefer_mvp in (False, True):
        for r in recipes_for_era("historic", mvp_only=prefer_mvp):
            a, b = str(r.get("input_a_id")), str(r.get("input_b_id"))
            if a in channel_by_resource and b in channel_by_resource and a != b:
                recipe = r
                break
        if recipe is not None:
            break
    if recipe is None:
        return {
            "status": "no_cross_terrain_recipe",
            "settlement_id": settlement_id,
            "channels": sorted(channel_by_resource),
            "terrains": sorted(set(bound_terrains)),
        }

    processor = processors[0]
    pid = str(processor["id"])
    binding = ProcessorBinding(
        building_id=pid,
        recipe_id=str(recipe["id"]),
        era="historic",
        input_a_channel_id=channel_by_resource[str(recipe["input_a_id"])],
        input_b_channel_id=channel_by_resource[str(recipe["input_b_id"])],
        output_capacity=Fraction(1, 10),
        health=100,
        max_health=100,
        active=True,
    )
    industry.install_processor(binding)
    unit_defs = list((cfg.get("core_upgrade") or {}).get("unit_defs") or [
        "unit.historic.skirmisher",
        "unit.historic.line",
        "unit.historic.heavy",
    ])
    factory_ids = []
    for i, factory in enumerate(factories[:3]):
        fid = str(factory["id"])
        unit_def = unit_defs[min(i, len(unit_defs) - 1)]
        industry.factories.create(
            fid,
            node_id=node_id,
            faction_id=str(settlement.get("faction_id") or ""),
            era="historic",
            unit_def_id=unit_def,
        )
        industry.factories.factories[fid]["meter"] = fraction_wire(Fraction())
        industry.factories.factories[fid]["settlement_id"] = settlement_id
        # Cost from unit archetype processed_units — default 2/3/5.
        cost = 2 if "skirmisher" in unit_def else 3 if "line" in unit_def else 5
        industry.install_route(
            FactoryRoute(fid, pid, unit_def, cost, Fraction(1))
        )
        factory_ids.append(fid)

    return {
        "status": "operational",
        "settlement_id": settlement_id,
        "recipe_id": recipe["id"],
        "processor_id": pid,
        "factory_ids": factory_ids,
        "channels": sorted(channel_by_resource),
        "terrains": sorted(set(bound_terrains)),
    }


@dataclass
class EraService:
    state: Any

    def _is_upgradeable_core_candidate(self, settlement_id: str) -> bool:
        """Cores need centre+warehouse slots (full foundation sites)."""
        has_centre = False
        has_wh = False
        for building in (self.state.buildings or {}).values():
            if building.get("settlement_id") != settlement_id:
                continue
            kind = str(building.get("slot_kind") or "")
            if kind == "centre":
                has_centre = True
            if kind == "warehouse":
                has_wh = True
        settlement = (self.state.settlements or {}).get(settlement_id) or {}
        if settlement.get("warehouse_id") or settlement.get("centre_id"):
            has_wh = has_wh or bool(settlement.get("warehouse_id"))
            has_centre = has_centre or bool(settlement.get("centre_id"))
        return has_centre and has_wh

    def request_transition(
        self,
        winner_faction_id: str,
        event_id: str,
        *,
        source_action_id: str | None = None,
    ) -> EraTransitionPlan:
        """Freeze, snapshot scores, build hashed plan. Does not mutate economy yet."""
        receipts = self.state.command_receipts.setdefault("era_transition", {})
        if any(r.get("status") == "committed" for r in receipts.values()):
            raise TypeValidationError("era transition already committed")
        freeze = _freeze_clocks(self.state)
        scores = ScoreService(self.state).scores()
        if int(scores.get(winner_faction_id, 0)) < VP_THRESHOLD:
            raise TypeValidationError(f"{winner_faction_id} below {VP_THRESHOLD} VP")
        trigger = TransitionTrigger(
            event_id=event_id,
            winner_faction_id=winner_faction_id,
            source_action_id=source_action_id,
            scores_at_trigger=scores,
        )
        # Snapshot world_version for freshness.
        plan = EraTransitionPlanner().plan(self.state, trigger)
        # Enrich collapse already on plan; prepare reserved successor IDs peek-only.
        pending = {
            "plan": plan.to_dict(),
            "freeze": freeze,
            "status": "planned",
            "world_version": int(self.state.world_version),
        }
        receipts[event_id] = pending
        self.state.clock["pending_era_transition"] = event_id
        self.state.board["era_transition_pending"] = True
        return plan

    def commit(self, plan: EraTransitionPlan | dict[str, Any]) -> dict[str, Any]:
        """Atomic commit: collapse → fission → cores → legacy → continuity → hazards → roster."""
        body = plan.to_dict() if isinstance(plan, EraTransitionPlan) else dict(plan)
        event_id = str(
            (body.get("trigger") or {}).get("event_id")
            or body.get("transition_id")
            or body.get("id")
            or ""
        )
        receipts = self.state.command_receipts.setdefault("era_transition", {})
        existing = receipts.get(event_id) or {}
        if existing.get("status") == "committed":
            return {"idempotent": True, "receipt": existing}
        # Also accept a committed receipt body re-submitted without trigger wrapper.
        if body.get("status") == "committed" and body.get("transition_id"):
            stored = receipts.get(str(body.get("transition_id"))) or {}
            if stored.get("status") == "committed":
                return {"idempotent": True, "receipt": stored}

        freshness = validate_plan_freshness(body, self.state)
        if not freshness.get("can_commit"):
            # Allow commit when world_version matches the planned pending receipt even if
            # freeze tokens changed hash slightly — require matching pending plan_hash.
            pending = existing if existing.get("status") == "planned" else None
            if not pending or pending.get("plan", {}).get("plan_hash") != body.get("plan_hash"):
                raise TypeValidationError(f"stale_or_tampered_plan:{freshness.get('reason')}")
            if int(pending.get("world_version", -1)) != int(self.state.world_version):
                raise TypeValidationError("stale_or_tampered_plan:world_version")

        # Bump version once at commit boundary.
        self.state.world_version = int(self.state.world_version) + 1
        next_era = str(body.get("next_era") or "historic")
        winner = str((body.get("trigger") or {}).get("winner_faction_id") or "")

        # 1) Collapse
        collapse_ids = list(body.get("collapse_faction_ids") or [])
        collapse_reasons = dict(body.get("collapse_reasons") or {})
        collapse_result = CollapseDisposition(self.state).apply(
            collapse_ids, reasons=collapse_reasons, transition_id=event_id
        )

        # 2) Fission / successor cores for survivors that must split
        survivors = list(body.get("survivor_faction_ids") or [])
        if not survivors and winner:
            survivors = [winner]
        fission_results = []
        core_settlement_ids: list[str] = []
        legacy_settlement_ids: list[str] = []
        settlement_assignments: dict[str, str] = {}

        for parent in survivors:
            sites = [
                sid
                for sid, s in self.state.settlements.items()
                if s.get("faction_id") == parent
                and s.get("operational", True)
                and not s.get("ruin_only")
                and self._is_upgradeable_core_candidate(sid)
            ]
            all_sites = [
                sid
                for sid, s in self.state.settlements.items()
                if s.get("faction_id") == parent
                and s.get("operational", True)
                and not s.get("ruin_only")
            ]
            must_split = (
                parent in (self.state.clock.get("mandatory_split_ids") or [])
                or parent in sole_era_starter_ids(self.state)
            )
            # Sole remaining multi-site survivor from a multi-faction contest enters
            # alone unless mandatory fission is set — do not force-split here.
            if parent in sole_era_starter_ids(self.state) or parent in (
                self.state.clock.get("mandatory_split_ids") or []
            ):
                must_split = True
            elif len(survivors) > 1:
                must_split = False
            else:
                # Entered alone originally → mandatory fission at this transition.
                started = list(self.state.clock.get("started_faction_ids") or [])
                must_split = len(started) <= 1 or self.state.clock.get("sole_era_starter") is True

            if must_split and len(sites) >= 2:
                succ_a = self.state.ids.new("faction")
                succ_b = self.state.ids.new("faction")
                if len(sites) >= 4:
                    fplan = plan_fission(
                        self.state,
                        parent_faction_id=parent,
                        successor_faction_ids=[succ_a, succ_b],
                        split=True,
                    )
                else:
                    fplan = plan_undersized_mandatory_split(
                        self.state,
                        parent_faction_id=parent,
                        successor_faction_ids=[succ_a, succ_b],
                    )
                fission_results.append(FissionDisposition(self.state).apply(fplan, transition_id=event_id))
                settlement_assignments.update(fplan.get("settlement_assignments") or {})
                for pair in fplan.get("core_pairs") or []:
                    for csid in pair.get("core_settlement_ids") or []:
                        if self._is_upgradeable_core_candidate(csid):
                            core_settlement_ids.append(csid)
                for sid in all_sites:
                    if sid not in core_settlement_ids:
                        legacy_settlement_ids.append(sid)
            else:
                from sim.dmb.eras.planner import rank_theoretical_sites

                ranked_rows = [
                    row
                    for row in rank_theoretical_sites(self.state)
                    if row.get("settlement_id") in sites
                ]
                # Prefer player start node, then theoretical capacity ranking.
                player_node = str((self.state.player or {}).get("node_id") or "")
                preferred = [
                    sid
                    for sid in sites
                    if str((self.state.settlements.get(sid) or {}).get("node_id") or "") == player_node
                ]
                cores: list[str] = []
                for sid in preferred:
                    if sid not in cores:
                        cores.append(sid)
                for row in ranked_rows:
                    sid = str(row.get("settlement_id") or "")
                    if sid and sid not in cores:
                        cores.append(sid)
                for sid in sorted(sites):
                    if sid not in cores:
                        cores.append(sid)
                cores = cores[:2] if len(cores) >= 2 else cores[:1]
                core_settlement_ids.extend(cores)
                for sid in all_sites:
                    settlement_assignments[sid] = parent
                    if sid not in cores:
                        legacy_settlement_ids.append(sid)

        # Deduplicate while preserving order
        seen: set[str] = set()
        core_settlement_ids = [s for s in core_settlement_ids if not (s in seen or seen.add(s))]
        legacy_settlement_ids = [
            s for s in legacy_settlement_ids if s not in core_settlement_ids and not (s in seen or seen.add(s))
        ]
        # Any surviving settlement not a core becomes legacy.
        for sid, settlement in self.state.settlements.items():
            if settlement.get("ruin_only"):
                continue
            if not settlement.get("faction_id"):
                continue
            if sid not in core_settlement_ids and sid not in legacy_settlement_ids:
                legacy_settlement_ids.append(sid)

        # 3) Core upgrades + Historic industry
        upgrade_svc = CoreUpgradeService(self.state)
        upgrade_results = []
        industry_results = []
        for sid in core_settlement_ids:
            if sid not in self.state.settlements:
                continue
            upgrade_results.append(
                upgrade_svc.upgrade_core(sid, transition_id=event_id, next_era=next_era, grant_starter=True)
            )
            industry_results.append(_rebind_historic_industry(self.state, sid))

        # 4) Legacy mark
        legacy_marks = mark_legacy_sites(self.state, legacy_settlement_ids, source_era=str(body.get("source_era") or "prehistoric"))

        # 5) Continuity
        continuity = ContinuityService(self.state).adapt_for_transition(
            transition_id=event_id,
            settlement_assignments=settlement_assignments,
            collapsed_faction_ids=collapse_ids,
        )

        # 6) Hazards
        hazard = _hazard_rollover(self.state, next_era=next_era)

        # 7) Draft discard + fresh Historic roster
        draft = DraftService(self.state)
        draft.discard_for_era(reason="era_transition")
        active = [
            fid
            for fid, f in self.state.factions.items()
            if f.get("status") == "active" and f.get("operational", True) is not False
        ]
        if not active:
            active = sorted(
                {
                    s.get("faction_id")
                    for s in self.state.settlements.values()
                    if s.get("faction_id") and not s.get("ruin_only")
                }
            )
        if active:
            draft.deal(next_era, list(active))
        TurnScheduler(self.state.clock).reset_for_era(list(active))

        # 8) Era clocks
        self.state.clock["era"] = next_era
        self.state.clock["era_id"] = next_era
        self.state.board["era_id"] = next_era
        self.state.clock["started_faction_ids"] = list(active)
        self.state.clock["sole_era_starter"] = len(active) == 1
        if len(active) == 1:
            mark_mandatory_fission(self.state, active[0])
        else:
            self.state.clock["mandatory_split_ids"] = []
        self.state.clock.pop("pending_era_transition", None)
        self.state.board.pop("era_transition_pending", None)
        # Unfreeze presentation pause but keep receipt.
        tokens = dict(self.state.clock.get("pause_tokens") or {})
        tokens.pop("era_transition", None)
        self.state.clock["pause_tokens"] = tokens
        self.state.clock["era_transition_frozen"] = False
        self.state.clock["last_era_transition_id"] = event_id
        self.state.board["presentation_era_transition"] = {
            "transition_id": event_id,
            "committed": True,
            "next_era": next_era,
            "core_settlement_ids": core_settlement_ids,
            "legacy_settlement_ids": legacy_settlement_ids,
            "collapse_faction_ids": collapse_ids,
        }

        receipt = {
            "status": "committed",
            "transition_id": event_id,
            "plan_hash": body.get("plan_hash"),
            "source_era": body.get("source_era"),
            "next_era": next_era,
            "winner_faction_id": winner,
            "collapse": collapse_result,
            "fission": fission_results,
            "core_upgrades": upgrade_results,
            "historic_industry": industry_results,
            "legacy_sites": legacy_marks,
            "continuity": continuity,
            "hazard_rollover": hazard,
            "roster": list(active),
            "world_version": int(self.state.world_version),
            "core_settlement_ids": core_settlement_ids,
            "legacy_settlement_ids": legacy_settlement_ids,
        }
        receipts[event_id] = receipt
        from sim.dmb.history.chronicle import HistoryService

        HistoryService(self.state).record_transition_receipt(receipt)
        return {"idempotent": False, "receipt": receipt}

    def maybe_trigger_from_interrupt(self, *, event_id: str | None = None) -> dict[str, Any] | None:
        """If clock shows vp_threshold, request+commit once."""
        if self.state.clock.get("last_era_transition_id"):
            return None
        if str(self.state.clock.get("interrupt_reason") or "") != "vp_threshold":
            return None
        winners = list(self.state.clock.get("interrupt_factions") or ScoreService(self.state).check_threshold())
        if not winners:
            return None
        winner = winners[0]
        eid = event_id or f"era_transition:{self.state.world_id}:{self.state.world_version}:{winner}"
        plan = self.request_transition(winner, eid)
        return self.commit(plan)
