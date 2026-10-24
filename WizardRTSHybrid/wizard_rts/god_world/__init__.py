"""God World: the `god_catan_v1` rules profile (docs/GOD_WORLD_PRD.md).

Six autonomous factions settle, trade, build roads and upgrade villages on the logical board of a 5-6 player Catan game, drawn as one
continuous world. The player is a god with a free camera: viewing, inspection and playback only.

This package is the whole authority for that profile: board (`board.py`), the five-slot economy and its ledger (`rules.py`, `ledger.py`),
journeys (`journeys.py`), the heuristic AI (`ai.py`), ages (`ages.py`), the village projection (`composition.py`) and the world object that
runs them on one clock (`world.py`). It never instantiates the legacy `WorldState` or `HybridWorld`: in this profile `GodWorld` is the only
live simulation (`net/host.py` and `net/android_entry.py` select it by profile).
"""
