# Manual Playtest — Encounter Progression Rulesets

```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
"$GODOT" --path godot_project
```

## Step-by-step checklist (this branch)

1. Launch the game locally (command above).
2. On the main menu, select **Blue Apprentice** in the encounter dropdown; confirm detail text (1 point, 4 attack magics, 4 max attacks, enemy tell).
3. Press **Start duel**.
4. Confirm **1 slot** appears with point label **Shield**.
5. Click the slot — confirm picker shows **only** Flame, Frost, Storm, Arcane (4 buttons).
6. Set secret (e.g. Frost), **Cast pattern**, submit at least one human attack — confirm human feedback row appears.
7. Confirm bot makes **one** attack with visible feedback.
8. Finish or abandon duel; press **Back to menu** (or **New duel** then back).
9. Select **Archmage Duel** → **Start duel**.
10. Confirm **4 slots** and **10 magic types** in picker.
11. Play at least **two alternating turns** (human attack → bot attack → human attack).
12. Confirm **both** human and bot feedback histories update.
13. Reach result screen; test **New duel** restart.

Web export preview — **only document if actually run**; not required for this branch.

## Automated alternative

```bash
tools/run_godot_ui_smoke.sh   # Blue Apprentice + Archmage paths
tools/run_godot_tests.sh
cd python_prototype && python3 -m pytest -q
```

## Report format

State: **passed** | **partially passed** | **failed** | **not performed**

## Legacy full-game checklist (Archmage)

- [ ] Encounter **Archmage Duel** selected
- [ ] Player and enemy wizard portraits visible; four point headers
- [ ] Cast pattern → human turn first (not bulk bot phase)
- [ ] Alternating turns with dual histories
- [ ] Result panel and **New duel**
