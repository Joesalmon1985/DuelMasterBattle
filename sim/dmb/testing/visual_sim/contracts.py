"""Visual Simulation QA kernel — contract loading and scenario classes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCENARIO_CLASSES = frozenset({"PRODUCTION_JOURNEY", "ARRANGED_STATE"})
ROOT = Path(__file__).resolve().parents[4]
CONTRACTS_DIR = ROOT / "qa" / "visual_sim" / "contracts"


def load_contract(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        alt = CONTRACTS_DIR / path
        if alt.is_file():
            p = alt
        else:
            raise FileNotFoundError(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    validate_contract(data)
    return data


def validate_contract(data: dict[str, Any]) -> None:
    required = ("scenario_id", "scenario_class", "fixture", "seed", "expectations")
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"contract missing keys: {missing}")
    if data["scenario_class"] not in SCENARIO_CLASSES:
        raise ValueError(f"invalid scenario_class: {data['scenario_class']}")
    if not isinstance(data["expectations"], dict):
        raise ValueError("expectations must be a dict independent of actual observations")


def list_contracts() -> list[Path]:
    if not CONTRACTS_DIR.is_dir():
        return []
    return sorted(CONTRACTS_DIR.glob("*.json"))
