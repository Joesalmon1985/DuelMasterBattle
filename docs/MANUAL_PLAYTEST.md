# Manual Human vs Bot Playtest

Run this script after launching the Godot project locally:

```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
"$GODOT" --path godot_project
```

## Checklist

- [ ] Launch Godot project.
- [ ] Press Play (or run command above).
- [ ] Select **Human vs Bot**.
- [ ] Click secret peg 1 and choose a colour.
- [ ] Click secret peg 2 and choose a colour.
- [ ] Click secret peg 3 and choose a colour.
- [ ] Click secret peg 4 and choose a colour.
- [ ] Confirm the **Lock code** button becomes enabled.
- [ ] Lock the code.
- [ ] Confirm the secret code is hidden (shows `****`).
- [ ] Confirm the bot makes guesses.
- [ ] Confirm bot guesses are visible on the board.
- [ ] Confirm feedback appears beside each bot guess (`●` exact, `○` colour).
- [ ] Confirm the bot stops after solving or after 12 guesses.
- [ ] Confirm the bot then sets a hidden code (human guess row becomes active).
- [ ] Make at least one human guess using the clickable peg selector.
- [ ] Submit the guess.
- [ ] Confirm feedback appears.
- [ ] Continue until win/loss or exhaust 12 guesses.
- [ ] Confirm the result screen appears.
- [ ] Press **New game**.
- [ ] Confirm a new game starts cleanly.

## Report format

State: **passed** | **partially passed** | **failed**

If failed, note the exact step that failed.

## Automated alternative

```bash
tools/run_godot_ui_smoke.sh
```

The scripted UI smoke test drives the same UI actions headlessly. If no visible Godot window is available, do not claim the manual playtest passed unless actually performed.
