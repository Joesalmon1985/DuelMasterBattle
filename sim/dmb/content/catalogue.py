"""Full four-era industrial resource and recipe catalogue (C13 / T115).

Loads the compiled 48-raw / 240-recipe packs and exposes era-filtered views.
Services remain nonstorable. Workbook descriptive roles stay metadata-only.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

from sim.dmb.core.types import TypeValidationError

ROOT = Path(__file__).resolve().parents[3]
CONTENT = ROOT / "godot_project" / "content" / "source"
RESOURCES_PATH = CONTENT / "resources" / "catalog.json"
RECIPES_PATH = CONTENT / "recipes" / "full.json"
CULTURE_PATH = CONTENT / "recipes" / "culture_access.json"
MANIFEST_PATH = ROOT / "godot_project" / "content" / "manifests" / "full.json"

ERAS = ("prehistoric", "historic", "modern", "future")
RECIPES_PER_ERA = 60
RAW_FREQUENCY = 10
RAW_COUNT = 48
RECIPE_COUNT = 240


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise TypeValidationError(f"missing catalogue file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class CatalogueSnapshot:
    resources: tuple[dict[str, Any], ...]
    recipes: tuple[dict[str, Any], ...]
    culture_access: Mapping[str, tuple[str, ...]]
    aliases: Mapping[str, str]
    resource_by_id: Mapping[str, dict[str, Any]] = field(repr=False)
    recipe_by_id: Mapping[str, dict[str, Any]] = field(repr=False)

    def recipes_for_era(
        self,
        era: str,
        *,
        mvp_only: bool = False,
        military_supply_only: bool = False,
    ) -> list[dict[str, Any]]:
        era_key = str(era).strip().lower()
        out: list[dict[str, Any]] = []
        for recipe in self.recipes:
            if str(recipe.get("era") or "").lower() != era_key:
                continue
            if mvp_only and not recipe.get("mvp_subset"):
                continue
            if military_supply_only and not recipe.get("baseline_military_supply", True):
                continue
            out.append(dict(recipe))
        return out

    def resources_for_era(self, era: str) -> list[dict[str, Any]]:
        era_key = str(era).strip().lower()
        return [dict(r) for r in self.resources if str(r.get("era") or "").lower() == era_key]

    def culture_recipe_ids(self, era: str) -> tuple[str, ...]:
        return tuple(self.culture_access.get(str(era).strip().lower(), ()))


class FullCatalogue:
    """Immutable runtime view of the full industrial catalogue."""

    def __init__(self, snapshot: CatalogueSnapshot) -> None:
        self._snapshot = snapshot

    @property
    def snapshot(self) -> CatalogueSnapshot:
        return self._snapshot

    @classmethod
    def load(
        cls,
        *,
        resources_path: Path | None = None,
        recipes_path: Path | None = None,
        culture_path: Path | None = None,
    ) -> "FullCatalogue":
        resources_payload = _load_json(resources_path or RESOURCES_PATH)
        recipes_payload = _load_json(recipes_path or RECIPES_PATH)
        culture_payload = _load_json(culture_path or CULTURE_PATH)
        resources = [dict(r) for r in resources_payload.get("resources") or []]
        recipes = [dict(r) for r in recipes_payload.get("recipes") or []]
        access_raw = culture_payload.get("access") or {}
        culture_access = {
            str(era): tuple(str(rid) for rid in (ids or []))
            for era, ids in access_raw.items()
        }
        aliases = {
            str(k): str(v) for k, v in (resources_payload.get("aliases") or {}).items()
        }
        snapshot = CatalogueSnapshot(
            resources=tuple(resources),
            recipes=tuple(recipes),
            culture_access=culture_access,
            aliases=aliases,
            resource_by_id={str(r["id"]): r for r in resources},
            recipe_by_id={str(r["id"]): r for r in recipes},
        )
        catalogue = cls(snapshot)
        catalogue.validate()
        return catalogue

    def validate(self) -> None:
        snap = self._snapshot
        if len(snap.resources) != RAW_COUNT:
            raise TypeValidationError(f"expected {RAW_COUNT} resources, got {len(snap.resources)}")
        if len(snap.resource_by_id) != RAW_COUNT:
            raise TypeValidationError("duplicate industrial resource ids")
        if len(snap.recipes) != RECIPE_COUNT:
            raise TypeValidationError(f"expected {RECIPE_COUNT} recipes, got {len(snap.recipes)}")
        if len(snap.recipe_by_id) != RECIPE_COUNT:
            raise TypeValidationError("duplicate recipe ids")

        for resource in snap.resources:
            rid = str(resource.get("id") or "")
            if not rid.startswith("ind."):
                raise TypeValidationError(f"bad resource id namespace: {rid}")
            if resource.get("namespace") == "industrial_service" and resource.get("storable", True):
                raise TypeValidationError(f"service must be nonstorable: {rid}")
            if resource.get("namespace") == "industrial_material" and not resource.get("storable", False):
                # Materials are storable; services are the exception.
                raise TypeValidationError(f"material must be storable: {rid}")

        for era in ERAS:
            era_recipes = self.recipes_for_era(era)
            if len(era_recipes) != RECIPES_PER_ERA:
                raise TypeValidationError(
                    f"{era}: expected {RECIPES_PER_ERA} recipes, got {len(era_recipes)}"
                )
            processors = {r["processor_id"] for r in era_recipes}
            outputs = {r["output_id"] for r in era_recipes}
            pairs = {(r["input_a_id"], r["input_b_id"]) for r in era_recipes}
            if len(processors) != RECIPES_PER_ERA or len(outputs) != RECIPES_PER_ERA:
                raise TypeValidationError(f"{era}: processor/output ids must be unique")
            if len(pairs) != RECIPES_PER_ERA:
                raise TypeValidationError(f"{era}: expected {RECIPES_PER_ERA} unique input pairs")

            frequency = Counter(
                rid
                for recipe in era_recipes
                for rid in (recipe["input_a_id"], recipe["input_b_id"])
            )
            if set(frequency.values()) != {RAW_FREQUENCY}:
                raise TypeValidationError(f"{era}: each raw must appear exactly {RAW_FREQUENCY} times")

            for recipe in era_recipes:
                if list(recipe.get("input_quantities") or []) != [1, 1]:
                    raise TypeValidationError(f"{recipe['id']}: inputs must be 1:1")
                if not recipe.get("baseline_military_supply", False):
                    raise TypeValidationError(f"{recipe['id']}: missing military-supply compatibility")
                if "source_gameplay_role_metadata_only" not in recipe:
                    raise TypeValidationError(f"{recipe['id']}: workbook role must stay metadata-only")
                if "sink" in recipe or "population_cost" in recipe:
                    raise TypeValidationError(f"{recipe['id']}: workbook role leaked into mechanics")
                a = snap.resource_by_id.get(str(recipe["input_a_id"]))
                b = snap.resource_by_id.get(str(recipe["input_b_id"]))
                if a is None or b is None:
                    raise TypeValidationError(f"{recipe['id']}: unknown input resource")
                if a.get("terrain") == b.get("terrain"):
                    raise TypeValidationError(f"{recipe['id']}: pair must cross terrains")

            culture_ids = set(snap.culture_access.get(era, ()))
            recipe_ids = {r["id"] for r in era_recipes}
            if culture_ids != recipe_ids:
                raise TypeValidationError(f"{era}: culture access must include all {RECIPES_PER_ERA} recipes")

    def recipes_for_era(
        self,
        era: str,
        *,
        mvp_only: bool = False,
        military_supply_only: bool = False,
    ) -> list[dict[str, Any]]:
        return self._snapshot.recipes_for_era(
            era, mvp_only=mvp_only, military_supply_only=military_supply_only
        )

    def resources_for_era(self, era: str) -> list[dict[str, Any]]:
        return self._snapshot.resources_for_era(era)

    def get_resource(self, resource_id: str) -> dict[str, Any]:
        try:
            return dict(self._snapshot.resource_by_id[resource_id])
        except KeyError as exc:
            raise TypeValidationError(f"unknown resource {resource_id}") from exc

    def get_recipe(self, recipe_id: str) -> dict[str, Any]:
        try:
            return dict(self._snapshot.recipe_by_id[recipe_id])
        except KeyError as exc:
            raise TypeValidationError(f"unknown recipe {recipe_id}") from exc

    def pick_cross_terrain_recipe(
        self,
        era: str,
        available_resource_ids: Iterable[str],
        *,
        mvp_only: bool = False,
    ) -> dict[str, Any] | None:
        available = {str(rid) for rid in available_resource_ids}
        for recipe in self.recipes_for_era(era, mvp_only=mvp_only):
            a = str(recipe.get("input_a_id") or "")
            b = str(recipe.get("input_b_id") or "")
            if a in available and b in available and a != b:
                return dict(recipe)
        return None

    def to_manifest_summary(self) -> dict[str, Any]:
        by_era = {era: len(self.recipes_for_era(era)) for era in ERAS}
        services = [
            r["id"]
            for r in self._snapshot.resources
            if r.get("namespace") == "industrial_service"
        ]
        return {
            "resources": len(self._snapshot.resources),
            "recipes": len(self._snapshot.recipes),
            "recipes_by_era": by_era,
            "services_nonstorable": services,
            "culture_access_per_era": {
                era: len(self._snapshot.culture_access.get(era, ())) for era in ERAS
            },
        }


@lru_cache(maxsize=1)
def load_full_catalogue() -> FullCatalogue:
    return FullCatalogue.load()


def recipes_for_era(
    era: str,
    *,
    mvp_only: bool = False,
    military_supply_only: bool = False,
) -> list[dict[str, Any]]:
    """Era-filtered recipe list from the full catalogue (wiring helper)."""
    return load_full_catalogue().recipes_for_era(
        era, mvp_only=mvp_only, military_supply_only=military_supply_only
    )


def validate_full_manifest(path: Path | None = None) -> dict[str, Any]:
    """Ensure manifests/full.json matches the loaded catalogue floors."""
    catalogue = load_full_catalogue()
    manifest = _load_json(path or MANIFEST_PATH)
    summary = catalogue.to_manifest_summary()
    floors = manifest.get("catalogue") or {}
    if int(floors.get("industrial_resources", -1)) != RAW_COUNT:
        raise TypeValidationError("full manifest resource floor mismatch")
    if int(floors.get("processor_recipes", -1)) != RECIPE_COUNT:
        raise TypeValidationError("full manifest recipe floor mismatch")
    for era in ERAS:
        key = f"{era}_recipes"
        if int(floors.get(key, -1)) != RECIPES_PER_ERA:
            raise TypeValidationError(f"full manifest {key} floor mismatch")
    if not floors.get("services_nonstorable", False):
        raise TypeValidationError("full manifest must declare services_nonstorable")
    if not floors.get("era_filtered_full_recipes", False):
        raise TypeValidationError("full manifest must declare era_filtered_full_recipes")
    return {"manifest": manifest, "summary": summary}
