# Coverage audit and era rules (13 Oct 2026, branch work/mechanics-completion-v4)

Evidence scripts: `WizardRTSHybrid/scripts/audit_claims/`. Every number below was computed from the code and data or from a simulation run on 13 Oct 2026; where something is only reasoned, it says so.

## 1. The eight checks

| # | Claim | Verdict |
|---|---|---|
| 1 | Primary Widelands raws come from map squares, inexhaustibly | **Partly.** Minerals yes; quarry rocks, trees, fish, game and crops are finite or renewable, not inexhaustible. |
| 2 | Every non-military Widelands building can be built and makes its wares | **Mostly, not proven for all.** All 193 runnable buildings are materially sustainable; 116 of 152 production sites made a ware in 5 game minutes; 36 made none. |
| 3 | Every manufacturable Widelands ware has a purpose | **No.** 66 wares across the five tribes feed nothing except trade. |
| 4 | All OpenRA units and (non power/extraction/storage) buildings can be made | **Yes** for every unit and building in the build menu (47 unit recipes, 25 buildings). A few more OpenRA items are excluded than you listed. |
| 5 | Mindustry extractors can be built and extract from existing squares using Widelands-made materials | **Yes to build, with a bootstrap ladder.** Only mechanical and pneumatic drills are pure Widelands wares. |
| 6 | Mindustry processing buildings can all be built | **Built yes; one cannot operate** (cyanogen synthesizer). |
| 7 | Mindustry power buildings can all be built | **Built yes; four generators cannot operate.** |
| 8 | Mindustry military buildings and units can be built and beat OpenRA | **Buildings yes. Six units cannot be produced. Beats OpenRA from tier 3 up, not at tier 1.** |

### 1. Raw materials
- Deposits on the 544 x 288 map: coal 521, iron 567, gold 604, stones 671 tiles. Mines and Mindustry drills on them are inexhaustible (D22; every unit logged as `mined_from_inexhaustible_deposit`). Mindustry drills turn them into copper, lead, titanium (tier 3), scrap, granite, beryllium (tier 3), thorium (tier 4), tungsten (tier 5); sand comes from desert and beach floor.
- **Quarries are not inexhaustible.** They cut surface rocks: 316 rocks of 6 loads (about 1,900 granite on the whole map), and a rock is removed when empty. The inexhaustible granite route is a stones mine (barbarian granite mine, empire marble mine, Frisian rock mine, Amazon stone mine, Atlantean crystal mine) or a Mindustry drill on stones; both need rations or power.
- Wells keep a 65 percent chance per cycle after the water runs out, so they never fully stop. Trees (foresters), fish (breeders), game (keepers) and crops (any arable land) renew but can be over-harvested.

### 2. Widelands buildings
- Coverage table: 198 functional (178 production sites, 15 warehouses and ports, 5 markets); excluded: 31 military sites, 11 training sites, 2 headquarters variants.
- Static: for each of the five tribes, every building's cost wares are made by that tribe's own chain from the foundation stock (193 of 193).
- Dynamic (inputs stocked by hand, 5 game minutes, 152 non-enhancement production sites): 116 made at least one output. The 36 that did not: 20 make no ware by design (5 soldier sites: four barracks and the Amazon initiation site; 5 shipyards; 5 ferry yards; 5 scout huts); 8 are foresters and similar tree and game keepers; 8 depend on siting or time (farms, bee, fruit, fish and dike work). The Frisian farm needs about 15 minutes; with a berry farm next to them, the beekeeper and fruit collector produced fruit and honey. **Not shown to produce:** aqua farm, diker, fish breeder, wilderness keeper.
- Tool and weapon smithies make a ware only when something requests it, so they look idle in a short run.
- The tests place buildings with scaffolding; construction by real carriers is not tested for each building.

### 3. Dead-end wares (produced, consumed by nothing)
After counting Widelands inputs, build costs, ware classes, soldier wares, OpenRA recipes and Mindustry costs, these remain (they can only be traded):
- Barbarians (12): ax_sharp, ax_broad, ax_bronze, ax_battle, ax_warriors, bread_paddle, felling_ax, fire_tongs, fishing_rod, hunting_spear, kitchen_tools, scythe.
- Empire (13): spear, spear_advanced, spear_heavy, spear_war, basket, bread_paddle, felling_ax, fire_tongs, fishing_rod, hunting_spear, kitchen_tools, scythe, shovel.
- Frisians (14): sword_long, sword_broad, sword_double, mead, basket, bread_paddle, felling_ax, fire_tongs, fishing_net, hunting_spear, kitchen_tools, needles, scythe, shovel.
- Atlanteans (13): trident_long, trident_steel, trident_double, trident_heavy_double, bread_paddle, buckets, fire_tongs, fishing_net, hook_pole, hunting_bow, milking_tongs, scythe, shovel.
- Amazons (14): chocolate, warriors_coat, boots_sturdy, boots_swift, boots_hero, spear_stone_tipped, spear_hardened, felling_ax, machete, kitchen_tools, needles, stone_bowl, firestones, shovel.
Cause: workers need no tools in the hybrid, and only armour, smithing tools and pack animals are ware classes. Fix options: tools as worker equipment, a "weapon" class for infantry recipes, food and luxury wares as a settlement-happiness input.

### 4. OpenRA
- All 47 unit recipes produce a unit when the prerequisite buildings stand and the wares are delivered (39 immediately, 8 after building their prerequisite: fix, dome, stek, atek). All 25 OpenRA build-menu buildings finish construction.
- Excluded, beyond power, refinery, silo and harvester: construction yard (`fact`, replaced by the MCV), `spef` and `hind` (disabled in the Red Alert rules), the mission-only ants, and the 11 decoy buildings (D27).

### 5 to 7. Mindustry buildings
- 252 buildable blocks (236 Mindustry plus 16 hybrid industrial lines; 17 sandbox blocks excluded). Static bootstrap closure: every block's cost can be reached in six rounds from log, plank, granite, iron, coal, gold and the drillable ores.
- With cost wares delivered, 240 of 252 finished construction in a world. The other 12 are the 8 drill kinds and 4 pumps, which correctly refuse sites with no deposit or water; placed on a valid site, all 14 finished.
- Pure Widelands wares build only the mechanical drill (plank, granite) and the pneumatic drill (plank, granite, iron). Everything else needs Mindustry wares (graphite, silicon, titanium, metaglass, thorium, beryllium, tungsten, oxide) made by the industry, so the order is forced: pneumatic drill, graphite press and silicon smelter, laser drill, and so on.
- **Nine blocks cannot operate** because arkycite has no source (no pump, floor or crafter yields it): cyanogen synthesizer, chemical combustion chamber, neoplasia reactor, pyrolysis generator (arkycite), and flux reactor, mech/ship/tank assemblers, shockwave tower (cyanogen).
- Thermal and attribute-based blocks are tested with a faked attribute value; whether the map has heat or spore tiles under them is unverified.
- The per-block function tests place blocks directly; the end-to-end ladder (Widelands wares to a laser drill to power to a unit) has not been run in a live game.

### 8. Mindustry military against OpenRA
- Buildings: all turrets, walls, doors, menders, shields, factories, reconstructors and assemblers build. 50 unit types exist.
- **Six units cannot be produced**: tecta, collaris, quell, disrupt, vanquish, conquer (the assemblers need cyanogen).
- Single-unit duels, 90 s, one seed (survivor health percent, OpenRA then Mindustry): Mammoth beats dagger (97/0) and mace (100/0), loses to fortress (0/51) and scepter (0/94). Heavy tank loses to mace (0/18) and fortress (0/68). MiG ties horizon (a bomber that cannot hit air) and loses to zenith and antumbra. Destroyer loses to minke (0/76) and bryde (0/66); cruiser loses to sei (0/99).
- Static rating: tier 1 Mindustry units have 5,000 to 63,000 health, against 40,000 to 90,000 for OpenRA tanks. Tier 3 starts at 41,000 to 450,000; tier 4 and 5 have 10 to 30 times an OpenRA tank's health. Cost-adjusted and mixed-army balance were not tested.

## 2. What is available at each era

A faction starts with the **foundation** (no card): hybrid ranger, quarry, well, hunter, tavern, clinic, processor and producer; each tribe's gatherers, foresters, sawmill and tavern or inn (50 entities)(`graph.foundation_kind`).
Each era has 42 cards (6 factions x 7 rounds). The list is what **exists somewhere in the world**; one faction drafts about 7 cards per era (plus bonus hands and leftovers), so it holds a fraction. "Available at the end of an era" is this era plus all earlier eras.

### Era 0: Prehistoric

cards 42 distinct entities 100

- OpenRA/hybrid bldg 4 : bakery, farm, scriptorium, war_lodge
- UNIT 3 : clubman, slinger, spearman
- WL amazons 16 : cassava_plantation, cassava_root_cooker, chocolate_brewery, cocoa_farm, ferry_yard, gardening_center, initiation_site, market, port, rope_weaver_booth, scouts_hut, shipyard, tapir_farm, warehouse, water_gatherers_hut, wilderness_keepers_tent
- WL atlanteans 16 : bakery, barracks, blackroot_farm, farm, ferry_yard, fishbreeders_house, horsefarm, market, mill, port, scouts_house, shipyard, smokery, spiderfarm, warehouse, weaving_mill
- WL barbarians 17 : bakery, barracks, brewery, cattlefarm, farm, ferry_yard, gamekeepers_hut, lime_kiln, market, micro_brewery, port, reed_yard, scouts_hut, shipyard, warehouse, weaving_mill, wood_hardener
- WL empire 18 : bakery, barracks, brewery, donkeyfarm, farm, ferry_yard, market, mill, piggery, port, scouts_house, sheepfarm, shipyard, stonemasons_house, vineyard, warehouse, weaving_mill, winery
- WL frisians 26 : aqua_farm, bakery, barracks, beekeepers_house, berry_farm, brewery, brick_kiln, clay_pit, collectors_house, dikers_house, drinking_hall, farm, ferry_yard, honey_bread_bakery, market, mead_brewery, port, reed_farm, reindeer_farm, scouts_house, sewing_room, shipyard, smokery, tailors_shop, warehouse, weaving_mill

### Era 1: Historic

cards 42 distinct entities 129

- OpenRA/hybrid bldg 29 : afld, agun, atek, barracks, brik, defense, dome, fenc, fix, flame_tower, gap, hbox, hpad, iron, ironmine, kenn, mine, mslo, naval_yard, pbox, pdox, sam, sbag, smelter, smithy, stek, sub_pen, tesla_coil, vehicle_factory
- UNIT 42 : apc, artillery, attack_dog, black_hawk, chinook, chrono_tank, commando, cruiser, demo_truck, destroyer, engineer, flak_truck, flamethrower, gap_vehicle, grenadier, infantry, jeep, landing_ship, light_tank, longbow, mad_tank, mammoth, mcv, mechanic, medic, medium_tank, mig, minelayer, missile_sub, patrol_boat, phase_tank, radar_jammer, rocket_soldier, shock_trooper, spy, submarine, supply_truck, tank, tesla_tank, thief, v2_launcher, yak
- WL amazons 5 : charcoal_kiln, dressmakery, furnace, stone_workshop, stonemine
- WL atlanteans 9 : armorsmithy, charcoal_kiln, coalmine, crystalmine, goldmine, ironmine, smelting_works, toolsmithy, weaponsmithy
- WL barbarians 16 : ax_workshop, charcoal_kiln, coalmine, coalmine_deep, coalmine_deeper, goldmine, goldmine_deep, goldmine_deeper, granitemine, helmsmithy, ironmine, ironmine_deep, ironmine_deeper, metal_workshop, smelting_works, warmill
- WL empire 13 : armorsmithy, charcoal_kiln, coalmine, coalmine_deep, goldmine, goldmine_deep, ironmine, ironmine_deep, marblemine, marblemine_deep, smelting_works, toolsmithy, weaponsmithy
- WL frisians 15 : armor_smithy_large, armor_smithy_small, blacksmithy, charcoal_burners_house, charcoal_kiln, coalmine, coalmine_deep, furnace, goldmine, goldmine_deep, ironmine, ironmine_deep, recycling_center, rockmine, rockmine_deep

### Era 2: Modern

cards 42 distinct entities 150

- MDY battery 2 : battery, battery_large
- MDY belt 5 : armored_conveyor, armored_duct, conveyor, duct, titanium_conveyor
- MDY bridge 3 : bridge_conveyor, duct_bridge, phase_conveyor
- MDY conduit 4 : conduit, plated_conduit, pulse_conduit, reinforced_conduit
- MDY constructor 2 : constructor, large_constructor
- MDY crafter 37 : atmospheric_concentrator, blast_mixer, carbide_crucible, coal_centrifuge, cryofluid_mixer, cultivator, cyanogen_synthesizer, disassembler, electrolyzer, graphite_press, hy_arc_smelter, hy_fibre_loom, hy_food_plant, hy_gold_refinery, hy_hydroponic_farm, hy_material_press, hy_protein_vat, hy_sawmill_line, hy_tool_foundry, hy_water_bottler, kiln, melter, multi_press, phase_synthesizer, phase_weaver, plastanium_compressor, pulverizer, pyratite_mixer, separator, silicon_arc_furnace, silicon_crucible, silicon_smelter, slag_centrifuge, spore_press, surge_crucible, surge_smelter, vent_condenser
- MDY deconstructor 2 : deconstructor, small_deconstructor
- MDY diode 1 : diode
- MDY drill 8 : blast_drill, eruption_drill, impact_drill, large_plasma_bore, laser_drill, mechanical_drill, plasma_bore, pneumatic_drill
- MDY generator 14 : chemical_combustion_chamber, combustion_generator, differential_generator, flux_reactor, impact_reactor, neoplasia_reactor, pyrolysis_generator, rtg_generator, solar_panel, solar_panel_large, steam_generator, thermal_generator, thorium_reactor, turbine_condenser
- MDY harvester 1 : hy_tree_harvester
- MDY heat_conductor 2 : heat_redirector, heat_router
- MDY heater 5 : electric_heater, heat_reactor, oxidation_chamber, phase_heater, slag_heater
- MDY incinerator 2 : incinerator, slag_incinerator
- MDY junction 1 : junction
- MDY liquid_bridge 3 : bridge_conduit, phase_conduit, reinforced_bridge_conduit
- MDY liquid_junction 2 : liquid_junction, reinforced_liquid_junction
- MDY logic 10 : hyper_processor, large_logic_display, logic_display, logic_processor, memory_bank, memory_cell, message, micro_processor, reinforced_message, switch
- MDY node 5 : beam_node, beam_tower, power_node, power_node_large, surge_tower
- MDY overflow 4 : overflow_duct, overflow_gate, underflow_duct, underflow_gate
- MDY payload_belt 4 : payload_conveyor, payload_router, reinforced_payload_conveyor, reinforced_payload_router
- MDY payload_loader 2 : payload_loader, payload_unloader
- MDY pump 6 : impulse_pump, mechanical_pump, oil_extractor, reinforced_pump, rotary_pump, water_extractor
- MDY router 4 : distributor, duct_router, router, surge_router
- MDY sorter 2 : inverted_sorter, sorter
- MDY stack_belt 2 : plastanium_conveyor, surge_conveyor
- MDY store 4 : container, reinforced_container, reinforced_vault, vault
- MDY tank 6 : liquid_container, liquid_router, liquid_tank, reinforced_liquid_container, reinforced_liquid_router, reinforced_liquid_tank
- MDY unit_factory 4 : hy_assembly_airfield, hy_assembly_barracks, hy_assembly_shipyard, hy_assembly_vehicle_plant
- MDY unloader 2 : duct_unloader, unloader
- MDY wall_drill 1 : cliff_crusher

### Era 3: Dystopian

cards 42 distinct entities 152

- MDY accelerator 1 : interplanetary_accelerator
- MDY assembler 3 : mech_assembler, ship_assembler, tank_assembler
- MDY assembler_module 1 : basic_assembler_module
- MDY build_turret 1 : build_tower
- MDY cargo 2 : unit_cargo_loader, unit_cargo_unload_point
- MDY core 6 : core_acropolis, core_bastion, core_citadel, core_foundation, core_nucleus, core_shard
- MDY door 3 : blast_door, door, door_large
- MDY launch_pad 1 : launch_pad
- MDY mass_driver 1 : mass_driver
- MDY mender 3 : mend_projector, mender, regen_projector
- MDY mine 1 : shock_mine
- MDY overdrive 2 : overdrive_dome, overdrive_projector
- MDY payload_driver 2 : large_payload_mass_driver, payload_mass_driver
- MDY radar 1 : radar
- MDY reconstructor 8 : additive_reconstructor, exponential_reconstructor, mech_refabricator, multiplicative_reconstructor, prime_refabricator, ship_refabricator, tank_refabricator, tetrative_reconstructor
- MDY repair 3 : repair_point, repair_turret, unit_repair_tower
- MDY shield 2 : barrier_projector, force_projector
- MDY turret 29 : afflict, arc, breach, cyclone, diffuse, disperse, duo, foreshadow, fuse, hail, lancer, lustre, malign, meltdown, parallax, ripple, salvo, scathe, scatter, scorch, segment, shockwave_tower, smite, spectre, sublimate, swarmer, titan, tsunami, wave
- MDY unit_factory 6 : air_factory, ground_factory, mech_fabricator, naval_factory, ship_fabricator, tank_fabricator
- MDY wall 26 : beryllium_wall, beryllium_wall_large, carbide_wall, carbide_wall_large, copper_wall, copper_wall_large, phase_wall, phase_wall_large, plastanium_wall, plastanium_wall_large, reinforced_surge_wall, reinforced_surge_wall_large, scrap_wall, scrap_wall_gigantic, scrap_wall_huge, scrap_wall_large, shielded_wall, surge_wall, surge_wall_large, thorium_wall, thorium_wall_large, thruster, titanium_wall, titanium_wall_large, tungsten_wall, tungsten_wall_large
- UNIT 50 : aegires, anthicus, antumbra, arkyid, atrax, avert, bryde, cleroi, collaris, conquer, corvus, crawler, cyerce, dagger, disrupt, eclipse, elude, flare, fortress, horizon, locus, mace, mega, merui, minke, mono, navanax, nova, obviate, oct, omura, oxynoe, poly, precept, pulsar, quad, quasar, quell, reign, retusa, risso, scepter, sei, spiroct, stell, tecta, toxopid, vanquish, vela, zenith

Widelands military and training buildings are not in the game; the army is OpenRA (Historic) and Mindustry (Dystopian). No OpenRA content arrives after Historic. Modern adds only the Mindustry industrial buildings.

## 3. Rules for era change (as implemented)

**When an era ends** (`vp.py`, drafting v2):
1. VP: +1 per standing settlement (a deployed MCV or the home command centre), +1 to the faction that destroys an enemy settlement's command centre; wizard destruction gives nothing.
2. Bar: the leader's current VP must reach `max(8, VP of the leader when the era began + 4)` and stay there 60 seconds.
3. Stall guard: otherwise the era ends 75 game minutes after it began, recorded as a "stall guard" transition.
4. Developer switches (`era_vp_end`, `era_vp_step`, `era_max_ms`, `era_vp`) change the pacing for training; the defaults above are provisional.

**What happens at an ordinary transition (D09, D11):**
- Nothing is destroyed or reset: settlements, buildings, units, people, roads, stocks, quests, wizard and VP ledger all continue. There is no forced upgrade; a building upgrades in place only if the owner pays (Widelands enhancement; a Mindustry drill upgrade costs the difference plus 25 percent of the old cost, S08).
- Cards already drafted stay; older units and buildings stay usable.
- The next era's 42-card pool is dealt: seven rounds of six game minutes, one pack of seven per faction, at least 60 percent from the new era, the rest older undrafted cards. A faction's first pack is guaranteed the era's essential cards its tribe can use (D29).
- Leftover rule: undrafted cards in a pack go to the faction if its VP is 8 or more when the era ends early; otherwise they are lost for that faction. Bonus hands of three cards need a scriptorium with paper.
- Faction floor (D28): the world keeps at least six factions; a faction that collapses returns its unpicked pack to the reserve, and a split successor gets a pack from the reserve.

**When the last era (Dystopian) ends:** the cycle ends, `cycle_pending` is set and the next command rebuilds the world (`history.cycle_reset`). Only the wizard survives (position and aspect scores) plus a summary of the old cycle. All settlements, buildings, units, people, quests, items and stocks are gone. The same land is re-dealt: factions are ranked by peak VP and settlement count, the strongest takes the fertile homeland nearest its old centroid, the rest follow in order, and all rule settings carry over. A collective loss (every faction lost) ends a cycle the same way.

**Gaps:** nothing reached Dystopian in two 120-minute test games, so the pacing is untested for completion; the VP numbers (8, +4, 75 minutes) are provisional; decision G (era pacing study) has not been run.
