from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

WORLDVIEW_SCORE_FIELDS = (
    "Score_Throne",
    "Score_Broken_Chain",
    "Score_Covenant",
    "Score_Ledger",
    "Score_Ascendant",
    "Score_Root",
    "Score_Cracked_Mirror",
)

REQUIRED_FIELDS = {
    "Profile_Version",
    "Character_ID",
    "Display_Name",
    "Village_Role",
    "Narrative_Tier",
    "District",
    "Home_or_Base",
    "Core_Desire",
    "Immediate_Want",
    "Core_Fear",
    "Secret",
    "Central_Contradiction",
    "Knowledge_Profile",
    "Knowledge_Boundary",
    "Primary_Worldview",
    "Secondary_Worldview",
    "Key_Ally",
    "Ally_Relationship",
    "Key_Rival",
    "Rival_Relationship",
    "Cross_District_Connection",
    "Cross_District_Relationship",
    "Dependent_or_Responsibility",
    "Dependency_Relationship",
    "Daily_Routine",
    "Recurring_Location",
    "Quest_Hook",
    "Quest_Complication",
    "Quest_Alternate_Solution",
    "Puzzle_Type",
    "Puzzle_Logic",
    "Puzzle_Clue_Source",
    "Post_Quest_State",
    "House_Content_Rule",
    *WORLDVIEW_SCORE_FIELDS,
}


@dataclass(frozen=True)
class CharacterProfile:
    data: dict[str, str]

    def __getitem__(self, key: str) -> str:
        return self.data.get(key, "")

    @property
    def id(self) -> str:
        return self["Character_ID"].strip()

    @property
    def name(self) -> str:
        return self["Display_Name"].strip()

    @property
    def tier(self) -> str:
        return self["Narrative_Tier"].strip()

    @property
    def district(self) -> str:
        return self["District"].strip()

    @property
    def location(self) -> str:
        return self["Recurring_Location"].strip() or self["Home_or_Base"].strip() or self.district

    def worldview_scores(self) -> tuple[int, ...]:
        values: list[int] = []
        for field in WORLDVIEW_SCORE_FIELDS:
            raw = self[field].strip()
            try:
                values.append(int(float(raw)))
            except ValueError:
                values.append(0)
        return tuple(values)


def _validate_headers(headers: Iterable[str]) -> None:
    missing = sorted(REQUIRED_FIELDS.difference(headers))
    if missing:
        raise ValueError(f"Character profile CSV is missing required columns: {', '.join(missing)}")


def load_profiles(path: Path | str) -> list[CharacterProfile]:
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header row: {path}")
        _validate_headers(reader.fieldnames)
        profiles = [CharacterProfile({k: (v or "").strip() for k, v in row.items()}) for row in reader]

    if not profiles:
        raise ValueError(f"CSV contains no character rows: {path}")

    ids = [p.id for p in profiles]
    names = [p.name for p in profiles]
    if any(not value for value in ids):
        raise ValueError("Every character needs Character_ID")
    if any(not value for value in names):
        raise ValueError("Every character needs Display_Name")
    if len(ids) != len(set(ids)):
        raise ValueError("Character_ID values must be unique")
    if len(names) != len(set(names)):
        raise ValueError("Display_Name values must be unique")

    known_names = set(names)
    for profile in profiles:
        for field in ("Key_Ally", "Key_Rival", "Cross_District_Connection", "Dependent_or_Responsibility"):
            target = profile[field]
            if target and target not in known_names:
                raise ValueError(f"{profile.id} {field} refers to unknown character {target!r}")

    return profiles
