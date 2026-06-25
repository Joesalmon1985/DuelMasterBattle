# Manual Human vs Bot Playtest — Wizard Duel

```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
"$GODOT" --path godot_project
```

## Checklist

- [ ] Launch Godot project and press **Human vs Bot** (or use **How to play** on menu).
- [ ] Choose difficulty (default **Expert**).
- [ ] Player and enemy wizard portraits visible; point headers show Shield/Body/Staff/Mind icons + labels.
- [ ] Click **Shield** slot → magic picker opens with 10 types.
- [ ] Select a magic type → slot fills (symbol + number).
- [ ] Repeat for **Body**, **Staff**, **Mind**.
- [ ] **Cast pattern** enabled only when all four points are set.
- [ ] Cast pattern → your points hidden (`****`).
- [ ] Enemy attacks appear **one row at a time** with **Hit / Weakness / Unaffected** feedback (icons + labels).
- [ ] **Skip enemy attacks** fast-forwards remaining bot rows.
- [ ] Enemy stops after solve or 12 attacks.
- [ ] Your attack row activates; click slots → same picker.
- [ ] **Attack** enabled only when all four guess slots filled.
- [ ] Continue until win/loss or 12 attacks.
- [ ] Result panel shows winner, solve/fail, attack counts.
- [ ] **New duel** starts cleanly.
- [ ] **How to play** / **How feedback works** panels open on board.

## Web preview

```bash
tools/export_web.sh
cd godot_project/build/web && python3 -m http.server 8080
```

Repeat checklist in browser at `http://localhost:8080`.

## Report format
State: **passed** | **partially passed** | **failed**

## Automated alternative
```bash
tools/run_godot_ui_smoke.sh
```
