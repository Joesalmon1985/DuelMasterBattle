# Architecture and modularity contract

Status: APPROVED direction (D07, D08, D14, D16, D20); module names below are RECOMMENDED. Prefer **incremental evolution of existing code** over rewrites. Do not create a new package unless a responsibility has nowhere to live. Current code map: `WizardRTSHybrid/wizard_rts/`.

## 1. Principles

1. **One canonical Python world.** `HybridWorld` (`wizard_rts/world.py`) is the only live simulation. It embeds the DuelMasterBattle `WorldState` and `ClockService`. No second economy, army, or clock. No Java Mindustry runtime. No separate Widelands or OpenRA process in play.
2. **Python is authoritative; Godot presents.** Godot sends validated commands and player input and renders snapshots. It never decides economy, combat, quest, or world state (D14). Presentation-only smoothing (the glide layer in `hybrid_art.gd`) never feeds back.
3. **Headless and deterministic.** Same seed + ordered commands ⇒ identical state across processes. No wall-clock decisions; no iteration over `set`s of strings for decisions; stable tie-breaking; counted (not timed) search budgets (`tests/test_determinism.py`).
4. **Physical item conservation.** See section 5.
5. **One military simulation.** All units from all eras live in `world.units` and are driven by the same orders, targeting, damage and AI (D16).
6. **One command surface.** The AI, God Mode, the training API and any tests use the same validated commands (`build`, `road`, `queue`, `move`, `order`, `demolish`, `deploy`, ...). The wizard campaign does not have this surface (D02): it uses interaction, magic and dialogue commands which are *different, narrower* commands validated by the simulation.
7. **Data over branches.** Adding a building, unit, ware, recipe, resource or card should be a data entry validated by schema, not a new `if kind == ...` branch in unrelated modules.

## 2. Authority split

| Concern | Owner | Notes |
| --- | --- | --- |
| Terrain, placement, pathing, territory | Python `grid/terrain/territory/construction` | Square grid, 4-way. |
| Wares, stock, logistics, recipes | Python `economy/logistics/workers/imm` (+ new `industry`) | Conserved. |
| Units, combat, orders | Python `military/rules/openra_damage` | OpenRA data; Mindustry units enter here. |
| AI | Python `ai.py` | Same commands as God Mode. |
| Technology, era, VP, settlements | Python (new `tech`, `eras`, `settlements`) | Not yet written. |
| Quests, people, dungeon state, dialogue facts | Python (bridge to `sim/dmb`) | Godot renders dialogue/puzzles and sends choices. |
| Mastermind duel rules and board | Existing duel service (`HazardDuelService`) | Lease pauses world clock (`hazard_duel` token). |
| Catastrophe regions | Python (new `regions`) | Non-physical overlay. |
| Rendering, input, camera, UI | Godot | `hybrid_world.gd`, `client/hybrid/*`. |
| God Mode UI | Godot, developer config only | |

Local JSON-over-TCP server (`server.py`, loopback only) is process separation, not netplay (D3 in `DECISIONS.md`).

## 3. Definitions and registries

Everything the sim knows about a *kind of thing* comes from a registry loaded at start from validated data. Runtime instances reference definitions by stable string ID plus a definition version.

| Registry | Today | Target |
| --- | --- | --- |
| Wares | `data/widelands_defs.json` (128), `wl_defs.py` | Add `mindustry.*` wares under their own namespace. Cross-namespace equivalence only by explicit mapping entries. |
| Resources/deposits | `terrain.py`, `resources.py`, `data/world/*` | Add per-resource ecology records (D17): `kind` (finite/renewable), `regen`, `carrying_capacity`, `valid_terrain`. |
| Buildings | Widelands defs + `construction.py` `RECIPES`/menu | Add `era`, `required_cards`, `upgrades_to`, `upgrade_cost`, `footprint`, `terrain_rules`, `tags`. |
| Units | `data/openra_rules.json` + hybrid recipes | Add `era`, `producer`, `required_cards`, cost in wares. Mindustry unit records produce the same unit row shape. |
| Recipes/programs | Widelands programs interpreter (`workers.py`) | Add machine recipes (`industry`), with power/liquid inputs. |
| Technology cards | none (hybrid) | `tech/cards.json`: id, era, prerequisite cards, physical prerequisites, unlocks (buildings, units, recipes). |
| Terrain | `terrain_defs.json` (pinned Widelands) | Extend with Mindustry ore/floor mapping (S10). |
| Settlements | derived from warehouse buildings | Explicit `settlement` records: stable ID, name, faction, centre, radius, founded_at, state. |
| Quests/dungeons/people | `sim/dmb/quests`, `people`, `godot_project/content/source/*` | Instances bind to settlement/building/worker/route IDs. |

**Stable IDs.** Definition IDs: `namespace.name` (`widelands.sawmill`, `openra.2tnk`, `mindustry.silicon_smelter`, `dmb.quest.shortage`). Instance IDs: allocated by the world's ID service (`self.dmb.ids.new(...)`), monotonic, never reused, never derived from list position. Settlement, quest and dungeon-instance IDs are instance IDs that survive save/load, ownership change and era transition.

## 4. Source importers, overrides and provenance

`pinned upstream` → `versioned importer script` → `generated, validated JSON in wizard_rts/data/` → `additive overrides (hand-written, separate files)` → `registry` → `simulation`.

- Importers live in `scripts/import_*.py` and record upstream URL, SHA and file/symbol in `sources/manifest.json`, `docs/SOURCE_REUSE.md` and `docs/LICENSES.md`.
- Never hand-edit generated files. Customisation is an override file keyed by ID. The override records why and the intended deviation.
- Unsupported upstream commands must **fail validation or be listed as unsupported**, never silently become free production. `feature_status.json` and `feature_catalogue.json` track behaviours, not file counts.
- Runtime play never reads `external/` (guarded by `tests/test_clean_environment.py`).
- Original art/derived copies follow `docs/LICENSES.md`; do not copy large amounts of upstream code or assets blindly.

## 5. Physical conservation contract

1. A ware is in exactly one place: building stock, worker/carrier hands, a conveyor/pipe/machine buffer, or an explicit reservation. A reservation is not a second copy.
2. Production consumes its inputs once and produces its outputs once. A queued unit or building takes real delivered goods; nothing materialises (except a flagged scenario/test grant, recorded in the event log).
3. Sources and sinks are explicit and logged: deposit extraction (reduces deposit), renewable growth (ecology model), consumption, destruction/loss, test grants.
4. Failed transport cannot teleport stock. Destruction/capture settles stock, cargo and reservations by documented policy (`lifecycle.purge_building`).
5. Era upgrade consumes delivered wares (S08); an old building does not produce a new-era good without a validated recipe.
6. A conservation test exists for every new transport mode: sum of wares in all locations + consumed − produced = constant.

**Worker versus conveyor/pipe/power (D08).**
- *Workers* (early eras): a task is a sequence of movement and action on the grid; output rate is a consequence of real walking and working. Hidden workers are a known gap, to be replaced by entities.
- *Conveyor/pipe/power* (Modern+): each belt segment/pipe holds typed buffered content, moves a bounded amount per tick, supports backpressure; power is a per-grid rate/capacity balance, not a ware; a deficit scales or stops consumers deterministically. Tick order is fixed and ID-ordered.
- *Bridge:* a machine output port deposits into a warehouse/construction-site/recruit-queue through the same stock API workers use, so both transports serve one request/stock contract.
- Machines, belts, pipes, nodes are **buildings/entities** in the world (with footprints, ownership, destruction), not hidden state.

## 6. Military and production unity

Unit factories (Widelands war factory, OpenRA barracks, Mindustry ground/air/naval factory) all end in the same spawn function that creates a `world.units` row with an OpenRA-style actor/weapon record. Stronger units are *data* (health, armour, weapons), not a second combat engine. `kill_unit`, `damage_building`, `lifecycle` remain the single destruction path (also used by wizard magic).

## 7. Event interfaces

The sim emits typed events into the bounded event log (6000 kept 3000): `built`, `destroyed`, `produced`, `delivered`, `shortage`, `unit_spawned`, `unit_killed`, `settlement_founded`, `settlement_destroyed`, `card_drafted`, `era_changed`, `outbreak`, `quest_effect_applied`, `puzzle_changed`. VP, chronicle, quests, dialogue facts and AI observations **read** events/state; they do not poke other modules' internals. Quest effects go back through typed, validated effect commands with receipts (idempotent: applying twice is a no-op).

## 8. Save, replay and level of detail

- Save: seed, config, ordered commands, game_ms, RNG state, all entity rows, deposits/ecology, reservations, conveyor/pipe/power state, card/era state, VP ledger, quest/puzzle state, people. `HybridEnv` already has save and replay (`sim_api.py`).
- Level of detail (D20): near activity (around the wizard and any active scene) at full fidelity; far activity may use a coarser step **only** if a test runs both versions from the same state and asserts equal item totals and equivalent outcomes within a stated tolerance. No LOD shortcut without that test.

## 9. Configuration profiles

| Profile | God Mode | Training API | Start | Used by |
| --- | --- | --- | --- | --- |
| `campaign` | off | off | primitive, card-gated | players |
| `developer` | on | on | selectable | developers, AI research |
| `test_showcase` | n/a (tests drive commands) | on | today's full six-faction start | existing regression suite |
| `test_minimal` | n/a | on | `minimal=True` single warehouse | bench tests |

The default for a player-facing launcher must be `campaign`. Tests assert (a) God Mode commands are rejected/unavailable in `campaign`, (b) available in `developer`.

## 10. Modules to add (not now)

`tech.py` (cards, drafting, unlock queries), `eras.py` (VP, thresholds, transitions, upgrades, reset), `settlements.py` (IDs, chronicle, VP ledger), `industry/` (items, drills, belts, pipes, power, crafters, unit factories), `regions.py` (catastrophe overlay), `story_bridge.py` (quest/people/dungeon ↔ world). Each ≤ a few hundred lines at first; each registers definitions and handles commands/events through the interfaces above.
