"""Versioned faction observations with knowledge filtering (C12 / T042)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.state import WorldState
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.technology.research import TechnologyService

OBSERVATION_SCHEMA = "ObservationV1"


@dataclass
class ObservationBuilder:
    state: WorldState

    def build(self, faction_id: str, decision_kind: str) -> dict[str, Any]:
        clock = self.state.clock
        scores = ScoreService(self.state)
        ledger = StockLedger(self.state)
        research = TechnologyService(self.state)

        own_stocks: dict[str, Any] = {}
        for store_id, store in self.state.stocks.items():
            if str(store_id).startswith("_"):
                continue
            # Own warehouses / settlement stores tagged with faction or belonging via settlements.
            owner = None
            for settlement in self.state.settlements.values():
                if settlement.get("store_id") == store_id or settlement.get("id") == store_id:
                    owner = settlement.get("faction_id")
                    break
            for building in self.state.buildings.values():
                if building.get("id") == store_id or building.get("store_id") == store_id:
                    owner = building.get("faction_id")
            if owner is not None and owner != faction_id:
                continue
            if owner is None and store_id not in {
                s.get("store_id") for s in self.state.settlements.values() if s.get("faction_id") == faction_id
            }:
                # Include unowned only when explicitly faction-keyed.
                if not str(store_id).startswith(str(faction_id)):
                    continue
            own_stocks[store_id] = deepcopy(store)

        own_carts = {
            cid: {
                "id": cid,
                "node_id": c.get("node_id"),
                "cargo": deepcopy(c.get("cargo") or {}),
                "capacity": c.get("capacity"),
                "mission": c.get("mission"),
            }
            for cid, c in self.state.carts.items()
            if c.get("owner_faction") == faction_id
        }

        own_centres = []
        for sid, settlement in self.state.settlements.items():
            if settlement.get("faction_id") != faction_id:
                continue
            own_centres.append(
                {
                    "id": sid,
                    "node_id": settlement.get("node_id"),
                    "tier": settlement.get("tier", "settlement"),
                    "vp": scores.settlement_vp(settlement),
                }
            )

        own_roads = [
            {"id": rid, "a": r.get("a"), "b": r.get("b")}
            for rid, r in self.state.roads.items()
            if r.get("faction_id") == faction_id
        ]

        own_units = [
            {
                "id": uid,
                "node_id": u.get("node_id"),
                "definition_id": u.get("definition_id"),
                "health": u.get("health"),
            }
            for uid, u in self.state.units.items()
            if u.get("faction_id") == faction_id
        ]

        # Observed enemies: public ownership only; no private tactical secrets.
        observed_enemies = []
        for uid, u in self.state.units.items():
            if u.get("faction_id") == faction_id:
                continue
            if not u.get("publicly_observed", True):
                continue
            observed_enemies.append(
                {
                    "id": uid,
                    "faction_id": u.get("faction_id"),
                    "node_id": u.get("node_id"),
                    "observed_strength": u.get("public_strength"),
                }
            )

        public_ownership = {
            sid: {"faction_id": s.get("faction_id"), "node_id": s.get("node_id")}
            for sid, s in self.state.settlements.items()
        }

        relations = deepcopy(self.state.factions.get(faction_id, {}).get("relations", {}))

        hand = []
        draft = getattr(self.state, "tech_draft", {}) or {}
        if draft.get("active"):
            hand = [
                {"id": c["id"], "definition_id": c["definition_id"]}
                for c in (draft.get("hands") or {}).get(faction_id, [])
            ]

        research_view = {
            "activated": list(research.research_of(faction_id).get("activated_definition_ids", [])),
            "modifiers": research.effective_modifiers(faction_id),
            "owned_count": len(research.research_of(faction_id).get("owned", {})),
        }

        # Explicitly exclude wizard private knowledge / conversations.
        wizard_secrets_excluded = True
        player = self.state.player
        public_player = {
            "node_id": player.get("node_id"),
            # pose/conversation/inventory secrets omitted
        }

        obs = {
            "schema": OBSERVATION_SCHEMA,
            "schema_version": 1,
            "faction_id": faction_id,
            "decision_kind": decision_kind,
            "time": {
                "game_ms": clock.get("game_ms"),
                "turn": clock.get("turn"),
                "round": clock.get("round"),
                "era": clock.get("era_id") or clock.get("era") or "prehistoric",
                "active_faction_id": clock.get("active_faction_id"),
                "seat_is_active": clock.get("active_faction_id") == faction_id,
            },
            "own": {
                "stocks": own_stocks,
                "carts": own_carts,
                "centres": own_centres,
                "roads": own_roads,
                "units": own_units,
                "vp": scores.score(faction_id),
                "hand": hand,
                "research": research_view,
            },
            "public": {
                "ownership": public_ownership,
                "relations": relations,
                "catastrophe": deepcopy(self.state.clock.get("catastrophe_public") or {}),
                "player_node": public_player,
            },
            "observed": {
                "enemies": observed_enemies,
            },
            "masks": {
                "wizard_private_excluded": wizard_secrets_excluded,
                "enemy_private_excluded": True,
            },
            "legal_version": int(self.state.world_version),
            "commitments": deepcopy(self.state.factions.get(faction_id, {}).get("commitments", [])),
        }
        return obs
