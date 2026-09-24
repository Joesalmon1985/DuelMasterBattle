# DuelMasterBattle — execution amendments

Authoritative supplement approved by Joe Salmon on 16 September 2026. These
instructions refine the v0.3 build pack without renumbering tasks or weakening
its contracts. Current explicit user instructions still have highest
precedence.

## Staged Python ownership cutover

Use a constrained version of preflight option B:

1. **T001–T006:** preserve and measure the existing Godot application.
2. **T007–T014:** build and verify the Python identity, state, command, clock
   and save core with isolated test worlds.
3. **T015–T024:** connect the normal launcher and a small playable G01 slice.
   In that running campaign Python exclusively owns durable world state.
   Disable the former Godot strategic tick, persistent mutation and campaign
   world-save writers for that runtime.

A temporary adapter may translate calls or projections, but Godot must not
simulate or save fields also owned by Python. Old code may remain as reference,
isolated regression tests or offline comparison. Do not expose an old-sim
backend in the new production entrypoint.

G01 certifies this migration slice, not complete village gameplay. **G05
(re-scoped again — return to narrative + usability):** fully explorable
Prehistoric board (19/54/72) **plus one simple persistent blocked-exit rockfall
quest**. Helper is **any eligible village worker** chosen via dialogue after
Inspect — not a preselected Person. Original shortage/demon/sluice prototype
remains **superseded** and archived (`FX-VILLAGE-QUEST`). Do not start
era-transition (T097) until Joe clears this gate.

**G05 dynamic local obstacles:** when Python clears a rockfall (or similar),
Godot must refresh Overworld `_entity_at` via `sync_dynamic_obstacle` /
`sync_dynamic_obstacles_from_area` on the same area payload that updates
WorldLayerPresenters. Visual-only layer updates leave stale walk blocks.
A full LocalArea rebuild also works but is not the preferred live path.

## Toolchain and pack location

- Initially pin Godot 4.4.1, subject to T003 confirming the executable and
  baseline tests. Pin Python 3.12.3 and actual dependencies found by T003.
- Align Windows launchers and export templates with Godot 4.4.1. Record Windows
  verification separately; Linux does not certify Windows.
- Any engine upgrade is a separate measured and tested change.
- Keep and commit this pack at `Pack/DuelMasterBattle_Build_Pack/`.
- Keep one authoritative progress ledger under this pack's `tracking/`.
- Ignore only the duplicate root `DuelMasterBattle_Build_Pack.zip` and
  appropriate generated caches, logs, saves and build outputs. Do not delete
  them or broadly hide source assets.

## T001–T004 additions

T001 confirms `BuildPackV03` ancestry and records the immutable original base
`a0936dd41f00ee7393067b1f800411800175d23e`. Later task commits may advance
HEAD; do not rebase automatically.

T002 adds an ownership table for world position/turns, factions, Catan
stocks/carts, worker/NPC identity, quest outcomes, encounter results and
campaign saves. For each group record current mutation/save entrypoints, target
owner and command boundary, adapting callers, intended regression or v0.3
difference, disconnect task and proof that the old writer is disconnected.
RETIRE means after callers and regressions are handled, never bulk deletion.

T003 records exact commands, versions, exit codes and test counts. Attempt
existing normal launch, E17A/E36B village, puzzle, dialogue and save/load flows
where available. Preserve semantic behavioural expectations separately from
intentional v0.3 changes. A relevant failure or missing suite is not a pass.

T004 wraps real runners and preserves exit status. Unknown tasks, missing or
empty required suites, unexpected skips and subprocess failures return
nonzero. Do not create placeholder scenarios or miniature alternate
simulations. Use focused checks per task and cumulative suites at gates.

## Cursor and execution discipline

Use one implementation agent editing this branch at a time. The root rule
`.cursor/rules/dmb-build-pack.mdc` points to the current task, progress,
repository map and this amendment; it must not inline the GDD or task deck.

Continue automatically through dependency-ready tasks. For each accepted task,
record files/symbols, actual commands/results, defects, commit and next task;
commit only task-owned changes. Stop at manual gates, a material unresolved
design requirement or a concrete blocker after three focused repair attempts.
The blocker packet must include reproducer/seed, assertion/log excerpt,
expected versus observed state, suspected owner, changed files and attempted
fixes. Never weaken assertions to avoid escalation.

Meaningful behavioural checks accompany Godot import checks. All ten human
gates remain mandatory and only Joe's explicit PASS clears one.

## Strengthened G01 evidence

Before requesting G01, automated and manual evidence must establish:

- one valid Travel causes exactly one durable node change and World Turn;
- retransmission after a lost reply returns the same receipt without mutation;
- one Wait press causes one turn; holding it and invalid travel cause none;
- save, complete exit, relaunch and load preserve IDs, position, clocks and
  command receipts;
- sidecar stop/disconnect pauses the client with no fallback to Godot sim;
- checkpoint recovery reports rollback honestly with no duplicate result or
  catch-up time;
- former Godot strategic tick/save writers cannot run in the new runtime;
- lease checkpoint/result retransmission has exclusive ownership and
  exactly-once persistent consequences.

The authenticated loopback Python/Godot bridge is permitted. "No network at
runtime" means no internet or LLM dependency.

## G04 interaction repair (18 September 2026)

Joe-directed corrective pass for G04 controls, ownership and hazards. Source
brief: `docs/DuelMasterBattle_G04_Interaction_Repair_Brief.md`. Receipt IDs
R01–R08 record the first repair pass; do not renumber T001 onward.

## G04 retained duel and shared interaction repair (19 September 2026)

Supersedes conflicting R06 / “choose fallback” decisions from the 18 September
pass. Authoritative addendum:
`docs/DuelMasterBattle_G04_Reuse_Repair_Addendum.md` (U01–U08).

**Cleared 2026-09-19:** Joe Salmon accepted G04 PASS against implementation
`75b7f539aa1916fb6c0a5f156be3efa5184dd7eb` on main via merge
`15eadbd7dd82ebb56167c745e4998f2fa06809fb`. T077/G05 is authorized.
Historical note: during the repair G04 was FIX_REQUIRED then AWAITING_HUMAN;
PASS was never granted from automation alone. Integration branch was
`fix/g04-retained-ui` from `origin/feature/spellbook-ui`, with `origin/main`
merged. Ensemble-only commits `58ea2d2` and `6f7be0f` remain a separate
follow-up on `BuildPackV03-ensemble-depth-pass` and were not part of the
accepted G04 merge.

### Control and validation

- Target first, action second: distant targets yield observation only; within
  shared tile-unit interaction range (baseline two tiles) open the approved
  military attached menu. Actions differ by capability: NPC Observe/Talk;
  soldier Observe/Buff…/Destroy; hazard Observe/Challenge when eligible. No
  permanent spell toolbar in play or normal gameplay.
- One shared target/action session serves NPCs, soldiers and hazards. Preserve
  the AttachedChoiceCard appearance Joe approved.
- A validated Observe learns that individual's permitted display name through
  the authoritative knowledge service (people and soldiers). Mere proximity
  must not silently name them. Talk uses the retained village
  WorldInteractionLabel / dialogue presentation with filtered bridge data.
- Validate distance against synchronised local poses, including moving leased
  units and the wizard after SyncPose/checkpoint. Re-evaluate at choice open
  and again at commit. Caller-supplied `observed_ids` grant no authority.
- One input router: UI choice vs semantic target vs ground move; no duplicate
  touch/mouse actions. Formal choices acquire a pause token; cancel/walk-away
  via shared movement intent (keyboard, pad, ground) releases only that token.

### Ownership, fixtures and pace

- A strategic node has zero or one controlling settlement. Invading armies may
  fight there with valid home/factory IDs elsewhere. Active industry at an
  owned node belongs to that settlement. FX-BATTLE must be a lawful one-owner
  defended settlement with a clear spawn and free cardinal movement.
- Pace the battle so a human can approach and inspect before it ends without
  weakening C07 combat math (spawn spacing / approach time only). Provide a
  clearly labelled isolated fixture reset (`g04_battle` / `g04_hazard`).

### Projection lifecycle

- Omitted view fields mean no update; an explicitly empty authoritative
  collection means remove those entities. Clear caches on world change or load
  of a different save. Reject stale replies (wrong world/version/request id).
  External unit/hazard actors must not be owned by people rebuild.

### Retained duel (supersedes R06 Mastermind production choice)

- T002 already selected `client/scenes/game_board.tscn`,
  `client/scripts/game_board.gd` and `sim/battle_sim.gd` (`DmbBattleSim`).
- Hazard Challenge must launch that retained scene/engine under a Python lease.
  The simplified Guess/Resign Mastermind panel is not the production Challenge
  path. Keep `sim/dmb/adventure/mastermind.py` as reference scoring evidence
  only.
- Configure GameBoard from the lease **before** scene startup (`configure_from_lease`
  before `add_child`). Preserve existing quick-duel and Adventure
  `pending_battle` entry points unchanged.
- Encounter differences (including G04 baseline four slots / six colours / ten
  casts) are explicit combatant/encounter data. Do not flatten other working
  encounters. Ordinary challenges must not inherit the prologue forced-defeat
  flag.
- Versioned duel checkpoints must restore wards, histories, windows, casts,
  duel time, 64-bit RNG and rival planner state without reroll. Duplicate or
  stale outcome submission is idempotent: the first valid result applies once;
  retransmits return the same receipt without a second cube/allowance mutation.
- Do not call legacy `Adventure.report_battle_result` to save a second campaign
  or transition into the old overworld from migrated Challenge play.

### Task ownership

- G04 owns the minimum shared target/observation/choice path and retained
  Challenge lease on the production bridge. T079 and T085 extend narrative
  coverage; T091 and T092 extend the retained `DmbBattleSim` implementation
  (not Python Mastermind as production). They must not recreate a competing
  interface or mark remaining work complete from this repair. Traceability:
  `tracking/interaction_traceability.json`.

### Human-decisive acceptance

- Automated checks are necessary and must pass before AWAITING_HUMAN; they are
  not sufficient for PASS. Decisive proof is walking up to a moving soldier,
  clicking, choosing a spell, seeing a persistent result, then the equivalent
  observe/Challenge flow on a visible hazard using the full retained duel UI.
  Linux launchers: `bash tools/play_g04_battle.sh`,
  `bash tools/play_g04_hazard.sh`.

## Overnight G06→G12 autonomous run (22–23 September 2026)

**Authorised by:** Joe Salmon via explicit overnight Cursor prompt on branch
`phase/g06-g12-autoqa` (starting SHA `d6b78d3883eb20d6ccd31ace92b1a2126fbbe39d`
on `main` after G06 historic-MVP merge).

This amendment **supersedes**, for this authorised run only, the build-pack
requirement to stop execution after each human gate (AGENT_START_HERE
“Human gates” / gate cards that say STOP at AWAITING_HUMAN). All other
contracts, ownership rules and acceptance oracles remain in force.

### Status vocabulary (G06 onward)

Distinguish these statuses carefully. Do **not** conflate them:

| Status | Meaning |
|---|---|
| `IN_PROGRESS` | Implementation underway |
| `IMPLEMENTATION_COMPLETE` | Tasks for the gate are coded; automation may still be pending |
| `AUTO_READY_FOR_OWNER_REVIEW` | Objective automated requirements for the gate passed; Joe has **not** accepted |
| `AWAITING_HUMAN` | Packet ready; agent historically stopped (legacy) |
| `PASS` | **Only** Joe’s explicit acceptance for the named build |
| `FIX_REQUIRED` | Joe rejected; reopen affected tasks |
| `PARTIAL — BLOCKED BY …` | Honest incomplete state with a concrete blocker |
| `AUTO_FAILED` | Automation ran and failed |

### Rules for this overnight run

1. G06 onward still requires Joe’s eventual **subjective** review. Automated
   testing does **not** constitute human acceptance.
2. Automated testing does **not** clear a gate as `PASS`, does not invent
   `accepted_by`, and does not invent acceptance timestamps.
3. When all **objective automated** requirements for a gate pass during this
   run, set the gate to `AUTO_READY_FOR_OWNER_REVIEW` (or equivalent wording
   in `tracking/progress.json` and `MORNING_REVIEW.md`).
4. `AUTO_READY_FOR_OWNER_REVIEW` **permits implementation to continue** to the
   next phase/task without waiting for Joe overnight.
5. Original gate evidence (screenshots, reports, saves, logs, montages) must
   remain available under `tracking/gates/Gxx/` for Joe’s later review.
6. No historical human acceptance may be invented. Existing true `PASS`
   records (G01–G04) stay as recorded.
7. If Joe later rejects a checkpoint (`FIX_REQUIRED`), reopen the relevant
   tasks, add regressions, repair, and resubmit — do not argue automation
   already “passed” the subjective bar.
8. **G10 redefinition for this development sequence:** G10 is a
   **functionally complete placeholder-art baseline**, not a production-art
   release. Semantic placeholder graphics are explicitly permitted for cards,
   buildings, upgrades, technologies, hazards, catastrophes, units, resources,
   items and other content.
9. Finished visual asset creation is deferred. Prefer readable semantic
   placeholders over blocking on artwork.
10. Existing real artwork may remain where already present; do not spend the
    overnight run polishing art.
11. **G11** (T161–T164) and **G12** (T165–T168) are added by this run for
    semantic-placeholder completeness and unattended functional acceptance.
    Do not renumber T001–T160.
12. Linux does not certify Windows. Training artifacts must be genuine or the
    blocker recorded honestly. Screenshots must be real Godot frames.

### Continuation policy

After T106 / early Historic checkpoint evidence, this run may begin T107 and
continue through T168 while recording `AUTO_READY_FOR_OWNER_REVIEW` at each
completed automated gate. Morning handoff:
`Pack/DuelMasterBattle_Build_Pack/tracking/OVERNIGHT_G06_G12_REPORT.md`.
