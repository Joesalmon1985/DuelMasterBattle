"""Catan dice grants (C04 / T029)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.rng import RngBank
from sim.dmb.core.state import WorldState
from sim.dmb.hazards.queries import catan_grant_suppressed
from sim.dmb.world.generation import TERRAIN_TO_GOOD


def terrain_good(terrain: str) -> str | None:
    return TERRAIN_TO_GOOD.get(terrain)


@dataclass
class CatanProductionService:
    state: WorldState
    rng: RngBank | None = None

    def __post_init__(self) -> None:
        if self.rng is None:
            self.rng = RngBank.from_dict(self.state.rng) if self.state.rng else RngBank()
            seed = 0
            if isinstance(self.state.rng, dict):
                seed = self.state.rng.get("streams", {}).get("gameplay", {}).get("seed", 0)
            self.rng.ensure("catan", seed=seed)

    def warehouse_for_settlement(self, settlement_id: str) -> str | None:
        settlement = self.state.settlements.get(settlement_id) or {}
        wh = settlement.get("warehouse_id")
        if wh and wh in self.state.buildings:
            b = self.state.buildings[wh]
            if b.get("status") != "destroyed" and b.get("slot_kind") == "warehouse":
                return str(wh)
        node_id = settlement.get("node_id")
        for bid, b in self.state.buildings.items():
            if (
                b.get("node_id") == node_id
                and b.get("slot_kind") == "warehouse"
                and b.get("status") != "destroyed"
                and (b.get("settlement_id") == settlement_id or settlement.get("warehouse_id") is None)
            ):
                return str(bid)
        return None

    def store_key(self, warehouse_building_id: str) -> str:
        return f"store:{warehouse_building_id}"

    def credit_good(self, store_id: str, good: str, qty: int) -> None:
        bucket = self.state.stocks.setdefault(store_id, {})
        cat = bucket.setdefault("catan", {})
        entry = cat.setdefault(good, {"available": 0, "reserved": 0, "escrow": 0})
        entry["available"] = int(entry.get("available", 0)) + int(qty)

    def available(self, store_id: str, good: str) -> int:
        return int(
            self.state.stocks.get(store_id, {})
            .get("catan", {})
            .get(good, {})
            .get("available", 0)
        )

    def settlements_touching(self, hex_id: str) -> list[str]:
        board = self.state.board
        hex_nodes = set(board.get("hex_nodes", {}).get(hex_id) or [])
        out: list[str] = []
        for sid, settlement in self.state.settlements.items():
            if settlement.get("status") in {"ruined", "destroyed", "inert"}:
                continue
            if not settlement.get("operational", True):
                continue
            node_id = settlement.get("node_id")
            node_hexes = set(
                board.get("node_hexes", {}).get(node_id)
                or settlement.get("touching_hexes")
                or []
            )
            if hex_id in node_hexes or node_id in hex_nodes:
                out.append(sid)
        return out

    def grant_for_roll(self, roll: int) -> dict[str, Any]:
        """Apply Catan grants for a dice total. Roll 7 grants nothing."""
        results: list[dict[str, Any]] = []
        suppressed: list[dict[str, Any]] = []
        if int(roll) == 7:
            return {"roll": roll, "grants": results, "suppressed": suppressed}
        board = self.state.board
        hex_terrain = board.get("hex_terrain") or {}
        hex_token = board.get("hex_token") or {}
        # Industrial depletion lives under board.industrial_balance and must NOT block Catan.
        for hex_id, token in hex_token.items():
            if int(token) != int(roll):
                continue
            terrain = str(hex_terrain.get(hex_id, ""))
            good = terrain_good(terrain)
            if good is None:
                suppressed.append({"hex_id": hex_id, "reason": "desert_or_no_catan_good"})
                continue
            if catan_grant_suppressed(board, hex_id):
                suppressed.append({"hex_id": hex_id, "reason": "catastrophe_cube", "good": good})
                continue
            for sid in self.settlements_touching(hex_id):
                settlement = self.state.settlements[sid]
                tier = settlement.get("tier", "settlement")
                amount = 2 if tier == "city" else 1
                warehouse_id = self.warehouse_for_settlement(sid)
                if warehouse_id is None:
                    suppressed.append(
                        {
                            "hex_id": hex_id,
                            "settlement_id": sid,
                            "reason": "missing_warehouse",
                            "good": good,
                            "amount": amount,
                        }
                    )
                    continue
                store_id = self.store_key(warehouse_id)
                self.credit_good(store_id, good, amount)
                results.append(
                    {
                        "hex_id": hex_id,
                        "settlement_id": sid,
                        "warehouse_id": warehouse_id,
                        "store_id": store_id,
                        "good": good,
                        "amount": amount,
                    }
                )
        return {"roll": roll, "grants": results, "suppressed": suppressed}

    def draw_and_grant(self) -> dict[str, Any]:
        assert self.rng is not None
        d1 = self.rng.draw_int("catan", 1, 6)
        d2 = self.rng.draw_int("catan", 1, 6)
        outcome = self.grant_for_roll(d1 + d2)
        outcome["dice"] = [d1, d2]
        self.state.rng = self.rng.to_dict()
        return outcome
