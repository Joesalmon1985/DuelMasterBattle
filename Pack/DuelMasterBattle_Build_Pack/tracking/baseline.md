# T001 baseline

## Repository

- Checkout: `/home/joe/Projects/DuelMasterBattle`
- Remote: `https://github.com/Joesalmon1985/DuelMasterBattle.git`
- Authoritative source: `origin/VillageQuestRunnerTry2`
- Execution branch: `BuildPackV03`
- Immutable original base:
  `a0936dd41f00ee7393067b1f800411800175d23e`
- Prepared expected commit `6b3780c34e9b7aeb5c0d51ad705e842e28aec86e`
  is an ancestor; the fetched source was one commit ahead.
- Pack/control import:
  `09ebb27445fa828822a228ff767088937e4889fb`

The execution branch was created directly from the fetched source commit. The
source branch was not modified or rebased. Subsequent task commits advance only
`BuildPackV03`; the original base above remains the ledger baseline.

## Preserved working files

The initial checkout had no tracked modifications. It contained:

- `Pack/` — the extracted build pack, now committed at its approved location;
- `DuelMasterBattle_Build_Pack.zip` — duplicate user upload, preserved and
  specifically ignored at the repository root.

No user file was reset, stashed, deleted or overwritten.

## Existing application boundary

The existing application is Godot 4.4:

- normal entry: `godot_project/project.godot` →
  `res://client/scenes/main_menu.tscn`;
- persistent world: `godot_project/sim/world/world_sim.gd`;
- in-process world caller: `godot_project/client/world/world_flow.gd`;
- campaign/save writer: `godot_project/client/scripts/adventure.gd`,
  `user://adventure.save`, schema version 4;
- village and puzzle tests launch their menus and then reuse the production
  Overworld, but village fixtures retain separate projection/quest code;
- Python currently supplies tested duel rules and offline dialogue tooling, not
  persistent world state;
- the Python sidecar, framed bridge, encounter leases and coordinated save
  repository are not present.

This GDScript simulation is the behavioural migration baseline. It is not the
target authority. Under the approved staged-B cutover, T007–T014 create the
Python core, and T015–T024 connect the G01 runtime with Python as the exclusive
durable state owner.

## Applicable instructions

Always apply:

1. `.cursor/rules/dmb-build-pack.mdc`
2. `Pack/DuelMasterBattle_Build_Pack/AGENT_START_HERE.md`
3. `Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md`
4. current task, named contract, repository map and prior receipt
5. `.hermes.md` and the relevant `docs/roles/` file for specialist work

The single authoritative ledger is
`Pack/DuelMasterBattle_Build_Pack/tracking/progress.json`.

## T001 evidence

Commands used:

```text
git fetch origin VillageQuestRunnerTry2
git rev-parse origin/VillageQuestRunnerTry2
git checkout -b BuildPackV03 origin/VillageQuestRunnerTry2
git merge-base --is-ancestor 6b3780c... a0936dd...
git merge-base --is-ancestor a0936dd... HEAD
git status --short --branch
```

Observed:

- fetched source and branch base: `a0936dd41f00ee7393067b1f800411800175d23e`;
- both ancestry checks succeeded;
- after committing the approved pack and control rule, tracked status was clean;
- task/game test execution is deferred to T003; T001 does not manufacture a
  unit-test pass for a read-only audit.
