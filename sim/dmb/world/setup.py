"""Apply SetupPlan into live WorldState (C04 / T036)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.construction.buildings import BuildingService
from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.logistics.carts import CartService
from sim.dmb.logistics.stock import StockLedger
from sim.dmb.world.board import HexBoard
from sim.dmb.world.generation import SetupPlan

STARTER_GOODS = {"timber": 2, "brick": 2, "wool": 1, "grain": 1}


@dataclass
class WorldSetupService:
    state: WorldState

    def apply(self, plan: SetupPlan, *, staging_nodes: list[str] | None = None) -> dict[str, Any]:
        """Commit centres/warehouses/primaries/factories/processor, starter goods, 2 carts, 1 road per core once."""
        receipts = self.state.command_receipts.setdefault("setup", {})
        setup_key = f"setup:{plan.seed}:{plan.faction_count}"
        if setup_key in receipts:
            return {"status": "already_applied", "receipt": receipts[setup_key]}

        board = plan.board
        self.state.board["topology"] = board.to_dict()
        self.state.board["hex_terrain"] = dict(plan.hex_terrain)
        self.state.board["hex_token"] = {k: int(v) for k, v in plan.hex_token.items()}
        self.state.board["hex_nodes"] = {hid: list(board.nodes_of_hex(hid)) for hid in board.hexes}
        self.state.board["node_hexes"] = {nid: list(board.touching_hexes(nid)) for nid in board.nodes}
        self.state.board["hazard_hexes"] = list(plan.hazard_hexes)
        self.state.board["hazard_cubes"] = {
            f"cube:{i}": {"hex_id": hid, "active": True} for i, hid in enumerate(plan.hazard_hexes)
        }

        buildings = BuildingService(self.state)
        ledger = StockLedger(self.state)
        carts = CartService(self.state, ledger=ledger)
        created: dict[str, Any] = {"settlements": [], "carts": [], "roads": [], "staging": []}

        for core in plan.cores:
            settlement_id = self.state.ids.new("settlement")
            centre = buildings.create(
                "building.centre",
                node_id=core.node_id,
                faction_id=core.faction_id,
                settlement_id=settlement_id,
            )
            wh = buildings.create(
                "building.warehouse",
                node_id=core.node_id,
                faction_id=core.faction_id,
                settlement_id=settlement_id,
            )
            for i in range(3):
                buildings.create(
                    "building.primary",
                    node_id=core.node_id,
                    faction_id=core.faction_id,
                    slot_index=i,
                    settlement_id=settlement_id,
                )
            buildings.create(
                "building.processor",
                node_id=core.node_id,
                faction_id=core.faction_id,
                settlement_id=settlement_id,
            )
            for i in range(3):
                buildings.create(
                    "building.factory",
                    node_id=core.node_id,
                    faction_id=core.faction_id,
                    slot_index=i,
                    settlement_id=settlement_id,
                )
            self.state.settlements[settlement_id] = {
                "id": settlement_id,
                "node_id": core.node_id,
                "faction_id": core.faction_id,
                "tier": "settlement",
                "operational": True,
                "warehouse_id": wh["id"],
                "centre_id": centre["id"],
                "core_index": core.index,
            }
            self.state.factions.setdefault(
                core.faction_id, {"id": core.faction_id, "settlement_ids": []}
            )["settlement_ids"].append(settlement_id)

            store_id = f"store:{wh['id']}"
            for good, qty in STARTER_GOODS.items():
                ledger.credit(store_id, good, qty)

            for _ in range(2):
                cart = carts.create(
                    owner_faction=core.faction_id,
                    home_store=store_id,
                    current_node=core.node_id,
                )
                created["carts"].append(cart["id"])

            # One legal road from core once
            neighbours = board.adjacent_nodes(core.node_id)
            if neighbours:
                road_id = self.state.ids.new("command")
                self.state.roads[road_id] = {
                    "id": road_id,
                    "a": core.node_id,
                    "b": neighbours[0],
                    "faction_id": core.faction_id,
                    "status": "built",
                    "setup": True,
                }
                created["roads"].append(road_id)
            created["settlements"].append(settlement_id)

        for node_id in staging_nodes or []:
            sid = self.state.ids.new("settlement")
            self.state.settlements[sid] = {
                "id": sid,
                "node_id": node_id,
                "faction_id": None,
                "tier": "staging",
                "staging": True,
                "operational": True,
                "ruin_only": False,
            }
            created["staging"].append(sid)

        receipt = {
            "id": setup_key,
            "seed": plan.seed,
            "faction_count": plan.faction_count,
            "created": created,
            "used_fallback": plan.used_fallback,
        }
        receipts[setup_key] = receipt
        return {"status": "applied", "receipt": receipt}

    def replace_cart(
        self,
        *,
        faction_id: str,
        home_store: str,
        current_node: str,
        pay: bool = True,
    ) -> dict[str, Any]:
        """Replacement cart after 1 timber/1 brick/1 ore at home warehouse; new ID."""
        ledger = StockLedger(self.state)
        carts = CartService(self.state, ledger=ledger)
        if pay:
            cost = {"timber": 1, "brick": 1, "ore": 1}
            for good, qty in cost.items():
                if ledger.available(home_store, good) < qty:
                    raise TypeValidationError("insufficient goods for replacement cart")
            ledger.consume(home_store, cost, cause_id="replacement_cart")
        cart = carts.create(
            owner_faction=faction_id,
            home_store=home_store,
            current_node=current_node,
        )
        return cart
