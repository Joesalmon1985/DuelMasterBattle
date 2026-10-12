# Programme plan v2: full content, assets, industrial revolution, catastrophes, neural factions

Status: **PROPOSAL for owner review. Nothing here is implemented.** Written 12 October 2026 on `feature/hybrid-playtest-fixes-v03` (HEAD `5c8ea6d`). No dependency was installed, no training was run, no gameplay file was changed.

**Relationship to `PLAN_ECONOMY_TECH_ERA_PROGRAMME.md` (v1).** v1 answered an earlier brief. This brief changes enough that where the two disagree, **v2 wins**. The differences are listed in section 12. The measurements in v1 section 1 still stand.

Evidence is cited by file or by a command that reproduces it. Measurements made for this plan used throwaway scripts in the scratchpad (not committed); section 3.3 gives the commands to repeat them.

---

## 0. Read this first: three findings that change the plan

1. **The machine I can see is not a Windows PC.** This session runs on `joe-ThinkPad-T460`, Ubuntu (Linux 6.8). I cannot inspect a Windows PC from here. What I measured is in section 2. The repository and its notes (`docs/WINDOWS_HANDOVER.md`, `*.ps1`) show you also work on a Windows machine that has .NET and the Red Alert content. The plan is therefore written for **two hardware tiers** and starts with a hardware probe you run on the Windows PC (section 2.3). Anything in the training plan that depends on core count, RAM or a GPU is a parameter until that probe has run.
2. **Speed is the binding constraint on everything the brief asks for**, especially neural-network training. A 75-minute six-faction game with about 500 buildings and 110 units runs at about 5x real time on this CPU, falling as the game grows (profile in section 3.3). A 180-minute game costs about an hour of one core. Full-game reinforcement learning at that speed is not feasible. The plan puts two performance programmes in front of the learning work and designs the learners to need far fewer full games (section 9).
3. **The imported catalogues are incomplete, and the asset pipeline is further from "complete original animation" than the coverage tables suggest.** Verified against the pinned upstream sources (section 3.1): 25 Mindustry units and about 53 non-environment Mindustry blocks (Erekir units, large walls, shield projectors, radar, world processors) are not imported; 5 Widelands markets are not imported; the existing OpenRA art covers about 20 of 92 actors, bakes turrets into the body frame, and 3 infantry types and 2 tanks use alias placeholders because the Red Alert archives that hold them have an encrypted header the importer cannot read. There is no layered Mindustry unit or machine-component rendering at all.

---

## 1. Programme goals restated as testable outcomes

| # | Outcome | How it will be proved |
| --- | --- | --- |
| G1 | One authoritative simulation containing the full Widelands civilian economy, the full OpenRA roster and the full Mindustry roster, with conserved wares and real transport | Catalogue audit vs upstream; per-entity functional tests; ledger conservation tests (section 4) |
| G2 | Four eras, each opened by one seven-round draft; VP ends eras; leftover-pack rule | Property tests, replay, tournaments (section 5) |
| G3 | A real industrial revolution in Modern and a Mindustry military in Dystopian | Throughput and obsolescence tests (section 6) |
| G4 | Catastrophes that can end the game for everyone, and a reason to cooperate | Loss-probability sweeps by policy (section 7) |
| G5 | Original artwork and animation, visibly correct in the Godot client | Asset ledger plus automated visual proofs (section 8) |
| G6 | God Mode tech/card inspector built on authoritative data | Headed tests (section 8.6) |
| G7 | Neural-network factions that beat the improved heuristic AI | Paired, held-out, multi-map evaluation (section 9) |
| G8 | Long headless runs fast and stable enough to train on | Performance gates (section 10) |
| G9 | Reliable unattended execution on Windows | Resume/recovery tests (section 11) |

---

## 2. Hardware and environment

### 2.1 What I measured (this ThinkPad, Ubuntu)

| Item | Value |
| --- | --- |
| CPU | Intel i5-6200U, 2 cores / 4 threads, 2.8 GHz max, 3 MB L3 (laptop, thermally limited) |
| RAM | 15 GiB total, about 8 GiB available while Claude Code and a browser are running |
| GPU | Intel HD 520 (integrated). No NVIDIA GPU, no CUDA |
| Disk | 234 GB, **92% full, 19 GB free** (CLAUDE notes require at least 10 GB free) |
| Software | Python 3.12.3, NumPy 1.26.4, Godot 4.5.1 (Linux build in `~/godot451`), Wine present; **no** PyTorch, no .NET, no compiler checked in this plan's probes |
| Headed Godot | About 7 fps on the full map (`CURRENT_STATUS_AND_GAPS.md` G11) |

### 2.2 Consequences

* This machine is good for development, tests and short runs. It is **not** a training machine. About 3 cores of simulation at a few times real time yields on the order of 100 full 180-minute games per day, and fewer as late-game cost grows.
* Disk is a hard risk: logs, checkpoints and replays must be pruned or moved to another drive (section 11.4).
* There is no GPU, so every learning design in section 9 has a CPU-only mode.

### 2.3 What I cannot see, and how the plan closes the gap

Milestone P0 adds `scripts/probe_hardware.py` (standard library only, plus optional `nvidia-smi` / `wmic` / PowerShell queries) and a `.ps1` wrapper. You run it once on the Windows PC (`! py -3 WizardRTSHybrid\scripts\probe_hardware.py --out hardware_windows.json` from a Windows session). It records CPU model, physical and logical cores, RAM, GPU model and VRAM, free disk per drive, power plan, Python/Godot/.NET/MSVC/Rust presence, and a short single-core and all-core simulation benchmark. The result is committed as evidence and the plan's parameters in the table below are then fixed.

| Parameter | Tier A (T460 class) | Tier B (typical desktop: 8+ cores, 32 GB, NVIDIA GPU) | Set by |
| --- | --- | --- | --- |
| Simulation workers | 3 | physical cores minus 2 | probe |
| Learner device | CPU | CUDA if torch finds a GPU | probe |
| Concurrent headed Godot | 1 | 1 | probe |
| Model size cap | about 1-2 M parameters | 5-20 M | VRAM / RAM |
| Overnight run length | 8 h | 8-72 h | owner |

---

## 3. Current state

### 3.1 Content catalogues verified against the pinned sources

Verification method: counted upstream definitions in `external/` with the commands in section 3.4 and compared with the imported JSON. Imported counts come from `wizard_rts/data/*.json`.

| Source | Upstream (pinned) | Imported | Gap |
| --- | ---: | ---: | --- |
| Widelands buildings (`data/tribes/buildings`) | 244 (178 production, 31 military, 17 warehouse/port, 11 training, **5 market**, 2 partially_finished) | 237 | 5 markets (needed: trade) and 2 construction-state buildings |
| Widelands workers / wares | 161 / 131 | 156 / 128 | 5 workers, 3 wares |
| Widelands ships | 5 | 0 as entities | |
| OpenRA Red Alert rules | structures 38, vehicles 20, infantry 24, aircraft 9, ships 6, plus civilian/husk/fake definitions | 92 actors / 45 weapons | The roster must be defined by an explicit filter (section 4.2); the other mods (`cnc`, `d2k`, `ts`) are in the checkout and are out of scope unless you say otherwise (Q4) |
| Mindustry blocks (`Blocks.java`, v146) | 395 definitions, of which about 130 are floors, terrain walls, props and ores | 214 | **about 53 buildings missing**: large walls (14), `scrap-wall` sizes (4), `door-large`, `shielded-wall`, `radar`, `shield-projector` (2), `large-shield-projector`, `beam-link`, `core-shard`, `thruster`, `heat-reactor`, `slag-centrifuge`, `launch-pad`, `interplanetary-accelerator`, `illuminator`, `canvas`, `world-processor`, `world-cell`, `world-message`, the sandbox sources and voids, and several Erekir turrets |
| Mindustry units (`UnitTypes.java`) | 64 definitions | 39 | **25 missing**: Erekir tanks (stell, locus, precept, vanquish, conquer), Erekir legs/air/naval/support (merui, cleroi, anthicus, tecta, collaris, elude, avert, obviate, quell, disrupt, evoke, incite, emanate, manifold, assembly-drone), neoplasm units (renale, latum) and missile types |
| Mindustry items / liquids | 22 / 11 | 22 / 10 | `neoplasm` liquid |

Two notes on the brief's wording:

* "Every Mindustry building, unit, item and liquid, including logic, payload and specialist systems" includes the **Erekir** tech tree that lives in the same source files. v1 proposed excluding logic, payload and mass-driver blocks; **v2 reverses that** (section 4.4).
* The pin is Mindustry v146 (September 2023). Newer builds exist. The plan keeps v146 unless you choose to re-pin (Q3), because a re-pin invalidates every comparison test.

### 3.2 What works (inherited from v1 and unchanged)

The square-grid world, the generic Widelands interpreter (153 of 178 production sites run in isolation), conserved wares and the ledger, an OpenRA combat core, a Mindustry slice (11 blocks, 1 unit), VP ledger, eras, unrest/split/collapse, hex-region outbreaks and blight nests, a stable tournament harness with paired seeds, six headless training environments, and 338 passing tests at the last verified commit. See v1 section 1 and `CURRENT_STATUS_AND_GAPS.md`.

### 3.3 New measurement: where the time goes

Profile: six `plus` AIs, campaign profile, seed 507, standard map, 75 game minutes of warm-up, then 180 game seconds under `cProfile` (profiling roughly doubles the cost; use the proportions, not the absolute time).

State at minute 75: 497 buildings, about 109 units, 252 workers, 476 carriers. Unprofiled wall clock: 15 min in 25 s, 30 min in 85 s, 45 min in 173 s, 60 min in 291 s, 75 min in 436 s (about 10x real time early, about 5x by minute 75). The v1 180-minute evidence run shows about 1x real time after minute 120.

| Share of 66 s profiled | Area | Notes |
| ---: | --- | --- |
| 32% | `forestry_quantum` (worker walking and programmes, trees) | `worker_quantum` 454,857 calls; `tree_quantum` 1,800 calls at 2 ms |
| 29% | `military_quantum` | `_unit_step` 194,841 calls; `_scan` 273,154 calls; `_walk` 152,778 |
| 16% | AI (`ai_plus.decide`, `_settlement_step`, `_can_pay`, `_makes`) | repeated affordability scans |
| 13% | `production_quantum` | |
| 12% | `logistics_quantum` | `waiting_for_this_road` called 444,082 times |
| **12%** | **`territory.command_centers` and `territory.settlement_of`** | **273,000 calls in 180 game seconds (1,500 per second) for data that changes a few times an hour. Pure redundancy, a one-line cache** |
| 16% | `dict.get` itself | 40.8 million calls: a symptom of per-entity dict rows; points to structure-of-arrays |

Conclusion: the first 2-4x is algorithmic (caches, dirty flags, spatial indexing) with no change in behaviour. Beyond that the representation (a dict per entity, Python loops per entity per tick) is the limit, which is why section 10 includes a compiled-kernel stage.

### 3.4 Commands that reproduce the audits

```
# Mindustry blocks/units missing vs source: see section 3.1 (regexes over core/src/mindustry/content/{Blocks,UnitTypes,Items,Liquids}.java)
python3 WizardRTSHybrid/scripts/audit_catalogues.py        # to be added in P0; prints the table in 3.1 from the pinned trees
find WizardRTSHybrid/external/widelands/data/tribes/buildings -name init.lua | wc -l
```

### 3.5 Assets: what exists

`godot_project/client/hybrid/art/` is 25 MB: Widelands 3,846 files, OpenRA 906, Mindustry 28, terrain 97, plus `catalogue.json` (1,978 items).

| Source | State | Gap against the brief |
| --- | --- | --- |
| Widelands | Building idle/working sheets, worker walk sheets in 8 directions, immovables, wares, terrain, carriers; player-colour handling partial | No audit of "every animation the Lua declares" vs "every animation imported"; ships, markets, build/dismantle animations unverified |
| OpenRA | About 20 actors (`1tnk 2tnk 3tnk 4tnk apc arty jeep mcv stnk v2rl`, `e1`, `barr weap fact ftur gun pbox proc tsla`, bullets and small effects). Vehicles are 32 facings with the **turret composited into the body frame** (`import_openra_units.py`). Infantry `e2 e3 shok` and tanks `ttnk ctnk` are **alias placeholders** because `hires.mix` and `expand2.mix` use the encrypted Westwood header and `mix_read.py` has no key derivation (docs/BLOCKERS) | 70+ actors without art; no independent turret; no infantry stand/run/shoot/die sets; no aircraft rotors; no ships; no build-up ("make") animations; no damage states beyond one frame; no effects library |
| Mindustry | 14 block PNGs and 3 unit PNGs, **single images** | Mindustry units are layered (base, cell, independently rotating weapons, treads, legs, rotors); machines are layered "drawers" with rotators, liquids, heat, flames. None of this is imported or rendered |
| Team colour | Hard-coded per faction for some sprites | A general mechanism (palette remap for OpenRA, tint mask for Mindustry/Widelands) is missing |

The Red Alert content packages are on this machine (`~/Videos/.config/openra/Content/ra/v2`: `conquer.mix hires.mix temperat.mix snow.mix interior.mix allies.mix russian.mix local.mix lores.mix expand/ ...`), so no download is needed; reading them is the blocker (section 8.3).

### 3.6 AI and training: what was tried and what it taught

* Heuristic AIs: `ai.py` (baseline) and `ai_plus.py` (plus). In 36 paired games per side `plus` scores VP 4.39 vs 2.94 and wins 9.5 vs 2.5 of 12 games (`docs/evidence/civilisation/war90_e`). `plus` is the bar to beat.
* RL experiment (`scripts/rl_experiment.py`): linear policy, seven macros, cross-entropy method. It "won" 5 of 6 held-out seeds by exploiting a cheap reward (territory) and never recruited, attacked or defended (p = 0.22).
* Standard-budget run on six small environments (`TRAINING_PROGRAMME.md`): duel and outbreak policies reach the scripted level but not beyond it; quest is memorised; **dungeon fails (5-10% vs expert 100%)**; the cross-system REINFORCE policy is worse than every scripted baseline.
* Lessons I take from this: (1) learn **on top of** scripted skills, not raw clicks; (2) never trust training reward alone (already your instruction); (3) the existing NumPy MLP is adequate for imitation but not for set-structured inputs such as card packs; (4) the single biggest failure was horizon and sample cost, which is the speed problem again.

---

## 4. Architecture for the full vision

### 4.1 The content graph (carried over from v1, extended)

A single compiled `ContentGraph` (new package `wizard_rts/content/`) merges the three importers into one schema of **entities** (building, unit, ware, liquid, worker, resource, effect), **recipes**, **cards** and **assets**. Behaviours are implemented once per **component class** and parameterised by data. v1 section 2 describes the model and the static checks; the changes for v2 are:

* **A card unlocks one or two entities** (one building, one unit, two buildings, two units, or one of each), as the brief says. The card generator pairs entities by rule (a unit with the building that makes it, a building with its chain partner such as a mine and its smelter) and applies hand overrides recorded with reasons.
* **Every entity carries an asset contract** (the list of animation states it must have, derived from the source: section 8.2) and a **functional contract** (section 4.5). An entity is not dealt in packs until both are satisfied.
* **Eligibility, not exclusion.** Content that cannot yet be `functional` is listed as `pending` with its blocker, never dropped from the catalogue and never counted as done.

### 4.2 Rosters, defined by explicit filters

| Era | Content that cards can unlock | Defined by |
| --- | --- | --- |
| Prehistoric | All **non-military** Widelands buildings (production, warehouse/port, market), workers, wares, resources, transport (roads, second carriers and animals, waterways, ferries, ships) | Widelands `tribes/` minus `militarysites` and `trainingsites` |
| Historic | All OpenRA units and all OpenRA buildings **except those primarily about power generation or resource extraction** | RA `rules/*.yaml`; excluded buildings are listed by name with reasons: `powr apwr fpwr` (power), `proc silo harv` (extraction/storage of credits). `fix`, `dome`, `atek`, `stek`, `gap`, etc. stay |
| Modern | Mindustry industrial blocks, power, liquids, logistics, units of the **support** class that act as workers (`mono poly mega`), plus **enhanced** OpenRA units | `Blocks.java` minus turrets and unit factories of the military roster (see 4.3) |
| Dystopian | The full Mindustry military roster (T1-T5, Serpulo and Erekir), military turrets and factories, remaining specialist blocks | `UnitTypes.java`, remaining `Blocks.java` |

The rosters above contain a few judgement calls (which Mindustry factories belong to Modern; which OpenRA tech buildings count as "power"). Each call is a row in a generated `rosters.md` the owner can edit; the compiler refuses an entity that is in no era or in two.

### 4.3 Component classes (target: about 45)

Production programme, extractor (drill/pump/beam drill/fracker/wall-crafter), conveyor family (conveyor, titanium/plastanium/armoured, junction, router, sorter, overflow/underflow, bridge, stack, duct family), liquid network (pump, conduit, router, junction, bridge, tank), power (source, sink, battery, node/beam node, diode, thermal/solar/consume/nuclear/impact), heat network (Erekir), unit factory, reconstructor, assembler (Erekir), **payload network** (payload conveyor, router, loader/unloader, mass driver), turret (item, power, liquid, continuous, laser, tractor, point-defence), projector (mend, overdrive, force, regen, repair tower/turret), storage and unloader, core/settlement centre, wall/door, **logic** (processor, memory, display, switch, message), scenario/sandbox (sources and voids, God Mode only), Widelands worker housing and market, OpenRA support power, garrison, aircraft, naval.

### 4.4 Where this brief changes earlier exclusions

* **Payload systems are required, not optional.** Mindustry reconstructors (T2-T5) accept a unit as a payload from a factory or payload conveyor. Without payload transport there are no T2-T5 units. Mass drivers also give factions a real long-distance item transport between distant settlements, which feeds the dispersed-territory pressure in section 5.
* **Logic is in scope.** The plan implements a deterministic subset interpreter of Mindustry's `mlog` (`LExecutor`/`LStatements`: set/op/jump/read/write/control/sensor/radar/ubind/ucontrol/uradar/draw/print/wait/end/getlink/packcolor ...). Factions' AIs can load programs from a small data library (for example "switch off the smelter below 20% power", "route sorter outputs"). Displays render the real draw buffer. This is real behaviour with simulation effects and tests, not a decoration. Estimated cost: one wave.
* **Erekir is in scope** (heat, beam nodes, ducts, assemblers, neoplasm hazards, 25 more units).
* **Sandbox blocks** (`item-source`, `power-void`, `payload-source`, ...) are marked `dev_only`: functional, usable by God Mode and tests, never dealt in packs. They are listed, not hidden.
* **Widelands military and training sites** are excluded because the brief says "non-military" (this matches D05). They are listed as `excluded` with that reason.

### 4.5 Definition of "functional" (the no-fakes rule)

An entity is `functional` only when every item below has a test id recorded in `feature_status.json`. The coverage report is generated from those ids and fails CI if an id does not resolve.

1. **Schema**: compiles; no unsupported command.
2. **Isolated behaviour**: a laboratory world builds it from a flagged test grant, supplies inputs by real delivery and checks the observable result.
3. **Connected**: in a scenario, inputs reach it by the real transport and its outputs reach a consumer.
4. **Draftable**: its card is reachable and unlocks exactly its entities.
5. **Used by an AI**: in a seeded tournament an AI builds or produces it without a grant, or it carries a justified `ai_unused: reason`.
6. **Visible**: its asset contract passes (section 8) and a headed test shows it rendered in the right place.

### 4.6 Simulation core refactor

Dict-per-entity rows stay for rarely-touched state. The hot entity classes (units, carriers, workers in motion, trees, conveyor items) move to **structure-of-arrays** with ID indirection, behind the same accessor API, so game code is unchanged and a hash-equality test proves identical state before and after (section 10).

---

## 5. Eras, drafting, victory points

### 5.1 Draft phase (per era)

* At the start of each era the dealer builds one pack of seven per faction in the ring. **Selection 1 occurs at the era start, then every six game minutes**, so selection 7 is at +36 minutes and the phase "closes" at about 42 minutes.
* A faction picks one card from the pack it holds, then passes the rest to the next faction in the ring. The ring direction alternates by era (left, right, left, right). A faction that does not choose within the window receives a deterministic default pick (logged `draft_default`), so the ring never stalls and the AI/NN decision interface has a hard deadline.
* A card unlocks one or two entities.
* There is no drafting between phases. The remainder of an era is development with what was drafted.
* **Unlock set** = foundation set ∪ entities of drafted cards. Placement and queueing already route through one gate (`kind_allowed` / `unit_allowed`); it becomes a set lookup.

### 5.2 Card supply per era

A phase deals 42 cards (7 x 6) plus bonus reserves. The Prehistoric catalogue holds on the order of 100+ cards, so a single game sees well under half of it, and a faction picks 7. Three rules keep this playable:

1. **Pack composition.** At least 60% of each pack's cards are from the current era; the rest are undrafted cards from earlier eras (so a faction can recover a missed chain). The dealer guarantees each pack holds at least two cards that are immediately useful to its first holder (completing a chain for something it holds or enabling something in the foundation set).
2. **Complementarity by design.** Card generation pairs entities (unit with factory) and the dealer deals at least one producer-side card in the world for every unit card dealt, so the "powerful unit but no factory" outcome is a strategic choice rather than an accident.
3. **Trade makes sparsity survivable.** A faction without a smelter can still buy iron from one that has (markets, caravans, ships, mass drivers). This is why trade (section 7.3) is part of the core loop, not an extra.

Coverage across the corpus is measured over many games: "every card has been dealt in at least N of M games, and drafted at least once" (section 8.5). It is **not** claimed that one faction in one game can reach every building; the brief itself implies it cannot (7 picks).

### 5.3 Paper and bonus picks that never take from other factions

v1 let the bonus pick come from the same pack, which removes a card from the neighbour. The brief forbids that. Revised mechanism:

* **Paper** is a hybrid ware (`dmb.paper`): none exists in the pinned Widelands or Mindustry data. Chain and costs are as in v1 section 3.5, with the data in `content/hybrid_overrides.json` and recorded in `SOURCE_REUSE.md`.
* The **scriptorium** (Historic card; Prehistoric chain parts are reed and water via the Widelands crafts families) holds up to 6 paper and has a scribe worker entity.
* At the start of a round, a faction whose scriptorium is operational and holds at least 2 paper receives a **bonus hand of three cards** drawn from a **reserve deck** that exists beside the circulating packs. It picks one; the other two are discarded. Paper is consumed on the pick. The circulating packs are untouched, so no other faction's normal selection is reduced or reordered.
* At most one bonus pick per round. Several scriptoria raise the paper buffer, not the number of picks.
* The reserve deck is sized at deal time (3 cards x number of scriptorium-capable factions + margin) and its draw is deterministic from `(seed, era, round, faction)`.

### 5.4 VP and ending an era

* VP are as today: +1 per standing settlement (an undeployed MCV or settlers' wagon is not one), +1 per enemy settlement destroyed, idempotent per ledger key.
* **Era end.** An era ends when a faction's **current VP** reaches the era threshold `T_e` (candidates and the study in 5.6), or when the world reaches the stall guard (a long fallback so a stuck world cannot hang; reported as a non-natural transition). Combined VP do not count.
* **No minimum duration.** Per the brief there is no minimum era length. Instead a short **evaluation tick** (VP is evaluated once per game second) and a **sustain requirement of 60 game seconds** at or above `T_e` guard against a single frame of captured-and-lost VP. This is a debounce, not a duration floor, and its value is a tunable parameter that can be set to zero.
* **Leftover-pack rule (as specified).** If the era ends before round 7:
  1. Everyone keeps the cards already drafted.
  2. Each faction with **current VP >= 8** receives all cards remaining in the pack it holds at that instant.
  3. Each faction below 8 VP loses the cards in its held pack.
  4. Packs of collapsed factions are discarded.
  5. The next era's draft phase begins.
* **VP at the instant of transition.** VP are read at the transition tick after the sustain window. A faction cannot change its VP between the trigger and the leftover distribution (the transition is atomic within one economy quantum).

### 5.5 Splits, collapses and the ring

* **Split** during a phase: the successor is inserted next to its parent; it inherits the parent's drafted cards; it takes over the **parent's current-round pack only if the parent has not yet chosen**, otherwise it waits and receives a pack at the next round formed from the reserve deck (so the ring grows without destroying a circulating pack). VP are counted per resulting faction at the moment of the split.
* **Anti-exploit.** A faction may not split in the final 60 seconds before a pending threshold crossing, and the leftover rule reads VP **after** the sustain window, so a split cannot be timed to strand a pack. A test replays logged phases with random splits injected.
* **Collapse**: the faction's held pack is discarded; its seat closes at the next era.
* **Cycle reset** (full four-era cycle): ring and cards are discarded as today.

### 5.6 Choosing the thresholds, and the runaway question

Study design (run in the tournament harness once the no-card economy and uncapped expansion exist):

* Candidate `T_e` per era: {8, 10, 12, 14} x {flat, rising-with-leader}. The leftover threshold stays 8 as specified.
* Measurements per setting, 30 seeds per cell, mirrored starts:
  * distribution of draft rounds completed before the transition (is early termination reachable but not the norm?),
  * leftover cards actually awarded per transition and their pick-over quality (the last cards in a pack have been passed through up to six hands),
  * tech lead: number of cards held by the leader minus the median, and whether the lead persists to the next era,
  * VP-to-win correlation: does the first faction to trigger an era win the cycle (target: well under 70%),
  * catastrophe exposure: does a very early end skip the collective-survival phase.
* Candidate anti-runaway levers, to be adopted only if measurement shows a runaway: higher `T_e` in later eras; the next era's pack order starting with the lowest-VP faction; a small draw bias in the next era toward cards that complement the weakest factions' holdings; hegemon unrest (v1 section 6.3); leftover cards limited to those compatible with the receiver's tribe. None of these is a minimum duration.

The expected effect is already visible from the rule: the leftover cards are the least-desirable ones after several hands, and only factions with at least 8 VP benefit, so the reward is real but bounded. The study decides whether that is enough.

---

## 6. Industrial and military revolutions

### 6.1 Resource model for the military roster

Each OpenRA unit gets a **physical recipe** from the Widelands economy (conserved wares, a build time, a producer building, and a prerequisite chain). The initial recipes are derived by a transparent rule, not guessed:

* OpenRA cost class → ware mix: infantry by role (food + timber + textile + simple metal tool), light vehicles (planks + iron + coal), heavy vehicles (iron, coal, gold, manufactured components such as gears or tools produced by Widelands workshops), aircraft (cloth, metal, rope), ships (planks, iron, rope, cloth). The base rule is in a table `military_recipes.csv` owned by the balance workbook (`docs/Widelands_OpenRA_Economy_Combat_Design_v01.xlsx` is the owner's starting point and will be read as input).
* The cost of the ware mix is calibrated so that a unit's **relative cost** matches its OpenRA cost ratio, using Widelands ware "values" derived from the production chain depth of each ware (a ware that needs a 5-building chain is worth more). The calibration is a script with a unit test.
* Different units therefore need food, timber, metals, textiles and manufactured components in different proportions, so economy shape determines which units a faction can sustain.

### 6.2 Modern: why Widelands becomes obsolete (and not by deletion)

Obsolescence must **emerge from numbers the simulation actually computes**. Four mechanisms, all tunable data:

1. **Throughput gap.** A Widelands site is one worker cycling a programme (tens of seconds per item). A Mindustry drill, crafter or unit factory on belts runs continuously. The importer already reads the real Mindustry rates; the plan defines an **industrial index** (items per game minute per settlement for the wares that military recipes consume) and tests that a Mindustry chain exceeds the Widelands equivalent by at least a stated factor (initial target 5x) at comparable build cost.
2. **Recipe shift.** Enhanced OpenRA units, and OpenRA production in Modern, require **manufactured components** (silicon, plastanium-class alloys, steel-class intermediates mapped through `ware_map`) that no Widelands building makes. A Widelands-only faction can still build Historic units but cannot build enhanced ones.
3. **Production speed.** Powered, automated factories build units several times faster than the Historic queue (the "substantially faster" requirement): the unit factory component takes a power multiplier and an input-buffer multiplier, both from data.
4. **People are the constraint.** Widelands food chains stay necessary for workers and soldiers' upkeep. They do not vanish; their share of total output shrinks. Mindustry needs initial investment paid in Widelands goods (already the rule) and power.

**Decisions the faction must make** (so that industrialisation is not a button): which Widelands chains to dismantle for refund (a fraction of cost back through the demolish command), which to keep for food and textiles, where to place drills on the existing deposit layer, how to power them (fuel, solar, thermal), how to route belts, liquids and payloads, and when to stop investing in armies to fund the factories. The heuristic AI and the neural controller both play this as an **industrialisation module** (section 9).

**Acceptance (G3).** Paired seeds, same map: an industrialising faction produces at least three times the military value per game minute of a non-industrialising faction by 30 minutes into Modern; a Widelands-only faction fails to build any enhanced unit; Widelands buildings still exist and operate (nothing is deleted by rule).

### 6.3 Dystopian

Mindustry units T1-T5 and specialists cost advanced items, power and liquids and are produced through factory → reconstructor payload chains. Their stats come from the pinned source; the plan requires a **round-robin duel matrix** (headless, cost-normalised) to show Dystopian units beat comparable OpenRA units by a stated margin at equal cost, and that no unit class (air, naval, legged, support) is dominated everywhere.

---

## 7. Catastrophes and cooperation

### 7.1 Current system

Hex regions (`regions.py`), cubes added every 10 game minutes, spread rules, an outbreak when a region overflows, **eight outbreaks end the cycle** (`terminal_loss`), blight nests as immobile hostile actors with era-scaled health (`nests.py`), workplace disruptions (`disruption.py`), unrest coupling (`society.py`). The wizard is the only treatment. Factions can already kill nests with ordinary combat.

### 7.2 Redesign for collective loss

* **Counters.** Keep the cumulative outbreak counter and add a **per-era counter**. Loss triggers on either exceeding its threshold: `L_era` per era or `L_total` across the cycle. Both are data.
* **Collective loss** ends the cycle for every faction: no winner, final VP irrelevant. This is the shared negative outcome that the neural controller's global reward uses.
* **Thresholds are calibrated, not guessed** (section 7.4).
* **Response toolkit available to factions without the wizard:**
  * *Military*: destroy nests (exists); a new "quarantine" order for garrisons that holds a region.
  * *Containment infrastructure*: a hospital/healer building family (Widelands has healers' equivalents in Atlanteans/Frisians/Empire; others use the shared hybrid `dmb.clinic`) that removes cubes in its radius at a rate paid in food, medicine wares (herbs, honey, etc. from the Widelands economy), and a worker entity.
  * *Resources*: medicine wares and rations as cure inputs; Modern adds Mindustry-made "vaccine" items; Dystopian adds sterilisation turrets that damage neoplasm nests.
  * *Trade*: wares and cure sales between factions.
  * *Recovery*: cleared regions regain production; disrupted workplaces repair as today.
* **Escalation by era.** Nest health, spread cadence and kinds scale by era from `data/outbreaks.json`, with a Dystopian neoplasm variant that uses the Erekir `neoplasm` liquid and units (`renale`, `latum`).

### 7.3 Diplomacy and trade (new core system)

Today there is a single global `ai_aggressive` switch and caravan trade (`trade.py`, 0.7 trades per game). The brief needs cooperation that can lapse back into war. Minimal design:

* **Relations**: per pair `war`, `truce`, `peace`, `alliance`, with expiry and explicit breaking. Units do not attack across `truce`/`peace`/`alliance`; units may enter allied/truce territory for a declared **intervention** (needed to kill a nest in a rival's region).
* **Offers**: structured, discrete messages (propose truce, request intervention, offer wares for wares; cards are not tradeable in this programme, Q10) with deterministic evaluation hooks for both heuristic and learned agents.
* **Markets**: the five Widelands markets, caravans, ships and mass drivers carry wares between settlements and factions under their own capacity limits.
* The heuristic AI gets a simple cooperative rule (help contain when the collective loss counter exceeds a fraction of the threshold and the helper can afford it), which defines the baseline the learned diplomacy module must beat.

### 7.4 Calibrating thresholds (the method)

Define four reference policies: *ignore* (no containment), *selfish* (contain only inside own territory), *cooperative* (heuristic from 7.3), *oracle-ish* (cooperative with full information). For `L_era ∈ {4, 6, 8, 12}` and `L_total ∈ {8, 12, 16, 24}` run 30 seeds each and record the probability of collective loss by era and the time to loss. Targets: *ignore* loses in most games, *selfish* loses in a meaningful minority, *cooperative* rarely loses. These targets are the definition of "tension between competition and survival". The calibrated values are written to `data/outbreaks.json`, with the run id of the study in a comment.

---

## 8. Original assets, animation and visual proof

### 8.1 Principle

An entity's **asset contract** is generated from the source's own sequence declarations, so "complete" is a diff, not a feeling: `declared sequences − imported sequences = ∅`. Permanent placeholders and borrowed sprites are not completed assets. The current `alias_placeholder` mechanism stays only as a labelled temporary state that the coverage report counts as missing.

### 8.2 What each source declares

| Source | Declared by | Contract items |
| --- | --- | --- |
| Widelands | Lua `animations`, `spritesheets`, `working_positions`, worker `walk_*` | per building: idle, working, build, dismantle, unoccupied; per worker: walk in each direction, work animations, with player-colour masks (`_pc`) |
| OpenRA RA | `mods/ra/sequences/*.yaml` and `rules/*.yaml` | per actor: stand/run/shoot/die/idle/prone frames by facing (infantry 8 facings, vehicles 32), turret frames and offsets, muzzle flashes, `make` (construction) sequences, damaged and critical-damage frames, building `idle`/`active`/`build-top`, aircraft rotors, ship facings, projectile and explosion sequences |
| Mindustry | `core/assets-raw/sprites/**`, `Draw*` drawers in `Blocks.java`, `UnitType` fields (`weapons`, `treadRegion`, `legCount`, `engines`, `rotors`), `Fx.java`, `Bullets.java` | per block: base, top, bottom, rotator(s), liquid region, heat region, flame, weave, conveyor frame strips; per unit: body, cell (team tint), outline, weapon mounts with offsets and independent rotation, treads, legs, rotors, engine flames |

### 8.3 Import pipelines

1. **Widelands**: extend the existing Lua importer to emit a *contract manifest* and report each declared animation missing from the art folder; import ships, markets, build and dismantle animations. This is a coverage task, not new research.
2. **OpenRA**:
   * Decrypt the Westwood MIX header. Two routes, in order of preference: (a) implement the published key derivation in `mix_read.py` (RSA with the Westwood public key to recover the Blowfish key, then Blowfish for the index; the algorithm is public and the public key string is in OpenRA's `MixFile` source; this needs a pure-Python Blowfish and big-integer RSA, about 150 lines, no new dependency), or (b) on the Windows PC use `OpenRA.Utility` (already scripted in `import_assets.py`). Route (a) is preferred because it works on both machines and is reproducible without .NET.
   * Read palettes (`temperat.pal`, `snow.pal`, `interior.pal`) and the **player-colour remap range**; emit images as **indexed + remap mask** so recolour is done in a shader for all six factions, instead of baking six copies.
   * Keep **body and turret as separate layers** with the sequence's offsets so a turret rotates independently of the hull.
   * Import muzzle flashes, projectile and explosion sequences, `make` animations (reverse for dismantle), damaged states, building overlays (`weap` door, `fact` animations, radar dish spin, helipad, airfield).
   * Shape format: one atlas per actor + a JSON of `{sequence: {start, length, facings, tick, offsets}}` parsed from the YAML rather than hand-written.
3. **Mindustry**:
   * Import every referenced PNG from `assets-raw/sprites` with its region name.
   * Parse the `drawer = new DrawMulti(...)` constructors and `UnitType` mount lists into JSON "drawer programs". There are about 40 `Draw*` classes; each becomes a small renderer in Godot (`DrawRegion`, `DrawRotator`/`DrawSpinning`, `DrawLiquidTile`/`DrawLiquidRegion`, `DrawHeatRegion`, `DrawFlame`, `DrawWeave`, `DrawPistons`, `DrawGlowRegion`, `DrawBlurSpin`, `DrawCells`, `DrawPlasma`, ...). Programs are data; the renderer interprets them with the authoritative state (progress, warmup, liquid level, power status).
   * `Fx.java` effects are code, not images. Each effect used by a bullet, block or unit becomes an **effect program** (particles/lines/rings with lifetime and easing) reproduced from the Java definition; the plan counts the effects actually referenced and ports those.
4. **Licensing record**: every imported file gets a row in `asset_ledger.csv` (source, path, SHA-256, tool and version, licence, permission note, date, contract item satisfied). `LICENSES.md` and `ASSET_INVENTORY.md` link to it. A test fails if a shipped art file has no ledger row, or a ledger row has no file.

### 8.4 Rendering features the Godot client must gain

Per-entity layered rendering with: facing → frame selection (8/16/32), independent turret and rotor angle driven by authoritative state, palette-remap/tint shader for faction colour, animation state machines (build, idle, work, damaged, destroyed) driven by sim state, projectile and effect pools, aircraft altitude and shadow, naval facing and wake, conveyor/belt animation synchronised to belt state, liquid fill and heat/glow layers.

The simulation must **expose the state the renderer needs** (turret angle per unit, working/idle phase per building, belt flow, liquid levels). Today units carry `facing` only. Adding `turret_angle`, `anim_state` and `visual_state` to the snapshot is part of M-V1 and has a determinism test (these fields enter the state hash only if gameplay depends on them; aiming already does, since targeting is simulated).

### 8.5 Visual and animation tests (proof, not file existence)

Each test is a headed Godot script that talks to a fresh sim, so it can assert what is **rendered**, not what is imported.

| Test | Proof |
| --- | --- |
| **Specimen sheet** per entity | Render each declared sequence for N frames at fixed camera/zoom; compare against the frame images in the atlas (pixel-exact for unscaled sprites). Stores golden hashes in `docs/evidence/visual/` |
| **Facing** | Order a unit to move in each of 8 headings; sample rendered frame index each tick; assert it equals the expected facing frame for the heading the **simulation** reports; assert the pixel region differs between opposite headings |
| **Turret independence** | Place a tank, move it east while its target is north; assert hull frame = east, turret frame = north-direction frame; rotate target and assert only the turret layer changes |
| **Working animation** | Run a production site; assert animation frame advances while `working=true` and stops when starved (compare consecutive frames) |
| **Construction/damage/destruction** | Drive a building through `constructing → complete → damaged(<50%) → critical → destroyed` and assert each state's frame set appears |
| **Position** | Entity world tile → screen pixel → inverse-projected back equals the sim tile; footprint corners drawn on the right tiles |
| **Faction colour** | Render the same unit for each faction; assert the remap region's hue differs and the non-remap pixels are identical |
| **No placeholder in view** | The inspector's "missing art" filter must be empty for every `functional` entity; a test fails on any `alias_placeholder` or `drawn_shape` asset for a card that can be dealt |
| **Animation frame checks without a window** | Where practical, the same selection logic runs as a pure GDScript function under `godot --headless` (frame index for facing/state) so most of the above can also run in CI without a GPU |

Headed screenshot tests are slow on Tier A (about 7 fps); they are grouped, run after each asset wave, and gate only milestones that touch rendering.

### 8.6 God Mode inspector (technology, cards, assets)

A Godot panel backed by new server queries, all computed from the authoritative world:

* `inspect.catalogue`: every card (id, name, era, unlocked entities, prerequisites, family, rarity), with entity asset keys and contract status.
* `inspect.factions`: per faction held cards with era, round, whether it was a bonus pick, and for each unlocked entity the **produced count and first-use time** (new `produced_<entity>` counters in `world.stats`, recorded where buildings and units are created, with a conservation test).
* `inspect.draft`: current phase, round number, time to next round, each faction's pack contents (God Mode only), bonus-pick status and paper, VP table, the threshold, and the **consequence of an immediate era transition** computed by calling the real transition function on a copy of the state (leftover cards each faction would receive or lose).
* Views: catalogue grid with filters (faction, era, card, source game, draft status, production status), card detail with the real imported art, **animated previews** (play any sequence), **direction previews** (rotate 8/32 facings; turret angle slider), **building animation previews** (idle/working/build/damaged/destroyed), a "missing or placeholder art" filter, and an "unproduced after drafted" filter for debugging chains and AI behaviour.
* The previews use the same renderer as the world (one code path), so a preview that looks right proves the in-game rendering path, and a broken animation is visible in one place.
* Tests: a headed script opens the inspector for each source game, selects a sample of cards, asserts the preview texture ids equal the entity asset keys from the catalogue, screenshots three states per sample, and verifies that every displayed number matches the simulation snapshot at the same tick.

---

## 9. Neural-network faction AI

### 9.1 Position

I recommend a **hierarchical, modular controller built on the heuristic AI's own skills**, trained by imitation first, then reinforcement learning in progressively larger scenarios, then league self-play. The previous full-game experiments failed for reasons that this design addresses directly (horizon, sample cost, raw action space, reward exploitation).

### 9.2 Architecture

```
          ┌──────────────────────────── Strategic coordinator (every ~3 game min) ───────────────────────────┐
          │ inputs: faction summary vector, VP table, era/draft state, catastrophe counters, threat map         │
          │ outputs: priority weights over modules + budget split (wares, workers, build slots) + stance        │
          └────────┬──────────┬───────────┬────────────┬───────────────┬───────────────┬──────────────┬───────┘
                   │          │           │            │               │               │              │
               Drafting    Economy &    Military    Trade &        Catastrophe    Industrialisation   (Wizard-facing
               (set/attn   placement    (production  diplomacy     containment    & replacement       interactions:
               over pack)  (ranker)     + tactics)   (offers)      (allocation)   (sequence)          later)
                   │          │           │            │               │               │
                   └──────────┴───────────┴── scripted skills / macros (existing AI helpers) ───┴───────────────┘
                                                      │
                                           validated simulation commands
```

* **Macros, not clicks.** Each module outputs a choice among legal, parameterised **skills** (build X near Y, expand to site Z, queue unit U at factory F, send squad S to target T, propose truce to P). The skills are the existing helpers (`_place_ranked`, `_find_expansion_site`, `_station`, `_pick_target`, `ai_industry`), refactored behind a common `Skill` interface with a legal-mask generator. This keeps the action space small and the game mechanics intact.
* **Observation encoders**: entity-set encoders (attention/pooling over buildings, units, sites, cards, regions) rather than the 50-number flat vector. Cards are encoded from the content graph (era, tags, unlock embeddings, prerequisite status), which lets the drafting network generalise to cards it has not seen.
* **Drafting module**: a small attention network over the cards in the pack, conditioned on the faction state vector and the goal weights from the coordinator. Trained first to imitate the heuristic drafter (v1 section 3.6 scorer), then improved with outcome-based RL: the reward is the **realised use** of a pick (built, produced, contributed to VP/strength) over the following window, plus denial value, estimated by branching rollouts from saved states (the simulator supports save/load and deterministic replay).
* **Economy and placement**: a learning-to-rank scorer over candidate sites/buildings generated by the legal-action machinery.
* **Military**: two parts: (a) *what to produce* (unit mix as a function of enemy composition and wares), (b) *what to do with squads* (attack/defend/retreat/target choice). Pretrain (b) on the abstract combat environment with Lanchester-style fights and the real OpenRA numbers, then tune in full games.
* **Trade/diplomacy**: discrete offer selection with population-based training, since the opponent model matters; evaluated against scripted partners first.
* **Catastrophe containment**: extends the existing outbreak environment to multi-faction: where to send forces, whom to ask for help, what to stockpile. Trained against the collective-loss reward.
* **Industrialisation**: a sequence policy over replace/invest/dismantle decisions, trained on a **Modern-start scenario** (a faction with Historic infrastructure and a tight resource budget) where the industrial index and 30-minute military output are the measured outcome.
* **Coordinator**: a small recurrent policy over module-level priority weights and stance. It is trained **last**, after the modules are competent, with a multi-objective reward (below).

### 9.3 Training methodology (staged)

1. **Instrumentation first**: unified feature extractor; skill interface; trajectory recorder that logs `(observation, legal mask, chosen skill, heuristic's choice)` per module from tournament games. Disk budget: stored compressed, rotated (section 11.4).
2. **Imitation (behaviour cloning + DAgger)** of `plus` per module, evaluated *per module* against the heuristic module with the rest of the faction heuristic ("module-swap tests"). A module may enter the next stage only if it is no worse than the heuristic module, with a stated margin, on held-out seeds.
3. **Per-module RL** (PPO with action masks, or for the drafting module a contextual-bandit/Q-learning variant since decisions are rare and independent enough) in cheap scenarios: drafting-only (short games, rest heuristic), industrialisation (Modern start), catastrophe (multi-faction outbreak environment), military (scripted economies with fixed armies), economy (first 40 minutes).
4. **Joint fine-tuning** with all modules active and a frozen coordinator that uses fixed priorities.
5. **Coordinator training**, then end-to-end fine-tuning at low learning rate.
6. **League self-play**: a population of checkpoints plus `baseline`, `plus` and scripted variants; prioritised fictitious self-play (opponents sampled by how often they beat the current learner); mirrored starts across the six homelands and five tribes; maps: the generated seeds plus the imported Widelands maps; asymmetric catastrophe conditions.
7. **Distillation to deployment form**: weights exported to `.npz`; **simulation workers use a NumPy inference path** with no PyTorch import, so rollouts are not slowed by framework start-up and Windows packaging stays simple. PyTorch is used only in the learner process (a dependency decision, section 17 Q6).

### 9.4 Rewards

Training reward is shaped from **terms that cannot be exploited by a degenerate policy**, each logged separately: settlements and VP (small), economic output per class, military value produced and lost (net), tech utilisation (picked cards actually used), catastrophe contribution (counterfactual: cubes cleared by this faction), cooperation outcomes (collective survival, shared). A **global terminal term** dominates: collective loss is strongly negative for every faction; cycle completion is positive. Reward weights are fixed per stage and recorded in the run manifest. Selection and reporting never use reward, only outcome metrics below.

### 9.5 Evaluation

* **Opponents**: `baseline`, `plus`, the previous champion, the previous 3 checkpoints, and a mixture. Mirrored pairing as in the tournament harness.
* **Coverage**: at least 30 held-out seeds, all 5 tribes in all 6 start positions, 2 shipped maps plus 4 generated, three catastrophe settings, with and without drafting, and 90- and 180-minute horizons.
* **Metrics** (outcome, not reward): VP at horizon and share of games won by VP; era-trigger fraction; settlements, buildings, military value and kills; industrial index; cards-used rate; catastrophe survival rate when co-playing with 5 `plus`; wall-clock inference cost per decision.
* **Acceptance for the first champion**: paired win share against `plus` with a 95% bootstrap lower bound above 0.55 on held-out seeds, no tribe below 0.50, no collective-loss rate higher than `plus`'s, and inference below 5 ms per decision. A sequential test (SPRT) decides promotion so a lucky run does not become champion.
* **Honest negatives are recorded** in `docs/evidence/training/` exactly as the previous run did.

### 9.6 Compute reality

At the current speed the policy for the full game cannot be trained from scratch. The plan therefore (a) spends two milestones on speed before training, (b) trains modules in short scenarios whose episodes are 5-20 simulated minutes, (c) uses imitation for the large majority of learning, (d) uses saved states and branching rollouts for credit assignment, and (e) caps the full-game league evaluation to what the measured throughput allows. The Tier A machine is a validation and imitation-data machine; serious RL needs Tier B (or the existing scheduled run window).

---

## 10. Performance programme (alternating with development)

### 10.1 Loop

```
IMPLEMENT → TEST → EXTENDED SIMULATION → ANALYSE → PROFILE → OPTIMISE → VERIFY (hash-equal + conservation + determinism) → CONTINUE
```

Every milestone ends with a **performance checkpoint**: `scripts/perf_gate.py` runs the standard scenario set, compares to a stored baseline (`docs/perf/baseline.json`), and fails if throughput drops by more than a set percentage or memory grows. The profile is saved under `docs/perf/`.

### 10.2 Stages

| Stage | Work | Expected effect | Safety proof |
| --- | --- | --- | --- |
| **S1 algorithmic** (immediately) | Cache `command_centers`/`settlement_of` and invalidate on build/destroy/deploy; spatial hash for `_scan` and nearest-enemy; dirty flags for `forestry_quantum` and trees; skip idle workers; batch `waiting_for_this_road`; cache AI affordability per decision; stop re-deriving `_makes` | 2-4x | State hash equal at every minute against the stored baseline for 10 seeds |
| **S2 PyPy / runtime spike** | Run `bench_sim.py` under PyPy 3.10 (the sim core is mostly pure Python dict/list code, which PyPy accelerates well); check NumPy usage in the hot path | Possibly 3-10x; unknown until tried | Same hash test; PyPy availability on Windows confirmed in the probe |
| **S3 structure-of-arrays + vectorised kernels** | Units, carriers, trees, conveyor items as NumPy arrays; Numba-jitted kernels (no compiler needed on Windows) for walking, scanning, belt movement, power balance; integer arithmetic only on the deterministic path (no fast-math) | 3-5x on top of S1 | Hash equality; a cross-process determinism test under different hash seeds and a Windows-vs-Linux state-hash comparison |
| **S4 native extension (conditional)** | Rust (via PyO3/maturin) or C++ kernels for pathfinding and combat only if S1-S3 do not reach the target; needs a toolchain on Windows (blocked today: BLOCKERS B1 shows no compiler there) | further 2-5x | Same proofs; build reproducible by script |
| **S5 parallel throughput** | Process-level parallelism over seeds (exists); shared read-only terrain via memory-mapped files; batch AI inference across environments in the learner; avoid re-creating the world per episode (the `_world_cache` exists for envs) | scales with cores | Throughput benchmark vs cores |

**Targets** (to be re-set after the Windows probe): mid-game (75 min, six factions) at least 25x real time per core; late game (180 min, 20+ settlements, 1,500 buildings, 400 units) at least 8x; cold start under 5 s; memory under 1.5 GB per world; snapshots for Godot under 25 ms on Tier A.

### 10.3 Subsystem notes

* **Pathfinding**: the route search is the cost the project already notes. Add hierarchical pathfinding (sector graph, as OpenRA does) and path reuse for squads; counted node budgets stay.
* **Logistics**: move to a per-road queue index instead of scanning carriers for who is waiting (`waiting_for_this_road` is 444k calls); maintain request/offer indexes by ware.
* **Military**: spatial hashing, target caching with expiry, range-bucketed scans; aircraft on a separate simple kinematic path.
* **Industry**: belts as integer slot arrays (items per belt tile as small ints) updated in one vectorised pass; power networks recomputed only when topology or demand changes; liquid networks by flow-conservation solve per component.
* **Memory**: bounded event log (exists), snapshot deltas (exist), compact ID tables.
* **AI inference**: NumPy batched forward passes; decisions every 1-3 game minutes, not every quantum; cache feature extraction.
* **Determinism**: every optimisation must pass `test_determinism.py` and the new hash-equality gate; ordering rules (stable ID order, no set iteration) remain.

---

## 11. Autonomous execution, checkpoints, recovery, Windows

### 11.1 Persistent development ledger

* `docs/ledger/LEDGER.md` (human summary, short) and `docs/ledger/ledger.json` (machine-readable): per milestone: status, acceptance criteria, evidence paths, commit SHAs, test counts, performance numbers, open problems, next actions, blocked-on-owner questions.
* Every session starts by reading the ledger, `git status`, the last commit, and re-running the **smoke gate** (section 11.5); it ends by updating the ledger and committing.
* `docs/ledger/QUESTIONS.md` is the **decision queue**: a session that needs an owner decision writes it there with a recommended default and continues with the default on work that does not depend on it.

### 11.2 Session protocol (what Claude Code should do each time)

1. Read `CLAUDE.md`, `WizardRTSHybrid/AGENTS.md`, this plan, the ledger.
2. Run the baseline: quick suite (about 12-25 min on Tier A), determinism, perf smoke.
3. Pick the next ledger item whose prerequisites are done.
4. Work in small commits; push the feature branch every 20-30 minutes (existing authorisation); never merge to `main`.
5. After each logical unit: unit tests; after each milestone: gate script (acceptance suite + tournaments + perf gate + visual suite when rendering changed).
6. Write evidence under `docs/evidence/<milestone>/` (small summaries only; raw logs go to `~/dmb_runs`).
7. Update ledger, commit, push.

### 11.3 Long runs, resumability, recovery

* **Run manifest** per run: git SHA, config, seeds, schedule, hardware record, code hash of `wizard_rts`, dependency versions. A run directory holds append-only logs and atomic checkpoints (write to temp file, `fsync`, rename).
* **Checkpoints**: tournaments checkpoint per completed game; trainers checkpoint every N minutes and at promotion events (weights, optimiser, RNG, replay buffer index, league state). Resuming never repeats completed games and never mixes code versions (a SHA mismatch requires a flag).
* **Supervisor**: `scripts/autorun/supervisor.py` with a Windows service-free wrapper (`.ps1` plus Task Scheduler entry, optional) that restarts crashed workers with exponential back-off, detects stalls via per-worker heartbeat files, caps restarts, and writes `STATUS.json`. Per-game wall-clock timeouts kill hung simulations and record the seed for a repro.
* **Sleep and power**: the PowerShell wrapper sets the power plan to prevent sleep for the run and restores it after; the run exits cleanly on a stop file.
* **Crash capture**: every failure writes `repro.json` (seed, config, git SHA, last command list) so any crash is reproducible by `replay`.
* **Interruption tests** (part of the autonomous-infrastructure milestone): kill the supervisor mid-game, resume, and assert final state hash equals an uninterrupted run; corrupt the newest checkpoint and assert fallback to the previous one.

### 11.4 Disk and logs (urgent on Tier A)

* Move `~/dmb_runs` and `runtime/` to a configurable path (`DMB_RUNS`), refuse to start if free space is below a threshold (default 10 GB), compress finished logs, keep only: manifests, summaries, per-game CSV, champion checkpoints, and the last N periodic ones.
* `docs/evidence/` keeps summaries only (the repository is already large: `docs/evidence` contains many screenshots and multi-megabyte JSON).

### 11.5 Windows reliability

* Everything runs through `py -3`/`python` with no POSIX-only calls; paths via `pathlib`; subprocess use cross-checked; multiprocessing with the `spawn` start method (the current `fork` use in the tournament harness fails on Windows and must be replaced and tested); no reliance on `/dev/shm`, signals or `fork`.
* A Windows CI-like script runs the smoke gate; the existing `.ps1` scripts (`run_tests.ps1`, `run_headed_suite.ps1`) are kept working and tested.
* A cross-platform **state-hash equality test**: the same seed and command list on Windows and Linux gives the same hash (integer-only determinism on the sim path; floats confined to rendering and AI inference).

### 11.6 Smoke gate (a few minutes) and full gate

* **Smoke**: import check, schema compile, 200 selected unit tests, a 5-minute six-faction game hash-compare, a 2-game cards scenario, perf micro-benchmark.
* **Full gate**: the full pytest suite, generated per-entity tests (marker `entities`), tournaments (modes in section 14), perf gate, headed visual suite, ledger update.

---

## 12. Differences from v1 (where this brief overrides it)

| Topic | v1 | v2 |
| --- | --- | --- |
| Draft cadence | Rolling cycle of 7 rounds repeating every 42 min | One seven-round phase **at the start of each era**; none between |
| Cards | Each unlocks exactly one entity | One or two entities |
| Bonus pick | Second card from the same pack | Separate reserve-deck bonus hand; never touches circulating packs |
| Era end | Rising bar, minimum duration 45 min, sustain 5 min | **No minimum duration**; 60 s debounce only; leftover-pack rule at 8 VP |
| Leader rewards | Extra pick, free upgrade | Leftover cards (specified); hegemon unrest kept as a tunable lever |
| Mindustry scope | Excluded logic, payload, cores | **Includes** logic, payload, Erekir; only sandbox blocks are `dev_only` |
| Catastrophes | Not covered | Section 7 |
| Assets | Labelled placeholders accepted | Not accepted as completed |
| Hardware | T460 assumed | Two tiers; Windows probe first |

---

## 13. Milestones

Each milestone: an acceptance suite, a performance checkpoint, evidence, a ledger entry and a git checkpoint. Session counts are rough (a session is one long autonomous run) and assume work proceeds in the order shown with the Windows probe done first.

| ID | Milestone | Main content | Acceptance (measurable) | Sessions |
| --- | --- | --- | --- | ---: |
| **P0** | Foundations | `probe_hardware`, ledger and decision queue, supervisor and resumable run framework, `audit_catalogues.py`, disk-space guards, Windows `spawn` fix for the tournament, baseline evidence archive | Probe committed for both machines; interruption tests pass; audit prints the table in 3.1; smoke gate under 10 min | 2 |
| **P1** | Performance S1 + runtime spike | Caches, indexes, dirty flags; PyPy trial; hash-equal gate; perf baseline | Mid-game ≥ 2x faster with identical state hashes on 10 seeds; PyPy result recorded | 2 |
| **P2** | No-card civilisation | v1 sections 5.1-5.3: foundation set, builders and mine workers as entities, uncapped expansion, founding cost, unrest terms, markets | Six factions, 10 seeds, 120 min, no cards: each founds ≥ 3 settlements; ledger balanced | 4 |
| **P3** | Content graph + cards + drafting + paper + eras | Compiler, reachability checks, 1-2 unlock cards, era-start phase, bonus reserve, VP rules, leftover rule, ring with splits | Property tests; 1,000 simulated phases without a dead pack; replay equality; leftover-rule tests including injected splits | 5 |
| **P4** | Asset pipeline foundation | Contract manifests; MIX decryption in Python; palette/remap; layered atlases; asset ledger; Godot layered renderer, facing and turret independence | Asset audit shows contract coverage per source; specimen/facing/turret tests pass for the first vertical slices (one infantry, one tank, one aircraft, one ship, one Widelands building, one Mindustry unit and machine) | 5 |
| **P5** | God Mode inspector v1 | Server queries, panel, previews | Headed inspector tests; every displayed value equals the snapshot | 2 |
| **P6** | Widelands wave | Remaining sites and commands, markets, ships, waterways, transport upgrades; assets complete | All non-military Widelands entities `functional` or listed with a blocker | 5 |
| **P7** | OpenRA wave | Roster per 4.2; all units and eligible buildings; infantry, vehicles, aircraft, ships, transports, capture, repair, support powers; recipes from the balance workbook; art complete | Every OpenRA unit `functional` and in the card pool; duel matrix report; no alias art | 7 |
| **P8** | Performance S2-S3 | SoA + Numba kernels (or PyPy decision) | Targets in 10.2 for mid-game; hash equality; Windows-vs-Linux hash test | 3 |
| **P9** | Mindustry wave A: industrial revolution | Crafters, drills, routing, liquids, power, heat, logistics, enhanced OpenRA units, industrial index, dismantle/replace commands | G3 acceptance in 6.2 | 7 |
| **P10** | Catastrophes + diplomacy | Section 7; calibration study | Section 7.4 targets; hospital and containment chains; intervention orders | 4 |
| **P11** | Mindustry wave B: payload, military roster, logic, Erekir | Payload network, factories + reconstructors, T1-T5, specialist units, mlog subset, Erekir | Every Mindustry entity `functional` or `dev_only`; duel matrix; mlog program tests | 9 |
| **P12** | Era and VP study | Section 5.6 | Chosen thresholds recorded as decisions with evidence | 2 |
| **P13** | Performance S4 (conditional) and large-scale validation | Native kernels if needed; 180-min and multi-hour games with many settlements | Late-game targets in 10.2 | 3 |
| **P14** | Neural stage 1 | Skill interface, feature encoders, recorder, imitation for all modules | Each module no worse than heuristic module in module-swap tests | 6 |
| **P15** | Neural stage 2 | Per-module RL in scenarios; industrialisation, catastrophe, drafting, military | Each module beats its heuristic counterpart with a stated margin | 7 |
| **P16** | Neural stage 3 | Coordinator, joint training, league self-play, overnight/multi-day runs | Section 9.5 champion criteria | 8 |
| **P17** | Balance and content campaign | Content report loop (unused entities, bottlenecks, ineffective AI), tuning | 8.5 of v1 and the completion criteria below | continuous (about 6) |
| **P18** | Release verification | Full headed visual suite, full gates on both machines, documentation | Completion criteria | 2 |

About **80 sessions** in total. P0-P3 are sequential and unlock the rest; P4 (assets) can run alongside P2-P3; P6, P7, P9, P11 are content waves that each include their art; P8 and P13 are performance gates deliberately placed before the learning stages.

---

## 14. Testing strategy

1. **Fast suite** (existing 338 tests, plus new property tests).
2. **Generated entity suite** (`pytest -m entities`): one parametrised laboratory test per entity from the catalogue (about 1,000 cases when complete).
3. **Scenario suite**: chains from ore to unit, industrial revolution, catastrophe containment, draft phases, splits.
4. **Tournaments** (extended modes): `nocards`, `draft`, `war`, `crisis`, `industrial`, `historical-180`, `multi-cycle` (several full cycles), `stress` (large armies). All with mirrored pairing and CI95.
5. **Headless long runs**: 90- and 180-minute games across seeds and both shipped maps; 6-12 hour games on Tier B; multi-cycle runs; evidence of draft/VP/production/trade/battles/growth/industrialisation/catastrophes/AI decisions via the event log and time series (the harness already writes `events.jsonl` and `timeseries.csv`).
6. **Visual suite** (headed): section 8.5, run per asset wave and at release.
7. **Determinism and replay**: two-process and cross-OS hash tests; replay from command logs reproduces the hash.
8. **Automated reports** (`scripts/content_report.py`, `scripts/balance_report.py`): unused buildings and units (with the diagnosis split between *cost*, *effectiveness*, *accessibility*, *broken chain*, *AI decision*), production bottlenecks by idle reason, inaccessible or never-picked cards, card pick-to-use latency, unit cost-effectiveness matrix, win rates by tribe/start/doctrine, era duration distributions, early-transition and leftover statistics, catastrophe loss rates by policy, industrial index curves. The diagnosis rule for an ignored unit is explicit: first check whether its chain works in isolation (a lab test), then in a scenario, then whether it is dealt and drafted, then whether the AI can afford it, and only then change cost or stats. **No unit is forced into use.**

---

## 15. Completion criteria

The programme is complete when all of the following hold and are recorded in the ledger with evidence paths:

1. **Catalogue**: `audit_catalogues.py` shows zero unexplained differences against the pinned sources; every entity is `functional`, `dev_only` (sandbox) or `excluded` with a stated reason (Widelands military/training); no entity is `pending`.
2. **Functionality**: the generated entity suite passes for 100% of `functional` entities; ledger conservation passes in all scenario and tournament runs.
3. **Eras and drafting**: all four eras are reachable by VP in natural play in ≥ 60% of 100-seed runs; at least 20% of eras end before round 7 and at most 80% do; leftover-pack rule and ring invariants pass property and replay tests; every card is dealt in at least 5 of 100 games and drafted in at least 1.
4. **Revolutions**: section 6.2 acceptance and the 6.3 duel matrix pass; every OpenRA unit and every Mindustry unit is produced in at least 5 of 100 mid-to-late games by some faction.
5. **Catastrophes**: section 7.4 targets met; in at least 20% of games with cooperative AIs a faction helps contain a catastrophe in a rival's territory.
6. **Assets**: asset contract coverage 100% for every `functional` entity; the visual suite passes on both machines; zero `alias_placeholder`/drawn shapes in the inspector's missing-art filter; `asset_ledger.csv` complete.
7. **Inspector**: all filters work; displayed numbers match the snapshot in the headed tests.
8. **Performance**: targets in 10.2 met on the Windows PC; late-game 180-minute six-faction game completes without exceeding memory or step-time limits; cross-OS hash equality.
9. **Neural**: a champion meets the section 9.5 criteria against `plus` and the previous champion on at least 30 held-out seeds; the final report includes honest negative results.
10. **Autonomy**: interruption/resume tests pass; a 24-hour unattended run completes with at least one injected crash recovered.
11. **Documentation**: ledger current; every derivation recorded in `SOURCE_REUSE.md` and `LICENSES.md`; the owner can regenerate every table in this plan from scripts.

---

## 16. Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Python simulation too slow for RL at the required scale | High | Blocks G7 | P1/P8/P13 stages, PyPy spike, scenario-based training, imitation-heavy design |
| Windows hardware weaker or different than assumed | Medium | Training scope | Probe first; tiered parameters |
| MIX decryption fails or content packages are incomplete | Medium | Blocks OpenRA art | Route (b) with `OpenRA.Utility`; fall back to a Windows-side extraction session |
| Mindustry drawers and `Fx` are code-driven and numerous | High | Large effort | Data-driven drawer programs; port only effects actually referenced; waves by class |
| mlog interpreter scope | Medium | Effort | Subset first (instructions used by shipped example programs), then widen; keep deterministic |
| Seven picks per era leaves sparse, incoherent factions | Medium | Gameplay quality | Pair-card design, complement rules, trade, measure with the 5.6 study |
| Runaway from early era end | Medium | Balance | Study, then levers in 5.6 |
| Learned policies exploit reward holes (seen already) | High | Wasted training | Outcome metrics, held-out seeds, reward logging, honest negative reporting |
| Disk exhaustion on Tier A | High | Run failures | Guards, pruning, external drive |
| Cross-OS float differences break determinism | Medium | Replay trust | Integer-only sim path; float only in rendering/inference; cross-OS hash test |
| Licensing of assets (EA Red Alert, Mindustry art) | Low-medium | Release | Ledger records the owner's permission; no redistribution assumptions are made by the code |
| Scope: about 80 sessions | Certain | Schedule | Waves ship value incrementally; each wave leaves the game playable |

---

## 17. Decisions needed from you

Defaults apply if unanswered; items marked ⚠ would be expensive to reverse.

| ID | Question | Default |
| --- | --- | --- |
| Q1 | ⚠ Please run the hardware probe on the Windows PC (`probe_hardware`, to be added in P0) and commit or paste the JSON. Is that PC the training machine? | Yes after probe |
| Q2 | Is the Linux ThinkPad to be treated as a development machine only for training purposes? | Yes |
| Q3 | Keep Mindustry v146, or re-pin to a newer build? | Keep v146 |
| Q4 | Is "OpenRA roster" the Red Alert mod only (`ra`), or also `cnc`, `d2k`, `ts`? | `ra` only |
| Q5 | Era thresholds are decided by the 5.6 study; any hard constraints (for example an era should rarely end before round 4)? | None; study decides |
| Q6 | ⚠ May I add PyTorch (CPU or CUDA) for the learner, and Numba and PyPy for speed, once the plan is approved? About 0.8-2.5 GB. | Yes, learner only; sim workers stay NumPy/Numba |
| Q7 | Prefer decrypting MIX files in pure Python (no new tool) or installing the .NET SDK for `OpenRA.Utility`? | Pure Python first |
| Q8 | May mass drivers and ships serve as the long-distance logistics that stress dispersed civilisations? | Yes |
| Q9 | Are `dmb.paper` and the hybrid clinic acceptable as labelled hybrid content? | Yes |
| Q10 | Should factions be able to trade cards? | No (not in this programme) |
| Q11 | Two shipped Widelands maps plus generated maps for evaluation; any other maps you want used? | As is |
| Q12 | Overnight/multi-day training windows: acceptable hours and whether the PC may be left unattended | Owner states |
| Q13 | Is "enhanced OpenRA units" a stat/cost variant produced by upgraded factories (as planned), or a different mechanism? | Variant units with distinct ids |
| Q14 | Mindustry sandbox blocks: keep as `dev_only`? | Yes |

---

## 18. First actions after approval

1. P0 item 1: add `probe_hardware`, run it here, and ask you to run it on Windows.
2. P0 item 2: create the ledger and decision queue, record this plan as milestone P0-P18.
3. P0 item 3: add `audit_catalogues.py` and commit its output.
4. P1: apply the cache and index changes, with the hash-equality gate in place before the first edit.
5. Review checkpoint: ledger plus perf baseline to you before starting P2.
