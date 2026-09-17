from __future__ import annotations

DEFAULT_COUNT = 5
MAX_COUNT = 10
OVERRIDE_MAX = 20

REQUIRED_TYPES = (
    "introduction",
    "relationship",
    "quest",
    "secret_pressure",
    "consequence",
)

EXTRA_TYPES = (
    "district_group",
    "relationship",
    "quest",
    "secret_pressure",
    "introduction",
    "consequence",
)


def validate_count(count: int, *, allow_more: bool = False) -> int:
    if count < 1:
        raise ValueError("Pilot count must be at least 1")
    cap = OVERRIDE_MAX if allow_more else MAX_COUNT
    if count > cap:
        raise ValueError(
            f"Pilot count {count} exceeds the safety cap of {cap}. "
            "This command will not generate the full catalogue."
        )
    return count


def _tier(scene: dict) -> str:
    by_id = {p.get("character_id"): p for p in scene.get("participant_profiles", [])}
    primary = by_id.get(scene.get("primary_character_id"), {})
    return str(primary.get("narrative_tier") or "")


def _index(scene_id: str) -> int:
    parts = str(scene_id).split("_")
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            return 0
    return 0


def _score_candidate(scene: dict, selected: list[dict]) -> tuple[int, int, int, int]:
    primaries = {s.get("primary_character_id") for s in selected}
    districts = {s.get("district") for s in selected}
    tiers = {_tier(s) for s in selected}
    unique_primary = 1 if scene.get("primary_character_id") not in primaries else 0
    unique_district = 1 if scene.get("district") not in districts else 0
    needed = {"Major", "Supporting", "Minor"} - tiers
    tier_gain = 1 if _tier(scene) in needed else 0
    need_group = not any(len(s.get("participant_ids") or []) >= 3 for s in selected)
    group_gain = 1 if need_group and len(scene.get("participant_ids") or []) >= 3 else 0
    return (unique_primary, unique_district, tier_gain, group_gain)


def _pick(pool: list[dict], selected: list[dict]) -> dict:
    return max(
        pool,
        key=lambda scene: (_score_candidate(scene, selected), -_index(scene.get("scene_id", "")), scene.get("scene_id", "")),
    )


def select_pilot_scenes(manifests: list[dict], *, count: int = DEFAULT_COUNT, allow_more: bool = False) -> list[dict]:
    count = validate_count(count, allow_more=allow_more)
    selected: list[dict] = []
    used_ids: set[str] = set()

    type_order = list(REQUIRED_TYPES)
    if count > len(REQUIRED_TYPES):
        type_order.extend(EXTRA_TYPES)

    for scene_type in type_order:
        if len(selected) >= count:
            break
        pool = [
            scene
            for scene in manifests
            if scene.get("scene_type") == scene_type and scene.get("scene_id") not in used_ids
        ]
        if not pool:
            continue
        choice = _pick(pool, selected)
        selected.append(choice)
        used_ids.add(choice["scene_id"])

    if len(selected) < count:
        leftovers = [scene for scene in manifests if scene.get("scene_id") not in used_ids]
        leftovers.sort(key=lambda scene: scene.get("scene_id", ""))
        for scene in leftovers:
            if len(selected) >= count:
                break
            selected.append(scene)
            used_ids.add(scene["scene_id"])

    if len(selected) < count:
        raise ValueError(f"Could only select {len(selected)} scenes; need {count}")
    return selected[:count]


def selection_record(scenes: list[dict]) -> dict:
    return {
        "count": len(scenes),
        "scene_ids": [scene["scene_id"] for scene in scenes],
        "scene_types": [scene.get("scene_type") for scene in scenes],
        "primary_character_ids": [scene.get("primary_character_id") for scene in scenes],
        "districts": [scene.get("district") for scene in scenes],
        "tiers": [_tier(scene) for scene in scenes],
        "participant_counts": [len(scene.get("participant_ids") or []) for scene in scenes],
    }
