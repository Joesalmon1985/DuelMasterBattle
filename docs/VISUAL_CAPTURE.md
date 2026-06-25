# Visual capture checklist

Godot headless mode cannot reliably capture viewport screenshots. Use this manual process for demo assets and release notes.

## Prerequisites

```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
"$GODOT" --path godot_project
```

Or launch from the Godot editor with `godot_project` as the project path.

## Screens to capture

| # | Screen | How to reach | What to show |
|---|--------|--------------|--------------|
| 1 | Main menu | Launch game | Title, Human vs Bot, How to play |
| 2 | Secret setup | Human vs Bot | Player wizard, Shield/Body/Staff/Mind headers, empty slots |
| 3 | Magic picker | Click any secret slot | Overlay grid with magic icons |
| 4 | Enemy attacking | Cast pattern | Enemy wizard, bot rows appearing, Skip button |
| 5 | Human attacking | After bot phase ends | Your attack row, phase label |
| 6 | Result | Finish duel | Winner, solve/fail counts, New duel |

## Web build (optional)

```bash
tools/export_web.sh
cd godot_project/build/web && python3 -m http.server 8080
```

Open `http://localhost:8080` and repeat key screens in the browser.

## Saving screenshots

Use your OS screenshot tool (e.g. Print Screen, Flameshot) at **1280×720** or **900×700** window size for consistency.

Optional helper:

```bash
tools/visual_checklist.sh
```

Prints this checklist and can launch the Godot project window.
