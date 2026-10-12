# DUELMASTERBATTLE
## Integrated Game Design Specification — Economy, Civilisations, Wizards and History
### Working Revision v0.4 • 11 October 2026 • PROPOSED, NOT APPROVED

> **Document status.** This is a consolidated proposal replacing the *economic and strategic-mechanics assumptions* of the 15 September 2026 v0.3 specification. It preserves the original adventure, magic, dungeon, dialogue, narrative and persistence intentions unless this document explicitly flags a conflict. Numerical values and architecture recommendations are proposals, not newly “locked” user decisions. The source v0.3 is the detailed historical design record; the current Git repository remains the authority for what is implemented.

**Source baseline:** original *Complete Game Design, Systems, Content & MVP Specification v0.3* (15 September 2026); `Joesalmon1985/DuelMasterBattle`, branch `feature/wizard-rts-hybrid-v02`, inspected at commit `6096997` (11 October 2026); Widelands, OpenRA and Mindustry upstream projects. The design has not been playtested as a unified four-era game.

---

# 1. Executive design statement

## 1.1 The game we are making

**DuelMasterBattle is a single-player systemic fantasy adventure set inside a persistent, autonomous civilisation simulation.** The player is an extraordinarily powerful wizard who lives through recurring historical eras, explores functioning settlements and dangerous dungeons, meets and influences persistent people, uncovers local and historical plots, and fights personal Mastermind-inspired magical duels. Political factions build economies, expand, trade, wage war and respond to catastrophes without requiring the wizard's command.

The original abstract Catan-like economy is superseded. **Prehistoric and Historic societies use a Widelands-derived physical economy and adapted OpenRA-style units and real-time combat. Modern and futuristic societies add a Mindustry-derived industrial layer with automation, energy, fluids and complex processing.** The simulation remains one persistent world; an era is a different set of available technology, buildings, resources, recipes, units, risks and art, not a separate game that resets the player's relationships.

The wizard's unique power is local intervention, not omniscient control. Economic failures become personal stories; wars have civilian consequences; dungeons are grounded in the same geography and institutions; ruins and cultural memory survive historical change. The player can observe production chains, learn why a settlement is starving, help or sabotage its inhabitants, or leave and discover the consequences later.

## 1.2 What changes and what stays

| Subject | v0.3 treatment | v0.4 direction | Status |
|---|---|---|---|
| Basic economy | Dice-generated Catan construction goods and calculated industry | One physically conserved ware/resource economy with Widelands-style extraction, workers, production and delivery | **Replace** |
| Industrial ages | Twelve artificial raw types per era, 60 generic combinations, abstract rates | Era-specific, authored/imported production graphs; Mindustry-type items, liquids, energy and conveyors in advanced eras | **Replace** |
| Combat | Three factory archetypes; turn-based inter-node marching; bespoke damage formula | Real-time OpenRA-derived actor, targeting, projectile, armour and orders; era-specific content packs | **Replace** |
| Geography | 19 Catan hexes, settlement corner nodes | Current hybrid's square-grid terrain as the implementation baseline, with strategic sectors/regions to be designed | **Revise** |
| Building territory | Catan spacing, node VP, upgrade | Headquarters/settlement ownership, suitable terrain, caravan-based founding, transport connectivity | **Propose** |
| Wizard duels | Deductive Mastermind-style colour-and-slot combat | Retain distinct personal encounter subsystem and pause contract | **Preserve** |
| Dungeons and puzzles | Spatial mechanisms, persistent locations, era reinterpretation | Preserve and anchor sites to actual settlements, industrial processes, ruins and disasters | **Preserve** |
| NPCs/quests | Persistent people, social checks, generated/compiled dialogue, systemic quests | Preserve, bind to real workplaces, warehouses, routes, units and settlement events | **Preserve** |
| Era history | Collapse, fission, continuity and catastrophes | Preserve the intent; replace the incompatible 10-VP/Catan calculations with a new trigger/transition design | **Decision** |
| Direct RTS controls | Prohibited for player | Current God Mode exists; propose debug/sandbox-only RTS control, separate from adventure mode | **Decision** |

## 1.3 Non-negotiable design identity

1. The world acts even when the player is elsewhere.
2. The wizard is physically present in that world, not a faction commander by default.
3. Goods, workers, resource sites, buildings, units and significant people have causal, persistent consequences.
4. Mastermind-derived magical duels are distinct from ordinary unit warfare.
5. Dungeons and settlement stories respond to the simulated world's facts, not disconnected quest generators.
6. History transforms geography and political identity without casually erasing the player's memory or unresolved stories.
7. Runtime play is offline, deterministic where feasible, and does not require an online LLM.
8. Development God Mode and automated tests must be capable of inspecting and manipulating the same canonical state, without creating a second simulation.

---

# 2. Status language and source-of-truth rules

**CONFIRMED INTENT** — stated in this October request or reaffirmed here: retain wizard duels, dungeons and settlement stories; replace Catan economy with Widelands/OpenRA; add Mindustry as the more advanced economy in Modern and Utopian/Future eras.

**PRESERVED LEGACY** — v0.3 concept that remains appropriate but has not necessarily been re-implemented in the hybrid (e.g. the seven Aspects, quest continuity, catastrophe limits). This is not a claim of working code.

**CURRENT IMPLEMENTATION** — observed from repository code/documentation at the inspected checkpoint; some entries were verified by an agent, not independently executed for this document.

**PROPOSED DEFAULT** — a practical direction recommended in this revision; can be changed without violating prior user decisions.

**OPEN DECISION** — choices with materially different gameplay or technical consequences; no automatic default becomes “locked.”

**DEFERRED** — outside the next playable slice, but a required architecture boundary can be specified now.

The master design decides intended behaviour. The repository's code and executable tests decide what exists. The feature catalogue, architecture handoff and design decision register should explicitly reference one another. An imported sprite, YAML actor or Lua definition does **not** count as a completed gameplay implementation.

---

# 3. The player experience and central loops

## 3.1 Primary wizard loop

**Travel → observe a functioning place → discover people and tensions → investigate → choose dialogue, spell, dungeon or duel intervention → commit an actual world consequence → depart → revisit to see what happened.**

The player can meaningfully change individual lives and local events without controlling everything. They remain a geographically limited outsider and a long-lived witness to history. The absence of a compulsory main quest is preserved: quests, personalities, crises, historical patterns and personal curiosity supply motivation.

**Examples grounded in the new economy:** a smith cannot make swords because iron deliveries are blocked; a fisher's waters are being contaminated by a future factory; a caravan disappears en route to a settlement site; a rival wizard has bound a mine's machinery; two factions contest a river crossing needed for grain; workers complain that a planner diverts food to an army; a ruined launch facility conceals a dungeon from a former cycle.

## 3.2 Civilisation loop, running independently

**Discover terrain and resources → establish a settlement → gather and transform wares → maintain transport and stores → recruit and equip units → defend, trade or conquer → establish additional settlements → change technology and politics.** Civilian and military production obey the same resource conservation rules, with explicit allowances for renewable natural processes and era-transition grants.

Autonomous factions pursue this loop, even if the wizard never visits. Nearby creatures, forestry, fields, individual goods carriers, construction sites and armies should behave consistently with the state seen in a headless simulation.

## 3.3 Adventure and economy must affect each other

A quest cannot create fictitious scarcity if warehouses contain abundant connected stock; a player decision to sabotage a bridge must actually disrupt traffic; destroying a barracks must affect real recruitment. Conversely, major economic events should generate opportunities for meaningful dialogue, discovery, rescue, diplomacy and dungeon exploration. The system must still work when no quest exists: stories arise from real causes, not from scripted fakery.

## 3.4 Perspective and player agency

**Proposed:** keep **Wizard/Adventure Mode** as the canonical campaign. It exposes travel, observation, conversation, exploration, inventory, spells and personal duels. Players may influence leaders and local events, but they do not directly queue buildings or order squads. Keep **God/Strategy Mode** for development, automated testing, balancing and an explicitly optional sandbox; it should not silently become campaign character authority. Any future playable faction-command mode is a separately labelled design decision.

---

# 4. Eras, technology and civilisational character

## 4.1 Era progression

| Era | Visual/social identity | Production foundation | Warfare baseline | Example story pressures |
|---|---|---|---|---|
| **Prehistoric** | Camps, foraging settlements, wood, stone, primitive agriculture | Reduced set of Widelands-style physical collection and craft chains | Clubs, spears, slings, primitive boats; OpenRA-style movement/targeting under low-tech data | Food security, migration, spirits, dangerous caves, rivalry over hunting grounds |
| **Historic** | Villages, towns, farms, castles, guilds, ports | Full Widelands-derived tribal economies, roads, workers, warehouses and processed goods | Spearmen, swordsmen, archers, cavalry, siege equipment; OpenRA-style tactical engine | Trade disputes, succession, siege, famine, artisan politics, demon cults |
| **Modern** | Industrial towns, factories, electricity, rail/road logistics | Mindustry-derived automation layered onto conserved resources: conveyors, power networks, liquids, mass processing | Firearms, vehicles, artillery, aircraft and naval forces using OpenRA-style actors | Pollution, class conflict, industry, sabotage, alien/demon manifestations |
| **Futuristic** | Dystopian **or** Utopian societies, robotics and automated infrastructure | Advanced Mindustry-derived multi-stage materials, networked power, fluids, high-throughput distribution and processors | Advanced OpenRA-like units/abilities, autonomous machines, potentially Tiberian Sun inspirations | AI governance, nuclear/energy threats, environmental restoration, historical archaeology |

**Open decision:** the user explicitly names a *Utopian* era, while v0.3 locks a *Dystopian Future* with Utopia deferred. The proposed data model supports both; the campaign's actual fourth-era path needs a deliberate choice. Do not label Utopia post-MVP simply because the September specification did so.

These are **technology packs on one common world simulation**. The engine should not branch into four incompatible clocks, maps, faction implementations or save formats. Prehistoric should not require the full complexity of the Historic economy from the opening minute; its restricted catalogue is an intentional on-ramp, not the removal of Widelands capabilities from the underlying engine.

## 4.2 Era content definitions

Each era package defines: available civilian buildings; goods/resources; deposits and renewables; workers and specialists; delivery modes; electricity/fluids services; military buildings and recruitable units; prerequisites; environmental changes; art/audio sets; appropriate settlement stories and dungeons; catastrophe variants; technology choices; and transition/legacy rules.

Culture/tribe is a separate **content package**, not a permanent biological faction identity. It determines economic specialisations and unit alternatives within an era. A faction can change culture packages on era transition while retaining its political ID, people and history. The current six faction colours and five Widelands tribes are an implementation baseline, not a permanent cap on eventual identities.

## 4.3 Technological change must be earned and visible

Era change should be triggered by actual civilisational development, not by crossing an arbitrary elapsed-time threshold. The September **10 VP** rule was tied to Catan settlements and cannot be carried over unchanged. Proposed replacement: **milestone-based advancement** informed by settlement networks, sustained production, population/institutions, research and enduring infrastructure, with a configurable upper bound against a stalled world. This remains an OPEN DECISION; formula, pacing and faction competition require playtesting.

Technology cards from the old seven-card rotating draft may be retained as a political/research mechanic, but the exact World Round cadence and hand-passing loop must be redesigned for a real-time world. Do not implement the old draft literally until the time contract is chosen.

## 4.4 History cycles and retained ruins

Retain the signature **Prehistoric → Historic → Modern → Future → reset/new cycle** macro-loop and the possibility of long-term consequences. Geography, special landmarks, wizard memory, meaningful NPC/quest records, selected structures/artifacts and ruins survive according to explicit disposition rules. Political factions may split, merge, collapse or found successor states. A factory need not keep operating after a civilisational collapse; its physical ruin, item effects and dungeon entrance may remain.

No ordinary era transition should silently erase a named NPC, active quest, previously discovered fact or dungeon mechanism. A full civilisational collapse requires explicit asset and NPC migration/retirement rules. Exactly how much older economic infrastructure continues to operate across two different technology layers is a significant OPEN DECISION.

---

# 5. Geography, terrain and world representation

## 5.1 Current source implementation

At inspected branch `feature/wizard-rts-hybrid-v02` / `6096997`, the active hybrid uses a **square-grid terrain simulation with four-direction movement**, rather than the former 19-hex Catan board as its operative construction topology. Its documented standard map is 544 × 288 tiles, with smaller/larger presets, multiple terrain classes, height, water, deposits, designated buildability and world generation. Selected Widelands `.wmf` maps can be loaded via a compatibility translation; Widelands' native triangular terrain/hex geometry is **not** reproduced exactly. The older axial hex coordinate code remains a legacy overlay/fallback in places.

This supersedes v0.3's 19-hex / 54-node / 72-edge Catan foundation for the hybrid path. **Do not reintroduce hex-grid Catan placement rules by accident.** The final mapping of strategic regions, locations and adventure travel onto the square terrain needs a design decision, not an unannounced rewrite of working coordinate code.

## 5.2 Proposed geography layers

1. **World tiles** — ground/water/elevation/deposits, walkability, construction masks, ecological state and tactical movement.
2. **Strategic regions** — named clusters of tiles for factions, travel summaries, catastrophes, territorial claims and era-wide developments; may be visible as sector boundaries without requiring Catan geometry.
3. **Settlement sites** — permanent world positions or polygons with headquarters, buildings, roads and inhabitants.
4. **Interiors and dungeons** — persistent spaces linked to a world entrance and stable IDs, entered without re-creating the village.

One canonical geometry/topology service supplies pathfinding, placement, line of sight, terrain checks, travel distances and map projection. Wizard exploration and unit/worker movement can share passability data while retaining different abilities (e.g. boats and amphibious units).

## 5.3 Land, ecological resources and site suitability

**Proposed terrain vocabulary:** woodland, natural grassland, arable land, pasture, hills, mountains/rock, marsh, riverbank, freshwater, coast/shallow water, deep water, desert and contaminated/ruined variants. These may map to several finer Widelands source terrain types; avoid overwriting or conflating the imported source classifications.

Natural renewables require rules for regeneration or capacity: trees regrow through forestry, fish reproduce to ecosystem limits, game populations recover, agricultural fertility and crops depend on suitable soil, and water may be replenished by an environmental process. Ore, coal, stone and unusual deposits may be finite. **An “infinite source” is not infinite instantaneous output**: rate, worker access, terrain, season/condition and replenishment must matter.

Examples of proposed placement rules:

| Terrain / condition | Eligible operations | Constraints |
|---|---|---|
| Mature woodland or growable woodland soil | Forester, woodcutter, hunter | Trees are physical objects; logging can exceed regrowth |
| Arable fields | Grain/vegetable farms, orchards | Need adequate fertility and workable ground |
| Pasture / grassland | Grazing livestock operations | Separate from arable-crop permission; livestock and fodder rules |
| Rocky terrain | Quarry, stonecutting | Actual accessible rock resource |
| Mineable mountain | Mine | Matching nonempty deposit, support/terrain requirements |
| Water and shore | Fishers, ports, docks, naval yards | Water depth, shore geometry and navigability |
| Industrial terrain | Factories, power, conveyors, pipes | Footprints, capacity, utilities and pollution rules |
| Settlement centre | Headquarters, warehouse/civic building | Legal founding site, clear footprint and minimum spacing |

The existing Widelands-derived build-cap checks are a starting point; new biome names, pasture exclusivity and settlement spacing are proposed additions, not claims that this all already works.

## 5.4 Settlements and expansion caravans

**Design candidate from the October discussion:** the central **Settlement Headquarters** combines an MCV's founding function with a main Widelands warehouse. It is permanent after deployment. Ordinary warehouses continue to exist and distribute wares. A **wagonwright/war factory** may manufacture an **expansion caravan** (later technology packs can substitute trucks, mobile bases or automated colony units). The caravan is a real unit with cargo, route, vulnerability, faction ownership and founding capability.

Founding validates: viable terrain and building footprint; distance from all existing headquarters including hostile ones; accessible land/sea route as applicable; any faction/resource prerequisites; settlement cap/political rules; an explicit starter package physically carried or consumed. Deployment is a one-time transition from caravan instance to permanent headquarters and must not duplicate contents or entity identity references. A deploy failure leaves the unit and cargo intact with a clear reason.

**Open decisions:** whether the headquarters counts as the only territorial origin; exactly how large the exclusion radius is; what happens to a captured or destroyed headquarters; whether city upgrades exist; what separates a warehouse satellite from a fully independent settlement; whether disconnected settlements can function autonomously.

---

# 6. Common economy contract across all eras

## 6.1 One conserved economy, changing transport/processing

The revised game replaces Catan's five dice-produced construction wares and abstract industrial throughput with **real inventories, production demands and physical/logically constrained delivery**. Wares have canonical type IDs; amounts exist at sites, in worker/carrying entities, in shipping buffers or reserved by transactions. A resource deposit is a separate environmental source, not an unlimited warehouse.

Proposed shared concepts:

- `ResourceDefinition` and `ResourceDeposit`: geography, amount/capacity, regeneration, extraction operation.
- `WareDefinition`: storable item, unit and properties; later-era products may be grouped by category without becoming interchangeable.
- `RecipeDefinition`: typed inputs/outputs, alternatives, timings, tools/workers, heat/power/fluid dependencies.
- `BuildingDefinition`: footprint, construction costs, programmes, workplace roles, storage, power/fluid/road interfaces, terrain permissions.
- `Inventory` / `Shipment`: on-site and in-transit, with reservation and once-only delivery.
- `ProductionOrder`: building/unit/ware target with explicit prerequisite and progress.
- `Network`: roads/carriers, conveyors, item junctions, liquid pipes, power distribution and advanced transport — different implementations of typed connections.

No ware may be in a source warehouse and inside a carrier simultaneously. Production consumes required inputs exactly once and yields outputs exactly once. Renewable extraction creates ware only through an authorised environmental process. Failed transport cannot teleport stock. Damage, capture and demolition must settle outstanding reservations and cargo according to policy.

## 6.2 Why not two competing resource ledgers?

The September document intentionally separated Catan construction goods from industrial flow. That distinction should be retired. A modern factory may require timber, copper, steel and power; a barracks may consume food and weapons; a settlement caravan carries building materials. They all use shared item identity and inventory contracts, even if different transport infrastructure handles them.

**Power and some fluid services differ from wares:** electricity is usually a rate/network capacity, not a box in a warehouse; fluids may have tank/buffer volumes and pipe flow. They need typed quantity/flow accounting so they cannot accidentally be shipped as ordinary discrete crates. This extends one economy model, not a wholly disconnected economic world.

## 6.3 Production graph and economic AI

The engine should compute a dependency graph of ingredients, producers, by-products, alternatives and infrastructure services. The AI must be able to infer that a missing iron sword is ultimately blocked by ore extraction, coal supply, smelting, smithing, transport or construction prerequisites. It must distinguish **available globally** from **available via a connected feasible route within a useful time**.

Bootstrap cycles are forbidden unless a starting grant or alternative recipe breaks the cycle. AI planners and inspectors need explicit “blocked because...” explanations. Complex advanced chains should use queues and buffers, but a queued unit is not permitted to materialise without delivered goods.

## 6.4 Widelands-inspired physical labour

For Prehistoric/Historic periods, gathering, planting, harvesting, tending livestock, mining, building and transporting should rely on real workplaces, workers and logistics. The current hybrid already moves named workers and carriers and keeps conserved warehouse stocks in core cases. Imported Widelands Lua programmes should remain authoritative where correctly supported, with documented deviations (square topology, missing worker behaviours, omitted military buildings).

The old specification's statement that worker movement is *decorative* is superseded. The updated principle is: **the canonical production programme and actual transport state determine the result; rendering of the worker is not itself a separate truth**. If workers are physically blocked, they must not both remain stranded and simultaneously complete their task by invisible fiat unless a specific off-screen level-of-detail simplification is contractually and deterministically defined.

## 6.5 Era migration and shared legacy commodities

Some wares persist across eras — timber, stone, grain, iron — while specialised wares and technologies appear later. Each historical instance records its source era/culture and definition version. An advanced factory may use an old resource through an explicit compatible recipe; old buildings do not magically convert their production without a validated upgrade.

If a new era introduces automated extraction, it can compete for ore deposits with surviving manual mines; both withdraw from a shared environmental resource with correct accounting. Old, abandoned mines can become dangerous dungeon spaces while retaining historical provenance.

---

# 7. Prehistoric and Historic: Widelands + OpenRA

## 7.1 Civilian economy target

Initial content target is the **meaningful breadth of the five Widelands tribal economies**: woodcutting/forestry, quarrying, mining, crops, animals, hunting, fishing, water, tools, textiles, food, smelting, smithing, processing, worker assignment, roads, warehouses, transport and relevant trade/ports. These are adapted through the actual supported source data and behaviours, not re-created as a 60-recipe combinatorial shortcut.

Prehistoric is a restricted subset: foraging, basic timber, stone/flint, crude tools, shelter, hunting and food preparation. Historic unlocks the larger craft and organised-production system. The original Widelands military barracks/training buildings should be deprecated as military producers in favour of the shared OpenRA-style recruitment framework; their recipes, visuals or historic-world references may remain where useful.

## 7.2 Military production

Replace Widelands military production sites **in the active gameplay catalogue** with OpenRA-style production queues backed by real Widelands goods. Proposed buildings and products:

| Production site | Example units | Example real wares/services |
|---|---|---|
| Training camp / Barracks | Spearman, swordsman, skirmisher, archer | Food, spears/bows, armour, staff/recruit |
| Stables | Scout, mounted archer, heavy cavalry | Horses, tack, food, weapons, leather |
| Siege yard | Catapult, ram, siege tower | Logs/planks, iron, rope, stone |
| Wagonwright / War factory | Cargo wagon, expansion caravan | Timber, iron, cloth, wheels, pack animals |
| Dock / Naval yard | Fishing boat, transport, war galley | Planks, rope, sailcloth, metal fittings |

All recipes are illustrative; exact equipment and amounts come later from a consolidated economic worksheet and balancing. Units are actor definitions independent of whether their mechanics originally came from an OpenRA rifleman, jeep, tank or boat. The source actor identity is provenance, not final gameplay nomenclature.

## 7.3 Combat contract

Use one real-time simulation for movement, orders, attack selection, weapon and projectile behaviour, damage/armour, death, buildings, and faction AI. It should be data-driven: a spearman is short-range anti-cavalry infantry; an archer uses projectile and reload attributes; cavalry is mobile shock force; siege engines are slow, vulnerable building attackers. Distinct units have their own IDs and injuries. Combat persists without the wizard present.

**Avoid introducing a second handcrafted damage formula for early eras.** Use OpenRA-inspired rules through canonical actor/weapon interfaces, applying era scaling in defined data. Imported actor/weapon features not yet implemented must be tracked by behaviour, not actor count. God Mode can issue orders for tests; the campaign's wizard watches, influences or intervenes instead.

## 7.4 Source integration goal versus implementation reality

The October branch is a Python-led simulation using imported Widelands data and OpenRA-derived combat mechanics. It is **not** both original engines executing together. That is acceptable if the behaviour is robust and comprehensively tested. Inventory all source-game capabilities and be honest about unsupported operations. The current production and combat implementations already include meaningful vertical slices, but not all workers, ships, aircraft, training, formation mechanics or AI behaviours.

---

# 8. Modern and Future: Mindustry as an advanced economy layer

## 8.1 What “using Mindustry” means

**Proposed scope:** adopt Mindustry's fundamental industrial logic, content ideas and where lawful, adapted source mechanics for **automated production, power, liquids, transport, specialised processing and high-throughput logistics**. Do not require the entire Mindustry game loop, waves, cores, launch sectors or its RTS controls to be embedded unchanged. The player remains the wizard and the world still has Widelands/OpenRA-style factions and settlement continuity.

Mindustry is implemented in Java and has a GPL-3.0 licence; it is not currently a demonstrated runtime component of this hybrid. Its source provides a reference and possible reusable code/content under licence review. It should be treated as a future integration programme, not a feature achieved by importing a catalogue.

## 8.2 Transition from manual logistics to automation

Modern settlement infrastructure introduces conveyors, unloaders, sorters, storage buffers, liquid conduits/tanks, drills, power generation and distribution, factories, repair facilities and automated defence supply. This is the same inventory/recipe model as earlier eras, with different transport and service graphs.

A medieval road carrier and a modern conveyor serve the same **abstract delivery objective**, but do not use the same motion/throughput implementation. A worker can still exist as an NPC with a job, while automated lines increasingly dominate industrial rates. Old road systems and new conveyors may run side by side.

## 8.3 Advanced processing, energy and fluids

- **Items:** ores, basic materials, intermediate goods, alloys, components, equipment. Deterministic transfer along conveyor/loader/storage networks, with capacity and backpressure.
- **Fluids:** water, oil, coolant and other liquids as buffered volume/flow with pipe connections and mixing/consumption rules.
- **Power:** generators, batteries, grids, consumption priorities, outages and surplus. A stalled grid must actually stop reliant factories.
- **Machines:** recipes, speed, efficiency, optional heat/catalysts, upgrades and maintenance; queues cannot consume the same input twice.
- **Networks:** belts, junctions, bridges, unloaders, mass distribution and advanced inter-settlement transportation once unlocked.
- **Pollution and land:** industry may contaminate water/soil, damage NPC livelihoods or create catastrophe risk; feedback into settlement stories and era advancement.

## 8.4 High-tech units and shared combat

Modern and future units continue using the common military framework. Armies may include infantry, armour, artillery, aircraft, naval units and advanced robots/drones. Mindustry-style production modules can fabricate equipment, components and whole units, but unit identity, tactics and combat remain in one OpenRA-derived actor system. Do not let a separate Mindustry simulation mint untracked units or ignore settlement stock conservation.

Potential Tiberian Dawn / Red Alert / Tiberian Sun inspirations are content inputs, not promises of one-to-one transfer. Tiberian Sun's OpenRA support/completeness must be independently verified before adopting it as a dependency.

## 8.5 Modern and Utopian differentiation

Modernity is not just faster medieval industry. It introduces mechanisation, electrification, liquids, volume throughput, potentially pollution and worker displacement. A **Utopian future** can favour clean energy, efficient recycling, ecological repair and distributed nonviolent systems; a **Dystopian future** can favour weapons, nuclear risk, coercive automation and hostile AI. Both can use the same advanced economy definitions with different policies, catastrophes, content packages and aesthetics.

Do not make sustainable resources literally costless or eliminate logistical challenges: recycling consumes time and energy; clean energy has infrastructure cost; advanced materials still depend on supply chains. This preserves the causal storytelling engine in optimistic eras.

## 8.6 Where should the advanced factory simulation run?

**Recommended architectural boundary:** maintain one authoritative Python world with **local factory-network sub-simulations** owning conveyor, pipe and power state. A fast area may use more detailed simulation near the wizard; distant factories may run an equivalent deterministic throughput abstraction, provided the conservation/production and event contract is consistent. This is a design proposal requiring technical proof, especially at the current laptop's reported terrain frame rate.

No second Mindustry Java process should independently control canonical resources or combat without an explicit synchronisation and replay protocol. Source-level integration and implementation strategy are OPEN DECISIONS.

---

# 9. Factions, AI, wars and society

## 9.1 Political state

Factions retain identity, leaders, diplomatic relations, settlements, culture/technology policy and history. The current hybrid has six AI factions with Widelands tribe assignments; this is a testable starting configuration, not the sole final political structure. Factions should create, defend and rebuild settlements; share or contest resources; respond to real shortages; negotiate trade; and react to catastrophes and the wizard.

A faction is not a culture, species or era. A political successor can inherit people and property while acquiring a new cultural/economic package. Military defeat does not automatically erase its NPCs.

## 9.2 One command contract for AI and strategy mode

AI agents and God Mode should issue the same validated commands: place a building, request a road, set a production queue, move/attack, establish a settlement, adjust policy, make a shipment and so forth. AI receives observations from the canonical world and does not mutate inventories secretly. The newly introduced headless `HybridEnv` training interface is a useful seam; it is not evidence that a trained strategic model exists or that the campaign should require one.

The campaign wizard instead acts through dialogue, spells, quests, diplomacy and physical interaction. No conversation directly bypasses command legality or hands the wizard an invisible army-control API.

## 9.3 Economic military causality

Recruitment fails when the goods are unavailable; distant material needs transport; enemy attacks may destroy workshops, roads, power, storage, barracks or home settlements; shortages affect both war readiness and civilian wellbeing. AI should strategically prioritise replacement of missing inputs, rebuilding logistics, local defence and expansion. It needs shortage diagnosis and the ability to found additional settlements, not simply hardcoded next-building sequences.

## 9.4 War, occupation and aftermath

Real-time units can fight anywhere, visited or not. Capture, retreat, surrender, siege and post-war occupation are separate rules requiring decisions and development. Named soldier/NPC casualties, refugees, ruined facilities, food loss, memorials and changing ruler policy should flow into settlement plot generation.

**Potential balance issue:** the September wizard could destroy any ordinary unit or building instantly and could not be harmed by faction military. This is preserved as a **legacy intention**, but needs an explicit balance decision under richer RTS combat. Local presence and social repercussions may restrain it; inventing a mana system without approval would change a prior explicit rule.

---

# 10. Wizard, magic and Mastermind encounters

## 10.1 Preserve the wizard as the protagonist

Keep the established personal viewpoint, investigation, social influence, historical memory and very unusual magical power. The wizard should not acquire generic RPG hunger, armour, XP levelling or a compulsory faction profession. The player may witness or intervene in nearby battles but is not a conventional RTS commander.

## 10.2 Mastermind-style duels

**Preserve the existing duel mechanic and implementation**: hidden sequence of colours, deduction from partial feedback, attempts/casts, configurable slot and colour counts, rival wizard/hazard actions and outcome effects. The original working starting baseline is **four slots, six colours, repeats allowed, ten casts per side** (subject to what the current code actually supports). Quest awards may add colours and slots. Do not replace these with ordinary weapon fights when modern units or Mindustry machinery appear.

A duel is an encounter over personal magical agency. The world and its economic/military clocks should pause according to a single explicit token/lease. Current hybrid documentation says the Ward Duel pauses `game_ms`. That working behaviour should be protected by regression tests through all era packages. The duel's own input/animation/cast clock remains playable.

## 10.3 World magic, hazards and catastrophe

The earlier specification separates rival-wizard/hazard duels from world effects such as destroying or buffing units/buildings and treating catastrophe manifestations. Retain that conceptual separation. World magic changes canonical state through validated typed effects and affects the owning settlement's resources, political relations and quests.

Candidate legacy rules: no ordinary mana meter; spell unlocks primarily through quests; temporary unit buffs; catastrophe treatment limited by physical presence/visit; extraordinary wizard survivability. Their final numbers and exceptions are OPEN for confirmation because the new continuous geography changes what a “visit” or “adjacent hex” means.

## 10.4 Major wizard cast and story progression

The broader project has considered recurring faction/colour-associated rival wizards and an opening sequence involving the player arriving in a settlement, learning an ordinary trade, gaining magic and duelling a mentor/rival. **Do not replace existing authored cast, dialogue or quest data with generic NPCs.** Before declaring story canon, inventory the repository's actual character IDs, scenes, quest gates and drafted story notes. Distinguish implemented scenes from earlier narrative proposals.

---

# 11. NPCs, settlement stories and dialogue

## 11.1 Stories live in real places

A settlement is the physical setting for its stories. NPCs have workplaces and routines attached to warehouses, bakeries, mines, ports, farms, factories, barracks, civic centres, inns and homes. A settlement that shifts from a timber village to a mechanised city retains street geography, landmark history, named people or their records, and durable quests where plausible.

**Preserve the original system of anchor NPCs:** each meaningful production building may have an associated named or persistent NPC with goals, preferences and memories. Not every moment of every generic worker's life needs simulation, but important workers have stable IDs and consequences if displaced or killed. Widelands worker objects and narrative NPC identities must be linked, not duplicated by separate rosters.

## 11.2 Quest generation contract

Preserve the September grammar: **world condition → affected entity → NPC who cares → desired change → obstacle → intervention options → validated world effect**. Its initial families remain useful: production shortage, blocked delivery, catastrophe response, diplomacy, military threat, personal NPC problem, discovery and conflicting interests.

A quest has a persistent ID, version, cause, bound entities, history, branches, state and applied-effect receipts. Revisit cannot respawn an already completed quest or resurrect a destroyed building. If an autonomous faction fixes the initial shortage before the wizard arrives, recognise a `resolved_by_world` outcome. If a named worker dies, support a successor/displacement/failure branch.

New economy-specific examples:

- A shepherd needs access to pasture blocked by a newly placed factory.
- A copper mine is exhausted; rival factions dispute a remote replacement deposit.
- A converter requires coolant; an industrial administrator conceals water shortages.
- An armourer's trade collapses when an era upgrade switches demand to firearms.
- A convoy of founding settlers needs a safe route across contested ground.
- A power outage traps a population behind automated gates, creating a dungeon-like rescue problem.

## 11.3 Dialogue and seven Aspects

**Preserve the v0.3 proposed seven Aspects**, pending implementation inventory: Reason, Empathy, Authority, Guile, Resolve, Curiosity and Wonder. They are faculties for checks, internal commentary and interpretations, rather than generic combat skills. The earlier 0–5 scores, starting at 1, with deterministic thresholds 2/4/6 and evidence/relationship modifiers remain a useful *legacy numerical baseline*, not a newly verified code fact.

Dialogue should read structured canonical facts: speaker, identity/knowledge, personal history, social position, faction, culture, era, home, workplace, local stock/transport/production state, war, catastrophe, relationships, active quests and past player choices. Unknown information remains hidden or appears as fallible inference. The player can walk away; dialogue does not become an unavoidable full-screen visual novel.

## 11.4 Offline prose compilation and truthful effects

Retain the prior principle: LLMs may help author or precompile diverse speech, attitudes, quest variants and histories **offline**; canonical facts, branches and state changes are owned by the game. At runtime, deterministic content selection uses validated structured data. No internet LLM is required for play. Typed quest effects can adjust relationships, policies, goals, labour status, deliveries, discovered knowledge, items and history only after the owning system validates preconditions.

## 11.5 Settlement narrative scaffolding

Each named settlement should expose, at minimum, a place identity, faction/culture, economic strengths, critical dependencies, local institutions, important people, recent events and unresolved tensions. A dynamic **settlement chronicle** records construction, disaster, production collapse, war, leadership change, migration, era upgrade and player intervention. This becomes the factual source for dialogue, rumours, dungeon clues and return visits.

The wizard's knowledge must not become a global economic debug dashboard by default. Debug view can show exact stock; adventure view uses observation, conversations and discovered evidence.

---

# 12. Dungeons, exploration and puzzles

## 12.1 Retain core dungeon identity

Preserve explorable interiors, spatial reasoning, environmental mechanisms, loops, optional secrets, switches, pressure triggers, keys, movable items, timed devices, doors, passages and dialogue clues. Dungeon gameplay is not replaced by building automation or RTS map traversal. Mechanism logic should be reusable across eras while the fiction changes (cave → mine → temple → bunker → laboratory → machine complex).

## 12.2 Connect dungeons to settlements and landscape

A dungeon entrance occupies a real world location: disused mine under a quarry, woodland cave, coastal ruin, old barracks basement, hydroelectric intake, derelict industrial plant or advanced research facility. Settlement events create or transform entrances; a later era can build over an old dungeon and expose its deeper layers. Buildings and NPCs should reference entrance/site IDs; world destruction may change accessibility but must not silently wipe puzzle history.

Dungeons contain consequences relevant to the world: returning stolen tools, unlocking a watercourse, rescuing a worker, restoring a power node, discovering an historical truth, removing a magical hazard or altering political trust. A reward may improve a real production condition through a validated effect, rather than an arbitrary resource spawn.

## 12.3 Persistent mechanisms, failure and soft locks

Puzzle states, items, doors, moved objects and completed branches survive exit, save and ordinary era change. Mandatory puzzle items have a recovery or alternate ending contract. Destruction of a settlement must trigger a quest/dungeon reconciliation path if a previously important entrance disappears. A required key cannot be permanently buried by map regeneration with no route to resolution.

## 12.4 Narrative “plots” and authored story arcs

Preserve authored recurring characters, rival wizard motives, distinctive dungeon arcs and settlement episodes where source material exists. Use a **story canon inventory** linking narrative beat → character IDs → settlement/world entities → era applicability → actual scene/quest files → test coverage. The present revision supplies an integration framework, not a claim that every historic plot is already implemented.

---

# 13. Time, simulation scale and pauses

## 13.1 Retire the Catan turn clock as an economic authority

The former World Turn generated dice goods, moved carts one edge, permitted army travel, drafted technology and advanced catastrophe. This is incompatible with the current continuous hybrid, where production, carriers, troops and combat already advance in simulated time. **Do not maintain the old World Turn mechanism as a second competing production/war clock.**

**Proposed:** one fixed-step **Game Time** owns the economy, all real-time units and environmental processes, both on- and off-screen. Player travel consumes actual simulated movement time or an explicitly measured fast-travel advance. Waiting advances the same world simulation. Formal menus, duels and certain authored encounters can pause it with explicit tokens. An optional longer **Council/History Tick** groups political decisions and research, but never mints goods or teleports armies.

## 13.2 Long-distance simulation and performance

The world must advance when no scene displays a distant settlement. However, simulating every conveyor and worker at full animation granularity everywhere may be infeasible. Use deterministic simulation tiers: high-fidelity nearby entities and economically equivalent off-screen scheduling at a slower cadence or aggregate batches, reconciling inventories and events exactly. This is a technical proposal requiring equivalence tests, not permission to produce fake goods.

Simulation performance, not merely rendering FPS, must be measured. Latest repository handoff reports low headed FPS on a full map on an older integrated-GPU laptop despite much faster headless advancement; gameplay budgets and profiling must target both.

## 13.3 Encounter ownership

A Mastermind duel obtains a global pause/lease; its own clock continues. Active dungeon puzzles own local mechanism state but emit canonical typed events. The world owns ordinary warfare and worker/economy state; Godot is primarily presentation and input. If Godot needs temporary encounter authority, use an explicit versioned lease and once-only event handoff. The original v0.3 contract that Godot independently computes live battles while Python calculates off-screen battles should be reviewed; one authoritative combat model is less risky if practical.

## 13.4 Reproducibility

Save seeds, configuration versions, ordered commands, times, RNG states, outstanding shipments, all relevant entity versions and chosen AI actions. Use stable IDs and deterministic tie-breaking. A save/load or window-focus pause cannot advance factories or give the wizard extra actions. Visual animation never consumes gameplay RNG or creates canonical wares.

---

# 14. Catastrophes, social consequences and historical pressures

## 14.1 Preserve catastrophe as the main global existential risk

Catastrophe is a separate problem from individual military loss. It spreads, produces regional pressure, affects economies, creates dungeons/quests, alters diplomacy and may eventually terminate a cycle/run. The earlier theme progression remains useful: demons/spiritual disturbances in early eras; pollution and alien incursions in Modern; nuclear, hostile AI or other advanced threats in dystopian futures. Utopian futures may face ecological restoration failures, runaway optimisation, intrusive systems or returning supernatural forces.

## 14.2 Replace old hex-cube accounting carefully

The September model uses catastrophe “cubes” on the 19-hex board, adjacent-hex treatment, a three-target visit allowance and an eight-outbreak loss threshold. That geometry no longer maps cleanly onto the square-grid simulation. **Preserve the bounded-attention principle but redesign the unit of exposure, region, proximity and treatment.** Candidates: region severity per strategic district; physical hazard sources/spread fields; settlement exposure; timed thresholds with local treatment windows. Exact cap, reset and trigger stay OPEN.

Catastrophes must affect actual mine yield, roads, health, water, power, crop production, AI behaviour and NPC displacement. Their visual and narrative presentation must make escalating danger readable before catastrophic failure.

## 14.3 Failure as history

A ruined settlement, lost war, failed rescue or broken friendship normally remains a story, not instant Game Over. Named NPCs have loss and displacement outcomes. The wizard remains unusual; a terminal run-ending catastrophe needs unambiguous rules and fair forewarning. Save/reload and quest recovery prevent accidental hard locks.

---

# 15. Technology, progression, diplomacy and era transitions

## 15.1 Research and capability

Technology is partly represented by real ability to build and supply prerequisites, not merely an abstract card. If a faction unlocks engines but lacks oil, steel or power, the new unit remains unavailable. An era package can add general technology; a faction's selected research can unlock or improve particular recipes, factories, networks, AI policy and military types.

The former seven-card draft is **optional preserved content**, pending decision on how it coexists with continuous time and physical prerequisites. It could become periodic council drafting, political doctrine, research choices or era-defining cultural inventions.

## 15.2 Expansion and era progression are distinct

Founding a settlement via caravan extends territory during an era. Advancing from Historic to Modern changes technology and social structures while keeping settlements, roads, people and history recognisable. Splitting a nation into successors is a political process, not the same operation as founding a new town. These require separate state transitions and tests.

## 15.3 Transition transaction

Proposed order: save/pause at a clean simulation boundary → snapshot actors/relationships/quests/dungeons/logistics → evaluate advancement and faction disposition → apply validated technology/culture upgrades → migrate/retain/retire relevant buildings and transport services → account for all wares/power/shipments without duplication → update geography/ruins → reconcile linked NPC/quest/entrance references → resume all clocks → record transition in chronicle. Never delete a living character or cancel a quest simply because the era name changed.

## 15.4 What survives, what upgrades, what becomes a ruin

| Object | Default recommendation | Needs decision? |
|---|---|---|
| Wizard, knowledge, spell progression | Fully persistent | Existing intent; confirm rules |
| Named NPC, relationships, active quests | Stable IDs and continuity until in-world events change them | Ageing/generations across millennia |
| Land and environmental history | Persistent; natural ecological change allowed | Geographic tectonic resets? |
| Headquarters and settlement identities | Persist if polity survives; upgrade in place with explicit costs | Yes — new-era starting grants |
| Wares and shipments | Retain stock and locations, migrate compatible definitions | Yes — obsolescence/recycling |
| Buildings, workers, machines | Retain until explicitly upgraded/closed/destroyed; legacy operation configurable | Yes — cross-era labour and power |
| Ordinary military | Survive ordinary era shift, may become obsolete; reset after full collapse | Yes — combat balance |
| Roads, conveyors, power | Physical traces remain; functioning networks by explicit condition | Yes — network conversion |
| Dungeons/puzzles/quest items | Persist or deliberately transform with alternate route | Existing intent |
| Ruins and monuments | Remain as place/history, may unlock exploration | Existing intent |

---

# 16. Presentation, UI and feedback

## 16.1 Canonical adventure camera and controls

Preserve readable 2D top-down sprites and direct wizard motion, contextual inspect/talk/use/cast actions, semantic labels, puzzle/dungeon transitions and approachable controls. The UI should never require the player to monitor a spreadsheet of warehouses to follow a story. Reveal economic truth through workers carrying supplies, idle factories, queues, inventories that a character can reasonably inspect and NPC testimony.

## 16.2 God Mode and diagnostic presentation

Maintain RTS controls and exact debug information as optional engineering tools, including building/terrain inspect, supply chain explanations, unit orders, multi-selection, test captures, pause/clock controls, minimap and programme traces. No duplicate rule logic in UI. World tiles, sector claims, build eligibility and resource overlays must reflect Python authoritative data.

## 16.3 Narrative clarity of automation

In Modern/Future eras, visually distinguish transport line direction, network failures, power shortage, liquid blockage, output bottlenecks and contamination. NPCs and local story scenes must exist alongside large factories; advanced industrial maps cannot become empty conveyor puzzles with no inhabitants.

---

# 17. Technical architecture and extension contract

## 17.1 One world, pluggable content packs

The existing Python `HybridWorld` owns the authoritative simulation; Godot presents it and sends validated commands. The source-derived Widelands stock/programme logic, OpenRA-derived combat, current terrain/square-grid tools and new Mindustry-derived factory networks should be separate systems sharing common entity IDs, data schemas, clock and event contracts.

**Recommended modules/interfaces:** `WorldState/Clock`; `Terrain/Topology`; `Faction/Settlement/Territory`; `DefinitionRegistry`; `Economy/Inventory/Production`; `Logistics` (roads/carriers/conveyors/pipes/power); `Unit/Combat/Order`; `AI/Planning`; `NPC/Quest/Knowledge`; `Dungeon/Puzzle`; `Magic/Duel`; `History/EraTransition`; `Save/Replay`; `Presentation Adapter`. These are responsibilities, not an instruction to create fourteen new packages immediately.

## 17.2 Import pipeline and provenance

`Pinned upstream Widelands/OpenRA/Mindustry data` → `versioned importer` → `normalised validated canonical definitions` → `optional additive override/era pack` → `runtime registry` → `simulator`. Keep original IDs and hashes for traceability; new gameplay IDs must not collide. Never hand-edit generated imports as a way to customise a spear or conveyor. Record deviations from upstream mechanics and licence obligations.

Widelands' physical worker/ware programme grammar, OpenRA's actor/weapon/trait schema and Mindustry's block/item/liquid/power definitions are different source languages. The canonical format should encode *meaningful interoperable behaviour*; it need not promise universal execution of every possible upstream scripting feature. Unsupported commands must fail validation or be explicitly documented, never silently become free production.

## 17.3 Definition examples (illustrative, not production schemas)

```yaml
ware: military.iron_spear
extends: widelands.iron_spear_generic
inputs: [metal.iron, wood.plank]
category: equipment

unit: historic.spearman
role: infantry.anti_cavalry
producer: historic.barracks
consumes: {military.iron_spear: 1, food.ration: 1}
combat: {weapon: historic.spear_thrust, range_cells: 1, movement_class: foot}
art: historic.spearman_set

building: historic.barracks
terrain_allow: [settlement_land]
construction: {wood.plank: 6, stone.granite: 3}
production_queue: infantry.historic
road_connection_required: true
```

```yaml
building: modern.coolant_plant
construction: {metal.steel: 20, component.electronics: 8}
consumes_liquid: {water: 10_per_second}
consumes_power: 80_per_second
produces_liquid: {coolant: 6_per_second}
placement: {land: true, pipe_connectable: true}
```

These examples are intentionally compact. Source syntax, units of time, power, fluid and collision requirements must be defined and schema-validated before actual use. The test of extensibility is whether adding these files creates working behaviour **without editing `world.py`, `military.py` and `ai.py` for each new ID**.

## 17.4 Save state, consistency and transactions

Stable IDs must distinguish definition from runtime instance. Save settlement headquarters, region/ownership, deposits, renewable state, inventories, reservations, carrier routes, conveyor queues, pipe/fluid volumes, power-grid state, current recipes, units/orders/health, NPC identities/relationships, quest/puzzle mechanisms, duels, catastrophes, era, RNG, history and bridge state. Atomic, idempotent commands should prevent double spend, duplicate troop recruitment and repeated quest rewards. A release-compatible migration strategy is required before a public campaign save format is promised.

## 17.5 Testing and visual evidence

Use headless unit and integration tests for conservation, production, mobility, combat, AI expansion, save/reload and deterministic replay; headed Godot screenshot tests for the actual visual world; longer autonomous multi-faction runs; a reproducible source-catalogue coverage report; and evidence tables connecting expectations to captured results. Nightly runs need a bounded event log, performance summaries and documented checks of screenshots for missing, misplaced or unchanged entities.

Test example sequence: lumberjack fells a tree → log delivered → sawmill processes → smith/carpenter builds an item → barracks requests it → delivery fulfils queue → visible spearman appears → receives move/attack order in test mode → outcome persists while wizard enters and exits a duel → a caravan founds a second settlement using correctly conserved cargo.

A future Modern test should follow ore → conveyor → smelter → component factory → power/fluids → unit factory → produced vehicle, including outages, clogged output and enemy sabotage.

## 17.6 Current hybrid baseline (documentation, not independent execution)

At the inspected source checkpoint, branch notes report: a square-grid Widelands-derived terrain model and Widelands map import; six AI factions; forestry, agriculture, mining, fishing, road transport and conserved goods; production-driven OpenRA barracks; projectile/damage/filter mechanics; early coastal naval yards, boats and submarines; a switchable God Mode; retained Ward Duel; a headless `HybridEnv` agent interface; nine headed test scripts and approximately 105 passing Python tests in the documented Ubuntu session. Some documentation tables still contain older “missing fishing/ships/terrain” entries; **the project documentation needs reconciliation before treating counts or status descriptions as current**.

Known broad gaps include full Widelands programme coverage and worker roles, source-equivalent complex logistics, complete OpenRA actor/trait coverage, AI settlement expansion, comprehensive unit/terrain art and performance. Modern/Future Mindustry systems are not yet implemented by this hybrid. Verified status must come from source plus current test evidence, not this design document.

---

# 18. Milestones, acceptance and scope

## 18.1 Development order

**M0 — freeze and document the working hybrid.** Run latest Linux/Windows tests; reconcile `STATE_OF_PLAY`, `PROJECT_STATUS`, `DECISIONS`, task ledger and handoff; preserve user changes and source provenance.

**M1 — complete Widelands civilian economy and logistics.** Close supported recipe/worker/asset gaps across tribes, handle input alternatives and real transport, validate conservation and availability, and prove AI can sustain basic settlements without free fallbacks.

**M2 — complete OpenRA-style general military simulation.** Expand actor/weapon features, movement/pathfinding, targeting, patrol/guard/repair, land/naval/air as prioritised, unit production from real wares and militarily credible AI. Keep imported content separate from playable medieval overlays.

**M3 — separate story canon from the old Catan world.** Build canonical places/settlements, named NPCs, semantic interaction, a real shortage-driven settlement quest, a persistent dungeon and an end-to-end Mastermind duel on the same active map.

**M4 — add settlement expansion and geographical economy.** Caravan production, destination validation, permanent headquarters, multiple warehouses, territory ownership, eco-terrain suitability and AI expansion; no stock teleportation.

**M5 — prove Prehistoric/Historic era content packs.** Era-specific buildings/units, stage-appropriate art/recipes, persistent settlements and an auditable era-transition/save case.

**M6 — Mindustry-style factory vertical slice.** One electricity network, one conveyor production line, one fluid network, stock conversion to a real modern unit, outage/backpressure tests and an NPC quest caused by the new industry.

**M7 — Modern and future systems.** Broaden automation, advanced combat, environmental consequences, technology/era policy, Utopia/dystopia branch resolution, recurring historical continuity and long-cycle automated tests.

## 18.2 New vertical slice: “the settlement that makes a spear”

A testable first adventure settlement has a forest, arable/pasture land, a mineable deposit, a warehouse headquarters, real producers, roads, a barracks and several persistent NPCs. A player can walk past working industry; observe a real shortage; talk to an affected person; enter a dungeon linked to that shortage; use a puzzle or magical duel; alter the real cause; and later observe a spearman recruited from delivered goods. God Mode can verify production and combat without becoming the player fantasy.

Acceptance: the same seed and commands reproduce goods conservation, visible causality, correct quest dialogue, persistent IDs, duel pause, and no duplicated stock after save/reload or scene transition.

## 18.3 Minimum releasable identity

A mere RTS demonstration is not a DuelMasterBattle MVP, and a fully simulated factory with no stories is not the game. A meaningful MVP needs **one functioning economy–warfare–adventure junction**: real production, at least one autonomous factional conflict, a persistent settlement with characters and reactive dialogue, one explorable dungeon, one Mastermind duel, and a lasting player choice. The **complete source-game feature baseline** is a separate longer-term implementation objective; do not postpone testing the actual wizard game until every upstream unit and building is copied.

---

# 19. Decision register — material conflicts to resolve

The following are *not* silently settled. Owners and dates can be assigned in the repository's formal design register. “Recommended” means a default for discussion, not a user approval.

| ID | Priority | Decision | Existing conflict / choices | Recommended working direction |
|---|---|---|---|---|
| D01 | **Now** | What is the fourth era? | September: dystopian Future required, Utopia deferred; October: explicitly “utopian eras” | Data supports both; choose Utopia as primary, alternative or branching future deliberately |
| D02 | **Now** | Is campaign strategy directly controllable? | September forbids RTS orders; current hybrid God Mode does issue orders | Wizard campaign autonomous; developer God Mode and optional separate strategy sandbox |
| D03 | **Now** | What map topology is canonical? | Old 19-hex Catan nodes; current square-grid terrain and four-way paths | Square tiles current baseline; design regions and travel layer without reverting to Catan geometry |
| D04 | **Now** | What advances strategic decisions and eras? | World Turns/rounds and 10 VP rely on Catan economy | Continuous fixed Game Time; council/history tick; replace VP trigger with advancement milestones |
| D05 | **Now** | What does “full Widelands/OpenRA” mean? | All original game mechanics vs relevant playable subset | Audited feature matrix: economy roles + critical OpenRA traits; phase content while retaining long-term coverage goal |
| D06 | **Now** | How is Mindustry integrated? | Source engine, direct adaptation or new model inspired by it? | Shared canonical economy with source-derived factory/conveyor/power/fluid modules; test one factory loop first |
| D07 | **Soon** | What constitutes a settlement and territory? | Old corner-node city rules; new headquarters caravan proposal | Deployable one-way settlement headquarters plus multiple normal warehouses; define region spacing and capture |
| D08 | **Soon** | Do physical workers constrain output everywhere? | September decorative throughput; hybrid physical logistics | Physical early-era movement authoritative; off-screen optimisations must preserve conservation/equivalence |
| D09 | **Soon** | How does new tech coexist with old buildings? | v0.3 automatic core upgrades and persistent legacy sites | Explicit upgrades, retired/legacy recipes and no free duplicate goods; decision on grants/obsolescence |
| D10 | **Soon** | Can the wizard destroy any unit/building instantly? | Explicit older rule; mature RTS may be trivialised | Preserve until consciously revised; test social consequences, radius and risk |
| D11 | **Soon** | What survives a historical cycle? | People, quests and buildings preserve, but millennia and faction reseeding conflict | Stable personal canon + explicit political/asset retirement; design NPC time/age model |
| D12 | **Soon** | Catastrophe unit and cadence? | Hex cubes, three-adjacent treatments, eight outbreaks on 19 hexes | Convert to regional/physical spread and time cadence; retain readable bounded-attention concept |
| D13 | **Soon** | Is technology drafting retained? | Seven-card draft per World Round no longer exists | Optional periodic civic/research choice; define political decisions without a Catan round |
| D14 | **Soon** | Who owns combat during on-screen scenes? | v0.3 Godot local authority vs current Python real-time combat | Prefer one Python authoritative combat model, with Godot rendering and duel-specific lease |
| D15 | Later | What is the Prehistoric economy subset? | Full Widelands economy vs primitive technologies | Explicit prehistoric tech pack; do not allow high-tech equipment on day one |
| D16 | Later | How do Mindustry era units enter the combat model? | Mindustry factories can themselves produce units; OpenRA actors own fighting | All production emits canonical units; only one military simulation/AI |
| D17 | Later | What governs old terrain-resource “infinite” renewal? | v0.3 exactly one finite/renewable per hex; Widelands ecosystem differs | Per-resource ecology, output rates and carrying capacities; no universal pair rule |
| D18 | Later | Should factions split/collapse mechanically? | September rigid survivor ranking and mandated split | Preserve political-history idea; redesign triggers based on real settlement/state, not VP thresholds |
| D19 | Later | What are the named wizard/settlement/dungeon canon? | Multiple narrative drafts and implementation stages | Audit scene/story assets and adopt one canon registry; do not auto-rewrite authored plots |
| D20 | Later | Performance model for automation? | Full detailed factory networks costly; headless/fps differs | High fidelity near activity, equivalent scheduled remote models; prove via stress tests |

## 19.1 Proposed immediate approvals

A short design meeting or follow-up can settle D01–D06. D07–D14 should be decided before large settlement/era refactors. D15–D20 may remain provisional through the first Historic vertical slice. **No implementation agent should reinterpret all 20 decisions as locked requirements.**

---

# 20. Specification invariants and testable contracts

The following are proposed shared contracts, drawn from current working systems and preserved game identity:

1. One authoritative world state and clock; no independent source-game economy or military state.
2. Wares are created, consumed, transferred, lost and reserved only by explicit events; no duplication.
3. All unit recruitment consumes real delivered inputs unless a clearly flagged scenario/test grant applies.
4. No building ignores terrain or source availability when the relevant restriction is enabled.
5. Terrain, pathfinding and placement consult one topology service in ordinary gameplay.
6. Faction AI and debug Strategy Mode use the same validated commands.
7. The adventure wizard may observe and influence but does not gain construction orders by accessing a debug API.
8. A duel pauses the appropriate world clock and never advances production or armies while paused.
9. World simulation continues independently of whether Godot currently renders that part of the map.
10. An active NPC/quest/dungeon reference cannot be silently erased by an era or settlement transition.
11. Old and new era machines draw from compatible shared resources without double counting.
12. Runtime dialogue cannot invent world facts or apply untyped code effects.
13. Source-game provenance, licence obligations and deviations are maintained for all imports.
14. Unknown/unsupported imported mechanics are marked unsupported, not represented as completed.
15. A new content definition does not require repeated ID-specific branches throughout unrelated modules.
16. Deterministic replay and save/reload cover transport, queues, unit state, quest effects and epoch transitions.
17. Visual proof requires headed screen captures and assertions against expected state, not headless-only passing tests.
18. The first playable adventure slice must include a real settlement story, dungeon and duel alongside economy and combat.

---

# 21. Source traceability and repository handoff

## 21.1 Original design source

`Complete Game Design, Systems, Content & MVP Specification v0.3`, dated 15 September 2026 (supplied text, 4,468 lines). Its twenty-three volumes and 231 numbered sections are retained as the detailed legacy record. The following appendices supply a **section-by-section disposition crosswalk**, so decisions and useful prose are not silently lost. The source v0.3 must remain archived unchanged.

## 21.2 Current implementation evidence

Repository `https://github.com/Joesalmon1985/DuelMasterBattle`, branch `feature/wizard-rts-hybrid-v02`, at checkpoint `6096997`. Review these files in their **current** revisions, not stale cached snippets: `WizardRTSHybrid/docs/PROJECT_STATUS.md`, `STATE_OF_PLAY.md`, `DECISIONS.md`, `WINDOWS_HANDOVER.md`, `CLAUDE_HANDOFF.md`, `AGENTS.md`; and core code for world, grid, terrain, mapgen, Widelands import, OpenRA import, production/ware/logistics, combat, construction, AI, training interface and Godot presentation. Repo documents may disagree internally; tests and current source are the implementation authority.

## 21.3 Upstream references

- Widelands — `https://github.com/widelands/widelands` (tribal programmes, workers, resource/terrain, roads/logistics; licence/provenance to be followed).
- OpenRA — `https://github.com/OpenRA/OpenRA` (actor and weapon data, targeting, movement, production and its mod/trait ecosystem; inspect pinned source mod and variant).
- Mindustry — `https://github.com/Anuken/Mindustry` (GPL-3.0, Java; industry, item/fluid/power networks and automation ideas).

**Licensing:** this document does not grant permission to copy source assets, art, code or proprietary third-party material across projects. The project must review the actual pinned source licences, attribution, asset permissions and combined distribution obligations before shipping derived code/assets.

---

# APPENDIX A — Original v0.3 section-disposition map

The full source has 231 numbered design sections. The crosswalk below is generated from their headings and identifies whether each is preserved, revised or superseded. “Preserved” means the design topic remains relevant; it does **not** certify its September numerical parameters or current implementation. “Revised” means consult v0.4 before using the old instructions. “Superseded” means the old mechanic should not be implemented without a new approval.

| v0.3 section | Original heading | Disposition / new home |
|---|---|---|
| §1 | One-sentence game definition | REVISE specification; §1–3 |
| §2 | Expanded product definition | REVISE specification; §1–3 |
| §3 | Player fantasy | PRESERVE theme/intent; §1–3 |
| §4 | Target player | PRESERVE theme/intent; §1–3 |
| §5 | Reference points | REVISE specification; §1–3 |
| §6 | Distinctive proposition | REVISE specification; §1–3 |
| §7 | Primary design problems | PRESERVE theme/intent; §1–3 |
| §8 | Design pillars | REVISE specification; §1–3 |
| §9 | System invariants | REVISE specification; §1–3 |
| §10 | Deliberate omissions | REVISE specification; §1–3 |
| §11 | Core experience | PRESERVE theme/intent; §3 |
| §12 | Core gameplay loop | PRESERVE theme/intent; §3 |
| §13 | Secondary loops | REVISE specification; §3 |
| §14 | Long-term loop | REVISE specification; §3 |
| §15 | Positive feedback | REVISE specification; §3 |
| §16 | Negative feedback | REVISE specification; §3 |
| §17 | Failure cascades | PRESERVE theme/intent; §3 |
| §18 | Recovery | PRESERVE theme/intent; §3 |
| §19 | Player authority | REVISE specification; §3 |
| §20 | Complete player verb list | PRESERVE theme/intent; §3 |
| §21 | Input philosophy | PRESERVE theme/intent; §3 |
| §22 | Selection and targeting | PRESERVE theme/intent; §3 |
| §23 | Camera and viewpoint | REVISE specification; §3 |
| §24 | World representation | SUPERSEDED mechanic; §5 |
| §25 | Scale | REVISE specification; §5 |
| §26 | Terrain | SUPERSEDED mechanic; §5 |
| §27 | Occupancy | REVISE specification; §5 |
| §28 | Movement | SUPERSEDED mechanic; §5 |
| §29 | Orientation | REVISE specification; §5 |
| §30 | Geography as gameplay | REVISE specification; §5 |
| §31 | Time model | SUPERSEDED mechanic; §13 |
| §32 | Time pressure | REVISE specification; §13 |
| §33 | Timed systems | SUPERSEDED mechanic; §13 |
| §34 | Visibility | PRESERVE theme/intent; §11/15 |
| §35 | Hidden information | PRESERVE theme/intent; §11/15 |
| §36 | Memory | PRESERVE theme/intent; §11/15 |
| §37 | Information as gameplay | PRESERVE theme/intent; §11/15 |
| §38 | Persistent world state | PRESERVE theme/intent; §11/15 |
| §39 | Persistent character state | PRESERVE theme/intent; §11/15 |
| §40 | Persistent strategic state | SUPERSEDED mechanic; §11/15 |
| §41 | Entity categories | PRESERVE theme/intent; §17 |
| §42 | Entity lifecycle | PRESERVE theme/intent; §17 |
| §43 | Entity state | PRESERVE theme/intent; §17 |
| §44 | Ownership and allegiance | PRESERVE theme/intent; §17 |
| §45 | Character model | PRESERVE theme/intent; §10–11 |
| §46 | Character creation or recruitment | PRESERVE theme/intent; §10–11 |
| §47 | Attributes | PRESERVE theme/intent; §10–11 |
| §48 | Skills | PRESERVE theme/intent; §10–11 |
| §49 | Character progression | PRESERVE theme/intent; §10–11 |
| §50 | Party structure | PRESERVE theme/intent; §10–11 |
| §51 | Death and replacement | PRESERVE theme/intent; §10–11 |
| §52 | Item model | PRESERVE theme/intent; §10–11 |
| §53 | Inventory model | PRESERVE theme/intent; §10–11 |
| §54 | Equipment | PRESERVE theme/intent; §10–11 |
| §55 | Object interaction | PRESERVE theme/intent; §10–11 |
| §56 | Persistent physical objects | PRESERVE theme/intent; §10–11 |
| §57 | Purpose of combat | REVISE specification; §7/9–10 |
| §58 | Combat flow | SUPERSEDED mechanic; §7/9–10 |
| §59 | Positioning | REVISE specification; §7/9–10 |
| §60 | Attack resolution | SUPERSEDED mechanic; §7/9–10 |
| §61 | Weapons and attack types | REVISE specification; §7/9–10 |
| §62 | Health, injury and death | REVISE specification; §7/9–10 |
| §63 | Combat resources | REVISE specification; §7/9–10 |
| §64 | Combat asymmetry | REVISE specification; §7/9–10 |
| §65 | Combat failure and retreat | REVISE specification; §7/9–10 |
| §66 | Ability model | PRESERVE theme/intent; §10 |
| §67 | Acquisition | PRESERVE theme/intent; §10 |
| §68 | Costs and constraints | PRESERVE theme/intent; §10 |
| §69 | Combination and experimentation | PRESERVE theme/intent; §10 |
| §70 | Survival pressures | PRESERVE theme/intent; §10 |
| §71 | Interaction between survival systems | PRESERVE theme/intent; §10 |
| §72 | Puzzle philosophy | PRESERVE theme/intent; §12 |
| §73 | Puzzle primitives | PRESERVE theme/intent; §12 |
| §74 | Puzzle grammar | PRESERVE theme/intent; §12 |
| §75 | Puzzle fairness | PRESERVE theme/intent; §12 |
| §76 | Failure, reset and recovery | PRESERVE theme/intent; §12 |
| §77 | Soft-lock prevention | PRESERVE theme/intent; §12 |
| §78 | Resource taxonomy | REVISE specification; §6–8 |
| §79 | Resource origin | SUPERSEDED mechanic; §6–8 |
| §80 | Resource representation | SUPERSEDED mechanic; §6–8 |
| §81 | Resource sinks | REVISE specification; §6–8 |
| §82 | Production model | SUPERSEDED mechanic; §6–8 |
| §83 | Production chains | SUPERSEDED mechanic; §6–8 |
| §84 | Capacity | SUPERSEDED mechanic; §6–8 |
| §85 | Demand | SUPERSEDED mechanic; §6–8 |
| §86 | Supply | SUPERSEDED mechanic; §6–8 |
| §87 | Transport model | SUPERSEDED mechanic; §6–8 |
| §88 | Network structure | SUPERSEDED mechanic; §6–8 |
| §89 | Distance cost | SUPERSEDED mechanic; §6–8 |
| §90 | Congestion | SUPERSEDED mechanic; §6–8 |
| §91 | Storage | SUPERSEDED mechanic; §6–8 |
| §92 | Logistics failure | SUPERSEDED mechanic; §6–8 |
| §93 | Worker roles | REVISE specification; §6/11 |
| §94 | Worker creation | REVISE specification; §6/11 |
| §95 | Worker assignment | REVISE specification; §6/11 |
| §96 | Worker autonomy | REVISE specification; §6/11 |
| §97 | Worker progression | REVISE specification; §6/11 |
| §98 | Indirect control | REVISE specification; §6/11 |
| §99 | Building purpose | REVISE specification; §5/6 |
| §100 | Placement | SUPERSEDED mechanic; §5/6 |
| §101 | Construction process | SUPERSEDED mechanic; §5/6 |
| §102 | Building dependencies | SUPERSEDED mechanic; §5/6 |
| §103 | Repair, upgrade and destruction | REVISE specification; §5/6 |
| §104 | Ownership | SUPERSEDED mechanic; §5/6 |
| §105 | Expansion | SUPERSEDED mechanic; §5/6 |
| §106 | Territorial value | REVISE specification; §5/6 |
| §107 | Territorial loss | REVISE specification; §5/6 |
| §108 | Need for asymmetry | REVISE specification; §4/9 |
| §109 | Shared foundation | REVISE specification; §4/9 |
| §110 | Structural differences | REVISE specification; §4/9 |
| §111 | Strategic identity | REVISE specification; §4/9 |
| §112 | Strengths and weaknesses | REVISE specification; §4/9 |
| §113 | Matchups | REVISE specification; §4/9 |
| §114 | Capability progression | SUPERSEDED mechanic; §15 |
| §115 | Prerequisites | SUPERSEDED mechanic; §15 |
| §116 | Gating | SUPERSEDED mechanic; §15 |
| §117 | AI purpose | REVISE specification; §9 |
| §118 | AI knowledge | REVISE specification; §9 |
| §119 | Local behaviour | REVISE specification; §9 |
| §120 | Strategic behaviour | REVISE specification; §9 |
| §121 | Authored versus general intelligence | REVISE specification; §9 |
| §122 | AI limitations | REVISE specification; §9 |
| §123 | Difficulty | REVISE specification; §9 |
| §124 | Fundamental content unit | REVISE specification; §11–12 |
| §125 | Reusable primitives | PRESERVE theme/intent; §11–12 |
| §126 | Bespoke content | PRESERVE theme/intent; §11–12 |
| §127 | Content hierarchy | REVISE specification; §11–12 |
| §128 | Level purpose | REVISE specification; §5/12 |
| §129 | Spatial structure | REVISE specification; §5/12 |
| §130 | Challenge placement | REVISE specification; §5/12 |
| §131 | Resource placement | REVISE specification; §5/12 |
| §132 | Safe and dangerous spaces | REVISE specification; §5/12 |
| §133 | Replayability | REVISE specification; §5/12 |
| §134 | Scenario purpose | PRESERVE theme/intent; §11–12 |
| §135 | Starting conditions | PRESERVE theme/intent; §11–12 |
| §136 | Objective | REVISE specification; §11–12 |
| §137 | Constraints | REVISE specification; §11–12 |
| §138 | Scripted events | REVISE specification; §11–12 |
| §139 | Failure conditions | REVISE specification; §11–12 |
| §140 | Alternative solutions | REVISE specification; §11–12 |
| §141 | Quest structure | PRESERVE theme/intent; §11 |
| §142 | Branches | PRESERVE theme/intent; §11 |
| §143 | Dialogue system | PRESERVE theme/intent; §11 |
| §144 | Dialogue reactivity | PRESERVE theme/intent; §11 |
| §145 | Consequences | REVISE specification; §11 |
| §146 | Overall progression | SUPERSEDED mechanic; §4/15 |
| §147 | Content sequencing | REVISE specification; §4/15 |
| §148 | Mechanical escalation | SUPERSEDED mechanic; §4/15 |
| §149 | Narrative escalation | PRESERVE theme/intent; §4/15 |
| §150 | Finale | PRESERVE theme/intent; §4/15 |
| §151 | First actions | REVISE specification; §3/14/18 |
| §152 | Teaching sequence | REVISE specification; §3/14/18 |
| §153 | Teaching method | REVISE specification; §3/14/18 |
| §154 | Mastery progression | REVISE specification; §3/14/18 |
| §155 | Difficulty dimensions | REVISE specification; §3/14/18 |
| §156 | Difficulty curve | REVISE specification; §3/14/18 |
| §157 | Difficulty combinations | REVISE specification; §3/14/18 |
| §158 | Difficulty settings | REVISE specification; §3/14/18 |
| §159 | Moment-to-moment rhythm | REVISE specification; §3/14/18 |
| §160 | Recovery periods | REVISE specification; §3/14/18 |
| §161 | Escalation | REVISE specification; §3/14/18 |
| §162 | Pacing controls | REVISE specification; §3/14/18 |
| §163 | Failure taxonomy | REVISE specification; §3/14/18 |
| §164 | Failure feedback | REVISE specification; §3/14/18 |
| §165 | Recovery | REVISE specification; §3/14/18 |
| §166 | Terminal failure | SUPERSEDED mechanic; §3/14/18 |
| §167 | Primary game screen | PRESERVE theme/intent; §16 |
| §168 | Secondary screens | REVISE specification; §16 |
| §169 | Information hierarchy | REVISE specification; §16 |
| §170 | Interaction feedback | REVISE specification; §16 |
| §171 | Diagnostic feedback | REVISE specification; §16 |
| §172 | Input efficiency | REVISE specification; §16 |
| §173 | Visual identity | REVISE specification; §16 |
| §174 | Gameplay readability | REVISE specification; §16 |
| §175 | Entity readability | REVISE specification; §16 |
| §176 | Environment readability | REVISE specification; §16 |
| §177 | Animation requirements | REVISE specification; §16 |
| §178 | Music | PRESERVE theme/intent; §16 |
| §179 | Sound effects | PRESERVE theme/intent; §16 |
| §180 | Informational audio | REVISE specification; §16 |
| §181 | Voice | PRESERVE theme/intent; §16 |
| §182 | Premise | PRESERVE theme/intent; §10–12 |
| §183 | World | REVISE specification; §10–12 |
| §184 | Characters | REVISE specification; §10–12 |
| §185 | Story delivery | PRESERVE theme/intent; §10–12 |
| §186 | Agency | PRESERVE theme/intent; §10–12 |
| §187 | Required simulation systems | REVISE specification; §13/17 |
| §188 | System ownership | REVISE specification; §13/17 |
| §189 | Update relationships | SUPERSEDED mechanic; §13/17 |
| §190 | Determinism | REVISE specification; §13/17 |
| §191 | Saveable state | REVISE specification; §13/17 |
| §192 | Networking | REVISE specification; §13/17 |
| §193 | Static definitions | REVISE specification; §17 |
| §194 | Runtime state | REVISE specification; §17 |
| §195 | Content extensibility | REVISE specification; §17 |
| §196 | Validation rules | REVISE specification; §17 |
| §197 | Required editors | REVISE specification; §17 |
| §198 | Debug tools | REVISE specification; §17 |
| §199 | Visualisation | REVISE specification; §17 |
| §200 | Content validation | REVISE specification; §17 |
| §201 | What needs balancing? | REVISE specification; §18 |
| §202 | Important ratios | SUPERSEDED mechanic; §18 |
| §203 | Intended asymmetry | REVISE specification; §18 |
| §204 | Tuning levers | REVISE specification; §18 |
| §205 | Target outcomes | REVISE specification; §18 |
| §206 | Required actor types | REVISE specification; §18 |
| §207 | Required objects | REVISE specification; §18 |
| §208 | Required structures | REVISE specification; §18 |
| §209 | Required environments | REVISE specification; §18 |
| §210 | Required scenarios | REVISE specification; §18 |
| §211 | Required narrative | REVISE specification; §18 |
| §212 | Required audiovisual assets | REVISE specification; §18 |
| §213 | Core identity test | REVISE specification; §18 |
| §214 | Core loop requirement | SUPERSEDED mechanic; §18 |
| §215 | Minimum challenge | REVISE specification; §18 |
| §216 | Minimum progression | REVISE specification; §18 |
| §217 | Minimum content | REVISE specification; §18 |
| §218 | MVP exclusions | REVISE specification; §18 |
| §219 | MVP start state | SUPERSEDED mechanic; §18 |
| §220 | MVP end state | SUPERSEDED mechanic; §18 |
| §221 | MVP definition | SUPERSEDED mechanic; §18 |
| §222 | Fun-risk questions | REVISE specification; §18 |
| §223 | Technical-risk questions | REVISE specification; §18 |
| §224 | Content-risk questions | REVISE specification; §18 |
| §225 | Balance-risk questions | REVISE specification; §18 |
| §226 | Usability-risk questions | REVISE specification; §18 |
| §227 | Prototype questions | REVISE specification; §18 |
| §228 | System dependency graph | REVISE specification; §17/18 |
| §229 | Core-loop dependency chain | REVISE specification; §17/18 |
| §230 | Content dependencies | REVISE specification; §17/18 |
| §231 | Highest dependency systems | REVISE specification; §17/18 |

# APPENDIX B — Suggested agent task after design approval

1. Read this revision, the user's actual resolutions of D01–D06, the original v0.3 and the latest current branch. Do not treat status guesses as source code facts.
2. Produce a discrepancy matrix linking every legacy mechanic that would cause incompatible implementation to its new rule. Do not delete legacy authored quests/characters or dungeon scenes.
3. Define minimal schema interfaces for resources, wares, recipes, power/fluids, unit definitions, buildings, settlement headquarters and an era pack. Demonstrate them with small tests before broad refactors.
4. Maintain a story-canon index: wizard cast, settlement plots, NPCs, dungeon entrances, puzzle IDs, quest conditions and source references.
5. Build the next vertical slice through actual stocked goods, one recruited unit, a quest, a dungeon and a duel; retain existing visual QA and long-run tests.
6. Continue Widelands/OpenRA integration on its own milestone track. Do not start a full Mindustry port before the historical economy and settlement interfaces are stable.
7. Keep all work on the appropriate feature branch and do not merge to `main` without explicit instruction.

**End of proposed v0.4 specification.**
