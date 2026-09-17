"""Immutable versioned definition catalogue."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

from sim.dmb.core.types import TypeValidationError, validate_definition_id


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True, slots=True)
class Definition:
    id: str
    schema_version: int
    kind: str
    era_id: str
    name_key: str
    description_key: str
    asset_family_id: str
    tags: tuple[str, ...]
    fields: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "schema_version": self.schema_version,
            "kind": self.kind,
            "era_id": self.era_id,
            "name_key": self.name_key,
            "description_key": self.description_key,
            "asset_family_id": self.asset_family_id,
            "tags": list(self.tags),
            "fields": self.fields,
        }


class DefinitionCatalog:
    def __init__(self) -> None:
        self._by_kind: dict[str, dict[str, Definition]] = {}
        self._hash = ""

    def load(self, definitions: Iterable[dict[str, Any]]) -> None:
        by_kind: dict[str, dict[str, Definition]] = {}
        for raw in definitions:
            defn = self._parse(raw)
            bucket = by_kind.setdefault(defn.kind, {})
            if defn.id in bucket:
                raise TypeValidationError(f"duplicate definition id: {defn.id}")
            bucket[defn.id] = defn
        self.validate_all(by_kind)
        self._by_kind = by_kind
        self._hash = self.compute_hash(by_kind)

    @staticmethod
    def _parse(raw: dict[str, Any]) -> Definition:
        def_id = validate_definition_id(str(raw["id"]))
        fields = dict(raw.get("fields", {}))
        for key, value in fields.items():
            if key.endswith("_cost") and isinstance(value, (int, float)) and value < 0:
                raise TypeValidationError(f"negative cost forbidden: {def_id}.{key}")
        return Definition(
            id=def_id,
            schema_version=int(raw.get("schema_version", 1)),
            kind=str(raw["kind"]),
            era_id=str(raw.get("era_id", "all")),
            name_key=str(raw.get("name_key", def_id)),
            description_key=str(raw.get("description_key", def_id)),
            asset_family_id=str(raw.get("asset_family_id", "default")),
            tags=tuple(str(tag) for tag in raw.get("tags", [])),
            fields=fields,
        )

    @classmethod
    def validate_all(cls, by_kind: dict[str, dict[str, Definition]]) -> None:
        known = {defn.id for bucket in by_kind.values() for defn in bucket.values()}
        for bucket in by_kind.values():
            for defn in bucket.values():
                for key, value in defn.fields.items():
                    if key.endswith("_ref"):
                        if value not in known:
                            raise TypeValidationError(f"bad ref {value!r} in {defn.id}")

    @staticmethod
    def compute_hash(by_kind: dict[str, dict[str, Definition]]) -> str:
        payload = {
            kind: {def_id: defn.to_payload() for def_id, defn in sorted(bucket.items())}
            for kind, bucket in sorted(by_kind.items())
        }
        return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()

    def get(self, kind: str, def_id: str) -> Definition:
        try:
            return self._by_kind[kind][def_id]
        except KeyError as exc:
            raise TypeValidationError(f"missing definition {kind}/{def_id}") from exc

    @property
    def catalog_hash(self) -> str:
        return self._hash

    def all_payloads(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for kind in sorted(self._by_kind):
            for def_id in sorted(self._by_kind[kind]):
                out.append(self._by_kind[kind][def_id].to_payload())
        return out
