"""Wizard Mode narrative configuration: `data/narrative/config.json`, with environment overrides for tests and the launcher.

Everything tunable by the owner lives in the JSON (R1 palette, the unlock and expiry times, caps); nothing here reads the wall clock.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

PATH = Path(__file__).resolve().parents[1] / "data" / "narrative" / "config.json"

# environment variable -> (section, key, cast); read at call time so a test can set them after import
ENV_OVERRIDES = {
    "HYBRID_NARRATIVE_UNLOCK_MS": ("narrative", "unlock_after_ms", int),
    "HYBRID_TUTORIAL_EXPIRE_MS": ("tutorial", "expire_ms", int),
    "HYBRID_AUTOSAVE_SECONDS": ("save", "autosave_seconds", float),
}


@lru_cache(maxsize=1)
def _file() -> dict[str, Any]:
    return json.loads(PATH.read_text())


def version() -> int:
    return int(_file()["narrative_version"])


def get(section: str, key: str, default: Any = None) -> Any:
    for env, (sec, k, cast) in ENV_OVERRIDES.items():
        if sec == section and k == key and os.environ.get(env):
            return cast(os.environ[env])
    return _file().get(section, {}).get(key, default)


def log_cap() -> int:
    return int(_file().get("log_cap", 400))
