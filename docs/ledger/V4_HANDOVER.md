# V4 handover (branch `work/mechanics-completion-v4`)

Plan: `docs/PLAN_MECHANICS_COMPLETION_V4.md`. Not merged to `main`; no neural-network work started.

## Done and pushed
- P1 cards: `wizard_rts/content/cards.py` (168 cards, 42 per era, 1-4 entities, essential tags, perfect-matching audit); `graph.check()` returns `[]`; dealer essential-card guarantee in `draft.deal`; AI picker for `gen.*` cards (`tech._ai_pick_generated`); bonus hands fall back to copies when the reserve is empty.
- Fake buildings excluded (D27); Mk2 skipped for excluded actors.
- Faction floor (D28): `history.MIN_FACTIONS`, `FLOOR_DELAY_MS`, `_floor_candidates`.
- Decisions D26-D32 recorded in `docs/DECISION_REGISTER.md` section 5.

## Known limits
- Historic readiness is 92% under the smart picker (the repeated tribe's second faction can lose its smithing card to its sibling).
- Modern is saturated (35 of 42 cards at 4 slots); some Modern and Dystopian cards are thematically loose.
- In rings above 6 the dealer hands out copies; a seat can be passed a last card it already holds (7 or 6 picks).
- Weaponless "functional" Mindustry units remain (P2 backlog).
- `scripts/hash_gate.py` baselines are stale (they diverge at minute 1); P0 re-records them under a new version label.
- Headed Godot proof must be run on the owner's machine.

## Next
P0 hash baselines and `state_hash` widening; P2 defect backlog; P3 ware-class costs (D31); P4 command tier, visibility (D32), `legal_actions`; P5 sweep tests and readiness report.
