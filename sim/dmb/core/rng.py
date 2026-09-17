"""Named deterministic RNG streams for gameplay and replay."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any, Sequence


def _seed_bytes(seed: int | str) -> int:
    raw = str(seed).encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


@dataclass
class RngBank:
    streams: dict[str, dict[str, Any]] = field(default_factory=dict)

    def ensure(self, stream: str, *, seed: int | str = 0, version: int = 1) -> None:
        if stream not in self.streams:
            self.streams[stream] = {
                "seed": seed,
                "version": version,
                "draws": 0,
            }

    def _rng(self, stream: str) -> random.Random:
        self.ensure(stream)
        entry = self.streams[stream]
        material = f"{entry['seed']}:{stream}:{entry['version']}:{entry['draws']}"
        return random.Random(_seed_bytes(material))

    def draw_int(self, stream: str, low: int, high: int) -> int:
        if low > high:
            raise ValueError("low > high")
        rng = self._rng(stream)
        value = rng.randint(low, high)
        self.streams[stream]["draws"] = int(self.streams[stream]["draws"]) + 1
        return value

    def shuffle(self, stream: str, ids: Sequence[str]) -> list[str]:
        items = list(ids)
        rng = self._rng(stream)
        rng.shuffle(items)
        self.streams[stream]["draws"] = int(self.streams[stream]["draws"]) + 1
        return items

    def to_dict(self) -> dict[str, Any]:
        return {"streams": {name: dict(data) for name, data in sorted(self.streams.items())}}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RngBank":
        bank = cls()
        for name, data in dict(payload.get("streams", {})).items():
            bank.streams[name] = {
                "seed": data.get("seed", 0),
                "version": int(data.get("version", 1)),
                "draws": int(data.get("draws", 0)),
            }
        return bank
