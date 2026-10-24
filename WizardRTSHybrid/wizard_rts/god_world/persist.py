"""God World saves: JSON under `DMB_RUNS/god_world/saves/` (never the wizard campaign's folder), written atomically with a `.prev` twin.
A save of another profile or schema is rejected with a clear message rather than half-loaded."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .world import GodWorld


class SaveError(RuntimeError):
    pass


def saves_dir() -> Path:
    root = os.environ.get("DMB_RUNS") or str(Path.home() / "dmb_runs")
    return Path(root) / "god_world" / "saves"


def slot_path(slot: str = "auto") -> Path:
    if slot not in ("auto", "manual", "quit", "boundary", "final", "age_started"):
        raise SaveError(f"unknown slot {slot}")
    return saves_dir() / f"god_world.{slot}.json"


def save_world(world: GodWorld, slot: str = "auto", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    path = slot_path(slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"kind": "god_world_save", "saved_at": time.time(), "world": world.to_dict(), "viewer": dict(extra or {})}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":"), default=str), encoding="utf-8")
    if path.exists():
        try:
            os.replace(path, path.with_suffix(".json.prev"))
        except OSError:
            pass
    os.replace(tmp, path)
    return {"status": "ok", "path": str(path), "slot": slot, "game_ms": int(world.game_ms), "age": int(world.age)}


def load_world(path: Path) -> tuple[GodWorld, dict[str, Any]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SaveError(f"cannot read {path}: {exc}") from exc
    if payload.get("kind") != "god_world_save" or "world" not in payload:
        raise SaveError(f"{path} is not a God World save")
    try:
        world = GodWorld.from_dict(payload["world"])
    except (ValueError, KeyError, TypeError) as exc:
        raise SaveError(f"{path}: unsupported or damaged save: {exc}") from exc
    return world, {"path": str(path), "saved_at": payload.get("saved_at"), "viewer": payload.get("viewer", {})}


def latest() -> Path | None:
    best: tuple[float, Path] | None = None
    for slot in ("quit", "auto", "manual", "age_started", "boundary", "final"):
        p = slot_path(slot)
        if p.exists():
            m = p.stat().st_mtime
            if best is None or m > best[0]:
                best = (m, p)
    return best[1] if best else None


def archive_all(stamp: str | None = None) -> list[str]:
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    out = []
    folder = saves_dir()
    if not folder.exists():
        return out
    for p in sorted(folder.glob("god_world.*.json")) + sorted(folder.glob("god_world.*.prev")):
        if ".retired-" in p.name:
            continue
        target = p.with_name(f"{p.stem}.retired-{stamp}{p.suffix}")
        try:
            os.replace(p, target)
            out.append(str(target))
        except OSError:
            pass
    return out
