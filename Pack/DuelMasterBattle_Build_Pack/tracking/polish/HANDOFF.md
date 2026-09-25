# Polish owner playtest repair — handoff (25 Sep 2026)

**Branch:** `work/current-main-polish`  
**Comparison point:** `a2766b1aae6bc48e1b2e92ce1965aadf77f4d1b5`  
**Status:** `OWNER_REVIEW_PENDING` (not owner PASS; not `AUTO_READY_FOR_OWNER_REVIEW`)

## Start here

1. **[Play Visual Review.bat](../../../../Play%20Visual%20Review.bat)** — two-faction FX-MVP review (seed 507)
2. Optional: **[Play Six-by-One Review.bat](../../../../Play%20Six-by-One%20Review.bat)** — isolated `g05_review_six_one` slot, factions=6 / cores_per_faction=1
3. Read **[docs/START_HERE_VISUAL_PLAYTEST.md](../../../../docs/START_HERE_VISUAL_PLAYTEST.md)**
4. In-game: compact **Spellbook** → open → switch pages / scroll / close at both orientations

Ordinary play remains **Play Latest Integrated Game.bat** (no privileged review pages).

## What was repaired this pass

| Area | Change |
| --- | --- |
| Actor lifetime | `WorldLayerPresenters` owns geometric actors; preserved across `_finish_village_build` / rebuild paths; remount if invalid |
| Demon body | Larger filled red diamond + contrasting outline; player label is type name only (no `treat OK`) |
| Spellbook layout | Wider portrait column; wrapping/selector page nav; diagnostic body scrolls inside panel; parchment contrast panel |
| Review data | Explicit review fields incl. stocks/factions/tech_draft/research/diplomacy; cart `cargo_lots`/`current_node`; zero vs unavailable vs no-event |
| HUD / Travel | Exit action cards clamp to usable rect below status/Wait row and above movement pad |
| Wait / Watch | On-HUD **Wait** (one World Turn) + **Watch world** / Pause / speed; book pause is its own token; Close-and-watch starts observer |
| Policy load | Content root = `godot_project/`; LF-normalized schema hash + CRLF artifact compat; `source=neural` proven in sim |
| Six-by-one | `BoardBuilder.generate(..., cores_per_faction=1)`; env `DMB_FACTION_COUNT` / `DMB_CORES_PER_FACTION`; factions 5–6 colours |
| Guided review | Next reverts chapter on failed load; Capture writes PNG + JSON context |

## Tests

- `python -m pytest tests/sim -q` → **507 passed, 0 failed**
- Focused: `tests/sim/test_owner_playtest_repair.py` (schema LF/CRLF, artifact path cwd-independence, neural load, six-by-one, read_view research/diplomacy)
- Neural activate on FX-MVP seed 507: `source=neural` for assigned build/trade policies

## Simple review tasks for Joe

1. Open the book, switch pages, scroll and close at portrait and landscape; text/actions reachable.
2. Walk north and Travel; return once. Watch for covered controls or disappearing actors.
3. See a visible demon body, win one retained Ward Duel and return cleanly.
4. Click **Wait** once, then **Watch world**. Confirm turn/round/time and pause/resume.
5. Use industry/technology/hazard checkpoints: factory→Person/soldier, card/effect, faction response before/after.
6. Review history at a transition and save/quit/reload.

## Known open (do not treat as finished)

- Fresh headed PNG matrix at 450×800 / 1280×720 / 960×540 after these repairs (book, north Travel, demon, Wait/Watch)
- Economy stall (idle carts / proposed trades / score growth) still needs a bounded neural-command progression proof or retained failed prerequisite
- Guided chapter predicates vs arranged CP-ERA / CP-WARD naming
- Windows certification not claimed from Linux/sim

## Honest gate

Mandatory **sim** suite is green and the listed blockers have source repairs. Owner approval stays pending until headed pointer evidence and remaining acceptance items land. Do **not** set `AUTO_READY_FOR_OWNER_REVIEW` on this handoff alone.
