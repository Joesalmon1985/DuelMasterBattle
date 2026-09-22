"""Offline precompiled dialogue line catalogue (C09 / T084).

Production load walks only top-level `*.json` under the dialogue source root.
Archived/retired banks live under `archive/` and are not selected in normal play.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sim.dmb.core.types import TypeValidationError

_CONTENT_ROOT = (
    Path(__file__).resolve().parents[3] / "godot_project" / "content" / "source" / "dialogue"
)

PRODUCTION_SCOPES = frozenset({"normal", "rockfall", "soldier", ""})
ARCHIVED_SCOPES = frozenset({"archived", "aspect", "test", "onboarding"})


@dataclass
class LineCatalog:
    lines: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | None = None, *, include_archive: bool = False) -> "LineCatalog":
        base = root or _CONTENT_ROOT
        catalog = cls()
        if not base.is_dir():
            return catalog
        paths = sorted(base.glob("*.json"))
        if include_archive:
            paths.extend(sorted(base.glob("archive/**/*.json")))
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            items = payload if isinstance(payload, list) else list(payload.get("lines") or [])
            for item in items:
                line_id = str(item.get("id") or "")
                if not line_id:
                    raise TypeValidationError(f"dialogue line missing id in {path}")
                catalog.lines[line_id] = dict(item)
        return catalog

    def get(self, line_id: str) -> dict[str, Any] | None:
        rec = self.lines.get(line_id)
        return dict(rec) if rec else None

    def candidates(
        self,
        *,
        speaker_role: str | None = None,
        quest_id: str | None = None,
        stage: int | None = None,
        cause_id: str | None = None,
        era_id: str | None = None,
        aspect_id: str | None = None,
        tags: list[str] | None = None,
        allow_archived: bool = False,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for line in self.lines.values():
            scope = str(line.get("scope") or ("aspect" if line.get("aspect_id") else "normal"))
            if not allow_archived and scope in ARCHIVED_SCOPES:
                continue
            if line.get("aspect_id"):
                if not aspect_id or str(line["aspect_id"]) != str(aspect_id):
                    continue
            elif aspect_id:
                # Explicit Aspect conversation prefers Aspect-tagged lines.
                continue
            if speaker_role and line.get("speaker_role") and line["speaker_role"] != speaker_role:
                continue
            if quest_id and line.get("quest_id") and line["quest_id"] != quest_id:
                continue
            if stage is not None and line.get("stage") is not None and int(line["stage"]) != int(stage):
                continue
            if cause_id and line.get("cause_id") and line["cause_id"] != cause_id:
                continue
            if era_id and line.get("era_id") and line["era_id"] not in {era_id, "all"}:
                continue
            if tags:
                line_tags = set(line.get("context_tags") or [])
                if not set(tags).issubset(line_tags) and line_tags and not line_tags.intersection(tags):
                    if line.get("priority") != "fallback":
                        continue
            out.append(dict(line))
        out.sort(key=lambda item: (-int(item.get("match_score", 0)), str(item.get("id"))))
        return out
