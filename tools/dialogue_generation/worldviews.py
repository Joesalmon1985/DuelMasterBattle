import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from .config import config


@dataclass(frozen=True)
class Worldview:
    code: str
    key: str
    name: str
    core: str
    shadow: str
    delta: Dict[str, int]


class WorldviewSet:
    def __init__(self, version: str, worldviews: List[Worldview], conviction_tiers: dict):
        self.version = version
        self.worldviews = worldviews
        self.conviction_tiers = conviction_tiers
        self.by_code = {w.code: w for w in worldviews}
        self.by_key = {w.key: w for w in worldviews}
        expected = {"M", "A", "R", "G", "S", "D", "C"}
        if set(self.by_code) != expected or len(worldviews) != 7:
            raise ValueError(f"Worldview config must contain exactly {sorted(expected)}")
        for w in worldviews:
            if set(w.delta) != expected:
                raise ValueError(f"Worldview {w.code} has invalid delta keys")

    def prompt_text(self) -> str:
        chunks = []
        for w in self.worldviews:
            chunks.append(f"{w.code} — {w.name}\nCore: {w.core}\nShadow: {w.shadow}")
        tiers = ", ".join(f"{k}={v}" for k, v in self.conviction_tiers.items())
        return "\n\n".join(chunks) + f"\n\nConviction tiers: {tiers}"

    def delta_for_key(self, key: str) -> Dict[str, int]:
        return dict(self.by_key[key].delta)


def load_worldviews(path: Path | None = None) -> WorldviewSet:
    path = path or Path(__file__).with_name("worldviews.json")
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    worldviews = [Worldview(**item) for item in raw["worldviews"]]
    return WorldviewSet(raw["version"], worldviews, raw["conviction_tiers"])
