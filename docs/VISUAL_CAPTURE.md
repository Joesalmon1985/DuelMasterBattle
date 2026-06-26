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
| 1 | Main menu | Launch game | Title, **encounter** dropdown, detail panel, **Start duel**, How to play |
| 2 | Blue Apprentice setup | Start duel → Blue Apprentice | 1 slot (Shield), enemy tell, player wizard |
| 3 | Magic picker (filtered) | Click secret or attack slot | Only encounter-allowed magics (e.g. 4 for Blue Apprentice attack) |
| 4 | Archmage setup | Back to menu → Archmage Duel | 4 point headers, 10-type picker |
| 5 | Alternating duel | Cast pattern | Human history + enemy history; one bot row per turn |
| 6 | Enemy attacking | After human attack | Enemy wizard name, Skip button (if delay enabled) |
| 7 | Result | Finish duel | Winner, attack counts, New duel, Back to menu |

## Web build (optional)

```bash
tools/export_web.sh
cd godot_project/build/web && python3 -m http.server 8080
```

Open `http://localhost:8080` and repeat key screens. Re-export after encounter UI changes — committed `build/` may be stale.

## Saving screenshots

Use your OS screenshot tool (e.g. Print Screen, Flameshot) at **1280×720** or **900×700** window size for consistency.

Optional helper:

```bash
tools/visual_checklist.sh
```

Prints this checklist and can launch the Godot project window.
