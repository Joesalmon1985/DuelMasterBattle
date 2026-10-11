# DuelMasterBattle — Open Design Decisions
## Extract from working v0.4 specification (11 October 2026)

**Not approved.** Decisions below are proposals for discussion. Do not silently mark any as locked. The master specification contains the detail and underlying source conflicts.

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

