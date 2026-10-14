# Execution plan: content freeze and hierarchical neuroevolution

This is the task-by-task guide for the agent that implements `docs/PLAN_HIERARCHICAL_NEUROEVOLUTION.md` (call it "the design"). The owner approved the design and every default in its section 15 on 14 October 2026 (decision register D33, D34, N01-N09). Do the tasks in order. Each task says what to build, how to test it, when it is done, and what to commit. When this document and the design disagree, this document wins; when the code disagrees with either, trust the code and the tests, then fix the document.

Repository root is `C:\Users\joesa\Documents\Cursor\DuelMaster\DuelMasterBattle`; the simulation package is `WizardRTSHybrid/wizard_rts/`; the new package is `WizardRTSHybrid/neuro/`. Commands below are for Windows (`py -3`); on Linux use `python3`.

---

## 0. Working rules (read every session)

1. **Branch.** Work on `feature/neuroevolution-plan` (or `feature/neuroevolution-m<N>` branched from it per milestone). Never merge into `main`; the owner does that. Push after every committed task.
2. **Progress ledger.** `docs/ledger/NEUROEVO_PROGRESS.md` lists every task below with a checkbox. Start a session by reading it and `git log --oneline -10`. Tick a task only when its "Done when" holds and its tests pass. Write one line of evidence next to the tick (test command and result, or a path under `WizardRTSHybrid/docs/evidence/neuroevo/`). End a session by updating the ledger, committing and pushing, even if a task is half done (then write "IN PROGRESS: <what is left>").
3. **Content is frozen.** Do not add, remove or rename any building, unit, ware, item, liquid or card. Never run a `scripts/import_*.py` script. If a task seems to need new content, it does not; use an existing entity or mechanic and note the gap in the ledger.
4. **Determinism.** Never iterate over a `set` of strings to make a decision; sort first. Never use wall-clock time in a decision. All randomness in the trainer comes from `numpy.random.Generator` objects seeded from recorded seeds. `tests/test_determinism.py` and the new `test_neuro_determinism.py` must stay green.
5. **The simulation decides legality.** The controller proposes; `HybridWorld`/`HybridEnv.apply` accepts or rejects. Never bypass `check_placement`, `queue_unit`, `tech.draft` or `kind_allowed`.
6. **No hidden information.** Anything the controller reads about other factions goes through `neuro/vision.py`.
7. **Tests after every task.** Quick suite for the touched areas plus `py -3 -m pytest WizardRTSHybrid/tests/test_sim_api.py WizardRTSHybrid/tests/test_content_freeze.py -q`. The full suite (`py -3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py`, 30-40 minutes) at the end of every milestone.
8. **Hash gate.** Any change inside `wizard_rts/` that is meant to preserve behaviour must pass `py -3 WizardRTSHybrid/scripts/hash_gate.py check --baseline WizardRTSHybrid/docs/perf/hash_baseline.json` (baselines re-recorded in T0.5). A change that is meant to alter behaviour (M1 visibility, successor control) re-records the baselines in the same commit and says so in the message.
9. **Commits.** One task per commit when practical, message `neuro(T<id>): <what>` and the attribution line the harness requires. Never `git add -A`; add the files you touched. Never commit `~/dmb_runs`, `*.npz` outside `WizardRTSHybrid/neuro/models/`, or `docs/release_notes.md` (a Windows case-collision artifact that always shows as modified).
10. **Stop points.** Stop and report to the owner at the end of M0, M1, M3, M5 and M6 (the ledger says "OWNER CHECKPOINT"). Report: what works, test counts, measured numbers, anything that deviates from the design.
11. **Honesty.** A run that completes is not learning. Report negative results exactly as the previous reports did (`docs/TRAINING_PROGRAMME.md`).

---

## Milestone M0: freeze the catalogue and prepare the machine

### T0.1 Verify the environment

Run and record in the ledger: `py -3 --version` (3.14.0 expected), `py -3 -c "import numpy; print(numpy.__version__)"` (2.4.0), `git status --short` (only `docs/release_notes.md` may show), and the 64-test subset: `py -3 -m pytest WizardRTSHybrid/tests/test_sim_api.py WizardRTSHybrid/tests/test_vp_eras.py WizardRTSHybrid/tests/test_outbreaks.py WizardRTSHybrid/tests/test_content_graph.py WizardRTSHybrid/tests/test_coverage.py WizardRTSHybrid/tests/test_nn.py WizardRTSHybrid/tests/test_neural_draft.py -q -p no:cacheprovider` (64 passed on 14 Oct). Done when all pass.

### T0.2 Optional packages

`py -3 -m pip install psutil`. If it fails, continue; every use of psutil must be inside `try/except ImportError`.

### T0.3 C compiler for the native A* kernel (N03)

Try, in order: `winget install -e --id BrechtSanders.WinLibs.POSIX.UCRT` (then open a new shell and check `gcc --version`); if winget is unavailable, `winget install -e --id MSYS2.MSYS2` and add `C:\msys64\ucrt64\bin` to the user PATH with `gcc` from `pacman -S mingw-w64-ucrt-x86_64-gcc`. Verify with `py -3 -m pytest WizardRTSHybrid/tests/test_native_astar.py -q` (it must report the kernel built, not skipped). If no route works within 30 minutes, write the exact error in the ledger and continue with the pure-Python fallback; nothing else depends on it.

### T0.4 Windows fixes for the three scripts that import `resource`

Files: `WizardRTSHybrid/scripts/bench_sim.py`, `long_stability.py`, `run_civilisation_tournament.py`. Add `WizardRTSHybrid/wizard_rts/sysinfo.py`:

```python
def rss_mb() -> int:
    """Peak or current resident memory in MB; -1 if unknown. psutil, then resource (POSIX), then ctypes GetProcessMemoryInfo (Windows)."""
```

Replace every `resource.getrusage(...)` with `sysinfo.rss_mb()`. Also make `scripts/bench_full_game.py` use it. Test: `py -3 WizardRTSHybrid/scripts/bench_sim.py --minutes 2` prints JSON on Windows; `py -3 WizardRTSHybrid/scripts/run_civilisation_tournament.py --seeds 507 --minutes 3 --jobs 1 --report-dir %TEMP%\civ_smoke` completes. Done when both run. Commit `neuro(T0.4): Windows-safe memory reporting`.

### T0.5 Hash baselines on Windows

The merged v4 work already recorded current baselines: `docs/perf/hash_baseline_v4.json` (showcase world, baseline AI) and `docs/perf/hash_baseline_v4_campaign_plus.json` (campaign, plus AI), checked by `WizardRTSHybrid/tests/test_hash_baseline.py` (first 3 minutes). Run that test and `py -3 WizardRTSHybrid/scripts/hash_gate.py check --baseline docs/perf/hash_baseline_v4.json` on this PC. If the hashes differ here (the baselines were recorded under Python 3.12/3.13 on Linux; a float or hash-order difference would show at minute 1), do **not** edit the simulation: re-record both files under the label `_v4_windows` with `hash_gate.py record` (same seeds and minutes), make `test_hash_baseline.py` pick the file by platform, and write in the ledger that Linux and Windows baselines differ (that is itself a finding for the determinism work). The older `WizardRTSHybrid/docs/perf/hash_baseline*.json` files are stale (V3 changed behaviour without re-recording) and are left as history.

### T0.6 The roster manifest and `freeze.py`

Create `WizardRTSHybrid/wizard_rts/freeze.py`:

```python
ROSTER_VERSION = "roster-1.0.0"
MANIFEST = Path(__file__).with_name("data") / "content_freeze.json"
DATA_FILES = ("widelands_defs.json", "openra_rules.json", "mindustry_defs.json", "mindustry_full.json", "mindustry_overrides.json", "tech_cards.json", "terrain_defs.json")

def live_roster() -> dict:
    """Sorted id lists from the live registries: entities (graph.entities), units (unit:* ids), cards (graph.generated_cards),
    hand_cards (tech.cards), wares (wl_defs.defs()['wares']), mdy_items, mdy_liquids (mindustry_defs.json), and
    excluded {id: reason} from coverage.build() rows with status 'excluded'. Also 'counts'."""
def data_hashes() -> dict[str, str]        # sha256 per DATA_FILES entry
def roster_hash(roster: dict | None = None) -> str   # sha256 of json.dumps({k: roster[k] for k in ("entities","units","cards","hand_cards","wares","mdy_items","mdy_liquids")}, sort_keys=True)
def manifest() -> dict                      # loads MANIFEST (cached)
def check() -> list[str]                    # human-readable differences live vs manifest: added/removed ids per list, excluded entries no longer excluded, data hash mismatches, version string
```

The counting logic exists in `WizardRTSHybrid/docs/evidence/neuroevo/scripts/count_entities.py`. Measured on the merged tree (`1b404a8b`, after `work/mechanics-completion-v4`): **582 entities** (486 buildings: 206 Widelands, 25 OpenRA, 252 Mindustry, 3 hybrid; 96 units: 42 OpenRA, 50 Mindustry, 4 hybrid), **168 generated cards** (four eras of 42, 1-4 slots each, `content/cards.py`), 33 hand cards, 41 hybrid build-menu kinds, 234 `full_menu` kinds; four-list prototype hash `7afaf3ae773ef391ddc9458babb96ea645d4f3106b6a34f5f3f234cd8a3d43f4` (the final hash will differ because wares, items and liquids are added). The 11 OpenRA decoy buildings are excluded by D27 and must appear in `excluded`.

Create `WizardRTSHybrid/scripts/freeze_content.py`:

```
py -3 WizardRTSHybrid/scripts/freeze_content.py --write                 # first time only: writes data/content_freeze.json from the live registries
py -3 WizardRTSHybrid/scripts/freeze_content.py --check                 # prints freeze.check(), exit 1 if any difference
py -3 WizardRTSHybrid/scripts/freeze_content.py --bump minor --reason "..."   # regenerates the manifest, bumps ROSTER_VERSION in freeze.py, appends a dated row to docs/CONTENT_FREEZE.md
```

`--write` refuses if the manifest exists (use `--bump`). The manifest JSON has the keys shown in the design, section 2.2, plus `base_commit` from `git rev-parse --short HEAD`.

Create `docs/CONTENT_FREEZE.md`: what is frozen, why (D33), the counts, how to run the check, the rule for bumps (reason, owner approval), and an empty changelog table.

Create `WizardRTSHybrid/tests/test_content_freeze.py`:

* `test_manifest_matches_live_registries`: `freeze.check() == []`.
* `test_counts`: manifest counts equal the measured numbers (entities 582, buildings 486, units 96, cards 168, hand cards 33, wares 128, items 22, liquids 11).
* `test_excluded_stay_excluded`: every id in `manifest()["excluded"]` has status `excluded` in `coverage.build()`.
* `test_data_files_unchanged`: `data_hashes() == manifest()["data_files"]`.
* `test_source_pins_unchanged`: the three commit SHAs in `sources/manifest.json` equal the ones recorded in `content_freeze.json["source_pins"]`.
* `test_importers_refuse_without_unfreeze`: for every `scripts/import_*.py`, running it with `subprocess` and no `DMB_UNFREEZE` exits with code 3 and prints "content is frozen" (fast: the guard runs before any import work).

Done when all six pass and `coverage_report.py --check` still passes. Commit `neuro(T0.6): roster manifest, freeze check, CONTENT_FREEZE.md`.

### T0.7 Importer guards

Add to the top of every `WizardRTSHybrid/scripts/import_*.py` (23 files), right after the docstring:

```python
from wizard_rts import freeze_guard  # noqa: E402  (content is frozen: D33)
freeze_guard.require_unfreeze(__file__)
```

with `WizardRTSHybrid/wizard_rts/freeze_guard.py`:

```python
def require_unfreeze(script: str) -> None:
    """Exit 3 with a notice unless DMB_UNFREEZE=1 is set and --reason <text> is in sys.argv (D33)."""
```

Mind the `sys.path` setup each script does before importing `wizard_rts`; place the guard after it. Done when `test_importers_refuse_without_unfreeze` passes and `DMB_UNFREEZE=1 py -3 scripts/import_openra_rules.py --reason test --help` reaches argparse. Commit `neuro(T0.7): importer guards`.

### T0.8 Documents and ledger for M0

Mark plan v2's P6/P7/P9/P11 rows in `docs/ledger/LEDGER.md` as "superseded by D33". Run the full test suite once on Windows and record the result (count, failures, time) in the ledger; fix only failures caused by this milestone, list the others as pre-existing. **OWNER CHECKPOINT.**

---

## Milestone M1: environment hardening

### T1.1 Visibility model

**What v4 already provides** (`wizard_rts/visibility.py`, D32): sight sources per faction (units 7 tiles, aircraft 10, buildings 8, a command centre its territory), `visible(world, faction, tx, ty)`, an explored-cell memory (`known`), `seen_enemies` (what is in sight now), `visibility_quantum` every 2 game seconds in `HybridWorld.advance`; `HybridEnv.observe` filters `enemy_capitals` by `known` and `threats` by `visible`, and `legal_actions["attack"]` lists only visible targets. **What is missing:** a memory of enemy *buildings* once seen (position, kind, last hp, last seen time, removal when seen gone), use of that memory by the heuristic AI (`ai._known_targets` still reads the global `_ai_known` set) and a per-faction list for the controller. Extend `visibility.py` rather than writing a parallel module; create `WizardRTSHybrid/neuro/__init__.py` (empty) and `WizardRTSHybrid/neuro/vision.py` as a thin facade over it with this interface (the constants below are the existing ones; keep them):

```python
# wizard_rts/visibility.py (existing constants): SIGHT_UNIT = 7, SIGHT_AIR = 10, SIGHT_BUILDING = 8, CELL = 4, QUANTA = 20
def memory_of(world, faction) -> dict[str, dict]     # NEW: world.__dict__["vis_memory"][faction] = {enemy_building_id: {"tile", "kind", "faction_name", "hp", "last_seen_ms"}}
def refresh(world, faction) -> None                  # EXTEND: after updating explored cells, every enemy building (not blight nests of faction "") in sight -> memory[id] updated;
                                                     #   a remembered building whose tile is in sight and which is destroyed/gone -> removed. Sorted iteration only.
def visible_units(world, faction) -> list[dict]      # NEW: alive, non-cloaked enemy units in sight, sorted by id (seen_enemies()["units"] rows)
def known_enemy_buildings(world, faction) -> list[dict]   # NEW: memory values sorted by id (may be stale: that is the point)
def visible_regions(world, faction) -> set[int]      # NEW: catastrophe regions containing a tile in sight (sample the region table at the sight sources)
# neuro/vision.py re-exports these and adds nothing else.
```

`visibility_quantum` already runs in `HybridWorld.advance`; keep its cadence. Make the heuristic AI use the memory: `ai._known_targets` returns `visibility.known_enemy_buildings` filtered as before (keep its 32-tile "becomes known" rule by seeding the memory from the same sources it used, so behaviour changes only where the old code saw more than the faction's sight). Replace in `HybridEnv.observe`: `enemy_capitals` -> only remembered enemy warehouses; `threats` -> computed from `visible_units`; `known_enemy_buildings` -> `len(known_enemy_buildings)`. `legal_actions["attack"]` lists only remembered buildings.

Tests `WizardRTSHybrid/tests/test_neuro_vision.py`: (a) on a fresh `campaign` world, Red's observation contains no enemy capital and no attack target (homes are more than 32 tiles apart: assert the distance first); (b) move a Red unit (God command `move`, developer profile) next to Blue's warehouse, advance 10 s: Blue's warehouse is in Red's memory and in `legal_actions["attack"]`; (c) kill that unit (`military.kill_unit`), advance 10 s: the memory entry remains (remembered); (d) destroy the warehouse by God `damage`, advance with a Red observer nearby: entry removed; (e) determinism: two worlds, same seed, 10 minutes with AI on, identical `vision.state` after sorting.

Re-record the hash baselines in the same commit (the AI's targeting may change) and say so. Run `run_civilisation_tournament.py --seeds 507 11 --minutes 40 --jobs 2` before and after; put both `summary.json` files under `docs/evidence/neuroevo/m1_vision/` with a three-line comparison. Commit `neuro(T1.1): visibility model for observations and the heuristic AI`.

### T1.2 Successor control (N07)

In `history.split`, after creating the successor: if `world.ai_factions is not None`: when the parent is in `world.ai_factions`, add the successor; otherwise append the successor to `world.__dict__.setdefault("agent_successors", {})[parent]` list. `HybridEnv` exposes `seats_of(faction) -> [faction] + successors (recursive)`; `step` accepts actions for successors and `observe` works for them. Test `test_neuro_successor.py`: force a split (set `SPLIT_*` thresholds low on a world fixture or use the existing split test fixture from `tests/test_civilisation_rules.py`), then (a) with an AI parent the successor issues commands within 60 s (`fstats[successor]` gains `ai_build` or `ai_military`); (b) with an agent parent, `env.seats_of("Red")` includes the successor and `env.apply(successor, build)` is accepted. Commit `neuro(T1.2): split successors are controlled`.

### T1.3 Alive means not collapsed

`HybridEnv._alive(f)` -> `history.state(world)["faction"].get(f, {}).get("state") != "collapsed"`. Add `info["faction_states"]`. Update `test_sim_api.py::test_elimination_terminates_the_faction_and_pays_the_penalty` if it relied on the warehouse rule (keep the penalty semantics). Commit.

### T1.4 Action surface

Already there after v4: `legal_actions` lists the faction's own `wl:` buildings and every `mdy:` machine it has unlocked (`_generated_menu`), attacks only on visible targets, the faction command tier (`world._not_mine`, `faction=` on queue/cancel/move/stop/rally/demolish/deploy/order/ability), versioned hash-checked saves (`SAVE_FORMAT = 2`), and training pacing knobs `era_max_ms` / `era_vp` (do **not** use these in training: full rules only). Extend `HybridEnv.ACTION_OPS` and `apply` with: `belt` (`w.belt(faction, tiles, end_dir, kind)`), `upgrade` (`w.upgrade(faction, building, to)`), `configure` (`w.configure(faction, building, key, value)`), `link_power` (`industry.commands.link_power`), `trade` (`trade.send_caravan(world, faction, wh_id, partner_wh_id, give, want)`, ownership of `wh_id` checked, partner must be a remembered or allied warehouse), `propose` (`diplomacy.propose(world, a, b, state, duration_ms)`), `respond` (`diplomacy.respond(world, offer_id, accept)` only for offers addressed to the faction). Every new branch checks ownership like the existing ones. Add `observe=True` parameter to `step`; when False, return `{}` for observations (saves 1-4 ms per agent per step). Tests in `test_neuro_actions_env.py`: each new op is rejected for a foreign building/unit with `not_yours`, accepted in a small developer-profile fixture where it is legal (use `industry.fixture` for belts and power; two allied factions for trade), and a malformed payload returns `malformed:*`. Commit `neuro(T1.4): full action surface in HybridEnv`.

### T1.5 Episode runner

Create `WizardRTSHybrid/neuro/episode.py`:

```python
@dataclass
class EpisodeConfig:
    seed: int; game_minutes: int = 240; map_size: str = "standard"; profile: str = "campaign"
    agent_seats: tuple[str, ...] = ()            # factions controlled by controllers
    opponents: dict[str, str] = field(default_factory=dict)   # faction -> "plus" | "baseline" | "champion:<id>" | "archive:<id>"
    outbreak_interval_scale: float = 1.0; diplomacy: bool = True; nest_policy: str = "coop"
    checkpoint_game_minutes: int = 30; wall_cap_s: int = 7200
    decision_s: int = 60; boot_decision_s: int = 20; boot_minutes: int = 10; event_min_gap_s: int = 15; tactical_s: int = 5; tactical: bool = False

@dataclass
class SeatResult: faction: str; vp: int; state: str; collapsed_at_min: float | None; fitness: float; tier: str; commands: int; rejected: int
@dataclass
class EpisodeResult: seed: int; end_reason: str; t_end_min: float; outcome: dict; outbreaks: int; seats: list[SeatResult]; control_seats: list[SeatResult]
                     state_hash: str; wall_s: float; vp_replay_ok: bool; ledger_ok: bool; checkpoints: int; decisions_logged: int

def run_episode(cfg: EpisodeConfig, controllers: dict[str, "Controller"], log_dir: Path | None, heartbeat: Path | None = None) -> EpisodeResult
```

Loop: build `HybridEnv(seed, map, agent_factions=cfg.agent_seats, step_ms=1000, max_game_ms=game_minutes*60000, profile)`; `reset()`; set world knobs (`cardset="v2"`, `draft_v2=True`, `diplomacy_enabled`, `nest_policy` per faction, `outbreak_interval_scale`, `ai_policy` for opponent seats: heuristic names map directly; champion/archive opponents are controllers too, so they become agent seats with their own genome); `initial = ledger.snapshot_totals(w)`. Each game second: collect commands from every controller whose scheduler says it is due (strategic, event or tactical), `env.step(actions, observe=False)`, append events to the controllers' filters, every `checkpoint_game_minutes` write `env.save()` to `log_dir/ckpt.pkl` (atomic) and touch the heartbeat. End when `info["episode_over"]` (collective loss or all agent seats collapsed), `game_ms >= horizon`, or wall cap. Before returning: `vp.replay(w) == vp.totals(w)`, `ledger.check(w, initial) == []`, fitness per seat (T4.1), control seats = the heuristic seats (their fitness is logged too). Until T3 exists, a `RandomController` that issues random legal commands from `legal_actions` stands in.

Test `test_neuro_episode.py`: (a) 10-minute episode on the small map with one random seat ends `horizon`, `vp_replay_ok`, `ledger_ok`; (b) `outbreak_interval_scale=0.02` and `loss_outbreaks_total=2` world knob -> `end_reason == "collective_loss"`, every seat tier `C`; (c) a seat whose warehouse is destroyed by God command at minute 2 (developer profile fixture) -> tier `E` with `collapsed_at_min` set; (d) checkpoint file exists after 30 game minutes in a 35-minute run and `HybridEnv.load` of it continues to the same final hash as the uninterrupted run; (e) marked `slow`: a full 240-minute episode with three random seats completes (run once, record wall time in the ledger). Commit `neuro(T1.5): episode runner`.

### T1.6 M1 wrap-up

Full suite; hash gate (re-recorded in T1.1); ledger. **OWNER CHECKPOINT.**

---

## Milestone M2: observation layer and candidates

### T2.1 Static tables

`WizardRTSHybrid/neuro/features.py`, part 1:

* `KIND_INDEX: dict[str, int]` from `freeze.manifest()["entities"]` order (593 rows; index 0 reserved for "unknown"). `KIND_STATIC: np.ndarray [594, 24]` float32 with columns: game one-hot 4 (widelands, openra, mindustry, hybrid), type 2 (building, unit), era 4, size 3 (small, medium, big; units 0), is_military, is_clinic, is_centre (warehouse/MCV/settlers), produces group 6, consumes group 6 (wares from `wl_defs.spec_for_kind` inputs/outputs mapped to `WARE_GROUPS`; Mindustry via `industry.registry.block` consume/output items), minus the log cost total as the 24th column. Document the exact column order in the module docstring; it is part of `OBS_SCHEMA_VERSION = "obs-1.0.0"`.
* `KEY_WARES` (24, fixed order): `log plank granite coal iron_ore iron gold ration bread meat fish wheat water ax brick marble blackwood grout reed cloth smoked_fish smoked_meat beer paper`.
* `WARE_GROUPS` (6): food, wood, stone, metal, cloth_tools, industrial; a `group_of(ware) -> int|None` using `learn.draft_module.WARE_GROUPS` extended with Mindustry items (`mdy.*` -> industrial).
* `CARD_FEATURES(world, faction, card_id) -> np.ndarray[28]` = `learn.draft_module.card_features` (reuse; its first four blocks are static, the rest live).
* `obs_schema_hash()` = sha256 of (`OBS_SCHEMA_VERSION`, `freeze.roster_hash()`, KEY_WARES, the KIND_STATIC column names).

### T2.2 Per-decision feature assembly

`features.py`, part 2: a `FeatureCache` per faction holding dirty sets fed by the controller's event filter, and these functions, each returning float32 arrays of exactly the widths in the design's section 4.3 (N1 32 per building; N2 100 per settlement; N3 28 per unit; N4 102; N5 12; N6 112 given pooled parts; N7 68; N8 50 plus a `[k, 31]` card matrix; N13 `[8, 16]`; N14 `[25, 10]` region matrix plus 13 globals). Every number is scaled as the table says (divisions, `log1p/5`, fractions in [0, 1]); clip to [-5, 5]; `assert np.isfinite`. Settlement membership of a building: `settlements.of(world, b)`; stocks at a centre: `world.stocks[cc_id]`; production and consumption rates: differences of `world.stats["made_<ware>"]`/`"consumed_<ware>"` over the last 5 game minutes (keep a 5-minute ring per faction; the global counters are per world, so attribute per faction from `produced`/`delivered` events filtered by faction, or, simpler and exact, from `world.fstats` if `note_produced` already records per faction: check `world.note_produced`). Threat near a settlement: `ai_plus.force_near` restricted to `vision.visible_units`. Expansion candidates: a visibility-limited port of `ai_plus._expansion_site/_site_value` returning the top 4 tiles with the 8 features listed.

Tests `test_neuro_features.py`: shapes and finiteness on (a) a fresh campaign world, (b) a 20-minute AI world (fixture cached with `envs/_world_cache`-style pickling to keep the test under 60 s), (c) a world where Red has one settlement versus a God-fixture world where Red has 6: the N2 row of the most-threatened settlement (put an enemy unit next to it) is identical in both when the settlement's own state is identical; (d) no feature reads a faction not visible: monkeypatch `vision.known_enemy_buildings` to return `[]` and assert enemy-derived features are zero. Timing test (not asserted, printed): feature assembly for one faction on the 20-minute world under 15 ms. Commit `neuro(T2.1-2.2): feature tables and assembly`.

### T2.3 Candidate generation

`WizardRTSHybrid/neuro/candidates.py`:

```python
@dataclass
class Candidate: head: str; action: dict; features: np.ndarray; key: tuple   # action is the exact HybridEnv.apply payload

class CandidateGenerator:
    def __init__(self, env, faction): ...
    def on_events(self, events): ...            # invalidate site rings of touched settlements
    def build(self) -> list[Candidate]          # H1: per settlement up to 12 legal sites (ring cache, refreshed each game minute or on invalidation) x affordable unlocked kinds from construction.full_menu() + industry.registry.kinds(); cap 96 by (distance, cost)
    def road(self) -> list[Candidate]           # H2: unconnected own buildings -> nearest connected building; settlement links; belt proposals (Modern) between a machine and the nearest warehouse within 12 tiles
    def produce(self) -> list[Candidate]        # H3: (operational factory, unit) pairs where tech.unit_allowed and queue < 5
    def expand(self) -> list[Candidate]         # H4: (founder unit, site) for top-4 sites; plus deploy where legal
    def military(self) -> list[Candidate]       # H5: squads (single-link clusters of idle armed units within 6 tiles) x targets (remembered enemy buildings within 120 tiles, nests in visible regions, own threatened settlements as defend, rally)
    def draft(self) -> list[Candidate]          # H6: current offers
    def trade(self) -> list[Candidate]          # H7: (partner warehouse known and not hostile, template give g / want h) + aid template
    def diplomacy(self) -> list[Candidate]      # H8: propose truce/peace to known factions at war; accept/decline pending offers; break
    def manage(self) -> list[Candidate]         # H9: demolish/dismantle/convert/enhance/upgrade per own building where legal
    def all(self) -> dict[str, list[Candidate]]
```

Every candidate's `action` must be accepted by `HybridEnv.apply` when nothing changed since generation; a rejection is logged as `candidate_rejected` with the reason and the generator learns nothing from it (no heuristics), it just excludes that key for the next 60 s. Test `test_neuro_candidates.py`: on the 20-minute fixture, apply every candidate of every head in a copy of the world (`pickle` the env, apply, discard) and assert at least 95% are accepted; print the rejection reasons for the rest. Timing printed: `all()` under 10 ms per faction. Commit `neuro(T2.3): candidate generation`.

---

## Milestone M3: networks and controller

### T3.1 Genome and networks

`WizardRTSHybrid/neuro/nets.py`. Architecture version `ARCH_VERSION = "arch-1.0.0"`. A `LAYOUT` list in this exact order (name, in, hidden, out):

```
N1 (32,32,16)  N3 (28,24,12)  N2 (100,64,24)  N4 (102,48,16)  N5 (12,16,8)  N6 (112,64,16)  N7 (68,32,12)
N8 (50,32,16)  N8card (31,16,1)  N13slot (16,8)  N13 (17,16,8)  N14region (10,8)  N14 (56,32,12)
N9 (124,64,16)  N10 (63,32,16)  N12 (112,64,57)  N11 (74,32,4)
H0 (41,16,1)  H1 (108,48,1)  H2 (70,32,1)  H3 (84,32,1)  H4 (60,32,1)  H5 (96,48,1)  H6 (49,16,1)  H7 (60,24,1)  H8 (50,24,1)  H9 (100,32,1)
EMB kind embedding (594, 8)   TEMP head temperatures (10,)  
```

Each entry is an MLP `in -> hidden (tanh) -> out (linear)`; two-layer entries have no hidden. Provide `genome_size()`, `slices()` (name -> (start, stop)), `random_genome(rng) -> np.ndarray[float32]` (He init, temperatures 1.0, embeddings N(0, 0.3)), `Nets(genome)` with a `forward_<name>(x)` for each entry operating on 2-D batches, and the pooling helper `pool(X) -> concat(mean, max)`. N12's output 57 = context 32 + memory 16 + priorities 8 + wait 1. Save/load through `persist.py` (T5.3) only. Tests `test_neuro_nets.py`: round trip flat -> modules -> flat exact; forward shapes for batch 0 (returns `(0, out)`), 1 and 500; `sum(sizes) == genome_size()` (expect roughly 75 k; record the exact number in the ledger and in `ARCH_VERSION` notes). Commit `neuro(T3.1): genome layout and networks`.

### T3.2 The controller

`WizardRTSHybrid/neuro/controller.py`:

```python
class Controller:
    def __init__(self, env, faction, nets: Nets, cfg: EpisodeConfig, rng_seed: int, log: DecisionLog | None): ...
    def on_step(self, game_s: int, events: list[dict]) -> list[dict]:
        """Called once per game second by the episode runner. Returns the commands for this second (usually [])."""
```

Scheduler: strategic tick when `game_s - last_tick >= decision_s` (or `boot_decision_s` during the first `boot_minutes`); event tick when the filter saw a trigger kind (design section 5.2) and `game_s - last_tick >= event_min_gap_s`, snapping to the next 5-second boundary; tactical tick every `tactical_s` if `cfg.tactical` (T8). A tick: `features.assemble(...)` -> N1..N14 -> N12 (with the stored memory 16) -> candidates -> heads -> selection rule (design 4.4: all scores on one scale via `TEMP`, issue in descending order every candidate above the wait score, at most one per head, at most 4 per tick, draft exempt; rejected -> try the head's next candidate once). Log each tick to `DecisionLog` (gzip JSONL: `game_s`, trigger, scores of the chosen and the top 3 rejected per head, commands, acceptance). Deterministic: no sampling; ties broken by candidate key order.

Add `train_ai.py play --genome random|<file> --seed 7 --minutes 60 --seat Red --record out.jsonl.gz` (the CLI skeleton, T5.4, may start here as `WizardRTSHybrid/neuro/cli.py`).

Tests `test_neuro_controller.py`: (a) a random genome plays 20 minutes on the small map: every emitted command was accepted or rejected with a reason; at least 20 commands and at least 4 distinct heads used; (b) with all head temperatures huge and wait bias high, zero commands are issued (the wait path works); (c) event tick: destroy an own building by God command, assert a tick within 5 s and the trigger logged. `test_neuro_determinism.py`: two subprocesses with different `PYTHONHASHSEED`, same genome file and seed, 15 minutes: identical final `state_hash()` and identical decision logs. Timing printed: per-tick cost at minute 20 under 15 ms. **OWNER CHECKPOINT** after M3. Commit `neuro(T3.2): controller`.

---

## Milestone M4: fitness, league, manifest, calibration

### T4.1 Fitness

`WizardRTSHybrid/neuro/fitness.py`, pure functions:

```python
@dataclass
class FitnessConfig: survive_base=1000.0; vp_weight=10.0; margin_weight=3.0; elim_base=100.0; elim_time_weight=400.0; loss_base=-1000.0; loss_time_weight=500.0; horizon_min=240.0

def seat_fitness(cfg, end_reason, t_end_min, seat_vp, seat_state, collapsed_at_min, other_root_vps: list[int]) -> tuple[float, str]:
    # returns (F, tier) exactly as the design 8.2: 'S', 'E', 'C'
def advantage(F_candidate, F_control) -> float
```

Permanent VP of a collapsed seat = conquest awards only (`vp.ledger` entries with `winner == f`). Table-driven tests (`test_neuro_fitness.py`) including: worst survivor beats best eliminated beats every collective loss; earlier loss is worse; VP ignored in tier C; cycle completion counts as S at the horizon; ties. Commit.

### T4.2 Manifest and versions

`WizardRTSHybrid/wizard_rts/__init__.py`: add `RULES_VERSION = "rules-2026-10-14"` (bump whenever a rule changes). `WizardRTSHybrid/neuro/manifest.py`: `build(config) -> dict` with git SHA and dirty flag, `freeze.ROSTER_VERSION` and `roster_hash()`, `RULES_VERSION`, sha256 of the `wizard_rts/` tree (sorted file list, contents), `ARCH_VERSION`, `OBS_SCHEMA_VERSION` + `obs_schema_hash()`, `ACT_SCHEMA_VERSION = "act-1.0.0"`, `FIT_SCHEMA_VERSION = "fit-1.0.0"`, the config, hardware (`scripts/probe_hardware.py` logic reused), Python/NumPy versions, seed stream names. `compatible(a, b) -> "same" | "reevaluate" | "incompatible"` by the rule in design 10.4. Tests: changing `RULES_VERSION` -> `reevaluate`; changing `ROSTER_VERSION` -> `incompatible`. Commit.

### T4.3 League

`WizardRTSHybrid/neuro/league.py`: `OpponentMixer(cfg, rng)` returns per game the three opponent seats (`plus` 0.40, `baseline` 0.10, champion 0.25, archive 0.25; falls back to heuristics when the archive is empty), mirrored seat sets A = (Red, Green, Purple) / B = (Blue, Yellow, Orange); `ChampionArchive(dir)` with `add(genome, manifest, evaluation) -> id` (never deletes), `current() -> id`, `BehaviourGrid` 3x3x2 over (conquest VP share, settlements founded, cubes cured + aid delivered) keeping the best fitness per cell; `promotion_decision(paired_results) -> dict` implementing design 7.5 (bootstrap 90% lower bound of the mean paired advantage > 0 and loss rate not higher; sequential stop after 6 games only if decisive). Tests: a candidate with better training mean but a losing held-out record is not promoted; archive never shrinks; mixer is deterministic for a seed. Commit.

### T4.4 Outbreak calibration study (N01)

Script `WizardRTSHybrid/scripts/calibrate_outbreaks.py`: for scale in {1.0, 0.5, 0.35, 0.25}, 10 seeds each (seeds 9000-9009), 240-minute six-`plus` games through a `spawn` pool of 14, using `episode.run_episode` with no agent seats; output `docs/evidence/neuroevo/m4_calibration/summary.md` with P(collective loss), median minute of loss, mean outbreaks, cubes cured, per scale. Choose the largest scale with 20-40% loss; write it into `neuro/configs/full240.json` and `proving60.json` as `outbreak_interval_scale` with a comment field naming the study. If no scale qualifies, write the table and stop: **owner decision**. Budget: 40 games, about 1.5 hours. Commit the evidence and configs.

---

## Milestone M5: evolution loop, persistence, CLI, launchers, reports

### T5.1 Workers

`WizardRTSHybrid/neuro/workers.py`: `GamePool(n, code_dir)` over `multiprocessing.get_context("spawn")`; each job is `(job_id, EpisodeConfig, {seat: genome_path or heuristic name}, log_dir)`; the worker process inserts `code_dir` first in `sys.path` (the run's code copy, T5.4), sets `HYBRID_AI=1`, runs the episode, writes `result.json` atomically, touches a heartbeat file every 60 game seconds; the parent kills a job whose heartbeat is older than `stall_s` or whose wall time exceeds `wall_cap_s`, records `wall_cap`, requeues once. Crash -> `repro.json` with seed, seats, genome ids, config, SHA, traceback; requeue once; second failure -> result `voided`. Test: a job with a deliberately raising controller produces `repro.json` and a `voided` result; a 2-job pool on the small map completes.

### T5.2 Evolution loop

`WizardRTSHybrid/neuro/evolve.py`:

```python
@dataclass
class EvolutionConfig: population=24; mirrored=True; sigma0=0.1; sigma_min=0.01; sigma_max=0.2; module_mask_probs=(0.5,0.35,0.15); full_mask_prob=0.1; adam_lr=0.02; seeds_per_generation=4; seats_per_game=3; imitation_fraction=0.25

class Evolution:
    def __init__(self, run_dir, config, manifest, rng_seed, seed_from: str | None): ...
    def generation(self, pool) -> GenerationSummary:
        # 1. seeds S_g from stream "train" (never from "heldout")
        # 2. children: 12 module-masked noise vectors eps_i, children theta +- sigma*eps_i (sigma per module)
        # 3. jobs: one control game per seed (six heuristic 'plus' seats) + one game per child per 2 seeds (legs alternate)
        # 4. fitness per (child, seed, seat); advantage vs control (same seed, same seat)
        # 5. rank-shaped (centered ranks) OpenAI-ES gradient; Adam step on theta; sigma per module by 1/5 success rule within bounds
        # 6. best child -> promotion queue if its mean advantage > 0
        # 7. checkpoint, logs, prune
```

Imitation seeding (N02): `neuro/imitation.py` fits each head's weights by ridge regression on `(features of the heuristic's chosen candidate, features of the alternatives)` pairs recorded from 20 control games (the recorder is a `Controller` in "shadow" mode that logs candidates but issues no commands while the heuristic plays the seat). Children tagged `seed=imitation`. Tests `test_neuro_evolve_smoke.py`: `population=4`, `seeds_per_generation=1`, 10-minute games, small map, 2 generations in-process (pool of 2): generation summaries written, `theta` changed, checkpoint exists; a second `Evolution` constructed from the checkpoint reports the same generation index and `theta`.

### T5.3 Persistence

`WizardRTSHybrid/neuro/persist.py`: `save_model(path_json, genome, manifest, evaluation)` writes `best_ai.json` (design 10.1) and `best_ai.npz` (one array per module plus `theta`), with the NPZ sha256 in the JSON; `load_model(path_json) -> (genome, meta)` verifies the hash and shapes; `save_checkpoint(run_dir, state)` / `load_checkpoint(run_dir)` (newest valid of the last 3, atomic temp+rename, fsync); `prune(run_dir, cfg)` keeps the last 3 checkpoints, game logs for the last 4 generations and all promotion games, enforces `max_run_gb`. Tests `test_neuro_persist.py`: save/load identical outputs on 100 random inputs; corrupted newest checkpoint -> previous one loads; a model with another `roster_version` is refused; another `rules_version` -> `reevaluate`.

### T5.4 CLI, code copy, run directory

`WizardRTSHybrid/neuro/cli.py` and the thin root `train_ai.py`:

```
train_ai.py train   [--config full240|proving60|smoke|<path>] [--run NAME|auto] [--workers 14] [--population 24] [--episode-game-minutes N] [--hours H] [--generations N] [--seed-from best|archive|none] [--allow-dirty]
train_ai.py resume  [--run NAME|latest] [--hours H]
train_ai.py evaluate --model best|<path> [--games 12] [--outbreak-scale training|1.0|<x>] [--workers 14]
train_ai.py status  [--run NAME|latest]
train_ai.py export  [--run NAME|latest] --out DIR
train_ai.py smoke
train_ai.py play    --genome best|random|<path> --seed N --minutes M --seat Red [--record FILE]
train_ai.py stop    [--run NAME|latest]        # writes the STOP file
```

Semantics the launchers rely on:

* `--run auto` (default for `train`): if `%DMB_RUNS%\neuro\current` points at a run whose manifest is `same` or `reevaluate` with the current code, resume it; otherwise start a new run `neuro/<YYYYMMDD-HHMM>` seeded from `WizardRTSHybrid/neuro/models/best_ai.json` when it exists (`reevaluate` -> the champion is re-evaluated on held-out games first and recorded as such), else random. `current` is a text file holding the run name.
* `--hours H`: stop cleanly (finish in-flight games, checkpoint) when the budget is reached; default 8.
* The run directory copies `WizardRTSHybrid/wizard_rts`, `WizardRTSHybrid/neuro`, `sim/dmb` into `runs/<name>/code/` at creation; workers import from there (design 9.5).
* On every clean stop **and** on every promotion: copy the champion to `WizardRTSHybrid/neuro/models/best_ai.json` + `.npz` (only when a champion exists; never overwritten by a worse one because only promotions change the champion), and write the session report (T5.6). Commit these two model files to git at owner checkpoints only (they are small, about 300 KB).
* Exit codes: 0 clean, 2 refused (dirty tree, incompatible, low disk), 3 crashed with traceback in `runs/<name>/crash.log`.

`neuro/configs/smoke.json` (small map, 10-minute games, population 4, 1 seed, 2 workers), `proving60.json` (60-minute games, population 16, 2 seeds, 14 workers), `full240.json` (design 9.3 values). Test: `train_ai.py smoke` finishes in under 10 minutes on this PC and leaves a resumable run plus a session report.

### T5.5 Windows launchers (root of the repository)

`Train AI.bat`:

```bat
@echo off
rem DuelMasterBattle: evolve the faction AIs. Usage: double-click (8 hours), or "Train AI.bat 3" for 3 hours.
setlocal
cd /d "%~dp0"
if "%DMB_RUNS%"=="" set "DMB_RUNS=%USERPROFILE%\dmb_runs"
set "HOURS=%~1"
if "%HOURS%"=="" set "HOURS=8"
echo Runs are stored in %DMB_RUNS%\neuro. Training for %HOURS% hours (stop early: run "Stop AI Training.bat").
powershell -NoProfile -Command "& { $null = [System.Threading.Thread]::CurrentThread; Add-Type -Name P -Namespace W -MemberDefinition '[DllImport(\"kernel32.dll\")] public static extern uint SetThreadExecutionState(uint f);'; [W.P]::SetThreadExecutionState(0x80000003) | Out-Null; py -3 train_ai.py train --run auto --hours %HOURS% --config full240 --workers 14; exit $LASTEXITCODE }"
echo.
if exist "WizardRTSHybrid\neuro\models\LAST_SESSION_REPORT.md" (
  echo ===== Last session report =====
  type "WizardRTSHybrid\neuro\models\LAST_SESSION_REPORT.md"
)
pause
```

(The PowerShell wrapper keeps the PC awake for the duration, N06; if the `Add-Type` line misbehaves, replace it with `powercfg /requests`-free approach: run `py -3 train_ai.py ... --keep-awake`, implementing keep-awake in Python via `ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)` in the trainer's main thread. Prefer the Python implementation; the bat then simply calls `py -3 train_ai.py train --run auto --hours %HOURS% --config full240 --workers 14 --keep-awake`.)

`Stop AI Training.bat`: `py -3 train_ai.py stop` then prints that the trainer will finish its current games and write the report. `AI Training Status.bat`: `py -3 train_ai.py status` then `pause`. `Evaluate Best AI.bat`: `py -3 train_ai.py evaluate --model best --games 12` then `pause`. `Prove Evolution Overnight.bat`: `py -3 train_ai.py train --run proving --config proving60 --hours 8 --keep-awake` (used once in M6). Test each by hand once and record in the ledger.

### T5.6 Session report and status

`WizardRTSHybrid/neuro/report.py` writes `runs/<name>/reports/session_<n>.md` and copies it to `WizardRTSHybrid/neuro/models/LAST_SESSION_REPORT.md`:

```
# AI training session report — <date> — run <name>

Verdict: IMPROVING | FLAT | WORSE | TOO EARLY TO SAY   (best advantage trend over the last 5 generations vs the 5 before: +x / -x)

This session: generations <a>..<b> (<n> new), <games> games (<control> controls), <sim hours> simulated hours in <wall hours> wall hours (<x>x real time per worker), <workers> workers.
Champion: <id> (promoted this session: yes/no; held-out: mean advantage +<a> [90% lower bound <lb>], collective-loss rate <r> vs control <rc>). Saved to WizardRTSHybrid/neuro/models/best_ai.json.
Collective loss: candidates <p>% of worlds, controls <pc>% (training outbreak scale <s>).

| generation | best advantage | mean advantage | best raw fitness | control loss rate | commands per tick | rejected % | sigma (mean) |
| ... one row per generation this session ... |

Behaviour grid: <k>/18 cells filled (military share / expansion / cooperation); best per cell listed below.
Decision statistics (best child, sampled game): heads used %, commands per tick, rejected %, draft picks taken on time %.
Disk: <gb> GB in the run (cap 20); last checkpoint generation <g>.
To continue: double-click "Train AI.bat" (it resumes this run). To test the champion: "Evaluate Best AI.bat".
Notes: <wall caps, voided games, crashes, anything the owner should know>
```

`status` prints the same header plus the run list. Test: after `smoke`, both files exist and contain every heading.

### T5.7 M5 wrap-up

`test_neuro_storage.py`: run 3 smoke generations with aggressive pruning settings and assert disk below the cap and the parent process RSS flat (within 50 MB). Full suite. **OWNER CHECKPOINT.** Show the owner `Train AI.bat` running `smoke` for two minutes.

---

## Milestone M6: first proof of evolution (60-minute games)

### T6.1 Run

`Prove Evolution Overnight.bat` (config `proving60`: 60-minute games, population 16, 2 seeds per generation, 14 workers, 8 hours; about 8-12 generations expected). Imitation fraction 0.25 (N02). Before starting: `train_ai.py smoke` green; disk and the training outbreak scale recorded.

### T6.2 Judge

Acceptance (design section 12): held-out evaluation (12 games, held-out seeds) of the generation-0 best versus the final generation's best: mean advantage of the final best is higher with a bootstrap 90% lower bound above 0, and it wins at least 8 of 8 paired held-out seeds against the generation-0 best. Produce `docs/evidence/neuroevo/m6_proof/report.md` with curves (generation vs best/mean advantage), the behaviour grid, decision statistics, whether imitation-seeded lineages won, and the verdict. **A run that merely completes fails.** If it fails, diagnose in this order and write the finding: (1) commands per tick near 0 or near 4 constantly (selection rule or temperatures), (2) rejection rate above 20% (candidate generation), (3) advantage variance across seeds larger than between children (increase seeds per generation), (4) sigma collapsed or exploded. Fix, rerun once. **OWNER CHECKPOINT** with the report either way.

---

## Milestone M7: performance pass (hash-equal)

O1-O5 of design 11.5 in order, each a separate commit with `hash_gate check` green and a perf note (`scripts/bench_full_game.py --minutes 60 --seed 7` before and after). Target: 240-minute game under 800 s on one idle core. If T0.3 installed a compiler, record the native A* gain separately.

---

## Milestone M8: tactical controller and triggers

`neuro/tactical.py` (N11, design 4.3 and 5.3): squads within 24 tiles of a visible enemy or hit in the last 10 s; four orders; runs every 5 s reading the cached N6/N10 vectors; included in the genome from the start (its slice exists in `LAYOUT`), activated by `EpisodeConfig.tactical=True` and `evolution` config `tactical=true`. Ablation: 12 paired held-out games with and without; report under `docs/evidence/neuroevo/m8_tactical/`. Adopt as default only if the lower bound of the paired advantage is above 0.

---

## Milestone M9: the 240-minute programme

1. Switch the default config to `full240` (it already is the `Train AI.bat` default; M6 used the proving config explicitly).
2. First overnight run with `Train AI.bat`; next morning read `LAST_SESSION_REPORT.md`; `Evaluate Best AI.bat`.
3. Repeat sessions. The champion archive and the behaviour grid grow; `best_ai.json` changes only on promotion. Commit `WizardRTSHybrid/neuro/models/` after each session the owner wants kept.
4. Every 5 sessions: a short review in `docs/evidence/neuroevo/progress/<date>.md` (champion lineage, held-out numbers at the training scale and at 1.0, strategies in the grid, open problems).

---

## Appendix A: files this programme creates

```
train_ai.py
Train AI.bat  Stop AI Training.bat  AI Training Status.bat  Evaluate Best AI.bat  Prove Evolution Overnight.bat
docs/CONTENT_FREEZE.md  docs/EXECUTION_PLAN_NEUROEVOLUTION.md (this)  docs/ledger/NEUROEVO_PROGRESS.md
WizardRTSHybrid/wizard_rts/freeze.py  freeze_guard.py  sysinfo.py  data/content_freeze.json
WizardRTSHybrid/scripts/freeze_content.py  calibrate_outbreaks.py  bench_full_game.py (exists)
WizardRTSHybrid/neuro/__init__.py vision.py features.py candidates.py nets.py controller.py tactical.py episode.py fitness.py manifest.py league.py evolve.py imitation.py persist.py workers.py report.py cli.py config.py
WizardRTSHybrid/neuro/configs/smoke.json proving60.json full240.json
WizardRTSHybrid/neuro/models/best_ai.json best_ai.npz LAST_SESSION_REPORT.md   (written by training; committed at checkpoints)
WizardRTSHybrid/tests/test_content_freeze.py test_neuro_vision.py test_neuro_successor.py test_neuro_actions_env.py test_neuro_episode.py test_neuro_features.py test_neuro_candidates.py test_neuro_nets.py test_neuro_controller.py test_neuro_determinism.py test_neuro_fitness.py test_neuro_manifest.py test_neuro_league.py test_neuro_evolve_smoke.py test_neuro_persist.py test_neuro_storage.py
WizardRTSHybrid/docs/evidence/neuroevo/<milestone>/...
%DMB_RUNS%\neuro\<run>\{manifest.json, code/, checkpoints/, games/, decisions/, champions/, reports/, generations.jsonl, STATUS.json, STOP}
```

## Appendix B: the owner's view

* **Start or continue training:** double-click `Train AI.bat` (8 hours) or `Train AI.bat 3` (3 hours). It resumes the current run if the code is compatible, otherwise starts a new run from the saved champion.
* **Stop early:** `Stop AI Training.bat`; the trainer finishes its current games, saves, and writes the report.
* **See how it went:** `WizardRTSHybrid/neuro/models/LAST_SESSION_REPORT.md` (also printed at the end of `Train AI.bat`), or `AI Training Status.bat`.
* **Best AI so far:** `WizardRTSHybrid/neuro/models/best_ai.json` + `best_ai.npz`; changes only when a candidate beats the champion on held-out games.
* **Check it independently:** `Evaluate Best AI.bat` (12 held-out games; prints advantage over the heuristic AI and collective-loss rates).
* **Watch it play (later, Godot):** `train_ai.py play --genome best --seed 7 --minutes 240 --record game.jsonl.gz` produces the decision log; a spectator feed into the God Mode HUD is a follow-up, not part of M0-M9.
