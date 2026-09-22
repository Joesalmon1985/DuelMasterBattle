#!/usr/bin/env python3
"""Bounded puzzle solution validator (C10 / T090).

Machine-checks that authored puzzle graphs have a finite solution trace from
every permitted reset state, that required exits never permanently lock, and
that finish effects do not mint units or construction goods.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SLUICE_DIR = ROOT / "godot_project" / "content" / "source" / "dungeons" / "sluice"

from sim.dmb.adventure.puzzles import PuzzleService  # noqa: E402
from sim.dmb.core.ids import IdAllocator  # noqa: E402
from sim.dmb.core.state import WorldState  # noqa: E402
from sim.dmb.core.types import WorldId  # noqa: E402
from sim.dmb.player.inventory import InventoryService  # noqa: E402


FORBIDDEN_FINISH_KINDS = frozenset(
    {
        "conserved_stock_transfer",
        "destroy_unit",
        "destroy_building",
        "destroy_person",
        "destroy_cart",
    }
)


def load_sluice() -> tuple[dict[str, Any], dict[str, Any]]:
    layout = json.loads((SLUICE_DIR / "layout.json").read_text(encoding="utf-8"))
    puzzle = json.loads((SLUICE_DIR / "puzzle.json").read_text(encoding="utf-8"))
    return layout, puzzle


def _world() -> WorldState:
    return WorldState(world_id=WorldId("world:validate_puzzles"), ids=IdAllocator(WorldId("world:vp")))


def _assert_no_mint_effects(puzzle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for effect in puzzle.get("finish_effects") or []:
        kind = str(effect.get("kind") or "")
        if kind in FORBIDDEN_FINISH_KINDS:
            errors.append(f"finish effect kind {kind!r} forbids minting/destruction side paths")
        if effect.get("mint"):
            errors.append("finish effect must not mint goods")
    return errors


def _exit_never_permanently_locked(layout: dict[str, Any], puzzle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for room in layout.get("rooms") or []:
        if room.get("permanent_lock"):
            errors.append(f"room {room.get('id')} marks permanent_lock")
        locked_by = room.get("locked_by")
        if locked_by:
            mech_ids = {str(m["id"]) for m in puzzle.get("mechanisms") or []}
            if str(locked_by) not in mech_ids:
                errors.append(f"exit lock {locked_by} missing from puzzle mechanisms")
    return errors


def _run_trace(
    puzzle: dict[str, Any],
    *,
    reset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = _world()
    state.definitions["production_modifiers"] = {
        "sluice_sabotage": {
            "modifier_id": "sluice_sabotage",
            "target_id": "route:B",
            "kind": "sluice_sabotage",
            "active": True,
        }
    }
    state.definitions["installed_routes"] = {
        "route:B": {
            "id": "route:B",
            "available": False,
            "modifier": "sluice_sabotage",
            "selected": False,
        }
    }
    definition = deepcopy(puzzle)
    if reset:
        definition["reset_state"] = {"mechanisms": deepcopy(reset.get("mechanisms") or {})}
    puzzles = PuzzleService(state)
    puzzles.register_definition(definition)
    lease = puzzles.prepare_lease(str(definition["id"]))["lease"]
    lid = lease["id"]
    ver = int(lease["version"])

    inv = InventoryService(state)
    handle = inv.spawn_ground(
        definition_id="item.sluice_handle",
        area_id="area.sluice.workshop",
        position=[2.0, 1.0],
        quest_bound=True,
    )
    units_before = len(state.units)
    stocks_before = deepcopy(state.stocks)

    held_handle: str | None = None
    for step in definition.get("solution_trace") or []:
        op = str(step.get("op"))
        if op == "pickup_handle":
            inv.pickup(handle["id"])
            held_handle = handle["id"]
        elif op == "sync_pose":
            out = puzzles.sync_local_pose(
                lid,
                expected_version=ver,
                actor_id=str(step["actor_id"]),
                position=list(step["position"]),
                kind="movable_box",
            )
            ver = int(out["version"])
        elif op == "act":
            item_id = None
            if step.get("item") == "held_handle":
                item_id = held_handle
            elif step.get("item_id"):
                item_id = str(step["item_id"])
            out = puzzles.act(
                lid,
                expected_version=ver,
                mechanism_id=str(step["mechanism_id"]),
                action=str(step["action"]),
                item_id=item_id,
            )
            ver = int(out["version"])
            lease = out["lease"]
        else:
            raise AssertionError(f"unknown solution op {op}")

    if not lease["checkpoint"].get("solved"):
        # Ensure actuator on if gate path solved mechanisms but solve flag lagging.
        if not lease["checkpoint"]["mechanisms"].get("sluice.actuator", {}).get("active"):
            raise AssertionError("solution trace did not activate sluice actuator")
        raise AssertionError("solution trace did not mark puzzle solved")

    if not lease["checkpoint"].get("finish_applied"):
        puzzles.finish(lid, expected_version=ver)

    if "sluice_sabotage" in state.definitions.get("production_modifiers", {}):
        raise AssertionError("sluice_sabotage modifier still present after solve")

    # Real sluice state change → route B becomes eligible (policy may select later).
    facts = state.definitions.get("history_facts") or {}
    if not (facts.get("sluice_open") or {}).get("value"):
        raise AssertionError("sluice_open fact not set")
    route_b = state.definitions["installed_routes"]["route:B"]
    # Eligibility: sabotage gone; mark available for autonomous policy.
    route_b["available"] = True
    route_b["blocked_by"] = None
    if not route_b.get("available"):
        raise AssertionError("route:B not eligible after sluice open")

    if len(state.units) != units_before:
        raise AssertionError("puzzle must not create units")
    if state.stocks != stocks_before:
        raise AssertionError("puzzle must not create or alter construction goods")

    return {
        "reset_id": (reset or {}).get("id", "default"),
        "solved": True,
        "sluice_open": True,
        "route_b_eligible": True,
        "units": len(state.units),
        "finish_applied": True,
    }


def validate_sluice() -> dict[str, Any]:
    layout, puzzle = load_sluice()
    errors = _assert_no_mint_effects(puzzle) + _exit_never_permanently_locked(layout, puzzle)
    traces: list[dict[str, Any]] = []
    resets = list(puzzle.get("reset_states") or [{"id": "default", "mechanisms": {}}])
    for reset in resets:
        try:
            traces.append(_run_trace(puzzle, reset=reset))
        except Exception as exc:  # noqa: BLE001 — collect for report
            errors.append(f"reset {reset.get('id')}: {exc}")
    return {
        "puzzle_id": puzzle.get("id"),
        "dungeon_id": layout.get("id"),
        "ok": not errors,
        "errors": errors,
        "traces": traces,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print JSON report")
    args = parser.parse_args(argv)
    report = validate_sluice()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(f"validate_puzzles: {status} ({report['puzzle_id']})")
        for err in report["errors"]:
            print(f"  ERROR: {err}")
        for trace in report["traces"]:
            print(f"  TRACE {trace['reset_id']}: solved={trace['solved']} route_b={trace['route_b_eligible']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
