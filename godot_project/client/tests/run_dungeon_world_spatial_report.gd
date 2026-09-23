extends SceneTree
## Writes docs/testing/DUNGEON_WORLD_SPATIAL_METRICS.json from the fixture.

const Fixture = preload("res://sim/world/dungeon_world_fixture.gd")
const Spec = preload("res://sim/world/wizard_dungeon_spec.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var fx = Fixture.new()
	fx.setup(507)
	var out := {
		"seed": 507,
		"hexes": fx.sim.board.hexes.size(),
		"nodes": fx.sim.board.nodes.size(),
		"edges": fx.sim.board.edges.size(),
		"settlements": [],
		"candidates": fx.candidates.duplicate(true),
		"specimen_node": fx.specimen_node,
		"bg_test_node": fx.bg_test_node,
		"bg_unassigned": fx.production_bg_unassigned(),
		"catalogue_max_room": [Spec.CATALOGUE_MAX_ROOM.x, Spec.CATALOGUE_MAX_ROOM.y],
		"reservation": [Spec.RESERVATION_W, Spec.RESERVATION_H],
		"size_profiles": [],
		"dungeon_defs": {},
	}
	for s in fx.settlements:
		out["settlements"].append(s)
	for code in Spec.all_types():
		var d: Dictionary = Spec.dungeon_def(code)
		out["dungeon_defs"][code] = {
			"dungeon_id": d["dungeon_id"],
			"wizard_id": d["wizard_id"],
			"rooms": d["rooms"],
			"flow": d["flow"],
			"production_terrain": d["production_terrain"],
		}
	for nid_name in [["specimen", fx.specimen_node], ["bg", fx.bg_test_node]]:
		var label: String = nid_name[0]
		var nid: int = int(nid_name[1])
		var code: String = "GW" if label == "specimen" else "BG"
		var profiles: Array = []
		for sz in Spec.SIZE_PROFILES:
			var area: Dictionary = fx.project_node(nid, sz, code, label == "specimen")
			profiles.append({"node": nid, "label": label, "size": [sz.x, sz.y], "metrics": fx.metrics_for(area),
				"fit": area.get("embedded_dungeon", {}).get("fit", "?"),
				"rooms": area.get("embedded_dungeon", {}).get("rooms", [])})
		out["size_profiles"].append_array(profiles)
	var path := "res://../docs/testing/DUNGEON_WORLD_SPATIAL_METRICS.json"
	# Write beside the project via absolute-ish user path from cwd expectation.
	var f := FileAccess.open("user://dungeon_world_spatial_metrics.json", FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(out, "\t"))
		f.close()
	# Also try repo docs path via ProjectSettings
	var abs := ProjectSettings.globalize_path("res://") + "../docs/testing/DUNGEON_WORLD_SPATIAL_METRICS.json"
	var f2 := FileAccess.open(abs, FileAccess.WRITE)
	if f2:
		f2.store_string(JSON.stringify(out, "\t"))
		f2.close()
		print("WROTE ", abs)
	else:
		print("WROTE user://dungeon_world_spatial_metrics.json (repo path failed)")
	print(JSON.stringify({"hexes": out["hexes"], "nodes": out["nodes"], "candidates": out["candidates"].size(),
		"specimen": out["specimen_node"], "bg": out["bg_test_node"]}, "\t"))
	quit(0)
