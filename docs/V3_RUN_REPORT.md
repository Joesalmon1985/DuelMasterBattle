# V3 run report — gameplay and asset completion (branch `work/gameplay-assets-v3`)

Not merged into `main`. Neural-network / AI training work is **deferred**; the heuristic AIs were used only to generate play and find bugs.

## Span
- Starting commit: `ded40a3` (parent of the first programme commit `5c11897`). Ending commit: the branch head (`git log --oneline ded40a3..HEAD`).
- Git timestamps: 2026-10-13 08:13 to about 10:30 BST (about 2.3 hours of committed work). **The 8-hour target was not reached**; this report lists what is left.
- 1907 files changed (mostly generated art), +37k / -2k lines.

## Complete (functional, tested)
- Era rules: Widelands production Prehistoric, whole OpenRA roster by Historic, Mindustry industry Modern, Mindustry units Dystopian; 7-round draft is the default on gated worlds (`legacy_draft=True` keeps the old set for regression tests); era bar uses current VP.
- Mindustry generic block engine (items, liquids, heat, power, payloads, turrets, logic, units T1-T5) with data-driven tests.
- OpenRA roster as hybrid buildings and recipes, abilities, aircraft, transports, Mk2 units from assembly lines.
- Widelands warehouses, ports, markets, shipyards, ferries, waterways, scouts, game keepers, ponds, terraforming.
- Hybrid industrial blocks that supersede Widelands buildings (3x+ throughput), drills for stone and ore, conversion and dismantling.
- Belts and machines can deliver into a Widelands warehouse (the bridge between the two economies).
- Coverage report (`scripts/coverage_report.py`, `docs/evidence/coverage/`), inspector coverage view with art parts/states.
- Scripted four-era scenario (`tests/test_four_era_scenario.py`): real era transitions, cards as developer fixture, no goods granted, ledger balanced.

## Partial / not done
- Scenario does not build the full Modern/Dystopian production chain; that chain is exercised in `test_industrial_revolution.py` and `test_mindustry_engine.py` with `modern_fixture`.
- Sea trade between factions' ports and an automatic ship-trade mode are not done.
- About 55 functional entities have no original art (hybrid `mdy:hy_*` blocks, Widelands warehouses and markets). OpenRA ftrk, mh60, tran, tent and tenf art is absent from the player's packages.
- Hash baselines (`scripts/hash_gate.py`) have **not** been re-recorded although behaviour changed.
- Performance profiling not done beyond the stability runs. Catastrophe containment/recovery has only per-era terminal-loss tests added.
- Godot inspector panel proof was not re-run headed after the inspector changes (headless Godot proofs in `test_mix_crypto.py` pass).

## Tests and runs
- Full suite (`pytest tests -n 3`, excluding `test_five_minutes.py`): 850 passed, 10 skipped, 5 failed. All five failures were fixed afterwards (stale test assumptions about assembly lines, a naval test stock reset, idle art for working-only Widelands sites, a Godot building-state check) and the affected files re-run green. The full suite was **not** re-run after those fixes.
- 180-minute AI stability run (seed 11, 6 AIs): no failures, ledger balanced, 6.6x real time, peak RSS 73 MB, reached **Modern (era index 2)** by minute 180 (the earlier 90-100 minute runs stayed in Historic); VP 3-9, so none reached Dystopian. Settlement VP saturates at 8-9 (documented for the later AI task).

## Decisions to review (owner)
Tier bonus making Mindustry units beat their counterparts; hybrid block costs; era bar settings; Mk2 stats; `legacy_draft` flag. See `docs/ledger/QUESTIONS.md`.

## Next steps
Re-record hash baselines; re-run the full suite; sea trade; art for hybrid blocks; headed Godot inspector proof; fuller scenario chain; performance profiling.
