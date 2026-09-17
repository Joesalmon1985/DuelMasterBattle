"""Command envelopes, routing and idempotent receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError


@dataclass(frozen=True)
class CommandEnvelope:
    protocol_version: int
    session_id: str
    world_id: str
    command_id: str
    expected_world_version: int
    kind: str
    payload: dict[str, Any]


@dataclass
class CommandResult:
    status: str
    code: str
    command_id: str
    world_version: int
    events: list[dict[str, Any]]
    interrupt: dict[str, Any] | None = None
    public_feedback: str = ""
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "code": self.code,
            "command_id": self.command_id,
            "world_version": self.world_version,
            "events": list(self.events),
            "interrupt": self.interrupt,
            "public_feedback": self.public_feedback,
            "payload": self.payload or {},
        }


class CommandRouter:
    def __init__(self, state: WorldState) -> None:
        self.state = state
        self._handlers: dict[str, Callable[[CommandEnvelope], CommandResult]] = {}

    def register(self, kind: str, handler: Callable[[CommandEnvelope], CommandResult]) -> None:
        self._handlers[kind] = handler

    def prior_receipt(self, command_id: str) -> dict[str, Any] | None:
        return self.state.command_receipts.get(command_id)

    def validate_envelope(self, envelope: CommandEnvelope) -> None:
        if envelope.protocol_version != 1:
            raise TypeValidationError("unsupported protocol_version")
        if envelope.world_id != self.state.world_id:
            raise TypeValidationError("foreign world_id rejected")
        if not envelope.command_id:
            raise TypeValidationError("command_id required")
        if envelope.kind not in self._handlers:
            raise TypeValidationError(f"unknown command kind {envelope.kind}")

    def route(self, envelope: CommandEnvelope) -> CommandResult:
        self.validate_envelope(envelope)
        prior = self.prior_receipt(envelope.command_id)
        if prior is not None:
            if prior.get("request_fingerprint") != self._fingerprint(envelope):
                return CommandResult(
                    status="REJECTED",
                    code="ID_REUSE",
                    command_id=envelope.command_id,
                    world_version=self.state.world_version,
                    events=[],
                    public_feedback="command id reused with different payload",
                )
            return CommandResult(**{**prior["result"], "status": "DUPLICATE"})
        if envelope.expected_world_version != self.state.world_version:
            return CommandResult(
                status="REJECTED",
                code="STALE_VERSION",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="stale world_version",
            )
        handler = self._handlers[envelope.kind]
        try:
            result = handler(envelope)
        except TypeValidationError as exc:
            return CommandResult(
                status="REJECTED",
                code="INVALID",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - convert to abort semantics for callers
            return CommandResult(
                status="REJECTED",
                code="INTERNAL",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback=str(exc),
            )
        if result.status in {"ACCEPTED", "DUPLICATE"}:
            self.state.command_receipts[envelope.command_id] = {
                "request_fingerprint": self._fingerprint(envelope),
                "result": result.to_dict(),
            }
        return result

    @staticmethod
    def _fingerprint(envelope: CommandEnvelope) -> str:
        import json

        return json.dumps(
            {
                "kind": envelope.kind,
                "payload": envelope.payload,
                "expected_world_version": envelope.expected_world_version,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
