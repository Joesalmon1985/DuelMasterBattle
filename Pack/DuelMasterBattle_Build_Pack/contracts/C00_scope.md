# C00 — Scope, authority and completion

Build-pack v1.0, 16 September 2026. Controlling design: [GDD v0.3](../source/GDD_v0.3.md), especially §§9, 188–192, 213–231 and Volume XXIII. This is a specification for future work. No repository audit, game implementation, training or gameplay test is claimed complete.

## Source precedence

Use current explicit user instructions, then the attached v0.3 LOCKED rules, then v0.3 DEFINED rules, then the implementation defaults in this pack. Earlier conversational class sketches are historical suggestions. In particular, do not implement the earlier all-GDScript world, physically delivered industrial production, ten processors per culture, aggregated soldier identities, battlefield wizard defeat, or NPC replacement on era change.

Every source section is mapped in [the coverage register](../reference/source_coverage.json). The unchanged source is included for disputed details; task workers normally read their card and named contract only. A genuine contradiction goes into a short decision record identifying both rules and the affected test. Do not silently resolve it by deleting an acceptance test.

## Finish lines

| Milestone | Required result |
|---|---|
| Integrated MVP | Playable two-faction Prehistoric → Historic sandbox, real Catan cargo, industry, soldiers, workers, magic, demons, quest, puzzle, duel, persistent people and saves |
| Full baseline game | Six-faction start; all four eras and repeatable Future → Prehistoric cycles; 240 processor definitions; all five catastrophe types; eight quest families; offline narrative; three accepted trained leadership policies; functional authoring/debug tools; coherent audiovisual families; packaged Windows desktop game |
| Deferred extensions | Utopia content, additional culture packages, mobile/web exports, multiplayer, full voice acting, very large narrative/profile expansion |

The GDD's potentially 100,000+ lines is an expansion ambition, not a fixed release minimum. The full baseline content floor chosen here is 16 quest templates, 8 reusable dungeon layouts, 4 recurring rival profiles, 24 technologies, 4 era art/audio families and 1,200 reviewed dialogue lines. More text does not compensate for missing branches. All later phases are part of this plan, even where they follow the MVP. Do not call the full game complete at the MVP gate.

## Operational defaults added by this pack

These close implementation gaps; they are not attributed to Joe as prior decisions. Store the values in definitions/configuration and review experience at the named gates.

| ID | Default | Review |
|---|---|---|
| I01 | Windows x64 is the first packaged target. Preserve the compatible Python/Godot versions discovered in the checkout, record exact versions, and pin them. A fresh project uses one available stable Godot 4 release and Python 3.12+; record rather than guess the installed versions. | G01/G10 |
| I02 | Local authoritative encounter steps are 50 ms; two steps align with a 100 ms world accounting boundary. No frame-time catch-up after focus loss. | G01/G04 |
| I03 | Begin with two carts per starting core. Replacing a destroyed cart costs 1 timber, 1 brick, 1 ore at its home warehouse. A paid order creates one new cart ID. | G02 |
| I04 | A construction staging store may exist at an empty node. It grants no ownership, VP, production or settlement-distance obstruction. | G02 |
| I05 | A starting core receives the same 2 timber, 2 brick, 1 wool, 1 grain bootstrap as an inherited core. Setup supplies one legal road from each core. Starting sites receive no free city or army. | G02 |
| I06 | Cube overflow propagates the incoming cube type; it does not retype existing cubes. A treatment targets a specific cube ID. | G04 |
| I07 | Where the repository has no usable duel rules, the fallback duel in C10 defines secrets, windows and ties. Existing tested mechanics take priority if compatible with v0.3. | G05 |
| I08 | Supported progression initially caps at eight colours and six slots. A saturated reward must use an explicitly authored alternative (knowledge/artifact), never display an upgrade that does nothing. | G05/G08 |
| I09 | Era conversion is mechanically atomic, followed by a four-second paused visual transformation. Skip/reduced-motion finishes presentation immediately without replaying conversion. | G06 |
| I10 | Full baseline content quantities above are release floors, selected to make completion measurable. | G08 |
| I11 | Trade uses reciprocal escrow and physical deliveries, as C05 defines; no remote stock swap or new bank-trading rule. | G02 |
| I12 | Training runs in resumable local batches with measured compute budgets; no automatic paid cloud jobs. Failure to qualify three policies leaves that milestone incomplete. | G09 |
| I13 | Era-scaled building health is centre 500, warehouse 300, other industry 200; a paid repair restores full health. | G03/G04 |
| I14 | Relationships use −100..100, with ±25 boundaries for the −1/0/+1 Aspect modifier. | G05 |
| I15 | Baseline processor inputs bind to specific eligible primary channels; route choice is explicit, and allocation shares constraints globally. | G03 |
| I16 | Compatible health technology preserves the unit's current health proportion; it cannot repeatedly heal on refresh. | G04 |
| I17 | Later technology requires any previously activated predecessor; inactive archived cards do not satisfy a gate. | G02 |
| I18 | Initial local area 48×48 tiles, expand in 16-tile steps; ordinary interaction range two tiles. Fixed encounter/accounting ordering is in C02. | G01/G05 |
| I19 | Construction/trade candidate scores, bounded goal-path lookahead and acceptance weights are explicitly specified in C12 for the heuristic baseline. | G02/G06 |

Source §40 explicitly protects an only remaining winner. If other factions dissolved during an era that began with several, preserve that winner and mark the next solo era for mandatory fission. Never collapse the last winning faction merely to satisfy a literal lowest-score rule.

## Repository boundaries

The checkout was not supplied. Paths throughout this pack are **target logical paths**, not claims that those files already exist. T001–T004 produce `tracking/repository_map.json`: actual root, branch, commit, dirty files, instructions, versions, test commands, and KEEP/ADAPT/REPLACE/RETIRE disposition with evidence. Map each logical path to an existing path where suitable. Preserve existing duel/puzzle strengths. Reuse the normal runtime in every village fixture.

No code migration starts before the map and baseline evidence exist. If the executor has no checkout, ask only for its local path or repository/branch; do not reconstruct the project from a remembered GitHub name. A fresh implementation is allowed only when the execution workspace is explicitly a new project. Retain user changes and prototype saves. Repository rules remain applicable; this pack grants no bypass.

## Architectural hard limits

Python owns durable world truth. Godot owns presentation, movement and explicitly leased live encounters. Offline tools own content production only. Every unit, cart, worker and building has a persistent ID. A formation is a set of unit IDs. There is one engine for the game, fixtures and training. Tests and inspectors may read privileged state; player labels and dialogue may not.

No runtime LLM, mana/HP/XP for the wizard, direct army/worker command UI, hidden economic gifts, indefinite worker-path blocking of production, unrequested bank trade, permanent ten-recipe restriction or forced MVP ending.
