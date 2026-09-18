"""Terminal catastrophe transition (C08 / T070)."""

from __future__ import annotations

from typing import Any


class TerminalService:
    def __init__(self, world_state: Any):
        self.state = world_state

    def trigger(self, reason: str) -> dict[str, Any]:
        """Transition running→terminal once; further scheduling stops."""
        if self.state.clock.get("terminal"):
            return {
                "status": "already_terminal",
                "reason": self.state.clock.get("terminal_reason"),
                "emitted": False,
            }
        self.state.clock["terminal"] = True
        self.state.clock["terminal_reason"] = reason
        self.state.clock["force_terminal"] = True
        events = self.state.hazards.setdefault("terminal_events", [])
        event = {
            "id": self.state.ids.new("event"),
            "reason": reason,
            "turn": int(self.state.clock.get("turn", 0)),
            "game_ms": int(self.state.clock.get("game_ms", 0)),
        }
        events.append(event)
        return {"status": "terminal", "event": event, "emitted": True, "return_to_menu": True}
