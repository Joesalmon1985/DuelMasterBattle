# Roadmap for the next development run(s)

> **Proposed next programme (not started, awaiting owner approval):** `PLAN_ECONOMY_TECH_ERA_PROGRAMME.md` (no-card civilisation, content graph, 7-Wonders draft ring, paper/scriptorium, single-faction 10-VP eras, content waves). This roadmap's M1-M6 are unchanged.

**Authorised for this run (owner instruction of 11 October 2026): the stop-after-each-milestone rule is superseded for that run only; branches are still never merged to `main`.** Live status per milestone, with completed / partial / blocked / not started, is in `IMPLEMENTATION_RUN_STATUS.md`; the restart point is `NEXT_AGENT_HANDOFF.md`. Original text: this is a plan; the run started on `NEXT_RUN_KICKOFF_PROMPT.md`. Decisions: `DECISION_REGISTER.md`. Gaps: `CURRENT_STATUS_AND_GAPS.md`.

## 0. Ordering and rules

Recommended order: **M1 → M2 and M3 (independent, can alternate) → M4 → M5 → M6**. M3 (wizard gameplay) must not wait for M6 (full RTS coverage). M6 items are interleaved as needs arise.

Every milestone keeps green: the 123-test hybrid suite (`WizardRTSHybrid/tests`), the 12 headed scripts, `test_determinism.py`, `test_territory.py`, AI-behaviour checks, legacy `tests/sim` and the Ward Duel test. Every milestone adds: Python headless tests; a headed Godot script with screenshots under `docs/evidence/<milestone>/`; replay/conservation assertions; a performance check (`scripts/bench_sim.py`, `ai_report.py` worst step < 1 s at 6 factions; headless ≥ 40× real time on the standard map); explicit pass/fail below. A defect seen in play counts as fixed only when a headed test shows it.

Common task boundary: an agent finishing a milestone commits on the feature branch, updates `PROJECT_STATUS.md`, `TASK_LEDGER.md`, `STATE_OF_PLAY.md`, `WORK_LOG.md`, and stops for review.

---

## M1 — Campaign profiles, drafted-tech unlocks, primitive start

> **Status (12 Oct 2026): implemented and verified for the primitive start, drafting, gating, God-Mode gating, AI development and the 40-minute peace/war runs.** See `IMPLEMENTATION_RUN_STATUS.md` for the exact tests and what is partial (card catalogue is 13 cards; era progression arrived with M4; draft prompt exists as a God-panel developer display only).

**Purpose.** Make the intended start real (D13, D15) and gate God Mode (D02) while keeping today's fully equipped start as a fixture.

**Reuse.** `HybridWorld(minimal=...)`, `_layout`/`_place_showcase`, `construction.py` menu and the existing "locked with reason" mechanism for naval units, `ai.py` plans, `sim/dmb/technology` as card-data reference.

**New/changed.** New `wizard_rts/tech.py` and `data/tech_cards.json`; `world.py` profile argument (`campaign`, `developer`, `test_showcase`, `test_minimal`; section 9 of `ARCHITECTURE_CONTRACT.md`); `construction.py` filter menu/`check_placement` by unlocked set; `ai.py` plans only from unlocked set, drafts by planner; `server.py`/`hybrid_world.gd`/`god_mode.gd` hide or reject God commands unless `developer`; `tests/conftest.py` default to `test_showcase`.

**Prerequisites.** None.

**Player-visible.** A new campaign opens with each faction owning a warehouse, a few primitive workplaces (woodcutter, forester, quarry, basic food), a handful of primitive units. A draft prompt (developer display first) adds a building to the menu and the AI builds it.

**Headless tests.**
- Campaign start: for every faction, the set of buildable kinds equals the primitive list; every other kind is rejected with `locked_by_card`.
- Drafting card C unlocks exactly its listed buildings/units, only if physical prerequisites hold (S06); same seed + commands ⇒ same unlock order across two processes.
- `campaign` rejects every God/training command; `developer` accepts them.
- `test_showcase` reproduces current stock/entity counts (regression numbers captured before the change).
- A 40-minute, 6-faction campaign run: every faction survives, drafts ≥ 1 card per S05 cadence, no negative stock, conservation holds.
**Headed.** `run_hybrid_campaign.gd`: launch in `campaign`, assert no God HUD button or `G` handler, screenshot of primitive settlement; `developer` launch shows God HUD; after a draft the build menu shows the new building.
**Performance.** Menu filtering ≤ 1 ms per call.
**Pass/fail.** All tests above green; existing suites unchanged; no gameplay code path for unlocked-only AI throws; fail if any locked kind can be built by any command path (including AI, MCV starter kit, tribe fallbacks).

**Risks.** The AI economy may collapse under primitive starts (existing AI assumes full kit): budget a rebalance pass; keep `test_showcase` for AI regression.

---

## M2 — First real Mindustry industrial-to-unit slice

> **Status (12 Oct 2026): the slice is implemented and verified** (pinned v146 importer, extraction on the existing deposits per D21, belts, power, crafters, unit factory, dagger, fight with an OpenRA unit, mine upgrade, conservation, determinism, headed `run_hybrid_industry.gd`). Original text below says "`terrain/mapgen` ore placement (S10)": **superseded by D21, no ore placement exists or will be added.** Liquids, routers, sorters, bridges, more machines and units, art: not done.

**Purpose.** Prove D06/D08/D16: deposit → drill → conveyor → crafter(/power) → unit factory → unit in the shared military sim, paid for by real Widelands goods and unlocked by a drafted card.

**Reuse.** Terrain deposits (`resources.py`), warehouse/stock API, construction sites and recipes, `world.units` spawn path, combat, God Mode build menu for dev view, M1 cards.

**New/changed.** `wizard_rts/industry/` (items/registry, drill, conveyor, power graph, crafter, unit factory); `scripts/import_mindustry_defs.py` → `data/mindustry_defs.json`; `sources/manifest.json` pin; `SOURCE_REUSE.md` and `LICENSES.md` rows; ~~`terrain/mapgen` ore placement (S10)~~ (removed by D21: extraction rules map the existing deposits); `tech_cards.json` Mindustry cards; Godot `client/hybrid/industry_view.gd` (belts with item dots, power/flow indicator); placeholder art labelled.

**Prerequisites.** M1 (cards). Pin chosen, upstream definitions read (see `MINDUSTRY_PROVENANCE.md`).

**Minimal end-to-end slice (visible and headless).** One copper+coal (or sand) deposit on a mountain tile set; a mechanical drill (built from delivered planks/granite/iron); a conveyor run of ≥ 8 tiles to a crafter; a combustion generator; the crafter's output delivered by conveyor to a unit factory (itself built from Widelands goods); the factory spawns one basic Mindustry ground unit that attacks an OpenRA unit and wins/loses by data.

**Headless tests.**
- Importer output equals values extracted from the pinned source for ≥ 10 named blocks/items (drill time, belt speed, crafter plan, unit stats); test records the SHA.
- Deposit decreases exactly by drilled amount (D17); sum of wares across deposit, drill, belts, crafter, factory stock, unit cost + waste is constant.
- Belt backpressure: block output, belt fills to capacity and drill stops; unblock, flow resumes; no loss or duplication.
- Power: remove generator ⇒ crafter stops (rate scaled by satisfaction); restore ⇒ resumes.
- Unit spawned has `world.units` row, fights under `military` rules; kill/death counters consistent.
- Card gating: without the card the machine kinds are rejected (`locked_by_card`).
- Determinism across two `PYTHONHASHSEED`s; replay from save.
**Headed.** `run_hybrid_industry.gd`: screenshot sequence of drill working, items moving on belts (frames differ), power indicator on/off, unit leaving factory, fight.
**Performance.** 200 belt tiles + 20 machines add ≤ 5% to the headless step; at 6 factions worst step < 1 s.
**Pass/fail.** All tests green and a demonstrated unit produced from ore with ledger totals reconciled. **Fail** if the unit appears without delivered inputs, if a second army engine exists, or if constants are copied without a source reference.

**Risks.** Fidelity vs. scope (use upstream numbers for the chosen blocks only); the 7 fps render budget (render belts as one multimesh, not per-item nodes); art terms.

---

## M3 — One live-settlement story: NPC, dungeon, duel, real consequence

> **Status (12 Oct 2026): implemented and verified as one vertical slice** (one NPC, one dungeon of four puzzles, one Mastermind duel, a real deposit change); Python core, Godot-RNG-exact puzzle port, headed UI. See `IMPLEMENTATION_RUN_STATUS.md`.

**Purpose.** Prove the wizard game is real (D19, D10): a settlement-driven quest where a real shortage causes a person's problem, a dungeon puzzle and a Mastermind duel change authoritative economy state.

**Reuse (do not redesign).** `sim/dmb/quests` (runtime, binding, causes), `sim/dmb/people`, `narrative`, `adventure`; `content/source/quests/shortage/`, `dungeons/mine` or `cave`, `dialogue/`, `aspects/`; `DmbPuzzleLogic`/`DmbPuzzleGen`, `puzzle.gd`, `dungeon_area.tscn`; duel service and Ward Duel; `world_interaction_label.gd`, `dialogue_box.gd`; village story slice as the pattern; fire magic.

**New/changed.** `wizard_rts/story_bridge.py` (settlement IDs → people/quests; shortage detector from stock/production events; typed effect applier with receipts); stable `settlement_id` in `territory.py`; a named worker (miner) linked to a real mine; dungeon entrance as a map-tile entity (disused mine/cave) with persistent puzzle state; Godot: NPC entity, dialogue via existing dialogue box, entering/leaving a dungeon area from `hybrid_world.gd` without losing world state.

**Prerequisites.** M1 (campaign profile, settlement identity may be built as part of M3 if M4 not done). Not M2.

**Minimal end-to-end slice.** In one campaign settlement the coal mine's deposit reaches depletion (or its delivery road is blocked by a hazard). The miner NPC (linked to the real mine worker) cites it. The wizard walks to the mine, talks to him (Aspect check), enters the linked dungeon (the old galleries; 1–2 puzzles from the existing templates), solves it, and either (a) duels a rival/guardian in a Mastermind duel or (b) takes the alternate branch. Effect: a validated world change, e.g. the mine's deposit gets an authoritative additional vein, or the blocked road is cleared. The smelter, which was starved, resumes and the stock of its product increases. Failure branch: the shortage persists and the NPC records the outcome.

**Headless tests.**
- Quest only offered when the shortage condition is true in the live state; if the AI fixes it first ⇒ `resolved_by_world`.
- Effect applied once (idempotent receipt); save/reload and re-enter never re-applies or respawns a completed quest.
- Destroying the mine mid-quest ⇒ failed/alternate branch, no soft lock, dungeon entrance persists or re-routes.
- Duel pauses `game_ms` (zero quanta), world resumes with identical entity IDs; duel outcome drives the typed effect.
- Conservation holds across the effect (the new vein is a logged source).
- Determinism and replay of the whole story with the same choices.
- Dialogue facts come from state; no free-text world mutation.
**Headed.** `run_hybrid_story.gd`: screenshots at mine shortage, dialogue, dungeon puzzle solved, duel board, mine producing again; asserts rendered NPC, dialogue text includes the real shortage, post-quest building shows working state.
**Performance.** Quest evaluation ≤ 1 ms per tick; dungeon scene load < 2 s on the T460.
**Pass/fail.** Full chain runs headed from walk-up to changed stock with all assertions; **fail** if any step uses a separate scripted state not in `HybridWorld`, if a quest reward spawns goods without a logged source, or if the legacy tests regress. Named characters stay placeholders from existing files; no canon claims.

**Risks.** Legacy dungeon generation is tied to Catan nodes (isolate and substitute tile entrances); Godot scene switching vs. one continuous world (use the Ward Duel lease pattern, which already preserves pose and entity IDs).

---

## M4 — VP and era progression foundation

> **Status (12 Oct 2026): implemented and verified** (settlement ids and chronicle, VP ledger, four eras with a stall guard, collapse/decline/split, cycle reset on the same land, headed `eras`). S04 threshold of 10 was not reachable in 40 game minutes; working default 6.

**Purpose.** D04/D07/D09/D18 foundation: settlement identity, VP ledger, era state and thresholds, in-place upgrades, faction decline/split/collapse hooks.

**Reuse.** `territory.py`, `lifecycle`, `ai.py`, `sim/dmb/eras` (planner, collapse, fission) as references.

**New/changed.** `settlements.py`, `eras.py`; config constants `ERA_VP_THRESHOLD`, `DRAFT_INTERVAL`, `UPGRADE_COST_FRACTION`; upgrade command; era-gated card pool; `snapshot` exposes VP/era for dev HUD.

**Prerequisites.** M1. M3's `settlement_id` may land here.

**Headless tests.** Founding adds 1 VP once; destroy adds 1 VP to the destroyer once (S01, S02); wizard destroy removes owner's VP, awards none (S03); undeployed MCV gives none; repeated events or reload never double-count; reaching threshold advances era, unlocking the next card pool; an upgrade consumes delivered wares, keeps building ID and workers; a faction that loses all command centres and MCVs collapses leaving ruins (S12); full-cycle reset leaves only the wizard and placement influenced by S07; reset ≠ era transition tests.
**Headed.** Dev HUD shows VP, era; screenshot of an upgrade and of a ruin after collapse.
**Performance.** VP bookkeeping O(events).
**Pass/fail.** Ledger replay equals live totals; no VP from non-settlements. **Risk:** the 10-VP threshold may be unreachable or trivial: expose telemetry (VP/time) and validate with `ai_report.py` over three seeds before fixing the number.

---

## M5 — Catastrophe region overlay and outbreaks

> **Status (12 Oct 2026): implemented and verified** (hex overlay, escalating spread, outbreaks, treatment, terminal loss, production effect; headed `outbreak`).

**Purpose.** D12: bounded-attention existential threat on a logical hex overlay.

**Reuse.** `coords.py` (hex math), `sim/dmb/hazards` deck/propagation, hazard content JSON, the existing hazard/duel contract.

**New/changed.** `regions.py` (overlay, outbreak cubes, spread, treatment), effect hooks on mine yield, crop growth, health/unrest, quest generation; map overlay in God/diagnostic view and a readable in-world sign (smoke, withered ground) near an outbreak.

**Prerequisites.** M1; useful after M3.

**Headless tests.** Every tile belongs to exactly one region; overlay never alters movement/placement; outbreak cadence deterministic; adjacent spread rules; treatment requires wizard presence; an outbreak reduces affected mine yield by a stated factor and recovers after treatment; loss threshold ends the cycle by explicit rule; replay.
**Headed.** Screenshot of a region with an outbreak and the visual cue; wizard treats it.
**Pass/fail.** Effects visible in conserved stock numbers, not decoration.

---

## M6 — Widelands worker economy completion and broader OpenRA content

> **Status (12 Oct 2026): partial.** Coverage is in the generated `WizardRTSHybrid/docs/COVERAGE.md`; builder and mine workers, liquids and most OpenRA content are not started.

**Purpose.** D05/D08 breadth; interleaved, not a gate for M3.

**Items.** Builder worker; real mine/smelter workers; flags and donkeys; tribe soldier-chain fixes (remove ax fallback); marble/gold/bricks; sheep/wool; gamekeeper; Frisian ponds; remaining Widelands civilian sites (58 need new commands); more OpenRA units/buildings with their traits (spread damage, patrol, repair, aircraft, garrisons, tech buildings); real ship/yard art.
**Tests.** Per item: bench run of the production site, conservation, headed shot; coverage report from `build_catalogue.py` increases by named behaviours.
**Pass/fail.** Each item's catalogue status moves only with test evidence.

---

## Cross-cutting acceptance checklist for the run

- [ ] No gameplay logic added in Godot.
- [ ] Every new content ID has a registry entry and provenance.
- [ ] Conservation test per new transport.
- [ ] Determinism test passes with two hash seeds.
- [ ] Headed screenshot evidence stored; docs updated; branch not merged to `main`.
