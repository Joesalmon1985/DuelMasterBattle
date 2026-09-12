from pathlib import Path
import json, sys
repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
req = [
 "godot_project/sim/world/village_test_profiles.gd",
 "godot_project/sim/world/village_test_dialogue.gd",
 "godot_project/sim/world/village_test_dialogue_story.gd",
 "godot_project/sim/world/village_composite_projection.gd",
 "godot_project/content/village_test_dialogue.json",
 "godot_project/client/world/overworld.gd"
]
missing=[p for p in req if not (repo/p).exists()]
if missing: raise SystemExit("Missing: "+", ".join(missing))
ow=(repo/"godot_project/client/world/overworld.gd").read_text(encoding="utf-8")
assert "Village dialogue/story fixture hook" in ow
assert "_VillageDialogueStory" in ow
d=json.loads((repo/"godot_project/content/village_test_dialogue.json").read_text(encoding="utf-8"))
assert d["story"]["route"] == ["reeve","woodcutter","miller","miner"]
print("Patch structure OK")
