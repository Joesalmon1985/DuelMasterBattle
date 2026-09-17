"""Technology card catalogue and prerequisite graph validation (C12 / T039)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sim.dmb.core.types import TypeValidationError, validate_definition_id

CONTENT_ROOT = Path(__file__).resolve().parents[3] / "godot_project" / "content" / "source"
TECHNOLOGY_DIR = CONTENT_ROOT / "technology"

# MVP eras for baseline technology (Modern/Future arrive in later content tasks).
MVP_ERAS = ("prehistoric", "historic")

EFFECT_KINDS = (
    "primary_flow",
    "processor_cap",
    "factory_ceiling",
    "cart_capacity",
    "unit_health",
    "unit_attack",
)

# Later-era predecessor pairs from the previous era's matching effect kinds.
PREDECESSOR_PAIRS: dict[str, tuple[str, str]] = {
    "primary_flow": ("primary_flow", "processor_cap"),
    "processor_cap": ("processor_cap", "factory_ceiling"),
    "factory_ceiling": ("factory_ceiling", "primary_flow"),
    "cart_capacity": ("cart_capacity", "primary_flow"),
    "unit_health": ("unit_health", "unit_attack"),
    "unit_attack": ("unit_attack", "unit_health"),
}

DEFAULT_MAX_STACKS = 3
PERCENT_BONUS = 0.10
CART_CAPACITY_BONUS = 1


@dataclass(frozen=True, slots=True)
class TechDef:
    id: str
    era: str
    effect_kind: str
    effect_value: float
    allowed_predecessor_ids: tuple[str, ...]
    prerequisite_mode: str
    compatibility_scope: str
    repeatable: bool
    max_stacks: int
    pool_weight: int
    name_key: str
    description_key: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "schema_version": 1,
            "kind": "technology",
            "era_id": self.era,
            "name_key": self.name_key,
            "description_key": self.description_key,
            "fields": {
                "effect_kind": self.effect_kind,
                "effect_value": self.effect_value,
                "allowed_predecessor_ids": list(self.allowed_predecessor_ids),
                "prerequisite_mode": self.prerequisite_mode,
                "compatibility_scope": self.compatibility_scope,
                "repeatable": self.repeatable,
                "max_stacks": self.max_stacks,
                "pool_weight": self.pool_weight,
            },
        }


def _scope_for(effect_kind: str) -> str:
    if effect_kind in {"unit_health", "unit_attack"}:
        return "unit_era"
    return "logistics"


def _effect_value(effect_kind: str) -> float:
    if effect_kind == "cart_capacity":
        return float(CART_CAPACITY_BONUS)
    return float(PERCENT_BONUS)


def tech_id(era: str, effect_kind: str) -> str:
    return f"tech.{era}.{effect_kind}"


def build_baseline_tech_defs(eras: Iterable[str] = MVP_ERAS) -> list[TechDef]:
    era_list = list(eras)
    if not era_list:
        raise TypeValidationError("at least one era required")
    defs: list[TechDef] = []
    for era_index, era in enumerate(era_list):
        for effect_kind in EFFECT_KINDS:
            predecessors: tuple[str, ...] = ()
            if era_index == 0:
                predecessors = ()
            else:
                prev_era = era_list[era_index - 1]
                left, right = PREDECESSOR_PAIRS[effect_kind]
                predecessors = (tech_id(prev_era, left), tech_id(prev_era, right))
            defs.append(
                TechDef(
                    id=tech_id(era, effect_kind),
                    era=era,
                    effect_kind=effect_kind,
                    effect_value=_effect_value(effect_kind),
                    allowed_predecessor_ids=predecessors,
                    prerequisite_mode="any_previously_activated",
                    compatibility_scope=_scope_for(effect_kind),
                    repeatable=True,
                    max_stacks=DEFAULT_MAX_STACKS,
                    pool_weight=1,
                    name_key=f"tech.{era}.{effect_kind}.name",
                    description_key=f"tech.{era}.{effect_kind}.desc",
                )
            )
    return defs


def write_baseline_content(directory: Path | None = None, eras: Iterable[str] = MVP_ERAS) -> Path:
    """Materialise baseline JSON under content/source/technology/."""
    root = directory or TECHNOLOGY_DIR
    root.mkdir(parents=True, exist_ok=True)
    by_era: dict[str, list[dict[str, Any]]] = {}
    for defn in build_baseline_tech_defs(eras):
        by_era.setdefault(defn.era, []).append(defn.to_payload())
    for era, payloads in by_era.items():
        path = root / f"{era}.json"
        path.write_text(json.dumps(payloads, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return root


def load_technology_definitions(directory: Path | None = None) -> dict[str, dict[str, Any]]:
    root = directory or TECHNOLOGY_DIR
    by_id: dict[str, dict[str, Any]] = {}
    if not root.exists():
        return by_id
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload if isinstance(payload, list) else [payload]
        for raw in items:
            def_id = str(raw["id"])
            if def_id in by_id:
                raise TypeValidationError(f"duplicate technology id: {def_id}")
            by_id[def_id] = dict(raw)
    return by_id


def parse_tech_def(raw: dict[str, Any]) -> TechDef:
    def_id = validate_definition_id(str(raw["id"]))
    fields = dict(raw.get("fields", {}))
    era = str(raw.get("era_id") or fields.get("era") or "")
    if not era:
        raise TypeValidationError(f"technology {def_id} missing era")
    effect_kind = str(fields.get("effect_kind", ""))
    if effect_kind not in EFFECT_KINDS:
        raise TypeValidationError(f"unknown effect_kind {effect_kind!r} on {def_id}")
    predecessors = tuple(str(item) for item in fields.get("allowed_predecessor_ids", []))
    mode = str(fields.get("prerequisite_mode", "any_previously_activated"))
    if mode != "any_previously_activated":
        raise TypeValidationError(f"unsupported prerequisite_mode {mode!r} on {def_id}")
    scope = str(fields.get("compatibility_scope", _scope_for(effect_kind)))
    return TechDef(
        id=def_id,
        era=era,
        effect_kind=effect_kind,
        effect_value=float(fields.get("effect_value", _effect_value(effect_kind))),
        allowed_predecessor_ids=predecessors,
        prerequisite_mode=mode,
        compatibility_scope=scope,
        repeatable=bool(fields.get("repeatable", True)),
        max_stacks=int(fields.get("max_stacks", DEFAULT_MAX_STACKS)),
        pool_weight=int(fields.get("pool_weight", 1)),
        name_key=str(raw.get("name_key", def_id)),
        description_key=str(raw.get("description_key", def_id)),
    )


class TechnologyCatalog:
    """Loads TechDef records and validates references / activation DAG."""

    def __init__(self) -> None:
        self._by_id: dict[str, TechDef] = {}

    def load(self, definitions: Iterable[dict[str, Any]] | None = None) -> None:
        if definitions is None:
            raw = load_technology_definitions()
            definitions = list(raw.values())
        by_id: dict[str, TechDef] = {}
        for raw in definitions:
            defn = parse_tech_def(raw)
            if defn.id in by_id:
                raise TypeValidationError(f"duplicate technology id: {defn.id}")
            by_id[defn.id] = defn
        self.validate(by_id)
        self._by_id = by_id

    @staticmethod
    def validate(by_id: dict[str, TechDef]) -> None:
        for defn in by_id.values():
            for pred in defn.allowed_predecessor_ids:
                if pred not in by_id:
                    raise TypeValidationError(
                        f"missing predecessor {pred!r} referenced by {defn.id}"
                    )
        # Activation edges: card -> each allowed predecessor (must activate after them).
        # Cycle detection over the predecessor dependency graph.
        visiting: set[str] = set()
        visited: set[str] = set()

        def dfs(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                raise TypeValidationError(f"technology prerequisite cycle involving {node}")
            visiting.add(node)
            for pred in by_id[node].allowed_predecessor_ids:
                dfs(pred)
            visiting.remove(node)
            visited.add(node)

        for tech_id_key in by_id:
            dfs(tech_id_key)

        # Baseline reachability: every MVP card is either prereq-free or reachable
        # via at least one predecessor path from a prereq-free prehistoric card.
        reachable = {tid for tid, defn in by_id.items() if not defn.allowed_predecessor_ids}
        changed = True
        while changed:
            changed = False
            for tid, defn in by_id.items():
                if tid in reachable:
                    continue
                if any(pred in reachable for pred in defn.allowed_predecessor_ids):
                    reachable.add(tid)
                    changed = True
        missing = sorted(set(by_id) - reachable)
        if missing:
            raise TypeValidationError(f"unreachable technology definitions: {missing}")

        # Baseline buildings/routes must work without luck-dependent tech —
        # i.e. no card is marked as a hard requirement for baseline capability.
        for defn in by_id.values():
            if defn.compatibility_scope not in {"logistics", "unit_era"}:
                raise TypeValidationError(
                    f"invalid compatibility_scope {defn.compatibility_scope!r} on {defn.id}"
                )

    def get(self, tech_def_id: str) -> TechDef:
        try:
            return self._by_id[tech_def_id]
        except KeyError as exc:
            raise TypeValidationError(f"missing technology {tech_def_id}") from exc

    def by_era(self, era: str) -> list[TechDef]:
        return [defn for defn in self._by_id.values() if defn.era == era]

    def all(self) -> list[TechDef]:
        return list(self._by_id.values())

    def pool_for_era(self, era: str) -> list[TechDef]:
        cards = self.by_era(era)
        if len(cards) != 6:
            raise TypeValidationError(f"era {era} must have exactly 6 baseline cards, got {len(cards)}")
        return sorted(cards, key=lambda d: d.id)

    @property
    def ids(self) -> set[str]:
        return set(self._by_id)
