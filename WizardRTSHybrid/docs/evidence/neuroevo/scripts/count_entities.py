import sys, json, hashlib
from pathlib import Path
HYB = Path(__file__).resolve().parents[4]  # WizardRTSHybrid (evidence copy of a scratch script; run from the repo)
sys.path.insert(0, str(HYB)); sys.path.insert(0, str(HYB.parent))
from wizard_rts import construction as con, tech, wl_defs, rules
from wizard_rts.content import graph
from wizard_rts.industry import registry as mdy, units as U
menu = con.full_menu()
units = {u: b for b, rs in con.RECIPES.items() for u in rs}
ents = graph.entities()
cards = graph.generated_cards()
hand = tech.cards()
wl = wl_defs.defs()
ra = json.load(open(HYB/"wizard_rts/data/openra_rules.json"))
md = json.load(open(HYB/"wizard_rts/data/mindustry_defs.json"))
summary = {
 "build_menu_hybrid_kinds": len(con.BUILD_MENU), "full_menu_kinds": len(menu), "wl_runnable": len([k for k in menu if k.startswith("wl:")]),
 "mdy_kinds": len(mdy.kinds()), "recipe_units": len(units), "mdy_producible_units": len([n for n in U.unit_list() if U.is_producible(n)]),
 "graph_entities": len(ents), "graph_buildings": sum(1 for e in ents.values() if e["type"]=="building"), "graph_units": sum(1 for e in ents.values() if e["type"]=="unit"),
 "generated_cards": len(cards), "hand_cards": len(hand), "wl_defs_buildings": len(wl["buildings"]), "wl_defs_wares": len(wl["wares"]), "wl_defs_workers": len(wl["workers"]),
 "openra_actors": len(ra["actors"]), "openra_weapons": len(ra.get("weapons", {})), "mdy_blocks": len(md["blocks"]), "mdy_units": len(md["units"]), "mdy_items": len(md["items"]), "mdy_liquids": len(md["liquids"]),
 "graph_check_problems": len(graph.check()),
}
by_game = {}
for e in ents.values(): by_game[(e["game"], e["type"])] = by_game.get((e["game"], e["type"]), 0) + 1
summary["graph_by_game_type"] = {f"{g}/{t}": n for (g,t), n in sorted(by_game.items())}
canon = json.dumps({"entities": sorted(ents), "cards": sorted(cards), "hand_cards": sorted(hand), "units": sorted(units)}, sort_keys=True).encode()
summary["roster_sha256_prototype"] = hashlib.sha256(canon).hexdigest()
print(json.dumps(summary, indent=1))
