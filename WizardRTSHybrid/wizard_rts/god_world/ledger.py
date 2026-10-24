"""The five-slot ledger: one canonical hand per faction, with every token in exactly one place.

Locations: a faction's available hand, a build reservation, a trade escrow, or a journey's cargo. Sources and sinks: initial grants, roll
grants, bank imports; completed-build consumption, bank exports, archived holdings (age rollover). `check()` proves the identity of PRD
section 8.4 for every role. Nothing cosmetic (worker loads, belt items) ever enters: there is no API for it."""

from __future__ import annotations

from typing import Any

from . import rules


class LedgerError(ValueError):
    pass


def _clean(goods: dict[str, int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for role, n in goods.items():
        if role not in rules.ROLES:
            raise LedgerError(f"unknown role {role!r}")
        n = int(n)
        if n < 0:
            raise LedgerError(f"negative amount {role}={n}")
        if n:
            out[role] = n
    return out


class Ledger:
    def __init__(self, faction_ids: list[str]) -> None:
        self.hands: dict[str, dict[str, int]] = {f: {r: 0 for r in rules.ROLES} for f in faction_ids}
        self.reservations: dict[str, dict[str, Any]] = {}  # rid -> {faction, purpose, goods}
        self.escrows: dict[str, dict[str, Any]] = {}  # eid -> {faction, goods, trade}
        self.cargo: dict[str, dict[str, Any]] = {}  # cid -> {owner, goods, journey}
        self.grants: dict[str, dict[str, int]] = {k: {r: 0 for r in rules.ROLES} for k in ("initial", "roll", "bank_import", "transition")}
        self.sinks: dict[str, dict[str, int]] = {k: {r: 0 for r in rules.ROLES} for k in ("build", "bank_export", "archived")}
        self.receipts: list[dict[str, Any]] = []  # durable, bounded by the world (age archives and bank books stay)
        self._next = 1

    # ------------------------------------------------------------------ ids
    def _id(self, prefix: str) -> str:
        self._next += 1
        return f"{prefix}{self._next}"

    # ------------------------------------------------------------------ hands
    def available(self, faction: str) -> dict[str, int]:
        return dict(self.hands[faction])

    def can_afford(self, faction: str, goods: dict[str, int]) -> bool:
        hand = self.hands[faction]
        return all(hand[r] >= n for r, n in _clean(goods).items())

    def grant(self, faction: str, goods: dict[str, int], source: str) -> None:
        if source not in self.grants:
            raise LedgerError(f"unknown grant source {source}")
        for r, n in _clean(goods).items():
            self.hands[faction][r] += n
            self.grants[source][r] += n

    # ------------------------------------------------------------------ build reservations
    def reserve(self, faction: str, goods: dict[str, int], purpose: str) -> str | None:
        goods = _clean(goods)
        if not self.can_afford(faction, goods):
            return None
        for r, n in goods.items():
            self.hands[faction][r] -= n
        rid = self._id("res")
        self.reservations[rid] = {"faction": faction, "purpose": purpose, "goods": goods}
        return rid

    def release(self, rid: str) -> bool:
        rec = self.reservations.pop(rid, None)
        if rec is None:
            return False
        for r, n in rec["goods"].items():
            self.hands[rec["faction"]][r] += n
        return True

    def consume(self, rid: str, purpose: str = "build") -> bool:
        rec = self.reservations.pop(rid, None)
        if rec is None:
            return False
        for r, n in rec["goods"].items():
            self.sinks[purpose][r] += n
        return True

    # ------------------------------------------------------------------ trade escrow and cargo
    def escrow(self, faction: str, goods: dict[str, int], trade: str) -> str | None:
        goods = _clean(goods)
        if not goods or not self.can_afford(faction, goods):
            return None
        for r, n in goods.items():
            self.hands[faction][r] -= n
        eid = self._id("esc")
        self.escrows[eid] = {"faction": faction, "goods": goods, "trade": trade}
        return eid

    def release_escrow(self, eid: str) -> bool:
        rec = self.escrows.pop(eid, None)
        if rec is None:
            return False
        for r, n in rec["goods"].items():
            self.hands[rec["faction"]][r] += n
        return True

    def load_cargo(self, owner: str, goods: dict[str, int], journey: str) -> str | None:
        """Available hand -> cargo (the initiator's offered goods, or a bank caravan's four tokens)."""
        goods = _clean(goods)
        if not goods or not self.can_afford(owner, goods):
            return None
        for r, n in goods.items():
            self.hands[owner][r] -= n
        cid = self._id("cgo")
        self.cargo[cid] = {"owner": owner, "goods": goods, "journey": journey}
        return cid

    def escrow_to_cargo(self, eid: str, new_owner: str, journey: str) -> str | None:
        """At the exchange: the partner's escrowed goods become the caravan's return cargo, owned by the initiator."""
        rec = self.escrows.pop(eid, None)
        if rec is None:
            return None
        cid = self._id("cgo")
        self.cargo[cid] = {"owner": new_owner, "goods": dict(rec["goods"]), "journey": journey}
        return cid

    def unload_cargo(self, cid: str, to_faction: str | None = None) -> bool:
        """Cargo -> a hand (the partner's at the exchange, the owner's on return)."""
        rec = self.cargo.pop(cid, None)
        if rec is None:
            return False
        target = to_faction or rec["owner"]
        for r, n in rec["goods"].items():
            self.hands[target][r] += n
        return True

    def export_cargo(self, cid: str) -> bool:
        """Bank trade: the four offered tokens leave the world."""
        rec = self.cargo.pop(cid, None)
        if rec is None:
            return False
        for r, n in rec["goods"].items():
            self.sinks["bank_export"][r] += n
        return True

    # ------------------------------------------------------------------ archive (age rollover)
    def archive_faction(self, faction: str, note: str) -> dict[str, int]:
        hand = self.hands[faction]
        archived = {r: n for r, n in hand.items() if n}
        for r, n in archived.items():
            self.sinks["archived"][r] += n
            hand[r] = 0
        if archived:
            self.receipts.append({"kind": "archive", "faction": faction, "goods": archived, "note": note})
        return archived

    # ------------------------------------------------------------------ the identity
    def totals(self) -> dict[str, dict[str, int]]:
        held = {r: 0 for r in rules.ROLES}
        for hand in self.hands.values():
            for r, n in hand.items():
                held[r] += n
        for col in (self.reservations, self.escrows, self.cargo):
            for rec in col.values():
                for r, n in rec["goods"].items():
                    held[r] += n
        sources = {r: sum(g[r] for g in self.grants.values()) for r in rules.ROLES}
        sinks = {r: sum(s[r] for s in self.sinks.values()) for r in rules.ROLES}
        return {"held": held, "sources": sources, "sinks": sinks}

    def check(self) -> None:
        t = self.totals()
        for r in rules.ROLES:
            if t["held"][r] != t["sources"][r] - t["sinks"][r]:
                raise LedgerError(f"{r}: held {t['held'][r]} != sources {t['sources'][r]} - sinks {t['sinks'][r]}")
        for hand in self.hands.values():
            if any(n < 0 for n in hand.values()):
                raise LedgerError("negative hand")

    # ------------------------------------------------------------------ save
    def to_dict(self) -> dict[str, Any]:
        return {"hands": {f: dict(h) for f, h in self.hands.items()}, "reservations": {k: dict(v, goods=dict(v["goods"])) for k, v in self.reservations.items()},
                "escrows": {k: dict(v, goods=dict(v["goods"])) for k, v in self.escrows.items()}, "cargo": {k: dict(v, goods=dict(v["goods"])) for k, v in self.cargo.items()},
                "grants": {k: dict(v) for k, v in self.grants.items()}, "sinks": {k: dict(v) for k, v in self.sinks.items()}, "receipts": list(self.receipts), "next": self._next}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Ledger":
        led = cls(list(payload["hands"]))
        led.hands = {f: {r: int(h.get(r, 0)) for r in rules.ROLES} for f, h in payload["hands"].items()}
        led.reservations = {k: dict(v, goods={r: int(n) for r, n in v["goods"].items()}) for k, v in payload.get("reservations", {}).items()}
        led.escrows = {k: dict(v, goods={r: int(n) for r, n in v["goods"].items()}) for k, v in payload.get("escrows", {}).items()}
        led.cargo = {k: dict(v, goods={r: int(n) for r, n in v["goods"].items()}) for k, v in payload.get("cargo", {}).items()}
        for k in led.grants:
            led.grants[k] = {r: int(payload.get("grants", {}).get(k, {}).get(r, 0)) for r in rules.ROLES}
        for k in led.sinks:
            led.sinks[k] = {r: int(payload.get("sinks", {}).get(k, {}).get(r, 0)) for r in rules.ROLES}
        led.receipts = list(payload.get("receipts", []))
        led._next = int(payload.get("next", 1))
        led.check()
        return led
