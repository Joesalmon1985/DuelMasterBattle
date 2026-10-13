# Current status, feature inventory and design gaps

> **Update 13 Oct 2026 (autonomous v2 run, branch `work/ubuntu-autonomous-v2`).** Since this inventory: no-card civilisation, era-start ring drafting with 137 generated cards, paper/scriptorium, clinics, relations/diplomacy, a content graph and God Mode inspector, a C A* kernel (about 1.6x faster at minute 30, hash-equal), MIX decryption and 29 more units of real art, building state sheets, a sprite-facing fix and independent turret layers are in. What works, what is partial and what is still absent is listed with evidence in `docs/V2_RUN_REPORT.md` and `docs/evidence/content_status.md`. This file below is otherwise unchanged.

Inspected 11 October 2026 on branch `feature/hybrid-playtest-fixes-v03`, HEAD `55d7762`. Source of truth for *what exists*: the code and tests. This file summarises them and distinguishes five levels:

- **WORKS** — exercised by a passing Python test and (where visible) a headed Godot script.
- **PARTIAL** — works for some cases; limits named.
- **IMPORTED** — data or art is present but no gameplay behaviour proves it.
- **TEST-ONLY** — exists for tests/dev, not for campaign play.
- **ABSENT** — nothing in the hybrid. Includes legacy features that live elsewhere in the repo but are not connected to the hybrid.

Design intent is in `DuelMasterBattle_Design_v0_5.md`. The detailed hybrid inventory remains `WizardRTSHybrid/docs/STATE_OF_PLAY.md` (partly stale, see section 7).

## 1. Verified baseline

- Branch `feature/hybrid-playtest-fixes-v03`, never merged into `main`. Local branches: this one and `feature/wizard-rts-hybrid-v02` (also on `origin`).
- Reported by the project docs (session 3): 123 Python tests and 12 headed Godot scripts passing. Re-run in this session: see section 8.
- Six untracked files from the owner (`docs/DuelMasterBattle_*_v0_4.*`, the 88-profile CSV, the Widelands/OpenRA economy workbook) are preserved untouched.

## 2. Hybrid simulation inventory (`WizardRTSHybrid/wizard_rts/`, ~7,900 lines)

| Area | Level | Evidence and limits |
| --- | --- | --- |
| Square-grid terrain, Widelands rules, buildcaps, deposits, imported `.wmf` maps | WORKS | `terrain.py`, `mapgen.py`, `grid.py`, `wl_map.py`; `tests/test_terrain.py`, `test_wl_map.py`; headed `run_hybrid_terrain.gd`. Not exact Widelands geometry (D5 in `DECISIONS.md`). |
| Forestry, quarry, mines (finite deposits), farming, hunting, fishing, food chain, smelting, sawmill, ax | WORKS | `workers.py`, `imm.py`, `resources.py`; tests `test_forestry`, `test_food`, `test_fishing`, `test_resources`. |
| 138 imported Widelands production programmes via a generic interpreter | WORKS (bench) | 153/153 bench rows; not each headed. 58 sites need unsupported commands; 59 military/training/ship sites not implemented. |
| Road logistics, carriers, wares conserved | WORKS | `logistics.py`; `test_logistics.py`. No flags/donkeys/priorities/rerouting. |
| Construction | PARTIAL | Sites request their cost over roads. **20 s timer with no builder worker** (conflicts with D08; a gap). |
| Hidden mine/smelter workers | PARTIAL | Not entities (conflicts with D08; a gap). |
| MCV, deploy, command centres, separation, territory | WORKS | `territory.py`; `test_territory.py`; headed `run_hybrid_mcv.gd`. Settlement = command-centre building; no persistent settlement ID, name, VP or chronicle. |
| OpenRA rules import and combat (92 actors, 45 weapons) | PARTIAL | `military.py`, `rules.py`, `data/openra_rules.json`. Only 4 of 94 actors integrated as playable. No spread damage, formations, hierarchical pathfinder, aircraft, veterancy, garrisons, patrol, repair. |
| Naval slice (yard, sub pen, patrol boat, submarine) | WORKS (sim) | `test_naval.py` (13). Ship/yard art are PLACEHOLDER shapes. |
| Goods-fed recruitment | WORKS | Barracks, war factory queues consume delivered wares. |
| Six factions, five tribes, AI (expansion, squads, scouting, retreat, navy) | WORKS | `ai.py`, `tribes.py`; `test_ai_behaviour`, `test_tribe_ai`; 40-minute, three-seed report. Non-Barbarian tribes recruit via a 25-minute ax fallback (their own chains stall). |
| Wizard fire magic and labels | WORKS | `magic.py` (buildings, units, workers, carriers, trees, rocks, animals within 3 tiles); `wizard_labels.gd`; headed `run_hybrid_wizard.gd`. |
| Retained Ward Duel pauses `game_ms` | WORKS | `run_hybrid_duel.gd`, `tests/sim/test_u05_retained_ward_duel.py`. Only one hazard on the map; no settlement/quest link. |
| God Mode (RTS HUD) | TEST-ONLY by intent, but currently always present | `god_mode.gd` loaded unconditionally in `hybrid_world.gd`; button/`G` toggles for everyone. See G1. |
| Headless training interface `HybridEnv` | TEST-ONLY | `sim_api.py`; `test_sim_api.py`. Learned policy is not better than scripted AI. |
| Determinism across processes | WORKS | `tests/test_determinism.py`. |
| Diagnostics for stuck entities | WORKS | `diagnostics.py`. |
| Mindustry (items, ores, drills, conveyors, power, liquids, crafters, unit factories) | **ABSENT** | No code, data, test or manifest entry. |
| Technology cards, drafting, era progression, tech-gated build menu | **ABSENT** in the hybrid | Everything in `construction.py` is available from the start (a few naval units are locked with reasons). Legacy `sim/dmb/technology/draft.py` and `sim/dmb/eras/` are not connected. |
| Victory points, settlement stable IDs, chronicle | **ABSENT** | Nothing in `wizard_rts`. |
| Catastrophe regions/outbreaks in the hybrid | **ABSENT** | Legacy `sim/dmb/hazards/` is Catan-hex-based and not connected. |
| Quests, NPCs, dialogue, dungeons in the hybrid | **ABSENT** | No call from `wizard_rts` or the hybrid Godot scene into any legacy quest/dialogue/dungeon component (the substring "quest" in `wizard_rts` is "request"). |
| Cycle reset / faction split / collapse | **ABSENT** | AI promotes a surviving outpost to capital or the faction is defeated; nothing else. |

## 3. Current-versus-intended gaps

| # | Current | Intended | Where it matters |
| --- | --- | --- | --- |
| G1 | God Mode and the AI-command surface exposed to every player. | Campaign hides God Mode; developer/test configuration enables it (D02). | `hybrid_world.gd`, `god_mode.gd`, `server.py`. |
| G2 | Full showcase start: each faction has its complete kit and every building is available. | Bare-bones campaign start; buildings/units unlocked by drafted cards (D13, D15). Showcase kept as a named fixture. | `world.py` (`_layout`, `_place_showcase`), `construction.py` (menu, `RECIPES`), `ai.py`. |
| G3 | MCV settlements are anonymous warehouses; owner is a faction colour. | Stable settlement identity with VP, chronicle, people, quests (D04, D07). | `territory.py`, `world.py`. |
| G4 | Workers/roads only. | Workers/roads plus authoritative conveyors, liquids, power, one economy (D06, D08). | new `industry` module; `logistics.py`, `economy.py`. |
| G5 | OpenRA actors partly imported, Widelands soldiers deprecated. | Broad OpenRA coverage plus stronger Mindustry units, one military sim (D05, D16). | `military.py`, `rules.py`, `data/`. |
| G6 | Ward Duel and fire magic exist; no dialogue, quest state, or persistent dungeon in the hybrid. | Settlement dialogue + quest + dungeon + duel changing real state (D19). | new bridge to legacy `sim/dmb/quests`, `narrative`, dungeons; Godot `hybrid_world.gd`. |
| G7 | Square map only; a legacy hex label for the player. | Square map plus logical catastrophe hex overlay (D03, D12). | `coords.py`, new `regions` module. |
| G8 | Mixed old docs: AGENTS.md said "two factions", "20 by 20 hex world", "Do not implement Mindustry"; STATE_OF_PLAY has stale rows. | One approved direction. | This documentation set. |
| G9 | Hidden workers and builder-less construction timer. | Real builders and entities (D08). | `workers.py`, `construction.py`. |
| G10 | Non-Barbarian tribe soldier chains stall; ax fallback after 25 min. | Each tribe feeds its own chains. | `tribes.py`, `ai.py`. |
| G11 | Headed render about 7 fps on the T460 with a full map; Windows unmeasured. | Playable budget for wizard walking. | `terrain_view.gd`, snapshot size. |

## 4. Quick reference: what is not implemented in the hybrid, said plainly

Mindustry, tech cards, eras, VP, catastrophes, dialogue/quests/dungeons, cycle reset, faction collapse rules. Imported actor definitions and art do not count as gameplay.

## 5. Inventory of legacy DuelMasterBattle assets (reuse before rewriting)

All live outside `WizardRTSHybrid/`. They were built against the Catan/hex game (v0.3) and run in their own Godot scenes and Python `sim/dmb`. None is wired into the hybrid yet. Status words above apply (they work in their own runtime where tests pass; not re-run here).

| Asset | Location | What it is | Integration notes |
| --- | --- | --- | --- |
| Python simulation package | `sim/dmb/` (~25k lines in 22 sub-packages: `quests`, `narrative`, `people`, `adventure`, `eras`, `hazards`, `technology`, `industry`, `construction`, `logistics`, `military`, `ai`, `time`, `persistence`, `world`, `encounters`...) | Typed world state, IDs, clock, effects, quests runtime/binding/causes, people, narrative, era planner/collapse/fission/continuity, hazard deck/propagation, tech draft/research | The hybrid already embeds `dmb.core.WorldState` and `ClockService`. `quests`, `people`, `narrative`, `adventure`, `persistence` are the integration targets. `construction/logistics/industry/military/ai` are the superseded Catan economy and are reference only. |
| Quest content | `godot_project/content/source/quests/` (19 files) | Families: shortage, transport, conflict, diplomacy, discovery, military, personal, catastrophe, pollution, archive; `boulder_quest.json` in dialogue | Candidate for M3. `shortage/` is the natural first quest. Schemas in `content/schemas/{quests,effects,puzzles,definition}.json`. |
| Dungeon content | `godot_project/content/source/dungeons/` (alien, bunker, cave, industrial, machine, mine, sluice, temple; 16 files) and `DD/` (Deathtrap backbone, encounter adaptation, replacement first-adventure plot) | Era-themed dungeon definitions; Deathtrap-derived canon backbone | Mine/cave/temple map to Historic; industrial/machine/bunker/alien to later eras. |
| Dungeon runtime and puzzles | `godot_project/client/adventure/puzzle.gd`, `dungeon_area.tscn`, `client/scripts/puzzle_test_*.gd`; `sim/world` puzzle logic (`DmbPuzzleLogic`, `DmbPuzzleGen`, `DmbDungeons`) | 8 puzzle templates (offerings, exchange, switch chain, plate hold, timed gate, mosaic, magic target, two levers), 4-room dungeons, persistent state | `docs/SETTLEMENTS_AND_DUNGEONS.md`. Dungeon generation there is tied to Catan nodes; entrance placement must change to hybrid map tiles. |
| Dialogue | `godot_project/content/source/dialogue/`, `compiled/dialogue/`, `compiled/packs/`, `content/source/people/` (profiles, goals, preferences), `aspects/`; tools "Run Dialogue Factory.bat", `Run Ensemble Authoring.bat`; docs `DIALOGUE_*` | Offline-compiled dialogue with seven Aspects | Reuse as-is; bind facts to hybrid state. |
| Village story slice | `godot_project/content/village_tests/E17A`, `E36B`, `village_test_dialogue.json`, `client/world/village_projector.gd`, `scenes/village_test_menu.tscn` | Four-beat story Reeve → Woodcutter → Miller → Miner on a 60x52 village (sawmill, mill, forge, mine) | Closest existing analogue to a settlement story on production buildings. |
| Cast and story docs | `docs/DMB_Character_Profiles_88_Disco_Elysium_Depth.csv` (untracked), `Duel_Master_Battle_Village_Cast_Matrix_*.xlsx`, `docs/characters/`, `docs/NARRATOR_VOICE.md`, `docs/FIRST_ADVENTURE.md`, `docs/SECOND_ADVENTURE_PLAN.md`, `DD/Duel Master Battle — Replacement First Adventure Plot.md` | Named cast, plots | **Canon is deferred (D19).** Do not rewrite or promote any to canon. Preserve files. |
| Mastermind duel | `godot_project/sim/` (duel ruleset, bestiary, bot, battle sim), `client/legacy/` (peg slots, ward barrier, cast timer), `client/duel/`, `client/encounters/duel_lease_adapter.gd`, `python_prototype/duel_mastermind/`; hybrid `HazardDuelService` | Colour-and-slot duel, progression, rival cast | Already driven from the hybrid for the Ward Duel. |
| World/story flow | `client/world/{overworld,world_play,story_events,world_flow,dialogue_box,era_transition}.gd` | Overworld, interaction labels, story events | `hybrid_world.gd` extends `overworld.gd`, so labels/dialogue box are reachable. |
| Hazards/catastrophes | `content/source/hazards/` (aliens, machines, nuclear, pollution), `sim/dmb/hazards/` (deck, propagation, responders) | Hex-cube outbreaks on the 19-hex board | Needs the regional overlay (M5); hazard definitions are reusable. |
| Tech cards | `sim/dmb/technology/` | Seven-card draft per World Round | Reference for card data; the cadence is replaced (S05). |
| Test suites | `tests/sim` (many `test_t0xx`, `test_g05`, `test_r06_mastermind_duel`, quest/boulder), Godot `sim/tools/run_tests.gd` | Legacy regression | Keep green; do not delete. |

## 6. Intentionally excluded versus postponed (D05)

Excluded (superseded): original Widelands barracks and training sites as military producers (recipes, art may stay for history; the AI no longer builds them, `ai.BUILD_WL_BARRACKS=False`); OpenRA refineries, harvesters, credits and power economy; Catan dice, node/edge board, World-Turn production.

Postponed (will be added, era/tech gated): remaining Widelands civilian buildings (58 sites need unsupported commands: scouts, ferries, ponds, gamekeeper, terraform, etc.; builder worker; flags/donkeys), remaining OpenRA units and buildings (aircraft, tech buildings, spread damage...), all Mindustry content, Utopia (deferred outright).

## 7. Documentation conflicts found and how they are corrected

| Conflict | Source | Correction |
| --- | --- | --- |
| "Do not implement Mindustry" | `WizardRTSHybrid/AGENTS.md` | Superseded by D06; AGENTS rewritten. |
| "Two factions run an economy" | `AGENTS.md` | Six factions, five tribes. |
| "20 by 20 hex world", "hex ownership cube_round" as the territory rule | `AGENTS.md`, `STATE_OF_PLAY.md` "What works" row, `DECISIONS.md` D1 | Superseded by D5/D03: square grid authoritative; hex only a legacy label and the future catastrophe overlay. `DECISIONS.md` D1 and D5 already say so; banners added. |
| Workers are decorative | v0.3 spec (not in repo) | Superseded by D08; v0.4 §6.4 and v0.5 §6. |
| Catan dice/resource economy authoritative | v0.3 spec, `sim/dmb` | Superseded; legacy code is reference only. |
| Four-vs-Utopia fourth era | v0.4 D01 | Dystopian Future (D01). |
| "Needs decision" items marked PROPOSED in v0.4 | v0.4 §19 | Now ratified in `DECISION_REGISTER.md`; v0.4 left unchanged as history. |
| `STATE_OF_PLAY.md` partial table: "ships, fishing missing"; header "Last updated end of session 2" in `PROJECT_STATUS.md` | hybrid docs | Naval and fishing now work (see section 2); banners added to point here. Full rewrite deferred to avoid destroying evidence. |
| Test counts (57, 105, 123) vary by document | hybrid docs | Treat `docs/WORK_LOG.md` plus a fresh run as authoritative (section 8). |

## 8. Baseline test run in this session

`python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py` (Ubuntu): **123 passed** (72 + 51 progress dots, no failures; run without a summary line, took roughly 25 minutes on a loaded machine). Headed Godot scripts and the legacy `tests/sim` suites were **not** re-run in this session; their results above are as reported by the project docs.


## 9. Update from the implementation run (12 October 2026)

- **G1 (God Mode / training surface not gated): fixed for the shipped entry.** `wizard_rts/server.py` rejects every faction-level op unless the profile is `developer`/`test_*`; the Godot client hides the God button and ignores `G` in `campaign`. `HybridEnv` is still an unguarded in-process developer tool (documented in `ARCHITECTURE_CONTRACT.md` §10). Tests: `test_campaign_tech.py`; headed `campaign`.
- **D15 start**: `profile="campaign"` gives the primitive start; `test_showcase` keeps the old start (the `HybridWorld` default). Card drafting exists (S05 cadence 15 game minutes, S06 prerequisites).
- **Mindustry (D06/D16/D21)**: WORKS for the M2 slice (see `MINDUSTRY_PROVENANCE.md`). ABSENT: liquids, routers, sorters, bridges, other factories and units, art.
- **M3-M5 WORK** (12 Oct update): persistent settlement ids and chronicle, VP ledger, four eras with a stall guard and cycle reset on the same land, hex-region outbreaks, the story bridge (one NPC, one dungeon, one duel) with headed UI, six headless environments, a NumPy training harness. See `IMPLEMENTATION_RUN_STATUS.md`.
- **Still ABSENT or weak:** trained dungeon and cross-system policies (they failed; `TRAINING_PROGRAMME.md`), builder and mine workers, liquids/routers, most OpenRA content, art for Mindustry machines (placeholders).
