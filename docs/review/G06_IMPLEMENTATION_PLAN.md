# G06 Implementation Plan — Prehistoric → Historic integrated MVP

**Branch:** `phase/g06-historic-mvp`  
**G05 base SHA:** `3df9090ae081928d000b5acf4290ccf707abf771`  
**Gate:** G06 ends at T114 → `AWAITING_HUMAN` (never self-PASS)  
**Out of scope:** Modern / Future / full-cycle (P12 / T115+)

## Architecture principle

```text
              SAME WORLD (19 hex / 54 node / LocalAreas)
                        │
              ┌─────────┴─────────┐
              │                   │
        PREHISTORIC STATE    ERA TRANSITION (atomic in-place)
                                  │
                                  ▼
                            HISTORIC STATE
```

No replacement board, no separate Historic scene, no NPC regeneration, no teleport-to-test-village production path.

## Path reconciliation (old task cards → this checkout)

| Logical pack path | Actual owner |
|---|---|
| `sim/dmb/eras/*` | **Create** under `sim/dmb/eras/` (package absent today) |
| `sim/dmb/history/chronicle.py` | **Create** `sim/dmb/history/` |
| `client/*` | `godot_project/client/*` |
| `content/source/*` | `godot_project/content/source/*` |
| `content/fixtures/*` | Prefer `sim/dmb/testing/fixtures.py` + `shared_fixtures/` / `godot_project/content/` as used by G05 |
| `content/source/dialogue/tutorial/` | Prefer `godot_project/content/source/dialogue/` + optional UI hints; do **not** put tutorial prose in NPC mouths |
| `tracking/` | `Pack/DuelMasterBattle_Build_Pack/tracking/` |
| `sim/dmb` in repository_map | Map still says `NOT_PRESENT`; **actual** package is `sim/dmb/` (established G01–G05) |
| T103 “shortage quest” | **Translate** to Rockfall / `quest.blocked_exit_boulder` (canonical G05 quest) |

Do **not** invent parallel systems merely to mirror old names.

## G05 baseline to preserve

Authoritative 19-hex world; same-sized LocalAreas; natural terrain; settlements/roads/trails; workers/industry; carts; military/formations/battles; hazards + Ward duel; world map; persistent people/dialogue; Rockfall quest; clean village dialogue; long-run military progression; **no** active shortage quest.

Named continuity Persons for transition tracing (seed 507 / node:35): `person:16`…`person:22` (and peers in dialogue audit).

## Known risk before T112 (must diagnose, not inject VP)

G05 long-run (`FX-LONG-WORLD`, seed 507, 200 turns):

- Settlements 4→4, cities 0, roads 4→5
- `CART_DEPARTED` / `CART_DELIVERED` = 0
- Units produced / battles worked

**Implication:** heuristic expansion/logistics may be insufficient to reach 10 VP legitimately. Before any balance papering: diagnose C04/C05/C12 construction + cart dispatch against production services. Fix defects; if design-paced, record evidence. FX-ERA may start near threshold; ≥1 full no-debug trajectory to 10 VP is still required.

---

## Task map T097–T114

### T097 — Pure EraTransitionPlanner + theoretical capacity ranking

| | |
|---|---|
| **Reuse** | `RateAllocator` theoretical flag (`sim/dmb/industry/allocation.py`); `ScoreService` / `VP_THRESHOLD` (`construction/scoring.py`); factory/route constraint builders; settlement/faction registries on `WorldState` |
| **Missing** | `sim/dmb/eras/` package; `EraTransitionPlan` hashed dataclass; pure `plan(snapshot, trigger)`; theoretical site ranking ignoring temporary catastrophe/damage/depletion |
| **Own files** | `sim/dmb/eras/__init__.py`, `planner.py`; extend allocation helpers only if needed for theoretical military output |
| **Tests** | `tests/sim/test_t097_era_planner.py` — catastrophe does not change rank; installed capacity does; ties by settlement ID; plan hash stable; planner does not mutate |
| **Visible** | None yet (pure plan object) |
| **Depends** | T096 / G05 tip |

### T098 — Multi-faction collapse + inert ruins

| | |
|---|---|
| **Reuse** | `ScoreService.settlement_vp` already zeros `ruined` / `ruin_only` / non-operational; `people/registry.py`; `logistics/stock.py` loss receipts patterns; T037 destruction patterns |
| **Missing** | Collapse selection (all &lt;5 VP + exactly one lowest remaining; capacity/ID ties; winner protection); `eras/collapse.py` disposition; inert ruin markers (no collision/VP/stock/loot/road capacity/reservation) |
| **Own files** | `sim/dmb/eras/collapse.py`; people displacement + stock retirement hooks |
| **Tests** | 10/9/8/7/6/5 loses 5; tied lowest uses capacity then ID; civilians survive displaced; ruins inert; losses once |
| **Visible** | Ruins as decorative markers (presentation later T105/T110) |
| **Depends** | T097 |

### T099 — Compact fission / successor ownership

| | |
|---|---|
| **Reuse** | Board graph distances (`world/board.py`); research inherit (`technology/research.py` `inherit_to_successor`); diplomacy defaults (`ai/diplomacy.py`); legal action surface (`ai/legal.py`) only if fission policy candidates already exist |
| **Missing** | Top-4 pairing (3 pairings, min within-pair distance, stable ties); settlement/road/unit/cart assignment; successor IDs from reserved block (allocated at **commit**, not plan); no Person duplication |
| **Own files** | `sim/dmb/eras/fission.py` |
| **Tests** | Known distance fixture picks minimum pairing; cargo aboard unchanged; siblings neutral/trade-permitted; people not cloned |
| **Visible** | Faction labels change after commit (later) |
| **Depends** | T098 |

### T100 — Historic core transform + one-time starter grant

| | |
|---|---|
| **Reuse** | `WorldSetupService` / `STARTER_GOODS`; building create/rebind patterns; industry bootstrap; Historic tech defs already in MVP eras |
| **Missing** | In-place centre/warehouse/primary/3 factory upgrade; Historic defs/bindings; minimal Historic processor route(s); meter reset; cores → 1 VP; idempotent transition+core receipt (2 timber, 2 brick, 1 wool, 1 grain); content under `godot_project/content/source/eras/historic/` (or mapped equivalent) |
| **Own files** | `sim/dmb/eras/upgrades.py`; Historic content JSON |
| **Tests** | City→1 VP core; no duplicate slots/persons; reload no second grant; factory meter 0; Catan stock retained |
| **Visible** | Historic core silhouette/labels (T110) |
| **Depends** | T099 |

### T101 — Legacy sites + paid upgrade

| | |
|---|---|
| **Reuse** | Construction orders (`construction/orders.py`); industry routes; scoring `legacy` → 0 VP until upgraded |
| **Missing** | Mark non-core survivors as operational legacy (old industry/units/stocks/people); paid delivered upgrade path; no free remote conversion; no duplicate slots |
| **Own files** | Extend `eras/upgrades.py`; wire order kind `legacy_upgrade` |
| **Tests** | Legacy factory still spawns old-era unit; depleted layer not refilled; paid upgrade → 1 VP, no extra slots |
| **Visible** | Distinct legacy vs Historic core (visual language update) |
| **Depends** | T100 |

### T102 — Sole-faction / zero-faction safeguards

| | |
|---|---|
| **Reuse** | Turn runner (`time/runner.py`); setup/recovery seeding (`world/setup.py`, recovery fixtures) |
| **Missing** | `eras/safeguards.py`; solo protection + mandatory fission; 2/3/1-site undersized rules + one-time distance exception; zero-faction next World Turn seeds two factions (not Game Over) |
| **Own files** | `safeguards.py`; runner hook |
| **Tests** | Solo survives then splits; one-site never duplicates 4 centres; empty world nonterminal; only-remaining mid-era winner not self-collapsed |
| **Visible** | Continued play after dissolution |
| **Depends** | T101 |

### T103 — People / Rockfall quest continuity

| | |
|---|---|
| **Reuse** | `world/boulder_quest.py`; `quests/runtime.py`; `adventure/item_recovery.py`; person dialogue truth conditions |
| **Missing** | `eras/continuity.py` adaptations for ownership/displacement; Rockfall state machine across transition (unseen / inspected / clearing / cleared); no shortage quest resurrection |
| **Own files** | `continuity.py` + quest adaptation hooks |
| **Tests** | Same quest ID; helper Person binding; never restart/duplicate/resurrect; cleared path stays clear; Person IDs stable |
| **Visible** | Same people/dialogue truth after era change |
| **Depends** | T102 |
| **Note** | Task card “shortage” → **Rockfall** |

### T104 — Atomic EraService commit + hazards + roster

| | |
|---|---|
| **Reuse** | Command/transaction interrupt patterns (`core/commands.py`, `time/turns.py`); hazard service era counters; draft discard (`technology/draft.py`) |
| **Missing** | `eras/service.py` `request_transition` / `commit`; freeze leases; cancel later old-era stages; hazard rollover; fresh seats/hands; single commit receipt |
| **Own files** | `service.py`; runner/encounter integration |
| **Tests** | Winner skips later draw; no partial draft; transition once; no extra turn/ms; stale lease rejected; save never half-converted |
| **Visible** | World era flag Historic after commit |
| **Depends** | T103 |

### T105 — TransitionPresenter + Chronicle

| | |
|---|---|
| **Reuse** | Pause tokens; projection/export; G05 shell patterns |
| **Missing** | `godot_project/client/world/era_transition.gd` (~4s staged, skip/reduced motion, presentation-only); `sim/dmb/history/chronicle.py`; Chronicle UI |
| **Own files** | Presenter + chronicle + UI |
| **Tests** | Skip/reload never re-converts; worker still visible; knowledge-filtered vs debug; ruins buildable |
| **Visible** | Freeze → highlight → collapse → transform → Historic labels → resume |
| **Depends** | T104 |

### T106 — FX-ERA (+ FX-SOLO regressions)

| | |
|---|---|
| **Reuse** | `sim/dmb/testing/fixtures.py`, `tools/run_scenario.py`, G05 fixture style |
| **Missing** | Near-10-VP production checkpoint; collapse/fission/legacy/quest continuity cases; `tools/play_fx_era.sh` |
| **Own files** | Fixture definitions + `tests/scenarios/test_era_transition.py` |
| **Tests** | Interrupt later old work; dispose once; old industry resumes; solo sequential boundaries; save/load match |
| **Visible** | Fast human retest path |
| **Depends** | T105 |

### T107 — Player screens

| | |
|---|---|
| **Reuse** | `inventory.gd`, `world_map_panel.gd`, pause screens, grimoire/spellbook host, knowledge filters |
| **Missing** | Complete pointer-only inventory/grimoire/knowledge/map/Chronicle; no RTS HUD; no remote army/spell from map |
| **Own files** | Mapped Godot UI under `godot_project/client/ui/` |
| **Tests** | Verb coverage; touch hit areas; map cannot order armies |
| **Visible** | Playable G06 screens |
| **Depends** | T106 |

### T108 — Integrated two-era sandbox

| | |
|---|---|
| **Reuse** | `prehistoric_world.py`, `play_g05.sh` / overworld shell, Rockfall, industry, military, hazards, map |
| **Missing** | `tools/play_g06.sh` launching **same** generated Prehistoric world with era continuation enabled; no Game Over after Historic |
| **Own files** | Launch + setup flags; main scene wiring to existing overworld |
| **Tests** | Normal start → can reach transition without injected VP/stock; post-Historic play continues |
| **Visible** | Full sandbox |
| **Depends** | T107 (+ economy diagnosis for reachability) |

### T109 — Contextual optional hints

| | |
|---|---|
| **Reuse** | G05 optional_hints pattern; pause/settings |
| **Missing** | Situation hints (map, blocked route, cart, hazard, approaching transition, legacy site); never into NPC mouths; archival onboarding stays archived |
| **Own files** | Hint content + `hints.gd` (or extend pause_screens) |
| **Tests** | Hints optional; truthful; off ⇒ actions still reachable |
| **Visible** | Dismissible tips |
| **Depends** | T108 |

### T110 — Prototype Historic presentation + a11y

| | |
|---|---|
| **Reuse** | Geometric placeholder language; faction colours |
| **Missing** | Distinct Historic core/factory/primary/soldier shapes+labels; transition FX; update `docs/WORLD_VISUAL_LANGUAGE.md`; reduced motion / non-colour cues; viewport checks 1280×720, 960×540, narrow |
| **Own files** | Presenters/assets under `godot_project/client/`; visual language doc |
| **Tests** | Manifest assets present; hit areas; pause settings invariant |
| **Visible** | Historic ≠ Prehistoric ≠ legacy at a glance |
| **Depends** | T109 |

### T111 — Cumulative replay / persistence

| | |
|---|---|
| **Reuse** | Replay harness, persistence coordinator, scenario runner |
| **Missing** | End-to-end Prehistoric→Historic continuation hash tests; Person/quest/cargo/grant idempotence |
| **Own files** | `tests/scenarios/test_mvp_continuation.py`; `tracking/mvp_validation/` |
| **Tests** | No duplicate transition/grants/people; save mid-loop matches uninterrupted |
| **Visible** | Report artifacts |
| **Depends** | T110 |

### T112 — Six-seed pacing evaluation

| | |
|---|---|
| **Reuse** | `testing/long_run.py`, long-run observer; extend event types |
| **Missing** | `tools/evaluate_mvp.py`; ≥6 seeds; observer events (`VP_GAINED`, `TEN_VP_REACHED`, `ERA_TRANSITION_PLANNED`, `FACTION_COLLAPSED`, `SUCCESSOR_CREATED`, `CORE_UPGRADED`, `LEGACY_SITE_RETAINED`, `HISTORIC_STARTED`); ≥1 legitimate Historic reach |
| **Own files** | Evaluator + `tracking/mvp_balance/` + observer extension |
| **Tests** | All runs terminate; failures retained; no hidden resources |
| **Visible** | Pacing table + long-run visuals |
| **Depends** | T111 (+ expansion/logistics fix if needed) |

### T113 — Desktop candidate

| | |
|---|---|
| **Reuse** | Existing packaging scripts if any; Linux Godot launch |
| **Missing** | `tools/package_desktop.py` / `build/desktop/` as far as **this** Linux environment allows; Windows sidecar requires Windows runner — record blocker honestly |
| **Own files** | Packaging tooling + `tracking/mvp_build/` notes |
| **Tests** | Clean launch where platform available; do not claim Windows if untested |
| **Visible** | Launch instructions |
| **Depends** | T112 |

### T114 — G06 human gate packet

| | |
|---|---|
| **Reuse** | G05 gate packet structure |
| **Missing** | `tracking/gates/G06/` full packet: commit, hashes, `play_g06.sh`, `play_fx_era.sh`, reports, Person/quest continuity tables, before/after evidence, known defects; `python tools/check.py --gate G06`; set `G06 = AWAITING_HUMAN`; **STOP** |
| **Own files** | Gate packet only (+ check wiring) |
| **Tests** | Gate wrapper PASS automated; human gate pending |
| **Visible** | Joe playtest checklist |
| **Depends** | T113 |

---

## Launch modes (to verify before advertising)

| Mode | Command (planned) | Purpose |
|---|---|---|
| Normal integrated | `bash tools/play_g06.sh` | Full Prehistoric sandbox → Historic |
| Near-transition | `bash tools/play_fx_era.sh` | FX-ERA checkpoint → 10 VP → inspect |

Both must be launched successfully before T114 reports them.

## Long-run observer extension (with T112 / earlier as needed)

Extend G05 long-run observer (do not invent a second tool) with era/expansion events listed under T112, derived from authoritative state/events.

## Dialogue / narrative discipline

- Keep G05 clean dialogue architecture.
- Do **not** resurrect Mara shortage / demon-sluice / Route A/B / `mvp_bank` into active play.
- Historic dialogue: truth-conditioned, scoped, no leakage.

## Task discipline

1. Implement task in order  
2. `python tools/check.py --task Tnnn`  
3. Write `tracking/handoffs/Tnnn.json`  
4. Commit task-owned work  
5. Continue  

Repair limit: 3 focused attempts → compact blocker.

## Stop condition

After T114: **G06 INTEGRATED PREHISTORIC → HISTORIC MVP READY — AWAITING HUMAN PLAYTEST**
