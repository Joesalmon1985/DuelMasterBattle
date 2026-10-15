"""Human-versus-human Ward duels, owned by the host.

Rules are the existing Ward/Weave rules in `wizard_rts/duel/ward.py` (fracture/echo/fade scoring, `compute_result`), the same
code the hazard duel and the headless duel environment use. Nothing here is a simplified minigame:

- Both players hide a ward of `slots` spells from a pool of `colours` (repeats allowed by default, as in the retained board).
- A round is one cast by each player; casts are accepted in either order. A cast is scored against the rival's hidden ward
  the moment it arrives (the caster learns fracture/echo/fade); the round closes when both have cast.
- The duel ends when, at the close of a round, a ward is broken or the casts are exhausted; `compute_result` (ported from
  `game_logic.gd`) decides victory, defeat, clash (both broke in the same round) or stalemate, exactly as the board does
  for human versus bot (fewer casts wins when both solve; best progress breaks a stalemate only at exhaustion).
- The rival's ward is never in a player's view until `done`.
- A player who does not cast within `cast_timeout_s` has a random legal weave cast for him (the board's auto-cast rule);
  a player gone for longer than the reconnect grace forfeits. The timeouts are wall-clock admission rules applied by the
  host loop (`tick(now)`), not simulation decisions; the duel itself is a pure function of the submitted casts.
"""

from __future__ import annotations

import zlib
from typing import Any

from wizard_rts.duel.ward import compute_result, random_pattern, score_attack
from wizard_rts.puzzle.rng import GodotRng

DEFAULT_POOL = [0, 1, 3, 4, 6, 9]  # sim/dmb/adventure/duels.py _DEFAULT_POOL (the G04 ward encounter spells)
EXTENDED_POOL = [0, 1, 3, 4, 6, 9, 2, 5]
FORMATS = {  # name -> slots, colours; the first PvP format is the accessible three-by-three one
    "three": {"slots": 3, "colours": 3, "max_casts": 10, "allow_repeats": True},
    "classic": {"slots": 4, "colours": 6, "max_casts": 10, "allow_repeats": True},
}
CAST_TIMEOUT_S = 60.0
INVITE_TIMEOUT_S = 30.0
CHALLENGE_RANGE = 2  # tiles (Manhattan): stand next to the other wizard


def make_format(spec: dict[str, Any] | str | None) -> dict[str, Any]:
    base = dict(FORMATS["three"])
    if isinstance(spec, str):
        base = dict(FORMATS.get(spec, FORMATS["three"]))
    elif isinstance(spec, dict):
        for k in ("slots", "colours", "max_casts"):
            if k in spec:
                base[k] = int(spec[k])
        if "allow_repeats" in spec:
            base["allow_repeats"] = bool(spec["allow_repeats"])
    base["slots"] = max(1, min(8, base["slots"]))
    base["colours"] = max(1, min(8, base["colours"]))
    base["max_casts"] = max(1, min(30, base["max_casts"]))
    if not base["allow_repeats"] and base["colours"] < base["slots"]:
        base["allow_repeats"] = True
    pool = list(EXTENDED_POOL[: base["colours"]]) if base["colours"] > len(DEFAULT_POOL) else list(DEFAULT_POOL[: base["colours"]])
    base["pool"] = pool
    return base


class PvpDuel:
    def __init__(self, duel_id: str, a: str, b: str, names: dict[str, str], fmt: dict[str, Any], seed: int, now: float) -> None:
        self.id = duel_id
        self.players = [a, b]
        self.names = dict(names)
        self.fmt = fmt
        self.state = "setup"  # setup -> active -> finished
        self.wards: dict[str, list[int] | None] = {a: None, b: None}
        self.history: dict[str, list[dict[str, Any]]] = {a: [], b: []}
        self.broke: dict[str, bool] = {a: False, b: False}
        self.round = 1
        self.cast_in_round: dict[str, bool] = {a: False, b: False}
        self.cast_seq: dict[str, int] = {a: 0, b: 0}
        self.result: dict[str, Any] | None = None
        self.reason = ""
        self.token = ""  # the pause token the session acquired
        self.rng = GodotRng(int(seed) & 0x7FFFFFFF)
        self.started_at = now
        self.round_opened_at = now  # for the cast timeout: measured from the first cast of the round
        self.first_cast_at: float | None = None
        self.left: dict[str, bool] = {a: False, b: False}
        self.finished_at: float | None = None

    # ---------------------------------------------------------------- helpers
    def rival(self, pid: str) -> str:
        return self.players[1] if pid == self.players[0] else self.players[0]

    def has(self, pid: str) -> bool:
        return pid in self.players

    def _legal(self, pattern: list[Any]) -> bool:
        try:
            vals = [int(v) for v in pattern]
        except (TypeError, ValueError):
            return False
        if len(vals) != self.fmt["slots"] or any(v not in self.fmt["pool"] for v in vals):
            return False
        if not self.fmt["allow_repeats"] and len(set(vals)) != len(vals):
            return False
        return True

    # ---------------------------------------------------------------- setup
    def submit_ward(self, pid: str, ward: list[Any]) -> dict[str, Any]:
        if self.state != "setup":
            return {"status": "rejected", "reason": "not_in_setup", "state": self.state}
        if self.wards[pid] is not None:
            return {"status": "ok", "idempotent": True, "state": self.state}
        if not self._legal(ward):
            return {"status": "rejected", "reason": "illegal_ward", "slots": self.fmt["slots"], "pool": list(self.fmt["pool"])}
        self.wards[pid] = [int(v) for v in ward]
        if all(w is not None for w in self.wards.values()):
            self.state = "active"
        return {"status": "ok", "state": self.state}

    # ---------------------------------------------------------------- casts
    def cast(self, pid: str, attack: list[Any], cast_seq: int, now: float) -> dict[str, Any]:
        if self.state == "finished":
            return {"status": "rejected", "reason": "finished", "state": self.state}
        if self.state != "active":
            return {"status": "rejected", "reason": "not_active", "state": self.state}
        expected = self.cast_seq[pid] + 1
        if int(cast_seq) == self.cast_seq[pid] and self.history[pid]:  # a replayed submission: the same feedback, no second cast
            last = self.history[pid][-1]
            return {"status": "ok", "idempotent": True, **{k: last[k] for k in ("fracture", "echo", "fade", "broken")}, "round": last["round"]}
        if int(cast_seq) != expected:
            return {"status": "rejected", "reason": "bad_cast_seq", "expected": expected}
        if self.cast_in_round[pid]:
            return {"status": "rejected", "reason": "already_cast_this_round", "round": self.round}
        if not self._legal(attack):
            return {"status": "rejected", "reason": "illegal_attack", "slots": self.fmt["slots"], "pool": list(self.fmt["pool"])}
        return self._apply_cast(pid, [int(v) for v in attack], auto=False, now=now)

    def _apply_cast(self, pid: str, attack: list[int], auto: bool, now: float) -> dict[str, Any]:
        rival = self.rival(pid)
        r = score_attack(self.wards[rival] or [], attack)
        self.cast_seq[pid] += 1
        rec = {"n": len(self.history[pid]) + 1, "round": self.round, "attack": list(attack), "fracture": r["fracture"], "echo": r["echo"],
               "fade": r["fade"], "broken": bool(r["broken"]), "auto": auto}
        self.history[pid].append(rec)
        self.broke[pid] = self.broke[pid] or bool(r["broken"])
        self.cast_in_round[pid] = True
        if self.first_cast_at is None:
            self.first_cast_at = now
        if all(self.cast_in_round.values()):
            self._close_round(now)
        return {"status": "ok", "fracture": r["fracture"], "echo": r["echo"], "fade": r["fade"], "broken": bool(r["broken"]), "round": rec["round"],
                "done": self.state == "finished"}

    def _close_round(self, now: float) -> None:
        a, b = self.players
        out_of_casts = len(self.history[a]) >= self.fmt["max_casts"] and len(self.history[b]) >= self.fmt["max_casts"]
        if self.broke[a] or self.broke[b] or out_of_casts:
            self._finish("solved" if (self.broke[a] or self.broke[b]) else "both_exhausted", now)
            return
        self.round += 1
        self.cast_in_round = {a: False, b: False}
        self.first_cast_at = None
        self.round_opened_at = now

    def _finish(self, reason: str, now: float) -> None:
        a, b = self.players
        ah = [(h["fracture"], h["echo"]) for h in self.history[a]]
        bh = [(h["fracture"], h["echo"]) for h in self.history[b]]
        res = compute_result(self.broke[a], self.broke[b], len(ah), len(bh), ah, bh, self.fmt["max_casts"])
        self.result = {"winner": a if res["outcome"] == "human_win" else (b if res["outcome"] == "bot_win" else ""), "reason": reason,
                       "both_solved": bool(self.broke[a] and self.broke[b]), "casts": {a: len(ah), b: len(bh)}, "ported": res["outcome"]}
        self.reason = reason
        self.state = "finished"
        self.finished_at = now

    def forfeit(self, pid: str, reason: str, now: float) -> dict[str, Any]:
        if self.state == "finished":
            return {"status": "ok", "idempotent": True}
        rival = self.rival(pid)
        self.result = {"winner": rival, "reason": reason, "both_solved": False, "casts": {p: len(self.history[p]) for p in self.players}, "ported": ""}
        self.reason = reason
        self.state = "finished"
        self.finished_at = now
        return {"status": "ok", "state": self.state}

    def auto_cast_overdue(self, now: float, timeout_s: float) -> list[str]:
        """Players whose cast is overdue (the rival cast `timeout_s` ago): the host casts a random legal weave for them."""
        if self.state != "active" or self.first_cast_at is None or now - self.first_cast_at < timeout_s:
            return []
        return [p for p in self.players if not self.cast_in_round[p]]

    def auto_cast(self, pid: str, now: float) -> dict[str, Any]:
        pattern = random_pattern(self.fmt["slots"], self.fmt["pool"], self.fmt["allow_repeats"], self.rng)
        if not self.fmt["allow_repeats"]:
            pattern = random_pattern(self.fmt["slots"], self.fmt["pool"], False, self.rng)
        return self._apply_cast(pid, pattern, auto=True, now=now)

    # ---------------------------------------------------------------- views
    def outcome_for(self, pid: str) -> str:
        if self.result is None:
            return ""
        if self.result["both_solved"] and not self.result["winner"]:
            return "clash"
        if self.result["winner"] == pid:
            return "victory"
        if self.result["winner"]:
            return "defeat"
        return "stalemate"

    def encounter(self, pid: str) -> dict[str, Any]:
        """The board's combatant records (the shape `game_board.gd` reads from a lease)."""
        rival = self.rival(pid)
        f = self.fmt

        def combatant(cid: str, name: str, archetype: str) -> dict[str, Any]:
            return {"id": cid, "display_name": name, "archetype": archetype, "kind": "player", "weave_size": f["slots"], "ward_size": f["slots"],
                    "attack_pool": list(f["pool"]), "ward_pool": list(f["pool"]), "allow_repeats": f["allow_repeats"], "max_casts": f["max_casts"],
                    "min_cast_seconds": 0.0, "max_cast_seconds": CAST_TIMEOUT_S}

        return {"slot_count": f["slots"], "colour_count": f["colours"], "max_casts": f["max_casts"], "allow_repeats": f["allow_repeats"],
                "attack_pool": list(f["pool"]), "ward_pool": list(f["pool"]), "min_cast_seconds": 0.0, "max_cast_seconds": CAST_TIMEOUT_S,
                "player_combatant": combatant("player", "You", "player"),
                "enemy_combatant": combatant("rival", self.names.get(rival, rival), "wizard")}

    def view(self, pid: str, now: float) -> dict[str, Any]:
        """Everything this player may know. The rival's ward appears only when the duel is over."""
        rival = self.rival(pid)
        out = {
            "duel_id": self.id, "kind": "pvp_ward_duel", "state": self.state, "you": pid, "rival": {"id": rival, "name": self.names.get(rival, rival)},
            "format": {k: self.fmt[k] for k in ("slots", "colours", "max_casts", "allow_repeats", "pool")},
            "your_ward": list(self.wards[pid] or []), "your_ward_locked": self.wards[pid] is not None, "rival_ward_locked": self.wards[rival] is not None,
            "round": self.round, "your_casts": len(self.history[pid]), "rival_casts": len(self.history[rival]), "max_casts": self.fmt["max_casts"],
            "your_history": [dict(h) for h in self.history[pid]], "rival_history": [dict(h) for h in self.history[rival]],
            "your_cast_pending": self.state == "active" and not self.cast_in_round[pid],
            "rival_cast_pending": self.state == "active" and not self.cast_in_round[rival],
            "cast_seq": self.cast_seq[pid], "done": self.state == "finished", "encounter": self.encounter(pid),
            "cast_deadline_s": (max(0.0, CAST_TIMEOUT_S - (now - self.first_cast_at)) if (self.state == "active" and self.first_cast_at is not None and not self.cast_in_round[pid]) else None),
        }
        if self.state == "finished" and self.result is not None:
            out["result"] = {"outcome": self.outcome_for(pid), "reason": self.reason, "winner": self.result["winner"], "your_casts": len(self.history[pid]),
                             "rival_casts": len(self.history[rival]), "rival_ward": list(self.wards[rival] or []), "your_ward": list(self.wards[pid] or [])}
            out["rival_ward"] = list(self.wards[rival] or [])
        return out


def duel_seed(world_seed: int, duel_id: str) -> int:
    return zlib.crc32(f"{world_seed}:{duel_id}".encode()) & 0x7FFFFFFF
