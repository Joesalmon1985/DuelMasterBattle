# DuelMasterBattle: God World

**Product requirements and Claude implementation brief · v1.0 · 24 October 2026**

**Status:** proposed specification for Joe Salmon's overhaul. Owner requirements are distinguished from proposed implementation defaults. This document specifies work to build; it does not claim that the new game or its acceptance tests have been implemented.

**Repository reviewed:** https://github.com/Joesalmon1985/DuelMasterBattle  
**Reviewed baseline:** `main`, commit `1b9513dd973087281bfcedeb8a786788331697b0`, dated 16 October 2026. Recheck the checkout and any later owner instructions before implementing.

## 1. Product definition

The player is a god watching a living civilisation from a freely movable camera. Six AI factions settle, trade, build roads, expand and upgrade villages on the logical board of a 5–6 player Catan game. The board is rendered as one large, continuous world populated with the existing Widelands, OpenRA and Mindustry art.

There are five economic resource roles. Their names, buildings and visual production chains change through four ages, but their construction and trading roles remain consistent. Catan-style production and expenditure drive the game. Workers, processing buildings, cargo and machines make those simple rules visible.

The first deliverable is an autonomous world that is enjoyable and understandable to watch on a phone. The player pans, zooms and inspects. The AI must play through all four ages without player assistance.

### 1.1 Owner requirements — mandatory

| ID | Requirement |
| --- | --- |
| O01 | Replace walking-avatar play with a god's view and a free camera. |
| O02 | Use the size and settlement/road topology of the 5–6 player Catan board. |
| O03 | Present one continuous world; hexes define regions within it, not separate village scenes. |
| O04 | Simplify the actual economy to Catan's five resource roles while retaining a visually rich web of goods, buildings and activity. |
| O05 | Give every village exactly one warehouse and production buildings derived from its adjacent hexes. |
| O06 | Make building numbers reflect production-roll odds and settlement versus city status. |
| O07 | Use the four age/resource mappings in section 5 as the starting content direction. |
| O08 | AI factions choose their initial settlements, trade, construct roads, found new settlements and upgrade cities. |
| O09 | Trade involves visible caravans departing from village warehouses. |
| O10 | A new settlement is founded by a visible group of key workers travelling from a village along constructed roads between board nodes. |
| O11 | Villages have military buildings and produce military units; those units stand around for now. |
| O12 | Disable combat, outbreaks and related threats in this first version. |
| O13 | One faction reaching 10 VP advances the shared world to the next age. |
| O14 | At transition, every faction carries its two largest/most productive villages into the next age as settlements, with construction of the new technology starting visibly. |
| O15 | Support touch drag to pan and two-finger pinch to zoom. Tapping an object reveals a label; tapping that label opens more detail. |
| O16 | Inspect existing economic rules, assets, rendering and infrastructure before choosing what to reuse. |

### 1.2 Proposed defaults — explicit design decisions for this draft

These defaults make the brief implementable. They are recommendations, not additional instructions previously given by Joe. Keep them in data/configuration where practical. An implementation run using this brief should use them unless the owner changes them; do not stop for routine choices already covered here.

| ID | Proposed default | Reason |
| --- | --- | --- |
| P01 | Six autonomous factions; the human controls only viewing, inspection and playback. | Establish a working civilisation simulation before adding god powers. |
| P02 | One global 2d6 production roll every 15 game seconds; all eligible villages benefit. AIs can act between rolls. | Catan's production distribution with continuous, watchable activity. |
| P03 | Five canonical resource balances per faction, with explicit reservations and cargo. Warehouses are physical endpoints, not separate local economic inventories. | Preserve the simplicity of a Catan hand and avoid adding an internal distribution game. |
| P04 | Standard road, settlement and city resource costs; score only completed settlements and cities. | Make expansion legible and testable. |
| P05 | No robber, discards, development cards, longest-road/army bonuses, ports or finite bank supply in the MVP. A 7 produces nothing. | Focus on the requested economy, trade and expansion loop. These are deliberate departures from full Catan. |
| P06 | No physical-piece caps in the MVP. | Buildings alone must be sufficient to reach 10 VP, including on a crowded board. In particular, five cities can reach 10 without cards or combat. |
| P07 | At age rollover, reset current-age VP and economic stock; retain two village sites per faction as level-one settlements. Other sites become non-producing historical remains and release their board occupancy. | Prevent immediate repeat transitions and allow a fresh expansion race on a finite board. **This is a major interpretation to review.** |
| P08 | Rank carry-over villages by expected output from dice odds and completed settlement/city level; use size and stable ID as tie-breakers. | Avoid selecting on lucky recent rolls. |
| P09 | Interpret “pyrite processor” as the existing **pyratite mixer** and its pyratite output. | The frozen Mindustry roster contains pyratite, not pyrite. Keep this naming choice easy to change. |
| P10 | Use a deterministic heuristic AI for the first working build. Retain an adapter for later learned policies. | Existing trained policies were built for different rules and are not proof of competence here. |
| P11 | Military production is an automatic visual village function, with a bounded quota and no expenditure from the five-resource economy yet. | Satisfy visible recruitment without starving settlement expansion. |
| P12 | Age four is the final age. Its first 10-VP result completes the run; the world may keep running in that age for observation. | A defined end state without inventing a fifth age or another reset loop. |

## 2. Claude handoff and precedence

Attach this file to Claude with the following instruction:

> Implement the God World pivot in the attached PRD in DuelMasterBattle. The owner is explicitly replacing the walking-wizard product and restoring Catan's strategic topology. Apply the mandatory requirements and the stated draft defaults. Read the current repository and applicable instructions, then work through the new milestones in section 14. Start with an audit and small executable rules tests, then deliver the working autonomous mobile spectator game. Use the existing Python authority, Godot rendering, asset catalogue and Android runtime where suitable. Update the repository's entry instructions and decision records to describe this pivot so older instructions cannot undo it. Do not merely reskin the existing RTS economy or build an isolated mock-up. Report which acceptance criteria are actually verified, with real runtime evidence. Make a feature branch; do not merge into main without a separate instruction. Do not treat superseded milestones or old product-direction approval gates as blockers to the milestones explicitly requested here.

### 2.1 Superseded rules

The reviewed `CLAUDE.md` and `WizardRTSHybrid/AGENTS.md` describe a wizard-led adventure, prohibit restoring Catan topology, and restrict God Mode to development. Those product rules conflict with this owner-requested overhaul and must be superseded for the new mode.

Also superseded in the new mode: production driven by full Widelands recipes or Mindustry power/fluid constraints; card-draft technology progression; conquest VP; world-total VP age thresholds; rising age bars; timer-triggered progression; wizard movement/health/tutorial gates; catastrophe and faction-collapse logic.

Keep the useful engineering constraints: one authoritative world, one clock, deterministic decisions, validated commands, stable identities, export-safe asset loading, honest evidence and preservation of unrelated work.

Do not bulk-delete the older adventure or its assets. Keep incompatible old saves separate. The new player-facing launch should enter God World without requiring an avatar, a tutorial conversation, a developer flag or a LAN lobby.

## 3. What the repository already provides

This is a source audit, not a fresh runtime test. Several older documents are stale; source and the current asset catalogue take priority over old status prose.

| Area inspected | Actual finding at the reviewed commit | Direction |
| --- | --- | --- |
| `WizardRTSHybrid/wizard_rts/world.py` | `HybridWorld` embeds the legacy world/clock and advances many interdependent systems. | Retain a single authority and clock; introduce a rules profile that selects the new systems. Simply hiding the wizard will leave the old game running. |
| `WizardRTSHybrid/wizard_rts/economy.py`, `workers.py`, `industry/` | Existing economy includes resource-changing worker programs and industrial simulation. | Reuse activity and definitions selectively. Disable their economic writes in God World. |
| `WizardRTSHybrid/wizard_rts/trade.py` | Real warehouse-to-warehouse caravans already exist. They spend a caravan fee, require a Trade unlock, check reserves and value, and can fail on arrival. | Reuse identities, journey concepts and presentation; replace costs, eligibility, reservations and cargo types with the five-slot rules below. |
| `WizardRTSHybrid/wizard_rts/vp.py` | Settlement/conquest scoring and several legacy transition paths coexist: world gains, rising leader bars, sustain windows and a stall guard. | Replace the God World path with exactly 10 current-age VP for one faction. Disable every alternate trigger in this mode. |
| `WizardRTSHybrid/wizard_rts/history.py` | Contains decline, collapse, splits and a new-world cycle reset. | Do not run these systems in God World. Implement a same-board age rollover instead. |
| `sim/dmb/world/board.py` | Shared-corner hex topology already exists, using integer corner keys. Its standard builder and serializer assume a radius-based board; radius 2 gives 19/54/72. | Generalise the topology utility to an explicit 30-cell layout. Do not start a second legacy simulation. |
| `sim/dmb/world/generation.py`, `setup.py` | Earlier Catan-world generation/setup exists. | Mine for rules and fixtures; remove old-size assumptions rather than copying an entire parallel game. |
| `godot_project/client/scenes/hybrid_world.gd` | Handles current world rendering, pinch suppression, picking and avatar-centred camera updates. | Extract reusable viewing/input functionality and replace the forced avatar focus. |
| `godot_project/client/hybrid/wizard_labels.gd` | Opens a single inspect card on a tap. | Reuse semantic data and picking, but implement the requested label-first, details-second interaction. |
| `godot_project/client/world/world_interaction_label.gd` | Earlier semantic-label implementation survives. | Inspect for reusable anchoring/state handling; remove proximity, dialogue and avatar assumptions. |
| `godot_project/client/hybrid/hybrid_art.gd`, `industry_view.gd` | Existing renderers use imported art, animation states, footprints and hotspots. | Reuse the art pipeline; derive new village composition from the board. |
| `godot_project/client/hybrid/art/catalogue.json` | 2,565 catalogue records, including animation variants; actual IDs and source/resource paths are recorded. | Select a small verified roster. Do not confuse record count with unique buildings or functioning mechanics. |
| `godot_project/client/scripts/asset_loader.gd` | Loads imported resources in exports, with source-image fallback in editor workflows. | All runtime art must continue through this package-safe loader. |
| `WizardRTSHybrid/wizard_rts/data/content_freeze.json` | Existing frozen roster includes the relevant Widelands and Mindustry families. | Recompose and simplify existing content; no mass import or new upstream content wave is needed. |
| `WizardRTSHybrid/scripts/android/overlay/PySimPlugin.kt`, `wizard_rts/net/android_entry.py` | Existing Chaquopy/CPython hosting route is packed into Android. | Use the existing on-device authority for standalone play. Do not make a PC-hosted viewer the finished mobile product. |

The Android README records desktop and packaging evidence and explicitly says physical-phone execution was unverified there. The new build needs fresh device evidence; an existing APK or a desktop screenshot is insufficient.

## 4. Board and continuous-world model

### 4.1 Logical board

Use the elongated 30-land-hex 5–6 player layout, with column lengths **3, 4, 5, 6, 5, 4, 3**, up to rotation/reflection. This is not a radius-three hexagon: a regular radius-three board has 37 hexes.

One exact axial cell set is:

```python
cells = [(q, r)
         for q in range(-3, 4)
         for r in range(-3, 3)
         if -2 <= -q-r <= 3]
```

Deduplicating the six integer corners and six edges of those cells gives **30 hexes, 80 nodes and 109 edges**. These counts were independently calculated while preparing this specification. The implementation must verify graph connectivity, reciprocal adjacency, maximum node degree three, and one to three touching land hexes per node.

| Economic role | Hex count |
| --- | ---: |
| WOOD | 6 |
| BRICK | 5 |
| SHEEP | 6 |
| WHEAT | 6 |
| ORE | 5 |
| Desert / non-producing | 2 |
| **Total** | **30** |

Distribute 28 number tokens across productive hexes: two each of 2 and 12; three each of 3, 4, 5, 6, 8, 9, 10 and 11. Deserts have no token. Use a seeded valid fixture first, then seeded variation; keep 6/8 hexes from sharing an edge. Save the resolved layout, not just an instruction to randomise it again.

### 4.2 Strategic graph versus local detail

The hex/node/edge graph determines production adjacency, settlement legality, road ownership and expansion connectivity. The continuous square-tile or equivalent local plane determines where buildings, trees, scenery and moving actors are drawn and how local routes avoid obstacles.

Keep the existing 2D, oblique/isometric-looking presentation where practical. This request does not require a new 3D engine or a forced mathematical projection that makes the imported sprites look worse. Use one coordinate-transform service consistently for terrain, sprites, paths, selection and camera inversion.

Every strategic node maps to a fixed warehouse anchor. Its village grows around that anchor. Every strategic edge maps to a reserved road corridor and a continuous world-space path between its endpoints. Neighbouring hex terrain meets seamlessly. Crossing a hex boundary never loads another scene or recentres the camera.

Choose macro-hex scale after measuring the selected sprites and the largest city footprint. Before locking it, demonstrate three neighbouring village districts and a worst-case city. Reserve enough room for up to 30 production stations, some containing two buildings, plus one warehouse, military facilities, streets and a clear road entrance. Do not silently reduce building counts to repair an undersized map.

Scenery and terrain variation must never make a legal node, road or warehouse exit physically unreachable. Decorative collisions may route actors locally; they cannot veto a Catan-legal expansion. Use reserved clear corridors, deterministic local placement and chunked rendering rather than generating millions of active Godot nodes.

### 4.3 Placement rules

Settlements occupy nodes; roads occupy edges; cities upgrade the same village/node. An occupied node excludes all immediately adjacent nodes, regardless of faction. A normal new settlement must connect to the founder's completed road network. A new road extends that faction's network or starts from its own completed village. Opponent villages interrupt expansion connectivity through their node. One faction owns an edge at a time.

Micro-streets inside a village are free presentation features. They never count as paid strategic roads or allow a settlement at an arbitrary local tile. Pending sites/roads reserve their node/edge and relevant distance-rule neighbours, so concurrent AI decisions cannot produce illegal completions.

## 5. Five resources across four ages

### 5.1 Economic identity and visible identity

Keep exactly five stable economic IDs: `WOOD`, `BRICK`, `SHEEP`, `WHEAT`, `ORE`. These are rule roles, not immutable physical commodities. UI names and icons use the current age. For example, age-three road construction costs one coal-role token and one titanium-role token, because those occupy the WOOD and BRICK slots.

| Stable role | Age 1 — Prehistoric | Age 2 — Historic | Age 3 — Modern | Age 4 — Dystopian Future |
| --- | --- | --- | --- | --- |
| WOOD | Wood · woodcutter | Timber · woodcutter + sawmill | Coal · coal drill | Pyratite · pyratite mixer/processor |
| BRICK | Quarry stone · quarry | Worked stone · quarry + mason | Titanium · titanium drill | Silicon · silicon smelter/processor |
| SHEEP | Game/meat · hunter | Livestock/meat · piggery | Sand · sand drill | Phase fabric · phase weaver/processor |
| WHEAT | Reeds · reed yard/farm | Wheat · wheat farm | Lead · lead drill | Blast compound · blast mixer/processor |
| ORE | Coal · coal mine | Iron · iron mine + coal mine | Copper · copper drill | Surge alloy · surge smelter/processor |

The age-two display names “timber”, “worked stone” and “iron” are draft naming choices for the owner's proposed chains. The stable role and recipe cost do not depend on which display name is selected.

Hex economic roles and number tokens persist through the ages. New-era deposits, plants, work areas and machinery change their visible interpretation. Do not run a geology or ore-depletion constraint that stops a hex producing what its strategic role requires.

### 5.2 Verified asset candidates

These catalogue IDs exist at the reviewed commit. Resolve through the catalogue, not by guessing filenames. Their presence proves available art metadata, not that the new gameplay is implemented.

| Purpose | Existing catalogue ID(s) | Composition guidance |
| --- | --- | --- |
| Single village warehouse | `widelands.warehouse` | One building and one entrance/dispatch yard. A city may enlarge its yard or replace its appearance, never add a second warehouse. |
| Woodcutter | `widelands.lumberjack` or `widelands.empire_lumberjacks_house` | Put trees/work area toward its source hex and the building nearer the village street. |
| Quarry stone | `widelands.empire_quarry` | Rocks and stone stacks; reserve a visible path to the warehouse. |
| Hunter | `widelands.empire_hunters_house` | Existing hunter workers and animals can supply the activity. |
| Reeds | `widelands.frisians_reed_farm` | Inspect sheet/frame metadata carefully; the catalogue's dimensions are not a reliable ground footprint. |
| Coal mine | `widelands.coalmine` | Use a coal workface and delivery props; no real extraction-rate dependency. |
| Sawmill | `widelands.sawmill` or `widelands.empire_sawmill` | Pair each station's woodcutter and sawmill with a short internal delivery route. |
| Mason | `widelands.empire_stonemasons_house` | Pair with the quarry; no additional BRICK grant. |
| Piggery | `widelands.empire_piggery` | Farmyard silhouette, animals and feed props; feeding is visual in this ruleset. |
| Wheat | `widelands.empire_farm` | Field patches and harvest workers face the source hex. |
| Iron mine | `widelands.empire_ironmine` | Pair visually with the coal mine in the ORE district. |
| Modern drills | `mindustry.block.mechanical_drill`, `mindustry.block.pneumatic_drill`, `mindustry.block.laser_drill` | Use existing drill bodies over resource-specific ground patches, stockpiles and icons. Five resource roles do not require five invented drill types. |
| Future WOOD / BRICK | `mindustry.block.pyratite_mixer`, `mindustry.block.silicon_smelter` | Reuse working layers where available. |
| Future SHEEP / WHEAT / ORE | `mindustry.block.phase_weaver`, `mindustry.block.blast_mixer`, `mindustry.block.surge_smelter` | Small belt/pipe/warehouse connections can show the richer manufacturing web. |
| Early military | `widelands.barbarians_barracks`, `widelands.soldier` | Prefer accurate source names. `dmb.war_lodge` and `dmb.clubman` currently have alias-placeholder status. Do not claim distinctive new art for those aliases. |
| Historic military | `openra.barracks`, `openra.e1`, `openra.weap`, `openra.3tnk` | Suggested barracks/infantry and city vehicle yard. The catalogue's war-factory ID is `openra.weap`. |
| Modern/future military | `mindustry.block.ground_factory`, `mindustry.unit.dagger`, `mindustry.unit.mace` | Use a small era-appropriate subset with verified export art. |

Widelands gives the civilian world most of its oblique silhouettes; OpenRA and Mindustry have different proportions and viewing angles. Normalise ground footprints, baselines, shadows and faction accents. Place top-view industrial sprites on consistent industrial ground pads so they read as machine roofs. Do not stretch whole bitmaps to fake perspective or apply the catalogue's existing scale values blindly in the new layout.

Use the same economic capabilities for all six factions. Five Widelands tribes do not imply five factions or tribe-specific access to resources. Faction identity comes from the existing colours, flags, cloth/roof accents, warehouse emblem and unit markers. Selected building variants can add visual variety without changing costs or yield.

## 6. Economic rules

### 6.1 Production

At each scheduled pulse, roll two independent fair six-sided dice with the saved simulation RNG. Sum them once for the world. Each completed, active village touching a matching productive hex gains **one token as a settlement or two as a city** in that hex's economic role. Apply all matching-hex grants. All factions benefit from the same roll. A 7 has no production effect.

Production is credited once at the authoritative pulse. An animated delivery is a receipt/presentation of that grant, not another inventory credit and not a gate on when the token becomes spendable.

| Roll | Ways out of 36 / pips | Probability |
| --- | ---: | ---: |
| 2 or 12 | 1 | 2.78% each |
| 3 or 11 | 2 | 5.56% each |
| 4 or 10 | 3 | 8.33% each |
| 5 or 9 | 4 | 11.11% each |
| 6 or 8 | 5 | 13.89% each |

Equivalently, `pips(n) = 6 - abs(7-n)` for a productive token. A village's expected output per pulse is `level * sum(pips(h) / 36)` across its touching productive hexes, with completed level 1 or 2.

**Never multiply the roll's token grant by the number of visible production buildings.** Higher odds already make the hex produce more often. Multiplying by its pip-derived building count would count productivity twice.

### 6.2 Construction and scoring

| Action | Cost in stable resource roles | Completion effect |
| --- | --- | --- |
| Road | 1 WOOD + 1 BRICK | One completed owned strategic edge; 0 VP. |
| Settlement | 1 WOOD + 1 BRICK + 1 SHEEP + 1 WHEAT | One village, one warehouse, level 1, 1 VP and settlement production. |
| City upgrade | 2 WHEAT + 3 ORE | Same village and warehouse, level 2, 2 total VP and double production. The upgrade adds 1 VP. |

Reserve cost on acceptance and consume it exactly once on successful completion. A rejected command changes nothing. A cancelled pre-completion build releases its reservation. The old settlement continues at level one while a city upgrade is under construction.

Founding has the physical journey and building stage in section 8. Default road/city construction duration is eight game seconds after a crew can reach the site. Timings are tunable presentation/pacing rules, not hidden resource recipes. Completing individual decorative workshops costs nothing beyond their village or city action.

Current-age VP is derived from completed active village levels. There is no conquest, unit-count or decorative-building score. Lifetime achievements are recorded separately and cannot trigger an age transition.

### 6.3 Inventory and trade eligibility

Store one canonical five-slot hand per faction. Track available, reserved and travelling resources explicitly; do not maintain an additional independently writable total on the HUD or each warehouse. A warehouse inspector should say “Faction resources” and can separately show “Produced here this age” and its journeys. Do not label a faction-wide balance as goods physically stored in that one building.

The faction can spend its available hand through any of its completed warehouses. Routine movement between its own workshops and warehouse is presentation only in this version. This is an intentional simplification of the current physical local-ware economy.

Allow mutually accepted inter-faction barter. No Trade card, flat caravan fee, minimum reserve of eight, hostility condition or old ware-value table applies. Those current `trade.py` rules would block early Catan-sized trades. Require positive, finite quantities on both sides; no negative amounts or free gifts.

A faction may also trade four identical available tokens for one token of a different role with an unlimited external bank. Give it a short visible warehouse dispatch/return journey to an exterior trade endpoint; charge no extra road or expedition resources. No port is required. The bank must remain available if other factions decline or lack useful goods.

### 6.4 Explicit departures from tabletop Catan

This is a Catan economy adapted to a continuous autonomous world. The board, odds, adjacency, basic costs and settlement/city yields are the core. Proposed departures are continuous AI action, timed construction and travel, unlimited bank supply, no piece caps, no robber/discards, no cards/bonus scoring/ports, and age rollover. Do not silently reintroduce full Catan subsystems or describe this MVP as a complete rules-identical implementation.

## 7. Village appearance and the visible economic web

### 7.1 Composition rule

A village consists of one warehouse at its node, production districts facing its adjacent hexes, local streets/yards, and military facilities. Each source hex contributes its own district, even if two adjacent hexes share a resource role.

**Proposed exact count:** `stations(village, hex) = pips(hex.number) * completed_village_level`. Each station contains the age-specific building or building pair in section 5. A desert contributes zero production stations. The city upgrade doubles station counts after completion. Military facilities and the warehouse are additional to this count.

Stations are a visible representation of expected capacity. A wood station in age two may include both a woodcutter and a sawmill. It remains one station tied to one source hex; its two buildings are not independent token producers.

Example: a settlement touching WOOD 6, BRICK 9 and WHEAT 3 has 5 wood stations, 4 stone stations and 2 crop/reed stations. It has 11 stations in total. In age one that generally means 11 primary buildings. In age two, with woodcutter+sawmill and quarry+mason pairs, it has 20 production buildings. As a city it has 22 stations and 40 such buildings. Its warehouse count remains one. On a roll of 6 it still receives only one WOOD token as a settlement, or two as a city.

Use deterministic reserved districts and paths. Keep the warehouse entrance and strategic-road approaches clear. Give each station and its component buildings a stable semantic ID tied to the village, source hex, age and station index. The inspector can explain “Timber district · source: woodland 6 · 5 stations · village gains 1 timber when a 6 is rolled.”

### 7.2 Work, processing and deliveries

Retain a visible production web using existing worker animations, props and machine layers:

- Woodcutters work trees, carry logs, and supply nearby sawmills in age two.
- Quarry workers carry stone to masons; hunters return with game; farms show planting/harvesting or livestock routines.
- Iron and coal mines share an ORE district's visible chain in age two.
- Modern drills feed short belts and loading areas; future processors show inputs, working layers, output and dispatch.
- Porters and carts use the village streets to the single warehouse.

Existing recipes are references for these activity sequences and visual cargo. Their intermediate logs, planks, feed, water, fuel, power, liquids and machine buffers are **not extra spendable economic inventories**. Disable the old economic mutations rather than letting them run invisibly beside the five-slot economy.

Show only extraction/production districts justified by that village's adjacent roles. Decorative stored inputs can come from warehouse props; do not add unrelated resource-producing districts merely to satisfy an upstream recipe. Labels explain the current role, source hex and status in ordinary game language.

Workers and cosmetic cargo never determine a roll's quantity or prevent credit when the camera is elsewhere. Their visual routines can reflect recent production and expected activity, but missed rendering frames cannot lose resources. Decorative trees regrow/replenish as needed; exhaustion, hunger and blackouts are outside this version.

### 7.3 Readability at different zoom levels

| View | What should be readable |
| --- | --- |
| Close | Individual workers, building silhouettes, source-facing districts, work and carrying animations, warehouse entrance and expedition assembly. |
| Village | Settlement versus city size, faction ownership, relative productivity, local goods flow and garrison. |
| Region | Large strategic roads, warehouse/village centres and travelling caravans/expeditions. Hide tiny worker details. |
| Whole board | All 30 regions, six factions, settlement distribution and road networks. Optional resource-number overlay; no forest of permanent name labels. |

Cull and simplify rendering at distance, while retaining authoritative journey progress, inventories and AI. Do not substitute a second schematic map scene when zooming out. Overview symbols are a level of detail in the same world and use the same entity IDs.

Production feedback should feel satisfying to watch: a restrained district response, visible delivery and a brief warehouse receipt. Avoid coin showers for resources the economy did not award. Use consistent small sounds where existing assets permit, with a mute control; the simulation must be fully understandable without sound.

## 8. Roads, expeditions and caravans

### 8.1 Strategic roads

A paid road is a prominent constructed route along exactly one logical edge, from node to node. Show a small crew and a visible advancing construction front. An accepted command reserves the edge and its cost; only completion makes that edge available to an expedition or to further expansion. Keep village micro-streets visually narrower and distinguish public paths from owned strategic roads.

Route endpoints attach to village entrances or clear node junctions. Reuse the continuous local grid/path representation for the world-space corridor, but the logical graph owns the road's identity and connectivity. Avoid individual expensive full-map path searches for every crew member or follower.

### 8.2 Settlement-founding journey

The AI must select a legal target node, a completed source village and a continuous route over its own completed roads. It reserves the target, spacing exclusion and settlement cost before dispatch.

1. Assemble a visible party at the source warehouse. Suggested presentation: builder, woodcutter, stoneworker/miner and porter. These are key workers, not a walking player avatar or a generic tank/MCV.
2. Load visible supplies corresponding to the reserved settlement cost. Do not charge a second expedition fee.
3. Travel the chosen strategic-road route with a leader and followers. Each journey has one authoritative route/progress; followers use stable formation offsets.
4. Reach the destination, erect the single warehouse, then construct its production and military districts. Use an eight-game-second warehouse stage by default.
5. Mark the village operational, consume the reservation once, award its 1 VP, and include it in future rolls. Workshops may finish their short presentation sequence after this activation, without changing yield.

An expedition inspector shows faction, origin, destination, cargo commitment and progress. Reservations prevent competing parties from creating illegal neighbours. A route/target invalidated by a legitimate state change cancels the uncommitted project and refunds it; age-boundary handling is specified separately below. Do not teleport a completed village into existence at command acceptance and then send a cosmetic party afterward.

### 8.3 Inter-faction trade journey

Use an explicit saved trade state machine with an ID, origin/destination warehouses, agreed give/want manifests, reservation IDs, cargo, route, progress and lifecycle state.

**Proposed transaction policy:** one initiating caravan travels out and returns. Both sides commit their offered resources when accepting the deal. The initiator's goods move from its available hand to outgoing cargo; the partner's goods are escrowed and cannot be spent while the caravan travels.

| State/event | Resource effect |
| --- | --- |
| Offer rejected | None. |
| Deal accepted / dispatch | Initiator's offered tokens become cargo; partner's promised tokens become reserved escrow. Each token remains owned/accounted exactly once. |
| Arrive at partner | Atomically credit offered cargo to the partner and move its escrowed return goods into the caravan. Record exchange exactly once. |
| Return home | Move return cargo into the initiator's available hand. Complete the journey once. |
| Cancel before exchange | Return outgoing cargo to its owner and release partner escrow according to the cancellation event; no exchange is recorded. |
| Failure after exchange | The exchange remains committed. Return cargo still belongs to the initiator and must remain accounted for until returned or explicitly reconciled. |

The normal peaceful game should not randomly refuse a fully reserved deal on arrival. This avoids the current system's arrival-time stock race. Duplicate arrival callbacks, snapshots and reloads cannot repeat the exchange.

Caravans prefer completed roads, and may use roads of any faction because all factions are peaceful in this version. **Proposed bootstrap rule:** they can also traverse unbuilt graph-edge corridors as slower foot trails. Such trails are visibly different, do not become owned roads, and cannot carry founding expeditions. This preserves Catan's ability to trade before two factions have connected their road networks.

Suggested visual travel speeds: one built strategic edge in six game seconds; a trail edge in twelve. Local approach/exit legs must be represented. Treat these as tunable game-space speeds, independent of zoom. An AI weighs completion time and does not route all useful trades across the entire island without reason.

Use bank caravans to an always-reachable exterior trade endpoint for 4:1 trades. Escrow four offered tokens and book one explicit bank-source receipt only on the return leg's completion. The inspector must identify bank trade; never pretend that another faction supplied those goods.

Limit active trade journeys to two per faction initially. A duplicate offer cannot reserve the same available stock twice. Save/load preserves both legs and all escrow. Offscreen journeys continue normally.

### 8.4 Conservation in the simplified economy

For each economic role, the accounting identity is:

`available hands + build reservations + trade escrow + journey cargo = initial grants + roll grants + bank imports - completed-build consumption - bank exports - explicitly archived holdings`.

Count each token in exactly one location. Production animations, barrel sprites and cosmetic belt items are excluded from this ledger by type. They must never be accepted by a spending API.

Age rollover archives old-age balances with receipts rather than disguising a reset as ordinary consumption. Failed/replayed commands and repeated transition processing leave the ledger unchanged.

## 9. Autonomous faction AI

### 9.1 Initial placement

Start with an empty board and visibly stage AI choices. Use a seeded first-player order and Catan-style snake placement: factions 1→6 place one settlement and adjacent road, then 6→1 place their second pair. Every placement obeys spacing, occupancy and positive-production checks. Setup requires no initial resource payment and grants no ordinary expansion VP events twice.

After all sites are operational, each faction starts at 2 VP and receives one resource per productive hex adjacent to its second settlement, once. Do not automatically give it one of every resource. Give the AI the same information a player inspecting the full board can see.

Score placement using expected production, useful resource diversity across both settlements, WOOD/BRICK access for expansion, WHEAT/ORE access for cities, and remaining legal expansion corridors. Avoid selecting six individually attractive but mutually landlocked starts. Use bounded lookahead and stable tie-breaking; log concise reasons so behaviour is inspectable.

The visible setup can be accelerated, but it must be a replay of real accepted placement decisions. Do not hand-place a final board and claim the AI chose it during the run.

### 9.2 Normal decisions

Use a readable heuristic baseline with explicit goals. On a decision step, an AI can inspect legal commands, choose an expansion/upgrade target, reserve and execute an affordable action, propose/accept a useful trade, wait for a known pending delivery or revise an infeasible plan.

Priorities should consider the cost and expected VP/output benefit of:

- an immediately affordable, useful city upgrade;
- founding at an already reachable legal node;
- building the next road toward a useful legal settlement site;
- trading a genuine surplus for the missing resource of a chosen plan;
- accumulating WHEAT/ORE for cities when expansion is constrained.

These are scoring inputs, not an inflexible ordering that always spends ore or always builds roads. Keep a small reserve for the current plan, penalise needless roads and repeatedly changing targets, and avoid trade-back loops. Accepting another faction's offer must help the recipient or meet its stated surplus policy; it must not be a scripted donation to the leader.

Make a bounded decision pass every game second with faction priority rotating deterministically. Trigger re-evaluation on resource receipt, build completion, trade completion or a blocked target. Use an action limit per pass to prevent one faction monopolising the simulation and prevent repeated zero-time trades.

### 9.3 Liveness and honest competence

When a faction waits, record a reason: missing resources, pending caravan, construction underway, no legal frontier or saving for a city. When the entire world makes no meaningful progress for many rolls, emit diagnostics showing inventories, targets and legal-action availability.

Fix planning, placement, trading or routing if a run stalls. Do not lower the 10-VP bar, grant emergency resources, destroy an opponent, silently advance an age on a timer or select a weaker board just to produce a passing demonstration. Bank trading, useful city upgrades and removing piece caps are the explicit MVP mechanisms for progress.

All factions use the same validated rule commands and the same action space. Headless runs and the rendered game use the same AI. Existing neural controllers can be retained behind a policy interface, but retraining belongs after this new ruleset is stable; training is not required to make the first autonomous build work.

## 10. Victory points and age rollover

### 10.1 Trigger and ranking

After an authoritative construction completion updates VP, check whether any one faction has at least 10 current-age VP. Record the first qualifying completion as the cause. If a batch makes multiple factions qualify at the same tick, resolve the reported age winner by ordered completion event, then stable faction ID. Advance the shared world once, not independently per faction.

Select two completed villages for **every** faction at the moment the trigger is recorded. Rank by:

1. Expected output per pulse from completed level and adjacent token odds, highest first.
2. Completed level/size, highest first.
3. Stable village ID.

Use theoretical output, not recent realised production or screen-visible building count. A city on weak hexes can rank below a settlement on much stronger hexes. Record the candidates, values and chosen two in the age-transition event.

All factions begin with two villages and cannot lose them in this peaceful MVP, so the normal case always has two candidates. A malformed save or fixture with fewer must fail validation or invoke an explicitly labelled fixture repair; do not silently invent survivors in a normal run.

### 10.2 Proposed carry-over contract

**Review-sensitive interpretation:** the two selected sites become the faction's only active settlements for the new age. Everything else becomes historical. This is chosen to preserve a meaningful repeated 10-VP race on one finite board. If Joe instead wants all older villages to remain economically active, the rollover rules, scoring and build-space policy need a different approved design before that variant is implemented.

| State | New-age treatment |
| --- | --- |
| Board, hex roles/numbers, terrain seed | Preserve. No new island or random redeal. |
| Six factions, colours and names | Preserve; no splits, collapse or extra winner reward. |
| Selected village IDs, names, node positions | Preserve. Reuse their single warehouse identity. |
| Selected city/settlement level | Restart as level-one settlements; city appearance/production retires. |
| New production buildings | Begin visible new-age construction at both selected villages of every faction. |
| Current-age score | Re-derive as 2 VP per faction when the carried sites are operational. |
| Non-selected villages | Retire from production and VP; release strategic occupancy after the transition. Keep a sparse historical footprint and chronicle. |
| Old strategic roads | Retire ownership and expansion connectivity; keep a visibly older public-path footprint. New paid roads can rebuild the same edge. |
| Old five-slot balances | Archive with a transition ledger entry; do not convert a stockpile of wood into a stockpile of pyratite just because the role ID is stable. |
| New starting resources | Grant one token per productive hex around the lower-ranked carried settlement, using the new age's display identities, once. |
| Outstanding offers/builds/expeditions | Cancel/reconcile once before archiving old resources; release node/edge reservations. |
| In-flight trades | Reconcile outgoing cargo/escrow to owners if unexchanged; preserve ownership of any already-exchanged return cargo. Archive resulting old-age holdings with receipts. Never credit the new age. |
| Military | Preserve old identities/history as inactive veterans or historical garrisons. They have no production, VP, blocking or combat effect. New age recruitment has its own bounded quota. |
| Lifetime statistics and history | Preserve separately from current-age mechanics. |
| Camera | Preserve position/zoom; announce the transition without forcing a camera tour. |

Historical remains are scenery with provenance, not invisible active settlements. A current-age settlement can legally reuse a released node, replacing/repairing its old warehouse footprint. Never draw two warehouses on top of each other. Historical buildings do not block current-age road corridors or distance-rule occupancy.

### 10.3 Transition transaction and visible construction

Use a saved transition ID and explicit phase: `RUNNING`, `TRANSITIONING`, then `RUNNING` for the next epoch. On entry, freeze new economic actions and production pulses; viewing remains available.

Make one deterministic transaction that records the winner/survivors, reconciles commitments, archives old balances and active-site state, changes the age, resets scores and prepares the selected sites' new production. Use a save checkpoint before and after the boundary; load must either finish an identified pending transition or resume the completed epoch, never apply it twice.

New construction at carried sites is an explicit free transition grant, not a request that depends on inaccessible new-era resources. Show scaffolds or an accurate available build state, followed by new districts coming online over approximately ten game seconds. Both warehouses remain single identifiable anchors. Start the next age's production schedule after the carried sites are ready, avoiding a bootstrap deadlock.

Emit `age_started` and the new starting grants once. Clear old AI plans and stale selected IDs carefully, then let the same six AIs resume. There is no automatic carry-over of a winner's score, no leader-plus-four threshold and no “world has gained enough VP” shortcut.

### 10.4 Fourth-age completion

In age four, the first faction to 10 VP receives one recorded final result instead of a fifth-age transition. Show a dismissible completion notice and the four age winners. Continue viewing and simulation in age four if desired; suppress repeat completion awards. An explicit New World action creates a separate run.

## 11. Military presentation without combat

Every settlement gets one military production facility appropriate to its age; cities may add a vehicle/machine facility as part of their larger composition. These are built automatically as part of village completion, not selected by the spectator.

Use the small verified asset subset in section 5. Suggested progression: Widelands barracks/soldiers; then OpenRA barracks/infantry and a city vehicle yard; then visible industrial recruitment and Mindustry units. Keep unit/facility names honest where existing art is shared. A catalogue alias is not proof of a distinct soldier type.

Proposed quota: produce one unit every 45 game seconds until four current-age units exist for a settlement or eight for a city. Use a reproducible queue and give every recruited unit an ID, source village, age and standing position. City upgrades increase the quota by four; they do not duplicate existing recruits. No resource charge, upkeep or VP is applied in this first version.

Units may move out of their facility to a clear parade/idle location and animate idly. They must not acquire targets, fire, fight, patrol to enemies, block civilian traffic, occupy economic nodes or trigger old military AI. Turn off projectile, damage, capture, threat, outbreak, nest, unrest and collapse effects at the simulation level.

At long zoom, render garrisons as compact groups or counts. Preserve their identities in state/history. Old veterans and new quotas must not cause an unbounded stream of active pathfinding actors. Future combat will require an explicit economic and tactical design; do not smuggle its costs into this spectator milestone.

## 12. Mobile viewing and semantic labels

### 12.1 Camera

- One-finger drag anywhere in the world pans the camera, including a drag that started over a building or unit.
- A short press/release without a drag is an inspect tap. Suggested drag threshold: eight logical dp, scaled correctly for device density and Godot viewport stretch.
- Two-finger pinch zooms around the gesture midpoint; that world location should remain under the midpoint. Track midpoint motion for two-finger panning too.
- A gesture that becomes a drag or pinch can never select an object on release. Suppress duplicate emulated mouse/touch events and cancellation/focus-loss leftovers.
- Clamp to the board bounds plus a small viewing margin. Derive zoom limits from a legible close view and the full-board fit. Start near a working village at a readable scale, not at a tiny whole-island overview.
- A small overview/fit button may show the entire island; it does not create another map mode. Do not auto-follow a warehouse, party or invisible legacy player after panning.
- Desktop equivalents: drag to pan, wheel/+/− to zoom, click to inspect. Keep them useful for testing.

No joystick, click-to-walk, avatar selection, wizard camera tether or movement-driven simulation clock remains in the new player experience. The world progresses while the player leaves the camera still.

### 12.2 Two-step label contract

Use a single selected semantic ID and three clear states: `HIDDEN`, `LABEL`, `DETAILS`.

| Gesture | Result |
| --- | --- |
| Tap a world object | Show a small anchored, tappable label naming it, with ownership/status where helpful. |
| Tap that label in a distinct second gesture | Open expanded details, using a readable bottom sheet/card on a phone. |
| Tap a different object | Replace selection and show its first-stage label. |
| Tap empty world | Dismiss the compact label or details sheet and clear selection. |
| Pan/pinch | Move/zoom the view without activating an object or advancing label state. |
| Dismiss details / Android Back | Return to its compact label, then dismiss on a further Back action. |

Do not make an accidental double event open details immediately. No avatar-distance, line-of-sight or dialogue-range condition applies to a god inspecting the world. Do not restore the older speech/response progression in this mode.

Anchor the compact label to the visible object using the same transform as rendering. Keep it inside safe screen bounds and away from the primary HUD. Minimum touch target is 48 logical dp; text stays screen-sized across world zoom. Hide an offscreen anchor without losing its semantic identity. An open detail sheet may remain available while its target is offscreen.

Resolve overlapping sprites by visible draw order/ground footprint and an enlarged touch hit area. At whole-board zoom prefer village/route groups to arbitrarily selecting an invisible worker. A semantic ID must refer to the same object before and after zoom, save/load and presentation culling.

### 12.3 Useful details

| Selected item | Detail content |
| --- | --- |
| Hex/region | Current-age resource name, number, exact odds, bordering active villages and last production. |
| Village/warehouse | Name/faction, settlement or city, age/VP, touching hexes, expected yield, station counts, faction resources, journeys and the AI's current plan. |
| Workshop/processor | What it is, source district/hex, current work/visual chain, and contribution to the village's strategic production. |
| Worker | Job, village and current visible task; no required dialogue menu. |
| Strategic road | Faction/current or historical status, endpoints, completion state and journey traffic. |
| Caravan | Origin/destination, both goods manifests, outbound/return state and progress. |
| Founding expedition | Origin/destination, worker roles, committed supplies and progress. |
| Military facility/unit | Age, village, unit count/quota or identity, and idle/garrison status. |
| Historical remains | Original village/faction/age and a concise history, clearly distinguished from active production. |

Do not expose debugging class names, token enums or “cosmetic economy implementation” jargon in the player flow. Explain the visible game's behaviour plainly, for example “This district supplies timber when its woodland rolls a 6.”

### 12.4 Minimal HUD and lifecycle

Show age, a compact six-faction VP strip, play/pause and speed (1×/2×/4×), a menu and an optional board overlay toggle. Details may expand this without covering the entire world permanently. Use small event notices for completed villages, dispatches and age changes; avoid mandatory modal acknowledgements during autonomous play.

Pause/speed affect the single simulation clock and authoritative journeys together. Camera/inspection work while paused. Keep camera movement separate from game-state commands. Save on explicit save, suitable periodic checkpoints and app backgrounding. Pause while backgrounded; no unrequested offline catch-up is needed.

Primary layout should work in the repository's portrait phone format. If landscape is supported, reflow HUD and details without altering world scale logic or interaction accuracy. Honour safe areas and Android Back. Loading must show progress and lead directly to a viewable world.

## 13. Technical integration and saved state

### 13.1 One selected ruleset, one simulation

Introduce a versioned `god_catan_v1` rules profile inside the authoritative Python application. It selects the new board, economy, AI, journeys, village construction and age system. It must not instantiate a second live legacy `WorldState` simulation alongside `HybridWorld`; reuse the embedded state/clock and geometry utilities appropriately.

Make the profile's update pipeline explicit. The current `HybridWorld.advance()` calls worker production, logistics, industry, regions, nests, society/history, drafting, recruitment, AI and military systems. In the new profile, run only the portions that belong to this PRD. Calling all those functions and hiding their UI will not satisfy the overhaul.

In particular, separate peaceful journey movement from military targeting; separate visual worker tasks from recipe production; and replace old progression checks instead of running both. The new profile's balance ledger is its only economic truth. Old ware totals and five-slot totals cannot both fund an action.

Prefer small modules beside the existing authoritative code, for example:

| Responsibility | Suggested location / existing integration |
| --- | --- |
| Explicit-cell strategic graph | Generalise `sim/dmb/world/board.py` utilities; use from the hybrid rules profile. |
| Five-slot definitions, costs and display mapping | New small data/registry file under `wizard_rts/data/`, with schema validation. |
| Roll production and construction legality | Focused God World rules module used by all commands and AI. |
| Reservations and resource accounting | One ledger service adapted to the five-slot holdings/cargo model. |
| Routes, caravans and expeditions | Adapt existing transport/trade concepts to the new graph and manifests. |
| Village identity, composition and age history | Existing settlement identity/event patterns plus a new deterministic projection service. |
| AI | New policy over the same legal-command API; retain a future controller adapter. |
| Camera, gesture arbitration and labels | Godot components extracted/adapted from the current world scene and interaction code. |
| On-device hosting, save IO and art loading | Existing Android/Python route, versioned save service and `AssetLoader`. |

These module names are recommendations. Organise around responsibilities, not a new framework or duplicated server. Keep old modes available as legacy development paths where practical, while the ordinary menu and launchers default to God World.

### 13.2 Authority and presentation contract

Python owns board legality, faction balances, dice/RNG, reservations, accepted plans, journey progress and arrival, construction completion, VP and age changes. Godot owns rendering, camera, gestures, label state and visual interpolation. A caravan arriving because Godot played an animation cannot be the authoritative exchange trigger.

Snapshots include stable IDs and all semantic data the viewer needs. Route/actor interpolation is read-only. Derive loading/culling interest from the free camera viewport, not the old wizard pose. Offscreen simulation continues; revisiting a place shows its current state.

Cosmetic randomness must have its own seeded stream or derive from stable visual keys. Changing zoom, opening a label, hiding a worker or rendering extra frames must not change the next dice roll or AI choice. Bound route-search work by counted budgets and cache shared paths.

Use the existing simulation quantum where possible. The proposed timing values are game time; 4× speed accelerates production, construction and travel together. Wall-clock time, screen-frame count and human camera actions are not rules inputs.

### 13.3 Minimum saved data

| Record | Required fields / invariants |
| --- | --- |
| Run | Schema/ruleset version, run ID, seed, game time, speed/pause state, current age/epoch, simulation RNG states and next scheduled roll. |
| Board | Shape ID, explicit axial cell list, resolved resource roles/tokens, stable node/edge geometry and ownership/reservations. |
| Faction | Stable ID/colour/name, available five-slot hand, commitments and AI goal/reason/cooldowns. VP is derived from villages. |
| Village | Stable ID/node/faction/name, epoch status, completed level, warehouse ID, construction state, source districts and generation version/seed. |
| Visual composition | Stable station/component IDs, source-hex bindings, anchors/footprints and any durable layout overrides. Reproducible scenery can regenerate. |
| Journey | Stable ID/type/owners/endpoints, graph/world route, authoritative progress, cargo, escrow links and phase. |
| Military | Stable unit ID, origin village/age, standing pose, quota membership and historical/current status. |
| Transition/result | Transition ID, phase, trigger completion/winner, selected villages, reconciliation receipts, new-age grants and completion flag. |
| History/events | Age winners, founded/upgraded/retired villages, transactions and bounded recent feed; durable receipts survive feed trimming. |
| Viewer | Camera position/zoom and optional selected semantic ID, separate from deterministic economic state. |

The current `HexBoard.from_dict()` rebuilds from radius. Update that path for explicit layouts; otherwise a save of the new board can silently return the wrong topology. Validate all references on load, including routes and reservations. New saves must not overwrite an incompatible wizard campaign save. Reject unsupported schemas with a clear message instead of partially loading them.

### 13.4 Packaging and performance

Ship a standalone Android build that starts the Python authority in the app and runs without a PC or network connection. Preserve the existing runtime build approach rather than replacing it with a phone browser or remote-only spectator. Networking/multiplayer is outside this milestone.

Maintain a data-driven allowlist for the actual selected art and all referenced animation parts. Validate every resource through the exported pack, using `AssetLoader`. The current art catalogue includes many more entries than are needed; neither a raw PNG on disk nor a successful desktop editor run proves the APK includes it.

Target sustained 30 fps or better on an identified supported Android device at normal village zoom, with responsive touch input during a long four-age run. Measure actual frame times, memory, texture loading and path-search counts; state the device and build. This is a target, not a claim that the current build reaches it.

Use chunked terrain, batched sprites, cached textures, bounded visible activity and shared routes. Keep village/actor state persistent while rendering only visible detail. Do not render all buildings as individual always-processing nodes or reparse the full catalogue every snapshot. Pause on app backgrounding and resume from the same saved clock without a catch-up storm.

## 14. Implementation milestones and completion evidence

The Claude handoff authorises this new sequence when the owner uses it to request implementation. Finish each milestone with runnable evidence and a short record of changes, results and remaining failures. Do not stop at another design document or a static showcase.

| Milestone | Deliverable | Exit evidence |
| --- | --- | --- |
| M0 — Reconcile and baseline | Read entry instructions/current source; record checkout and baseline checks; update product direction and feature-branch plan. Produce the small verified asset manifest. | Old/new rule decisions are explicit. Selected resource paths resolve. Existing failures are distinguished from new failures. |
| M1 — Executable Catan world | 30/80/109 board, six-faction legal setup, five-slot inventory, production, roads, cities and 10-VP scoring in the authoritative runtime. | Deterministic headless tests and several real AI age-one wins without forced resources or timers. |
| M2 — Mobile observer and villages | Free camera, touch arbitration, two-step labels, one continuous map and source/odds-derived village composition. | Actual headed before/action/after captures for pan, pinch, first tap and label tap. A maximum-size city fits and remains readable. |
| M3 — Physical economic journeys | Constructed roads, warehouse caravans, bank trade and worker founding parties tied to authoritative reservations/arrival. | Observe a real AI-negotiated trade and a real AI-founded village; ledger and save/load checks pass in each journey phase. |
| M4 — Four-age continuity | Same-board rollover, every faction's two chosen sites, new-age construction, score/stock reset, history and final-age result. | One uninterrupted autonomous run through all three transitions and the fourth-age 10-VP result. No debug advance, elapsed-time fallback or manual intervention. |
| M5 — Autonomous soak and Android | Robust AI over a fixed seed corpus; exported art and standalone on-device runtime; usable controls over a long run. | Metrics/event logs for the corpus, meaningful runtime captures, APK/export audit and actual phone checklist results. |

**Headless seed corpus:** use seeds 0–19 for a reproducible first acceptance set, including separate regression runs for previously used seed 507. Each must finish all four ages with legal actions, balanced accounts and no forced transition. A provisional diagnostic budget is 600 production pulses per age. Reaching that budget is a failed/stalled run to investigate, not permission to advance it. Report every seed, per-age winner, pulse count, trade count, completed villages/cities and stall reasons.

**Pacing target:** initially aim for roughly 10–25 minutes per age at 1×, then tune the pulse/travel/construction intervals using real results. Keep the 10-VP threshold, costs and declared rules fixed during pacing work. The corpus diagnostic budget is not the desired player waiting time.

**Visual evidence set:** capture the real game at setup, a working age-one village, a city beside a settlement, first-stage label, expanded detail, pan/pinch states, a trade outbound/exchange/return, a founding departure/arrival, each age's production districts, an age-boundary before/after view, idle military and the fourth-age completion. Include at least portrait 450×800-equivalent framing and physical-device evidence. Do not count boot-only screenshots as playtests.

Run meaningful unit/property tests for the new economic contracts and existing regression checks relevant to shared code. Headless simulation success cannot certify mobile input or visual layout. An APK build cannot certify on-device hosting. Mark missing evidence as unverified and continue independent fixes; do not mark the product complete while core acceptance remains unmet.

## 15. Acceptance criteria and concrete test cases

| ID | Observable pass condition |
| --- | --- |
| AC01 | A new normal game opens God World with no walking avatar, joystick, wizard tutorial or developer menu requirement. |
| AC02 | Board has exactly 30 land hexes, 80 unique nodes and 109 unique edges, with the specified terrain/token inventory and valid reciprocal adjacency. |
| AC03 | Save/load reproduces the exact 30-cell layout, IDs, token assignments and current occupancy. It never rebuilds a regular 19- or 37-hex board. |
| AC04 | Six AIs visibly choose two legal initial settlements and roads each in snake order; resources from the second settlement are granted once. |
| AC05 | Controlled rolls credit each adjacent settlement once and city twice, including multiple matching hexes; deserts and 7 give nothing. |
| AC06 | Enumerating all 36 dice pairs gives exactly five hits for a 6 hex: a settlement gains five tokens and a city ten over that enumeration, regardless of its visible station count. |
| AC07 | The economy exposes exactly five spendable roles. Old worker programs, machine recipes, power and decorative cargo cannot add, remove or block those balances. |
| AC08 | Roads, settlements and cities charge the stated costs once, refund uncommitted cancellations and reject invalid/duplicate commands without mutation. |
| AC09 | A city is worth two total VP, not three. Five completed cities can reach 10 without development cards, combat or a forbidden piece cap. |
| AC10 | Every active village has exactly one warehouse. Production districts, station counts and source bindings match adjacent roles, pips and completed level. |
| AC11 | A city doubles production stations while keeping one warehouse, and its additional visual processors do not create additional economic yield. |
| AC12 | Same-role adjacent hexes retain separate source districts and their distinct roll behaviour. Desert-facing space does not gain a producing workshop. |
| AC13 | A new village stays pending while its worker party travels its owned completed-road route; production/VP begin only at operational completion. |
| AC14 | Concurrent founders cannot occupy the same node or adjacent excluded nodes; incomplete roads never enable expansion. |
| AC15 | A real inter-faction trade reserves both manifests, visibly exchanges and returns; accounting balances before, during and after every leg. |
| AC16 | A partner cannot spend escrowed goods; replayed arrival cannot pay twice. Save/load in every trade phase preserves exact ownership. |
| AC17 | Isolated starting factions can trade via slower trails, while founding expeditions still require owned completed roads. Bank 4:1 remains available without a port or another faction's consent. |
| AC18 | A faction at 10 triggers the shared transition once; six factions totalling 10 while each is below 10 do not. Waiting alone never advances an age. |
| AC19 | Ranking selects two villages independently for each faction from theoretical production. A 12-pip settlement outranks a city touching only a 2-pip hex. |
| AC20 | Transition preserves the selected IDs/nodes/warehouse identity, starts new construction, resets active scores/balances and reconciles old commitments exactly once. |
| AC21 | Non-selected historical sites and old roads cannot produce, award VP or retain hidden strategic occupancy/connectivity. A legal site can be refounded without duplicate warehouses. |
| AC22 | Reloading at an age boundary neither repeats grants nor skips/forks the transition. The normal rollover begins the next age with two level-one villages per faction. |
| AC23 | All four age mappings and a final-age result occur in one autonomous run. Old VP timers, rising bars, drafts and global-total triggers remain inactive. |
| AC24 | Military facilities visibly produce the bounded garrison. Units never attack, damage, block a caravan or consume expansion resources; no outbreaks occur. |
| AC25 | Dragging from a sprite pans; a pinch zooms around its midpoint; neither gesture selects on release. Synthetic mouse events do not duplicate touch actions. |
| AC26 | First tap shows an anchored name label; a separate tap on that label opens details. Labels remain usable at all zoom levels and phone safe areas. |
| AC27 | Panning away never snaps back to an old avatar. Revisiting shows progressed villages/journeys; culling follows the camera viewport. |
| AC28 | Camera movement, selection, frame rate and view distance do not alter headless economic/AI results for the same simulation inputs. |
| AC29 | The standalone APK boots and advances locally on a supported phone without a PC or internet connection, and selected assets resolve in the exported pack. |
| AC30 | Every acceptance seed completes legally within the diagnostic budget; actual pacing/performance and any unverified device checks are reported honestly. |

**Small ledger vector:** start A with two WOOD and B with two BRICK. Accept a 1:1 trade. A has one available WOOD and one outbound WOOD cargo; B has one available BRICK and one escrowed BRICK. At exchange B gains one available WOOD and the caravan holds one BRICK; on return A receives that BRICK. Totals stay at two WOOD and two BRICK throughout. Reapplying exchange/arrival events changes nothing.

**Small scoring vector:** two settlements plus three cities equal 8 VP. Upgrading a settlement makes it 9, not 10. Upgrading the other makes it 10 and records one age trigger. A decorative workshop completing in that village awards no VP.

**Carry-over vector:** record three villages of one faction with expected capacities 12/36, 10/36 and 4/36. Choose the first two, even if the third happened to receive more recent rolls. If both chosen villages were cities, both restart as settlements, leaving 2 current-age VP after the transition, rather than carrying 4 or 10 into the next race.

## 16. Boundaries and later work

The longer-term direction is a god game. Preserve seams for future encouragement/discouragement, disciples and minigames played with other gods, but none of those is necessary for this autonomous-world milestone. Existing Skull/duel/story ideas must not become a prerequisite to watching the economy progress.

Defer god powers, player economic commands, human faction turns, multiplayer, combat, outbreaks, conquest, faction fission, miracles, drafting, quests, dungeons and full upstream recipe/power/fluid simulation. Preserve useful assets and code behind clear legacy boundaries. Do not expand the imported content roster as a substitute for completing the requested loop.

The three owner-facing design choices most worth reviewing are **what happens to non-carried villages and old stock at age change**, **the deliberately reduced Catan rules subset**, and **pyratite versus pyrite naming**. The defaults above are concrete enough to build and test; they should remain explicit rather than disappearing into implementation assumptions.

## 17. Sources and review limits

### Repository evidence

All repository observations refer to the pinned commit above. Source files and the full asset catalogue were read; a few representative imported sprites were visually inspected. The game was not executed during preparation of this PRD, and old test/performance claims are not fresh verification.

- [Repository entry instructions](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/CLAUDE.md) and [hybrid instructions](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/WizardRTSHybrid/AGENTS.md).
- [Authoritative world/update loop](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/WizardRTSHybrid/wizard_rts/world.py), [trade](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/WizardRTSHybrid/wizard_rts/trade.py), [VP/eras](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/WizardRTSHybrid/wizard_rts/vp.py) and [history](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/WizardRTSHybrid/wizard_rts/history.py).
- [Legacy integer-corner board](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/sim/dmb/world/board.py).
- [Godot world/camera input](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/godot_project/client/scenes/hybrid_world.gd), [current inspection labels](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/godot_project/client/hybrid/wizard_labels.gd) and [art renderer](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/godot_project/client/hybrid/hybrid_art.gd).
- [Full asset catalogue](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/godot_project/client/hybrid/art/catalogue.json), [frozen content roster](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/WizardRTSHybrid/wizard_rts/data/content_freeze.json) and [packaged image loader](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/godot_project/client/scripts/asset_loader.gd).
- [Android status and packaging](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/README_ANDROID_TWO_PHONES.md) and [on-device Python plugin](https://github.com/Joesalmon1985/DuelMasterBattle/blob/1b9513dd973087281bfcedeb8a786788331697b0/WizardRTSHybrid/scripts/android/overlay/PySimPlugin.kt).

Keep existing asset attribution and provenance records. Catalogue licence strings are source metadata, not a new independent legal review; check the project's existing notices when selecting/repackaging art.

### Catan reference baseline

Official publisher references establish the underlying board-game mechanics. The continuous-world, visual-station, caravan, AI and age-transition systems in this document are proposed game-specific designs.

- [CATAN base rules, 2020](https://www.catan.com/sites/default/files/2021-06/catan_base_rules_2020_200707.pdf): reference for corner/edge placement, roll-based settlement/city production, basic construction costs and trading.
- [CATAN 5–6 rules, 2022 revision](https://www.catan.com/sites/default/files/2024-03/Catan%20Game%205-6%20Rules%202022%20240313.pdf): 30-terrain-hex board and setup diagram, extension pieces and starting setup.
- [CATAN 5–6 rules, 2025](https://www.catan.com/sites/default/files/2025-03/CN3082%20CATAN%20%E2%80%93%205-6%20Rulebook%202025%20reduced.pdf): extension components, number discs and paired-player turn structure. This PRD intentionally replaces that tabletop turn structure with autonomous continuous action.

The 80-node/109-edge totals are derived from the explicit 30-cell graph, not claimed as counts printed in the rulebooks. Production percentages are exact calculations from two fair dice, rounded to two decimal places for display.
