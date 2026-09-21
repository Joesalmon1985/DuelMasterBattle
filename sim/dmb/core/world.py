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


def get_construction_service(sim: "WorldSim") -> "ConstructionService":
    from sim.dmb.construction.orders import ConstructionService

    return ConstructionService(sim.state)


_UNIT_PERSON_NAMES = (
    "Bren", "Cal", "Dorin", "Ellis", "Fenna", "Garr", "Hale", "Ivo",
    "Jora", "Kest", "Lira", "Marn", "Ness", "Orin", "Piet", "Quinn",
    "Rusk", "Sera", "Tovin", "Una", "Vell", "Wren", "Yara", "Zell",
)


def _ensure_unit_person_name(unit: dict[str, Any]) -> str:
    """Stable once-generated individual name for a soldier (save-compatible)."""
    existing = unit.get("person_name") or unit.get("given_name")
    if existing:
        return str(existing)
    import zlib

    digest = zlib.crc32(str(unit.get("id", "")).encode("utf-8")) & 0xFFFFFFFF
    name = _UNIT_PERSON_NAMES[digest % len(_UNIT_PERSON_NAMES)]
    unit["person_name"] = name
    return name


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
    industry: Any = field(init=False)
    rng: RngBank = field(init=False)

    def __post_init__(self) -> None:
        self.router = CommandRouter(self.state)
        self.tx = TransactionCoordinator(self.state)
        self.clock = ClockService(self.state.clock)
        self.turns = TurnScheduler(self.state.clock)
        self.runner = TurnRunner(self.state, self.turns)
        self.outcomes = ImmediateOutcomeService(self.state)
        from sim.dmb.industry.service import IndustryService

        self.industry = IndustryService(self.state)
        self.rng = RngBank.from_dict(self.state.rng)
        self._register_handlers()
        if self.catalog.catalog_hash == "" and self.state.definitions.get("payloads"):
            self.catalog.load(self.state.definitions["payloads"])
        from sim.dmb.persistence.migrate import ensure_unit_person_links

        ensure_unit_person_links(self.state)

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
        self.router.register("SyncPresentation", self._handle_sync_presentation)
        self.router.register("CastDestroy", self._handle_cast_destroy)
        self.router.register("CastBuff", self._handle_cast_buff)
        self.router.register("OpenBattleLease", self._handle_open_battle_lease)
        self.router.register("BattleCheckpoint", self._handle_battle_checkpoint)
        self.router.register("CloseBattleLease", self._handle_close_battle_lease)
        self.router.register("StartHazardDuel", self._handle_start_hazard_duel)
        self.router.register("ResolveHazardDuel", self._handle_resolve_hazard_duel)
        self.router.register("HazardDuelAction", self._handle_hazard_duel_action)
        self.router.register("HazardDuelCheckpoint", self._handle_hazard_duel_checkpoint)

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
        from sim.dmb.persistence.migrate import SCHEMA_VERSION, ensure_unit_person_links

        ensure_unit_person_links(self.state)
        return {
            "schema_version": SCHEMA_VERSION,
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
        industry_events = self.industry.advance_quanta(quanta)
        self.state.world_version += 1
        events = self.events.append_batch(
            [
                {
                    "kind": "advanced",
                    "command_id": envelope.command_id,
                    "payload": {
                        "quanta": quanta,
                        "clock": self.clock.clock_view(),
                        "industry_events": industry_events,
                    },
                }
            ]
        )
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=events,
            payload={"quanta": quanta, "clock": self.clock.clock_view(), "industry_events": industry_events},
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
        from sim.dmb.narrative.knowledge import KnowledgeFact, filter_entity, reveal
        from sim.dmb.narrative.semantic import SemanticResolver

        entity_id = str(envelope.payload.get("entity_id", ""))
        local_poses = envelope.payload.get("local_poses")
        resolver = SemanticResolver(self.state)
        classified = resolver._record_for(entity_id)
        if classified is None:
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
        kind, record = classified
        # Observation-led durable identity for people and soldiers.
        # People: Observe does not stamp personal names (Interact/Talk does).
        # Units: Observe reveals public archetype label; Talk uses linked Person.
        if kind == "person":
            pass
        elif kind == "unit":
            person_id = record.get("person_id")
            person = self.state.people.get(person_id) if person_id else None
            if person and not record.get("person_name"):
                record["person_name"] = person.get("name") or person.get("display_name")
            elif not record.get("person_name"):
                _ensure_unit_person_name(record)
            reveal(
                self.state,
                entity_id,
                KnowledgeFact(entity_id, "observed", role=str(record.get("archetype", "soldier"))),
                role=str(record.get("archetype", "soldier")),
            )
            self.state.knowledge[entity_id].pop("name", None)
            fx = self.state.board.setdefault("fx_battle", {})
            labels = fx.setdefault("labels", {})
            fac = str(record.get("faction_id") or "")
            from sim.dmb.narrative.semantic import ARCHETYPE_LABELS, FACTION_COLOUR

            colour = FACTION_COLOUR.get(fac, fac.replace("faction:", "").title() or "Unit")
            arch = str(record.get("archetype") or "")
            labels[entity_id] = f"{colour} {ARCHETYPE_LABELS.get(arch, arch.title() or 'Soldier')}".strip()
            self.state.world_version += 1
            if person_id and person_id not in self.state.knowledge:
                reveal(
                    self.state,
                    str(person_id),
                    KnowledgeFact(str(person_id), "met", role="soldier"),
                    role="soldier",
                )
                self.state.knowledge[str(person_id)].pop("name", None)
        inspect = resolver.inspect(
            entity_id,
            local_poses=local_poses if isinstance(local_poses, dict) else None,
        )
        view = filter_entity(self.state, entity_id)
        label = view.get("label") or inspect.get("label")
        if kind == "person" and not view.get("known"):
            label = view.get("label") or "unknown"
        view.update(
            {
                "kind": kind,
                "label": label,
                "description": inspect.get("description"),
                "nearby": inspect.get("nearby"),
            }
        )
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[{"kind": "observed", "entity_id": entity_id}],
            payload=view,
            public_feedback="observed",
        )

    def _handle_interact(self, envelope: CommandEnvelope) -> CommandResult:
        from sim.dmb.narrative.knowledge import KnowledgeFact, filter_entity, reveal

        payload = envelope.payload
        action = str(payload.get("action") or "")
        if action == "confirm_village_quest":
            from sim.dmb.world.fx_village_solutions import confirm_pending_quest

            out = confirm_pending_quest(self.state) or {"status": "noop"}
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "quest_confirm", "payload": out}],
                payload=out,
                public_feedback=str(out.get("status") or "confirmed"),
            )
        if action == "pickup":
            from sim.dmb.player.inventory import InventoryService

            item_id = str(payload.get("item_id") or payload.get("entity_id") or "")
            try:
                item = InventoryService(self.state).pickup(item_id)
            except Exception as exc:
                return CommandResult(
                    status="REJECTED",
                    code="INVALID",
                    command_id=envelope.command_id,
                    world_version=self.state.world_version,
                    events=[],
                    public_feedback=str(exc),
                )
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "pickup", "item_id": item_id}],
                payload=item,
                public_feedback=f"picked up {item.get('label') or item_id}",
            )
        if action == "drop":
            from sim.dmb.player.inventory import InventoryService

            item_id = str(payload.get("item_id") or payload.get("entity_id") or "")
            area_id = str(payload.get("area_id") or self.state.player.get("area_id") or "area.village")
            position = payload.get("position") or self.state.player.get("position") or [0, 0]
            try:
                item = InventoryService(self.state).drop(
                    item_id, area_id=area_id, position=[float(position[0]), float(position[1])]
                )
            except Exception as exc:
                return CommandResult(
                    status="REJECTED",
                    code="INVALID",
                    command_id=envelope.command_id,
                    world_version=self.state.world_version,
                    events=[],
                    public_feedback=str(exc),
                )
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "drop", "item_id": item_id}],
                payload=item,
                public_feedback=f"dropped {item.get('label') or item_id}",
            )
        if action == "enter_sluice":
            self.state.player["area_id"] = "area.sluice"
            self.state.player["position"] = [8.0, 9.0]
            from sim.dmb.adventure.puzzles import PuzzleService
            from sim.dmb.world.overworld_export import export_sluice_area

            lease = PuzzleService(self.state).prepare_lease("puzzle.sluice", area_id="area.sluice")
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "enter_sluice"}],
                payload={"area": export_sluice_area(self.state), "lease": lease},
                public_feedback="entered sluice works",
            )
        if action == "return_village":
            fx = self.state.board.get("fx_village") or {}
            self.state.player["area_id"] = "area.village"
            self.state.player["node_id"] = str(fx.get("node_id") or "node:village")
            self.state.player["position"] = [28.0, 32.0]
            from sim.dmb.world.overworld_export import export_overworld_area

            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "return_village"}],
                payload={"area": export_overworld_area(self.state)},
                public_feedback="returned to village",
            )
        if action == "puzzle_act":
            from sim.dmb.adventure.puzzles import PuzzleService

            lease_id = str(payload.get("lease_id") or "")
            mechanism_id = str(payload.get("mechanism_id") or payload.get("entity_id") or "")
            mech_action = str(payload.get("mechanism_action") or payload.get("op") or "toggle")
            expected = int(payload.get("expected_version") or payload.get("lease_version") or 0)
            item_id = payload.get("item_id")
            try:
                out = PuzzleService(self.state).act(
                    lease_id,
                    expected_version=expected,
                    mechanism_id=mechanism_id,
                    action=mech_action,
                    item_id=str(item_id) if item_id else None,
                )
            except Exception as exc:
                return CommandResult(
                    status="REJECTED",
                    code="INVALID",
                    command_id=envelope.command_id,
                    world_version=self.state.world_version,
                    events=[],
                    public_feedback=str(exc),
                )
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "puzzle_act", "mechanism_id": mechanism_id}],
                payload=out,
                public_feedback=str(out.get("status") or "acted"),
            )
        if action == "puzzle_push":
            from sim.dmb.adventure.puzzles import PuzzleService

            lease_id = str(payload.get("lease_id") or "")
            mechanism_id = str(payload.get("mechanism_id") or payload.get("entity_id") or "")
            expected = int(payload.get("expected_version") or payload.get("lease_version") or 0)
            position = payload.get("position")
            try:
                if position is not None:
                    out = PuzzleService(self.state).sync_local_pose(
                        lease_id,
                        expected_version=expected,
                        actor_id=mechanism_id,
                        position=[float(position[0]), float(position[1])],
                        kind="movable_box",
                    )
                else:
                    out = PuzzleService(self.state).act(
                        lease_id,
                        expected_version=expected,
                        mechanism_id=mechanism_id,
                        action="push",
                    )
            except Exception as exc:
                return CommandResult(
                    status="REJECTED",
                    code="INVALID",
                    command_id=envelope.command_id,
                    world_version=self.state.world_version,
                    events=[],
                    public_feedback=str(exc),
                )
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "puzzle_push", "mechanism_id": mechanism_id}],
                payload=out,
                public_feedback=str(out.get("status") or "pushed"),
            )
        # Route-clearing interaction for catastrophe cubes (G02 / FX-CARGO).
        if action == "clear_hazard":
            cube_id = str(payload.get("cube_id") or payload.get("entity_id") or "")
            cubes = self.state.board.setdefault("hazard_cubes", {})
            if cube_id and cube_id in cubes:
                cubes.pop(cube_id, None)
            elif cube_id == "" and cubes:
                # Clear first active cube when unspecified.
                first = next(iter(cubes))
                cubes.pop(first, None)
                cube_id = first
            else:
                return CommandResult(
                    status="REJECTED",
                    code="INVALID",
                    command_id=envelope.command_id,
                    world_version=self.state.world_version,
                    events=[],
                    public_feedback="no hazard to clear",
                )
            fx = self.state.board.get("fx_cargo") or {}
            cart_id = str(fx.get("cart_id") or "")
            cart = self.state.carts.get(cart_id) if cart_id else None
            if isinstance(cart, dict) and cart.get("status") == "blocked":
                cart["status"] = "en_route"
                cart.pop("block_reason", None)
                from sim.dmb.presentation.journeys import begin_cart_assignment_journey

                begin_cart_assignment_journey(self.state, cart_id)
            if fx:
                fx["delivery_status"] = "en_route"
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "hazard_cleared", "cube_id": cube_id}],
                payload={"cleared": cube_id, "remaining": list(cubes.keys())},
                public_feedback="hazard cleared",
            )
        if str(payload.get("action") or "") == "place_route_block":
            fx = self.state.board.get("fx_cargo") or {}
            block_node = str(payload.get("node_id") or fx.get("block_node") or fx.get("block_hex") or "")
            if not block_node:
                return CommandResult(
                    status="REJECTED",
                    code="INVALID",
                    command_id=envelope.command_id,
                    world_version=self.state.world_version,
                    events=[],
                    public_feedback="no block node",
                )
            self.state.board.setdefault("hazard_cubes", {})["fx-block"] = {
                "node_id": block_node,
                "hex_id": block_node,
                "active": True,
            }
            fx["delivery_status"] = "blocked_route"
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "hazard_placed", "node_id": block_node}],
                payload={"node_id": block_node},
                public_feedback="route blocked",
            )
        if str(payload.get("action") or "") == "start_delivery":
            return self._start_fx_cargo_delivery(envelope)
        action = str(payload.get("action") or "")
        if action in {"industry_damage", "industry_strike", "industry_clear_strike", "industry_repair"}:
            from sim.dmb.construction.orders import ConstructionService
            from sim.dmb.people.jobs import JobService

            fx = self.state.board.get("fx_industry") or {}
            processor_id = str(fx.get("processor_id") or "")
            if not processor_id or processor_id not in self.state.buildings:
                return CommandResult(
                    status="REJECTED",
                    code="INVALID",
                    command_id=envelope.command_id,
                    world_version=self.state.world_version,
                    events=[],
                    public_feedback="industry fixture unavailable",
                )
            event: dict[str, Any]
            if action == "industry_damage":
                building = self.state.buildings[processor_id]
                building["health"] = max(1, int(building.get("max_health", 100)) // 4)
                event = {"kind": "industry_damage", "building_id": processor_id}
            elif action in {"industry_strike", "industry_clear_strike"}:
                modifier = 0 if action == "industry_strike" else 1
                JobService(self.state).set_modifier("industry:operator:fx", modifier)
                event = {"kind": action, "modifier": modifier}
            else:
                service = ConstructionService(self.state)
                order = service.reserve_order(
                    "repair",
                    faction_id="faction:industry",
                    store_id=str(fx["repair_store_id"]),
                    target_building=processor_id,
                )
                if order.get("status") != "ready":
                    return CommandResult(
                        status="REJECTED",
                        code="INVALID",
                        command_id=envelope.command_id,
                        world_version=self.state.world_version,
                        events=[],
                        payload=order,
                        public_feedback=str(order.get("reason", "repair unavailable")),
                    )
                committed = service.commit_delivered(str(order["id"]))
                event = {
                    "kind": "industry_repair",
                    "building_id": processor_id,
                    "order_id": order["id"],
                    "paid": dict(order["required_goods"]),
                    "result": committed.get("completion_receipt", {}).get("result", {}),
                }
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[event],
                payload=event,
                public_feedback=event["kind"].replace("_", " "),
            )

        entity_id = str(payload.get("entity_id", ""))
        person = self.state.people.get(entity_id)
        if person is None and entity_id in self.state.units:
            # Soldiers are Persons; Talk may target unit_id and resolve via person_id.
            linked = self.state.units[entity_id].get("person_id")
            person = self.state.people.get(linked) if linked else None
            if person is not None:
                entity_id = str(linked)
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
        action = str(payload.get("action") or "inspect")
        if action in {"talk", "dialogue", "start_dialogue"}:
            from sim.dmb.narrative.dialogue import DialogueResolver
            from sim.dmb.narrative.line_catalog import LineCatalog

            reveal(
                self.state,
                entity_id,
                KnowledgeFact(entity_id, "met", role=str(person.get("role", "villager"))),
                role=str(person.get("role", "villager")),
            )
            self.state.knowledge[entity_id]["name"] = person.get("display_name")
            fx = self.state.board.get("fx_village") or {}
            quests = self.state.quests or {}
            quest_id = str(fx.get("quest_template_id") or "quest.factory_shortage")
            stage = 0
            for q in quests.values():
                if str(q.get("template_id") or q.get("definition_id") or "") == quest_id:
                    stage = int(q.get("stage") or 0)
                    break
            resolver = DialogueResolver(self.state, LineCatalog.load())
            session = resolver.start(
                speaker_id=entity_id,
                quest_id=quest_id,
                stage=stage,
                cause_id=str(fx.get("cause_template_id") or "cause.factory_shortage"),
                era_id=str((self.state.board or {}).get("era_id") or "ancient"),
                node_id=str(self.state.player.get("node_id") or ""),
            )
            choices = resolver.choices(str(session["id"]))
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "dialogue_started", "entity_id": entity_id, "session_id": session["id"]}],
                payload={
                    "kind": "dialogue",
                    "entity_id": entity_id,
                    "session": session,
                    "choices": choices,
                    "text": session.get("text"),
                    "speaker_name": person.get("display_name") or "Worker",
                },
                public_feedback=str(session.get("text") or "talked"),
            )
        if action in {"choose_dialogue", "dialogue_choose"}:
            from sim.dmb.narrative.dialogue import DialogueResolver
            from sim.dmb.narrative.line_catalog import LineCatalog

            session_id = str(payload.get("session_id") or "")
            choice_id = str(payload.get("choice_id") or "")
            resolver = DialogueResolver(self.state, LineCatalog.load())
            result = resolver.choose(session_id, choice_id)
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "dialogue_choice", "session_id": session_id, "choice_id": choice_id}],
                payload=result,
                public_feedback=str((result.get("session") or {}).get("text") or "chosen"),
            )
        if action in {"close_dialogue", "dialogue_close"}:
            from sim.dmb.narrative.dialogue import DialogueResolver
            from sim.dmb.narrative.line_catalog import LineCatalog

            session_id = str(payload.get("session_id") or "")
            resolver = DialogueResolver(self.state, LineCatalog.load())
            closed = resolver.close(session_id)
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "dialogue_closed", "session_id": session_id}],
                payload=closed,
                public_feedback="closed",
            )
        # Bind visible warehouse / cart / staging to authoritative records.
        inspect_payload = self._inspect_fx_person(entity_id, person)
        if inspect_payload is not None:
            reveal(
                self.state,
                entity_id,
                KnowledgeFact(entity_id, "met", role=str(person.get("role", "villager"))),
                role=str(person.get("role", "villager")),
            )
            self.state.knowledge[entity_id]["name"] = person.get("display_name")
            self.state.world_version += 1
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "inspected", "entity_id": entity_id}],
                payload=inspect_payload,
                public_feedback=str(inspect_payload.get("summary") or "inspected"),
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

    def _inspect_fx_person(self, entity_id: str, person: dict) -> dict | None:
        from sim.dmb.logistics.stock import StockLedger

        role = str(person.get("role") or "")
        fx = self.state.board.get("fx_cargo") or {}
        if role == "warehouse" or entity_id == fx.get("warehouse_person_id"):
            store_id = str(person.get("store_id") or fx.get("store") or "")
            ledger = StockLedger(self.state)
            stock = {}
            for good in ("timber", "brick", "wool", "grain", "ore"):
                stock[good] = {
                    "available": ledger.available(store_id, good),
                    "reserved": ledger.reserved(store_id, good),
                    "escrow": ledger.escrow(store_id, good),
                }
            return {
                "kind": "warehouse",
                "entity_id": entity_id,
                "name": person.get("display_name") or "Warehouse",
                "store_id": store_id,
                "stock": stock,
                "delivery_reservation_id": fx.get("delivery_reservation_id"),
                "summary": f"Warehouse {store_id} timber a={stock['timber']['available']} r={stock['timber']['reserved']}",
            }
        if role == "cart" or entity_id == fx.get("cart_person_id"):
            cart_id = str(person.get("cart_id") or fx.get("cart_id") or "")
            cart = dict(self.state.carts.get(cart_id) or {})
            cargo = [
                {"good_id": lot.get("good_id"), "quantity": lot.get("quantity"), "status": lot.get("status")}
                for lot in cart.get("cargo_lots") or []
                if lot.get("status") == "aboard"
            ]
            status = str(cart.get("status") or "idle")
            if status == "en_route":
                phase = "travelling"
            elif status == "blocked":
                phase = "blocked"
            elif status in {"arrived", "delivered"}:
                phase = "delivered"
            else:
                phase = "idle"
            dest = cart.get("destination_store") or fx.get("staging_store")
            return {
                "kind": "cart",
                "entity_id": entity_id,
                "name": person.get("display_name") or "Cart",
                "cart_id": cart_id,
                "status": status,
                "phase": phase,
                "current_node": cart.get("current_node"),
                "destination_store": dest,
                "route": list(cart.get("route") or []),
                "route_index": cart.get("route_index"),
                "cargo": cargo,
                "delivery_status": fx.get("delivery_status"),
                "summary": (
                    f"Cart {cart_id} {phase} @ {cart.get('current_node')} "
                    f"cargo={cargo} dest={dest}"
                ),
            }
        if role == "staging" or entity_id == fx.get("staging_person_id"):
            store_id = str(person.get("store_id") or fx.get("staging_store") or "")
            ledger = StockLedger(self.state)
            stock = {
                good: {
                    "available": ledger.available(store_id, good),
                    "reserved": ledger.reserved(store_id, good),
                    "escrow": ledger.escrow(store_id, good),
                }
                for good in ("timber", "brick", "wool", "grain", "ore")
            }
            return {
                "kind": "staging",
                "entity_id": entity_id,
                "name": person.get("display_name") or "Staging",
                "store_id": store_id,
                "stock": stock,
                "construction_status": fx.get("construction_status"),
                "summary": f"Staging {store_id} timber a={stock['timber']['available']}",
            }
        return None

    def _start_fx_cargo_delivery(self, envelope: CommandEnvelope) -> CommandResult:
        """Assign the FX-CARGO cart using the fixture delivery reservation when present."""
        from sim.dmb.logistics.carts import CartService
        from sim.dmb.logistics.routes import RoutePlanner
        from sim.dmb.logistics.stock import StockLedger
        from sim.dmb.core.types import TypeValidationError

        fx = self.state.board.setdefault("fx_cargo", {})
        cart_id = str(fx.get("cart_id") or "")
        store = str(fx.get("store") or "")
        staging_store = str(fx.get("staging_store") or "")
        n0 = str(fx.get("N0") or "")
        n2 = str(fx.get("N2") or "")
        required = dict(fx.get("required") or {"timber": 1, "brick": 1, "wool": 1, "grain": 1})
        if not cart_id or not store or not staging_store or not n0 or not n2:
            return CommandResult(
                status="REJECTED",
                code="INVALID",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="fx_cargo incomplete",
            )
        cart = self.state.carts.get(cart_id)
        if cart is None:
            return CommandResult(
                status="REJECTED",
                code="INVALID",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="missing cart",
            )
        aboard = [
            lot for lot in cart.get("cargo_lots") or [] if lot.get("status") == "aboard"
        ]
        if cart.get("status") in {"assigned", "en_route", "blocked"} and aboard:
            return CommandResult(
                status="REJECTED",
                code="BUSY",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                payload={"cart_id": cart_id, "status": cart.get("status"), "cargo": aboard},
                public_feedback="delivery already in progress",
            )

        ledger = StockLedger(self.state)
        carts = CartService(self.state, ledger=ledger)
        routes = RoutePlanner(self.state)
        planned = routes.route(str(cart.get("owner_faction") or "faction:1"), n0, n2)
        if planned.get("path") is None:
            return CommandResult(
                status="REJECTED",
                code="BLOCKED",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                payload={"reason": planned.get("reason"), "required": required},
                public_feedback=str(planned.get("reason") or "route blocked"),
            )

        available = {good: ledger.available(store, good) for good in required}
        reserved = {good: ledger.reserved(store, good) for good in required}
        res_id = str(fx.get("delivery_reservation_id") or "")
        res_record = (self.state.stocks.get("_reservations") or {}).get(res_id)
        reservation_id = None
        created_reservation = False
        if isinstance(res_record, dict) and res_record.get("status") == "reserved":
            reservation_id = res_id
        else:
            missing = {
                good: int(required[good]) - int(available.get(good, 0))
                for good in required
                if int(available.get(good, 0)) < int(required[good])
            }
            if missing:
                return CommandResult(
                    status="REJECTED",
                    code="INSUFFICIENT",
                    command_id=envelope.command_id,
                    world_version=self.state.world_version,
                    events=[],
                    payload={
                        "required": required,
                        "available": available,
                        "reserved": reserved,
                        "missing": missing,
                        "store_id": store,
                    },
                    public_feedback=(
                        f"need {required}; available {available}; missing {missing} at {store}"
                    ),
                )
            try:
                created = ledger.reserve(f"fx-play-{envelope.command_id}", required, store_id=store)
            except TypeValidationError as exc:
                return CommandResult(
                    status="REJECTED",
                    code="INSUFFICIENT",
                    command_id=envelope.command_id,
                    world_version=self.state.world_version,
                    events=[],
                    payload={"required": required, "available": available, "store_id": store},
                    public_feedback=str(exc),
                )
            reservation_id = created["id"]
            created_reservation = True
            fx["delivery_reservation_id"] = reservation_id

        # Snapshot cargo count so a failed assign can roll back the load.
        before_lots = list(cart.get("cargo_lots") or [])
        before_status = cart.get("status")
        try:
            carts.load_from_reservation(cart_id, reservation_id)
            carts.assign(cart_id, list(planned["path"]), destination_store=staging_store)
        except Exception as exc:
            cart["cargo_lots"] = before_lots
            cart["status"] = before_status
            if created_reservation:
                try:
                    ledger.release_reservation(reservation_id)
                except Exception:
                    pass
            return CommandResult(
                status="REJECTED",
                code="FAILED",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                payload={"required": required, "available": available, "error": str(exc)},
                public_feedback=f"delivery failed: {exc}",
            )

        fx["delivery_status"] = "en_route"
        fx["construction_pending"] = True
        fx["reservation_id"] = reservation_id
        person_id = str(fx.get("cart_person_id") or "person:cart")
        person = self.state.people.get(person_id)
        if isinstance(person, dict):
            person["node_id"] = cart.get("current_node", n0)
            person["label"] = "Hauler Cart (travelling)"
            person["display_name"] = person["label"]
        from sim.dmb.presentation.journeys import begin_cart_assignment_journey

        journey = begin_cart_assignment_journey(self.state, cart_id)
        self.state.world_version += 1
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[{"kind": "delivery_started", "cart_id": cart_id, "path": planned["path"]}],
            payload={
                "cart_id": cart_id,
                "path": planned["path"],
                "reservation_id": reservation_id,
                "required": required,
                "journey": journey,
            },
            public_feedback="delivery started",
        )

    def _handle_sync_presentation(self, envelope: CommandEnvelope) -> CommandResult:
        from sim.dmb.presentation.journeys import apply_presentation_progress

        # Presentation lease: does not advance turns or bump world_version.
        result = apply_presentation_progress(self.state, dict(envelope.payload or {}))
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[],
            payload=result,
            public_feedback="presentation_synced",
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

    def _handle_cast_destroy(self, envelope: CommandEnvelope) -> CommandResult:
        from sim.dmb.player.magic import MagicService

        target_id = str(envelope.payload.get("target_id") or "")
        lease_id = envelope.payload.get("lease_id")
        observed = envelope.payload.get("observed_ids")
        observed_set = set(str(x) for x in observed) if isinstance(observed, list) else None
        local_poses = envelope.payload.get("local_poses")
        poses = local_poses if isinstance(local_poses, dict) else None
        out = MagicService(self.state).destroy(
            target_id,
            observed_local_ids=observed_set,
            command_id=envelope.command_id,
            lease_id=str(lease_id) if lease_id else None,
            local_poses=poses,
        )
        if out.get("status") == "rejected":
            return CommandResult(
                status="REJECTED",
                code=str(out.get("reason") or "INVALID"),
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                payload=out,
                public_feedback=str(out.get("reason") or "rejected"),
            )
        if out.get("status") not in {"pending_lease", "idempotent"}:
            self.state.world_version += 1
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[{"kind": "cast_destroy", "payload": out}],
            payload=out,
            public_feedback=str(out.get("status")),
        )

    def _handle_cast_buff(self, envelope: CommandEnvelope) -> CommandResult:
        from sim.dmb.player.magic import MagicService

        target_id = str(envelope.payload.get("target_id") or "")
        buff_kind = str(envelope.payload.get("buff_kind") or "")
        observed = envelope.payload.get("observed_ids")
        observed_set = set(str(x) for x in observed) if isinstance(observed, list) else None
        local_poses = envelope.payload.get("local_poses")
        poses = local_poses if isinstance(local_poses, dict) else None
        frozen = bool(self.state.clock.get("pause_tokens"))
        out = MagicService(self.state).apply_buff(
            target_id,
            buff_kind,
            observed_local_ids=observed_set,
            command_id=envelope.command_id,
            frozen=frozen,
            local_poses=poses,
        )
        if out.get("status") == "rejected":
            return CommandResult(
                status="REJECTED",
                code=str(out.get("reason") or "INVALID"),
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                payload=out,
                public_feedback=str(out.get("reason") or "rejected"),
            )
        self.state.world_version += 1
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[{"kind": "cast_buff", "payload": out}],
            payload=out,
            public_feedback=str(out.get("status")),
        )

    def _handle_open_battle_lease(self, envelope: CommandEnvelope) -> CommandResult:
        from sim.dmb.encounters.registry import EncounterRegistry

        battle_id = str(envelope.payload.get("battle_id") or "battle:fx")
        battle = (self.state.battles or {}).get(battle_id)
        if not isinstance(battle, dict):
            return CommandResult(
                status="REJECTED",
                code="NO_BATTLE",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="no battle",
            )
        # Prevent duplicate active local lease for same participants.
        for existing in (self.state.leases or {}).values():
            if (
                isinstance(existing, dict)
                and existing.get("kind") == "battle"
                and existing.get("state") == "ACTIVE"
                and existing.get("battle_id") == battle_id
            ):
                return CommandResult(
                    status="ACCEPTED",
                    code="OK",
                    command_id=envelope.command_id,
                    world_version=self.state.world_version,
                    events=[],
                    payload={"lease": existing, "reused": True},
                    public_feedback="lease_active",
                )
        unit_ids = [str(uid) for uid in (battle.get("participants") or []) if uid in self.state.units]
        snapshot_units = {uid: dict(self.state.units[uid]) for uid in unit_ids}
        buildings = {
            bid: dict(self.state.buildings[bid])
            for bid in (battle.get("buildings") or [])
            if bid in self.state.buildings
        }
        hostiles = battle.get("hostiles") or {
            "faction:red": ["faction:blue"],
            "faction:blue": ["faction:red"],
        }
        snapshot = {
            "units": snapshot_units,
            "buildings": buildings,
            "cover_by_target": dict(battle.get("cover_by_target") or {}),
            "blockers": list(battle.get("blockers") or []),
            "hostiles": hostiles,
            "battle_id": battle_id,
        }
        lease_id = self.state.ids.new("lease")
        registry = EncounterRegistry()
        # Seed registry from durable leases index for exclusivity checks.
        for lid, lease in (self.state.leases or {}).items():
            if isinstance(lease, dict) and lease.get("state") == "ACTIVE":
                for eid in lease.get("entity_ids") or []:
                    registry.entity_index[str(eid)] = str(lid)
        try:
            lease = registry.grant(
                "battle",
                unit_ids,
                snapshot,
                lease_id,
                owner_session=str(envelope.session_id or ""),
            )
        except TypeValidationError as exc:
            return CommandResult(
                status="REJECTED",
                code="LEASE_CONFLICT",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback=str(exc),
            )
        record = {
            "lease_id": lease.lease_id,
            "kind": "battle",
            "battle_id": battle_id,
            "entity_ids": list(unit_ids),
            "version": lease.version,
            "state": "ACTIVE",
            "checkpoint": snapshot,
            "checkpoint_hash": lease.checkpoint_hash,
            "pending_destructions": [],
        }
        self.state.leases[lease_id] = record
        for uid in unit_ids:
            self.state.units[uid]["lease_id"] = lease_id
            self.state.units[uid]["lease_version"] = lease.version
        battle["state"] = "LOCAL"
        battle["lease_id"] = lease_id
        self.state.world_version += 1
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[{"kind": "battle_lease_opened", "lease_id": lease_id}],
            payload={"lease": record, "snapshot": snapshot},
            public_feedback="lease_opened",
        )

    def _handle_battle_checkpoint(self, envelope: CommandEnvelope) -> CommandResult:
        from sim.dmb.military.units import MilitaryService

        lease_id = str(envelope.payload.get("lease_id") or "")
        lease = (self.state.leases or {}).get(lease_id)
        if not isinstance(lease, dict) or lease.get("state") not in {"ACTIVE", "FREEZING"}:
            return CommandResult(
                status="REJECTED",
                code="NO_LEASE",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="no lease",
            )
        version = int(envelope.payload.get("version") or 0)
        base_hash = str(envelope.payload.get("base_checkpoint_hash") or "")
        if version and int(lease.get("version") or 0) != version:
            return CommandResult(
                status="REJECTED",
                code="STALE_CHECKPOINT",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="stale checkpoint",
            )
        if base_hash and str(lease.get("checkpoint_hash") or "") and base_hash != str(lease.get("checkpoint_hash")):
            return CommandResult(
                status="REJECTED",
                code="STALE_CHECKPOINT",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="stale checkpoint hash",
            )
        delta = envelope.payload.get("delta") or envelope.payload.get("checkpoint") or {}
        # Apply pending destructions from magic.
        for pending in list(lease.get("pending_destructions") or []):
            tid = str(pending.get("target_id") or "")
            units_delta = delta.setdefault("units", {})
            if tid in self.state.units:
                units_delta.setdefault(tid, {})
                units_delta[tid]["alive"] = False
                units_delta[tid]["current_health"] = 0
                units_delta[tid]["status"] = "dead"
        lease["pending_destructions"] = []
        applied = MilitaryService(self.state).receive_checkpoint(lease_id, delta)
        # Persist building damage if present.
        for bid, patch in (delta.get("buildings") or {}).items():
            building = self.state.buildings.get(bid)
            if building is None:
                continue
            for key in ("current_health", "health", "alive", "status"):
                if key in patch:
                    building[key] = patch[key]
        lease["checkpoint"] = delta
        lease["version"] = int(lease.get("version") or 0) + 1
        import hashlib
        import json

        lease["checkpoint_hash"] = hashlib.sha256(
            json.dumps(delta, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        self.state.world_version += 1
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[{"kind": "battle_checkpoint", "lease_id": lease_id}],
            payload={"lease": lease, "applied": applied},
            public_feedback="checkpoint",
        )

    def _handle_close_battle_lease(self, envelope: CommandEnvelope) -> CommandResult:
        from sim.dmb.military.offscreen import OffscreenBattleResolver

        lease_id = str(envelope.payload.get("lease_id") or "")
        reason = str(envelope.payload.get("reason") or "travel")
        lease = (self.state.leases or {}).pop(lease_id, None)
        if lease is None:
            return CommandResult(
                status="REJECTED",
                code="NO_LEASE",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="no lease",
            )
        # Final checkpoint commit if provided.
        final = envelope.payload.get("checkpoint") or lease.get("checkpoint") or {}
        if final.get("units"):
            from sim.dmb.military.units import MilitaryService

            MilitaryService(self.state).receive_checkpoint(lease_id, final)
        for uid in lease.get("entity_ids") or []:
            unit = self.state.units.get(uid)
            if unit is not None:
                unit["lease_id"] = None
        battle_id = str(lease.get("battle_id") or "")
        battle = (self.state.battles or {}).get(battle_id)
        outcome = None
        if reason == "travel" and battle is not None:
            # Offscreen continues from checkpoint; no global clock advance.
            snap = {
                "units": {
                    uid: dict(self.state.units[uid])
                    for uid in (battle.get("participants") or [])
                    if uid in self.state.units
                },
                "buildings": {
                    bid: dict(self.state.buildings[bid])
                    for bid in (battle.get("buildings") or [])
                    if bid in self.state.buildings
                },
                "cover_by_target": dict(battle.get("cover_by_target") or {}),
                "hostiles": battle.get("hostiles"),
            }
            outcome = OffscreenBattleResolver(self.state).resolve(snap)
            battle["state"] = "OFFSCREEN_RESOLVED"
            battle["last_outcome"] = outcome
        elif battle is not None:
            battle["state"] = "CLOSED"
        self.state.world_version += 1
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[{"kind": "battle_lease_closed", "lease_id": lease_id, "reason": reason}],
            payload={"lease_id": lease_id, "reason": reason, "outcome": outcome},
            public_feedback="lease_closed",
        )

    def _handle_start_hazard_duel(self, envelope: CommandEnvelope) -> CommandResult:
        from sim.dmb.adventure.duels import HazardDuelService

        cube_id = str(envelope.payload.get("cube_id") or "")
        out = HazardDuelService(self.state).begin(cube_id)
        if out.get("status") != "started":
            return CommandResult(
                status="REJECTED",
                code=str(out.get("reason") or "INVALID"),
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                payload=out,
                public_feedback=str(out.get("reason") or "rejected"),
            )
        self.state.world_version += 1
        public = out.get("public") or HazardDuelService.public_view(out.get("duel") or {})
        duel = out.get("duel") or {}
        # Never ship private checkpoint secrets beyond what the lease needs.
        safe_duel = {
            k: v
            for k, v in duel.items()
            if k not in {"mastermind", "checkpoint"}
        }
        safe_duel["has_checkpoint"] = bool(duel.get("checkpoint"))
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[{"kind": "hazard_duel_started", "cube_id": cube_id}],
            payload={"status": "started", "duel": safe_duel, "public": public},
            public_feedback="duel_started",
        )

    def _handle_hazard_duel_action(self, envelope: CommandEnvelope) -> CommandResult:
        """Legacy Mastermind step — only for kind=hazard_duel reference leases.

        Production Challenge uses retained GameBoard; Channel×3 shortcuts stay rejected.
        """
        from sim.dmb.adventure.mastermind import MastermindDuel

        duel_id = str(envelope.payload.get("duel_id") or "")
        action = str(envelope.payload.get("action") or "")
        duel = (self.state.leases or {}).get(duel_id)
        if not isinstance(duel, dict):
            return CommandResult(
                status="REJECTED",
                code="NO_DUEL",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="no duel",
            )
        if duel.get("kind") == "hazard_ward_duel":
            return CommandResult(
                status="REJECTED",
                code="USE_RETAINED_BOARD",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                payload={"reason": "use_game_board"},
                public_feedback="Retained GameBoard owns this duel; Guess panel removed",
            )
        if duel.get("kind") != "hazard_duel":
            return CommandResult(
                status="REJECTED",
                code="NO_DUEL",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="no duel",
            )
        if duel.get("resolved"):
            return CommandResult(
                status="REJECTED",
                code="ALREADY_RESOLVED",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                public_feedback="already resolved",
            )
        if action in {"channel", "falter"}:
            return CommandResult(
                status="REJECTED",
                code="FORBIDDEN_SHORTCUT",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                payload={"reason": "use_guess"},
                public_feedback="Mastermind guesses required; Channel shortcut removed",
            )
        if action == "resign":
            return self._handle_resolve_hazard_duel(
                CommandEnvelope(
                    protocol_version=envelope.protocol_version,
                    session_id=envelope.session_id,
                    world_id=envelope.world_id,
                    command_id=envelope.command_id,
                    expected_world_version=self.state.world_version,
                    kind="ResolveHazardDuel",
                    payload={"duel_id": duel_id, "success": False},
                )
            )
        if action == "guess":
            guess = envelope.payload.get("guess")
            if not isinstance(guess, list):
                guess = envelope.payload.get("colours")
            result = MastermindDuel.submit_guess(duel, guess if isinstance(guess, list) else [])
            if result.get("status") == "rejected":
                return CommandResult(
                    status="REJECTED",
                    code=str(result.get("reason") or "INVALID_GUESS"),
                    command_id=envelope.command_id,
                    world_version=self.state.world_version,
                    events=[],
                    payload=result,
                    public_feedback=str(result.get("reason") or "invalid guess"),
                )
            self.state.world_version += 1
            if result.get("outcome") == "success":
                return self._handle_resolve_hazard_duel(
                    CommandEnvelope(
                        protocol_version=envelope.protocol_version,
                        session_id=envelope.session_id,
                        world_id=envelope.world_id,
                        command_id=envelope.command_id,
                        expected_world_version=self.state.world_version,
                        kind="ResolveHazardDuel",
                        payload={"duel_id": duel_id, "success": True},
                    )
                )
            if result.get("outcome") in {"draw", "failure"}:
                return self._handle_resolve_hazard_duel(
                    CommandEnvelope(
                        protocol_version=envelope.protocol_version,
                        session_id=envelope.session_id,
                        world_id=envelope.world_id,
                        command_id=envelope.command_id,
                        expected_world_version=self.state.world_version,
                        kind="ResolveHazardDuel",
                        payload={"duel_id": duel_id, "success": False},
                    )
                )
            return CommandResult(
                status="ACCEPTED",
                code="OK",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[{"kind": "hazard_duel_guess", "feedback": result.get("feedback")}],
                payload=result,
                public_feedback="exact=%s colour=%s"
                % (
                    (result.get("feedback") or {}).get("exact"),
                    (result.get("feedback") or {}).get("colour_only"),
                ),
            )
        return CommandResult(
            status="REJECTED",
            code="UNKNOWN_ACTION",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[],
            public_feedback="unknown duel action",
        )

    def _handle_resolve_hazard_duel(self, envelope: CommandEnvelope) -> CommandResult:
        from sim.dmb.adventure.duels import HazardDuelService

        duel_id = str(envelope.payload.get("duel_id") or "")
        success = bool(envelope.payload.get("success"))
        out = HazardDuelService(self.state).resolve(
            duel_id, success=success, command_id=envelope.command_id
        )
        if out.get("status") in {"missing_duel"}:
            return CommandResult(
                status="REJECTED",
                code="NO_DUEL",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                payload=out,
                public_feedback="no duel",
            )
        if out.get("status") != "idempotent":
            self.state.world_version += 1
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[{"kind": "hazard_duel_resolved", "payload": out}],
            payload=out,
            public_feedback=str(out.get("status")),
        )

    def _handle_hazard_duel_checkpoint(self, envelope: CommandEnvelope) -> CommandResult:
        from sim.dmb.adventure.duels import HazardDuelService

        duel_id = str(envelope.payload.get("duel_id") or "")
        checkpoint = envelope.payload.get("checkpoint") or {}
        out = HazardDuelService(self.state).save_checkpoint(
            duel_id, checkpoint if isinstance(checkpoint, dict) else {}
        )
        if out.get("status") == "missing_duel":
            return CommandResult(
                status="REJECTED",
                code="NO_DUEL",
                command_id=envelope.command_id,
                world_version=self.state.world_version,
                events=[],
                payload=out,
                public_feedback="no duel",
            )
        if out.get("status") == "saved":
            self.state.world_version += 1
        return CommandResult(
            status="ACCEPTED",
            code="OK",
            command_id=envelope.command_id,
            world_version=self.state.world_version,
            events=[],
            payload=out,
            public_feedback=str(out.get("status")),
        )
