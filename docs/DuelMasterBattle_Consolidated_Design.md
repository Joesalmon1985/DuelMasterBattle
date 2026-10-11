# DuelMasterBattle - Consolidated Design Document

> Single-read edition, 11 October 2026. **Generated** by `WizardRTSHybrid/scripts/build_consolidated_design.py` from the part files in `docs/`; edit the parts and regenerate. Direction approved by the owner (D01-D20); items marked PROPOSED / RECOMMENDED are open defaults. Code and tests decide what exists. The next-run kickoff prompt stays in `NEXT_RUN_KICKOFF_PROMPT.md`.

## Contents

1. Part I - Game design (v0.5)
2. Part II - Decision register
3. Part III - Architecture and modularity contract
4. Part IV - Current status, inventory and gaps
5. Part V - Roadmap for the next run
6. Part VI - Mindustry provenance and licensing


---

# Part I - Game design (v0.5)


Date: 11 October 2026. Status: **direction approved by the owner (decisions D01–D20 in `DECISION_REGISTER.md`); algorithms marked "recommended" are PROPOSED / TO VALIDATE.**

This is the authoritative statement of the game we are making. It supersedes `DuelMasterBattle_Design_v0_4.md` (a proposal, kept unchanged) and the Catan/turn-based economic parts of the 15 September v0.3 specification (not in this repository; the v0.4 Appendix A crosswalk maps its 231 sections). Where this file and v0.4 disagree, this file wins. Where any design file and the running code disagree about what *exists*, the code and tests win; see `CURRENT_STATUS_AND_GAPS.md`.

Related: `ARCHITECTURE_CONTRACT.md` (how it is built), `ROADMAP_NEXT_RUN.md` (what to build next), `WizardRTSHybrid/docs/MINDUSTRY_PROVENANCE.md` (source and licensing).

Status labels: **APPROVED** (owner decision), **RECOMMENDED** (proposed default, validate), **LEGACY** (from v0.3, kept as intent, not verified in the hybrid), **NOT IMPLEMENTED** (plan only).

---

### 1. The game in one page

**DuelMasterBattle is a wizard-led adventure set inside an autonomous civilisation simulation. It is not a player-controlled RTS.** (APPROVED, D02)

The player is a powerful wizard who walks through real settlements, gets to know the people who live there, uncovers plots, explores genuine dungeons, solves physical and environmental puzzles, intervenes in crises, and fights Mastermind-style colour-and-slot magical duels. These are the heart of the game and must never be displaced by economic or military development.

The world is a real, evolving strategy simulation that runs whether or not the wizard is watching. Six factions (five Widelands tribes, one repeated) found settlements, gather and process real goods, build roads and warehouses, equip armies and fight, and drift through four eras. Quests, people and dungeons exist *inside* this live economy and military world:

- A resident has a problem because a real mine is depleted, a real delivery is blocked, a neighbour threatens a real settlement, or an industrial machine is failing.
- The wizard's choices cause persistent, validated changes in actual simulation state (stock, buildings, workers, relations, ownership).
- If no quest exists, the world still works. Stories grow out of real causes; nothing is faked.

The wizard is **not a faction commander**. God Mode (RTS controls) and the headless training API stay in the product **only for development, debugging, tests and AI research**.

### 2. The four eras (APPROVED, D01, D05, D06, D09, D15)

One world, one clock, one save format. An era changes what is *available*, not which game is running.

| Era | Economy | Military | Story pressure (examples) |
| --- | --- | --- | --- |
| **Prehistoric** | Minimal Widelands-style: foraging, wood, stone, simple food, a few primitive workplaces. Small populations. More content only by drafting technology cards. | Primitive units (clubs, spears, slings, simple boats) through OpenRA-style rules and low-tech data. | Food security, migration, spirits, dangerous caves, hunting-ground rivalry. |
| **Historic** | Richer Widelands: full resource gathering, workers, production chains, roads, warehouses, mines, smelting, smithing. This supplies OpenRA-style real-time armies. | Barracks, stables, siege, war factory, shipyards (Widelands goods in, OpenRA-style units out). | Trade disputes, siege, famine, depleted mines, demon cults. |
| **Modern** | Mindustry-style drills, conveyors, power, pipes, liquids, machines, manufacturing and unit factories, unlocked by drafted cards and built from produced Widelands goods. Interoperates with existing resources, inventories, military and settlements. | Machine-built units that are meaningfully stronger than Historic units; same military simulation. | Pollution, strikes, sabotage, machine malfunction, alien/industrial hazards. |
| **Dystopian Future** | Advanced Mindustry-style industry and stronger military tech. | Strongest units and defences. | Hostile automation, nuclear/energy threats, AI governance, archaeology of past cycles. |

Utopia is an optional future extension, not the fourth era (D01).

**Technology** (D13, D15, D16): a faction begins with bare-bones facilities. Progress comes from **drafted technology cards** plus real prerequisites (a card for machine production is no use without the goods that build the machine). The Catan dice/resource-card economy is removed. Draft cadence is RECOMMENDED in `DECISION_REGISTER.md` S05–S06.

**Era upgrades** (D09): existing buildings upgrade in place for a real resource cost, keeping identity, history and workers. RECOMMENDED cost rule: `DECISION_REGISTER.md` S08.

### 3. The player experience (APPROVED)

Core loop: **travel → observe a working place → meet people and tensions → investigate → choose dialogue, spell, dungeon or duel → commit a real world consequence → leave → come back and see what happened.**

- Normal play exposes walking, observation, conversation, inventory, spells, dungeons and duels.
- The wizard does not queue buildings or order squads. Influence arrives through people, leaders, magic and consequences.
- The wizard may destroy any ordinary unit or building within local interaction range, whatever its allegiance or era (D10). Today fire magic (`magic.py`, 3 tiles) already burns buildings, units, ships, workers, carriers, trees, rocks and animals through the normal lifecycles; what is missing is allegiance/era-aware consequences, VP effects and quest hooks. The effect must flow through the same destruction path as combat, with real consequences (stock, workers, roads, ownership, VP per S03).
- Rival wizards and hazards are fought by the Mastermind duel, not by weapons.
- Developer God Mode and the training API are enabled only by an explicit developer/test configuration.

### 4. Settlements, territory and victory points (APPROVED D04, D07)

- A **settlement** is an established MCV/command-centre (a deployed MCV or a faction's first warehouse) and its surrounding territory (radius/footprint). Each is an individual settlement with its own autonomy, stock and logistics (current model, `territory.py`).
- An **undeployed MCV is not a settlement.** It is a vehicle carrying a starter kit.
- **VP:** +1 for each established settlement a faction holds; +1 for destroying an enemy settlement. Recipients, once-only counting and wizard-caused destruction are RECOMMENDED in `DECISION_REGISTER.md` S01–S03. The old 10-VP era threshold is a provisional configurable candidate (S04).
- A settlement needs a **stable ID** that survives deployment, ownership change and save/load, because stories, people, quests, VP and the chronicle attach to it.
- **Settlement chronicle** (LEGACY intent, NOT IMPLEMENTED): a record of founding, disasters, wars, shortages, upgrades and wizard actions. It is the factual source for dialogue, rumours and dungeon clues.

### 5. The world and its resources (APPROVED D03, D17)

- The **square grid with four-direction movement is authoritative** for terrain, movement, placement, territory and pathfinding. Terrain classes, heights, buildcaps, finite deposits and renewables come from Widelands rules (`terrain.py`, `mapgen.py`, `resources.py`; D5 in `WizardRTSHybrid/docs/DECISIONS.md`).
- Resources follow **resource-specific ecology**, not one rule: trees grow by terrain affinity; fish breed up to their initial amount; game wanders and breeds; ore, coal and stone are finite deposits; there are **no Mindustry ore tiles** (D21): advanced extractors yield different wares at the same existing sites from one shared finite reserve, and sand comes from existing desert/beach terrain (mapping in S10). "Renewable" never means unlimited output: rate, worker access and carrying capacity limit it.
- Strategic **regions** (a logical hex overlay) exist for catastrophes and history only (section 8).

### 6. Economy (APPROVED D05, D08, D15, D16, D17)

One conserved economy for all eras. Wares exist in a building's stock, a worker's or carrier's hands, a conveyor/pipe/machine buffer, or a construction/production reservation. They are never created or destroyed except by explicit, flagged sources and sinks (deposit extraction, renewable growth, consumption, destruction, a test grant).

- **Early eras (physical):** output is bounded by real workers, tasks and movement. A lumberjack walks, fells a tree, carries the log; a carrier hauls it. No decorative worker may secretly produce unlimited goods (D08). Known exceptions in the current code are listed as gaps.
- **Modern and Future (automated):** authoritative conveyors, pipes, machines and power networks with capacity and backpressure. A power outage must stop dependent machines. Items on a belt are real items.
- **Manual and automated delivery coexist** in one inventory model; a road carrier and a conveyor are two transports serving the same request/stock contract.
- **Mindustry is used for content and mechanics**, not as a separate runtime (section 11, `MINDUSTRY_PROVENANCE.md`).
- **Exclusions (D05):** original Widelands barracks/training as military producers, and OpenRA refineries, harvesters and credits/power-as-currency, are superseded. Soldiers and vehicles come from OpenRA-style production queues paid in real wares.
- **Campaign start (D15):** minimal facilities only. The existing fully equipped six-faction start is preserved as a named test fixture.

### 7. Military (APPROVED D14, D16)

One real-time military simulation in Python: orders, movement, targeting, projectile/damage, armour, death, naval, buildings and AI. Data-driven from OpenRA rules (`data/openra_rules.json`, 92 actors, 45 weapons) and later Mindustry unit definitions. All units — spearman, tank, ship, Mindustry mech — are entries in the same `world.units` with the same order/command API. Mindustry factories *emit* units into this simulation; they never run a second army engine. Military continues without the wizard present; the wizard's relation to it is influence and intervention.

### 8. Catastrophes and history (APPROVED D11, D12, D18)

**Outbreaks and hex cubes (D12).** Keep escalating outbreaks and cube accounting, but on a logical hex-region overlay over the square-grid map. The overlay is non-physical: no movement, placement or territory rule reads it. It *does* feed production, yield, health, quests, AI behaviour and the player's exploration (the wizard treats a region by being physically present). Era themes: demons/spirits early, pollution and aliens in Modern, nuclear/hostile automation in the Dystopian Future. Region size, cadence and cap are RECOMMENDED in S09.

**Cycles (D11).** Two different transitions:

1. **Era transition inside a cycle:** people, settlements, buildings, stock, roads and quests persist under defined upgrade/retire rules; nothing is silently deleted or duplicated; no free goods (design v0.4 §15.3–15.4 is the starting rule set).
2. **Full Future-to-Prehistoric reset:** only the wizard survives as a living persistent character and state owner (knowledge, spell progress, memory). All NPCs, settlements, infrastructure, armies, quests and inventories stop being active (they may leave ruins, dungeon entrances and cultural memory as *places*, not living state). The final geographic "peaks" of the old factions influence where the new factions start (RECOMMENDED definition, S07).

**Faction rise, decline, split and collapse (D18).** Preserve the history idea, driven by real conditions rather than VP ranking (RECOMMENDED algorithm, S12): decline from lost capital or stalled production; split from large, unlinked, unstable settlement groups; collapse when no command centre or MCV remains, leaving ruins. A successor faction has a new ID and inherits real assets.

### 9. Wizard, magic and duels (APPROVED; LEGACY details)

- **Mastermind duels** are a separate, preserved subsystem for rival wizards and hazards: hidden colour sequence, deduction from feedback, casts, slots and colours growing through quests. LEGACY baseline: four slots, six colours, repeats allowed, ten casts per side (to be confirmed against `godot_project/sim/duel_ruleset.gd`). The retained Ward Duel already pauses `game_ms` in the hybrid and must keep doing so.
- **World magic** (fire today) changes canonical state through typed, validated effects. No ordinary mana meter (LEGACY).
- **Seven Aspects** (Reason, Empathy, Authority, Guile, Resolve, Curiosity, Wonder) shape dialogue checks (LEGACY, see `godot_project/content/source/aspects/`).
- The wizard does not use hunger, armour, XP levelling or a faction profession.

### 10. People, quests and dungeons (APPROVED D19)

- People, settlements and quests are bound to **real entities**: a smith to a smithy, a miner to a mine, a courier to a route. Important workers have stable IDs linked to the world's worker objects; no parallel rosters.
- **Quest grammar (LEGACY, preserved):** world condition → affected entity → NPC who cares → desired change → obstacle → intervention options → validated world effect. Families: production shortage, blocked delivery, catastrophe, diplomacy, military threat, personal problem, discovery, conflicting interests.
- A quest has a persistent ID, bound entity IDs, state, and effect receipts. It cannot respawn after completion, resurrect a destroyed building, or fake scarcity that the economy does not show. If the world fixes the cause first, the quest resolves as `resolved_by_world`.
- **Dungeons** keep their identity: explorable interiors, spatial puzzles, mechanisms, keys, doors, secrets. Entrances occupy real map locations tied to real places (disused mine, ruin, plant). Solving or failing has real consequences; puzzle state persists across exit, save and ordinary era change; there is a recovery path for soft locks.
- **Reuse the existing implementations** (dungeon generator, puzzle logic, quest templates, dialogue and the village story test). Inventory is in `CURRENT_STATUS_AND_GAPS.md` §5. Named canon (character names, plots) stays undecided until the game is more solid (D19); one small integration slice proves the mechanism (roadmap M3).
- Dialogue and prose are authored/compiled offline; runtime selection is deterministic over structured facts; no online model is required; dialogue cannot invent facts or apply untyped effects.

### 11. Mindustry integration (APPROVED D06, D16; NOT IMPLEMENTED)

- Source: the official `https://github.com/Anuken/Mindustry` (GPL-3.0). A pinned revision is chosen and recorded at the start of the implementation run.
- **What is used:** item, ore/floor, drill, conveyor, power, liquid, pipe, crafter and unit-factory *definitions and behaviour*, ported to Python data and small deterministic modules inside the one world. Not used: the Mindustry wave game, cores, campaign launch sectors, RTS controls, Java runtime.
- **No second geology (D21).** A Mindustry drill sits on existing Widelands deposit/terrain tiles and converts reserve units into its configured ware at a data-driven rate; upgrading a Widelands mine to a drill keeps the building's id. New wares, never new deposit squares.
- **Chain to prove first (proven in the M2 slice, `test_industry_slice.py`):** real deposit → drill → conveyor → crafter (power if needed) → unit factory → a unit that joins `world.units` and fights with OpenRA-style rules, built from machines that were themselves paid for in produced Widelands goods and unlocked by a drafted card.
- Fidelity must be demonstrated against upstream numbers, not claimed. A source manifest entry is not an implemented mechanic.

### 12. Time, performance and determinism (APPROVED D14, D20)

- One fixed-step Game Time owns economy, units, environment and catastrophes. Menus, duels and authored scenes may pause it with explicit tokens (the duel's `hazard_duel` token already works).
- Same seed plus same ordered commands gives the same result across processes and `PYTHONHASHSEED` (guarded by `tests/test_determinism.py`).
- Distant systems may be simulated cheaper only if **deterministic, item-conserving and outcome-equivalent**, with a test comparing detailed and reduced runs. Nearby activity is simulated faithfully. Never decide anything by wall-clock time or by iterating a string set.

### 13. Presentation (APPROVED D14)

Godot presents Python's state and sends validated commands/input. Wizard Mode uses the existing walkable Overworld presentation. God Mode and diagnostics are developer tools. Visible truth: workers carrying wares, idle buildings, queues, power/flow indicators in automated eras, with inhabitants alongside machines. Any defect seen in play counts as fixed only when a headed Godot test (screenshot or rendered-state assertion) shows it.

### 14. Minimum identity

A mere RTS demo is not DuelMasterBattle, and a factory sim without stories is not either. The first releasable identity needs one live junction of **real production → autonomous conflict → a persistent settlement with people → a dungeon → a Mastermind duel → a lasting change**. Do not postpone the wizard game until every upstream building and unit is imported.

### 15. Where details live

| Topic | Document |
| --- | --- |
| Closed decisions and open defaults | `DECISION_REGISTER.md` |
| Modules, IDs, authority, conservation | `ARCHITECTURE_CONTRACT.md` |
| What works today, gaps, legacy asset inventory | `CURRENT_STATUS_AND_GAPS.md` |
| Next big run, acceptance tests | `ROADMAP_NEXT_RUN.md`, `NEXT_RUN_KICKOFF_PROMPT.md` |
| Source licences and Mindustry research | `WizardRTSHybrid/docs/LICENSES.md`, `MINDUSTRY_PROVENANCE.md`, `sources/manifest.json` |
| Long-form v0.4 reasoning, v0.3 section crosswalk | `DuelMasterBattle_Design_v0_4.md` (history), Appendix A |
| Implementation history | `WizardRTSHybrid/docs/STATE_OF_PLAY.md`, `PLAYTEST_FIXES.md`, `DECISIONS.md`, `WORK_LOG.md` |


---

# Part II - Decision register


Status: **D01–D20 APPROVED by the owner (Joe), 11 October 2026; D21 added by the owner's implementation-run instruction the same day.** This replaces the "PROPOSED" register in `DuelMasterBattle_Design_v0_4.md` §19 and `DuelMasterBattle_Open_Decisions_v0_4.md` (kept unchanged as history). The high-level decisions below are closed; do not ask them again. Only the sub-details marked **PROPOSED / TO VALIDATE** (section 2) remain open, and each has a recommended default so work is not blocked.

Design context: `DuelMasterBattle_Design_v0_5.md`. Architecture: `ARCHITECTURE_CONTRACT.md`. Plan: `ROADMAP_NEXT_RUN.md`.

### 1. Closed decisions

| ID | Decision | Status | Consequence for implementers |
| --- | --- | --- | --- |
| D01 | The fourth era is the **Dystopian Future**. Utopia is a deferred optional extension. | APPROVED | Era data has four slots: Prehistoric, Historic, Modern, Dystopian Future. Keep the era data model open to a later fifth/alternate era, but build nothing for it. |
| D02 | No direct control of factions or armies in the normal wizard game. God Mode stays for debugging, tests and developer inspection. | APPROVED | God Mode and the `HybridEnv` command surface must sit behind an explicit developer/test configuration (see gap G1 in `CURRENT_STATUS_AND_GAPS.md`). |
| D03 | The square-tile, four-direction-movement terrain is the baseline. A logical hex overlay is allowed for catastrophe regions. No Catan settlement topology. | APPROVED | `grid.py`/`terrain.py` stay authoritative. Hex code (`coords.py`) is only a region/label overlay. |
| D04 | Each established MCV/command-centre settlement is worth **1 VP**. Destroying an enemy settlement awards **1 VP**. An undeployed MCV is not a settlement. The old 10-VP era threshold is a provisional candidate. | APPROVED (rule); sub-details PROPOSED, see S01–S04 | Needs a settlement identity and a once-only event ledger (roadmap M4). |
| D05 | Long-term: all relevant Widelands civilian buildings and OpenRA units/buildings, except explicitly superseded facilities (original Widelands barracks/training military production, OpenRA refineries/harvesters/credit economy). Six factions cover all five Widelands tribes (one repeated). Everything is era/technology gated, not available at game start. | APPROVED | Coverage is tracked by behaviour in `feature_catalogue.json`, not by file count. Exclusions are listed in `CURRENT_STATUS_AND_GAPS.md` section 6. |
| D06 | **Mindustry is in scope for the next major run.** Mindustry wares come from the **existing** Widelands deposits and terrain (see D21): advanced extractors yield different wares at the same physical sites; sand comes from existing desert/beach terrain. First Mindustry machines are built from produced Widelands goods. Machines ultimately supply Mindustry unit production. Advanced units are meaningfully stronger than OpenRA-era units. Drafted tech cards unlock progression. | APPROVED; ware-per-deposit mapping is data (`mindustry_overrides.json`), see D21 and S10 | See roadmap M2 and `WizardRTSHybrid/docs/MINDUSTRY_PROVENANCE.md`. |
| D07 | Every deployed MCV/command centre is an individual settlement; territory is its radius/footprint. Preserve per-settlement autonomy and logistics. | APPROVED | Matches the current `territory.py` model. Settlement identity must become stable and persistent (roadmap M3/M4). |
| D08 | Early economy output is bounded by **real workers, tasks and movement**. Advanced Mindustry production uses authoritative conveyors, pipes, machines and power. No decorative workers producing unlimited goods. | APPROVED | Known current exceptions are hidden mine/smelter workers and the 20 s builder-less construction timer (gaps in `CURRENT_STATUS_AND_GAPS.md`). |
| D09 | Era advancement and tech drafting introduce stronger units/buildings. Existing buildings upgrade to later-era versions for a real resource cost, keeping identity and history. | APPROVED; upgrade costs PROPOSED, see S08 | Upgrade is an in-place transition command that consumes delivered wares. No free grants. |
| D10 | The wizard may destroy any ordinary unit or building, regardless of allegiance or era, within local interaction rules. Rival wizards and hazards keep magical duel contracts. World effects must be real. | APPROVED | Already true for fire magic within 3 tiles (`magic.py`). Extend to units; wizard-caused destruction behaves as in S03. |
| D11 | At a complete **Future-to-Prehistoric cycle reset**, only the wizard survives as a living persistent character/state owner. NPCs, settlements, infrastructure, armies, quests and inventories do not remain active. The geographic peaks/end state of prior factions influence new starting locations. Ordinary era transitions inside a cycle are different and may keep living identities and real infrastructure. | APPROVED; "peaks" definition PROPOSED, see S07 | Cycle reset and era transition are two separate state transitions with separate tests. |
| D12 | Retain outbreak escalation and **hex catastrophe cubes** on a logical regional overlay over the square-grid world. | APPROVED; region size and cadence PROPOSED, see S09 | The overlay is non-physical: no movement or placement rule reads it, but production, health, yield and quests may. |
| D13 | Retain technology-card drafting. Cadence and prerequisites are redesigned independent of Catan dice. | APPROVED; cadence PROPOSED, see S05–S06 | Existing `sim/dmb/technology/draft.py` is legacy reference only. |
| D14 | Python is the authoritative simulation and tactical combat owner, headless and deterministic. Godot presents it. | APPROVED | The v0.3 Godot `local_battle.gd` authority is retired for hybrid play. |
| D15 | The campaign starts with **minimal, bare-bones Widelands facilities**. More existing buildings arrive by drafting cards. Consistent with D05's eventual breadth. | APPROVED | The current fully equipped six-faction showcase start becomes a named test fixture (roadmap M1). |
| D16 | Mindustry machinery and unit factories need the right drafted tech cards. Their units join the **same** military simulation. | APPROVED | No second army engine. Produced units are ordinary `world.units` entries with an OpenRA-style actor/weapon record. |
| D17 | Resource-specific ecology, depletion, regeneration and carrying capacity. No one-size-fits-all rule. | APPROVED | Per-resource parameters live in data (`resources.py`, `data/`). Already true for trees, fish, game, and finite mines. |
| D18 | Keep the historical rise, decline, split and collapse of factions, driven by real settlement, economic and political conditions. Do not reintroduce all September VP elimination rules. | APPROVED; algorithm PROPOSED, see S12 | Proposed algorithm is in design v0.5 section 9.4. |
| D19 | Defer final named character/story canon until the game is more solid. Inventory and preserve existing stories, NPCs, quests and dungeons. Plan one small genuine integration slice. | APPROVED | The inventory is in `CURRENT_STATUS_AND_GAPS.md` section 5. Do not rewrite the narrative catalogue. |
| D20 | Simulate relevant nearby activity faithfully. Distant/headless systems may be optimised only by deterministic, item-conserving, outcome-equivalent processing with explicit tests. | APPROVED | Any level-of-detail shortcut needs an equivalence test (design v0.5 section 12). |
| D21 | **No Mindustry ore tiles, no second map-generation pass, no geological overlay.** The Widelands terrain, deposits and resource-site positions are authoritative in every era. An advanced (Mindustry-capable) extractor pulls a *different ware* from the *same* physical site by data-driven rule (an iron-bearing site can give iron through the Widelands mine rule, or copper, lead or titanium through a drill; sand derives from existing desert/beach terrain; water from existing water). Every site has one canonical finite reserve shared by all extractors; the conversion factor (reserve units per output item) is data. Existing mines are upgradeable in place to advanced extractors for delivered wares (S08), keeping building identity. New **inventory wares** (mdy.*) are allowed; new **deposit sites** are not. These are game adaptation rules, not claims about Mindustry's geology. | APPROVED (owner clarification, 11 Oct 2026) | `data/mindustry_overrides.json` `extraction`; `wizard_rts/industry/extraction.py`; tests `test_industry_mechanics.py::test_reserve_is_shared_and_decreases_exactly`, `test_no_new_deposit_kinds_exist`. |

### 2. Implementation sub-decisions (PROPOSED / TO VALIDATE)

These are the only open items. Each has a recommended default; an implementation agent may use the default as a **configurable constant** but must not describe it as settled. Confirm after the first playable slice.

| ID | Parent | Question | Recommended default | Reason |
| --- | --- | --- | --- | --- |
| S01 | D04 | Who receives the 1 VP when a settlement is destroyed? | The faction that dealt the final destroying blow to the command centre's last standing building *of the settlement's centre kind* (the centre itself), not to the last unit nearby. Wizard-caused destruction (S03) awards nothing. | Centre destruction is a single discrete event with one actor. |
| S02 | D04 | How is a VP counted exactly once? | A VP ledger keyed by `(settlement_id, event)`, event in {`founded`, `destroyed`}. Each key can be written once. A settlement's founding VP is a standing value (lost when the settlement stops existing); a destruction VP is permanent. Re-founding on the same tile creates a new `settlement_id`. | Idempotent, replayable, survives save/load. |
| S03 | D04/D10 | How does wizard-caused destruction behave? | The settlement's founding VP is removed from its owner (it no longer exists). No attacker VP is awarded. The wizard has no VP. Event is recorded in the chronicle with `cause: wizard`. | The wizard is not a faction (D02). |
| S04 | D04 | Era threshold. | Keep **10 VP** as a configurable `ERA_VP_THRESHOLD`, evaluated as the highest VP on any faction, with a time-based upper bound as a stall guard. | Provisional per D04. With six factions and 2-3 settlements each, 10 VP is reachable mainly by conquest. Validate by simulation (roadmap M4). |
| S05 | D13 | Draft cadence. | One draft round per faction per fixed Game Time interval (default 15 game minutes), plus one extra round on each era change. A draft offers 3 cards from the faction's currently unlockable pool; one is chosen. AI picks by its planner; the wizard never drafts for a faction. | Real-time, no dice, bounded and testable. |
| S06 | D13 | Card prerequisites. | A card needs (a) era >= card era, (b) its prerequisite cards drafted, (c) *physical* prerequisite met at draft time, e.g. at least one working building of a named kind. A card that unlocks Mindustry machines needs the Historic era plus a working smithy chain. | Keeps "technology is partly real ability" (v0.4 §15.1). |
| S07 | D11 | What do faction "peaks" mean? | At reset, for each faction record the **centroid of its settlements weighted by peak population or building count** at the time of its highest settlement count, plus its final-era VP. New cycle faction starts are placed on the original six homelands *rotated* so the strongest faction's centroid region seeds the next cycle's most fertile start. Only positions and a small number of seed values carry over; no wares, buildings, or units. | Meets D11 (geography influences starts, nothing else survives) and is deterministic. |
| S08 | D09 | Era upgrade costs. | Each upgrade costs the difference between the new and old building construction recipe plus a fixed fraction (default 25%) of the old recipe, paid in delivered wares. The old building keeps its ID, history and workers. | No free grants; no loss of identity. |
| S09 | D12 | Catastrophe region size and cadence. | A logical flat-top hex grid of radius about 24 tiles per hex, about 19-37 hexes on the standard 544x288 map, anchored at the map centre. Outbreak cube added to a region on a fixed Game Time interval (default 10 game minutes) at a deterministically chosen region. Treatment requires the wizard physically within the hex. Loss threshold stays 8 outbreaks until validated. | Preserves bounded attention; size must make a hex walkable in minutes. |
| S10 | D06/D21 | Which ware can each existing site yield to which extractor? | **Implemented (v146 pin, tunable data):** `coal` deposit: coal (tier 2). `iron` deposit: copper and lead (tier 2, 1 reserve unit per item), titanium (tier 3, 2 units per item). `stones`: scrap. `gold`: none. Sand from existing desert/beach terrain (infinite floor drop, tier 2). Tier = Mindustry `Drill.tier`; hardness from `Items.java`. Thorium and other items are not mapped yet. The Widelands mine rules are untouched. | D21: no new geography; the pairing is a game adaptation, recorded in `mindustry_overrides.json`. |
| S11 | D06 | First Mindustry machine cost. | **Implemented:** paid in delivered Widelands goods (plank, granite, iron). Explicit hybrid costs per block in `mindustry_overrides.json`, chosen with the conversion copper→iron, lead→granite, silicon/titanium→iron at about a quarter of the Mindustry item count plus a plank per structural part; the upstream requirements are kept as `source_cost` in the registry. A conveyor run pays one plank per three tiles. | Respects D06 "built with actually produced Widelands goods". |
| S12 | D18 | Faction rise/decline/split/collapse. | Computed from state, not VP: **decline** when a faction has lost its capital or has no productive building in 10 game minutes; **split** when a faction holds 4 or more settlements, the largest two are separated by more than N tiles with no road/ware link, and one has a low unrest/loyalty score; **collapse** when it holds no command centre and no MCV. A split creates a successor with its own ID, inheriting the disconnected settlements, their buildings, workers and units. Collapse leaves ruins. No ranking-based elimination. | Real conditions, deterministic, testable. |

### 3. Open questions that are *not* decisions

- Final Mindustry source pin (SHA) — chosen by the implementation agent at the start of M2 and recorded in `sources/manifest.json`.
- Art for Mindustry blocks and units. Mindustry art is GPL with its own asset terms; check before copying. Placeholder shapes are acceptable, labelled as such.
- Windows frame-rate budgets: unmeasured. Ubuntu T460 is about 7 fps headed on the full map.


---

# Part III - Architecture and modularity contract


Status: APPROVED direction (D07, D08, D14, D16, D20); module names below are RECOMMENDED. Prefer **incremental evolution of existing code** over rewrites. Do not create a new package unless a responsibility has nowhere to live. Current code map: `WizardRTSHybrid/wizard_rts/`.

### 1. Principles

1. **One canonical Python world.** `HybridWorld` (`wizard_rts/world.py`) is the only live simulation. It embeds the DuelMasterBattle `WorldState` and `ClockService`. No second economy, army, or clock. No Java Mindustry runtime. No separate Widelands or OpenRA process in play.
2. **Python is authoritative; Godot presents.** Godot sends validated commands and player input and renders snapshots. It never decides economy, combat, quest, or world state (D14). Presentation-only smoothing (the glide layer in `hybrid_art.gd`) never feeds back.
3. **Headless and deterministic.** Same seed + ordered commands ⇒ identical state across processes. No wall-clock decisions; no iteration over `set`s of strings for decisions; stable tie-breaking; counted (not timed) search budgets (`tests/test_determinism.py`).
4. **Physical item conservation.** See section 5.
5. **One military simulation.** All units from all eras live in `world.units` and are driven by the same orders, targeting, damage and AI (D16).
6. **One command surface.** The AI, God Mode, the training API and any tests use the same validated commands (`build`, `road`, `queue`, `move`, `order`, `demolish`, `deploy`, ...). The wizard campaign does not have this surface (D02): it uses interaction, magic and dialogue commands which are *different, narrower* commands validated by the simulation.
7. **Data over branches.** Adding a building, unit, ware, recipe, resource or card should be a data entry validated by schema, not a new `if kind == ...` branch in unrelated modules.

### 2. Authority split

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

### 3. Definitions and registries

Everything the sim knows about a *kind of thing* comes from a registry loaded at start from validated data. Runtime instances reference definitions by stable string ID plus a definition version.

| Registry | Today | Target |
| --- | --- | --- |
| Wares | `data/widelands_defs.json` (128), `wl_defs.py` | Add `mindustry.*` wares under their own namespace. Cross-namespace equivalence only by explicit mapping entries. |
| Resources/deposits | `terrain.py`, `resources.py`, `data/world/*` | Add per-resource ecology records (D17): `kind` (finite/renewable), `regen`, `carrying_capacity`, `valid_terrain`. |
| Buildings | Widelands defs + `construction.py` `RECIPES`/menu | Add `era`, `required_cards`, `upgrades_to`, `upgrade_cost`, `footprint`, `terrain_rules`, `tags`. |
| Units | `data/openra_rules.json` + hybrid recipes | Add `era`, `producer`, `required_cards`, cost in wares. Mindustry unit records produce the same unit row shape. |
| Recipes/programs | Widelands programs interpreter (`workers.py`) | Add machine recipes (`industry`), with power/liquid inputs. |
| Technology cards | none (hybrid) | `tech/cards.json`: id, era, prerequisite cards, physical prerequisites, unlocks (buildings, units, recipes). |
| Terrain | `terrain_defs.json` (pinned Widelands) | **No** ore/floor additions (D21). Extraction rules (`mindustry_overrides.json` `extraction`) map the existing `res_kind` layer and desert/beach terrain names to wares. |
| Mindustry content | pinned `external/mindustry` | Pipeline: pinned source → `scripts/import_mindustry_defs.py` → `data/mindustry_defs.json` (original numbers) → `data/mindustry_overrides.json` (labelled hybrid adaptation) → `wizard_rts/industry/registry.py`. Runtime never reads the Java tree or the raw JSON directly. |
| Settlements | derived from warehouse buildings | Explicit `settlement` records: stable ID, name, faction, centre, radius, founded_at, state. |
| Quests/dungeons/people | `sim/dmb/quests`, `people`, `godot_project/content/source/*` | Instances bind to settlement/building/worker/route IDs. |

**Stable IDs.** Definition IDs: `namespace.name` (`widelands.sawmill`, `openra.2tnk`, `mindustry.silicon_smelter`, `dmb.quest.shortage`). Instance IDs: allocated by the world's ID service (`self.dmb.ids.new(...)`), monotonic, never reused, never derived from list position. Settlement, quest and dungeon-instance IDs are instance IDs that survive save/load, ownership change and era transition.

### 4. Source importers, overrides and provenance

`pinned upstream` → `versioned importer script` → `generated, validated JSON in wizard_rts/data/` → `additive overrides (hand-written, separate files)` → `registry` → `simulation`.

- Importers live in `scripts/import_*.py` and record upstream URL, SHA and file/symbol in `sources/manifest.json`, `docs/SOURCE_REUSE.md` and `docs/LICENSES.md`.
- Never hand-edit generated files. Customisation is an override file keyed by ID. The override records why and the intended deviation.
- Unsupported upstream commands must **fail validation or be listed as unsupported**, never silently become free production. `feature_status.json` and `feature_catalogue.json` track behaviours, not file counts.
- Runtime play never reads `external/` (guarded by `tests/test_clean_environment.py`).
- Original art/derived copies follow `docs/LICENSES.md`; do not copy large amounts of upstream code or assets blindly.

### 5. Physical conservation contract

1. A ware is in exactly one place: building stock, worker/carrier hands, a conveyor/pipe/machine buffer, or an explicit reservation. A reservation is not a second copy.
2. Production consumes its inputs once and produces its outputs once. A queued unit or building takes real delivered goods; nothing materialises (except a flagged scenario/test grant, recorded in the event log).
3. Sources and sinks are explicit and logged: deposit extraction (reduces the one canonical reserve of the site, whichever extractor takes it; `stats["extracted_units_<kind>"]`), renewable growth (ecology model), consumption, destruction/loss, test grants.
4. Failed transport cannot teleport stock. Destruction/capture settles stock, cargo and reservations by documented policy (`lifecycle.purge_building`).
5. Era upgrade consumes delivered wares (S08); an old building does not produce a new-era good without a validated recipe.
6. A conservation test exists for every new transport mode: sum of wares in all locations + consumed − produced = constant.

**Worker versus conveyor/pipe/power (D08).**
- *Workers* (early eras): a task is a sequence of movement and action on the grid; output rate is a consequence of real walking and working. Hidden workers are a known gap, to be replaced by entities.
- *Conveyor/pipe/power* (Modern+): each belt segment/pipe holds typed buffered content, moves a bounded amount per tick, supports backpressure; power is a per-grid rate/capacity balance, not a ware; a deficit scales or stops consumers deterministically. Tick order is fixed and ID-ordered.
- *Bridge:* a machine output port deposits into a warehouse/construction-site/recruit-queue through the same stock API workers use, so both transports serve one request/stock contract.
- Machines, belts, pipes, nodes are **buildings/entities** in the world (with footprints, ownership, destruction), not hidden state.

### 6. Military and production unity

Unit factories (Widelands war factory, OpenRA barracks, Mindustry ground/air/naval factory) all end in the same spawn function that creates a `world.units` row with an OpenRA-style actor/weapon record. Stronger units are *data* (health, armour, weapons), not a second combat engine. `kill_unit`, `damage_building`, `lifecycle` remain the single destruction path (also used by wizard magic).

### 7. Event interfaces

The sim emits typed events into the bounded event log (6000 kept 3000): `built`, `destroyed`, `produced`, `delivered`, `shortage`, `unit_spawned`, `unit_killed`, `settlement_founded`, `settlement_destroyed`, `card_drafted`, `era_changed`, `outbreak`, `quest_effect_applied`, `puzzle_changed`. VP, chronicle, quests, dialogue facts and AI observations **read** events/state; they do not poke other modules' internals. Quest effects go back through typed, validated effect commands with receipts (idempotent: applying twice is a no-op).

### 8. Save, replay and level of detail

- Save: seed, config, ordered commands, game_ms, RNG state, all entity rows, deposits/ecology, reservations, conveyor/pipe/power state, card/era state, VP ledger, quest/puzzle state, people. `HybridEnv` already has save and replay (`sim_api.py`).
- Level of detail (D20): near activity (around the wizard and any active scene) at full fidelity; far activity may use a coarser step **only** if a test runs both versions from the same state and asserts equal item totals and equivalent outcomes within a stated tolerance. No LOD shortcut without that test.

### 9. Configuration profiles

| Profile | God Mode | Training API | Start | Used by |
| --- | --- | --- | --- | --- |
| `campaign` | off | off | primitive, card-gated | players |
| `developer` | on | on | selectable | developers, AI research |
| `test_showcase` | n/a (tests drive commands) | on | today's full six-faction start | existing regression suite |
| `test_minimal` | n/a | on | `minimal=True` single warehouse | bench tests |

The default for a player-facing launcher must be `campaign`. Tests assert (a) God Mode commands are rejected/unavailable in `campaign`, (b) available in `developer`.

### 10. Modules to add (not now)

`tech.py` (cards, drafting, unlock queries), `eras.py` (VP, thresholds, transitions, upgrades, reset), `settlements.py` (IDs, chronicle, VP ledger), `industry/` (items, drills, belts, pipes, power, crafters, unit factories), `regions.py` (catastrophe overlay), `story_bridge.py` (quest/people/dungeon ↔ world). Each ≤ a few hundred lines at first; each registers definitions and handles commands/events through the interfaces above.


### 10. Implemented in the M1/M2 slices (verified by tests, see `IMPLEMENTATION_RUN_STATUS.md`)

- **Profiles** (`wizard_rts/tech.py`): `campaign` (primitive start, locked kinds, God/training ops rejected by the server), `developer` (same start and locks, God ops accepted), `test_showcase` (the previous fully equipped start; the `HybridWorld` default so older tests are unchanged), `test_minimal`. The server defaults to `campaign` (`HYBRID_PROFILE`). `HybridEnv` is an in-process developer tool and is not reachable from the shipped client.
- **Gating**: every placement and unit-queue path goes through `construction.check_placement` / `queue_unit`, which return `locked_by_card`.
- **Industry** (`wizard_rts/industry/`): machines are ordinary construction sites in `world.buildings` (kind `mdy:*`, hybrid cost in delivered Widelands goods); belts are one construction site per run whose tiles go live on completion; power graphs join adjacent blocks and laser links; drills read the existing deposit layer. One clock (the 100 ms economy quantum); produced units are ordinary `world.units`.
- **Ledger** (`wizard_rts/ledger.py`): `snapshot_totals`/`check` balance held + consumed against held + made for every ware, counting belts and machine buffers.


---

# Part IV - Current status, inventory and gaps


Inspected 11 October 2026 on branch `feature/hybrid-playtest-fixes-v03`, HEAD `55d7762`. Source of truth for *what exists*: the code and tests. This file summarises them and distinguishes five levels:

- **WORKS** — exercised by a passing Python test and (where visible) a headed Godot script.
- **PARTIAL** — works for some cases; limits named.
- **IMPORTED** — data or art is present but no gameplay behaviour proves it.
- **TEST-ONLY** — exists for tests/dev, not for campaign play.
- **ABSENT** — nothing in the hybrid. Includes legacy features that live elsewhere in the repo but are not connected to the hybrid.

Design intent is in `DuelMasterBattle_Design_v0_5.md`. The detailed hybrid inventory remains `WizardRTSHybrid/docs/STATE_OF_PLAY.md` (partly stale, see section 7).

### 1. Verified baseline

- Branch `feature/hybrid-playtest-fixes-v03`, never merged into `main`. Local branches: this one and `feature/wizard-rts-hybrid-v02` (also on `origin`).
- Reported by the project docs (session 3): 123 Python tests and 12 headed Godot scripts passing. Re-run in this session: see section 8.
- Six untracked files from the owner (`docs/DuelMasterBattle_*_v0_4.*`, the 88-profile CSV, the Widelands/OpenRA economy workbook) are preserved untouched.

### 2. Hybrid simulation inventory (`WizardRTSHybrid/wizard_rts/`, ~7,900 lines)

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

### 3. Current-versus-intended gaps

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

### 4. Quick reference: what is not implemented in the hybrid, said plainly

Mindustry, tech cards, eras, VP, catastrophes, dialogue/quests/dungeons, cycle reset, faction collapse rules. Imported actor definitions and art do not count as gameplay.

### 5. Inventory of legacy DuelMasterBattle assets (reuse before rewriting)

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

### 6. Intentionally excluded versus postponed (D05)

Excluded (superseded): original Widelands barracks and training sites as military producers (recipes, art may stay for history; the AI no longer builds them, `ai.BUILD_WL_BARRACKS=False`); OpenRA refineries, harvesters, credits and power economy; Catan dice, node/edge board, World-Turn production.

Postponed (will be added, era/tech gated): remaining Widelands civilian buildings (58 sites need unsupported commands: scouts, ferries, ponds, gamekeeper, terraform, etc.; builder worker; flags/donkeys), remaining OpenRA units and buildings (aircraft, tech buildings, spread damage...), all Mindustry content, Utopia (deferred outright).

### 7. Documentation conflicts found and how they are corrected

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

### 8. Baseline test run in this session

`python3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py` (Ubuntu): **123 passed** (72 + 51 progress dots, no failures; run without a summary line, took roughly 25 minutes on a loaded machine). Headed Godot scripts and the legacy `tests/sim` suites were **not** re-run in this session; their results above are as reported by the project docs.


### 9. Update from the implementation run (12 October 2026)

- **G1 (God Mode / training surface not gated): fixed for the shipped entry.** `wizard_rts/server.py` rejects every faction-level op unless the profile is `developer`/`test_*`; the Godot client hides the God button and ignores `G` in `campaign`. `HybridEnv` is still an unguarded in-process developer tool (documented in `ARCHITECTURE_CONTRACT.md` §10). Tests: `test_campaign_tech.py`; headed `campaign`.
- **D15 start**: `profile="campaign"` gives the primitive start; `test_showcase` keeps the old start (the `HybridWorld` default). Card drafting exists (S05 cadence 15 game minutes, S06 prerequisites). Era index is fixed at 0.
- **Mindustry (D06/D16/D21)**: WORKS for the M2 slice (see `MINDUSTRY_PROVENANCE.md`). ABSENT: liquids, routers, sorters, bridges, other factories and units, art.
- Still ABSENT: persistent settlement IDs, VP, eras, outbreaks, story bridge, headless quest/dungeon/duel/outbreak environments, trained policies.


---

# Part V - Roadmap for the next run


**Authorised for this run (owner instruction of 11 October 2026): the stop-after-each-milestone rule is superseded for that run only; branches are still never merged to `main`.** Live status per milestone, with completed / partial / blocked / not started, is in `IMPLEMENTATION_RUN_STATUS.md`; the restart point is `NEXT_AGENT_HANDOFF.md`. Original text: this is a plan; the run started on `NEXT_RUN_KICKOFF_PROMPT.md`. Decisions: `DECISION_REGISTER.md`. Gaps: `CURRENT_STATUS_AND_GAPS.md`.

### 0. Ordering and rules

Recommended order: **M1 → M2 and M3 (independent, can alternate) → M4 → M5 → M6**. M3 (wizard gameplay) must not wait for M6 (full RTS coverage). M6 items are interleaved as needs arise.

Every milestone keeps green: the 123-test hybrid suite (`WizardRTSHybrid/tests`), the 12 headed scripts, `test_determinism.py`, `test_territory.py`, AI-behaviour checks, legacy `tests/sim` and the Ward Duel test. Every milestone adds: Python headless tests; a headed Godot script with screenshots under `docs/evidence/<milestone>/`; replay/conservation assertions; a performance check (`scripts/bench_sim.py`, `ai_report.py` worst step < 1 s at 6 factions; headless ≥ 40× real time on the standard map); explicit pass/fail below. A defect seen in play counts as fixed only when a headed test shows it.

Common task boundary: an agent finishing a milestone commits on the feature branch, updates `PROJECT_STATUS.md`, `TASK_LEDGER.md`, `STATE_OF_PLAY.md`, `WORK_LOG.md`, and stops for review.

---

### M1 — Campaign profiles, drafted-tech unlocks, primitive start

> **Status (12 Oct 2026): implemented and verified for the primitive start, drafting, gating, God-Mode gating, AI development and the 40-minute peace/war runs.** See `IMPLEMENTATION_RUN_STATUS.md` for the exact tests and what is partial (card catalogue is 13 cards; era index is fixed at 0 until M4; draft prompt exists as a God-panel developer display only).

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

### M2 — First real Mindustry industrial-to-unit slice

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

### M3 — One live-settlement story: NPC, dungeon, duel, real consequence

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

### M4 — VP and era progression foundation

**Purpose.** D04/D07/D09/D18 foundation: settlement identity, VP ledger, era state and thresholds, in-place upgrades, faction decline/split/collapse hooks.

**Reuse.** `territory.py`, `lifecycle`, `ai.py`, `sim/dmb/eras` (planner, collapse, fission) as references.

**New/changed.** `settlements.py`, `eras.py`; config constants `ERA_VP_THRESHOLD`, `DRAFT_INTERVAL`, `UPGRADE_COST_FRACTION`; upgrade command; era-gated card pool; `snapshot` exposes VP/era for dev HUD.

**Prerequisites.** M1. M3's `settlement_id` may land here.

**Headless tests.** Founding adds 1 VP once; destroy adds 1 VP to the destroyer once (S01, S02); wizard destroy removes owner's VP, awards none (S03); undeployed MCV gives none; repeated events or reload never double-count; reaching threshold advances era, unlocking the next card pool; an upgrade consumes delivered wares, keeps building ID and workers; a faction that loses all command centres and MCVs collapses leaving ruins (S12); full-cycle reset leaves only the wizard and placement influenced by S07; reset ≠ era transition tests.
**Headed.** Dev HUD shows VP, era; screenshot of an upgrade and of a ruin after collapse.
**Performance.** VP bookkeeping O(events).
**Pass/fail.** Ledger replay equals live totals; no VP from non-settlements. **Risk:** the 10-VP threshold may be unreachable or trivial: expose telemetry (VP/time) and validate with `ai_report.py` over three seeds before fixing the number.

---

### M5 — Catastrophe region overlay and outbreaks

**Purpose.** D12: bounded-attention existential threat on a logical hex overlay.

**Reuse.** `coords.py` (hex math), `sim/dmb/hazards` deck/propagation, hazard content JSON, the existing hazard/duel contract.

**New/changed.** `regions.py` (overlay, outbreak cubes, spread, treatment), effect hooks on mine yield, crop growth, health/unrest, quest generation; map overlay in God/diagnostic view and a readable in-world sign (smoke, withered ground) near an outbreak.

**Prerequisites.** M1; useful after M3.

**Headless tests.** Every tile belongs to exactly one region; overlay never alters movement/placement; outbreak cadence deterministic; adjacent spread rules; treatment requires wizard presence; an outbreak reduces affected mine yield by a stated factor and recovers after treatment; loss threshold ends the cycle by explicit rule; replay.
**Headed.** Screenshot of a region with an outbreak and the visual cue; wizard treats it.
**Pass/fail.** Effects visible in conserved stock numbers, not decoration.

---

### M6 — Widelands worker economy completion and broader OpenRA content

**Purpose.** D05/D08 breadth; interleaved, not a gate for M3.

**Items.** Builder worker; real mine/smelter workers; flags and donkeys; tribe soldier-chain fixes (remove ax fallback); marble/gold/bricks; sheep/wool; gamekeeper; Frisian ponds; remaining Widelands civilian sites (58 need new commands); more OpenRA units/buildings with their traits (spread damage, patrol, repair, aircraft, garrisons, tech buildings); real ship/yard art.
**Tests.** Per item: bench run of the production site, conservation, headed shot; coverage report from `build_catalogue.py` increases by named behaviours.
**Pass/fail.** Each item's catalogue status moves only with test evidence.

---

### Cross-cutting acceptance checklist for the run

- [ ] No gameplay logic added in Godot.
- [ ] Every new content ID has a registry entry and provenance.
- [ ] Conservation test per new transport.
- [ ] Determinism test passes with two hash seeds.
- [ ] Headed screenshot evidence stored; docs updated; branch not merged to `main`.


---

# Part VI - Mindustry provenance and licensing


Status: **pinned, cloned, imported and partly implemented (M2 slice).** Original research notes of 11 October 2026 follow; the section "Pin and what is implemented" below records what the implementation run did (12 October 2026). Nothing is claimed beyond what the named tests exercise.

### What is recorded

| Item | Value |
| --- | --- |
| Official source repository | `https://github.com/Anuken/Mindustry` |
| Language / build | Java; Gradle |
| Licence | GPL-3.0 (stated in the upstream repository; verify the `LICENSE` file and per-directory notices at the pinned revision) |
| Pinned revision | **`v146` = `26b66f9bdbd3a77b32f10f3cb350a9a737d5f012`** (commit date 2023-09-03; the long-lived stable release, well over two weeks old; tags up to v160.7 exist upstream and may be adopted later by changing the manifest and re-running the importer). Original wording: the implementation agent chooses a release tag or commit at least two weeks old, records the full SHA in `sources/manifest.json` (`id: mindustry`) and in `docs/SOURCE_REUSE.md`, and clones into `external/mindustry` via `scripts/setup_external.*`. |
| Compatibility | GPL-3.0 content may be combined with this GPL-3.0-or-later project. Art, sound and any non-code assets may carry separate terms: check at the pinned revision before copying any asset. Placeholder art is acceptable until checked. |

A manifest entry is not an implemented mechanic. Do not describe Mindustry as integrated until a test exercises a behaviour taken from it.

### What the implementation agent must inspect before coding (D06, D16)

At the pinned revision read the actual definitions, not summaries:

1. **Items and ores:** `core/src/mindustry/content/Items.java` (copper, lead, sand, coal, titanium, thorium, scrap, metaglass, graphite, silicon, plastanium, etc.): `cost`, `hardness`, flammability.
2. **Floors/ores and generation:** `content/Blocks.java` (ore blocks, floors such as sand/darksand, vents), and the world generation / ore placement rules (`mindustry.maps.generators` and the `Planets`/sector presets) to decide which terrain yields which ore. Do not assume "pasture thorium": check, then record the mapping in `DECISION_REGISTER.md` S10.
3. **Drills:** `mechanical-drill`, `pneumatic-drill`, `laser-drill`...: `tier`, `drillTime`, size, `hardnessOffset`, formula in `world/blocks/production/Drill.java`.
4. **Conveyors and item transport:** `world/blocks/distribution/Conveyor.java`, `Junction`, `Router`, `Sorter`, `Bridge`, `Unloader`: speed, capacity per tile (4 items), update order and backpressure.
5. **Power:** `world/blocks/power/*` (generators, batteries, nodes), `PowerGraph.java`: satisfaction ratio model.
6. **Liquids:** `world/blocks/liquid/*`, `Liquid`: pipes, tanks, flow, capacity.
7. **Crafters:** `world/blocks/production/GenericCrafter.java` and block definitions (graphite press, silicon smelter, kiln, etc.): consume/produce, craft time, power.
8. **Unit factories and units:** `world/blocks/units/UnitFactory.java`, `Reconstructor`; `content/UnitTypes.java` (dagger, mace, fortress, nova, flare, horizon, risso...): health, armor, speed, weapons, build cost and time, plans.
9. **Tech prerequisites:** `content/TechTree.java` and `SectorPresets`/research requirements: use to seed the card prerequisite graph (S06).
10. **Block build requirements:** `requirements(Category, with(Items.copper, N...))` for each block, used to derive Widelands-goods costs (S11) via a written conversion table.

### How to use the source (and how not to)

- Port **data and compact algorithms** (drill rate, conveyor movement, power satisfaction, crafter timing, unit stats) into Python modules driven by generated JSON, with unit tests comparing results against values computed from the pinned source.
- Do not copy large Java engine classes, the rendering, networking, or the campaign/wave logic. Do not run a Java process in play. Do not create an independent army or economy.
- Record in `SOURCE_REUSE.md` per mechanic: file and symbol, status (`source-derived adapted`/`not implemented`), comparison test, remaining differences.
- Every Mindustry item must exist as a ware in the shared economy, every produced unit must appear in `world.units`.

### Open questions for the implementation agent to answer in writing

- Units: are belt speed/drill time in ticks (60/s)? Map to the sim's quantum with an explicit scale factor and document it.
- How do the first Mindustry machines translate to Widelands goods (S11)?
- Which Mindustry units are first (suggest ground: dagger/mace; air: flare)?
- Art: use a clearly labelled placeholder if asset terms are unconfirmed.


### Pin and what is implemented (12 October 2026)

| Item | State |
| --- | --- |
| Pin | `sources/manifest.json` entry `mindustry` (tag `v146`, full SHA above, GPL-3.0). `scripts/setup_external.sh mindustry` makes a sparse checkout (content, type, world/blocks sources, unit sprites, about 10 MB; `MINDUSTRY_FULL=1` gives a full one). `scripts/setup_external.ps1` walks the manifest and makes a full clone. `scripts/verify_pins.py` checks every checkout against the manifest; `tests/test_mindustry_pipeline.py` runs it. |
| Source read directly | `Items.java`, `Liquids.java`, `Blocks.java`, `UnitTypes.java` (all imported), `Drill.java` (`getDrillTime`: `drillTime + 50 * hardness`, divided by the drill multiplier), `Conveyor.java` (`itemSpace 0.4`, `capacity 3`, `speed` tiles per tick), `UnitFactory.UnitPlan`, `PowerNode` fields (`laserRange`, `maxNodes`), `Battery` (`consumePowerBuffered`). Not yet read in depth: `TechTree.java`, junction/router/sorter, pumps and conduits, reconstructors, effects. |
| Importer | `scripts/import_mindustry_defs.py` → `wizard_rts/data/mindustry_defs.json` (22 items, 10 liquids, 214 blocks that have a `requirements` call, 39 unit types). Original numbers only; ticks converted to seconds in derived fields. `--check` fails if the JSON is out of date. Known simplification: the importer takes one weapon per unit and the first bullet's damage; drill `items_per_second` lists only the items in `DRILLABLE`. |
| Adaptation | `wizard_rts/data/mindustry_overrides.json` (labelled as our decisions): ware map, hybrid construction costs in Widelands goods, extraction rules (D21), unit scales (`hp_scale` 50, `damage_scale` 25, speed and range in RTS cells, mirrored weapons). The registry keeps the upstream cost as `source_cost`. |
| Registry | `wizard_rts/industry/registry.py`. Blocks: mechanical and pneumatic drill, conveyor, power node, battery, combustion generator, solar panel (small, large), silicon smelter, graphite press, ground factory. Unit: dagger. |
| Behaviour (tests) | `tests/test_industry_mechanics.py` (18 tests), `tests/test_industry_slice.py` (4), `tests/test_mindustry_pipeline.py` (17). Rates tested: drill formula, belt speed (8 tiles in about 4.4 s), spacing, backpressure, power satisfaction, battery, combustion fuel, factory plan time. |
| Not implemented | Liquids, pumps and conduits; junction, router, sorter, bridge; plastanium and surge items; reconstructors and other factories; air and naval Mindustry units; thorium and scrap extraction beyond the rule table; drill water boost; warmup; Erekir content. |
| Art and sound | **None imported.** `external/mindustry/core/assets*` is checked out (sprites exist) but the asset terms were not verified (the repository `LICENSE` is GPL-3.0 for the whole tree; per-asset notices were not checked), so every machine, belt and unit is a labelled placeholder drawn by `godot_project/client/hybrid/industry_view.gd` (coloured shapes, "placeholder art" text). Never describe them as upstream art. |
| Runtime | No Java, no second economy, battlefield or clock: the layer runs inside `HybridWorld.advance`. |
