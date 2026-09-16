# DUELMASTERBATTLE

## Complete Game Design, Systems, Content & MVP Specification

### Working Design Specification v0.3 — 15 September 2026

---

# DESIGN STATUS

This is **Working Design Specification v0.3, 15 September 2026**, replacing v0.2.

- **LOCKED**: an explicit user decision. Change only through a deliberate design revision.
- **DEFINED**: a selected, buildable rule, including sensible defaults chosen under the user's instruction to resolve remaining questions.
- **TUNABLE**: a working numerical value with a defined rule; playtesting may change the value.
- **POST-MVP**: intentionally scheduled later, with a stated baseline or extension boundary. It is not an unanswered prerequisite.

There are no unassigned design questions blocking the MVP code plan. Validation questions remain experiments with a chosen baseline, not instructions for programmers to invent rules.

**Revision basis.** The user's latest decisions take precedence over the older economy, timing, targeting and era-loss rules. This revision updates the affected sections and decision records throughout the document. In particular: there are two distinct economies; industrial output runs in Game Time; ordinary worker motion is illustrative; carts and individual military units are real persistent entities; every culture can access all 60 processors for its era; the wizard can destroy any unit or building and cannot be harmed by faction military; living NPCs and active quests survive era changes; collapsed settlements become inert ruins; a sole surviving faction is protected and scheduled to split.

**Defaults chosen in this revision** include node-capacity calculation, wait semantics, catastrophe treatment granularity, concrete VP/construction rules, era starter facilities, technology draft edge cases, seven Aspect definitions, battle handoff, and Python/Godot ownership. These are DEFINED rather than retrospectively attributed to the user.

The title **DuelMasterBattle** remains a working title. References to design sections retain their original numbering.

---

# VOLUME I — GAME DEFINITION

# PART I — PRODUCT

## 1. One-sentence game definition

**LOCKED**
A systemic single-player fantasy adventure in which the player inhabits an extraordinarily powerful wizard travelling through a perpetually cycling civilisation, exploring settlements and dungeons, forming relationships, solving people's problems and intervening with magic in autonomous economies, wars and era-specific catastrophes without directly controlling the societies whose histories they alter.

---

## 2. Expanded product definition

**LOCKED / DEFINED**

DuelMasterBattle is an offline single-player systemic RPG/adventure in one persistent 19-hex strategic region. History cycles through Prehistoric, Historic, Modern/industrial and Futuristic eras. Future is dystopian by default; an optional later Utopian branch has a defined extension rule in the resolved decision register.

The wizard explores settlements and dungeons, talks to persistent people, solves problems, fights Mastermind magical duels and intervenes in autonomous wars. The player never commands faction workers or armies.

There are **two separate economic layers**:

1. **Construction and trade:** Catan-style dice generate the five basic goods—timber, brick, wool, grain and ore—at eligible settlement nodes. They are stored locally and moved in persistent cargo-carrying carts before they can fund roads, settlements, cities or trades.
2. **Industry and military production:** each era supplies twelve industrial raw-resource types, two per terrain. Persistent buildings and shared finite deposits determine calculated processing capacity and the real-time output of three military factories per settlement/city. Workers visibly extract, carry and process goods, but their walking paths and animation completion do not drive production.

Industrial output advances at all settlements in **Game Time**, including off-screen settlements. Armies cannot travel between strategic nodes merely because seconds pass. An accepted player journey or Wait advances one **World Turn**; the rotating active faction may then move its disengaged forces up to two nodes. A **World Round** completes when every active faction has taken its seat; every faction then drafts one technology card.

Wizard/hazard duels pause Game Time and World Turns while the duel runs on its own encounter clock. Local faction battles use real positioning, range and terrain. Each visible soldier corresponds to one persistent military unit. On departure, the remaining battle is calculated from its actual current state.

At the first committed action that gives a faction 10 VP, the era ends immediately. When multiple factions entered the era, all below 5 VP and one lowest-scoring faction collapse; the sole-faction exception prevents extinction. Collapsed settlements, industry and roads become inert scenery and release their sites. Surviving non-splitting factions upgrade their two highest-capacity settlement sites; voluntary splits normally use four sites in two geographically compact pairs. If an era begins with one faction, it must split at the next transition. Full rules and undersized-split recovery are in §40.

Surviving buildings, workers, units and stocks remain; old industry can still produce old units. Living NPCs do not age out or get replaced merely because an era changes. Active quests continue using stable IDs. Non-core legacy settlements do not score new-era VP until upgraded. Each culture currently has access to the complete 60-recipe catalogue for its era; future culture-specific restrictions are an extension.

The wizard's constraint is presence. They are immune to faction military damage and may destroy any local unit or building with one spell. A visit permits at most one successful magical catastrophe treatment per adjacent hex, up to three; Wait does not renew that allowance. Ordinary failure remains non-terminal. Uncontrolled catastrophe reaching the outbreak limit kills the wizard and returns to the menu.

Catastrophe themes remain demons in Prehistoric/Historic, pollution and aliens in Modern, and nuclear escalation plus hostile AI/cyborgs in dystopian Future. The working loss threshold is eight outbreaks in the current era.

The initial product is an offline desktop game using Godot for local play and Python for the persistent world. Pointer-driven controls must work as single-touch controls; mobile packaging is deferred. Presentation is readable 2D top-down sprite art. There is no compulsory main quest, maximum cycle count or generic retirement ending; particular authored quests may offer explicit endings.

---

## 3. Player fantasy

**LOCKED**
The mechanical fantasy is:

> **Be the immensely powerful but geographically limited outsider living inside history rather than commanding it from above.**

The player should feel like:

- an adventurer walking through functioning societies;
- a powerful wizard whose intervention can dramatically change local events;
- a recurring witness to civilisation;
- an investigator of people, places and systems;
- a participant in wars without becoming their general;
- someone whose opinions can influence rulers without possessing them;
- someone who can remember a place across enormous historical transformations;
- someone forced to decide what deserves their finite attention.

The wizard can destroy any local ordinary unit or building with one spell and cannot be harmed by faction military.
The wizard does **not** possess enough attention to personally solve every simultaneous crisis.

---

## 4. Target player

**DEFINED**
The intended player enjoys:

- systemic games;
- emergent storytelling;
- exploration;
- simulation;
- RPG dialogue;
- puzzle solving;
- indirect strategy;
- discovering why events happened;
- replayable procedural worlds.

The player does not need to be an expert strategy gamer because the strategy simulation is not directly controlled.
The design expects patience and curiosity but should avoid requiring spreadsheet-level management.
Mastery should come from understanding relationships between systems rather than memorising extensive control schemes.
Accessibility of interaction is prioritised over mechanical simplicity underneath.

---

## 5. Reference points

**DEFINED**

### Catan

**Inherit:**

- hex resource geography;
- nodes and edges;
- roads;
- settlements and cities;
- victory points;
- development race.

**Do not inherit:**

- abstract resource cards as the final economy;
- fixed board-game session ending at 10 VP.

**Transform:**
10 VP becomes the trigger for a global historical era transition.

---

### Widelands

**Inherit:**

- production chains;
- local stocks;
- indirect workers;
- transport networks;
- logistical bottlenecks;
- visible economic causality.

**Do not inherit:**

- player-directed settlement management as the primary experience.

The faction AI operates the economy. In this adaptation, industrial throughput is calculated; worker carrying and processing animations illustrate it. Real Catan cargo, source depletion and building destruction remain mechanically consequential. Local worker navigation does not determine throughput.

---

### Command & Conquer

**Inherit:**

- technologically legible military forces;
- economic production feeding warfare;
- factional military character;
- dramatic clashes.

**Do not inherit:**

- player RTS control;
- unit selection;
- direct battlefield orders.

Armies are autonomous.

---

### Pandemic

**Inherit:**

- escalating distributed threats;
- spread;
- local worsening;
- cascade risk;
- failure caused by insufficient attention.

**Transform:**
the catastrophe changes identity across eras.

---

### Dungeon Master

**Inherit:**

- compact explorable dangerous spaces;
- environmental puzzles;
- persistent mechanisms;
- spatial reasoning;
- systemic dungeon grammar.

**Transform:**
"dungeon" is era-neutral and may mean cave, mine, temple, bunker, laboratory, alien structure or machine complex.

---

### Disco Elysium

**Inherit:**

- dialogue as gameplay;
- highly reactive conversations;
- internal faculties commenting on events;
- passive and active checks;
- failure producing narrative rather than simply blocking it;
- player knowledge changing what can be understood.

**Do not inherit:**

- a dialogue-heavy presentation that replaces physical world exploration;
- its exact skills, setting or writing voice.

---

### Mastermind

**Inherit:**

- hidden information;
- hypothesis;
- attempt;
- partial feedback;
- deduction;
- progressively narrowing possibilities.

This remains the basis of the project's personal magical duel system.

---

## 6. Distinctive proposition

**LOCKED**
The distinctive proposition is the interaction of seven layers:
PERSISTENT HEX GEOGRAPHY
        ↓
AUTONOMOUS CIVILISATIONS
        ↓
LOCAL CONSTRUCTION STOCKS + CALCULATED INDUSTRY
        ↓
AUTONOMOUS TECHNOLOGICAL WARFARE
        ↕
ERA-SPECIFIC WORLD CATASTROPHE

PLAYER WALKS INSIDE THESE SYSTEMS
        ↓
SEMANTIC KNOWLEDGE UI
        ↓
DIALOGUE / QUESTS / DUNGEONS / MAGIC
        ↓
HISTORICAL CONSEQUENCES
        ↓
ERA RESET
        ↓
NEW VERSION OF THE SAME WORLD

The player is neither the ruler of the simulation nor an irrelevant spectator.
They are an exceptionally powerful local intervention inside it.

---

# PART II — DESIGN PROBLEMS

## 7. Primary design problems

### Problem: enormous simulation complexity could overwhelm the player

**Chosen solution:** The simulation remains mostly autonomous and is exposed through people, physical activity and semantic labels rather than management dashboards.
**Trade-off:** Some exact numerical information remains hidden.
**Validation:** New players must be able to diagnose simple economic and political situations by observing the world.

---

### Problem: indirect strategy may make the player feel irrelevant

**Chosen solution:** Local magical intervention is intentionally powerful.
The wizard can:

- destroy assets;
- protect units;
- influence battles;
- solve crises;
- change leaders' opinions;
- remove threats.

**Trade-off:** The player must be prevented from becoming a global omnipotent strategy controller.
**Validation:** A battle the player attends should feel dramatically different from one they ignore.

---

### Problem: player power could trivialise the world

**Chosen solution:** Presence costs time.
Moving between strategic nodes advances the world.
**Validation:** Playtests must repeatedly produce situations in which the player sincerely regrets being unable to attend two simultaneous events.

---

### Problem: six factions × four eras × thousands of entities creates impossible hand-authoring requirements

**Chosen solution:** Structured procedural generation plus LLM content compilation.
Deterministic game systems generate truth; LLMs generate expression.
**Validation:** Bulk-generated content must pass schema, canon, knowledge and quality checks.

---

### Problem: generated dialogue could become incoherent

**Chosen solution:**
SIMULATION FACTS
\+ CHARACTER FACTS
\+ ERA / CULTURE-PACKAGE CONTEXT
\+ KNOWLEDGE STATE
\+ QUEST STATE
\+ CHRONICLE
        ↓
LLM CONTENT COMPILER
        ↓
VALIDATION
        ↓
CANONICAL DIALOGUE DATA

The LLM cannot directly change simulation state.

---

### Problem: history could branch exponentially

**Chosen solution:** Era transitions summarise retired history while preserving living NPC identities, active quests and surviving assets. Historical compression must not delete live references.

---

### Problem: economy could feel like irrelevant background simulation

**Chosen solution:** Economic failure generates visible human, military and quest consequences.

---

### Problem: a sandbox without a main quest could feel directionless

**Chosen solution:** NPCs and simulated institutions constantly generate goals, conflicts and invitations.
The player chooses what to care about.
**Trade-off:** The game relies heavily on convincing world-generated stories.
**Validation:** Players should spontaneously form personal priorities without being assigned a compulsory global objective.

---

### Problem: catastrophe could feel unfair

**Chosen solution:** Terminal catastrophe must emerge through escalating readable stages rather than random instant failure.

---

## 8. Design pillars

### Pillar 1 — The world acts without the player

Industry advances at all settlements in Game Time; strategy, travel and catastrophe follow World Turns regardless of which node is rendered. Defined global pauses apply during duels and modal screens.

**Violation:** simulating an unvisited settlement only when the player first arrives, or making decorative worker motion authoritative.

### Pillar 2 — Attention is the player's strategic resource

Being somewhere means not being elsewhere.

**Violation:** consequence-free instantaneous global intervention.

### Pillar 3 — Power without command

The wizard can be locally devastating but cannot issue direct economic or military orders.

**Violation:** RTS command mode.

### Pillar 4 — Economic causality creates stories

Economic shortages must create downstream effects that appear through workers, production, military capability and quests.

**Violation:** military units spawning independently of economy.

### Pillar 5 — Knowledge is interface

The player sees what they currently understand, not omniscient labels.

**Violation:** automatically exposing hidden identity and exact systemic values.

### Pillar 6 — History transforms rather than replaces geography

The same strategic board and production values persist across eras and cycles. Settlements, roads, ruins and infrastructure accumulate history even when their mechanical relevance changes.

**Violation:** unrelated maps every era.

### Pillar 7 — Failure usually becomes history

Lost wars, failed quests, destroyed settlements and NPC deaths remain valid game states.

**Violation:** making ordinary setbacks automatic Game Over conditions.

### Pillar 8 — Catastrophe is different

Only terminal catastrophe normally ends the run.

### Pillar 9 — Culture is an era-specific mechanical package

Culture means a collection of buildings and units. Factions may change culture packages when an era changes rather than preserving a permanent culture identity.

**Violation:** treating culture as an immutable faction essence that prevents era-specific redesign.

### Pillar 10 — Generated content never owns truth

All LLM-assisted dialogue and prose is produced offline, validated, written into game files and selected deterministically at runtime. Canonical mechanics and runtime facts belong to the simulation.

---

## 9. System invariants

**LOCKED user decisions, with DEFINED operational defaults where stated**

1. The player never directly commands workers or military formations.
2. Every accepted adjacent-node journey advances exactly one World Turn; a rejected journey advances none.
3. Wait advances one World Turn without changing the player's strategic node.
4. One rotating faction occupies the active seat per World Turn; every active faction occupying its seat once completes a World Round.
5. Every active faction drafts exactly one card after a completed World Round.
6. The first committed action producing 10 VP interrupts the current turn/round and begins era transition.
7. With multiple factions entering an era, all below 5 VP and one lowest-scoring faction collapse at its end; ties use the rule in §40.
8. A faction that began the era alone is not eliminated as its own lowest-scoring faction; it must split at that era's transition.
9. Non-splitting survivors upgrade their two highest theoretical-capacity sites. Normal splits use the top four sites in compact pairs.
10. Collapsed-faction settlement/road ruins have no mechanical effects and never reserve a site.
11. Other surviving settlements and their old buildings remain operational, but score no new-era VP until upgraded.
12. Living NPC identities, jobs unless changed, relationships and active quests survive era changes.
13. Geography and production numbers persist across eras and full cycles.
14. Catan goods and era-specific industrial resources are different resource namespaces and ledgers.
15. Dice generate only the five Catan goods at nodes, never the twelve industrial resources.
16. A finite industrial deposit belongs to a hex and resource layer; all extractors draw from that same deposit.
17. Each occupied node has a total capacity of 1–5 primary production buildings, not 1–5 per hex or per resource.
18. Every culture currently has access to all 60 distinct cross-terrain recipes/building types per era.
19. Industrial throughput and military production progress in Game Time at visited and unvisited nodes.
20. Worker animation/pathfinding cannot create, duplicate, withhold or destroy economic output.
21. Every ordinary worker has a persistent identity and job. A replacement worker receives a new identity.
22. Every cart and military unit is a persistent entity; cargo, casualties and building destruction have canonical consequences.
23. Strategic army travel occurs only on World Turns, up to two nodes on its faction's activation.
24. Local battle movement, range and terrain are mechanically real.
25. The wizard cannot be harmed by faction military. One successful destruction spell destroys any targeted local ordinary unit or building regardless of allegiance or era; rival wizards/hazards use the duel contract.
26. Support buffs stack and expire by Game Time; the exact magnitudes/durations are tunable.
27. Wizard/hazard duels freeze Game Time, strategic turns, production, buffs and other battles; their own duel clock continues.
28. A visit permits one successful catastrophe treatment per adjacent hex, at most three. Wait, menus, interior entry and save/load do not reset it.
29. Only terminal catastrophe normally ends the run.
30. Runtime gameplay is offline and never depends on an LLM.
31. Generated prose cannot invent canonical facts or apply arbitrary state writes.
32. Every mutable fact has one owner; an encounter may temporarily receive explicit ownership without creating a second competing state.
33. Wizard progression uses quest-awarded colours/slots and defined Aspect changes, not conventional XP levels.
34. The same commands, clock advances, definitions and recorded policy choices must replay deterministically.

---

## 10. Deliberate omissions

**DEFINED**
No:

- direct RTS unit orders;
- manual worker micromanagement;
- conventional settlement-management interface;
- compulsory main quest;
- global omniscient economic dashboard;
- requirement to save every NPC;
- universal quest markers;
- conventional grind-based enemy killing as the primary progression loop;
- simulation of every individual citizen's complete life;
- continuously simulated millennia between eras;
- online LLM dependency for canonical gameplay;
- requirement for thousands of mechanically unique combat systems;
- multiplayer in the current design;
- routine hunger/thirst survival meters;
- arbitrary resource exhaustion ending a faction's ability to function forever.

---

# VOLUME II — PLAYER EXPERIENCE

# PART III — CORE EXPERIENCE

## 11. Core experience

The player repeatedly:

- travels;
- notices;
- investigates;
- talks;
- interprets;
- decides what matters;
- solves local problems;
- explores dangerous spaces;
- fights occasional important magical duels;
- intervenes in autonomous battles;
- influences leaders;
- watches consequences propagate;
- leaves;
- later discovers what happened without them.

The mental activity is primarily:
**What is happening here? Why? Who wants what? Do I care? What can I change? What else will happen while I do this?**

---

## 12. Core gameplay loop

TRAVEL
→ OBSERVE A CHANGING PLACE
→ IDENTIFY PEOPLE / PROBLEMS / OPPORTUNITIES
→ INVESTIGATE
→ CHOOSE WHETHER TO INTERVENE
→ TALK / EXPLORE / CAST / DUEL / SOLVE
→ WORLD STATE CHANGES
→ TIME PASSES
→ CONSEQUENCES PROPAGATE
→ TRAVEL ELSEWHERE OR RETURN LATER

It remains interesting because the same actions occur against changing social, economic, political, technological and catastrophic contexts.

---

## 13. Secondary loops

### Dialogue

Observe → learn identity → conversation/check → choice → validated relationship, knowledge, policy or quest effect.

### Construction and trade

World Turn dice → five basic goods at producing nodes → local stock → cargo reservation → persistent cart → delivery → build/upgrade or trade.

### Industry

Era-specific resources → primary capacity and shared depletion → calculated processing flows → three factory production meters in Game Time → persistent individual military units.

Workers illustrate these flows; their navigation does not determine them.

### War

Industry produces units → autonomous groups gather → active-faction World Turn permits travel → local tactical battle or off-screen resolution → persistent losses/destruction.

### Catastrophe

Turn-based placement → cube accumulation/outbreak → economic disruption → bounded local wizard treatment or faction response → recovery or terminal limit.

### Dungeon

A real local problem → site → investigation/mechanisms/duel → validated consequence.

### Technology

Completed World Round → simultaneous single-card choices → unlock/archive → pass remaining hands → redeal after seven picks.

### Era

10 VP → immediate transition → collapse or sole-faction protection → optional/mandatory fission → core upgrades → continuing people, quests and legacy industry.

---

## 14. Long-term loop

```text
PREHISTORIC
→ ERA COMPETITION
→ GLOBAL ERA RESET

HISTORIC
→ ERA COMPETITION
→ GLOBAL ERA RESET

MODERN
→ ERA COMPETITION
→ GLOBAL ERA RESET

DYSTOPIAN FUTURE (current required path)
→ COLLAPSE
→ PREHISTORIC
→ NEW CYCLE
```

The game records completed cycles and has no fixed maximum cycle count. A later Utopian future branch remains architecturally supported but is POST-MVP.

Across a full Future → Prehistoric transition the following survive:

- strategic hex geography;
- each hex's production number/value;
- ruins;
- buried bunkers and structures;
- future artifacts;
- radioactive/contaminated zones where created;
- demon scars;
- myths carrying distorted memories of previous cycles;
- the wizard's complete memory.

Old roads may survive as landscape traces. Ancient AI systems or robots may survive where content rules choose to preserve them. These are supported possibilities rather than guaranteed outcomes.

---

## 15. Positive feedback

Strong factions can:

- control better resource geography;
- build larger economies;
- draft synergistic technologies;
- field stronger military;
- acquire more productive cities;
- reach 10 VP more quickly.

Runaway growth is constrained by:

- era ending at 10 VP;
- era reset;
- catastrophe;
- military losses;
- logistical complexity;
- potential faction fission;
- redistribution/new generation of finite resources.

---

## 16. Negative feedback

**DEFINED**

- Multi-faction era transitions eliminate weak factions and one lowest-scoring faction.
- A sole faction is protected from self-elimination and must split at the next transition.
- Voluntary fission considers geographic separation, military losses and durable quest/policy effects; the baseline policy is defined in §120.
- Shared finite deposits run down; catastrophe and real building destruction reduce capacity.
- Military losses must be replaced by real-time production.
- Only selected settlement cores upgrade automatically; legacy sites need a delivered construction upgrade before scoring again.
- Old units remain but are substantially outclassed by newer units.
- Waiting strengthens industry across the whole world, not only the player's preferred settlement.
- There is no hidden mana cost or worker-path obstruction penalty added to restrain the wizard.

These are balancing mechanisms to validate, not guarantees that every seed produces an evenly matched contest.

---

## 17. Failure cascades

Intended.
Example:
ALIEN ATTACK / DEMON INFESTATION / POLLUTION
→ RESOURCE SITE IMPAIRED
→ RAW INPUT FALLS
→ PROCESSOR IDLES
→ MILITARY PRODUCTION FALLS
→ BORDER DEFENCE WEAKENS
→ TERRITORY LOST
→ FURTHER RESOURCE LOSS
→ NPC CRISES

The player should be able to discover these causally.

---

## 18. Recovery

### Trivial

Failed conversation attempt, minor puzzle error, small battle loss.
Recovery is immediate or cheap.

### Costly

Destroyed infrastructure, military defeat, damaged relationship.
World must spend time/resources recovering.

### Lasting

Settlement destroyed, leader dies, faction loses territory, failed major quest.
These become history.

### Terminal

Era-specific catastrophe crosses the terminal-loss condition.
Wizard dies.
Return to main menu.
Manual save reload remains possible.

---

# PART IV — PLAYER CONTROL

## 19. Player authority

### Directly controls

- wizard movement;
- interaction;
- investigation;
- dialogue response;
- inventory;
- spell use;
- personal duel actions;
- dungeon mechanisms.

### Indirectly influences

- ruler policy;
- faction strategic priorities;
- war;
- trade;
- diplomatic hostility;
- catastrophe response;
- settlement outcomes;
- historical development.

### Observes

- worker behaviour;
- economic logistics;
- military movement;
- faction construction;
- technology drafting outcomes;
- wars away from the player's current location.

### Cannot directly control

- worker assignment;
- army orders;
- faction construction queue;
- technology choice of another faction;
- strategic ownership;
- catastrophe spread.

---

## 20. Complete player verb list

- move locally;
- travel to an adjacent strategic node;
- wait one World Turn;
- observe, inspect and examine;
- approach, talk, choose and walk away;
- enter and exit;
- pick up, drop, use and give items;
- equip an artifact/focus;
- combine specifically supported objects;
- activate, open and close;
- push/pull puzzle objects;
- select a spell and target;
- destroy a unit or building;
- apply a support buff;
- challenge a wizard/hazard to a duel;
- investigate and solve;
- influence, threaten, persuade and ask;
- receive rewards;
- save and load;
- review knowledge and history.

Wait is a deliberate contextual control with one activation per press; it is not an automatic repeat action.

---

## 21. Input philosophy

**LOCKED**
The world is operated primarily through direct movement and semantic labels.
Click/tap:
TARGET OUT OF INTERACTION RANGE
→ OBSERVE

TARGET IN INTERACTION RANGE
→ CONTEXTUAL INTERACTION

The player should not need a strategy-game control interface to understand the simulation.

---

## 22. Selection and targeting

Semantic labels select NPCs/workers, individual units/carts, buildings, resource sites, roads, objects, puzzle mechanisms, dungeon entrances, hazards and landmarks. A formation label inspects the group and its members; it does not make one spell destroy the whole formation.

Observation is knowledge-filtered. Unknown identity does not prevent selecting a visible unit/building. World destruction works at the current node regardless of friendly, neutral or hostile affiliation; it cannot target a remote strategic-map marker.

A worker/civilian represented as an ordinary world unit is also destructible and can die. Rival wizards and duel-capable hazards belong to the distinct duel-actor contract. The player wizard is not a self-destruction target.

Touch and mouse use the same semantic action. Invalid/stale targets produce feedback without costs or time advancement.

---

## 23. Camera and viewpoint

**DEFINED**

The local game uses a **2D top-down sprite perspective in a Pokémon-like presentation style**.

The camera is player-centred and should support:

- readable semantic labels;
- clear tile/world navigation;
- seeing local workers, vehicles and battles;
- compact settlement and dungeon readability;
- no RTS strategic command zoom.

Rotation is not required. Start with a player-centred integer 4× scale and optional 3×/5× zoom, with responsive framing and separately scaled touch labels. These are tunable prototype values, not undecided behaviour.

---

# VOLUME III — WORLD AND SIMULATION

# PART V — SPACE

## 24. World representation

**DEFINED**
Strategic world:

- 19 Catan-style hexes;
- axial hex coordinates;
- six corner nodes per hex;
- shared node topology;
- edges connecting nodes;
- roads on edges;
- settlements/cities on nodes.

Local world:
Each significant strategic node may project into a detailed explorable settlement, wilderness area, battle area or dungeon space.

---

## 25. Scale

Strategic nodes are abstract geographic locations.
Local projected spaces expand those locations into player-scale environments.
Strategic travel compresses distance and time.
The player walking across a local settlement does not represent the same time scale as moving between strategic nodes.

---

## 26. Terrain

**DEFINED**

Terrain types remain Woodland, Clay Mountains, Ore Mountains, Fields, Grazing Land and Desert. Every hex retains its geometry and production number permanently.

A settlement node touches at most three hexes and can potentially access up to six era-specific industrial resources. Actual extraction is limited by the node's total 1–5 primary sites (§80).

The separate Catan construction-good mapping is:

| Terrain | Catan good from a matching roll |
|---|---|
| Woodland | Timber |
| Clay Mountains | Brick |
| Ore Mountains | Ore |
| Fields | Grain |
| Grazing Land | Wool |
| Desert | None |

Desert still has an industrial production number and its two industrial resources; it does not become an inert terrain merely because it yields no Catan good.

**Generation default:** 19 hexes with terrain counts 4 Woodland, 3 Clay Mountains, 3 Ore Mountains, 4 Fields, 3 Grazing Land and 2 Desert. Use the number multiset 2,3,3,4,4,5,5,6,6,8,8,9,9,9,10,10,11,11,12, assigned with seeded shuffling. Validate initial placements and regenerate deterministically when the configured starting factions cannot receive two distance-legal sites. Generation attempts have a bounded fallback to a validated fixture board.

Terrain affects industry, construction goods, local appearance, strategic value and quest/dungeon themes.

---

## 27. Occupancy

Strategic:

- hexes may contain catastrophe state;
- nodes may contain settlements, units, dungeon sites and conflicts;
- edges contain roads/routes.

Multiple factions can contest strategic locations during battle.
Local spaces use normal physical collision.

---

## 28. Movement

Local movement is direct and continuous. Strategic travel is along one node edge per player journey, with or without a constructed road. Roads constrain carts and economic expansion, not the wizard's ability to explore.

A committed adjacent-node move advances exactly one World Turn. Wait advances the same turn without changing node. Re-entering an interior, loading a save or returning from a duel is not ordinary strategic travel.

Disengaged formations can move at most two node edges on their faction's active turn, stopping at the first hostile engagement. Units produced during stationary Game Time may move and fight within their current local battle, but may not change strategic node. Newly produced units join the next eligible activation, never receive a retroactive move.

Carts move one road edge per World Turn under §87. Wizard and military transit are exempt from catastrophe's civilian transport prohibition.

---

## 29. Orientation

Local facing may matter for:

- movement animation;
- puzzle mechanisms;
- visual combat.

Strategic facing is abstract.

---

## 30. Geography as gameplay

Important decisions arise from:

- resource adjacency;
- road connection;
- travel distance;
- strategic junctions;
- settlement productivity;
- war fronts;
- where the player currently is;
- how far simultaneous crises are from the player.

---

# PART VI — TIME

## 31. Time model

**LOCKED mixed-time model; DEFINED clock and pause defaults**

### Game Time

Game Time is elapsed unpaused play time. It advances industrial flow calculation, finite extraction, military production, timed buffs, local faction combat and timed puzzle mechanisms. Industry runs for every occupied node, not just the rendered one. No real-world time accrues while the application is closed.

Godot supplies fixed clock advances; Python records Game Time as integer milliseconds and advances industrial accounting in 100 ms quanta. Rendering frame rate is not an economic multiplier. Local combat uses a fixed simulation step and reports its clock position.

Ambient speech and ordinary exploration allow Game Time to run. A formal dialogue choice, inventory/Chronicle/settings screen, pause menu, loss of focus, save/load barrier or bridge failure pauses it. This preserves unhurried reading without turning all street conversations into production exploits. Pausing never grants a strategic turn.

### Wizard-duel time

A wizard/hazard duel globally pauses Game Time and all strategic activity. Production, carts, other battles, timed buffs and puzzle hazards do not advance. The duel's own input/casting clock runs, so the duel remains playable. On completion, apply its result once, release the pause and resume the saved clocks without catch-up time.

### World Turn

One accepted adjacent-node journey or explicit Wait advances exactly one World Turn. Real-time seconds alone never roll Catan dice, move strategic armies/carts, draft technologies or spread catastrophe.

Each turn has one rotating active-faction seat. All factions receive eligible Catan production and may finish delivered construction; only the active faction initiates new strategic orders/trade/diplomacy and moves its disengaged military forces up to two nodes. The complete transaction is in §189.

Wait changes no location and grants no artificial seconds of military production. It does not reset the current catastrophe-treatment visit. Menu time and repeated button-down frames never count as extra Waits.

### World Round

A round records the faction IDs scheduled at its start. Each gets one active seat. The remaining valid seats complete in order; factions eliminated during play are skipped. At round end each still-active faction drafts exactly one card. Era transitions discard an unfinished old-era round and start a new one without an extra draft.

### Era

The first committed VP-changing action to reach 10 VP interrupts further old-era actions immediately. A local battle/building destruction may therefore affect VP between World Turns. Era duration is not a fixed real-time timer.

---

## 32. Time pressure

Presence constrains where the wizard can intervene. Travel and Wait advance strategic crises; Game Time grows military forces throughout the world and advances local fighting.

A player may spend a long time exploring one location without a new catastrophe placement. This is intentional, not an unnoticed simulation bug. The treatment-per-visit rule prevents clearing every cube from the same hex without further strategic movement. Waiting in one location does not generate a free local military advantage because all functioning settlements produce in the same Game Time.

Formal reading/menus and wizard duels pause Game Time. The game does not force dialogue decisions under a global stopwatch.

---

## 33. Timed systems

| Clock | Systems |
|---|---|
| Game Time | Industrial throughput, extraction/depletion, military production progress, local battle movement/attacks, buff expiry, timed puzzle hazards |
| World Turn | Catan rolls, construction/trade orders and delivered completion, cart travel, active-faction strategic movement, diplomacy, catastrophe placement, turn-based quest deadlines |
| World Round | One technology draft per active faction; longer policy durations |
| Duel clock | Mastermind cast windows, rival reasoning/casts and duel result |
| Immediate committed event | Knowledge, item transfer, dialogue effects, building/unit destruction, quest transitions, VP threshold and era transition |

Every duration declares its clock. Pause/resume and save/load preserve each clock and remaining duration. There is no recovery-time penalty for an ordinary duel loss.

---

# PART VII — INFORMATION

## 34. Visibility

Things physically visible can still remain unidentified.
Seeing an entity does not automatically reveal canonical identity.

---

## 35. Hidden information

May include:

- NPC identity;
- intentions;
- faction plans;
- exact production values;
- exact army strength;
- catastrophe severity;
- technologies not observed;
- hidden dungeon mechanisms;
- conversation conditions;
- future historical consequences.

---

## 36. Memory

Knowledge persists after discovery.
Semantic labels improve with recognition.
Example:
STRANGER
→ SOLDIER
→ IRONMOOT SOLDIER
→ CAPTAIN EDRAN
→ CAPTAIN EDRAN — 7TH COMPANY COMMANDER



---

## 37. Information as gameplay

The player decides based on incomplete interpretation.
Internal faculties, NPC testimony and observation may provide competing interpretations rather than objective answers.

---

# PART VIII — PERSISTENCE

## 38. Persistent world state

Within and across ordinary era transitions, preserve the IDs and state of surviving roads, settlements, buildings, industrial layers, local stocks, carts/cargo, units, NPCs, relationships, knowledge, quests, dungeons and puzzle mechanisms.

Era transition changes political status, scoring eligibility, current culture and selected core definitions. It does not regenerate an inhabited location from scratch or discard its people.

History may be summarised for storage, but summaries cannot delete live references or change remembered facts. Destruction, faction collapse and full-cycle reseeding have explicit dispositions in §40.

---

## 39. Persistent character state

The wizard retains:

- complete memory across eras and full historical cycles;
- discovered knowledge;
- relationships where the relevant character still exists;
- quest-earned spell colours;
- quest-earned spell slots;
- important inventory/artifacts according to item-specific persistence rules;
- completed-cycle history.

The wizard does not gain conventional character levels. The principal long-term mechanical progression currently defined is increased Mastermind/magic complexity through additional colours and slots awarded by quests.

---

## 40. Persistent strategic state

**LOCKED continuity; DEFINED transition algorithm**

### Trigger, ranking and collapse

After each atomic VP-changing action, if a faction reaches 10 VP, freeze ordinary scheduling, snapshot the old era and perform one transition transaction. VP is scored under §104.

Rank each settlement by **theoretical industrial military capacity**: the sum of the three factory rates with local deposits available, current installed facilities and permanent technologies, ignoring temporary depletion, catastrophe, combat damage, buffs and blocked carts. Use §82's allocation rules; include settlement/city capacity multipliers. Ties use stable settlement ID. This rank is computed once before transition.

With two or more factions at era start, every faction below 5 VP collapses. Also collapse exactly one lowest-VP faction; equal VP is broken by lower total theoretical settlement capacity, then stable faction ID. This does not eliminate the winning faction when it is the only faction.

If the era began with one faction, exempt it from the lowest-faction elimination rule and require fission at this transition. If a multi-faction transition leaves one survivor, that survivor enters the next era alone and is marked for mandatory fission at its next transition.

### Surviving factions and core upgrades

A non-splitting survivor upgrades its two best sites, or all of its sites if fewer than two remain. A normal split uses its four best sites. Of the three ways to pair four sites, choose the smallest sum of graph distances within the pairs; break equal sums by sorted site IDs.

Living NPCs—including ordinary workers—retain their IDs, relationships and active quests. There is no automatic ageing, death, generational replacement or quest cancellation at an era boundary.

All non-core surviving buildings, workers, units and stocks remain operational under their own era definitions. Legacy factories can produce legacy units. New-era units are substantially stronger (§60). Old settlements score zero current-era VP until upgraded. Newly upgraded inherited cores begin as settlements worth 1 VP, including sites previously classed as cities.

### What an upgraded core starts with

An inherited core needs a working new-era economy, not an impossible requirement to manufacture resources using factories it does not yet possess.

The transition therefore:

- upgrades its settlement centre and warehouse in place, preserving site IDs;
- adapts its existing 1–5 primary sites to the new-era resource layer, preserving building IDs, positions and workers;
- provides the new era's three military factory sites and the minimal available processors needed for their selected valid local input routes;
- preserves additional legacy processors, units, items, cargo and stocks;
- grants each core one explicitly recorded starter package of 2 timber, 2 brick, 1 wool and 1 grain at its warehouse, once per transition ID;
- resets new-era factory production meters to zero; it does not grant an instant army.

The five Catan goods are era-independent and remain useful. Legacy industrial materials retain their era and feed compatible legacy recipes. There is no hidden sixth construction currency or requirement for an imaginary new-era version of wool.

Newly founded settlements receive their basic civic/warehouse/industrial facilities as part of their settlement construction cost; enhancements and extra processors follow §101. Core grants and setup packages are explicit exceptions to normal delivery costs.

### Fission ownership and too few sites

Assign each remaining settlement to the successor with the nearest core, measured by graph distance; ties use successor ID. Workers, resident NPCs, buildings and stocks stay with their sites. Assign roads by nearest successor core using the smaller endpoint distance; carts retain cargo and are retargeted only through a validated delivery change. Units follow their home site's successor, or the nearest core if homeless. Both successors inherit the parent's research history and external relations; they begin neutral and trade-permitted toward one another.

Voluntary fission requires four sites and room under the initial six-faction limit. Mandatory sole-faction fission overrides the four-site requirement: with two or three sites, give each successor at least one existing core; with one site, seed a second successor at the nearest legal empty node. If no distance-legal node exists, an emergency successor may use the nearest empty node as an explicit one-time distance-rule exception. A sole faction capable of reaching 10 VP normally has enough sites, so this is a recovery edge case. Do not invent four duplicate settlements.

A faction with no remaining settlements is dissolved during ordinary play; its living civilians survive as displaced NPCs. If all factions disappear, the next World Turn seeds two new factions at legal empty sites with the standard starting package. This is recovery, not Game Over. The wizard is never forced to kill time until an impossible era threshold.

### Collapsed factions

Remove their settlements, operational buildings, military organisations and road ownership. Disband their military units, retire their economic stocks/cargo from active ledgers, and record the loss once. Retain living civilian NPCs as displaced people; assign a reachable surviving settlement or a neutral local camp without consuming a strategic settlement site. Their quests continue or use the invalid-target branches in §141.

Collapsed settlement and road ruins are **inert scenery**: no collision, VP, production, loot, transport capacity, building cost, eligibility restriction or reserved plot. A new settlement/road footprint simply replaces overlapping ruin art. Plot-relevant bunkers/dungeons are separately defined entities, not mechanical rewards hidden in these inert ruins.

### Full Future → Prehistoric cycle

This is an explicit political reseeding event: create six new factions where the main-game board permits, using the normal validated setup procedure. Retire previous faction memberships and military organisations; retain people's identities and active quests and reassign their jobs/affiliations by location. Previous structures and units become inert legacy records/scenery unless a separately authored relic rule keeps a particular non-faction entity active. Thus a future army is not carried into the next Prehistoric VP contest.

Preserve geography, production numbers, wizard memory/progression, knowledge, living NPC identities, relationships, active quests, inventory and persistent dungeon/puzzle state. Artifacts, bunkers, myths and scars survive through explicit entity rules. Existing finite layers remain in history; each new cycle receives a new current resource layer. Catastrophe rollover follows §166. Full-cycle political reseeding is distinct from ordinary era continuity.

---

# VOLUME IV — ACTORS AND OBJECTS

# PART IX — ENTITY MODEL

## 41. Entity categories

- Wizard/player.
- Named NPC.
- Generated NPC.
- Faction leader.
- Worker.
- Soldier.
- Champion/hero.
- Rival wizard.
- Military formation.
- Vehicle.
- Building.
- Settlement.
- Resource site.
- Ware.
- Shipment.
- Road.
- Item.
- Spell effect.
- Catastrophe entity/state.
- Dungeon.
- Puzzle mechanism.
- Landmark.
- Technology.
- Historical fact.
- Semantic entity.

---

## 42. Entity lifecycle

### NPC / worker

Create stable identity → assign role/workplace → interact and acquire history → optionally change role through a quest → survive era changes → die/disappear only through a specific event. A vacated job receives a new worker ID; the old person is not overwritten.

### Building

Validate construction → reserve/deliver costs → build → contribute capacity → damage/repair/upgrade/destroy. Era-core upgrades preserve identity and change definition; legacy buildings remain until an explicit disposition.

### Unit / formation

Factory meter completes → create persistent unit ID → assign autonomous group → wait for strategic activation → move/fight → preserve individual casualties, buffs and health. A formation groups unit IDs; it does not replace their identities.

### Cart

Reserve cargo → load → persist route and position → advance on World Turns → deliver once, reroute, cancel or be destroyed. Cargo cannot also exist as spendable source stock.

### Catastrophe

Place cube → intensify/outbreak → affect economy/transit → remove through validated treatment or trigger terminal loss.

---

## 43. Entity state

Every persistent entity has a stable ID, kind, creation cycle/era, current location, owner or affiliation, active/disposition state and version. Records add only relevant fields; a road does not require NPC personality fields.

Separate building definition ID from building instance ID, political faction ID from culture-package ID, and real entity ID from disposable visual-node ID. Save job assignments, worker identity, individual military health/buffs, cart cargo, production progress, quest references and local edits. Never identify a person by display name or a building by its current array index.

Knowledge and labels reference entity IDs. Reprojection cannot recreate a destroyed building, replace a named worker or erase a completed interaction.

---

## 44. Ownership and allegiance

Political entities belong to active factions.

The game begins a cycle with six political factions, but collapse and fission can change the number of factions between eras.

Relationships can include:

- allied;
- trading;
- neutral;
- hostile;
- war;
- embargo/non-trading policy.

Faction strategic AI can decide when to treat another faction as hostile or allied and can propose alliances or trade relationships.

The player belongs to no ordinary faction.

---

# PART X — CHARACTERS AND PARTY

## 45. Character model

Named characters differ through:

- culture;
- era;
- occupation;
- personality;
- goals;
- relationships;
- knowledge;
- institutional power;
- dialogue voice;
- personal history.

LLM generation supplies large-scale characterisation from structured inputs.

---

## 46. Character creation or recruitment

The player wizard is predefined.
There is no conventional recruitable party.
NPCs are generated/authored as inhabitants of the simulation.

---

## 47. Attributes

**DEFINED**

The wizard has seven Aspect scores, unlocked spell colours/slots, knowledge, relationships, inventory and historical state. No conventional HP, mana, stamina, hunger or XP level is introduced.

Faction military cannot damage the wizard. Wizard/hazard duels have their own win/loss rules. Puzzle hazards use explicit reset, displacement or quest consequences rather than a hidden generic health bar.

---

## 48. Skills

**DEFINED default seven Aspects**

| Aspect | Domain | Internal voice |
|---|---|---|
| Reason | Evidence, logic, causal explanation | Precise and questioning |
| Empathy | Feelings, care, understanding others | Attentive and humane |
| Authority | Institutions, legitimacy, persuasion through standing | Formal and assured |
| Guile | Deception, bargaining, concealed motives | Wry and suspicious |
| Resolve | Commitment, courage, resisting pressure | Direct and steadfast |
| Curiosity | Exploration, experimentation, asking further questions | Restless and inquisitive |
| Wonder | Magic, symbolism, imagination and unusual connections | Evocative but fallible |

Each score is an integer 0–5, initially 1. Significant authored quest/choice effects may change a score by ±1, clamped to the range. Award each change once per effect ID; repeating dialogue cannot farm it. There is no generic XP pool.

Checks are deterministic: Aspect score + explicit evidence modifiers + a clamped relationship modifier is compared with the authored threshold. Defaults: 2 easy, 4 demanding, 6 exceptional; evidence modifiers normally 0–2, relationship modifier −1/0/+1. Choices and failures have authored consequences. A failed attempt may be retried only after relevant state changes, not by reopening the same conversation.

Passive comments read knowledge-filtered context. An Aspect's interpretation is not an authoritative fact and cannot leak hidden identity. Personality, choice filtering and internal voice can be developed incrementally against these stable seven definitions.

---

## 49. Character progression

**LOCKED AT CORE LEVEL**

The wizard does not use conventional XP levels.

Mechanical magical progression comes from quests that increase:

- the number of spell colours available;
- the number of slots available in Mastermind-style magical encounters.

Increasing colours and slots also increases duel/hazard complexity. Other progression such as knowledge, relationships and historical memory is persistent but does not need a conventional numerical level system.

---

## 50. Party structure

**NOT APPLICABLE** as a conventional controllable party.
Temporary companions may accompany the player but remain autonomous NPCs.

---

## 51. Death and replacement

NPCs and military units can die through explicit events; ordinary era transitions do not kill them. Worker replacement preserves the departed person's record and creates a separate new person for the vacant post.

The wizard cannot suffer battlefield defeat from faction units. There is no local-military-overwhelm teleport rule.

Losing a wizard/hazard duel applies its defined consequences once and returns the wizard to the last surviving friendly settlement. Friendly means neutral-or-better settlement relation to the wizard, regardless of faction-to-faction war. If it no longer qualifies, choose the nearest non-hostile settlement; if none exists, use the nearest catastrophe-free wilderness node, then the least-affected node. Recovery arrival costs no World Turn and grants no production catch-up. On returning to a previously visited node within the same turn, retain its existing catastrophe-treatment ledger.

Only the global catastrophe loss condition ordinarily kills the wizard and ends the run.

---

# PART XI — ITEMS AND INVENTORY

## 52. Item model

Categories:

- quest objects;
- puzzle tools;
- magical artifacts;
- keys/access objects;
- historical objects.

Avoid excessive conventional loot.

---

## 53. Inventory model

**DEFINED**

Use a simple persistent inventory with no weight or encumbrance limit. Stack identical fungible objects; preserve unique IDs for artifacts, keys with distinct uses and quest objects. Transfers are atomic and must not duplicate an object.

Mandatory quest/puzzle objects have an explicit recovery or alternate-outcome rule. The wizard's personal inventory is not a substitute for faction construction stock or shipment logistics.

---

## 54. Equipment

**DEFINED MVP default**

Two optional equipment slots: one magical focus and one artifact. Quest/puzzle tools can be used from inventory and need no equipment slot. Protective clothing is presentation unless an item has an explicitly supported effect.

Equipment does not grant conventional armour against faction military because the wizard is already immune. Additional slots are post-MVP content extensions, not required engine behaviour.

---

## 55. Object interaction

Objects may be:

- collected;
- inspected;
- used;
- combined where specifically supported;
- given to NPCs;
- placed into puzzle mechanisms.

---

## 56. Persistent physical objects

Important dropped objects retain their instance ID, area and local position across visits, saves and ordinary era changes. When a building upgrade changes navigation, move stranded important objects to the nearest accessible point while recording the relocation; do not silently delete them.

Portable quest objects, artifacts and keys survive full cycles by default. Temporary consumables disappear only when actually consumed. A destroyed/retired location rehomes required objects to its replacement accessible site or activates the quest's defined alternative route.

---

# VOLUME V — CHALLENGE SYSTEMS

# PART XII — COMBAT

## 57. Purpose of combat

Combat exists at two scales.

### Personal duel

Tests deduction and magical understanding.

### Strategic warfare

Creates world change, political pressure and situations the wizard can choose to influence.
Combat is not primarily a source of XP.

---

## 58. Combat flow

### Personal wizard/hazard combat

The existing Mastermind-derived system handles rival wizards and duel-capable demons, aliens, hostile AI/cyborg avatars and magical hazards. Pollution requires cleanup through faction/quest actions.

Starting a duel pauses the whole world's Game Time and World Turns. The duel's own clock continues. On victory or loss, apply its validated outcome once and resume the world. Ordinary loss is non-terminal (§51).

### Strategic and local faction warfare

Each of a node's three military factories accumulates production progress in Game Time and creates an individual persistent unit on completion. Autonomous leadership groups these units.

Disengaged forces may travel up to two nodes on their faction's active World Turn and stop on meeting opposition. No strategic travel occurs during stationary real-time play.

At the player's node, combat is a live top-down tactical encounter: actual positions, movement, collision/navigation, line of sight, range, attack cooldowns and terrain matter. The wizard may destroy or buff individual targets but cannot issue orders.

At other nodes, or when the player leaves a battle, resolve the remaining engagement from its current unit/building state using §60. Preserve casualties, damaged buildings, completed production and active modifiers. Leaving is not a reset and never recreates the original armies.

---

## 59. Positioning

Local battles use actual two-dimensional positions, passable terrain, cover, line of sight, attack range and movement speed. Each unit has its own position and target. Buildings occupy persistent footprints; destroying one removes its collision and actual capacity.

Strategic coordinates identify which node a force occupies. A formation is a grouping/order convenience over individual unit IDs, not a substitute combatant.

Local worker routes are presentation. Military positioning and routes during a local battle are gameplay. The two must not share the rule that physical obstruction is economically irrelevant.

Wizard/hazard duels retain their existing deduction-focused layout.

---

## 60. Attack resolution

**DEFINED baseline; numerical constants TUNABLE**

### Wizard/hazard duel

Retain the existing Mastermind feedback/ruleset machinery. The initial ruleset is four slots, six colours, repeats allowed and ten casts per side; existing configurable cast windows remain. Quests can increase colours/slots. Defeat follows §51.

### Wizard destruction

One valid destruction spell destroys any local **ordinary unit (military, worker/civilian or cart) or building**, irrespective of owner, allegiance, health or era. A target must exist at the current strategic node and have a currently observed/selectable local representation. There is no hostile-only gate, faction immunity, damage roll, mana cost or damage cap. A 0.25-second visual cast/recovery interval prevents duplicate input; it is presentation/input pacing, not an economic cost.

Special rival wizards and duel-capable catastrophe manifestations use the duel contract, not the faction-unit class. Ordinary worker/civilian units are also valid destruction targets; their deaths update their real identity, job and quests. Rival wizards and magical hazards remain duel actors. Building destruction alone displaces civilians by default rather than killing everyone nearby.

Destroying a real building removes its corresponding capacity and effects immediately. Destroying a settlement centre removes political settlement ownership under §104. A cart loses its actual cargo. Repeated commands against an already destroyed ID are harmless no-ops. Harm to a faction's assets changes its opinion and quest state even though it cannot injure the wizard.

### Unit combat

Use shared data for maximum health, attack damage, attack period, movement speed, range, armour and cover. For each hit:

damage = max(1, round_half_up(attack × era_multiplier × attack_modifiers × (1 − cover_fraction) − armour)).

Base cover is 0 or 0.25 according to terrain; modifiers and caps are explicit data. Range and line of sight gate attacks; deterministic target selection uses nearest eligible enemy, then lowest current health, then unit ID. Simultaneous-step damage is gathered before casualties are applied, so iteration order does not grant extra attacks.

Working era multiplier: 1 / 10 / 100 / 1000 for Prehistoric / Historic / Modern / Future health and attack. Apply it once, before buffs; this makes old units strongly outclassed without deleting them. Legacy units do not upgrade just because their faction does.

Initial unit archetypes (base armour is zero unless a definition supplies another value):

- skirmisher: 60 health, 10 attack, 1.2-second period, range 4 tiles, speed 2.5 tiles/second;
- line fighter: 100 health, 15 attack, 1-second period, range 1 tile, speed 2;
- heavy fighter: 180 health, 25 attack, 1.5-second period, range 1 tile, speed 1.4.

These numbers are a working baseline, not a claim of proven balance.

### Buffs

Support effects stack additively by effect type. Each application has its own ID and expiry. Initial effects grant a temporary shield worth 25% of era-adjusted maximum health, +25% attack frequency, or +1 tile attack range for 30 seconds of Game Time. Cap total remaining shield at twice maximum health, attack frequency at 3× its unbuffed value, and extra range at +4 tiles. New shield grants are clipped to the available cap. Damage consumes shield points in earliest-expiry order before canonical health; shield expiry discards only unused shield points and cannot kill the unit. Buffs do not heal canonical health or change base armour. Save shield balances and all remaining durations. Duels/menus pause them.

### Off-screen/departure calculation

Python resolves a frozen participant snapshot with deterministic 0.25-second combat steps, using remaining health, attack cooldown, current position/range where present, terrain/cover and currently active buff modifiers. Units approach to range according to speed; unreachable opposing groups produce a stalemate. Damage uses the same shared data/formula. No new production or reinforcements enter during this instantaneous calculation.

The simulated combat steps order attacks; they do not advance global Game Time or grant industrial production. Buffs active at handoff are held constant for this calculation and keep their original Game-Time expiry afterward. This is an explicit off-screen approximation, not a claim that attended and unattended micro-positioning produce identical casualties.

End when opposition is defeated, a side commits to withdrawal, or 120 simulated combat seconds elapse. A timeout is a saved stalemate, not an invented victory. Re-evaluate a stalemate only on a new strategic turn or material state change. Default withdrawal occurs when a side's remaining effective health is below 25% of its entry total and a passable friendly adjacent node exists. Mark its survivors as withdrawing at the current node; they cease the current engagement and cannot capture the site or start another attack. Execute their retreat to the reserved adjacent node on their next legal movement activation, revalidating the route then. If the route is no longer legal, choose another eligible friendly neighbour; if none exists, return them to contested status. A fresh enemy attack can engage withdrawing units normally. Withdrawal never grants an immediate inter-node move. If the threshold is reached without any eligible retreat route, the side fights on.

When control changes between Python and Godot, preserve unit IDs, health, positions, casualties, buffs and building damage. Compare conservation and continuity, not exact equality between the two combat models.

---

## 61. Weapons and attack types

Generated from era + faction + technology + unit archetype.
Large full-game catalogue expected.
Mechanical archetypes should be far fewer than named unit profiles.

---

## 62. Health, injury and death

Every military unit has its own saved health and alive/destroyed state. A formation's strength is derived from its surviving members. Buildings have health for military attacks, while a wizard destruction spell bypasses it.

The wizard has no faction-combat health bar and is immune to faction military damage. Wizard/hazard duels can still be lost under their deduction rules, and terminal catastrophe still ends the run.

Civilian NPC death requires an explicit event. Building destruction displaces its worker NPCs by default; it does not automatically kill every person visually standing nearby.

---

## 63. Combat resources

The wizard does not currently require a separate conventional mana/ammunition economy.

Personal magical capability is constrained by:

- colours unlocked through quests;
- number of slots unlocked through quests;
- being physically present at the relevant node.

Military forces are constrained by the economic resources required to manufacture and replace units.

---

## 64. Combat asymmetry

Military asymmetry is produced by the current era's culture package, technology cards, available processed resources and unit mix.

A culture package is a collection of buildings and units rather than an immutable civilisation identity. A surviving political faction can therefore use a different unit/building culture in a later era.

Technology upgrades for an era are shared/universal definitions even though factions may draft different subsets of them.

---

## 65. Combat failure and retreat

Autonomous military forces retreat under §60 or lose units/buildings. Their defeats remain canonical history.

The wizard is never defeated or knocked out by faction military. They may leave a local battle whenever movement permits; its remainder is calculated from current state.

A lost wizard/hazard duel applies its quest/world consequence and returns the wizard under §51, with no recovery timer or extra World Turn. Only terminal catastrophe normally produces Game Over.

---

# PART XIII — ABILITIES / MAGIC / SPECIAL ACTIONS

## 66. Ability model

Magic has two distinct contracts.

**Duel/hazard magic:** Mastermind colours and slots challenge rival wizards and duel-capable catastrophe entities. Pollution is not a magical duel.

**World/battlefield magic:** a destruction spell destroys any selected local unit, cart or building regardless of allegiance or era; support spells add timed stacking modifiers to military units. Range is the local observed/selectable target area, not global strategic targeting.

Destroying buildings changes actual industry, storage, ownership and quests through validated effects. Magic never creates direct economic or army orders.

For catastrophe, one successful duel removes one cube from one adjacent hex and consumes that hex's allowance for the current node visit. Up to three different adjacent hexes can be treated. See §166 for save/load, Wait and multiple-cube details.

---

## 67. Acquisition

**DEFINED**

Quest completion is the primary progression source for magic.

Quests can award:

- additional magical colours;
- additional spell/Mastermind slots.

These increase the player's available capability and the complexity of later wizard/hazard duels.

No separate conventional spell-skill XP tree is currently required.

---

## 68. Costs and constraints

Presence and information are the primary constraints. There is no mana, reagent or conventional spell-skill XP economy.

World destruction is available against every local unit/building without allegiance gating. Support buffs stack within §60's numerical caps and expire in Game Time. Faction military cannot harm the wizard.

Catastrophe treatment is limited to one success per adjacent hex per visit, not an arbitrary mana pool. Wait advances the world but does not renew that visit. A wizard duel pauses the world without awarding production or strategic movement during its duration.

No additional spell cost may be introduced silently as a balancing shortcut; a change would require a deliberate later design revision.

---

## 69. Combination and experimentation

Use the existing Mastermind combination rules for duels and a small explicit set of world effects for the MVP.

Offensive colours can differ visually while sharing the same unit/building destruction result. Support colours use the defined protection, attack-frequency and range buffs. No general elemental-combination engine is required.

Era changes do not change magical deduction rules. Additional effects are data-driven only where their underlying mechanics already exist.

---

# PART XIV — SURVIVAL

## 70. Survival pressures

Traditional hunger, thirst, sleep and temperature are **NOT CORE**.
World catastrophe is the major survival pressure.

---

## 71. Interaction between survival systems

**NOT APPLICABLE** beyond health/magic/catastrophe unless future testing demonstrates a need.

---

# PART XV — PUZZLES AND SYSTEMIC PROBLEMS

## 72. Puzzle philosophy

Puzzles should reward:

- observation;
- spatial reasoning;
- learned mechanism grammar;
- contextual knowledge.

Avoid arbitrary riddles detached from the world.

---

## 73. Puzzle primitives

- switches;
- pressure triggers;
- keys/access objects;
- item receptors;
- timed mechanisms;
- sequences;
- movable objects;
- doors/gates;
- hidden passages;
- spatial orientation;
- environmental transformations;
- dialogue information.

---

## 74. Puzzle grammar

SIMPLE PRIMITIVE
→ TWO-PRIMITIVE COMBINATION
→ SEQUENCE / SPATIAL DEPENDENCY
→ MULTI-ROOM SYSTEM
→ ERA-SPECIFIC PRESENTATION

The underlying logic can be reused while visual context changes.

---

## 75. Puzzle fairness

Mandatory puzzles must contain enough information to infer a solution.
Faculty observations and NPC information may provide secondary clues.

---

## 76. Failure, reset and recovery

Mandatory puzzle errors must normally be recoverable.
Permanent consequences are acceptable when they open another valid route.

---

## 77. Soft-lock prevention

Required puzzle items may not be permanently destroyed without an alternative completion state.
Automated quest/puzzle validation required.

---

# VOLUME VI — ECONOMY AND INDIRECT SYSTEMS

# PART XVI — RESOURCES

## 78. Resource taxonomy

**LOCKED**

The tables below describe industrial resources only. They are distinct from the five dice-produced Catan construction/trade goods.

Every strategic terrain hex supplies exactly two industrial raw resources for the current era:

- one finite resource;
- one renewable resource.

A settlement can touch at most three hexes and therefore directly access at most six raw resources: three finite and three renewable.

### Prehistoric era

| Area | Finite resource | Renewable resource |
|---|---|---|
| Woodland | Hunted boar | Foraged berries and nuts |
| Clay Mountains | Surface clay | Spring water |
| Ore Mountains | Flint | Mountain herbs |
| Fields | Wild grain | Foraged food |
| Grazing Land | Hunted goats | Wild wool |
| Desert | Surface salt | Desert fruit |

### Historic era

| Area | Finite resource | Renewable resource |
|---|---|---|
| Woodland | Old-growth timber | Managed wood |
| Clay Mountains | Brick clay | Pottery |
| Ore Mountains | Iron ore | Water power |
| Fields | Fertile soil | Grain |
| Grazing Land | Livestock | Wool |
| Desert | Salt | Glass |

Fertile soil is consumed by intensive farming unless restored. Livestock represents animals slaughtered for meat while wool can be repeatedly harvested.

### Modern era

| Area | Finite resource | Renewable resource |
|---|---|---|
| Woodland | Hardwood | Industrial timber |
| Clay Mountains | Cement minerals | Industrial bricks |
| Ore Mountains | Metals | Hydroelectric power |
| Fields | Phosphate fertiliser | Mechanised crops |
| Grazing Land | Meat | Dairy products |
| Desert | Oil | Solar power |

### Futuristic era — current corrected resource set

| Area | Finite resource | Renewable resource |
|---|---|---|
| Woodland | Ancient hardwood | Clean air |
| Clay Mountains | Rare-earth clay | Purified water |
| Ore Mountains | Rare minerals | Geothermal power |
| Fields | Concentrated nutrients | Synthetic crops |
| Grazing Land | Fertile topsoil | Cultured protein |
| Desert | Exotic minerals | Solar power |

Additional processed wares are created through faction/culture processing buildings.

---

## 79. Resource origin

**Two independent sources**

Catan construction goods are minted by matching World Turn dice at occupied settlement nodes. They are not withdrawn from the industrial finite-resource ledger. A depleted industrial ore layer does not silently disable the Catan ore roll.

Industrial raw resources come from era-specific hex layers. Each finite layer has one shared saved balance; every extracting node reserves and consumes from it. Renewable flow is inexhaustible but capacity-limited. Extraction and industrial production use Game Time, not dice.

An ordinary era transition adds the new resource layer without erasing old balances. Legacy primary buildings can keep extracting the old layer and feeding legacy military production. New-era core upgrades rebind their primary sites to the new layer. Full-cycle layers use cycle IDs so the new Prehistoric layer does not refill an old deposit accidentally.

Working default: 600 extraction units per finite hex/resource layer and no natural refill during an era. Scripted restoration is allowed only through an explicit resource effect. Deposit quantities are tunable; shared accounting is invariant.

---

## 80. Resource representation

**LOCKED: 1–5 primary buildings in total per occupied node**

Use the existing pip table, but calculate the node's primary-site capacity from its **best adjacent production number**, never the sum:

| Best adjacent number | Total primary sites at the node |
|---|---:|
| 6 or 8 | 5 |
| 5 or 9 | 4 |
| 4 or 10 | 3 |
| 3 or 11 | 2 |
| 2 or 12 | 1 |

This maximum rule is the chosen default for interpreting several adjacent numbers. A city does not double the site count. Upgrading an existing primary site reuses its slot; keeping old-era sites does not create an extra allowance.

Each primary building is assigned to one adjacent hex and one era/resource layer. It has separate finite and renewable flow channels from that terrain's pair. Several buildings can share a hex, but must share its one finite deposit. The AI spreads its first sites over available terrains before adding duplicate capacity.

**Construction stock:** integer quantities of five era-independent Catan goods in node warehouses or loaded carts. They are physically located and must be delivered. Canonical IDs use catan.timber / catan.brick / catan.wool / catan.grain / catan.ore, distinct from every industrial resource ID.

**Industrial state:** source balances, installed capacities, allocated flows and factory progress. Animated crates and worker loads are representations of these flows, not additional spendable inventories. Actual scripted or legacy industrial stock records may exist and remain era-tagged; only an explicit allocation consumes them. Non-storable power/clean-air services are rate capacities, not cart cargo.

A matched non-desert hex grants 1 Catan good to each adjacent settlement, or 2 to a city, at that node's warehouse. Catastrophe suppresses that hex's grant. A roll of 7 grants nothing and adds no robber/discard rule.

---

## 81. Resource sinks

Catan goods pay for roads, settlement centres, city upgrades, legacy-site upgrades, industrial construction/repair and trades. Costs are reserved locally and consumed once at the construction site/staging warehouse.

Industrial raw flow, finite deposits and compatible legacy stocks feed calculated processing/military output. Worker walking does not consume a second copy. There is no compulsory worker food/upkeep economy in the MVP.

Destruction can remove stock/cargo; the ledger records this as a loss. Trade transfers goods rather than creating them. Era setup packages are explicit recorded grants.

---

# PART XVII — PRODUCTION

## 82. Production model

**LOCKED algorithmic industry with visible worker activity**

Each settlement/city has three military factory sites. Each completed military unit corresponds to one saved entity. Primary sites, processors, technologies, finite deposits and building damage determine production rates; workers act out the resulting activity.

The algorithm operates in Game Time for every node:

1. Read active primary channels, finite availability, catastrophe and installed processor/factory capacities.
2. Select each factory's legal input route from its era's recipe definitions.
3. Allocate shared input and processor capacity among the three requested unit rates.
4. Advance production meters by allocated units/second × elapsed Game Time; account for finite extraction once.
5. On a meter reaching 1, create one persistent unit at that node and retain any fractional remainder.

No unit can be manufactured from unavailable capacity merely because an animation finishes. Conversely, a worker stuck behind a visual obstacle does not pause the meter.

**Working rate model:** a primary channel supplies 0.1 industrial units/second; each processor consumes 1 of each of its two inputs per output and is capped at 0.1 outputs/second. Three factory archetypes consume 2, 3 or 5 processed outputs per unit, respectively, with one unit/minute as the initial factory-rate ceiling. All are tunable data.

Every processor output is eligible for the default military supply input category. The three unit types differ by conversion cost and combat stats. Each factory uses a selected valid processor route; advanced data may require multiple specific outputs later. This permits a reduced MVP catalogue and makes all 60 recipes usable without hand-authoring 60 different combat mechanics.

Allocate rates by deterministic progressive filling: raise equally weighted factory requests together until a raw-source, processor or factory limit binds; freeze the constrained requests and continue the rest. Shared finite availability is a global constraint across extracting nodes. Use stable IDs for ties and fixed-point quantities with saved remainders. No raw supply or processor throughput can be counted twice.

A city multiplies its primary flow capacity by 2, not its site count. Permanent technology modifiers apply afterward. Directly unavailable input stops the affected route; the AI may select another installed compatible route. Old factories retain their old recipes, resource layers and unit definitions.

Industrial transport inside a village is visual. The MVP does not require inter-node industrial shipments; Catan construction/trade carts remain real. Deliberately adding industrial import later requires explicit shipment definitions and the same conservation rules, not implied teleportation.

---

## 83. Production chains

Every era has twelve industrial raw resources: two from each of six terrains. Pair two resources from different terrains, without regard to input order. This yields 60 valid recipes per era and 240 over the four eras.

Every pair has its own processor definition and processed output. Every culture currently receives the complete catalogue for its era. Catalogue access does not mean all processors appear in every settlement: installation depends on useful local inputs, construction costs and AI choices.

There is no ten-processor-per-culture restriction. Future culture-specific recipes, visuals, bonuses or restrictions can be added through explicit data, without introducing one programming subclass per building.

The initial MVP may activate a tested subset of recipes to prove the loop. Its schema and validators must support the full catalogue and may not hard-code that subset as a culture limit.

Military rates derive from §82. Visible extraction/processing activity must match the selected routes and reported bottlenecks, although each carrier movement is illustrative.

---

## 84. Capacity

Capacity depends on:

- 1–5 total primary sites at the node;
- each site's assigned hex, resource layer and shared finite balance;
- installed processor/factory definitions;
- settlement/city multiplier and technology;
- damaged or destroyed real buildings;
- catastrophe on the source hex;
- explicit quest/policy production modifiers.

Capacity does not depend on an ordinary worker's path completion, a decorative crate's arrival, the player's collision with a worker, or how many local sprites are rendered.

Jobs have persistent identities and assignments. A production shutdown caused by a strike/quest is an explicit saved modifier, not inferred from an NPC standing in the wrong place. A vacated ordinary job is backfilled under §94.

Debug and knowledge-filtered player feedback identify the actual limiting source or facility.

---

## 85. Demand

The strategic layer requests construction/trade cargo and industrial expansion according to legal AI actions.

The industrial layer requests rates for its three military unit types. Equal weights are the default; faction policy may alter these priorities. The rate allocator respects real installed capacity and shared finite supply.

There is no hidden population hunger or worker-upkeep sink. Such a mechanic would need a future explicit design change.

---

## 86. Supply

Construction/trade supply comes from local spendable stock and committed deliveries along legal road routes. A distant warehouse cannot pay a local cost before its shipment arrives.

Industrial supply comes from the node's assigned adjacent-resource channels, compatible legacy stocks when explicitly allocated, and installed processors. The rate solver prevents duplicate allocation. Only Catan goods use mandatory inter-node cart logistics in the MVP.

Animated loads, local pathfinding and projected worker activity never mint supply.

---

# PART XVIII — LOGISTICS

## 87. Transport model

**LOCKED persistent carts and cargo**

A cart has a stable ID, owner, current node/edge, source, destination, reserved cargo, route, status and delivery ID. The baseline is capacity 4 Catan goods and speed one constructed road edge per World Turn, for all factions' carts. Later transport changes those data values.

Goods leave spendable source stock when loaded. Delivery credits destination stock exactly once. A cart cannot cross an edge without the required road/access permission, or enter a civilian-blocked catastrophe node. A destroyed cart loses its cargo; ownership changes trigger explicit rerouting, return or recorded loss.

Local cart animation displays this persistent entity. It may approach a departure point in real time, but crossing a strategic edge occurs only in the World Turn. Decorative industrial carrying is a different visual activity, without a cargo entity.

If the wizard stands in the way, workers/carts visually reroute or wait for a presentation-safe path; this does not alter their already defined industrial or strategic scheduling.

---

## 88. Network structure

Constructed strategic roads form the cart/construction network. Own, allied and explicitly trade-permitted roads are usable; hostile or embargoed segments are not. Unowned wilderness edges require a road before cargo can use them.

Local settlement paths organise appearance and navigation. Their length and congestion do not reduce industrial throughput. Military local navigation remains mechanically real.

A road is built from a connected owned staging node; pay its materials there. A new settlement's costs must reach its target node over completed roads before construction commits.

---

## 89. Distance cost

Strategic road distance determines cart delivery turns and exposure to disruption. Player node distance determines how many World Turns elapse while travelling. Armies traverse at most two edges on their own activation.

Local decorative worker route length does not alter military production. Local combat distance does affect movement time and range.

---

## 90. Congestion

**DEFINED**

Strategic transport bottlenecks come from cart availability, four-good capacity, one-edge speed, route permissions and catastrophe. No road-traffic queue or per-edge congestion simulation is required for the MVP.

Local workers route around the wizard and one another. If no purely visual route is available, use an idle/work alternative animation and flag the layout for repair; never fabricate an economic shutdown from that navigation failure.

---

## 91. Storage

Catan goods are saved per node warehouse or cart. Default warehouses have no hard capacity limit in the MVP, avoiding an extra unrequested warehouse-management game. Cargo and construction reservations reduce spendable stock.

Industrial flow counters are not another physical stockpile. Real legacy/quest-created industrial stock has a resource/era ID and a defined consumer; retained stock is not automatically upgraded.

Warehouse destruction records its stock loss. Site upgrades preserve surviving stores. Rendering an idle stack of boxes does not create accessible inventory.

---

## 92. Logistics failure

The player diagnoses through:

- idle buildings;
- absent shipments;
- empty stores;
- NPC complaints;
- semantic labels;
- visible road disruption.

The player does not personally fix routing menus.
They may physically/magically solve causes or influence policy.

---

# PART XIX — WORKERS / AUTONOMOUS AGENTS

## 93. Worker roles

Primary extraction, processing, construction, transport and military facilities have ordinary workers with persistent IDs and jobs. Every production building has at least one anchor NPC; its assigned ordinary worker may fulfil that role.

Their workplace, preferences, relationships and dialogue can support quests. A worker is a real person represented by a lightweight record, even when not visually instantiated.

Economic production uses calculated capacity. Worker movement shows what the economy is doing; it does not determine whether a material has canonically arrived.

---

## 94. Worker creation

Assign one persistent worker to each active production-building job slot by default; additional visible staff may be lightweight persistent workers where useful. Each has ID, name, occupation, workplace, role/status, relationships and dialogue profile.

When a quest changes a person's occupation, moves them or recruits them elsewhere, retain that person and their history. Create a different replacement ID for the vacant job on the next Game-Time accounting tick. The original worker is never silently renamed/reused.

Building destruction leaves its living workers displaced unless an explicit event kills them. They may be reassigned; jobs and current appearance adapt to a new era while identity persists. Ordinary workers can become major quest characters without identity conversion.

---

## 95. Worker assignment

Faction administration assigns jobs automatically. The wizard can affect people through quests but cannot use an assignment interface.

Ordinary vacancy backfill is automatic and does not create an extra pathfinding-based production delay. Strikes, abandonment or sabotage reduce capacity only through explicit simulation effects with stated duration/removal conditions.

---

## 96. Worker autonomy

Workers walk, carry, operate facilities, converse and react visually to danger in real time. They use local navigation around obstacles and the wizard.

The animation layer follows authoritative workplace state, production status and catastrophe. It must not alter throughput, consume stock or complete quests merely because an animation loops. Explicit interactions are validated commands.

---

## 97. Worker progression

Workers are individually persistent, but do not require worker XP levels. Jobs, workplace changes, relationships and quest history are saved per person. Specialist categories and building technologies determine economic capabilities; movement animation and repeated work cycles do not award hidden progression.

---

## 98. Indirect control

The wizard does not assign workers.
They can:

- solve the problem preventing workers working;
- influence leaders;
- protect or destroy infrastructure;
- affect catastrophe;
- interact with workers as people.

---

# VOLUME VII — CONSTRUCTION, TERRITORY AND FACTIONS

# PART XX — CONSTRUCTION

## 99. Building purpose

Buildings turn geographic potential and technology into actual economic/military capability.

---

## 100. Placement

The faction AI chooses strategic settlement/road sites using §104's legality. The local layout places each persistent building in a stable footprint, preserving exits, usable interaction points and important items.

Each settlement/city has 1–5 primary sites in total and three military factory sites. Other processors/civic buildings use available local layout space; expand the generated local area when needed rather than dropping real buildings.

Local footprint placement affects appearance, walkability, combat cover and targetability. It does not introduce worker-travel penalties into the industrial formula.

---

## 101. Construction process

**DEFINED baseline costs and completion**

| Action | Delivered Catan cost |
|---|---|
| Road edge | 1 timber + 1 brick |
| New settlement, including its baseline civic/industry sites | 1 timber + 1 brick + 1 wool + 1 grain |
| Settlement → city | 2 grain + 3 ore |
| Legacy settlement → current-era settlement | 1 timber + 1 brick + 1 wool + 1 grain |
| Additional processor or replacement industrial building | 1 timber + 1 brick + 1 ore |
| Repair a damaged building | 1 brick + 1 ore |

Reserve cargo, transport it, then commit the action once at the delivered construction phase. Road costs are consumed at its connected staging node; all other costs at the target node. There is no extra building animation timer controlling completion.

Basic settlement sites include a warehouse/centre, its assigned primary sites, three factories and one feasible default processor route. All three factories may initially share that route, with §82 allocating its constrained output. If geography has no cross-terrain pair, industry waits for another site/route and the validator must not invent an illegal recipe. At least each faction's starting core pair must include a viable industrial site.

Additional processing options are built deliberately as technology, strategy and local resources justify them. All numeric costs are tunable. The wizard never pays these costs through a player construction menu.

Era inherited-core starter upgrades/packages are the explicit exception in §40.

---

## 102. Building dependencies

Definitions state era/culture eligibility, technology requirements, strategic site, resource/input routes and any supply-capacity dependencies.

Construction costs use the five Catan goods. Industrial output uses the twelve era raw types and valid processed outputs. Power/clean-air services are local capacity dependencies, not stored or carted goods.

Validate the dependency graph and its bootstrap path. An initial facility cannot require a product obtainable only from that same unbuilt facility unless a defined starter package supplies it.

---

## 103. Repair, upgrade and destruction

Buildings persist with individual IDs and may be damaged, destroyed, repaired or upgraded. Damage scales usable capacity by current-health/max-health; destroyed buildings contribute none. Wizard destruction bypasses health.

Ordinary era transition upgrades only inherited cores automatically. Other settlements, buildings, workers, units and stocks remain. Old-era factories continue producing old-era units from their retained resource layers and rates.

A legacy site becomes current-era only after delivery and payment of its defined upgrade cost. Adapt primary/factory slots in place; keep extra legacy processors unless explicitly rebuilt. The five Catan goods remain valid across eras; it is industrial definitions, resources and units that become technologically obsolete.

Collapsed-faction settlements are the exception: their operational assets are removed and their inert ruins can be built over freely (§40).

---

# PART XXI — TERRITORY

## 104. Ownership

**DEFINED**

A settlement centre owns its strategic node for its faction. Destroying the centre removes that ownership and its VP; destruction does not automatically transfer it to the attacker. Remaining surviving industrial structures become inactive/unowned until a legal settlement rebuild claims and repairs them. This differs from era-collapse ruins, which have no mechanics.

Current-era settlement = 1 VP; current-era city = 2 VP total. Legacy unupgraded settlements/cities = 0 current-era VP. There are no hidden VP cards, Longest Road or Largest Army points in the baseline. There are no per-faction board-game piece caps; board legality is the limit.

A new settlement needs an empty node, no settlement at an adjacent node, and a connected usable own-road endpoint. Initial setup and the explicit emergency reseeding rule have their own placement contract. A city upgrades an owned current-era settlement. Roads connect to an owned settlement or road and cannot extend through a hostile owned node.

Check the 10-VP trigger immediately after every committed scoring change. Simultaneous candidate builds commit in active-seat order then faction ID, so a winner is unambiguous. A later destruction cannot undo a transition that already triggered.

---

## 105. Expansion

Faction strategy proposes legal roads, settlements, city upgrades and legacy-site upgrades. Costs are delivered using real cart logistics. The player influences circumstances, not queues.

Military or wizard destruction can clear ownership. Rebuilding then follows normal site legality; victory is not automatic annexation. Collapsed-faction ruin art never blocks the distance test or adds a clearing fee.

---

## 106. Territorial value

Territory provides:

- renewable resources;
- finite deposits;
- expansion space;
- transport routes;
- strategic positions;
- settlement sites.

---

## 107. Territorial loss

Destroying a settlement centre removes its owner and score. Surviving industrial assets are stranded/inactive until claimed by legal rebuilding; cargo and workers receive explicit dispositions. Roads remain unless destroyed and may lose access or become disconnected.

A faction that loses its last centre dissolves, with civilian continuity and no-factions recovery under §40. Era-collapse ruins have no remaining economy, loot or collision.

NPCs, knowledge and quests receive events referring to the original stable IDs. Do not replace a destroyed place with a different living settlement while keeping its old quests silently bound.

---

# PART XXII — FACTIONS / TRIBES / CLASSES

## 108. Need for asymmetry

**DEFINED**

The game begins with six political factions, but **culture is not a permanent identity layer**.

Mechanical asymmetry is supplied by era-specific culture packages: collections of buildings and units that determine how a faction converts the common resource/technology framework into economy and military force.

The first MVP can use simple/default culture packages. Additional alternative cultures and richer differentiation are POST-MVP content once the core economy and AI are working.

---

## 109. Shared foundation

All political factions share:

- the same strategic geometry;
- Catan-style VP and settlement rules;
- the same World Turn / World Round cadence;
- technology drafting framework;
- resource-production rules;
- logistics framework;
- catastrophe framework;
- neural-network strategic-AI interface.

The initial six political factions in the current implementation can retain their existing names for the MVP, but they are not required to represent six immutable cultures across all eras.

---

## 110. Structural differences

A culture package selects era-compatible building/unit definitions, visuals and permitted technology effects. For the current implementation, every package includes all 60 valid processors for its era and the same three military archetypes.

Factions still differ through geography, installed facilities, technology, policy, units and history. No artificial ten-recipe restriction is applied.

Future culture-specific recipes, bonuses and substitutions extend this schema after the baseline is proven. Such extensions must preserve declared supply feasibility and identify any deliberate restriction.

---

## 111. Strategic identity

The player does not play as a faction.

Faction strategic identity emerges from:

- the culture package's units/buildings;
- resource geography;
- technology cards drafted;
- decisions made by the faction's trained neural-network leadership policies;
- diplomacy and war history.

Because culture can change by era, a faction's later strategic identity can differ substantially from its earlier one.

---

## 112. Strengths and weaknesses

**DEFINED baseline; differentiated packages POST-MVP**

All initial cultures share their era's complete processing catalogue and three unit archetypes. Strengths and weaknesses initially arise from terrain, source capacity, installed routes, technology, policy and wars.

Later packages may add explicit bonuses, substitutions or restrictions. No further cultural-design approval is needed before implementing the shared baseline.

---

## 113. Matchups

Matchups should emerge from:

- available resources;
- processing ratios;
- three military unit types;
- universal technology upgrades actually drafted;
- neural-network strategic decisions;
- geography;
- player intervention.

Avoid hard-coded universal faction matchups.

---

# PART XXIII — TECHNOLOGY AND UNLOCKING

## 114. Capability progression

**LOCKED rotating seven-card draft; DEFINED edge cases**

At era start deal seven cards to each faction using the seeded current-era pool. Each completed World Round every faction selects exactly one card from its current hand. Resolve all selections against the same pre-draft snapshot, then pass the remaining hands clockwise in stable seat order.

After the seventh pick, the hands are empty: deal seven fresh cards immediately for future rounds. Use a declared weighted pool with replacement, so small MVP pools remain usable. A single faction passes to itself. Era transition discards unfinished hands and starts a fresh era pool.

Drafting acquires a card. Activation requires its prerequisites. If no card is currently playable, the faction still drafts one into its research archive; it activates automatically once a valid predecessor exists. There is no free extra draw or skipped one-card invariant.

Duplicate non-stackable technologies are archived as inert copies. A definition may explicitly permit stacking up to three copies; never infer repeat bonuses from duplicate text. No purchase cost, trade, theft or copying is introduced.

---

## 115. Prerequisites

Prehistoric cards have no predecessor gate. Later cards require at least one listed predecessor, giving a branching many-to-many graph.

Research history survives ordinary era transitions and is copied to successors on fission. Effects apply only to declared compatible eras/definitions; an old technology does not automatically upgrade old units into new ones. Inactive drafted cards remain archived until their gate is satisfied.

Full-cycle political reseeding starts new current-cycle faction research; Chronicle history is retained but does not grant every new faction all prior technology.

Validate reference existence, acyclic activation dependencies and at least one reachable route to each required baseline capability. The starting pool includes general throughput and logistics cards; baseline buildings and unit production never require a luck-dependent missing card.

---

## 116. Gating

Era selects the current industrial resource layer, unit/building definitions, technology pool and appearance. All baseline culture packages receive that era's complete 60-processor catalogue.

The first implementation uses one default package per era, with Prehistoric and Historic in the MVP. Additional culture-specific variants and the Utopian extension follow later.

Legacy settlements remain old-era and non-scoring until upgraded with delivered Catan construction goods. Their industrial inputs/outputs stay tied to their own era. The five basic construction goods do not acquire a new incompatible identity each era.

---

# VOLUME VIII — AI AND AUTONOMY

# PART XXIV — AI

## 117. AI purpose

Faction AI selects legal strategic actions: construction, technology, trade, diplomacy, military objectives, catastrophe response and voluntary fission. The engine enforces costs, clocks, placement, movement, VP and state ownership.

The MVP uses a deterministic heuristic policy. The later target is a small trained policy library, with one active leadership policy per faction per era. Switching to neural leadership changes action selection, not the economic or legal rules.

Local tactical and worker controllers remain bounded authored behaviours. LLMs supply offline prose, never runtime strategy.

---

## 118. AI knowledge

Each strategic policy observes a structured, versioned view:

- its local Catan stocks, reservations and pending cargo;
- settlements, roads, legal sites, VP and legacy status;
- industrial capacities, finite-resource availability and three unit-production rates;
- unit counts/strength by node and era, current engagements and casualty history;
- technology hands, owned/research-archive cards and prerequisites;
- public ownership, diplomatic relations and catastrophe;
- durable quest/policy commitments.

Default faction strategy knows public board ownership, routes and catastrophe, its own full economy/army, and observed enemy forces; it does not read the wizard's hidden knowledge or private conversations. NPC dialogue receives the NPC's own knowledge, not the faction controller's observation.

The adapter supplies a legal-action mask and stable IDs. The same observation contract is used by heuristic and neural policies.

---

## 119. Local behaviour

Workers, soldiers and NPCs use lightweight role-based autonomous behaviour.

---

## 120. Strategic behaviour

**DEFINED baseline**

On its active turn the heuristic policy:

1. responds to a catastrophe blocking a core or essential route when it has an eligible force;
2. completes/funds a legal action that reaches 10 VP;
3. restores missing productive/core capability;
4. expands or upgrades toward VP, favouring source diversity, theoretical capacity and short delivery distance;
5. builds useful processors and schedules military objectives;
6. offers a mutually deliverable trade for an identified shortage.

All candidates come from the legal-action generator. Score ties use stable action IDs. No repeated free action loop is allowed: one new construction order and one trade/diplomatic proposal per activation, plus one order per disengaged formation. Previously delivered construction may complete for every faction.

Diplomacy defaults to neutral with trade permitted. Attacks establish war; alliances allow transit and military cooperation. Explicit agreements and witnessed wizard asset destruction modify relations/commitments, not hidden dialogue strings. A trade is a saved bilateral shipment contract, not an instantaneous stock swap.

Voluntary fission is considered only with at least four sites and fewer than six resulting factions. The heuristic splits when the top-four compact pairs are at least four node edges apart and less than 50% of its entry military effective strength was lost during the era. Otherwise it stays unified. Quest commitments can veto or encourage voluntary fission. Mandatory sole-faction fission overrides this policy.

The six-faction ceiling is an initial tunable workload/geography limit, not six permanent culture identities.

---

## 121. Authored versus general intelligence

**DEFINED**

The engine owns legality and outcomes. A strategy policy returns a candidate action ID; the engine revalidates it before execution. Stale or illegal proposals are rejected without partial mutation, then use the best legal heuristic fallback.

For later neural leadership, use a policy scorer over the current legal candidate list and structured observation features. Begin with imitation of heuristic trajectories, then actor-critic training against the same simulator. Retain at most three behaviourally different accepted policies in the initial library.

At era start, select one policy per faction with a seeded choice and retain it for that era. Do not let several neural networks issue conflicting orders simultaneously. Quest effects change explicit observation fields/commitments; they do not attempt to edit opaque model weights.

---

## 122. AI limitations

**DEFINED training and replay defaults; quality remains a validation task**

Train against the real rule implementation. A headless training controller advances fixed 30-second Game-Time intervals and legal World Turns; it does not bypass industrial costs or give free units. Episodes end at era transition, terminal catastrophe or 1,000 World Turns.

Initial reward: +10 for triggering the era win, −10 for collapse, −10 for terminal catastrophe, +0.2 per net VP gained and −0.001 per activation. VP-loss reverses the shaping reward. A timeout is a draw. Do not reward endless stock accumulation or actions that merely increase logged activity.

Promote a neural policy only after at least 200 fixed evaluation seeds show legal play, no increase in catastrophic failure and competitive 10-VP performance against the baseline. Diversity is measured by build/trade/war behaviour; it is not obtained by weakening legality.

Inference uses the pinned policy version and deterministic action ranking where supported. Record actual selected actions for portable replay rather than assuming floating-point model inference is bit-identical on every machine. Failed/slow inference falls back to the heuristic within the same legal-action contract.

Fission constraints and the mandatory sole-faction split are engine rules even if a learned policy proposes otherwise.

---

## 123. Difficulty

Difficulty adjusts catastrophe placement cadence, duel assistance and hint availability. Initial faction leadership remains the same legal heuristic across modes; stronger neural policies can be selected later without secret resources.

Use the default settings in §158. Never make the wizard vulnerable to faction military as an undocumented difficulty modifier.

---

# VOLUME IX — CONTENT DESIGN

# PART XXV — CONTENT GRAMMAR

## 124. Fundamental content unit

The most important cross-system content primitive is the **Semantic Entity**.
It connects:
SIMULATION ENTITY
\+ WORLD POSITION
\+ KNOWLEDGE STATE
\+ LABEL
\+ OBSERVATION
\+ INTERACTION

Other primitives:

- dialogue node;
- quest state;
- puzzle mechanism;
- building definition;
- technology card;
- unit archetype.

---

## 125. Reusable primitives

- semantic contracts;
- dialogue states;
- faculty interjections;
- quest conditions;
- puzzle triggers;
- production recipes;
- technology prerequisites;
- unit archetypes;
- culture-package definitions;
- catastrophe states.

---

## 126. Bespoke content

Reserve expensive bespoke work for:

- major recurring wizards;
- major faction leaders;
- exceptional historical events;
- major dungeons;
- unique artifacts;
- important era transitions.

---

## 127. Content hierarchy

SIMULATION STATE
→ LOCAL SITUATION
→ SEMANTIC ENTITIES
→ NPC GOALS / QUEST OPPORTUNITIES
→ DIALOGUE / DUNGEON / CONFLICT
→ PLAYER INTERVENTION
→ WORLD CONSEQUENCE
→ HISTORICAL RECORD



---

# PART XXVI — LEVEL / MAP DESIGN

## 128. Level purpose

Every explorable space should reveal or interact with the surrounding simulation.
Avoid unrelated filler dungeons.

---

## 129. Spatial structure

Use:

- main routes;
- optional branches;
- loops;
- locked/conditional areas;
- secrets;
- shortcuts.

---

## 130. Challenge placement

Challenge follows narrative/system state.
Examples:

- demon-infested mine;
- industrial sabotage site;
- alien landing area;
- future machine complex.

---

## 131. Resource placement

Strategic resources belong to hex geography.
Local areas physically communicate extraction or exploitation.

---

## 132. Safe and dangerous spaces

Settlement centres tend towards social/safe content.
Frontiers, catastrophe sites and dungeons increase danger.
No location is universally safe if simulation changes.

---

## 133. Replayability

Replayability varies through:

- persistent board geography plus changing finite-resource layers;
- faction survival and collapse;
- AI-chosen fission;
- neural-network policy differences;
- technology draft history;
- wars and alliances;
- catastrophe placement/spread;
- generated NPCs and precompiled quest/dialogue variants;
- player intervention;
- accumulated ruins, myths, artifacts and scars across historical cycles.

---

# PART XXVII — MISSIONS / SCENARIOS

## 134. Scenario purpose

The main game is a sandbox, not a mission sequence.
Scenario structures can be used for:

- tutorial;
- testing;
- curated historical crises.

---

## 135. Starting conditions

Scenario-specific.
Main game starts in prehistoric era with generated world/faction state.

---

## 136. Objective

Main sandbox has no compulsory victory objective.
NPC quests have local objectives.

---

## 137. Constraints

Can be used in tutorial/test scenarios.

---

## 138. Scripted events

Use sparingly.
Prefer systemic conditions.

---

## 139. Failure conditions

Quest failure differs from game failure.
Only terminal catastrophe normally ends the game.

---

## 140. Alternative solutions

Strongly preferred.
Magic, dialogue, exploration and non-intervention can all produce different valid outcomes.

---

# PART XXVIII — QUESTS AND DIALOGUE

## 141. Quest structure

**DEFINED runtime grammar**

World condition → affected entity → persistent NPC who cares → desired change → obstacle → optional intervention → validated world effect.

The eight initial families are shortage/production failure, blocked transport, catastrophe response, diplomacy, military threat, personal worker/NPC problem, discovery and conflicting interests. The MVP implements one rich family through this common grammar; others are later template content.

A quest instance stores stable ID, template/version, cause ID, bound NPC/site/object IDs, state, prerequisites, chosen branches, outcome and applied effect IDs. It normally has 2–5 meaningful states. It is created once from a real condition and retained; revisiting a village does not regenerate its cast or reset the graph.

Supported states: offered, active, suspended, completed, resolved_by_world and failed_with_consequence. Several quests may coexist. At most one active instance for the same template/cause/affected-entity tuple is generated; a genuinely new occurrence gets a new cause ID.

Era transitions retain active quests and bindings. A change in era alone neither completes nor fails them. Current lines must describe current world facts while preserving remembered promises.

If the world fixes the original problem first, use resolved_by_world and acknowledge what happened; grant only effects whose predicates still hold. If an NPC dies, a target is destroyed or a faction collapses, use an authored successor, displaced-NPC, recovery or failure branch. Never resurrect the old entity to preserve a preferred plot.

Every MVP template must provide an invalid-target route and an alternative for lost mandatory objects. Concurrent outcomes revalidate immediately before commit; effects carry idempotency IDs so two conversations cannot grant the same reward twice. Runtime prose never decides which branch is true.

---

## 142. Branches

Branches follow explicit conditions over player knowledge, relationships, the seven Aspects, current world facts and persistent quest state. A branch may open because another actor solved the problem.

Checks use §48's deterministic rules. Failure must lead to a defined continuation, consequence or later state-dependent retry. Do not create a mandatory infinite retry gate.

Quest deadlines declare World Turns or Game Time. Default systemic deadlines use World Turns and do not consume time while the player reads a paused choice.

---

## 143. Dialogue system

World-anchored dialogue.
Speech stays attached to the person rather than always transitioning to a separate full-screen conversation mode.
Approximately three natural responses at once is a useful presentation target.
Walking away remains valid.

---

## 144. Dialogue reactivity

Dialogue reads structured runtime context such as:

```text
SPEAKER
POLITICAL FACTION
ERA
CULTURE PACKAGE / BUILDING ROLE WHERE RELEVANT
ROLE / WORKPLACE
PREFERENCES
LOCAL WORLD STATE
ECONOMY
WAR
CATASTROPHE
PLAYER KNOWLEDGE
RELATIONSHIP
QUEST
HISTORY
SEVEN ASPECTS
```

All dialogue is generated/authored **offline before release** and written into game data files. Runtime code selects among pre-generated conditional line banks and may safely insert validated variables such as names or counts.

There is no runtime LLM call and no requirement for internet access.

---

## 145. Consequences

Dialogue/quest data requests typed effects: relationship change, knowledge discovery, quest transition, Aspect change, durable AI commitment, diplomatic agreement, item transfer, production modifier, construction-stock transfer, catastrophe treatment, entity relocation or historical fact.

The owning system validates each effect and its preconditions. World consequences are applied atomically and once by effect ID. No arbitrary Python/GDScript expression or generated state patch is allowed in prose data.

Effects cannot silently grant army orders to the player, bypass cargo delivery, make a worker animation authoritative, or exceed a catastrophe visit allowance. Any exceptional authored outcome declares its exception explicitly.

---

# PART XXIX — CAMPAIGN / MACRO STRUCTURE

## 146. Overall progression

There is no conventional linear campaign.

Historical macro-loop:

```text
PREHISTORIC
→ HISTORIC
→ MODERN
→ DYSTOPIAN FUTURE
→ PREHISTORIC
→ ...
```

This can continue indefinitely while completed cycles are tracked.

A Utopian Future branch remains a supported later extension but the current build should always proceed to Dystopia unless a future quest/content system explicitly changes that path.

---

## 147. Content sequencing

Technology and social complexity increase with eras.
The same geography supplies continuity.

---

## 148. Mechanical escalation

Prehistoric introduces:

- labels and knowledge;
- dialogue and seven Aspects;
- Mastermind magic;
- demons;
- basic resource/processing economy;
- strategic faction AI;
- technology draft.

Historic expands:

- upgraded culture package;
- stronger processing/military production;
- organised warfare;
- chained technology prerequisites.

Modern expands:

- industrial resource set;
- modern culture package;
- more powerful military;
- pollution catastrophe;
- alien catastrophe.

Future currently expands into the dystopian path:

- future resource/culture package;
- nuclear-war catastrophe;
- hostile AI/cyborg catastrophe;
- the most technologically powerful military/economy.

Utopian future + returning demons is POST-MVP.

---

## 149. Narrative escalation

Narrative comes primarily from accumulated world history rather than a fixed plot.
The wizard's relationship with recurring patterns provides thematic continuity.

---

## 150. Finale

There is no mandatory final campaign finale.

The world is designed to continue cycling indefinitely until:

- terminal catastrophe ends the run; or
- a specific authored/generated quest offers a legitimate ending state.

The wizard cannot simply retire or voluntarily die through a generic menu action.

Completed historical cycles are recorded as part of the run's history.

---

# VOLUME X — LEARNING, DIFFICULTY AND PACING

# PART XXX — LEARNING

## 151. First actions

Player learns:

1. move;
2. read labels;
3. observe;
4. approach and interact;
5. talk;
6. recognise knowledge-dependent labels.

---

## 152. Teaching sequence

Then:

- quest interaction;
- puzzle;
- personal duel;
- demon/catastrophe signal;
- economy observation;
- faction activity;
- military battle;
- strategic magic;
- technology;
- VP/era transition.

---

## 153. Teaching method

Prefer:

- safe experimentation;
- NPC explanation;
- environmental consequence;
- repeated observation.

Use explicit tutorial text only where interaction would otherwise be opaque.

---

## 154. Mastery progression

NOTICE SYSTEM
→ UNDERSTAND LOCAL EFFECT
→ RECOGNISE CAUSAL CHAIN
→ PREDICT CONSEQUENCE
→ DELIBERATELY INTERVENE
→ ACCEPT OPPORTUNITY COST



---

# PART XXXI — DIFFICULTY

## 155. Difficulty dimensions

- deduction;
- puzzle inference;
- incomplete information;
- catastrophe prioritisation;
- travel/time management;
- strategic uncertainty;
- dialogue checks;
- personal magical combat.

---

## 156. Difficulty curve

Later eras add industrial, technological and catastrophe interactions and much stronger military units. The wizard's immunity and core magical rules remain unchanged. Difficulty must come from deduction, knowledge, competing interests and presence rather than secretly giving faction soldiers a way to harm the wizard.

---

## 157. Difficulty combinations

Highest tension comes from simultaneous problems:
WAR
\+ CATASTROPHE
\+ NPC CRISIS
\+ DISTANCE

The player cannot solve everything.

---

## 158. Difficulty settings

**DEFINED initial settings; TUNABLE**

| Setting | Catastrophe draw interval | Duel/puzzle support |
|---|---:|---|
| Gentle | Every 5 World Turns | Optional strong hints and deduction assistance |
| Standard | Every 3 World Turns | Contextual hints on request |
| Severe | Every 2 World Turns | Minimal automatic hints |

Each placement step draws one hex initially, two once the era has completed four World Rounds, and three after eight rounds. The terminal threshold is eight outbreaks per era on all three modes. AI units receive no hidden production or combat bonuses.

Accessibility settings independently pause on reading screens, enlarge labels/targets and reduce motion. All controls work without hover or multi-button chords.

---

# PART XXXII — PACING

## 159. Moment-to-moment rhythm

MOVE
→ NOTICE
→ STOP
→ INTERACT
→ THINK
→ ACT
→ MOVE



---

## 160. Recovery periods

Normal settlements and post-crisis periods provide slower social/exploration time.

---

## 161. Escalation

World simulation naturally accumulates conflicts.
Era proximity to 10 VP creates macro-level anticipation.

---

## 162. Pacing controls

- strategic travel;
- production rate;
- faction actions;
- catastrophe rate;
- war duration;
- quest density;
- dialogue length;
- dungeon size;
- technology-draft cadence.

---

# PART XXXIII — FAILURE

## 163. Failure taxonomy

- failed dialogue/check;
- failed quest;
- NPC death;
- destroyed settlement;
- military defeat;
- faction collapse;
- bad technology path;
- puzzle error;
- duel loss;
- catastrophe escalation;
- terminal catastrophe.

---

## 164. Failure feedback

World should make causal failure legible.
Catastrophe must provide escalating audiovisual, environmental and social warnings.

---

## 165. Recovery

All failures except terminal catastrophe should have continued-play outcomes.

---

## 166. Terminal failure

**LOCKED cube/outbreak structure; DEFINED pacing and treatment**

### Cube state and effects

A hex holds 0–3 active catastrophe cubes in total. Cubes have a type and stable hazard/cause references. Any cube blocks that hex's Catan grants and industrial source flows. It also blocks civilian/cart transit through touching strategic nodes; military and the wizard can enter to respond. Local decorative workers do not enforce this strategic ban through collision.

On a fourth attempted cube, keep the hex at three, increment the era-global outbreak counter, and attempt one cube on each adjacent hex. A propagation event records which hexes already outbreaked; each can outbreak at most once in that event. Process adjacency in stable hex-ID order and stop immediately if terminal loss occurs.

### Appearance and timing

Default setup places one demon cube on each of three seeded distinct hexes, choosing a validated start with at least one productive reachable site per faction. Placement uses a seeded deck of all 19 hex IDs; reshuffle its discard when empty. Draw cadence and draw counts follow §158.

New placements use the current era's supported catastrophe types. Modern alternates pollution and alien additions; dystopian Future alternates nuclear-escalation and hostile-machine additions. Existing cubes retain their type across ordinary era changes. Typed quests therefore do not silently change a demon into pollution.

### Wizard treatment and visits

One successful hazard duel removes **one cube** of the challenged type from the chosen adjacent hex. It does not clear all three cubes automatically. A node visit permits one successful magical treatment per adjacent hex, up to three successes when all three neighbouring hexes are affected.

Store the treated hex IDs in the visit state. Wait, saving/loading, menus, entering interiors and duel recovery do not refresh this ledger. Returning to the same node within the same World Turn reuses its ledger. A genuine later strategic return creates a new visit after travel has advanced the world. Failed duels do not consume a successful-treatment allowance, but their authored consequences still apply.

Pollution uses cleanup projects/quests and faction treatment rather than a duel. Faction response is separate from the wizard's allowance: an eligible responding formation may remove one cube instead of moving/attacking on its activation. Pollution requires a cleanup-capable facility/unit; other types require an appropriate military responder.

### Rollover and terminal loss

The outbreak threshold is **eight cumulative outbreaks within the current era**. Reset the counter at successful era transition, preserve total outbreaks in the Chronicle, and preserve surviving cubes/typed causes. This allows an endless game without a lifetime counter guaranteeing eventual unavoidable loss.

At a full cycle, retain mapped contamination/scars as legacy state; reset active catastrophe from the new-cycle starting rules, explicitly resolving or adapting any quest tied to a retired active hazard. Living NPCs and quest records are retained.

On reaching the threshold, emit one terminal event, stop all further world actions, end the run and return to the menu. Manual reload remains possible, including a save that is already strategically doomed. No faction defeat or loss of every settlement substitutes for this terminal condition.

---

# VOLUME XI — INTERFACE AND FEEDBACK

# PART XXXIV — UI

## 167. Primary game screen

Minimal local-world screen containing:

- player/world;
- semantic labels;
- contextual speech/interactions;
- only essential player-state UI.

No strategy HUD is permanently required.

---

## 168. Secondary screens

Provide inventory/equipment, grimoire, knowledge/journal, discovered world map, Chronicle and save/load/settings screens. They pause Game Time while open. The map is knowledge-filtered and does not grant remote destruction, army orders or a global economic management interface.

---

## 169. Information hierarchy

### Always visible

what the player can physically perceive and relevant labels.

### Inspection

identity, observed state and deeper contextual information.

### Hidden

exact simulation variables and undiscovered truth.

---

## 170. Interaction feedback

Labels and observation text react to:

- range;
- knowledge;
- invalid targeting;
- changed world state.

---

## 171. Diagnostic feedback

Important because player does not have a management dashboard.
Examples:
FORGE — IDLE
ROAD — BLOCKED
ORE CART
ABANDONED MINE
SICKLY CROPS
UNIDENTIFIED LIGHTS

NPCs provide human explanations.

---

## 172. Input efficiency

Frequent actions must remain one-step or near-one-step:

- move;
- tap/click target;
- observe;
- interact;
- choose response;
- target magic.

---

# VOLUME XII — PRESENTATION

# PART XXXV — ART

## 173. Visual identity

**LOCKED 2D top-down sprite direction; DEFINED prototype defaults**

Use 16×16 logical terrain tiles, approximately 16×24 character sprites, four-direction movement and a default integer 4× pixel scale. Buildings use multiples of the terrain tile. Keep logical tile size separate from UI sizing and configurable camera scale.

Provide walk/idle/work/attack/hit/death states through shared archetype families. Start with four walk frames and two work frames where appropriate; art can improve without changing simulation.

Use a responsive landscape-first local view with scalable dialogue and semantic labels. Touch targets have at least a 48-logical-pixel hit region at the UI scale. No essential interaction depends on hover, right-click, a keyboard shortcut or simultaneous button presses. A pointer press maps to a touch press.

Units, worker identities and building footprints remain recognisable through upgrades and revisits. Battle readability comes from silhouette, faction colour, era and selective labels; display full labels for the focused/nearby actors rather than covering every unit with text.

These are buildable starting values, not a requirement for final polished art before the MVP.

---

## 174. Gameplay readability

Must communicate:

- faction;
- era;
- building role;
- danger;
- catastrophe;
- interactability;
- military class.

---

## 175. Entity readability

Use strong silhouettes/archetypes.
Thousands of generated unit **profiles** do not imply thousands of bespoke sprite sets.
Variants should reuse archetype asset families.

---

## 176. Environment readability

A player should visually recognise:

- resource exploitation;
- prosperity;
- decline;
- war;
- catastrophe;
- technological era.

---

## 177. Animation requirements

Core:

- player movement;
- NPC locomotion;
- worker activity;
- transport;
- building activity;
- military fighting;
- magical effects;
- catastrophe state.

---

# PART XXXVI — AUDIO

## 178. Music

Era- and situation-responsive.
Functions:

- identify historical atmosphere;
- support exploration;
- signal crisis;
- signal battle/catastrophe.

---

## 179. Sound effects

Major groups:

- magic;
- world interaction;
- industry;
- transport;
- military;
- demons;
- aliens;
- machinery;
- environment.

---

## 180. Informational audio

Important alerts can include:

- industrial shutdown;
- battle;
- catastrophe presence;
- puzzle mechanism;
- nearby danger.

Avoid global alarm spam.

---

## 181. Voice

Full voice acting for LLM-scale dialogue is not currently practical and is not required.
Text-first world dialogue.
Major recurring characters could receive selective voice later.

---

# PART XXXVII — NARRATIVE

## 182. Premise

The wizard persists while political factions repeatedly rise, collapse, split and adopt new era-specific cultures of buildings and units.

Civilisation advances from prehistory through historic and modern eras into a dystopian technological future, then collapses back into a new prehistory. The same geography and production values remain beneath accumulating ruins, artifacts, contamination, myths and scars.

The wizard remembers every cycle and experiences history through the ordinary people, workplaces, wars and catastrophes generated by the underlying simulation.

---

## 183. World

One strategically persistent region.
Its geography remains recognisable while:

- political borders;
- settlements;
- technology;
- industries;
- armies;
- architecture;
- threats

change radically.

---

## 184. Characters

Narrative roles include:

- the wizard;
- rival wizards;
- faction leaders;
- neural-network-controlled strategic leadership represented through NPC institutions/figures where appropriate;
- production-building anchor NPCs;
- workers;
- soldiers;
- specialists;
- lightweight ambient inhabitants;
- catastrophe-linked characters.

Every production building should provide at least one persistent anchor NPC with dialogue and preferences.

The majority of dialogue/personality content is generated offline from structured templates and stored as game data.

---

## 185. Story delivery

- world events;
- conversations;
- internal faculties;
- semantic labels;
- quests;
- dungeons;
- environmental history;
- faction cultural records;
- consequences observed later.

---

## 186. Agency

The player can meaningfully change:

- individuals;
- settlements;
- battles;
- relationships;
- policies;
- faction fortunes;
- catastrophe response.

The player cannot guarantee control over civilisation as a whole.

---

# VOLUME XIII — TECHNICAL AND CONTENT ARCHITECTURE

# PART XXXVIII — SIMULATION ARCHITECTURE

## 187. Required simulation systems

- Hex Board.
- Strategic Time.
- Faction State.
- Catan VP/expansion.
- Settlement Economy.
- Ware/Production.
- Logistics.
- Workers.
- Technology Draft.
- Buildings.
- Military Production.
- Formations.
- Battle Resolution.
- Catastrophe.
- NPC/Character State.
- Quest.
- Dialogue.
- Faculties/Checks.
- Knowledge/Semantic Interaction.
- Dungeon/Puzzle.
- Magic.
- Duel.
- Era Transition.
- Historical Record.
- Save/Load.
- LLM Content Foundry.

---

## 188. System ownership

**LOCKED one owner per truth; DEFINED Python/Godot boundary**

| Owner | Responsibilities |
|---|---|
| Python world core | Strategic topology/turns/rounds, Game-Time industry, finite deposits, construction stocks/carts, factions/technology/VP, catastrophe, NPC identities/jobs/relationships, quests, knowledge, inventory, era transitions, off-screen battle resolution, history and complete save envelope |
| Godot runtime | Input, rendering, audio, local movement/collision/navigation, local tactical combat, puzzle mechanisms and Mastermind duel execution |
| Offline content tools | Generate/validate/compile definitions and prose; never participate in runtime truth |

Godot's local battle, puzzle and duel modules own their live encounter state while active. Python grants an encounter ID/version and suspends any competing resolver for the leased entities. Godot returns ordered deltas/checkpoints and one final outcome. Python persists these, applies cross-system consequences and rejects stale/duplicate results. Canonical unit identity, cargo and inventory cannot be independently recreated by a scene.

A newly produced unit at a locally active battle is sent into that encounter once. A destruction command affecting leased units/buildings is routed through the encounter owner and committed once; neither side silently overwrites the other.

Godot owns immediate local movement. Crossing a strategic exit requires an acknowledged journey command. All visits, Waits, quest choices, item transfers and era changes use the same typed command path in the normal game and test harness.

This keeps the existing Godot duel/puzzle strengths while allowing headless Python world simulation and training. It is not a requirement to port every frame-level rule to Python.

---

## 189. Update relationships

**DEFINED transactional order**

Between World Turns, Game-Time quanta advance industrial production everywhere and local owned encounters. At a journey or Wait, stop at a clock boundary; never process a half-applied production tick.

1. Validate the action, settle any outgoing local battle snapshot and calculate its off-screen remainder when leaving it.
2. Commit the wizard's destination (or unchanged node for Wait), then increment World Turn and identify the rotating active faction. This makes a battle at the arrival node eligible for local presentation.
3. Roll 2d6 and credit only eligible Catan goods to node warehouses.
4. Deliver/move all carts one eligible road edge; fulfil recorded delivery contracts exactly once.
5. Complete all fully delivered legal construction in stable active-seat order. Check VP after each atomic completion.
6. The active faction may issue one new construction order and one trade/diplomacy proposal. Any immediately affordable local completion uses the same commit/VP check.
7. Move that faction's disengaged formations up to two nodes. Stop on engagement; calculate off-screen fights, and open local encounter ownership for fights at the wizard's node.
8. Apply scheduled faction catastrophe treatment and, if due, catastrophe draws/outbreak propagation. Terminal catastrophe interrupts immediately.
9. Evaluate NPC/quest/policy consequences. Any VP-changing effect triggers the same immediate check.
10. Mark the active seat complete. If the round is complete, perform one simultaneous technology draft per active faction and start the next round; otherwise advance the seat.

**Immediate means immediate:** after any committed action reaches 10 VP, cancel the remaining old-era steps, freeze local encounters at their current checkpoints and perform §40 once. Do not wait until step 9 or allow a later battle to undo the winner. Unspent cargo/stock stays in its actual state, subject to explicit collapse dispositions.

Era transition itself is atomic. Recompute scores after it, start a fresh turn/round schedule and reproject the current node. It does not grant a second player move, a free old-era draft or extra elapsed seconds.

Wait runs the same World Turn at the same node and does not close a local battle simply for being a Wait. Wizard-duel/modal-pause state rejects travel/Wait until the encounter or screen closes.

---

## 190. Determinism

**DEFINED requirement**

Reproduction requires the initial seed, definition/content version, ordered commands, exact Game-Time advances, saved RNG stream states, and recorded neural-policy actions—not just a seed.

Use separate RNG streams for board generation, Catan dice, catastrophe, content binding, strategic choices and encounters. Rendering and ambient animation cannot consume a gameplay stream. Stable IDs and tie-break orders prevent dictionary iteration changing results.

Use integer/fixed-point economic accounting and preserve fractional production remainders. Local encounters run fixed-step logic; frame interpolation does not determine combat. The off-screen calculation is a declared separate approximation (§60), not expected to match every attended battle's casualties.

Save/replay includes active leases and pause clocks. A paused duel, worker animation or failed transport reconnect cannot add economic time or execute a command twice.

---

## 191. Saveable state

**DEFINED versioned save**

Save:

- schema version, rules/content manifest, world seed and all RNG streams;
- era/cycle, Game Time, turn/round, faction seat schedule and pending transition ID;
- board, resource layers, ownership, roads and persistent local layout overrides;
- local Catan stocks/reservations, cart routes/cargo/delivery IDs and trade contracts;
- industrial assignments/capacities, real legacy stocks and factory progress/remainders;
- factions, relations, technologies/hands/archive, policy version/commitments and VP basis;
- individual units, health, buffs, formations, positions and current battle state/lease;
- catastrophe cubes/types, outbreak counts, deck/discard and current visit-treatment ledger;
- player location, inventory, equipment, colours/slots, Aspects, knowledge and history;
- persistent NPCs/jobs/relationships, quest instances/effect receipts and dungeon/puzzle state;
- Godot-owned encounter snapshots, including an in-progress duel's clock and RNG.

Saving uses a coordinated pause/checkpoint barrier across Python and Godot, then an atomic file replacement and one previous-good backup. Loading validates versions/references before resuming. Wall-clock time while closed is ignored.

The overhaul starts a new save schema. Prototype saves are not silently loaded as compatible or deleted; offer a clear unsupported-version message and a new-game option. Future schema changes use explicit migrations, each tested by continuation equivalence.

IDs of dead/retired entities remain as compact historical reference records. Rebuildable visuals are regenerated from the saved layout seed plus persistent edits, never from a fresh random village on each visit.

---

## 192. Networking

**No online gameplay, multiplayer, account login or runtime LLM.**

Initial deployment is an offline desktop Godot application with a bundled Python sidecar process and runtime. The player is not expected to install Python, run a server or configure dependencies.

Use a versioned, length-framed JSON command/event protocol over a loopback-only local connection, with a random per-launch session token. This is inter-process communication on the same computer, not an internet service. The launcher handles process startup, handshake, timeout, shutdown and bounded restart.

Every mutation has a command ID, session ID and expected state/encounter version. Duplicate commands return their prior result. Bridge failure pauses Game Time and controls; recovery restores the last coordinated checkpoint and never pretends the world advanced.

Mobile-friendly pointer/touch controls are required now. Android/iOS/web packaging is post-MVP: the transport and ownership contracts must allow a future embedded/replacement backend, but the desktop Python sidecar is not claimed to run unchanged on those platforms.

---

# PART XXXIX — DATA-DRIVEN DESIGN

## 193. Static definitions

Must be external data where possible:

- era definitions;
- culture packages (unit/building collections);
- resource tables;
- primary-production counts/rules;
- processing recipes;
- buildings;
- workers;
- technologies/cards/prerequisites;
- units and military-production buildings;
- catastrophe types;
- spells/colours/slot definitions;
- seven Aspect definitions;
- semantic labels;
- NPC/anchor-NPC templates;
- dialogue line banks;
- quest templates;
- puzzle definitions;
- full-cycle legacy rules.

All LLM-produced dialogue/content is compiled into these static game files before release.

---

## 194. Runtime state

Definitions describe types. Runtime records describe persistent instances.

Store ownership/affiliation, resource-layer balances, node stocks/cargo, factory progress, individual worker jobs and unit health/buffs, relationships, goals, technologies, catastrophe, knowledge, quests, history and local deviations.

Rendering objects reference persistent IDs and carry disposable animation state only. The normal game, authored fixtures and generated village tests use the same runtime and projections; a fixture does not become a second quest-state owner.

---

## 195. Content extensibility

Designers/LLM pipeline should be able to add new:

- unit profiles;
- buildings;
- technologies;
- dialogues;
- quests;
- NPCs;
- economic recipes

without engine changes where the mechanics already exist.

---

## 196. Validation rules

Reject nonexistent IDs, invalid era/culture references, impossible tech gates, circular mandatory production routes without a bootstrap, illegal effects, inaccessible mandatory objects, missing quest invalidation routes, and prose that leaks unknown facts.

Check economic namespaces: Catan goods cannot be accidentally consumed as similarly named industrial resources. Every recipe pairs different terrains and has one unique processor/output; full catalogues contain 60 pairs per era with each raw resource appearing in ten pairs.

Validate total primary sites ≤ node capacity ≤ 5, exactly three baseline military factory slots, shared finite conservation, worker/job identity, one entity per soldier/cart, and no duplicated stock between warehouse/cargo/reservation.

Validate clocks and ownership: one journey/Wait equals one turn, no strategic drift from Game Time, no production during a duel, no competing battle resolver, and idempotent result/effect processing.

A valid content schema is not proof of an enjoyable quest or well-balanced economy; those remain playtests.

---

# PART XL — AUTHORING TOOLS

## 197. Required editors

Eventually require:

- economy/dependency viewer;
- technology graph viewer/editor;
- era/culture-package editor;
- quest graph editor;
- dialogue editor;
- semantic-entity inspector;
- puzzle/dungeon tools;
- era-transition inspector.

---

## 198. Debug tools

Expose:

- stocks;
- production requests;
- logistics;
- AI priorities;
- VP;
- technologies;
- armies;
- catastrophe state;
- NPC goals;
- quest state;
- player knowledge.

---

## 199. Visualisation

Priority:

- economy graph;
- road/logistics graph;
- technology dependencies;
- strategic AI goals;
- military movement;
- catastrophe spread;
- semantic-knowledge state.

---

## 200. Content validation

Bulk validation must run before generated content is accepted.
LLM critic passes should supplement rather than replace deterministic validators.

---

# VOLUME XIV — BALANCE

# PART XLI — BALANCE MODEL

## 201. What needs balancing?

Critical relationships:

- VP acquisition speed;
- era duration;
- strong-vs-weak faction recovery;
- resource availability;
- economy throughput;
- transport;
- military production;
- battle attrition;
- technology-draft value;
- catastrophe escalation;
- magical intervention power.

---

## 202. Important ratios

| Economic or pacing relationship | Meaning |
|---|---|
| Catan grants : construction cost | Expansion speed per World Turn |
| Cart capacity/speed : delivery distance | Real construction/trade delays |
| Primary supply : processing : factory demand | Calculated military units per Game-Time second |
| Shared finite balance : extraction rate | Industrial longevity |
| Military loss : replacement rate | War sustainability |
| Legacy : new-era combat stats | Technological obsolescence without deleting units |
| World Turns : completed rounds | Draft and policy cadence |
| Player travel/Wait : catastrophe placement | Strategic opportunity cost |
| Buff duration : local combat duration | Intervention strength |
| Real-time waiting : all-faction production | Stationary-play fairness |

Local worker path length is deliberately absent from the throughput calculation.

---

## 203. Intended asymmetry

The baseline cultures share each era's complete processor catalogue and three unit archetypes. Faction differences emerge from geography, installed capacity, technology, strategy, diplomatic history and player effects.

Future culture-specific content is optional and explicit. Culture can change between eras without changing faction or NPC identity.

---

## 204. Tuning levers

- production-building count by pip value;
- finite deposit size;
- processing recipe ratios;
- transport capacity;
- building/rebuild cost;
- technology-card pool and duplicate count;
- technology hand replenishment;
- neural-network reward shaping / policy selection;
- unit cost and battle strength;
- catastrophe cube placement rate;
- outbreak terminal threshold;
- VP scoring;
- fission AI inputs/reward;
- era finite-resource rebalance;
- friendly wizard-buff magnitudes.

---

## 205. Target outcomes

**DEFINED validation targets; balance remains experimental**

- All policies issue legal actions and seeded unattended runs can reach 10 VP.
- Industry progresses off-screen and respects finite supply without worker-animation dependence.
- Local Catan shortages and cargo disruption have observable construction/trade consequences.
- A wizard can decisively alter a local battle and destroy real assets without acquiring an RTS command interface.
- Multi-faction transitions collapse weak contenders; single-faction eras continue and then split.
- NPCs and active quests remain recognisable across upgrades.
- Catastrophe provides readable, treatable pressure before terminal loss.
- Technology drafts always complete, even with duplicates or unplayable hands.
- Mobile-style pointer controls can operate every required interaction.
- Saving during production, a quest or a duel resumes the same canonical state.

These are acceptance targets to measure; they are not reports that tests have already passed.

---

# VOLUME XV — CONTENT REQUIREMENTS

# PART XLII — CONTENT INVENTORY

## 206. Required actor types

Full game requires:

- 1 persistent wizard;
- recurring rival wizards;
- six initial political factions per new cycle;
- a small ensemble/library of trained strategic neural-network policies;
- one anchor NPC per production building;
- faction leaders and other influential NPCs;
- individually persistent ordinary workers and military units;
- three principal military-unit types per culture package, with later variants/upgrades;
- catastrophe opponent representations for demons, aliens, hostile AI/cyborg systems and nuclear-war content where appropriate;
- potentially very large numbers of generated named NPC/unit profiles stored offline.

Exact full-game counts remain content-production decisions.

---

## 207. Required objects

Baseline content includes quest/puzzle items, focuses/artifacts, five Catan construction goods, 48 era-specific industrial raw definitions and 240 distinct processed outputs across four eras. Similar display names do not merge their IDs.

Power and other non-storable industrial services are declared capacity inputs rather than physical cart cargo. Exact cosmetic variants are content work, not additional economic classes.

---

## 208. Required structures

- Six terrain-linked primary-production archetypes per era, instantiated within the node-wide 1–5-site limit.
- 60 distinct processing-building definitions per era, available to every current culture.
- Three military factory archetypes per era.
- Settlement/city centre, warehouse and civic structures.
- Strategic roads and persistent transport vehicles.
- Upgrades that preserve building identity and legacy processing.
- Dungeon/quest structures and inert collapse-ruin art.

A catalogue entry is a building type, not an instruction to spawn every type at every node. The MVP can prove a reduced recipe set while preserving the full schema.

---

## 209. Required environments

- strategic 19-hex world;
- settlement projection types;
- wilderness nodes;
- caves;
- mines;
- historical structures;
- industrial spaces;
- modern installations;
- alien locations;
- future machine complexes.

---

## 210. Required scenarios

No fixed mission count.
Need:

- tutorial sequence;
- systemic quest templates;
- faction/policy situations;
- catastrophe situations;
- dungeon templates;
- battle situations.

---

## 211. Required narrative

Potentially **100,000+ lines** of dialogue/text at full scale.
The design assumes LLM-assisted production.
Human-written prose at this volume is explicitly not required.

---

## 212. Required audiovisual assets

Use modular 2D top-down sprite/tile families.

Need:

- wizard sprite set;
- NPC/worker/soldier archetypes;
- production/processing/military-building sprites;
- transport sprites;
- prehistoric and Historic MVP tilesets first;
- later Modern/Future tilesets;
- catastrophe overlays/effects;
- magic/duel effects;
- semantic-label UI;
- battle effects;
- era-responsive audio palettes.

Generated unit/NPC profiles should reuse sprite archetypes rather than demanding unique art.

---

# VOLUME XVI — MVP DEFINITION

# PART XLIII — FINDING THE SMALLEST REAL GAME

## 213. Core identity test

The MVP must demonstrate embodied wizard exploration, semantic labels, persistent NPC dialogue, autonomous factions, real carted Catan goods, calculated real-time industry with visible workers, individual-unit warfare, catastrophe, unrestricted local destruction magic, one dungeon/quest and Mastermind duel, travel/Wait turns, and one ordinary era transition with surviving people and quests.

A display-only village with no world consequences or a headless simulation without playable exploration is not the completed MVP.

---

## 214. Core loop requirement

Minimum full loop:
VISIT SETTLEMENT
→ DISCOVER ECONOMIC/SOCIAL PROBLEM
→ INTERACT WITH NPC
→ TRAVEL / EXPLORE
→ WORLD ADVANCES
→ INTERVENE
→ ECONOMY / WAR / CATASTROPHE CHANGES
→ RETURN
→ OBSERVE CONSEQUENCE
→ ERA ENDS
→ SAME PLACE APPEARS TRANSFORMED



---

## 215. Minimum challenge

Need:

- one competing faction;
- one real resource bottleneck;
- one autonomous military conflict;
- demon escalation capable of terminal loss.

---

## 216. Minimum progression

MVP requires one transition:
**Prehistoric → one Historic variant.**
This is essential because persistence-through-history is central identity.

---

## 217. Minimum content

**DEFINED MVP scope**

- One 19-hex board with the six terrain types.
- Two starting political factions in the MVP scenario; the normal full-game setup supports six.
- One shared default culture package in Prehistoric and one in Historic.
- Five Catan goods, real per-node stock, road delivery and construction.
- 1–5 primary sites per occupied node, a tested subset of cross-terrain processors, and three factory/unit archetypes.
- Persistent ordinary workers/anchor NPCs, carts, units and buildings.
- Deterministic heuristic faction policy and a small technology pool exercising seven-card draft behaviour.
- One demon cube/outbreak system including the treatment-per-visit limit and Wait.
- One systemic quest family, one dungeon and one rival-wizard Mastermind duel.
- The seven defined Aspect mechanics with a small authored line bank.
- A complete Prehistoric → Historic transition preserving NPCs/quests and continuing legacy industry.
- Core starter upgrades, inert collapse ruins, legacy-site rebuilding and the mandatory sole-faction fission rule in headless fixtures.
- Coordinated save/load and desktop Godot/Python startup.

Full catalogue coverage, wider narrative content and neural training are subsequent content/implementation phases, not prerequisites for the first playable proof.

---

## 218. MVP exclusions

The MVP does not require culture-specific economic restrictions, trained neural leadership, voluntary learned fission, Modern/Future presentation, pollution/alien/nuclear/machine content, Utopia, repeated complete historical cycles, a 100,000-line corpus, final art, a full technology catalogue or mobile export packages.

The deterministic sole-faction survival/fission safeguard is included even while richer voluntary fission is deferred. The seven Aspect definitions and their basic checks are included; only their extensive writing is deferred.

A reduced recipe set is allowed for the MVP demonstration. Do not encode a permanent ten-recipe culture limit.

---

## 219. MVP start state

Player begins as wizard in prehistoric world.
Nearby:

- labelled settlement;
- people;
- basic economy;
- two autonomous factions;
- early demon pressure.

---

## 220. MVP end state

A faction reaches 10 VP, transition occurs exactly once, collapsed sites become inert ruins, and survivors receive working Historic cores. The wizard enters a transformed place and recognises the same living NPCs, relationships and continuing quest.

The slice also proves that old factories/units remain where appropriate, Catan cargo/stock is conserved, production resumes from saved meters, and save/load does not duplicate a core starter package or reset a catastrophe visit.

The MVP demonstration ends after this first transition; its architecture must not treat that demonstration endpoint as a forced ending of the full game.

---

## 221. MVP definition

The MVP is a small but complete two-era systemic sandbox in which the wizard can explore a generated prehistoric world, understand people and economic activity through semantic labels and dialogue, allow autonomous factions to produce and fight, respond to an escalating demon threat, undertake one dungeon/quest and Mastermind duel, influence events through magic without commanding the strategy layer, and then witness the world reset into a recognisably inherited Historic era after a faction reaches 10 VP.

---

# VOLUME XVII — VALIDATION PLAN

# PART XLIV — DESIGN QUESTIONS REQUIRING PROOF

## 222. Fun-risk questions

- Is watching an autonomous economy interesting from ground level?
- Does indirect war involvement feel empowering rather than passive?
- Does travel create meaningful opportunity cost?
- Do players care about generated NPC goals without a main quest?
- Does observing the same places across eras create emotional payoff?
- Does Mastermind combat remain enjoyable over many encounters?
- Is catastrophe suspenseful rather than annoying?

---

## 223. Technical-risk questions

These are validation experiments against defined rules, not unresolved design choices:

- Does the desktop Python sidecar launch, pause, recover and shut down reliably?
- Does fixed-time industrial accounting remain deterministic at visited and unvisited nodes?
- Are shared finite resources and construction cargo conserved?
- Does Godot/Python encounter handoff preserve unit IDs, damage, buffs and clock state?
- Can a late/duplicate result be rejected without a double reward, casualty or World Turn?
- Can persistent NPCs, quests, objects and local layouts survive upgrades and ruin replacement?
- Do saved in-progress duels and production meters resume without extra elapsed time?
- Are the heuristic/legal-action contracts suitable for later neural training?
- Can offline dialogue fallback cover defined states without inventing facts?
- Can local tactical combat and the declared off-screen approximation remain understandable and computationally bounded?

---

## 224. Content-risk questions

Validate whether the 60-recipe-per-era catalogue remains distinguishable and useful, whether its reduced MVP routes teach the economy, and whether future culture variants add meaningful differences.

Precompiled dialogue must cover era changes, displaced workers, resolved-by-world problems and destroyed targets. Evaluate repetition and factual accuracy before expanding the corpus.

Large counts of persistent identities need compact records and reusable voices/sprites, not a unique hand-written biography or image for every person.

---

## 225. Balance-risk questions

Measure:

- VP snowballing and sufficient legal routes to reach 10;
- catastrophe cadence versus travel/Wait and three-hex treatment;
- army accumulation while stationary, including rival production;
- old/new unit strength ratios;
- industrial flow fairness and finite depletion;
- recurring technology drafts and inert duplicates;
- sole-faction fission and six-faction limit;
- unrestricted local wizard destruction and timed buff stacks;
- off-screen instant resolution versus attended reinforcement opportunities.

Do not disguise a balancing change as a bug fix. Change a tunable value or deliberately revise the relevant rule.

---

## 226. Usability-risk questions

Can players understand:

- why a factory stopped;
- why a war began;
- why an army is weak;
- why catastrophe is worsening;
- what their intervention changed

without strategy dashboards?
This is probably the largest human-interface validation question.

---

## 227. Prototype questions

### Attention

Prototype two simultaneous crises separated spatially.
Success if players feel a genuine prioritisation dilemma.

### Economy readability

Prototype one three-step production chain visible from street level.
Success if player can identify bottleneck without debug UI.

### Autonomous battle

Prototype AI-vs-AI fight with wizard intervention.
Success if player feels important but not in direct command.

### Generated quest

Generate quest from a real shortage.
Success if players care about the human problem and recognise the systemic consequence.

### Era transition

Run same settlement before/after reset.
Success if players recognise place and history while accepting the mechanical reset.

### Catastrophe

Run escalating demons.
Success if terminal loss feels foreseeable and deserved.

---

# VOLUME XVIII — SYSTEM DEPENDENCIES

# PART XLV — DEPENDENCY MAP

## 228. System dependency graph

| System | Reads / requires | Produces / enables |
|---|---|---|
| World identity and clocks | Definitions, seed, commands | Stable IDs, Game Time, turns/rounds |
| Construction/trade | Hex rolls, node ownership, roads | Local goods, real cargo, delivered builds |
| Industry | Resource layers, installed buildings, Game Time | Shared depletion, allocated flows, individual units |
| Faction policy | Legal observation, economy, diplomacy | Validated strategic orders |
| Technology | Completed rounds, hands, research | Typed capability modifiers |
| Military | Units, orders, terrain, clock/encounter ownership | Battles, casualties, asset destruction |
| Catastrophe | Turn cadence, typed hex state | Shutdown, transit bans, treatment, terminal loss |
| Persistent local projection | Entity IDs, saved layout, knowledge | Readable people/buildings/targets |
| Quests/dialogue | Real causes, NPCs, knowledge, Aspects | Validated choices and once-only effects |
| Puzzle/duel encounters | Context, local state, pause lease | Saved encounter outcomes |
| VP / era transition | Committed scoring and capacity | Collapse/fission, cores, continuing legacy state |
| Save/load | Every authoritative owner and version | Consistent resumable checkpoint |

The Godot/Python bridge carries these contracts; it is not another owner of world truth.

---

## 229. Core-loop dependency chain

WORLD / TIME
→ SEMANTIC INTERACTION
→ FACTION STATE
→ ECONOMY
→ LOGISTICS
→ WAR
→ CATASTROPHE
→ NPC / QUEST PROJECTION
→ PLAYER INTERVENTION
→ CONSEQUENCE
→ VP
→ ERA TRANSITION



---

## 230. Content dependencies

Before mass content generation:
ERA DEFINITIONS
→ CULTURE-PACKAGE DEFINITIONS
→ RESOURCE / ECONOMY SCHEMAS
→ TECH SCHEMA
→ UNIT ARCHETYPES
→ NPC SCHEMA
→ QUEST SCHEMA
→ DIALOGUE SCHEMA
→ LLM GENERATION

Generating prose before these are stable creates waste.

---

## 231. Highest dependency systems

Highest architectural dependency:

1. Clock/pause authority and World Turn transaction.
2. Persistent IDs and Python/Godot command/encounter ownership.
3. Separation of construction cargo from industrial capacity.
4. Resource layers, rate allocation and individual military output.
5. Knowledge-filtered local projection and persistent people.
6. Quest/effect runtime and invalidation branches.
7. Era transition, core bootstrap, collapse ruins and sole-faction recovery.
8. Coordinated versioned save/load.
9. Technology and legal faction-policy interfaces.
10. Offline content validation.

Define these contracts before mass content generation. A long list of classes without their state ownership and tests is insufficient.

---

# VOLUME XIX — DESIGN DECISION REGISTER

## DEC-001 — Player relationship to strategy simulation

**Chosen:** embodied indirect influence; no worker or army command.  
**Status:** LOCKED.

---

## DEC-002 — Strategic time

**Chosen:** Game Time advances industry globally; World Turns advance only through travel or Wait; one rotating active seat per turn and one draft per faction per completed round. Wizard/hazard duels pause the whole world but run their own clock.
**Status:** LOCKED user timing choices; clock defaults DEFINED in §31.

---

## DEC-003 — Era ending

**Chosen:** the first faction to reach 10 VP immediately ends the era for everyone, including mid-round.  
**Status:** LOCKED.

---

## DEC-004 — Collapse

**Chosen:** in a multi-faction era, collapse all below 5 VP and one lowest-scoring faction using deterministic ties. A sole faction is exempt from self-elimination and must split at the next transition. Collapsed operational sites become mechanically inert ruins.
**Status:** LOCKED user exception and ruin treatment; tie/recovery defaults DEFINED.

---

## DEC-005 — Fission

**Chosen:** voluntary fission remains a strategic policy choice requiring four sites and respecting the initial six-faction ceiling. Mandatory sole-faction fission is an engine rule. Pair the best four sites compactly; assign legacy assets by nearest core; use §40's undersized-split recovery.
**Status:** DEFINED, with neural policy quality to be validated later.

---

## DEC-006 — Era reseeding

**Chosen:** rank theoretical capacity, upgrade two cores per survivor/successor, preserve living NPCs and active quests, keep other surviving buildings/units/stocks operational. Core facilities receive an explicit starter upgrade/package; legacy-site upgrades use delivered Catan goods.
**Status:** LOCKED continuity and rank basis; startup details DEFINED.

---

## DEC-007 — Culture

**Chosen:** culture is an era-specific collection of units and buildings, not an immutable identity. A political faction may adopt a new culture package each era. Initial culture alternatives are deferred until the MVP works.  
**Status:** LOCKED.

---

## DEC-008 — Historical cycle

**Chosen:** Prehistoric → Historic → Modern → Dystopian Future → Prehistoric, repeating without a maximum cycle count. Utopia remains a later extension.  
**Status:** LOCKED for current build.

---

## DEC-009 — Full-cycle persistence

**Chosen:** preserve geography, numbers, wizard memory/progression, living NPC identities/relationships, active quests and explicit legacy objects. Reset political competition to six new factions; obsolete strategic organisations become inert history/scenery unless a specific relic rule preserves an entity.
**Status:** DEFINED full-cycle interpretation, distinct from ordinary era continuity.

---

## DEC-010 — Terminal loss

**Chosen:** catastrophe is the only ordinary terminal loss. Eight outbreaks in the current era triggers one Game Over event; successful era transition resets the active counter while retaining Chronicle totals and surviving hazards.
**Status:** LOCKED loss structure; counter scope DEFINED and threshold TUNABLE.

---

## DEC-011 — Catastrophe identities

**Chosen:** Prehistoric/Historic demons; Modern pollution + aliens; current Future nuclear war + hostile AI/cyborgs; optional later Utopia returns to demons.  
**Status:** LOCKED for current path.

---

## DEC-012 — Economy

**Chosen:** separate five dice-produced, cart-transported Catan goods from twelve industrial raw types per era. A node has 1–5 total primary sites, using its best adjacent pip count. Shared finite layers and installed processors determine three military factory rates in Game Time. Worker motion is illustrative.
**Status:** LOCKED user economy/identity decisions; rate formulas/default capacities DEFINED.

---

## DEC-013 — Technology

**Chosen:** seven-card rotating hands, one simultaneous pick per faction per World Round, redeal after seven picks. Unplayable picks enter a research archive; activate when prerequisites are met. Non-stackable duplicates remain inert. No cost/trade/theft/copy.
**Status:** DEFINED, including former hand-replenishment question.

---

## DEC-014 — Strategic AI

**Chosen:** deterministic heuristic first; later a seeded three-policy neural library with one leadership policy per faction/era. All use the same legal-action/observation contract. Engine rules override illegal choices. Training/evaluation defaults are in §§120–122.
**Status:** DEFINED; policy competence requires experiments.

---

## DEC-015 — Magic progression

**Chosen:** quest rewards increase spell colours and Mastermind slots. Era does not change magic mechanics.  
**Status:** LOCKED.

---

## DEC-016 — Dialogue Aspects

**Chosen:** Reason, Empathy, Authority, Guile, Resolve, Curiosity and Wonder, scored 0–5 from an initial 1. Deterministic checks use explicit evidence/relationship modifiers; once-only narrative effects change scores.
**Status:** DEFINED default, closing the names and mechanics question.

---

## DEC-017 — Narrative generation

**Chosen:** all LLM content is generated offline, validated and written into game files. No runtime LLM or internet dependency. Runtime uses conditional pre-generated banks/templates.  
**Status:** LOCKED.

---

## DEC-018 — Visual presentation

**Chosen:** 2D top-down sprites, 16×16 terrain, 16×24 characters, four directions, responsive labels and single-pointer/touch controls. Desktop packaging first; mobile controls now, exports later.
**Status:** LOCKED direction; prototype dimensions DEFINED/TUNABLE.

---

## DEC-019 — Ending

**Chosen:** history can continue indefinitely, completed cycles are recorded, and catastrophe ends the run. Some quests may offer explicit ending outcomes. No generic retirement/voluntary death.  
**Status:** DEFINED.

---

# VOLUME XX — DEVELOPMENT-HANDOFF METADATA

# PART XLVII — SYSTEM HANDOFF RECORDS

## SYSTEM — Strategic World Simulation

**Purpose:** coordinate persistent world truth, clocks, legal faction actions and immediate era transitions.
**Status / MVP:** DEFINED / CORE MVP.
**Dependencies:** stable IDs, topology, command protocol, definitions, RNG streams and local encounter leases.
**Runtime:** turns/rounds, Game Time, seats, factions, scoring, pending commands and transitions.
**Tests:** movement/Wait exactly once, paused-world invariance, immediate mid-turn 10 VP, stale/duplicate rejection, deterministic continuation, sole-faction recovery.
**Done:** normal play and headless fixtures use the same rules and can complete a valid era transition without losing people or cargo.

---

## SYSTEM — Semantic Knowledge Interaction

**Purpose:** Make a complicated world interactable through simple labels.
**Status:** DEFINED and partly existing.
**MVP:** CORE MVP.
**Dependencies:** entity IDs, player location, knowledge state.
**Dependants:** dialogue, magic targeting, quests, investigation.
**Human validation:** critical.
**Definition of done:** all important local entities can be observed and contextually interacted with through knowledge-dependent labels.

---

## SYSTEM — Settlement Economy

**Purpose:** support actual construction/trade logistics and calculated industry beneath visible settlement activity.
**Status / MVP:** DEFINED / CORE MVP.
**Rules:** five local Catan goods; persistent cargo carts; twelve industrial raw types/era; shared finite hex layers; node-wide 1–5 primary capacity; all 60 recipes available per culture; three real-time military factory meters; persistent workers whose paths do not drive output.
**Tests:** namespaces, finite conservation, capacity allocation, frame-independent output, simultaneous extraction, worker path independence, building destruction, legacy-layer continuation and save-resume meters.
**Done:** a real shortage/destruction changes production and dialogue while a decorative path obstruction does not.

---

## SYSTEM — Technology Draft

**Purpose:** divergent capability growth through rotating hands.
**Status / MVP:** DEFINED / MVP SUPPORTING.
**Rules:** §§114–115, including archive, duplicates, hand refresh, simultaneous selection and singleton passing.
**Tests:** one pick per round, seven-pick refresh, empty legal-choice set, prerequisite activation, duplicate caps, transition discard and fission research inheritance.
**Done:** every configured faction count completes a draft without an undefined state.

---

## SYSTEM — Military Simulation

**Purpose:** convert calculated industry into persistent units and real local tactical conflict.
**Status / MVP:** DEFINED / CORE MVP.
**Rules:** three factories, one persistent unit per completion, two-node strategic movement on active turns, Godot local positions/range/terrain, Python departure/off-screen calculation, wizard immunity and any-unit/building destruction, stacking timed buffs.
**Tests:** no strategic travel from seconds alone; valid movement limits; casualties/health/buffs preserved across handoff; no duplicate resolver; friendly/neutral targeting allowed; immunity; expiry pause; actual facility/cargo loss.
**Done:** the same battle participants survive arrival/departure/save boundaries; the difference between local tactics and off-screen approximation is explicit.

---

## SYSTEM — Catastrophe

**Purpose:** distributed disruption and the ordinary terminal-loss condition.
**Status / MVP:** DEFINED / CORE MVP, demons first.
**Rules:** §166: 0–3 typed cubes, any cube blocks source production/civilian transit, stable propagation with at most one outbreak per hex per event, eight outbreaks per era, cadence by difficulty.
**Wizard:** one successful cube removal per adjacent hex per visit, at most three; Wait/reload does not refresh; duel pauses all world clocks.
**Tests:** fourth-cube chains, cyclic propagation, terminal interruption, shared hex treatment, visit persistence, pollution exclusion and era-counter rollover.
**Done:** predictable seeded pressure can be treated, affect industry/cargo and end the run once.

---

## SYSTEM — Era Transition

**Purpose:** transform political/economic era while preserving living people and place.
**Status / MVP:** DEFINED / CORE MVP.
**Rules:** §40, including immediate winner, theoretical ranking, deterministic collapse ties, inert ruins, core startup, legacy industry, continuing quests, asset assignment and sole-faction mandatory split.
**Tests:** all faction-count edge cases; 10 VP interruption; starter packages once; two/four-core selection; no duplicate IDs; no quest reset; old factories still produce old units; collapsed ruin has no mechanics; costs delivered for rebuilding.
**Done:** a transformed Historic settlement is playable with the same people/quests and coherent retained state.

---

## SYSTEM — Dialogue / LLM Content Foundry

**Purpose:** provide large-scale reactive dialogue without runtime AI dependency.

**Design status:** DEFINED conceptually.

**MVP status:** MVP SUPPORTING; mass generation POST-MVP.

**Dependencies:** NPC schema, building anchor NPCs, seven Aspects, world facts, quest state, knowledge, faction/era context.

**Generation model:** all LLM text is produced offline, validated and stored in the game files. Runtime selects precompiled conditional line banks/templates and can substitute safe variables such as names/counts.

**Validation:** schema, canon, knowledge, state-write legality, repetition, tone/quality.

**Definition of done:** the shipped game can run entirely offline and cover defined runtime narrative states without inventing simulation facts.

---

## SYSTEM — Dungeon / Puzzle

**Purpose:** turn a world problem into direct exploratory play with persistent consequences.
**Status / MVP:** DEFINED / CORE MVP.
**Owner:** Godot's local mechanism runtime under an encounter ID; Python owns persistent inventory, quest/effect receipts and saved snapshot.
**Rules:** explicit mechanism conditions/effects, safe mandatory-object recovery and invalid-target branches.
**Tests:** solvability of the bounded MVP state space, no duplicate items, save/revisit continuity, destroyed-building route recovery, duel/modal pause of timed hazards and once-only world outcomes.
**Done:** one playable dungeon/quest uses the normal world interface and changes canonical state.

---

## SYSTEM — Mastermind Duel

**Purpose:** personal magical deduction distinct from faction combat.
**Status / MVP:** existing core to retain/adapt / CORE MVP.
**Owner:** Godot encounter runtime with saved RNG/ruleset; Python applies outcome once.
**Rules:** existing four-slot/six-colour/ten-cast baseline; all world clocks freeze during the duel; quest progression adds supported colours/slots; ordinary loss uses safe recovery.
**Tests:** preserve existing feedback/rules tests; add world-clock freeze, save mid-duel, stale result rejection, once-only cube removal/reward and safe recovery fallback.
**Done:** an end-to-end duel behaves identically when entered from a rival, quest or supported catastrophe.

---

# PART XLVIII — CONTENT HANDOFF RECORDS

## CONTENT TYPE — Era Culture Package

**Purpose:** provide compatible building/unit data and visual identity for an era.
**Required data:** stable package/era ID, all 60 processor references, primary definitions, three military factories/units, technology compatibility, upgrade mappings and visual assets.
**MVP:** one default Prehistoric and one Historic package, exercising a reduced recipe subset while allowing full-catalogue access.
**Later:** explicit culture-specific bonuses/substitutions/restrictions.
**Validation:** unique valid input pairs, output IDs, referenced resources, working starter routes and no ten-recipe hard-code.

---

## CONTENT TYPE — Unit Profile

**Purpose:** historical/factional identity for one military archetype.
**Required data:** stable definition ID, era, archetype, health, attack, period, speed, range, armour, supply recipe, permanent technology modifiers and visual family.
**MVP quantity:** six military definitions—three per implemented era—plus separate wizard/hazard encounter definitions.
**Runtime:** each manufactured unit receives its own ID, health, location and timed modifiers.
**Later:** many named/visual variants can reuse the same mechanics.

---

## CONTENT TYPE — Dialogue Set

**Purpose:** contextual social experience.
**Required data:** speaker, world facts, relationship, knowledge, goal, allowed state writes.
**MVP quantity:** hundreds of lines.
**Full quantity:** potentially 100,000+.
**LLM generation:** YES.
**Human quality judgement:** sample/major content.

---

## CONTENT TYPE — Technology Card

**Purpose:** change declared faction capabilities.
**Required data:** ID, era, allowed predecessor IDs, typed effects, repeatability/cap, artwork/text keys and activation scope.
**MVP:** six cards per implemented era: primary throughput +10%, processor throughput +10%, factory ceiling +10%, cart capacity +1, unit health +10% and unit attack +10%. Throughput/combat cards can stack to three copies; cart capacity to three added goods. Historic versions each accept any of the two related Prehistoric predecessors.
**Pool:** weighted sampling with replacement to support seven-card hands; duplicates follow §114.
**Later:** larger content catalogue using the same schema.

---

## CONTENT TYPE — Quest

**Purpose:** translate a real simulation condition into a human-scale problem.
**Required data:** template/version, cause predicate, binding rules, persistent NPC/site references, 2–5 states, conditions, choices, typed effects, invalid-target branches, era-continuation behaviour and dialogue keys.
**MVP:** one rich systemic family with at least two valid solutions, a world-resolved outcome and a loss/destruction contingency.
**Validation:** reachable completion/consequence routes, safe required-item recovery and once-only effect IDs.

---

# VOLUME XXI — REUSABLE DESIGN RECORDS

# APPENDIX A — GENERIC SYSTEM RECORD

Each system record contains: purpose; design rule IDs; responsible runtime/language; authoritative state; read-only dependencies; commands accepted; events emitted; clock; RNG stream; static definitions; saved fields/version; invariants; failure/recovery; MVP status; performance budget; unit/integration/manual acceptance checks.

Explicitly state whether it can change VP, catastrophe, inventory, entity ownership or a local encounter lease. List user-visible feedback and the systems that consume its events.

---

# APPENDIX B — ACTOR RECORD

Required fields: definition ID; instance ID; actor kind; creation/current era; faction or displaced status; culture/appearance; role; job/workplace; goals; location; knowledge; relationships; dialogue profile; semantic labels; permitted interactions; destruction/duel contract; quest references; ordinary-era and full-cycle dispositions.

Military records additionally define health, combat stats, order/group, buffs and encounter ownership. Ordinary workers retain identity even when their job changes or their visual node is unloaded.

---

# APPENDIX C — ITEM RECORD

Required fields: definition/instance ID; era; purpose; source; stackability; ownership/location; semantic labels; inventory/equipment rules; allowed uses; puzzle/quest bindings; supported effects; recovery route; ordinary-era and full-cycle persistence.

An object referenced by an active quest cannot be silently regenerated with a different ID.

---

# APPENDIX D — BUILDING RECORD

Required fields: definition/instance ID; era/culture access; node/footprint; primary-slot or factory-slot use; economic archetype; construction/repair cost; technology; source-layer binding; input/output rate definitions; job/anchor NPC; actual health/capacity; visual activity; catastrophe effects; upgrade mapping; destruction consequences; saved state.

Declare whether the building is a centre, warehouse, primary site, processor, military factory or narrative structure. Inert ruin art is not an operational building record.

---

# APPENDIX E — RESOURCE / WARE RECORD

Required fields: stable ID; display name; namespace (Catan good / industrial material / industrial service); era/cycle layer if applicable; terrain; finite/renewable status; unit/rate precision; source; extraction rules; storage eligibility; shipment eligibility; processors/consumers; catastrophe effect; rollover disposition.

Do not infer compatibility from a shared display name. Power and similar services are capacity inputs, not physical cargo.

---

# APPENDIX F — PRODUCTION CHAIN RECORD

Required fields: recipe ID; era; two distinct-terrain raw inputs and ratios; unique processor/output; compatible culture references; raw/processor rate limits; eligible military consumers; allocation priority; finite reservations; technology modifiers; shortage reason; anchor NPC narrative cues; upgrade mapping; validation cases.

Document the rate calculation separately from its worker/animation depiction. The latter must not introduce additional costs or timing.

---

# APPENDIX G — PUZZLE RECORD

Required fields: puzzle ID/version; systemic origin; strategic node and local area; mechanisms; initial state; actions; conditions/effects; item bindings; completion/consequence states; recovery routes; clock/pause behaviour; saved fields; semantic labels; world outcome; automated solution trace and manual readability check.

Every mandatory object or route has a defined response to destruction, displacement or era upgrade.

---

# APPENDIX H — LEVEL / MAP RECORD

Required fields: area ID; strategic node/adjacent hexes; era/culture; projection seed; stable layout anchors; persistent entity bindings; exits/arrival points; navigation/collision; battle terrain; economic/political/catastrophe context; important item positions; legacy overlays; local overrides; regeneration and save rules.

Test reachability of exits and required interactions. Decorative worker paths do not become economic dependencies.

---

# APPENDIX I — MISSION / SCENARIO RECORD

Used for tutorials and reproducible tests rather than a compulsory campaign.

Record scenario ID/version, seed, definition manifest, initial world state, Game Time/turn/round, player location/knowledge, factions/cargo, local encounter/quest state, scripted commands and clock advances, expected outcomes, allowed failure branches and reset/exit behaviour.

---

# APPENDIX J — FACTION / CLASS RECORD

Keep political faction state separate from culture definitions.

Faction: ID, lineage, era, core sites, all owned assets, diplomacy, policy/version, commitments, research/hands, VP basis, collapse/fission flags and history.

Culture: ID/era, all 60 baseline processor references, primary archetypes, three military factories/units, technology compatibility, visual package and upgrade mappings. Future restrictions must be explicit fields, not missing data treated as an accidental rule.

---

# APPENDIX K — AI BEHAVIOUR RECORD

Record policy ID/version, observation schema, legal action contract, heuristic score or model artifact, seeded selection, inference deadline/fallback, deterministic tie-break, training reward/evaluation seeds, known limitations and debug explanation.

For a player-influenced policy field, state the typed effect, allowed range, duration clock, expiry, event source and whether it can affect voluntary fission. Mandatory survival/fission safeguards cannot be disabled by a policy.

---

# APPENDIX L — DESIGN VALIDATION RECORD

Record testable hypothesis; the selected baseline rule; why it may fail; fixture/seed and content version; commands/time advances; expected machine-checkable result; human experience question; metric; result; defect/revision decision and acceptance date.

Use it for gameplay and technical risks. A selected baseline is not evidence that the experiment passed, and a passing unit test is not evidence that a scene is enjoyable.

---

# VOLUME XXII — FINAL DESIGN COMPLETENESS AUDIT

This is a **design coverage audit**, not a claim that code or tests are complete.

| Area | v0.3 disposition |
|---|---|
| Product, player authority and MVP | Defined; desktop first, touch-friendly controls |
| Two clocks plus duel clock | Defined, including pause, Wait and turn ordering |
| Two economic ledgers | Defined: real Catan cargo and calculated industry |
| Primary counts and shared deposits | Defined: node total 1–5, best adjacent pips, shared finite layers |
| Workers, units, carts and buildings | Persistent identity and ownership rules defined |
| Processing catalogue | Complete 60-per-era access for every current culture |
| Local/off-screen combat | Real local tactics; explicit departure approximation and continuity |
| Wizard power and recovery | Any ordinary unit/building destruction; faction-military immunity; duel-only ordinary defeat |
| Catastrophe | Placement, visits, cube removal, rollover and terminal ordering defined |
| VP, construction and technology | Concrete baseline rules and edge cases defined |
| NPCs, quests, knowledge and Aspects | Persistence, invalidation, checks and seven definitions supplied |
| Era transition and collapse | Ranking, bootstrap, inert ruins, singleton split and full-cycle distinction defined |
| Runtime ownership and saving | Python/Godot responsibilities, protocol and coordinated checkpoints defined |
| Neural leadership | Baseline/future interface, training and evaluation defaults selected |
| Art and controls | Buildable prototype defaults; quality validation pending |
| Future content | Explicit post-MVP scope; no unanswered MVP prerequisite |

Remaining work is code/task/test planning, implementation, content population, experiments and tuning. Any later change must update its rule, affected definitions, acceptance cases and save migration.

---

# RESOLVED DESIGN REGISTER — v0.3

All former open questions now have a selected answer. These defaults may be revised deliberately after testing; they are not blank decisions left to an implementation agent.

### O-01 — Neural strategic AI training — RESOLVED

Use the versioned legal-action/observation contract and heuristic MVP. Later train a candidate-action scorer through imitation then actor-critic improvement, with §122's explicit rewards/evaluation. Keep three accepted policies and select one per faction/era. Record actions for replay. Mandatory fission remains an engine rule.

### O-02 — Fission legacy ownership — RESOLVED

Nearest-successor-core assignment by graph distance; stable-ID ties. People and stocks stay with their settlement; units follow home sites; cargo remains attached to its cart until an explicit reroute/delivery. Core pairing and undersized mandatory splits follow §40.

### O-03 — Technology hand replenishment — RESOLVED

Seven simultaneous round picks, then deal seven new cards from the weighted era pool with replacement. Archive inactive picks and non-stackable duplicates. Era changes discard leftover hands.

### O-04 — Processing catalogue — RESOLVED BY USER

All cultures access all 60 valid processors per era. No ten-recipe restriction. Local installation is a separate decision. Future culture-specific content uses explicit extension data.

### O-05 — Mass-battle calculation — RESOLVED

Individual health/stats, deterministic target selection, shared damage formula and current-state handoff are in §60. Off-screen resolution is instantaneous global-time-wise and freezes active buff modifiers for its calculation. It preserves losses and identity but does not promise identical outcomes to attended tactics.

### O-06 — Seven Aspects — RESOLVED

Reason, Empathy, Authority, Guile, Resolve, Curiosity and Wonder. Scores/checks/progression/retry behaviour are in §48. No new conventional HP/mana/XP block.

### O-07 — Culture-package content — RESOLVED FOR BASELINE

One shared-access package per implemented era with three unit archetypes. Alternative culture-specific bonuses, restrictions and aesthetics are post-MVP expansions, not required for architecture.

### O-08 — Utopia extension — RESOLVED AS POST-MVP CONTRACT

Default Future remains dystopian. The future extension uses a saved next_future_path flag, set only by a validated explicit quest outcome before Modern → Future transition. Snapshot that flag at transition. With the Utopian content pack installed, choose its package/catastrophe table; otherwise the flag-setting outcome is not offered. Do not show an apparently successful Utopian choice that silently loads dystopia. Returning demons use the same cube/treatment system. This feature is not in the MVP.

### O-09 — Quest grammar — RESOLVED BASELINE; QUALITY TO VALIDATE

Use the eight declared families and §141's common state/effect contract. Implement one rich family first. Variation comes from real cause, bound people and competing outcomes. Dedupe by cause/affected entity; supply invalid-target and world-resolved branches. Test variety before scaling the library.

### O-10 — Anchor and ordinary NPC depth — RESOLVED BY USER

Every ordinary worker has a persistent identity/job. Its workplace anchor can be that same worker. A job change preserves the original person and creates a replacement when needed. Bigger dialogue roles add data to the same identity. Living people survive era changes.

### O-11 — Battlefield defeat — RESOLVED BY USER

Faction military cannot harm the wizard. Remove the overwhelmed-on-battlefield defeat/teleport rule. Keep ordinary loss/recovery for wizard/hazard duels and terminal catastrophe death.

### O-12 — Art prototype — RESOLVED DEFAULT

16×16 terrain, approximately 16×24 characters, four directions, integer pixel scaling, shared animation families and scalable pointer/touch controls. Labels focus on nearby/selected actors. Final quality is tested, not presumed.

### Additional operational defaults — RESOLVED

- Wait advances one strategic turn, no artificial Game-Time interval and no renewed treatment allowance.
- Treatment removes one cube from each successfully challenged adjacent hex, up to three different hexes per visit.
- Primary capacity uses the best adjacent pip count and is total per node.
- Shared deposits include their era/cycle layer; old layers are not overwritten.
- Five construction goods remain usable across ordinary eras.
- Core bootstrap upgrades existing sites and adds a once-only starter package.
- The solo survivor is protected and splits at the following transition; no-faction recovery is non-terminal.
- Active quests retain IDs and use defined world-resolved/invalid-target branches.
- No encumbrance; one focus and one artifact equipment slot.
- Mobile controls are required; a mobile Python deployment is not promised.
- Old prototype saves are retained but not assumed compatible.
- Multiplayer, online simulation and runtime LLM use remain excluded.

---

# VOLUME XXIII — ACCEPTANCE CONTRACTS FOR THE CODE PLAN

These are expected behaviours for future implementation. No test results are claimed here.

| Contract | Minimum acceptance case |
|---|---|
| Time and industry | Advancing 60 unpaused seconds gives identical output with different render-frame patterns; travelling is not required for production. |
| Strategic movement | No army changes node from seconds alone; one legal activation moves at most two edges; Wait uses the same World Turn. |
| Duel pause | During a 60-second duel, world Game Time, output, other battles and buff durations remain unchanged. |
| Two ledgers | Catan dice change only node construction goods; industrial flow changes only its own source/progress records. |
| Shared finite source | Two nodes contest the last extraction unit without a negative balance or duplicate military progress. |
| Worker representation | Blocking a worker's visual route does not change throughput; a real building destruction does. |
| Persistent identities | A quest moves a worker; their ID/relationships survive and the replacement receives a different ID. |
| Cargo | Source stock, loaded cargo, delivered stock and recorded losses conserve quantity; a duplicate delivery cannot pay twice. |
| Catalogue | Full data has 60 unique unordered cross-terrain pairs per era, 60 processor IDs and 60 outputs; each raw type appears ten times. |
| Military identity | One factory completion creates one unit ID; entering/leaving a scene cannot clone it or restore casualties. |
| Wizard actions | Friendly, neutral and enemy unit/building targets are destructible; faction military cannot reduce wizard health. |
| Catastrophe visit | Treat three different adjacent hexes once each; repeated treatment, Wait and reload cannot refresh spent allowances. |
| Catastrophe cascade | A cyclic spread visits each outbreaking hex once and emits terminal loss exactly at the configured limit. |
| Immediate era end | A 10-VP construction stops the remainder of that old-era turn and grants no extra technology draft. |
| Transition continuity | Theoretical ranking selects cores; NPC/quest IDs persist; old non-core factories still produce old units. |
| Ruins | Collapsed ruin art contributes no ownership, collision, output, loot or placement restriction. |
| Solo faction | A lone faction survives, can play its next era and obligatorily produces two successors at its transition. |
| Technology | A seven-round draft cycle completes with one faction, duplicates and entirely inactive hands without skipping a pick. |
| Quest concurrency | Two outcomes targeting the same problem revalidate; item/reward effects apply at most once. |
| Save and bridge | Mid-production, mid-quest and mid-duel saves resume exactly; stale/duplicate commands cannot advance time or repeat effects. |
| Touch usability | A single pointer can move, interact, choose, target, Wait, pause and save without hover/right-click/keyboard dependence. |

Use unit tests for isolated rules; integration tests for cross-system transactions and encounter handoff; seeded/property tests for conservation, generation and replay; Godot headless/client checks for scene contracts; and human playtests for dialogue quality, navigation, battle readability and enjoyment. Tests for implementation details alone do not replace these behavioural contracts.

---

# FINAL HANDOFF STATUS

The v0.3 design is ready to become a traceable code, object, data and test plan. The user's new rules are integrated throughout; the former open register is resolved with explicit defaults.

The implementation plan should map every rule to its owning system, persistent data, command/event interface, dependencies, tests and acceptance criterion. Inventory existing code as retain/adapt/replace/retire. Do not maintain separate production and fixture quest engines.

Recommended proof sequence:

1. Stable IDs, two clocks, pause rules, typed commands and coordinated save envelope.
2. Python/Godot desktop bridge with a deterministic fixture and mobile-friendly controls.
3. Board, local Catan stocks, persistent carts, legal construction and heuristic factions.
4. Industrial capacity/depletion and three Game-Time factory meters, with visible persistent workers.
5. Individual military units, local tactics, wizard intervention and off-screen handoff.
6. Catastrophe placement/treatment/terminal behaviour and the Wait action.
7. Persistent local projection, seven Aspects, one systemic quest and one dungeon/duel.
8. Immediate 10-VP transition, inert ruins, core bootstrap and continuing people/quests.
9. Legacy upgrades, sole-faction safeguards and regression fixtures.
10. Wider recipe/narrative content, neural training and later eras after the integrated MVP is validated.

This is a design update and future acceptance specification. It does not claim that the existing repository already implements these changes.

---