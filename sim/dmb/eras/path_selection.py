"""Future path selection — dystopia baseline; Utopia only with installed pack (T129)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sim.dmb.core.types import TypeValidationError

ROOT = Path(__file__).resolve().parents[3]
UTOPIA_PACK = ROOT / "godot_project" / "content" / "source" / "eras" / "utopia" / "pack.json"

BASELINE_PATH = "dystopia"
ALLOWED_PATHS = frozenset({"dystopia", "utopia"})


def utopia_pack_installed(path: Path | None = None) -> bool:
    target = path or UTOPIA_PACK
    return target.is_file()


def get_next_future_path(state: Any) -> str:
    value = str(state.clock.get("next_future_path") or BASELINE_PATH).lower()
    return value if value in ALLOWED_PATHS else BASELINE_PATH


def set_next_future_path(
    state: Any,
    path: str,
    *,
    quest_flag: bool = False,
    utopia_pack_path: Path | None = None,
) -> dict[str, Any]:
    """Persist next_future_path. Utopia requires installed pack + quest flag."""
    normalised = str(path or "").strip().lower()
    if normalised not in ALLOWED_PATHS:
        raise TypeValidationError(f"unsupported future path {path!r}")
    if normalised == "utopia":
        if not utopia_pack_installed(utopia_pack_path):
            raise TypeValidationError("utopia_pack_missing")
        if not quest_flag:
            raise TypeValidationError("utopia_requires_quest_flag")
    state.clock["next_future_path"] = normalised
    return {"next_future_path": normalised, "baseline": normalised == BASELINE_PATH}


def baseline_path_or_default(state: Any) -> str:
    """Ordinary baseline always dystopia when Utopia pack is absent."""
    if not utopia_pack_installed():
        state.clock["next_future_path"] = BASELINE_PATH
        return BASELINE_PATH
    return get_next_future_path(state)
