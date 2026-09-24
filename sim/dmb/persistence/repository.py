"""Versioned atomic save repository."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import TypeValidationError
from sim.dmb.core.world import WorldSim
from sim.dmb.persistence.migrate import SCHEMA_VERSION, migrate_world_dict


SUPPORTED_SCHEMA = SCHEMA_VERSION
LEGACY_READABLE = {1, SCHEMA_VERSION}


@dataclass
class SaveRepository:
    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def slot_path(self, slot: str) -> Path:
        safe = "".join(ch for ch in slot if ch.isalnum() or ch in ("-", "_"))
        if not safe:
            raise TypeValidationError("invalid slot")
        return self.root / f"{safe}.json"

    def backup_path(self, slot: str) -> Path:
        return self.root / f"{slot}.previous.json"

    def write(self, slot: str, snapshot: dict[str, Any]) -> Path:
        path = self.slot_path(slot)
        existing = path.read_text(encoding="utf-8") if path.is_file() else None
        try:
            if int(snapshot.get("schema_version", -1)) != SUPPORTED_SCHEMA:
                raise TypeValidationError("unsupported save schema")
            world = snapshot.get("world", {})
            if world.get("legacy_godot_world_tick_enabled") or world.get("legacy_godot_world_save_enabled"):
                raise TypeValidationError("refusing save that enables legacy Godot writers")
            # Validate by round-tripping world state before touching the slot.
            try:
                WorldState.from_dict(world)
            except Exception as exc:  # noqa: BLE001
                raise TypeValidationError(f"invalid world payload: {exc}") from exc
            temporary = path.with_suffix(".tmp")
            payload = dict(snapshot)
            payload["content_hash"] = self.compute_content_hash(payload)
            temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if path.exists():
                backup = self.backup_path(slot)
                os.replace(path, backup)
            os.replace(temporary, path)
            return path
        except Exception:
            # Corrupt/unsupported candidates never replace a good slot or backup.
            if existing is not None and (not path.is_file() or path.read_text(encoding="utf-8") != existing):
                path.write_text(existing, encoding="utf-8")
            raise

    def read(self, slot: str) -> dict[str, Any]:
        path = self.slot_path(slot)
        if not path.is_file():
            raise TypeValidationError(f"missing save slot {slot}")
        raw = path.read_text(encoding="utf-8")
        try:
            payload = json.loads(raw)
            return self._normalize_payload(payload)
        except (json.JSONDecodeError, TypeValidationError, KeyError, TypeError) as exc:
            backup = self.backup_path(slot)
            if backup.is_file():
                try:
                    payload = json.loads(backup.read_text(encoding="utf-8"))
                    restored = self._normalize_payload(payload)
                    restored["_recovery"] = {
                        "restored_from_backup": True,
                        "slot": slot,
                        "message": (
                            "Primary save was corrupt or mismatched; "
                            "restored previous backup without deleting prototype files."
                        ),
                        "cause": str(exc),
                    }
                    return restored
                except (json.JSONDecodeError, TypeValidationError, KeyError, TypeError) as backup_exc:
                    raise TypeValidationError(
                        f"corrupt save and backup also unusable: {backup_exc}"
                    ) from backup_exc
            raise TypeValidationError(f"corrupt save and no backup: {exc}") from exc

    @staticmethod
    def compute_content_hash(snapshot: dict[str, Any]) -> str:
        """Hash payload body excluding the content_hash field itself."""
        body = {key: value for key, value in snapshot.items() if key != "content_hash"}
        return hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        version = int(payload.get("schema_version", -1))
        if version not in LEGACY_READABLE:
            raise TypeValidationError("unsupported-version")
        stored_hash = payload.get("content_hash")
        if stored_hash is not None:
            expected = self.compute_content_hash(payload)
            if stored_hash != expected:
                raise TypeValidationError("content hash mismatch — refusing silent load")
        world = payload.get("world")
        if not isinstance(world, dict):
            raise TypeValidationError("missing world")
        if version < SUPPORTED_SCHEMA:
            world = migrate_world_dict(world, from_schema=version)
            payload = dict(payload)
            payload["world"] = world
            payload["schema_version"] = SUPPORTED_SCHEMA
        WorldState.from_dict(payload["world"])
        return payload

    def load_world(self, slot: str) -> WorldSim:
        payload = self.read(slot)
        state = WorldState.from_dict(payload["world"])
        sim = WorldSim(state=state)
        if "events" in payload:
            from sim.dmb.core.events import EventJournal

            sim.events = EventJournal.from_dict(payload["events"])
        if "replay" in payload:
            from sim.dmb.core.replay import ReplayLog

            sim.replay = ReplayLog.from_dict(payload["replay"])
        return sim
