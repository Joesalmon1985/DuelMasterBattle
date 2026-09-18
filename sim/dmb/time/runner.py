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
    "5_active_decisions",
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
        elif stage == "5_active_decisions":
            payload.update(self._stage_active_decisions())
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

        before_nodes = {cid: str(c.get("current_node")) for cid, c in self.state.carts.items()}
        before_status = {cid: str(c.get("status")) for cid, c in self.state.carts.items()}
        moved = carts.advance_all(validate_edge=validate_edge)
        self._sync_fx_cargo_cart_person(before_nodes=before_nodes, before_status=before_status)
        self._maybe_queue_fx_construction(ledger)
        return {"moved": [m.get("id") for m in moved], "carts": moved}

    def _sync_fx_cargo_cart_person(
        self,
        *,
        before_nodes: dict[str, str] | None = None,
        before_status: dict[str, str] | None = None,
    ) -> None:
        from sim.dmb.presentation.journeys import (
            enqueue_committed_edge,
        )

        fx = self.state.board.get("fx_cargo") or {}
        cart_id = str(fx.get("cart_id") or "")
        person_id = str(fx.get("cart_person_id") or "")
        cart = self.state.carts.get(cart_id) if cart_id else None
        person = self.state.people.get(person_id) if person_id else None
        if not isinstance(cart, dict) or not isinstance(person, dict):
            return
        prev_node = (before_nodes or {}).get(cart_id) or str(person.get("node_id") or "")
        new_node = str(cart.get("current_node") or prev_node)
        status = str(cart.get("status") or "idle")
        prev_status = (before_status or {}).get(cart_id) or ""

        if status == "blocked":
            fx["delivery_status"] = "blocked_route"
            label = "Hauler Cart (blocked)"
            person["node_id"] = new_node
            # Attempted hop toward next route node.
            route = list(cart.get("route") or [])
            idx = int(cart.get("route_index", 0))
            nxt = str(route[idx + 1]) if idx + 1 < len(route) else new_node
            enqueue_committed_edge(self.state, cart_id, from_node=new_node, to_node=nxt, blocked=True)
        elif status in {"en_route", "assigned", "loaded"}:
            fx["delivery_status"] = "en_route"
            label = "Hauler Cart (travelling)"
            if prev_node and new_node and prev_node != new_node:
                enqueue_committed_edge(self.state, cart_id, from_node=prev_node, to_node=new_node)
            else:
                person["node_id"] = new_node
        elif status in {"arrived", "delivered"}:
            fx["delivery_status"] = "delivered"
            label = "Hauler Cart (delivered)"
            if prev_node and new_node and prev_node != new_node:
                enqueue_committed_edge(self.state, cart_id, from_node=prev_node, to_node=new_node)
            else:
                person["node_id"] = new_node
            if prev_status not in {"arrived", "delivered"} and status == "arrived":
                from sim.dmb.presentation.journeys import maybe_begin_unload_presentation

                maybe_begin_unload_presentation(self.state, cart_id)
        else:
            label = "Hauler Cart (idle)"
            person["node_id"] = new_node

        person["label"] = label
        person["display_name"] = label
        if person_id in self.state.knowledge:
            self.state.knowledge[person_id]["name"] = label

    def _maybe_queue_fx_construction(self, ledger) -> None:
        """After playable delivery lands, reserve a settlement order for completions."""
        fx = self.state.board.get("fx_cargo") or {}
        if not fx.get("construction_pending"):
            return
        cart_id = str(fx.get("cart_id") or "")
        cart = self.state.carts.get(cart_id) if cart_id else None
        if not isinstance(cart, dict) or cart.get("status") != "arrived":
            return
        staging_store = str(fx.get("staging_store") or "")
        n2 = str(fx.get("N2") or "")
        required = dict(fx.get("required") or {"timber": 1, "brick": 1, "wool": 1, "grain": 1})
        if not staging_store or not n2:
            return
        for good, qty in required.items():
            if ledger.available(staging_store, good) < qty:
                return
        from sim.dmb.construction.orders import ConstructionService

        order = ConstructionService(self.state, ledger=ledger).reserve_order(
            "settlement",
            faction_id="faction:1",
            store_id=staging_store,
            target_node=n2,
        )
        fx["construction_pending"] = False
        fx["delivery_status"] = "delivered"
        fx["construction_order_id"] = order.get("id")
        if order.get("status") == "ready":
            fx["construction_status"] = "ready"
        else:
            fx["construction_status"] = str(order.get("status") or "blocked")
            fx["construction_reason"] = order.get("reason")

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

    def _stage_active_decisions(self) -> dict[str, Any]:
        """Only the active seat may initiate construction/trade/diplomacy/military."""
        if self.interrupted:
            return {"skipped": True, "reason": "interrupted"}
        active = self.scheduler.active_seat()
        battle_results = self._resolve_pending_offscreen(active)
        if not active or active == "faction:player":
            return {"faction_id": active, "applied": [], "battles": battle_results}
        from sim.dmb.ai.policy import PolicyService

        policy = PolicyService(self.state)
        policy.assign_brain(active, "heuristic")
        record = policy.activate(active, decision_kind="seat")
        # Apply accepted military objectives without granting ownership on victory.
        applied_objectives = self._apply_military_commitments(active, record)
        return {
            "faction_id": active,
            "activation": record,
            "battles": battle_results,
            "military_objectives": applied_objectives,
        }

    def _resolve_pending_offscreen(self, active_faction: str | None) -> list[dict[str, Any]]:
        """Resolve disengaged battles offscreen; open local leases when player present."""
        from sim.dmb.military.offscreen import OffscreenBattleResolver

        results = []
        player_node = str((self.state.player or {}).get("node_id") or "")
        for battle_id, battle in list((getattr(self.state, "battles", {}) or {}).items()):
            if battle.get("state") not in {"PENDING", "OFFSCREEN", "ACTIVE"}:
                continue
            if battle.get("local_lease_id"):
                # Local lease owns resolution.
                continue
            node_id = str(battle.get("node_id") or "")
            if node_id == player_node and battle.get("prefer_local"):
                # Open local lease for correct participant units.
                participants = list(battle.get("participants") or [])
                lease_id = self.state.ids.new("lease")
                from sim.dmb.encounters.registry import EncounterRegistry

                # Persist lightweight lease marker on world; full registry may be session-scoped.
                snap = {
                    "units": {
                        uid: dict(self.state.units[uid])
                        for uid in participants
                        if uid in self.state.units
                    },
                    "node_id": node_id,
                }
                self.state.leases[lease_id] = {
                    "lease_id": lease_id,
                    "kind": "battle",
                    "entity_ids": participants,
                    "state": "ACTIVE",
                    "checkpoint": snap,
                }
                battle["local_lease_id"] = lease_id
                battle["state"] = "LOCAL"
                results.append({"battle_id": battle_id, "mode": "local_lease", "lease_id": lease_id})
                continue
            resolver = OffscreenBattleResolver(self.state)
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
                "entry_effective_health": dict(battle.get("entry_effective_health") or {}),
                "material_change_version": int(battle.get("material_change_version") or 0),
            }
            outcome = resolver.resolve(snap)
            resolver.commit_to_world(outcome, battle_id=battle_id)
            # Attacker victory may destroy a centre but never assigns ownership.
            if outcome.get("outcome") == "victory":
                for bid in battle.get("buildings") or []:
                    building = self.state.buildings.get(bid)
                    if building and not building.get("alive", True):
                        building["destroyed_by_battle"] = True
                        # Explicitly do not set faction_id to attacker.
            results.append(
                {
                    "battle_id": battle_id,
                    "mode": "offscreen",
                    "outcome": outcome.get("outcome"),
                    "ownership_transferred": False,
                }
            )
        return results

    def _apply_military_commitments(self, faction_id: str, record: dict[str, Any]) -> list[dict[str, Any]]:
        applied = []
        commitments = (self.state.factions.get(faction_id) or {}).get("commitments") or []
        for commitment in commitments[-5:]:
            if commitment.get("action_kind") != "military_objective":
                continue
            params = commitment.get("params") or {}
            fid = params.get("formation_id")
            formation = (getattr(self.state, "formations", {}) or {}).get(fid)
            if formation is None:
                continue
            formation["objective"] = params.get("objective")
            if params.get("objective") == "attack" and params.get("node_id"):
                # Movement happens via military_move candidates; record intent only.
                formation["objective_node"] = params.get("node_id")
            applied.append({"formation_id": fid, "objective": formation.get("objective")})
        return applied

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
            if stage in {
                "2_production",
                "3_logistics",
                "4_completions",
                "5_active_decisions",
            }:
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
            from sim.dmb.player.visits import VisitService

            VisitService(self.state).arrive(to_node, "travel", int(self.state.clock.get("turn", 0)))
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
        from sim.dmb.player.visits import VisitService

        VisitService(self.state).arrive(current_node, "wait", int(self.state.clock.get("turn", 0)))
        self._run_stages(arrival_handler=None)
        if self.interrupted:
            seat = {"round_complete": False, "interrupted": True, "draft": None}
            self.state.clock["draft"] = None
            self._discard_tech_draft_on_interrupt()
        else:
            seat = self.scheduler.finish_seat()
            seat = self._maybe_resolve_tech_draft(seat)
        self.state.clock["last_seat"] = {
            "round_complete": bool(seat.get("round_complete")),
            "active_faction_id": self.scheduler.active_seat(),
            "tech_draft": seat.get("tech_draft"),
            "tech_snapshot_pick_index": seat.get("tech_snapshot_pick_index"),
            "interrupted": bool(seat.get("interrupted") or self.interrupted),
        }
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
        if self.interrupted:
            self._discard_tech_draft_on_interrupt()
            seat = dict(seat)
            seat["tech_draft"] = None
            seat["draft_suppressed"] = True
            return seat
        draft = getattr(self.state, "tech_draft", None)
        if not isinstance(draft, dict) or not draft.get("active"):
            return seat
        from sim.dmb.ai.heuristic import HeuristicBrain
        from sim.dmb.technology.draft import DraftService

        svc = DraftService(self.state)
        snap = svc.collect_choices(
            {"turn": int(self.state.clock.get("turn", 0)), "round": int(self.state.clock.get("round", 0))}
        )
        brain = HeuristicBrain()
        choices: dict[str, str] = {}
        for faction_id, hand in snap["hands"].items():
            cands = [
                {
                    "id": card["id"],
                    "action_kind": "tech_pick",
                    "params": {"definition_id": card.get("definition_id")},
                }
                for card in hand
            ]
            if not cands:
                continue
            obs = {"own": {"vp": 0}, "public": {}, "faction_id": faction_id}
            choices[faction_id] = brain.choose(obs, cands)
        outcome = svc.resolve_round(choices)
        # Persist a human-readable last-pick map for economy/HUD inspection.
        picks = {}
        for receipt in outcome.get("acquired") or []:
            if not isinstance(receipt, dict):
                continue
            fid = str(receipt.get("faction_id") or "")
            defn = str(receipt.get("definition_id") or "")
            picks[fid] = {
                "card_id": receipt.get("instance_id") or receipt.get("card_id"),
                "definition_id": defn,
                "name": defn,
            }
        draft = getattr(self.state, "tech_draft", None)
        if isinstance(draft, dict):
            draft["last_picks"] = picks
            draft["last_pick_round"] = int(self.state.clock.get("round", 0))
            draft["last_pick_turn"] = int(self.state.clock.get("turn", 0))
            draft["last_resolution"] = {
                "pick_index": outcome.get("pick_index"),
                "picks": picks,
                "owned_counts": outcome.get("owned_counts"),
            }
        seat = dict(seat)
        seat["tech_draft"] = outcome
        seat["tech_snapshot_pick_index"] = snap.get("pick_index")
        seat["tech_picks"] = picks
        return seat

    def run_faction_round(self) -> dict[str, Any]:
        """Advance every scheduled faction seat once with production/logistics/decisions."""
        roster = list(self.state.clock.get("scheduled_faction_ids") or [])
        results = []
        for faction_id in roster:
            if self.interrupted:
                break
            self.interrupted = False
            self.scheduler.begin_turn("Seat")
            self.state.clock["active_faction_id"] = faction_id
            self.state.clock["completed_seats"] = [
                f for f in roster if roster.index(f) < roster.index(faction_id)
            ]
            self._run_stages(arrival_handler=None)
            if self.interrupted:
                seat = {"round_complete": False, "interrupted": True, "draft": None}
                self._discard_tech_draft_on_interrupt()
            else:
                seat = self.scheduler.finish_seat()
                seat = self._maybe_resolve_tech_draft(seat)
            results.append(
                {
                    "faction_id": faction_id,
                    "seat": seat,
                    "stages": list(self.stages_executed or []),
                }
            )
            if seat.get("round_complete") or self.interrupted:
                break
        return {
            "results": results,
            "round_complete": bool(self.state.clock.get("round_complete")),
            "interrupted": self.interrupted,
            "draft": self.state.clock.get("draft"),
        }

    def run_seats_round(self) -> dict[str, Any]:
        """Advance through every scheduled seat once; unfinished rounds yield no draft."""
        return self.run_faction_round()
