from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


def write_scene_summary(manifests: list[dict], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "scene_id", "scene_type", "district", "location", "primary_character_id",
        "participants", "dramatic_problem", "relationship_count", "quest_hook", "puzzle_type",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for m in manifests:
            writer.writerow({
                "scene_id": m["scene_id"],
                "scene_type": m["scene_type"],
                "district": m["district"],
                "location": m["location"],
                "primary_character_id": m["primary_character_id"],
                "participants": "|".join(m["participant_ids"]),
                "dramatic_problem": m["dramatic_problem"],
                "relationship_count": len(m["relationship_context"]),
                "quest_hook": m["quest_material"]["hook"],
                "puzzle_type": m["puzzle_material"]["type"],
            })


def coverage_report(manifests: list[dict], character_ids: list[str]) -> dict:
    primary = Counter(m["primary_character_id"] for m in manifests)
    appearances = Counter(pid for m in manifests for pid in m["participant_ids"])
    scene_types = Counter(m["scene_type"] for m in manifests)
    return {
        "characters": len(character_ids),
        "scenes": len(manifests),
        "scene_types": dict(scene_types),
        "primary_scene_coverage": {cid: primary[cid] for cid in character_ids},
        "appearance_coverage": {cid: appearances[cid] for cid in character_ids},
        "characters_with_zero_primary_scenes": [cid for cid in character_ids if primary[cid] == 0],
        "characters_with_zero_appearances": [cid for cid in character_ids if appearances[cid] == 0],
    }
