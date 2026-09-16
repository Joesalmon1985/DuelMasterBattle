# Implementation decisions register

Status: registered defaults, not completion claims. Mechanical changes to a
LOCKED v0.3 rule require Joe's explicit revision.

## Authority

1. Joe's current explicit instructions.
2. v0.3 LOCKED rules.
3. v0.3 DEFINED rules.
4. Build-pack implementation defaults.
5. Compatible existing implementation.

The approved execution supplement is `../EXECUTION_AMENDMENTS.md`. It selects a
staged option-B cutover: isolated Python core in T007–T014, then a G01 slice in
which Python is the exclusive durable state owner. Existing Godot simulation
code can supply behaviour and regression evidence but cannot remain a live
writer in that campaign.

## C00 implementation defaults

| ID | Registered default | Review |
|---|---|---|
| I01 | First package is Windows x64. Initial pins are Godot 4.4.1 and Python 3.12.3; any engine change is separate and tested. | G01/G10 |
| I02 | Godot leased encounters step at 50 ms; two steps align with the 100 ms accounting boundary; no focus-loss catch-up. | G01/G04 |
| I03 | Two starting carts/core; replacement costs 1 timber, 1 brick, 1 ore and creates one new ID. | G02 |
| I04 | Empty-node construction staging grants no ownership, VP, production or distance obstruction. | G02 |
| I05 | Starting/inherited core bootstrap is 2 timber, 2 brick, 1 wool, 1 grain plus one legal road; no free city/army. | G02 |
| I06 | Overflow propagates incoming cube type; treatment targets a cube ID. | G04 |
| I07 | Preserve compatible tested duel rules; use C10 fallback only if no usable implementation exists. | G05 |
| I08 | Initial progression supports up to 8 colours/6 slots; saturated rewards require an authored alternative. | G05/G08 |
| I09 | Era conversion is atomic, followed by a four-second paused presentation; skip/reduced motion completes presentation once. | G06 |
| I10 | Full-baseline content floors are the measurable values in C00/full-baseline manifest. | G08 |
| I11 | Trade is reciprocal escrow plus physical delivery; no remote stock swap/bank rule. | G02 |
| I12 | Training is local, resumable and measured; no automatic paid cloud jobs; three unqualified policies leave the milestone incomplete. | G09 |
| I13 | Building health: centre 500, warehouse 300, other industry 200; paid repair restores full health. | G03/G04 |
| I14 | Relationships range −100..100; ±25 boundaries produce the −1/0/+1 Aspect modifier. | G05 |
| I15 | Processor inputs bind to explicit eligible primary channels; global allocation shares constraints. | G03 |
| I16 | Health technology preserves current health proportion and cannot heal repeatedly on refresh. | G04 |
| I17 | Later technology requires a previously activated predecessor; inactive archived cards do not qualify. | G02 |
| I18 | Initial local area is 48×48, expanding in 16-tile steps; ordinary interaction range is two tiles. | G01/G05 |
| I19 | Construction/trade scoring and bounded lookahead use C12's explicit heuristic values. | G02/G06 |

## Additional controlling decisions

- Preserve an only remaining winning faction and require next-era fission.
- Python owns persistent truth; Godot owns rendering/input/local movement and
  explicitly leased encounter state.
- Normal play, fixtures and training use one authoritative simulation.
- Workers, soldiers, carts and buildings have persistent IDs; animation does
  not drive production.
- Catan construction/trade cargo and Game-Time industry remain separate.
- Only accepted Travel and distinct Wait presses advance World Turns.
- Duels freeze world time; ordinary faction military cannot defeat the wizard.
- Living people and active quests survive era transitions.
- Runtime has no internet or LLM dependency; authenticated loopback IPC is
  required and permitted.
