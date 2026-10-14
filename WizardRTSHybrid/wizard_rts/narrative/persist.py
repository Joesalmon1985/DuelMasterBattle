"""Wizard Mode save and load: the `HybridEnv` pickle shape plus the narrative version, written atomically, with the previous valid save kept.

    {"format": 2, "hash": world.state_hash(), "narrative_version": N, "world": world, "profile", "seed", "game_ms"}

Everything Wizard Mode keeps (the RTS world and factions, the wizard's pose and progress, people, links, quests, leases, pause tokens) is inside the
pickled world, so a load restores exactly what a save saw. Saving is a pure read of the world between two `advance` calls and never advances the
clock. The server never reads the wall clock: autosave is timed by the Godot client (plan section 12, R5).
"""

from __future__ import annotations

import os
import pickle
import re
from pathlib import Path
from typing import Any

from wizard_rts import narrative
from wizard_rts.narrative import config

SLOT_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
PROTOCOL = 5
REQUIRED = ("format", "hash", "narrative_version", "world")


class SaveError(Exception):
    """A save was refused or could not be read. `reason` is one of: bad_slot, missing, corrupt, format, newer_version, older_version, io."""

    def __init__(self, reason: str, detail: str = "", prev: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail
        self.prev = prev  # path of the previous valid save when one exists (offered to the player)


def save_format() -> int:
    from wizard_rts.sim_api import HybridEnv

    return int(HybridEnv.SAVE_FORMAT)  # the format number is the environment's: a bump there is noticed by test_wizard_save


def saves_dir(profile: str) -> Path:
    root = Path(os.environ.get("DMB_RUNS") or (Path.home() / "dmb_runs"))
    return root / "saves" / profile


def slot_path(profile: str, slot: str) -> Path:
    if not SLOT_RE.match(slot or ""):
        raise SaveError("bad_slot", f"slot names are 1 to 32 letters, digits, - or _ (got {slot!r})")
    return saves_dir(profile) / f"{slot}.pkl"


def prev_path(path: Path) -> Path:
    return path.with_name(path.name[: -len(".pkl")] + ".prev.pkl")


def _read(path: Path) -> dict[str, Any]:
    try:
        blob = path.read_bytes()
    except FileNotFoundError as exc:
        raise SaveError("missing", str(path)) from exc
    except OSError as exc:
        raise SaveError("io", str(exc)) from exc
    try:
        payload = pickle.loads(blob)
    except Exception as exc:  # a truncated or damaged pickle fails in many ways (EOFError, UnpicklingError, AttributeError ...)
        raise SaveError("corrupt", f"{type(exc).__name__}: {exc}") from exc
    if not isinstance(payload, dict) or any(k not in payload for k in REQUIRED):
        raise SaveError("corrupt", "not a Wizard Mode save")
    return payload


def _valid(path: Path) -> bool:
    try:
        _read(path)
        return True
    except SaveError:
        return False


# ------------------------------------------------------------------ save

def save_world(world: Any, path: Path | str) -> dict[str, Any]:
    """Write `world` to `path` atomically (tmp file, fsync, `os.replace`), keeping the previous valid save as `<slot>.prev.pkl`."""
    path = Path(path)
    game_ms = int(world.dmb.clock.get("game_ms", 0))
    digest = world.state_hash()
    payload = {"format": save_format(), "hash": digest, "narrative_version": config.version(), "world": world,
               "profile": world.profile, "seed": world.seed, "game_ms": game_ms}
    blob = pickle.dumps(payload, protocol=PROTOCOL)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        if path.exists() and _valid(path):  # only a good save becomes the fallback; a damaged one never replaces it
            os.replace(path, prev_path(path))
        os.replace(tmp, path)
    except OSError as exc:
        raise SaveError("io", str(exc)) from exc
    return {"path": str(path), "hash": digest, "game_ms": game_ms, "bytes": len(blob)}


# ------------------------------------------------------------------ load

MIGRATIONS: dict[int, Any] = {}  # narrative_version n -> function(payload) -> payload at n + 1 (none exist yet; the mechanism does)


def migrate(payload: dict[str, Any]) -> dict[str, Any]:
    v = int(payload["narrative_version"])
    while v < config.version():
        step = MIGRATIONS.get(v)
        if step is None:
            raise SaveError("older_version", f"save is narrative version {v}, the code is {config.version()} and has no migration")
        payload = step(payload)
        v += 1
        payload["narrative_version"] = v
    return payload


def load_world(path: Path | str) -> tuple[Any, dict[str, Any]]:
    """Read, verify and return (world, info). Refuses a damaged save (offering `.prev`), another format, or a newer narrative version.
    A world whose recomputed hash differs from the stored one still loads, flagged `recovered` and `hash_mismatch`."""
    path = Path(path)
    prev = prev_path(path)
    try:
        payload = _read(path)
    except SaveError as exc:
        if exc.reason in ("corrupt", "io") and _valid(prev):
            exc.prev = str(prev)
        raise
    if payload["format"] != save_format():
        raise SaveError("format", f"save format {payload['format']!r} is not {save_format()}: it was written by another version")
    if int(payload["narrative_version"]) > config.version():
        raise SaveError("newer_version", f"save is narrative version {payload['narrative_version']}, this code knows {config.version()}")
    payload = migrate(payload)
    world = payload["world"]
    narrative.enable(world)  # a save from a world that had no Wizard Mode state gains it here
    mismatch = world.state_hash() != payload["hash"]
    return world, {"path": str(path), "game_ms": int(payload.get("game_ms", 0)), "profile": payload.get("profile", world.profile),
                   "seed": payload.get("seed", world.seed), "hash": payload["hash"], "hash_mismatch": mismatch, "recovered": mismatch}
