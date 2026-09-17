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
    # FX-CLOCK playable fixtures: wizard pose + linked exits with arrival poses.
    state.player = {
        "node_id": "node:1",
        "area_id": "area.home",
        "position": [4.0, 5.0],
        "facing": "down",
        "pose_generation": 0,
    }
    state.board = {
        "nodes": {
            "node:1": {
                "id": "node:1",
                "def": "node.home",
                "label": "Home Clearing",
                "area_id": "area.home",
                "theme": "grass",
                "exits": {
                    "node:2": {
                        "exit_id": "home.east",
                        "direction": "east",
                        "hold_position": [12.0, 5.0],
                        "hold_facing": "right",
                        "arrival": {
                            "node_id": "node:2",
                            "area_id": "area.road",
                            "position": [1.5, 5.0],
                            "facing": "right",
                        },
                    }
                },
            },
            "node:2": {
                "id": "node:2",
                "def": "node.road",
                "label": "Stone Road",
                "area_id": "area.road",
                "theme": "path",
                "exits": {
                    "node:1": {
                        "exit_id": "road.west",
                        "direction": "west",
                        "hold_position": [1.0, 5.0],
                        "hold_facing": "left",
                        "arrival": {
                            "node_id": "node:1",
                            "area_id": "area.home",
                            "position": [12.0, 5.0],
                            "facing": "left",
                        },
                    }
                },
            },
        }
    }
    person_id = state.ids.new("person")
    state.people[person_id] = {
        "id": person_id,
        "definition_id": "npc.villager",
        "node_id": "node:1",
        "grid": [10, 3],
        "role": "guide",
        "display_name": "Mira",
    }
    # Unknown until observed; role permitted on interact/reveal.
    state.knowledge = {}
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
        self.router.register("Interact", self._handle_interact)
        self.router.register("SyncPose", self._handle_sync_pose)

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
        from sim.dmb.narrative.knowledge import filter_entity

        entity_id = str(envelope.payload.get("entity_id", ""))
        view = filter_entity(self.state, entity_id)
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[],
            payload=view,
            public_feedback="observed",
        )

    def _handle_interact(self, envelope: CommandEnvelope) -> CommandResult:
        from sim.dmb.narrative.knowledge import KnowledgeFact, filter_entity, reveal

        entity_id = str(envelope.payload.get("entity_id", ""))
        person = self.state.people.get(entity_id)
        if person is None:
            return CommandResult(
                status="REJECTED",
                code="INVALID",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="unknown entity",
            )
        if person.get("node_id") != self.state.player.get("node_id"):
            return CommandResult(
                status="REJECTED",
                code="OUT_OF_RANGE",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="too far to interact",
            )
        reveal(
            self.state,
            entity_id,
            KnowledgeFact(entity_id, "met", role=str(person.get("role", "villager"))),
            role=str(person.get("role", "villager")),
        )
        # Permit name only after interaction.
        self.state.knowledge[entity_id]["name"] = person.get("display_name")
        self.state.world_version += 1
        view = filter_entity(self.state, entity_id)
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[],
            payload=view,
            public_feedback="interacted",
        )

    def _handle_sync_pose(self, envelope: CommandEnvelope) -> CommandResult:
        payload = envelope.payload
        # Reject delayed source-area pose updates after Travel has committed.
        reported_node = payload.get("node_id")
        if reported_node is not None and str(reported_node) != str(self.state.player.get("node_id")):
            return CommandResult(
                status="REJECTED",
                code="STALE_NODE",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                payload={"node_id": self.state.player.get("node_id")},
                public_feedback="stale_pose",
            )
        reported_gen = payload.get("pose_generation")
        if reported_gen is not None and int(reported_gen) != int(self.state.player.get("pose_generation", 0)):
            return CommandResult(
                status="REJECTED",
                code="STALE_POSE",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                payload={"pose_generation": self.state.player.get("pose_generation", 0)},
                public_feedback="stale_pose",
            )
        pos = payload.get("position")
        if isinstance(pos, (list, tuple)) and len(pos) >= 2:
            self.state.player["position"] = [float(pos[0]), float(pos[1])]
        if payload.get("facing"):
            self.state.player["facing"] = str(payload["facing"])
        # Pose sync does not advance turns or bump world_version (presentation lease).
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[],
            payload={
                "position": self.state.player.get("position"),
                "facing": self.state.player.get("facing"),
                "node_id": self.state.player.get("node_id"),
                "pose_generation": self.state.player.get("pose_generation", 0),
            },
            public_feedback="pose_synced",
        )
