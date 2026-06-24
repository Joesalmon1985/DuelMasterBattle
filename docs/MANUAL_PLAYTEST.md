# Manual Human vs Bot Playtest — Wizard Duel

```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
"$GODOT" --path godot_project
```

## Checklist

- [ ] Launch Godot project and press **Human vs Bot**.
- [ ] Choose difficulty (default **Expert**).
- [ ] Click **Shield** slot → magic picker opens with 10 types.
- [ ] Select a magic type → slot fills (symbol + number).
- [ ] Repeat for **Body**, **Staff**, **Mind**.
- [ ] **Cast pattern** enabled only when all four points are set.
- [ ] Cast pattern → your points hidden (`****`).
- [ ] Enemy attacks appear one row at a time with **Hit / Weakness / Unaffected** feedback.
- [ ] Enemy stops after solve or 12 attacks.
- [ ] Your attack row activates; click slots → same picker.
- [ ] **Attack** enabled only when all four guess slots filled.
- [ ] Continue until win/loss or 12 attacks.
- [ ] Result panel shows both outcomes.
- [ ] **New duel** starts cleanly.

## Report format
State: **passed** | **partially passed** | **failed**

## Automated alternative
```bash
tools/run_godot_ui_smoke.sh
```
