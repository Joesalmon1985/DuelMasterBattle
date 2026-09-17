"""Strategic Travel/Wait runner for the G01 slice + construction/cargo stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.time.turns import TurnScheduler

# Preserve G01 stage ids (2_score, 3_follow_on) and insert C03 cargo stages.
STAGES = (
    "0_boundary",
    "1_arrival",
    "2_score",
    "2_production",
    "3_logistics",
    "4_completions",
    "3_follow_on",
    "9_seat_end",
)


def _exit_destinations(node: dict[str, Any]) -> list[str]:
    exits = node.get("exits", [])
    if isinstance(exits, dict):
        return [str(key) for key in exits.keys()]
    return [str(item) for item in exits]


def _exit_link(node: dict[str, Any], to_node: str) -> dict[str, Any] | None:
    exits = node.get("exits", {})
    if isinstance(exits, dict) and to_node in exits:
        link = dict(exits[to_node])
        link.setdefault("to_node", to_node)
        return link
    links = node.get("exit_links", {})
    if isinstance(links, dict) and to_node in links:
        link = dict(links[to_node])
        link.setdefault("to_node", to_node)
        return link
    return None


@dataclass
class TurnRunner:
    state: WorldState
    scheduler: TurnScheduler
    interrupted: bool = False
    stage_id: str | None = None
    stages_executed: list[str] | None = None

    def interrupt(self, reason: str) -> None:
        self.interrupted = True
        self.state.clock["interrupt_reason"] = reason

    def run_stage(self, stage: str) -> dict[str, Any]:
        """Execute one named stage; used by Travel/Wait and tests."""
        self.stage_id = stage
        payload: dict[str, Any] = {"stage": stage}
        if stage == "2_production":
            payload.update(self._stage_production())
        elif stage == "3_logistics":
            payload.update(self._stage_logistics())
        elif stage == "4_completions":
            payload.update(self._stage_completions())
        return payload

    def _stage_production(self) -> dict[str, Any]:
        if not self.state.settlements:
            return {"grants": []}
        from sim.dmb.construction.production import CatanProductionService
        from sim.dmb.core.rng import RngBank

        rng = RngBank.from_dict(self.state.rng) if self.state.rng else RngBank()
        prod = CatanProductionService(self.state, rng=rng)
        outcome = prod.draw_and_grant()
        return outcome

    def _stage_logistics(self) -> dict[str, Any]:
        if not self.state.carts:
            return {"moved": []}
        from sim.dmb.logistics.carts import CartService
        from sim.dmb.logistics.routes import RoutePlanner
        from sim.dmb.logistics.stock import StockLedger

        ledger = StockLedger(self.state)
        carts = CartService(self.state, ledger=ledger)
        # Carts assigned during this turn's decisions must not move retroactively.
        # begin_turn clears assigned_this_turn — only clear moved markers here if new turn.
        if self.state.clock.get("_logistics_turn") != self.state.clock.get("turn"):
            carts.begin_turn()
            # Re-mark carts assigned on this turn (assigned_turn == current)
            turn = int(self.state.clock.get("turn", 0))
            for cid, cart in self.state.carts.items():
                if cart.get("assigned_turn") == turn:
                    carts.assigned_this_turn.add(cid)
            self.state.clock["_logistics_turn"] = turn
        routes = RoutePlanner(self.state)

        def validate_edge(a: str, b: str, cart: dict[str, Any]):
            return routes.validate_next_edge(str(cart.get("owner_faction")), a, b)

        moved = carts.advance_all(validate_edge=validate_edge)
        return {"moved": [m.get("id") for m in moved], "carts": moved}

    def _stage_completions(self) -> dict[str, Any]:
        from sim.dmb.construction.orders import ConstructionService
        from sim.dmb.construction.scoring import ScoreService, VP_THRESHOLD

        svc = ConstructionService(self.state)
        committed = []
        # Cyclic seat order from active seat, then stable order IDs
        active = self.scheduler.active_seat()
        orders = sorted(
            self.state.orders.values(),
            key=lambda o: (
                0 if o.get("faction_id") == active else 1,
                str(o.get("faction_id") or ""),
                str(o.get("id") or ""),
            ),
        )
        for order in orders:
            if order.get("status") != "ready":
                continue
            result = svc.commit_delivered(str(order["id"]))
            committed.append(result)
            if result.get("interrupt"):
                self.interrupt(str(result["interrupt"].get("kind") or "vp_threshold"))
                break
            winners = ScoreService(self.state).check_threshold(VP_THRESHOLD)
            if winners:
                self.interrupt("vp_threshold")
                break
        return {"committed": committed}

    def _run_stages(self, *, arrival_handler=None) -> None:
        self.stages_executed = []
        for stage in STAGES:
            self.stage_id = stage
            if stage == "1_arrival" and arrival_handler is not None:
                arrival_handler()
            if stage == "2_score":
                self.state.clock["last_score"] = {
                    "node_id": self.state.player.get("node_id"),
                    "turn": self.state.clock["turn"],
                }
            if stage in {"2_production", "3_logistics", "4_completions"}:
                self.run_stage(stage)
            self.stages_executed.append(stage)
            if stage == "2_score" and self.state.clock.pop("interrupt_after_score", False):
                self.interrupt("after_score")
            if self.interrupted:
                break

    def execute_travel(self, from_node: str, to_node: str) -> dict[str, Any]:
        self.interrupted = False
        self.stages_executed = []
        nodes = self.state.board.get("nodes", {})
        if from_node != self.state.player.get("node_id"):
            raise TypeValidationError("travel from_node mismatch")
        if to_node not in nodes:
            raise TypeValidationError("unknown destination")
        source = nodes[from_node]
        if to_node not in _exit_destinations(source):
            raise TypeValidationError("nonadjacent travel")
        link = _exit_link(source, to_node)
        if link is None:
            raise TypeValidationError("missing exit link")
        arrival = dict(link.get("arrival") or {})
        if str(arrival.get("node_id", to_node)) != to_node:
            raise TypeValidationError("arrival node mismatch")
        pos = arrival.get("position")
        if not isinstance(pos, (list, tuple)) or len(pos) < 2:
            raise TypeValidationError("arrival position required")
        facing = str(arrival.get("facing") or "down")
        area_id = str(arrival.get("area_id") or nodes[to_node].get("area_id") or "")

        self.scheduler.begin_turn("Travel")

        def on_arrival() -> None:
            self.state.player["node_id"] = to_node
            if area_id:
                self.state.player["area_id"] = area_id
            self.state.player["position"] = [float(pos[0]), float(pos[1])]
            self.state.player["facing"] = facing
            self.state.player["pose_generation"] = int(self.state.player.get("pose_generation", 0)) + 1
            self.state.clock["last_travel"] = {
                "from_node": from_node,
                "to_node": to_node,
                "exit_id": link.get("exit_id"),
                "arrival": {
                    "node_id": to_node,
                    "area_id": self.state.player.get("area_id"),
                    "position": list(self.state.player["position"]),
                    "facing": facing,
                },
            }

        self._run_stages(arrival_handler=on_arrival)
        if self.interrupted:
            seat = {"round_complete": False, "interrupted": True, "draft": None}
            self.state.clock["draft"] = None
            self._discard_tech_draft_on_interrupt()
        else:
            seat = self.scheduler.finish_seat()
            seat = self._maybe_resolve_tech_draft(seat)
        return {
            "turn": int(self.state.clock["turn"]),
            "node_id": self.state.player["node_id"],
            "area_id": self.state.player.get("area_id"),
            "position": list(self.state.player.get("position", [])),
            "facing": self.state.player.get("facing"),
            "pose_generation": int(self.state.player.get("pose_generation", 0)),
            "seat": seat,
            "interrupted": self.interrupted,
            "stages": list(self.stages_executed or []),
        }

    def execute_wait(self, current_node: str, press_id: str) -> dict[str, Any]:
        seen = set(self.state.clock.setdefault("wait_press_ids", []))
        if press_id in seen:
            raise TypeValidationError("duplicate wait press")
        if current_node != self.state.player.get("node_id"):
            raise TypeValidationError("wait node mismatch")
        seen.add(press_id)
        self.state.clock["wait_press_ids"] = sorted(seen)
        self.interrupted = False
        self.scheduler.begin_turn("Wait")
        self._run_stages(arrival_handler=None)
        if self.interrupted:
            seat = {"round_complete": False, "interrupted": True, "draft": None}
            self.state.clock["draft"] = None
            self._discard_tech_draft_on_interrupt()
        else:
            seat = self.scheduler.finish_seat()
            seat = self._maybe_resolve_tech_draft(seat)
        return {
            "turn": int(self.state.clock["turn"]),
            "node_id": current_node,
            "press_id": press_id,
            "seat": seat,
            "interrupted": self.interrupted,
            "stages": list(self.stages_executed or []),
        }

    def _discard_tech_draft_on_interrupt(self) -> None:
        draft = getattr(self.state, "tech_draft", None)
        if isinstance(draft, dict) and draft.get("active"):
            from sim.dmb.technology.draft import DraftService

            DraftService(self.state).discard_for_era(reason=str(self.state.clock.get("interrupt_reason") or "interrupt"))

    def _maybe_resolve_tech_draft(self, seat: dict[str, Any]) -> dict[str, Any]:
        """On completed World Round, resolve one simultaneous tech pick when a draft is active."""
        if not seat.get("round_complete"):
            return seat
        draft = getattr(self.state, "tech_draft", None)
        if not isinstance(draft, dict) or not draft.get("active"):
            return seat
        from sim.dmb.technology.draft import DraftService

        svc = DraftService(self.state)
        snap = svc.collect_choices({"turn": int(self.state.clock.get("turn", 0)), "round": int(self.state.clock.get("round", 0))})
        # Seat-end default: deterministic first-card pick (heuristics override later in T043/T046).
        choices = svc.auto_pick_first()
        outcome = svc.resolve_round(choices)
        seat = dict(seat)
        seat["tech_draft"] = outcome
        seat["tech_snapshot_pick_index"] = snap.get("pick_index")
        return seat


    def run_seats_round(self) -> dict[str, Any]:
        """Advance through every scheduled seat once; unfinished rounds yield no draft."""
        results = []
        while self.scheduler.active_seat() is not None:
            faction = self.scheduler.active_seat()
            results.append({"faction_id": faction})
            seat = self.scheduler.finish_seat()
            results[-1]["seat"] = seat
            if seat.get("round_complete"):
                break
        return {
            "results": results,
            "draft": self.state.clock.get("draft"),
            "round_complete": bool(self.state.clock.get("round_complete")),
        }
