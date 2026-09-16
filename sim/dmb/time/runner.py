"""Strategic Travel/Wait runner for the G01 slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.time.turns import TurnScheduler

STAGES = ("0_boundary", "1_arrival", "2_score", "3_follow_on", "9_seat_end")


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

    def execute_travel(self, from_node: str, to_node: str) -> dict[str, Any]:
        self.interrupted = False
        self.stages_executed = []
        nodes = self.state.board.get("nodes", {})
        if from_node != self.state.player.get("node_id"):
            raise TypeValidationError("travel from_node mismatch")
        if to_node not in nodes:
            raise TypeValidationError("unknown destination")
        exits = list(nodes[from_node].get("exits", []))
        if to_node not in exits:
            raise TypeValidationError("nonadjacent travel")
        self.scheduler.begin_turn("Travel")
        for stage in STAGES:
            self.stage_id = stage
            if stage == "1_arrival":
                self.state.player["node_id"] = to_node
            if stage == "2_score":
                self.state.clock["last_score"] = {"node_id": to_node, "turn": self.state.clock["turn"]}
            self.stages_executed.append(stage)
            if stage == "2_score" and self.state.clock.pop("interrupt_after_score", False):
                self.interrupt("after_score")
            if self.interrupted:
                break
        if self.interrupted:
            seat = {"round_complete": False, "interrupted": True, "draft": None}
            self.state.clock["draft"] = None
        else:
            seat = self.scheduler.finish_seat()
        return {
            "turn": int(self.state.clock["turn"]),
            "node_id": self.state.player["node_id"],
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
        self.scheduler.begin_turn("Wait")
        seat = self.scheduler.finish_seat()
        return {
            "turn": int(self.state.clock["turn"]),
            "node_id": current_node,
            "press_id": press_id,
            "seat": seat,
        }

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
