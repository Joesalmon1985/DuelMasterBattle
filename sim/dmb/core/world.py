"""Authoritative world simulation orchestration for the G01 slice."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sim.dmb.content.catalog import DefinitionCatalog
from sim.dmb.core.commands import CommandEnvelope, CommandResult, CommandRouter
from sim.dmb.core.events import EventJournal
from sim.dmb.core.ids import IdAllocator
from sim.dmb.core.outcomes import ImmediateOutcomeService
from sim.dmb.core.replay import ReplayLog
from sim.dmb.core.rng import RngBank
from sim.dmb.core.state import WorldState
from sim.dmb.core.transaction import TransactionCoordinator
from sim.dmb.core.types import TypeValidationError, WorldId
from sim.dmb.time.clock import ClockService
from sim.dmb.time.runner import TurnRunner
from sim.dmb.time.turns import TurnScheduler


def bootstrap_world(world_id: str = "world:g01", seed: int = 7) -> "WorldSim":
    state = WorldState(world_id=WorldId(world_id), ids=IdAllocator(WorldId(world_id)))
    state.clock["scheduled_faction_ids"] = ["faction:player"]
    state.rng = RngBank().to_dict()
    bank = RngBank.from_dict(state.rng)
    bank.ensure("gameplay", seed=seed)
    bank.ensure("ambient", seed=f"ambient:{seed}")
    state.rng = bank.to_dict()
    catalog = DefinitionCatalog()
    catalog.load(
        [
            {
                "id": "node.home",
                "schema_version": 1,
                "kind": "node",
                "era_id": "all",
                "name_key": "Home",
                "fields": {"rate": 1},
            },
            {
                "id": "node.road",
                "schema_version": 1,
                "kind": "node",
                "era_id": "all",
                "name_key": "Road",
                "fields": {"rate": 1, "home_ref": "node.home"},
            },
        ]
    )
    state.catalog_hash = catalog.catalog_hash
    state.definitions = {"payloads": catalog.all_payloads(), "hash": catalog.catalog_hash}
    return WorldSim(state=state, catalog=catalog)


@dataclass
class WorldSim:
    state: WorldState
    catalog: DefinitionCatalog = field(default_factory=DefinitionCatalog)
    events: EventJournal = field(default_factory=EventJournal)
    replay: ReplayLog = field(default_factory=ReplayLog)
    router: CommandRouter = field(init=False)
    tx: TransactionCoordinator = field(init=False)
    clock: ClockService = field(init=False)
    turns: TurnScheduler = field(init=False)
    runner: TurnRunner = field(init=False)
    outcomes: ImmediateOutcomeService = field(init=False)
    rng: RngBank = field(init=False)

    def __post_init__(self) -> None:
        self.router = CommandRouter(self.state)
        self.tx = TransactionCoordinator(self.state)
        self.clock = ClockService(self.state.clock)
        self.turns = TurnScheduler(self.state.clock)
        self.runner = TurnRunner(self.state, self.turns)
        self.outcomes = ImmediateOutcomeService(self.state)
        self.rng = RngBank.from_dict(self.state.rng)
        self._register_handlers()
        if self.catalog.catalog_hash == "" and self.state.definitions.get("payloads"):
            self.catalog.load(self.state.definitions["payloads"])

    def _register_handlers(self) -> None:
        self.router.register("Travel", self._handle_travel)
        self.router.register("Wait", self._handle_wait)
        self.router.register("AdvanceGame", self._handle_advance)
        self.router.register("Pause", self._handle_pause)
        self.router.register("Resume", self._handle_resume)
        self.router.register("Save", self._handle_save_marker)
        self.router.register("Load", self._handle_load_marker)
        self.router.register("Observe", self._handle_observe)

    def dispatch(self, envelope: CommandEnvelope) -> CommandResult:
        if self.state.legacy_godot_world_tick_enabled or self.state.legacy_godot_world_save_enabled:
            raise TypeValidationError("legacy Godot writers enabled in migrated runtime")
        result = self.router.route(envelope)
        if result.status == "REJECTED" and self.tx._active:
            self.tx.abort()
        if result.status == "ACCEPTED":
            self.replay.append(envelope.kind, envelope.payload, sequence=len(self.replay.inputs) + 1)
            self.state.rng = self.rng.to_dict()
        return result

    def advance(self, delta_ms: int, clock_sequence: int) -> CommandResult:
        envelope = CommandEnvelope(
            protocol_version=1,
            session_id="local",
            world_id=self.state.world_id,
            command_id=f"advance:{clock_sequence}",
            expected_world_version=self.state.world_version,
            kind="AdvanceGame",
            payload={"delta_ms": delta_ms, "clock_sequence": clock_sequence},
        )
        return self.dispatch(envelope)

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "world": self.state.to_dict(),
            "events": self.events.to_dict(),
            "replay": self.replay.to_dict(),
            "catalog_hash": self.state.catalog_hash,
        }

    def _commit_mutation(self, envelope: CommandEnvelope, mutate, event_kind: str) -> CommandResult:
        before = self.state.to_dict()
        self.tx.begin(envelope.kind)
        try:
            payload = mutate()
            interrupt = self.outcomes.check()
            self.state.world_version += 1
            events = self.events.append_batch(
                [{"kind": event_kind, "command_id": envelope.command_id, "payload": payload}]
            )
            self.tx.commit()
        except Exception:
            self.tx.abort()
            # Ensure state restored
            restored = WorldState.from_dict(before)
            self.state.__dict__.update(restored.__dict__)
            self.clock = ClockService(self.state.clock)
            self.turns = TurnScheduler(self.state.clock)
            self.runner = TurnRunner(self.state, self.turns)
            raise
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=events,
            interrupt=interrupt,
            public_feedback=event_kind,
            payload=payload,
        )

    def _handle_travel(self, envelope: CommandEnvelope) -> CommandResult:
        payload = envelope.payload

        def mutate() -> dict[str, Any]:
            return self.runner.execute_travel(str(payload["from_node"]), str(payload["to_node"]))

        return self._commit_mutation(envelope, mutate, "travelled")

    def _handle_wait(self, envelope: CommandEnvelope) -> CommandResult:
        payload = envelope.payload

        def mutate() -> dict[str, Any]:
            return self.runner.execute_wait(str(payload["current_node"]), str(payload["press_id"]))

        return self._commit_mutation(envelope, mutate, "waited")

    def _handle_advance(self, envelope: CommandEnvelope) -> CommandResult:
        payload = envelope.payload
        quanta = self.clock.request_advance(int(payload["delta_ms"]), int(payload["clock_sequence"]))
        self.state.world_version += 1
        events = self.events.append_batch(
            [
                {
                    "kind": "advanced",
                    "command_id": envelope.command_id,
                    "payload": {"quanta": quanta, "clock": self.clock.clock_view()},
                }
            ]
        )
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=events,
            payload={"quanta": quanta, "clock": self.clock.clock_view()},
            public_feedback="advanced",
        )

    def _handle_pause(self, envelope: CommandEnvelope) -> CommandResult:
        token = self.clock.acquire_pause(str(envelope.payload.get("reason", "ui")), "client")
        self.state.world_version += 1
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[],
            payload={"token": token},
            public_feedback="paused",
        )

    def _handle_resume(self, envelope: CommandEnvelope) -> CommandResult:
        self.clock.release_pause(str(envelope.payload["token"]))
        self.state.world_version += 1
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[],
            public_feedback="resumed",
        )

    def _handle_save_marker(self, envelope: CommandEnvelope) -> CommandResult:
        self.state.world_version += 1
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[],
            payload={"slot": envelope.payload.get("slot")},
            public_feedback="save_requested",
        )

    def _handle_load_marker(self, envelope: CommandEnvelope) -> CommandResult:
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[],
            payload={"slot": envelope.payload.get("slot")},
            public_feedback="load_requested",
        )

    def _handle_observe(self, envelope: CommandEnvelope) -> CommandResult:
        entity_id = str(envelope.payload.get("entity_id", ""))
        known = entity_id in self.state.knowledge or entity_id == self.state.player.get("node_id")
        view = {
            "entity_id": entity_id,
            "known": known,
            "label": entity_id if known else "unknown",
        }
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[],
            payload=view,
            public_feedback="observed",
        )
