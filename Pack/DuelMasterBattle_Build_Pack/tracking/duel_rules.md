# T002 duel rules and retention decision

## Decision

Retain and adapt the existing Godot `DmbBattleSim` production duel and its UI as
the leased encounter runtime. Retain Python scoring, encounter definitions,
deterministic bots and cross-language fixtures as reusable rules evidence.
Do **not** replace the working duel with C10's fallback, and do not make the
Python alternating-turn prototype the production duel.

`DmbRealtimeDuelSim` remains regression/reference code until the production
`DmbBattleSim` lease has equivalent coverage. It must not remain a selectable
second production authority after that cutover.

## Existing production behaviour

The production scene is `client/scenes/game_board.tscn`, driven by
`client/scripts/game_board.gd`. Adventure encounters arrive through
`Adventure.pending_battle`; quick duels derive symmetric combatants from the
selected ruleset. The board currently instantiates `DmbBattleSim`, despite its
stale header saying `DmbRealtimeDuelSim`.

`DmbBattleSim` provides:

- a player-selected hidden Ward and seeded enemy Ward;
- independent player/enemy real-time cast windows and automatic casting;
- exact-position fracture plus remaining-colour echo feedback;
- repeated colours and configurable pools, Ward/weave sizes and cast limits;
- deterministic seeded enemy planning with a bounded per-frame think budget;
- simultaneous resolution at the same update boundary (`clash`);
- victory when the enemy Ward breaks or its casts exhaust first;
- defeat when the player Ward breaks or player casts exhaust first;
- stalemate when both exhaust together;
- a separately advancing `duel_time` that respects its local pause flag;
- an authored prologue forced-defeat policy, enabled only by the story request.

The existing quick-duel catalogue is broader than C10's fallback:

- Python/Godot default Archmage: four loci, ten essence colours and twelve
  casts (`python_prototype/duel_mastermind/constants.py`);
- introductory and advanced encounters vary slots, pools, repeats and windows;
- the UI text currently says “Ten casts each”, which conflicts with the Python
  default constant and must be resolved by the later retained-duel task, not
  silently changed during audit;
- C10's required baseline says four slots, six colours and ten casts. Because
  tested existing rules take priority when compatible, T091 must map authored
  encounter/progression definitions explicitly rather than flattening the
  catalogue to the fallback.

## Python prototype behaviour

`SequentialDuelGame` is an alternating Human-first prototype:

1. the player fills and locks a legal secret;
2. the bot creates one seeded secret;
3. the player and bot take one guess per alternating turn;
4. a sole solution wins immediately;
5. if both are represented as solved, fewer guesses wins and equal guesses
   draw;
6. if both exhaust without solving, it draws; helper logic also contains a
   best-progress tiebreak for other incomplete terminal inputs.

This is useful pure rules/bot test material, but it is not production timing.
The Python `test_realtime_rules.py` only validates catalogue/profile metadata;
the real-time state machine exists in Godot.

## Compatibility with v0.3/C10

Compatible and retained:

- one legal hidden Ward per side;
- multiplicity-correct exact/colour-only feedback;
- configurable pools, repeats, slots, cast limits and cast windows;
- seeded deterministic rival behaviour;
- separate duel clock;
- simultaneous solve handling;
- Godot presentation and local duel execution.

Required adaptations:

- acquire a global Python-owned pause token before granting the duel lease;
- checkpoint secrets, current inputs, histories, windows, casts, duel RNG and
  rival planning state; current read models are not complete serializers;
- restore without rerolling secrets;
- submit versioned checkpoints/results and make duplicate outcomes idempotent;
- revalidate target/quest eligibility before one persistent consequence;
- route recovery through C10 and advance no World Turn/Game Time;
- prove focus loss pauses duel input and does not release unrelated pause
  tokens;
- reconcile authored encounter counts/pools and stale UI copy in T091 against
  v0.3 progression, without invoking the fallback casually.

The existing `Adventure.pending_battle` / `last_battle_result` handoff is not an
encounter lease and directly triggers client saves. T018–T019 establish the
lease/checkpoint boundary; T091–T092 complete retained mechanics, persistence
and outcome recovery.

## Save and defeat behaviour today

- `Adventure.request_battle()` stores a request and saves immediately.
- `game_board.gd` resolves combatants from that request.
- `Adventure.report_battle_result()` records the outcome, may mark a defeated
  encounter, clears the pending request and saves.
- Ordinary `DmbBattleSim` defeat ends the duel; story/quest code decides its
  campaign meaning.
- Mid-duel secrets, timers, bot candidates and current input are not part of
  the Adventure v4 campaign save.

Therefore existing presentation and mechanics are KEEP/ADAPT, while the
durable result/save handoff is REPLACE through the C02/C10 contracts.

## Evidence files

- `python_prototype/duel_mastermind/{constants,feedback,duel_ruleset,encounters,game_state}.py`
- `python_prototype/tests/{test_feedback,test_game_state,test_realtime_rules}.py`
- `shared_fixtures/*.json`
- `godot_project/sim/{battle_sim,realtime_duel_sim,feedback,duel_ruleset}.gd`
- `godot_project/sim/tests/{test_core_duel,test_early_solver}.gd`
- `godot_project/client/scripts/{game_board,adventure}.gd`
- `Pack/DuelMasterBattle_Build_Pack/contracts/C10_adventure.md`
