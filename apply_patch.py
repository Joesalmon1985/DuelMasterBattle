#!/usr/bin/env python3
from pathlib import Path
import shutil, sys

patch_root = Path(__file__).resolve().parent
payload = patch_root / "payload"
repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()

def die(msg):
    print("ERROR:", msg)
    raise SystemExit(1)

overworld = repo / "godot_project/client/world/overworld.gd"
runner = repo / "godot_project/client/scripts/village_test_runner.gd"
if not overworld.exists() or not runner.exists():
    die("Run from the DuelMasterBattle repo root, or pass its path as argument.")

backup_dir = repo / ".village_test_patch_backup"
backup_dir.mkdir(exist_ok=True)
backup = backup_dir / "overworld.gd"
if not backup.exists():
    shutil.copy2(overworld, backup)
    print("Backed up", backup)

for src in payload.rglob("*"):
    if src.is_file():
        rel = src.relative_to(payload)
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print("Wrote", rel)

text = overworld.read_text(encoding="utf-8")
preload_marker = 'const _VillageTestRunner = preload("res://client/scripts/village_test_runner.gd")'
preload_line = 'const _VillageDialogueStory = preload("res://sim/world/village_test_dialogue_story.gd")'
if preload_line not in text:
    if preload_marker not in text:
        die("Expected VillageTestRunner preload not found; overworld.gd differs from current main.")
    text = text.replace(preload_marker, preload_marker + "\n" + preload_line, 1)

func_marker = 'func _interact_npc(e: Dictionary) -> void:\n\tvar adv := _adv()\n\tvar id := str(e["id"])\n'
hook = '''func _interact_npc(e: Dictionary) -> void:
\tvar adv := _adv()
\tvar id := str(e["id"])
\t# Village dialogue/story fixture hook. Normal campaign NPCs never enter this branch.
\tif _village_test_active and e.has("village_test_story"):
\t\t_input_locked = true
\t\t_touch.set_enabled(false)
\t\t_face_npc_toward_john(e)
\t\tvar test_result: Dictionary = _VillageDialogueStory.interact(adv, e)
\t\tfor test_line in test_result.get("lines", []):
\t\t\tawait _dialogue.say_async(str(e.get("name", "")), str(test_line))
\t\tadv.bump_talk(id)
\t\t_input_locked = false
\t\t_touch.set_enabled(true)
\t\t_update_prompt()
\t\treturn
'''
if "Village dialogue/story fixture hook" not in text:
    if func_marker not in text:
        die("Expected _interact_npc opening not found; no unsafe function edit was made.")
    text = text.replace(func_marker, hook, 1)

overworld.write_text(text, encoding="utf-8")
print("Patched godot_project/client/world/overworld.gd")
print("DONE. Run Play Village Test Menu.bat and select E17A.")
