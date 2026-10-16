extends SceneTree

## Exports the legacy Deathtrap Dungeon zones (`DmbWorldData`, the `dd_*` areas) and the
## legacy bestiary (`DmbBestiary`) to JSON for the Python host (`wizard_rts/data/trial/`).
## Run:  godot --headless --path godot_project --script res://client/tools/export_legacy_zones.gd
## Env:  DMB_ZONES_OUT (directory; default the repository's WizardRTSHybrid/wizard_rts/data/trial).
## The output is data the Trial reads at run time; the GDScript tables stay the legacy adventure's.

const WorldData = preload("res://client/world/world_data.gd")
const Bestiary = preload("res://sim/bestiary.gd")


func _init() -> void:
	var out_dir := OS.get_environment("DMB_ZONES_OUT")
	if out_dir == "":
		out_dir = ProjectSettings.globalize_path("res://../WizardRTSHybrid/wizard_rts/data/trial")
	DirAccess.make_dir_recursive_absolute(out_dir)
	var zones := {}
	for id in WorldData.area_ids():
		if not String(id).begins_with("dd_"):
			continue
		zones[id] = WorldData.get_area(id)
	var beasts := {}
	for id in Bestiary.ids():
		beasts[id] = Bestiary.get_data(id)
	_write(out_dir.path_join("legacy_zones.json"), {"source": "godot_project/client/world/world_data.gd", "zones": zones})
	_write(out_dir.path_join("legacy_bestiary.json"), {"source": "godot_project/sim/bestiary.gd", "opponents": beasts})
	print("ZONES_EXPORT_OK zones=%d opponents=%d dir=%s" % [zones.size(), beasts.size(), out_dir])
	quit(0)


func _write(path: String, data: Dictionary) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data, "  ", false, true))
	f.store_string("\n")
	f.close()
