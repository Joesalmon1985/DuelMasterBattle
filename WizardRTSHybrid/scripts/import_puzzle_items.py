#!/usr/bin/env python3
"""Generate wizard_rts/data/puzzle_items.json from the game's own GDScript catalogue (godot_project/sim/world/items.gd and
client/scripts/colour_data.gd). The Python puzzle port reads names and tags from here; the parity test checks them against Godot."""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
items_gd = (ROOT / "godot_project/sim/world/items.gd").read_text()
colour_gd = (ROOT / "godot_project/client/scripts/colour_data.gd").read_text()
items = {}
for m in re.finditer(r'^\t"(\w+)": \{"name": "([^"]*)", "sprite": "([^"]*)", "desc": "((?:[^"\\]|\\.)*)", "tags": \[([^\]]*)\]\}', items_gd, re.M):
    items[m.group(1)] = {"name": m.group(2), "sprite": m.group(3), "desc": m.group(4).replace("\\'", "'"),
                         "tags": re.findall(r'"(\w+)"', m.group(5))}
ess = re.search(r"const ESSENCE_NAMES := \[(.*?)\]", colour_gd, re.S).group(1)
out = {"source": "godot_project/sim/world/items.gd, client/scripts/colour_data.gd", "items": items, "essence_names": re.findall(r'"([^"]*)"', ess)}
(ROOT / "WizardRTSHybrid/wizard_rts/data/puzzle_items.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
print(len(items), "items", len(out["essence_names"]), "essences")
