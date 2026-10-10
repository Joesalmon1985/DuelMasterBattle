# Decisions

## D1 — Hex ownership is cube_round, not a 48 by 48 square

Question: how does one tile plane assign every tile to one hex of a 20 by 20 map?

Alternatives: an exclusive axis-aligned 48 by 48 square centred on each hex; a second collision grid; `cube_round` of the tile center with the largest rounding error kept on z.

Evidence: squares centred on hexes overlap and leave gaps, so they cannot be an ownership map. `tests/test_coords.py` checks one owner, full coverage, a walkable step between edge neighbours, and that the boundary function does not consult collision.

Rejected: the 48-square map. Settlement layout may still use a 48-tile local scene inside a hex footprint. That footprint is the owned tile set.

Reopen if a test shows a tile with two owners or a gap.

## D2 — Source-derived ports until an upstream binary is a dependency of play

Question: how should the first economy and military experiments land?

Alternatives: call the Widelands and OpenRA processes during play; paste upstream sources into the hybrid; port the smallest tested functions and label them.

Evidence: Widelands is GPL-2.0-or-later and must not be pasted as GPL-2-only. OpenRA compiled and its engine tests passed, but `PathFinder.FindPathToTargetCell` needs the OpenRA world, locomotor, and actor map. The hybrid snapshot records `source-derived-adapted` for stock and damage, and `provisional-scaffolding` for carrier routes and soldier steps.

Rejected: naming a DuelMasterBattle cart or formation after either engine. Both engines are not one game until an economic behaviour and a military behaviour from those implementations write the same `WorldState`.

Reopen when a packaged upstream library or process performs the warehouse update or the warhead without the hybrid reading `external/` at runtime.

## D3 — Local TCP is process separation, not netplay

Question: how does Godot see the Python world?

The server is newline JSON on `127.0.0.1`. One process owns the world for its lifetime. A dropped client must not kill the process. The clean-environment test rejects any connect that is not loopback and any `open()` under `external/`.
