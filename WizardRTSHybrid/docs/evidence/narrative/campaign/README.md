# Evidence: the apprentice opening (15 October 2026)

* `full_hybrid.log`: the complete hybrid Python suite during development (1204 passed, 11 skipped); `final_gate.log`: hash baseline, determinism, content freeze,
  isolation and every narrative and wizard test after the last code edits (175 passed).
* `headed_apprentice_win.log`, `headed_apprentice_lose.log`: the whole opening played through the real UI and the real Ward Duel board at 450 x 800
  (`run_hybrid_apprentice.gd`, ending `win` and `lose`); `headed_ui.log`, `headed_suite_others.log`: the interface geometry test (five sizes, now including the
  scene card and the Game Over card) and the neighbouring headed tests.
* `shots/`: `win_a01` arrival, `win_a02` the mentor, `win_a02b` a failed Aspect check (disabled retry), `win_a03` the mentor's creed answers, `win_a05` ordinary
  people's opinions, `win_b01` the stranger's notice, `win_b02` the mentor meets him, `win_b03` the mentor falls, `win_b04` the apprentice's answers (Resolve check
  and seven beliefs), `win_c01` the lethal duel board, `win_c02`/`lose_c02` the result, `lose_d01` Game Over, `lose_d02` a new game, `win_e01` victory,
  `win_e02` and `win_e03` the aftermath (a villager's reaction and a worldview answer), `win_e04` the journal with its objective, `win_e05` the HUD,
  `ui_450x800_*` the scene and Game Over cards from the geometry test.
