"""Strategic Travel/Wait runner for the G01 slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.time.turns import TurnScheduler

STAGES = ("0_boundary", "1_arrival", "2_score", "3_follow_on", "9_seat_end")


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
        for stage in STAGES:
            self.stage_id = stage
            if stage == "1_arrival":
                # Commit node, area, position and facing together.
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
