# DuelMasterBattle — AUTHORISED LONG IMPLEMENTATION RUN
## Autonomous six-faction civilisation, full Widelands/OpenRA/Mindustry integration, inexhaustible mineral extraction, headless statistical playtesting, balance and God Mode spectator view

**Owner instruction:** 12 October 2026. This document authorises **gameplay implementation, testing, data import, UI/visual repair, documentation, and iterative balancing** without stopping for approval after each checkpoint. It does **not** authorise merging into `main`, discarding local work, hiding failures, or misrepresenting incomplete coverage as completed. Continue autonomously through verified checkpoints for as long as the available session, machine capacity and access permit. If the session must end, leave a clean, documented restart point.

**Repository:** `https://github.com/Joesalmon1985/DuelMasterBattle`  
**Last checked:** branch `feature/hybrid-playtest-fixes-v03`, commit `6ab0a4c0241b` (may be superseded by newer commits by the time this is run). **Inspect the real local HEAD and working tree first.** Follow `CLAUDE.md`, `WizardRTSHybrid/AGENTS.md` where compatible with the owner's latest decisions, and the authoritative design/decision documents.

---

## 1. The outcome I want to SEE, not just read about

After this run, I want to launch the **real Godot game** on my Ubuntu ThinkPad, open **God Mode in spectator mode**, choose **16× time**, and watch six *autonomous* factions inhabiting the *same living world*:

1. Start in **Prehistoric** with basic Widelands economies; workers, foresters, carriers, quarries, farms and warehouses visibly work and exchange goods.
2. **Draft technology cards from era-appropriate packs of up to seven**, with clear timers, card details and unlock dependencies; AI factions draft intelligently without player assistance.
3. **Progress into Historic** through actual VP, settlement growth, conquest and world events—not a developer-only scripted jump—and see the economies and forces materially change as technology unlocks.
4. Advance further to **Modern and Dystopian Future** where feasible during longer watched/headless games. Widelands goods bootstrap real Mindustry drills, belts, power, crafters and military factories; OpenRA and Mindustry military share one battle simulation.
5. **Expand** by constructing and deploying MCVs, supporting distinct territories and settlement economies; **compete** over favourable locations; **build real armies, attack, defend, raze settlements and gain/loss VP**; undergo justified political/economic **splits, declines and collapses**.
6. Suffer **catastrophes/outbreaks that demonstrably affect workers/economy/settlements**, with legible alerts and visible corrective action. Faction AI mitigates crises through its legal economic/military actions; an optional **scripted wizard test agent** can use the wizard's own treatment abilities under the same movement and time constraints. Do **not** silently give each faction magic or direct wizard control in ordinary campaign mode.
7. Show all of this through an **informative but uncluttered God Mode HUD**, visible unit and material movement, era/VP progress, faction status and an event feed. The operator can choose a faction to *inspect* without disabling its AI; separately opt in to issuing commands.

**Non-negotiable:** The headless simulation and Godot presentation are the **same authoritative Python `HybridWorld`**, not separate demonstration scripts that manufacture buildings or decisions. Godot is the rendering/input client. At 16× the world must remain responsive and visually comprehensible on the ThinkPad T460; if measured performance requires lower view range/LOD, optimise without skipping simulation rules.

The usual campaign remains a **wizard-led adventure inside autonomous civilisation**. The RTS is not converted into a player-commanded campaign. God Mode is developer/debug/spectator only. Preserve quests/dungeons/duels/outbreaks, including cross-system effects.

---

## 2. Changes to game design RATIFIED NOW

### D22 — Mineral extraction sites are **inexhaustible**, for both Widelands and Mindustry

This new owner decision **supersedes all older specifications and tests requiring depletion of Widelands mineral mines or Mindustry drills**. In particular it supersedes finite-reserve assumptions in D17/D21, the `mine_exhausted` trigger, `industry/extraction.py`, `industry/sim.py`, AI policies concerning worked-out mines, and tests expecting deposits to shrink. Preserve D21's **single existing resource map**.

- A valid **existing Widelands resource/terrain site** remains the authoritative source location. **No extra Mindustry resource squares or separate geology** are permitted.
- A Widelands **coal, iron, gold or analogous mineral mine** working at a valid deposit **never permanently exhausts that site**. A Mindustry drill also never exhausts it, including when configured to produce copper/lead/titanium from a shared iron-bearing site. Keep the data-driven deposit-to-ware mapping and tech/tier gates.
- For **rock/stone mineral production**, follow the same *no permanently exhausted mineral source* intent where relevant, without breaking quarry workers or visually adding rocks from nothing. If quarry mechanics need a distinct renewable rock-face model, implement and document it clearly. Trees/forestry, wildlife, crops and fish retain their own ecology and reproduction rules; don't make all biological production infinite by mistake.
- A mine/drill can still stop or slow due to **unbuilt site, wages/food, absent worker, lack of power/fuel, input shortage, belt backpressure, blocked roads, occupied output, lack of upgrade card, damage, war, sickness, sabotage, catastrophe, or deliberate shutdown**. Site availability and terrain suitability remain strategically meaningful. Mineral ware production has an **explicit source ledger** (e.g. `mined_from_inexhaustible_deposit`), and all **downstream** manufacturing, stock movement, consumption and unit costs remain strictly conserved. Never counterfeit stocks without an event or claim literal mineral-reserve conservation when the source is now infinite.
- Fix **all** code paths: worker mine programme, generic Widelands imported mines, Mindustry tiered drills, upgrades, headless envs, fixtures, AI replacement-mine heuristics, status text, UI, save/load migration, tests and report metrics. Test long (> 2 hours game time) continuous production without exhaustion, while demonstrating throughput/power/food/transport bottlenecks still work. If an old save has reserve 0, determine whether it is a valid deposit using its original resource **kind/site** rather than treating zero stock as a permanent absence. Do not generate a new mineral tile to recover it.
- **Repair the M3 story.** A real mine running dry is no longer a valid cause. Make the existing miner/dungeon/duel quest arise from a **genuine disruption** (e.g. blocked road, collapsed access, sabotaged machinery, missing delivery, or catastrophe-induced closure), not a fictitious exhausted vein. Completion must remove/repair the real blocking condition, visibly restore production and have exactly-once effects. Do not turn off the story to make this change easy. Update original tests and create new headed/manual tests.

### D23 — The AI war-and-economy world is a first-class acceptance target

A faction cannot pass merely by spawning a scripted showcase building or winning a synthetic headless reward. It must take legal actions from a primitive economy; draft through legal offers; pay for and construct building/road/MCV chains; manufacture and deploy troops; attack/defend; sustain its logistics; and generate documented emergent historical events **without cheating or developer grants**.

### D24 — Headless simulated players and reports drive development

The main feedback loop is repeated, fully simulated, **deterministic headless games driven by transparent heuristic AI players**, paired with real headed Godot tests and manual acceptance. A separate neural-learning framework already exists; retain it, but **do not prioritise costly neural-network training over strong heuristic baseline behaviour**. Neural tests can be used as supplementary adversarial or exploration agents once the core ecology/AI is reliable.

### D25 — 16× God Mode spectator experience and full unit/building usage

Every relevant building and unit in the approved scope of Widelands, OpenRA and Mindustry should ultimately be **constructible, economically supported, simulated, functional in its intended role and AI-usable** once its card/era prerequisites are satisfied. Source imports alone are not implementation. Exclude only units/buildings already explicitly superseded by approved design (e.g. OpenRA refinery/harvester-credit gameplay and superseded Widelands military production) or demonstrably irrelevant source/tooling objects, and document each exclusion. Do not invent a claim that all ~900 existing catalogue entries are working without exercising them. This is a **large, potentially multi-session programme**; implement as much true usable breadth as possible while leaving an exact coverage backlog, rather than superficial wrappers passing trivial tests.

---

## 3. Required sequence of work — execute, TEST, COMMIT, CONTINUE

### Checkpoint P0 — Safety and measured baseline

1. Check branch, `git status --short`, untracked and user-edited files. Do not commit unrelated work (`git add -A` forbidden); preserve local changes. Choose a new feature branch from the latest approved development branch if needed, and note it in status. Never merge or force-push without owner instruction.
2. Read: `docs/DuelMasterBattle_Consolidated_Design.md`, `docs/DECISION_REGISTER.md`, `docs/ARCHITECTURE_CONTRACT.md`, `docs/IMPLEMENTATION_RUN_STATUS.md`, `docs/NEXT_AGENT_HANDOFF.md`, `WizardRTSHybrid/docs/COVERAGE.md`, `WizardRTSHybrid/docs/TRAINING_PROGRAMME.md`, and actual simulation, AI, terrain, economy, construction, tech, history, catastrophe and Godot HUD code.
3. Read pinned `WizardRTSHybrid/sources/manifest.json`. Existing checkouts include Widelands, OpenRA and Mindustry v146. `scripts/setup_external.sh` can recreate them. Preserve pin/provenance and licences. Where original art is clearly usable, import/animate it; do not commit large clone trees, unrelated upstream binaries or unlicensed art. Preserve a compact reproducible local import workflow.
4. Run current regression suites, 3 deterministic strategy seeds, headed smoke and a benchmark. Record **raw outputs, machine specs, SHA and actual elapsed time**. Distinguish pre-existing failures from newly introduced defects. Run baseline tests BEFORE changing code where practical.
5. Add/update `docs/AUTONOMOUS_CIVILISATION_RUN_STATUS.md`, with fixed dates, checkpoints, before/after metrics and outstanding issues. Write a minimal run plan/todo ledger there. Commit baseline/docs if appropriate.

### Checkpoint P1 — Fix the owner's **actual Ubuntu playtest** issues, then integrate them into regression tests

Treat the following as bug reports from **12 October 2026**, not optional subjective opinions:

**P1.1 Wizard movement, collisions, map density.** The wizard currently walks through trees/rocks. Make standing solid trees, rocks, impassable structures and relevant environmental obstacles truly impassable to **both Godot local movement and authoritative Python `set_pose`**. Support walkable cleared tiles after harvest/burning. Synchronise blocker deltas and avoid sending huge per-frame state redundantly. Ensure paths to work sites, quest NPCs, outbreak healers and dungeons remain traversable. Tune initial tree density *especially around settlements, roads and quest spots* without making forestry unproductive or deleting the world's ecology. Add obstacle/navigation headless tests, headed wizard tests and dense-settlement screenshots.

**P1.2 Interaction panels and passive labels.** User screenshot: fire-magic buttons overlap the observation text. Inspect `godot_project/client/world/world_interaction_label.gd`: `_layout_responses()` offsets below description but `_follow()` currently overwrites `_scroll.position` back to `(0,0)` when in response state. Fix robustly, including at T460 viewport sizes/camera zoom. Passive settlement labels overlap severely: fewer labels, short title-only labels, non-overlapping placement/priority, hide distant labels, NPC/quest labels highest priority. Expanded dialogue suppresses others, must remain legible/on-screen. Add automatic rect-overlap test and save **real screenshots**. Do not just resize text to invisibility.

**P1.3 Quest discoverability and completion.** Manual `launch_scenario.sh story` resulted in clicking a red mine and only receiving the generic **Burn it with fire magic** interaction; the miner was not discoverable. Ensure the initiating NPC has a clear portrait/name/quest indicator, reachable tile and unmistakable invitation to talk. Clicking NPC or using `E` works independently from fire-magic labels and can take precedence when appropriate. Make the gallery findable. Complete the revised real-disruption quest manually from wizard walk-up → genuine dialogue → dungeon → puzzle → duel → real world effect → return, with **no teleporting and no direct bypass of UI actions** in the acceptance demonstration (test fixtures may initialise the world only).

**P1.4 Outbreak discoverability and consequences.** Manual `outbreak` showed a purple hex region and withered-ground marker but no discernible healer or treatment UI and no visible change to workers/production. Make the healer locatable and reachable, describe the region, cubes, treatment control and cooldown. Give players an accessible catastrophe status/event panel and in-world visual effects that correlate with actual measured production loss, unrest and/or worker disruption. `T` must visibly initiate a timed action and lower the cube count when valid. The purple hex outline and withered ground must be labelled. Test with/without catastrophe to verify measurable economic effects and changing output after treatment; ensure a penalty doesn't silently become purely cosmetic.

**P1.5 Readable technology drafting.** Current `tech.py` uses 3 offers despite owner's **desired pack of seven**. Design and implement an era-specific technology catalogue with enough meaningful cards to enable up to **seven valid offers** while respecting prerequisites; never duplicate/pad with impossible cards simply to reach seven. Provide an inspectable catalogue per era with unlocks, prerequisites, optional repeat/stock rules and counts. Clear dedicated draft panel and timers: next draft round; how long a live offer remains selectable; what was selected; what it unlocks. Use a configurable default cadence and selection window; don't pretend an unimplemented clock counts down. AI chooses legally and reasonably; developer spectator can inspect a faction's offers; taking *manual control* is a separate explicit action. Do not give the campaign wizard faction RTS command authority. Current prototype has 13 cards across Prehistoric/Historic/Modern and no Dystopian cards; expand real meaningful sets rather than inflating card count cosmetically.

**P1.6 Import genuine available art/animations where licensed.** The user wants available Widelands/OpenRA/Mindustry sprites and animations reused rather than permanent coloured boxes. Inspect pinned upstream artwork and licence/attribution for each asset family; where usable, run repeatable import pipeline; adopt sprite frames/rotations/animation states rather than replacing functionality with static screenshots. Keep labelled coloured geometric placeholder sprites **only where suitable licensed source art does not exist or import is not practical**, and list remaining placeholders. Don't hold back functional work just to paint everything, but ensure the final 16× demonstration is visually comprehensible.

Checkpoint must include focused regressions, one headed screenshot/video sequence for each repaired interaction, and a **human reproduction guide**. Don't stop after this checkpoint; continue.

### Checkpoint P2 — Implement **inexhaustible mineral mining** across Widelands/Mindustry and remove obsolete depletion behaviours

Implement ratified D22 end to end. Update data architecture with **infinite site potential and finite in-flight wares**; do not reset `res_amt` to a misleading magical value or create new ore squares. Ensure AI no longer abandons a site for depletion, and test indefinite concurrent extraction at the same source location with consistent downstream inventories. Preserve mining technology differences, scarcity of accessible sites, rate ceilings, transport limits, power/cost, combat susceptibility and economy incentives. Replace mining-quest trigger and fixture. Update all source documents/decision register (D22–D25), code comments and user-visible info.

Minimum tests: 2+ game hours of Widelands coal+iron operation; 2+ game hours of Mindustry extraction on same physical iron site; mixed simultaneous producers; resource never runs out; starvation and power outages still stop machines; save/replay/migration deterministic; no ware duplication on belts; downstream conservation with explicit mineral source events.

### Checkpoint P3 — Make six **heuristic AI faction players** competent, robust and observable

Audit the existing `ai.py`, `ai_industry.py`, `tech.py`, `territory.py`, `history.py`, `vp.py`, `regions.py`, `construction.py`, `logistics.py`, `military.py`. Upgrade/replace *rules and priorities*, not underlying authority:

- **Economy bootstrap:** independent six-faction plans per Widelands tribe: resource site selection, legal building placement, genuine construction deliveries, supply chain dependency resolution, rations/food, roads, blocked roads, working farms/forestry/mining, upgrading, repairs and queues. Maintain separate settlement stocks and territory; a faction cannot reach into another warehouse or use God commands. No wares/units generated except documented mineral deposits, lawful ecological reproduction, and legitimate starting kit.
- **Tech card strategy:** choose from actual offered cards based on resource bottlenecks, military threats, economy prerequisites and available era; avoid unreachable dependency dead ends; react to era changes. Log every offer, selection, rejection and resulting building unlock.
- **Expansion:** produce/load/deploy MCVs, choose reachable viable sites, connect and support a new settlement. Avoid indefinite retries on impossible spots. Penalise overexpansion that destroys the home economy; preserve autonomous independent outpost logic.
- **Military:** recruit/make historically appropriate units with real inputs, stage squads, scout/identify enemies, attack-move, defend, retreat/repair where supported, target meaningful enemy assets and respond to raids; preserve water/ground/air movement constraints and faction identity. Strategic asymmetry and counterplay matter. OpenRA/Mindustry units must share the existing military clock, targeting and damage engine; no second auto-resolved army game.
- **Catastrophes:** AI governors perceive real local consequences and react with allowed mitigations: reroute supplies, sustain food, shelter or evacuate where modelled, rebuild/defend crucial workplaces, guard/assist a healer if appropriate. **Wizard-only magic remains wizard-only.** For headless crisis-response experiments provide a separate `ScriptedWizardAgent` which travels, talks, treats and duels by the **same public actions, distances, costs and timing** as the human player, not teleport/cheat ops. Faction AI may collaborate indirectly with the wizard; do not silently grant six automatic wizards.
- **Fission and collapse:** splits should come from visible, explainable underlying pressures (separated settlements, economic hardship/unrest, military defeat, political logic). On split, reassign ownership/territory/units/stocks consistently, log cause, preserve active simulations; on collapse, leave ruins and maintain legal VP. Provide deterministic fixtures for rare splits plus naturally emerging cases under longer war/stress runs.
- **Diagnostics:** when an AI does nothing, explain why: missing ware, missing tech, unreached building, incompatible site, unavailable unit, blocked road, insufficient time, command rejected, or waiting on cooldown. AI never repeatedly spams illegal actions without an issue raised.

**One agent does not need to govern a faction through a neural policy to pass.** Prefer transparent rules, robust baselines and measurable performance. More complex RL can come afterwards.

### Checkpoint P4 — Broaden **actual playable content**, source-driven and audited

The user's target is that **all relevant units and buildings can be built and used**, across approved Widelands, OpenRA and Mindustry scope. Start with current `WizardRTSHybrid/docs/COVERAGE.md` and its source catalogue; in the last checked report, only **11/214 Mindustry blocks**, **1/39 Mindustry units**, **153/237 Widelands buildings**, **2/37 OpenRA buildings**, **2/57 OpenRA units** had simulated status, and much worker/liquid functionality was missing. Recalculate from current code; don't assume those counts still hold.

- Establish **uniform usable actor/building/ware registry** with per-definition `imported`, `recipe/cost`, `eligible era/card`, `buildable`, `operational`, `AI usable`, `Python tested`, `Godot rendered/headed tested`, `unsupported/explicit exclusion + rationale`.
- **Widelands**: complete material chains for the five tribes, physical workers/carriers, builder workers, prospectors/miners, specialists, food/rations, trade/territory, and relevant existing buildings. Eliminate placeholder construction/recruitment where imported rules provide real requirements. Automatically probe every declared buildable building type for a valid placement, delivered input, output/use and AI usage; don't claim success from the Lua parse alone.
- **OpenRA**: source-derived valid actors/buildings, production prerequisites, balanced recruitment with Widelands goods, locomotion, pathing, combat weapon behaviour, building attacks, turrets, sea/air units as appropriate; exclude only superseded harvester/refinery economy and other expressly approved exclusions.
- **Mindustry**: keep pinned repository and importers; implement broad relevant category coverage: drills, conveyors, routers, sorters, junctions/bridges, storage, power graphs/generators/batteries, liquid pipes/pumps/coolants, processors/crafters, factories, reconstructors, unit tiers, turrets and other intended devices. Use Mindustry source-derived numbers where meaningful, document converted units and hybrid balance. No independent second economy or map. Machines must show working/blocking/inputs/outputs and units must fight in the shared army.
- **Cards/eras**: each unit/building unlock ties into legible era progression. Historical tech upgrades materially change the units/economy. Avoid granting technology solely because an importer finds a row.
- **Assets**: import/animate actual licensed source assets where practical; precisely record asset origin and placeholders. Test headless build/operation and headed visibility.
- For any remaining definition, record the exact blocker (missing interpreter action, missing input recipe, missing art, physics/pathing, labour, etc.) and a reproducible failing example. **Never artificially mark catalogue items as complete to satisfy a target.**

**Scope management:** True support for hundreds of definitions is very substantial. Extend generic interpreters and registries first, then cover categories systematically, with passing real use cases. If session resources expire, leave an honest incomplete coverage matrix rather than rushing to a fake 100%. Continue autonomous checkpoints until constrained.

### Checkpoint P5 — Statistical headless tournaments and an iterative bug/balance loop

Build an easy-to-run entry point such as:

```bash
python3 WizardRTSHybrid/scripts/run_civilisation_tournament.py \
  --mode standard --seeds 507 11 23 101 102 103 104 105 106 107 \
  --minutes 120 --factions 6 --report-dir "$HOME/dmb_runs/civ_2026-10-12"
```

Make exact CLI flags reflect real implementation, print `--help`, do not write the example as if it already exists. It must invoke the **normal complete HybridWorld update**, not `envs/_world_cache.py` fast-mode which skips workers/AI, and not a `test_showcase` or `HYBRID_ERA_MS` rig. Use standard production/AI paths. Seeded runs must be reproducible from the same code+configuration; log special fixtures separately and never mix them into normal-play statistics.

**Modes, with clearly separated reports:**

1. `peace-economy`: six factions start primitive with ordinary rules, warfare suppressed via an explicit *test mode only*, verify no basic-economic starvation/loops and tech advancement.
2. `war`: normal six-faction competition, all rules and economic prices intact; eliminations and conquest are legitimate outcomes, **not test failures**.
3. `crisis`: normal economy and warfare plus outbreaks with natural cadence; compare no wizard intervention vs an autonomous **legal wizard pilot** on paired seeds. Test policy response, blocked production, effect sizes, time to mitigation and whether the simulation recovers.
4. `historical-cycle`: run until meaningful era transitions / faction splits / victory or time/cycle horizon; **no artificial developer era force**. Support resume/checkpoint and bounded runtime. Use deliberate deterministic fixture tests to validate rare code paths, but report them separately from naturally generated tournament frequencies.
5. `mixed/all-features`: broadened source content, unlocked by the AI over time; use a separate scenario test for advanced tech that an ordinary campaign has not reached yet. Keep every result correctly labelled.

**Progressive budgets:** First run 3 seeds × 15–30 game minutes and fix crashes/obvious stalls; then ≥10 seeds × ≥60 game minutes in peaceful and war; then ≥10 seeds × ≥120 game minutes in normal war/crisis/historical mode **where machine budget permits**, with at least one deliberate full-cycle stress run. Keep sessions bounded, configurable, parallelism restrained on the ThinkPad, results/checkpoints outside repo if bulky. Log elapsed wall time, peak memory, and speed. Long runs are opt-in: do not make routine tests take an hour.

**Per-game / per-faction telemetry, captured at sensible game-time intervals, preferably 60 game seconds:**

- seed, SHA/config, map size, policy version, faction/tribe, start and end time, survival, split/collapse reason;
- era index/time, *reason* for era advancement (VP vs stall guard), global progress, remaining cycles;
- tech rounds, actual 7-card offer contents or fewer where eligible, picked cards, missing prerequisites, unspent offers;
- settlement/MCV counts, deployment success/rejections, territory, VP found/conquered/lost, split chronicle;
- buildings by source game and category; attempted/completed/operational/stalled/destroyed, jobs/workers, stockouts and waiting causes;
- goods by ware: mineral source totals, inputs, outputs, net/available/cargo/consumed, warehouse inventories, delivered construction resources, negative or unexplained stock;
- armies by type, recruited, active, killed, damaged; damage to enemy units/buildings/settlements; offensive/defensive orders; target-selection failures; lost fleets;
- industry: drill rates (unlimited site), belt throughput/backpressure, power supply/demand, liquid flow, crafter uptime, real unit output;
- catastrophe: kind, hex location, cubes, severity, production-factor losses, unrest, spread, mitigation decisions, wizard treatment, recovery time, terminal losses;
- simulation time, wall time, real-time multiplier, p50/p95/max tick latency, snapshot/update latency, RSS/peak memory, test timeouts/errors.

**Report outputs:**

- `run_manifest.json` with exact SHA, seeds, configs, machine specs, original/unmodified baseline hashes;
- `games.csv`, `factions.csv`, `timeseries.csv`, `events.jsonl`, `coverage.csv`, `validation_failures.json`;
- a **self-contained browsable HTML report** (matplotlib/plotly as installed, or simple HTML/SVG if dependencies unavailable) showing population/settlement growth, stock/throughput, building/unit composition, VP/tech/era timeline, faction survival/war, split/collapse history, catastrophic impacts and recovery, CPU/performance, inter-seed spread and confidence intervals where meaningful;
- an accessible **plain-English written analysis** (`BALANCE_REPORT.md`), with reproduction seeds/timestamps, actual vs expected behaviour, measured disparities, regression risk, changes made, and remaining issues. Explain *why* numbers indicate a bug/balance problem; don't optimise one arbitrary scalar reward.

**What should trigger bug fixes, rather than be hidden as a 'balance choice':** AI build deadlocks, permanently starved required chains, unconstructible intended buildings/units, illegal or free inventory, loss of supplies in transport, duplicate VP or units, inexplicable no-op armies, broken naval pathing, no tech growth, era advancement only due to stall guards, simultaneous resource claims in another economy, seed-dependent crashes, non-deterministic replay, no catastrophe effects, healer not reachable, splits orphaning armies, no visual feedback or display overlap.

**Balance iteration:** Identify top 3–5 proven systemic problems, fix their actual cause, add regression tests, rerun the same paired seeds, report before/after and check other strategies didn't regress. Then repeat. Adjust production rates/costs, draft cadence, military stats, settlement incentives and catastrophe impacts via labelled configurable data; preserve source provenance. Protect against an exploit where infinite mines let factions spam armies without power, workers, food, transport or construction costs. Use cross-faction fairness metrics without making all strategies identical. An aggressive AI eliminating another faction is valid, but a faction that cannot function due to a broken supply graph is not.

**Minimum evidence targets, use as diagnostic thresholds rather than reasons to fabricate results:**

- Zero critical exceptions, negative stocks, impossible unit spawns, double-counted VP, or state-hash mismatch in the tournament run.
- All six factions build physically operating primitive economies and draft eligible cards in the **peace** scenario; set realistic completion windows from observed build and draft cadences, and publish any faction-specific stalls.
- Across 10+ normal-play seeds, aim for **≥8/10 reaching Historic through normal VP progression** within 60 game minutes and **≥6/10 reaching Modern** within 120 game minutes. If these are not possible under the rules, diagnose why and adjust the *economy and incentives first*, then document any proposed VP threshold/cadence change; never force an era change invisibly or silently redefine metrics.
- Military forces of multiple factions visibly make and receive legal combat orders; meaningful battles with measured casualties and asset damage occur in war mode; legitimate losses allowed.
- At least one real six-faction run shows viable **MCV expansion** and one documented natural **split or collapse** across an adequately sized long-run sample; use deterministic stress fixtures to cover rare fission paths even if natural frequency is low. Don't require every seed to split.
- With catastrophe enabled, show a **measured production/unrest difference** vs paired no-catastrophe seed, and measurable improvement/recovery from a legal response. Treating cubes must change both the region and economy; if lack of a wizard makes some outbreaks unmanageable, report it as intended gameplay limitation rather than granting faction AI magic.
- Headless standard-map speed should remain sufficient for meaningful tournaments (previous reported ≈32× realtime/58 MB peak on the T460, though code/content changes will affect this). Report any drop and profile hotspots; never compromise physics to inflate speed.

### Checkpoint P6 — **Player-visible** 16× God Mode spectator acceptance

Implement/document a simple command from repository root such as:

```bash
WizardRTSHybrid/scripts/launch_scenario.sh autoplay
```

This should launch **a normal primitive campaign world** in developer God Mode with **spectator, not faction takeover**. It should start or allow selection of 16× time (and a means to slow/pause). If `autoplay` doesn't exist, implement and document it; don't invent terminal success output. No staging resources; no pre-unlocked cards; no `HYBRID_ERA_MS` fast-forward fixture; no debug-spawned military. Use a **documented seed** shown by the tournament to be representative, and permit `HYBRID_SEED` for user variation.

**God Mode spectator HUD should let me see:**

- Era and **why it is progressing** (VP earned since era began/threshold, elapsed time, outstanding tech); new card rounds with **up to seven options**, draft interval/expiry and eventual picks;
- six faction colours, tribe, current settlements/VP and power/food/mineral/military status at a glance; faction selection for **inspection only** by default, with explicit **Take Control** / **Release AI** separate from viewing;
- economy visually advancing: actual Widelands workers/carriers, road construction, buildings completing, stock changes, advanced Mindustry belts, fluids/power/factory progress where implemented;
- military units moving to targets and fighting, attack/conquest notifications and ruined structures, MCVs travelling/deploying, splits/collapses with a readable explanation;
- catastrophe visible and labelled (hex outline/hazard type/cube severity, impact on named workplaces, healer quest/treatment, faction reaction), with no mystery unclickable withered patches;
- camera pan/zoom, speed controls, unobstructed unit/building inspection, no overlapping labels, and reasonable FPS. Provide a **recent-event timeline** and optional per-faction graph/status panel, not a forest of permanent labels;
- ability to switch from spectator to Wizard Mode and back without world reset or losing entities. The wizard should be blocked by solid trees/rocks, and story/healer interactions should be easy to find.

Add a headed **`run_hybrid_autoplay.gd`** or equivalent that launches *the real game*, watches **16×** through meaningful game time, captures **timestamped** screenshots and state checkpoints for primitive start → first draft → operational new technology → successful MCV founding → first real battle → first catastrophe and reaction → first natural Historic transition, and ideally Modern. Where events are stochastic, use recorded seeds and condition-based waits/timeouts instead of inserting event records or skipping simulation. The test must fail if a required event does not occur in its documented limit. Also provide **human launch instructions** and estimated wall-clock viewing time under observed 16× conditions.

For another machine, ensure the custom `GODOT=/path` override still works and asset import directions are reproducible. A headless test alone **does not** satisfy this checkpoint.

---

## 4. Quality, tests and reporting standards applying to EVERY checkpoint

- **One authoritative state**: if an entity is visible in Godot, it exists in real snapshot/state. No duplicate virtual armies, economy stores or special Godot-side time. Do not disable economy/workers/AI for acceptance tournaments. Deliberately accelerated Godot headed tests may control `speed`, but must not skip Python simulation quanta.
- **Honest automation:** Regression/coverage counts must mean the claimed behaviour was actually exercised. Source rows imported ≠ executable; headless episode completion with `_world_cache.economy=False` or `place_wizard_near` ≠ player-traversable. Keep these fast unit environments for specialist training, but clearly separate from **full-simulation** end-to-end evaluation.
- **Reliability:** Deterministic seeds, `PYTHONHASHSEED`-independent replay, save/load continuity, negative-ware and double-spend asserts, idempotent settlement VP and split/collapse receipts, no infinite loops/stalls. Test two different map sizes and all five tribes across six factions.
- **Performance:** Profile actual hot spots (AI pathfinding/retries, snapshot size, expanding actor count, industry belt updates), implement data/LOD/culling judiciously and establish per-checkpoint before/after timing. Avoid silently weakening simulation to pass performance. Preserve queued-input responsiveness at 16×.
- **Art and licences:** Reuse pinned official clone source code and art only with appropriate licences, notices and provenance. Generate deterministic import artifacts and keep source repos gitignored. Use functional simple sprites as fallback; placeholder label must be honest.
- **Test preservation:** Run existing hybrid pytest, legacy sim tests, Godot headless tests, 17+ headed tests, import/pin/source parity tests, new full gameplay tests, one long multi-seed tournament and reported player-level Ubuntu manual scenarios. If one suite rewrites compiled content, clean up **only** generated files known to be modified by that suite; don't reset unrelated user changes.
- **Commits:** Create small meaningful commits after each verified checkpoint. Maintain `AUTONOMOUS_CIVILISATION_RUN_STATUS.md`, a new `docs/evidence/civilisation/README.md` and `docs/NEXT_AGENT_HANDOFF.md` with exact SHA, tests, failures, metrics, files changed, current checkpoint, next task. Do not merge `main`.
- **No false completion:** On hitting token/context/session constraints, leave build/tests green when possible, describe remaining work, commands to resume, never pretend every actor or era is complete. If performance on T460 limits a specific long test, record the constrained result and permit a stronger machine to reproduce.

### Preferred launch/test entry points (adapt/extend, do not delete)

```bash
# Fast baseline headless sanity
python3 WizardRTSHybrid/scripts/run_all_scenarios.py --suite smoke

# Existing Python regressions
python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py

# Existing headed tests, graphical Ubuntu session required
WizardRTSHybrid/scripts/run_headed_suite.sh campaign campaign_dev industry story outbreak eras war god

# Existing complete headless benchmark
python3 WizardRTSHybrid/scripts/bench_sim.py --map standard --minutes 10 --seed 507

# New work to build: headless tournament, metrics report, genuine 16× spectator playback
python3 WizardRTSHybrid/scripts/run_civilisation_tournament.py --help
WizardRTSHybrid/scripts/launch_scenario.sh autoplay
```

### Final answer to owner must contain

1. **The single command** to watch a **real six-faction AI game at 16×** on Ubuntu. Explain spectator vs controlling factions.
2. One-sentence state for each of: inexhaustible Widelands mines, inexhaustible Mindustry drills, tree/rock collisions, readable labels, 7-card draft UI, player-completable quest, accessible healer, outbreak production effect, reusable licensed art/animations.
3. Exact **code SHA, branch**, tests run and **pass/fail** results, headed screenshot paths, and which behaviours were actually seen.
4. **Statistical tournament report** links/paths and a short evidence-driven narrative of economies, tech, eras, expansions, wars, splits/collapses, outbreaks and performance over multiple seeds; explicit counts for VP-driven vs stall-driven transitions.
5. **Coverage matrix:** number of relevant imported buildings and units from each source vs **actually operational, AI-used, Python-tested and headed-verified**. A list of unimplemented/blocked categories. No claim of completion without evidence.
6. Bugs and balance issues found, fixes made, measured before/after, known failures and next priorities.
7. A concise **Ubuntu manual checklist** the owner can use to confirm that the world visibly progresses from Prehistoric → Historic and later eras, with an estimate of watch time and map seed.

**Approval:** You are authorised to execute these instructions and keep going across checkpoints autonomously until blocked by time/session/machine resources. Prioritise a complete, truthful, watchable **living civilisation simulation** over superficial feature counts. No approval stop after P0/P1/P2/etc.; use commits and handoff documents to make each step resumable. Do not contact me for routine implementation choices. Escalate only real owner decisions that would contradict these instructions or the established wizard-game identity.
