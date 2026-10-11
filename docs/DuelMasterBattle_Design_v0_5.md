# DuelMasterBattle — Game Design Specification v0.5 (RATIFIED DIRECTION)

Date: 11 October 2026. Status: **direction approved by the owner (decisions D01–D20 in `DECISION_REGISTER.md`); algorithms marked "recommended" are PROPOSED / TO VALIDATE.**

This is the authoritative statement of the game we are making. It supersedes `DuelMasterBattle_Design_v0_4.md` (a proposal, kept unchanged) and the Catan/turn-based economic parts of the 15 September v0.3 specification (not in this repository; the v0.4 Appendix A crosswalk maps its 231 sections). Where this file and v0.4 disagree, this file wins. Where any design file and the running code disagree about what *exists*, the code and tests win; see `CURRENT_STATUS_AND_GAPS.md`.

Related: `ARCHITECTURE_CONTRACT.md` (how it is built), `ROADMAP_NEXT_RUN.md` (what to build next), `WizardRTSHybrid/docs/MINDUSTRY_PROVENANCE.md` (source and licensing).

Status labels: **APPROVED** (owner decision), **RECOMMENDED** (proposed default, validate), **LEGACY** (from v0.3, kept as intent, not verified in the hybrid), **NOT IMPLEMENTED** (plan only).

---

## 1. The game in one page

**DuelMasterBattle is a wizard-led adventure set inside an autonomous civilisation simulation. It is not a player-controlled RTS.** (APPROVED, D02)

The player is a powerful wizard who walks through real settlements, gets to know the people who live there, uncovers plots, explores genuine dungeons, solves physical and environmental puzzles, intervenes in crises, and fights Mastermind-style colour-and-slot magical duels. These are the heart of the game and must never be displaced by economic or military development.

The world is a real, evolving strategy simulation that runs whether or not the wizard is watching. Six factions (five Widelands tribes, one repeated) found settlements, gather and process real goods, build roads and warehouses, equip armies and fight, and drift through four eras. Quests, people and dungeons exist *inside* this live economy and military world:

- A resident has a problem because a real mine is depleted, a real delivery is blocked, a neighbour threatens a real settlement, or an industrial machine is failing.
- The wizard's choices cause persistent, validated changes in actual simulation state (stock, buildings, workers, relations, ownership).
- If no quest exists, the world still works. Stories grow out of real causes; nothing is faked.

The wizard is **not a faction commander**. God Mode (RTS controls) and the headless training API stay in the product **only for development, debugging, tests and AI research**.

## 2. The four eras (APPROVED, D01, D05, D06, D09, D15)

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

## 3. The player experience (APPROVED)

Core loop: **travel → observe a working place → meet people and tensions → investigate → choose dialogue, spell, dungeon or duel → commit a real world consequence → leave → come back and see what happened.**

- Normal play exposes walking, observation, conversation, inventory, spells, dungeons and duels.
- The wizard does not queue buildings or order squads. Influence arrives through people, leaders, magic and consequences.
- The wizard may destroy any ordinary unit or building within local interaction range, whatever its allegiance or era (D10). Today fire magic (`magic.py`, 3 tiles) already burns buildings, units, ships, workers, carriers, trees, rocks and animals through the normal lifecycles; what is missing is allegiance/era-aware consequences, VP effects and quest hooks. The effect must flow through the same destruction path as combat, with real consequences (stock, workers, roads, ownership, VP per S03).
- Rival wizards and hazards are fought by the Mastermind duel, not by weapons.
- Developer God Mode and the training API are enabled only by an explicit developer/test configuration.

## 4. Settlements, territory and victory points (APPROVED D04, D07)

- A **settlement** is an established MCV/command-centre (a deployed MCV or a faction's first warehouse) and its surrounding territory (radius/footprint). Each is an individual settlement with its own autonomy, stock and logistics (current model, `territory.py`).
- An **undeployed MCV is not a settlement.** It is a vehicle carrying a starter kit.
- **VP:** +1 for each established settlement a faction holds; +1 for destroying an enemy settlement. Recipients, once-only counting and wizard-caused destruction are RECOMMENDED in `DECISION_REGISTER.md` S01–S03. The old 10-VP era threshold is a provisional configurable candidate (S04).
- A settlement needs a **stable ID** that survives deployment, ownership change and save/load, because stories, people, quests, VP and the chronicle attach to it.
- **Settlement chronicle** (LEGACY intent, NOT IMPLEMENTED): a record of founding, disasters, wars, shortages, upgrades and wizard actions. It is the factual source for dialogue, rumours and dungeon clues.

## 5. The world and its resources (APPROVED D03, D17)

- The **square grid with four-direction movement is authoritative** for terrain, movement, placement, territory and pathfinding. Terrain classes, heights, buildcaps, finite deposits and renewables come from Widelands rules (`terrain.py`, `mapgen.py`, `resources.py`; D5 in `WizardRTSHybrid/docs/DECISIONS.md`).
- Resources follow **resource-specific ecology**, not one rule: trees grow by terrain affinity; fish breed up to their initial amount; game wanders and breeds; ore, coal and stone are finite deposits; there are **no Mindustry ore tiles** (D21): advanced extractors yield different wares at the same existing sites from one shared finite reserve, and sand comes from existing desert/beach terrain (mapping in S10). "Renewable" never means unlimited output: rate, worker access and carrying capacity limit it.
- Strategic **regions** (a logical hex overlay) exist for catastrophes and history only (section 8).

## 6. Economy (APPROVED D05, D08, D15, D16, D17)

One conserved economy for all eras. Wares exist in a building's stock, a worker's or carrier's hands, a conveyor/pipe/machine buffer, or a construction/production reservation. They are never created or destroyed except by explicit, flagged sources and sinks (deposit extraction, renewable growth, consumption, destruction, a test grant).

- **Early eras (physical):** output is bounded by real workers, tasks and movement. A lumberjack walks, fells a tree, carries the log; a carrier hauls it. No decorative worker may secretly produce unlimited goods (D08). Known exceptions in the current code are listed as gaps.
- **Modern and Future (automated):** authoritative conveyors, pipes, machines and power networks with capacity and backpressure. A power outage must stop dependent machines. Items on a belt are real items.
- **Manual and automated delivery coexist** in one inventory model; a road carrier and a conveyor are two transports serving the same request/stock contract.
- **Mindustry is used for content and mechanics**, not as a separate runtime (section 11, `MINDUSTRY_PROVENANCE.md`).
- **Exclusions (D05):** original Widelands barracks/training as military producers, and OpenRA refineries, harvesters and credits/power-as-currency, are superseded. Soldiers and vehicles come from OpenRA-style production queues paid in real wares.
- **Campaign start (D15):** minimal facilities only. The existing fully equipped six-faction start is preserved as a named test fixture.

## 7. Military (APPROVED D14, D16)

One real-time military simulation in Python: orders, movement, targeting, projectile/damage, armour, death, naval, buildings and AI. Data-driven from OpenRA rules (`data/openra_rules.json`, 92 actors, 45 weapons) and later Mindustry unit definitions. All units — spearman, tank, ship, Mindustry mech — are entries in the same `world.units` with the same order/command API. Mindustry factories *emit* units into this simulation; they never run a second army engine. Military continues without the wizard present; the wizard's relation to it is influence and intervention.

## 8. Catastrophes and history (APPROVED D11, D12, D18)

**Outbreaks and hex cubes (D12).** Keep escalating outbreaks and cube accounting, but on a logical hex-region overlay over the square-grid map. The overlay is non-physical: no movement, placement or territory rule reads it. It *does* feed production, yield, health, quests, AI behaviour and the player's exploration (the wizard treats a region by being physically present). Era themes: demons/spirits early, pollution and aliens in Modern, nuclear/hostile automation in the Dystopian Future. Region size, cadence and cap are RECOMMENDED in S09.

**Cycles (D11).** Two different transitions:

1. **Era transition inside a cycle:** people, settlements, buildings, stock, roads and quests persist under defined upgrade/retire rules; nothing is silently deleted or duplicated; no free goods (design v0.4 §15.3–15.4 is the starting rule set).
2. **Full Future-to-Prehistoric reset:** only the wizard survives as a living persistent character and state owner (knowledge, spell progress, memory). All NPCs, settlements, infrastructure, armies, quests and inventories stop being active (they may leave ruins, dungeon entrances and cultural memory as *places*, not living state). The final geographic "peaks" of the old factions influence where the new factions start (RECOMMENDED definition, S07).

**Faction rise, decline, split and collapse (D18).** Preserve the history idea, driven by real conditions rather than VP ranking (RECOMMENDED algorithm, S12): decline from lost capital or stalled production; split from large, unlinked, unstable settlement groups; collapse when no command centre or MCV remains, leaving ruins. A successor faction has a new ID and inherits real assets.

## 9. Wizard, magic and duels (APPROVED; LEGACY details)

- **Mastermind duels** are a separate, preserved subsystem for rival wizards and hazards: hidden colour sequence, deduction from feedback, casts, slots and colours growing through quests. LEGACY baseline: four slots, six colours, repeats allowed, ten casts per side (to be confirmed against `godot_project/sim/duel_ruleset.gd`). The retained Ward Duel already pauses `game_ms` in the hybrid and must keep doing so.
- **World magic** (fire today) changes canonical state through typed, validated effects. No ordinary mana meter (LEGACY).
- **Seven Aspects** (Reason, Empathy, Authority, Guile, Resolve, Curiosity, Wonder) shape dialogue checks (LEGACY, see `godot_project/content/source/aspects/`).
- The wizard does not use hunger, armour, XP levelling or a faction profession.

## 10. People, quests and dungeons (APPROVED D19)

- People, settlements and quests are bound to **real entities**: a smith to a smithy, a miner to a mine, a courier to a route. Important workers have stable IDs linked to the world's worker objects; no parallel rosters.
- **Quest grammar (LEGACY, preserved):** world condition → affected entity → NPC who cares → desired change → obstacle → intervention options → validated world effect. Families: production shortage, blocked delivery, catastrophe, diplomacy, military threat, personal problem, discovery, conflicting interests.
- A quest has a persistent ID, bound entity IDs, state, and effect receipts. It cannot respawn after completion, resurrect a destroyed building, or fake scarcity that the economy does not show. If the world fixes the cause first, the quest resolves as `resolved_by_world`.
- **Dungeons** keep their identity: explorable interiors, spatial puzzles, mechanisms, keys, doors, secrets. Entrances occupy real map locations tied to real places (disused mine, ruin, plant). Solving or failing has real consequences; puzzle state persists across exit, save and ordinary era change; there is a recovery path for soft locks.
- **Reuse the existing implementations** (dungeon generator, puzzle logic, quest templates, dialogue and the village story test). Inventory is in `CURRENT_STATUS_AND_GAPS.md` §5. Named canon (character names, plots) stays undecided until the game is more solid (D19); one small integration slice proves the mechanism (roadmap M3).
- Dialogue and prose are authored/compiled offline; runtime selection is deterministic over structured facts; no online model is required; dialogue cannot invent facts or apply untyped effects.

## 11. Mindustry integration (APPROVED D06, D16; NOT IMPLEMENTED)

- Source: the official `https://github.com/Anuken/Mindustry` (GPL-3.0). A pinned revision is chosen and recorded at the start of the implementation run.
- **What is used:** item, ore/floor, drill, conveyor, power, liquid, pipe, crafter and unit-factory *definitions and behaviour*, ported to Python data and small deterministic modules inside the one world. Not used: the Mindustry wave game, cores, campaign launch sectors, RTS controls, Java runtime.
- **No second geology (D21).** A Mindustry drill sits on existing Widelands deposit/terrain tiles and converts reserve units into its configured ware at a data-driven rate; upgrading a Widelands mine to a drill keeps the building's id. New wares, never new deposit squares.
- **Chain to prove first (proven in the M2 slice, `test_industry_slice.py`):** real deposit → drill → conveyor → crafter (power if needed) → unit factory → a unit that joins `world.units` and fights with OpenRA-style rules, built from machines that were themselves paid for in produced Widelands goods and unlocked by a drafted card.
- Fidelity must be demonstrated against upstream numbers, not claimed. A source manifest entry is not an implemented mechanic.

## 12. Time, performance and determinism (APPROVED D14, D20)

- One fixed-step Game Time owns economy, units, environment and catastrophes. Menus, duels and authored scenes may pause it with explicit tokens (the duel's `hazard_duel` token already works).
- Same seed plus same ordered commands gives the same result across processes and `PYTHONHASHSEED` (guarded by `tests/test_determinism.py`).
- Distant systems may be simulated cheaper only if **deterministic, item-conserving and outcome-equivalent**, with a test comparing detailed and reduced runs. Nearby activity is simulated faithfully. Never decide anything by wall-clock time or by iterating a string set.

## 13. Presentation (APPROVED D14)

Godot presents Python's state and sends validated commands/input. Wizard Mode uses the existing walkable Overworld presentation. God Mode and diagnostics are developer tools. Visible truth: workers carrying wares, idle buildings, queues, power/flow indicators in automated eras, with inhabitants alongside machines. Any defect seen in play counts as fixed only when a headed Godot test (screenshot or rendered-state assertion) shows it.

## 14. Minimum identity

A mere RTS demo is not DuelMasterBattle, and a factory sim without stories is not either. The first releasable identity needs one live junction of **real production → autonomous conflict → a persistent settlement with people → a dungeon → a Mastermind duel → a lasting change**. Do not postpone the wizard game until every upstream building and unit is imported.

## 15. Where details live

| Topic | Document |
| --- | --- |
| Closed decisions and open defaults | `DECISION_REGISTER.md` |
| Modules, IDs, authority, conservation | `ARCHITECTURE_CONTRACT.md` |
| What works today, gaps, legacy asset inventory | `CURRENT_STATUS_AND_GAPS.md` |
| Next big run, acceptance tests | `ROADMAP_NEXT_RUN.md`, `NEXT_RUN_KICKOFF_PROMPT.md` |
| Source licences and Mindustry research | `WizardRTSHybrid/docs/LICENSES.md`, `MINDUSTRY_PROVENANCE.md`, `sources/manifest.json` |
| Long-form v0.4 reasoning, v0.3 section crosswalk | `DuelMasterBattle_Design_v0_4.md` (history), Appendix A |
| Implementation history | `WizardRTSHybrid/docs/STATE_OF_PLAY.md`, `PLAYTEST_FIXES.md`, `DECISIONS.md`, `WORK_LOG.md` |
