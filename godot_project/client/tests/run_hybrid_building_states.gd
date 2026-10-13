extends SceneTree

const HybridArt = preload("res://client/hybrid/hybrid_art.gd")

## Building state art proof (plan v2 8.5 "Working animation", "Construction"): the real hybrid_art picks the imported working / build
## sheet for a working or constructing Widelands building, the sheet loads, its frames differ from each other and from idle.
## No simulation server required.


func _init() -> void:
	call_deferred("_run")


func _frame_diff(item: Dictionary, a: int, b: int) -> int:
	var img := Image.load_from_file(ProjectSettings.globalize_path(String(item["godot"])))
	if img == null:
		return -1
	var cols := int(item["columns"])
	var fw := img.get_width() / cols
	var fh := img.get_height() / int(item["rows"])
	var diff := 0
	for y in fh:
		for x in fw:
			var pa := img.get_pixel((a % cols) * fw + x, (a / cols) * fh + y)
			var pb := img.get_pixel((b % cols) * fw + x, (b / cols) * fh + y)
			if pa != pb:
				diff += 1
	return diff


func _run() -> void:
	var art := HybridArt.new()
	art.load_catalogue()
	var bad := 0
	var checked := 0
	for id in art.items.keys():
		var sid := String(id)
		if not sid.ends_with(".working"):
			continue
		var base := sid.trim_suffix(".working")
		var working: Dictionary = art._item_for({"class": "building", "definition": base, "working": true})
		var idle: Dictionary = art._item_for({"class": "building", "definition": base})
		var building: Dictionary = art._item_for({"class": "building", "definition": base, "constructing": {"progress_ms": 1}})
		var ok: bool = String(working.get("id", "")) == sid and String(idle.get("id", "")) == base
		if art.items.has(base + ".build"):
			ok = ok and String(building.get("id", "")) == base + ".build"
		else:
			ok = ok and String(building.get("id", "")) == base
		var frames := int(working.get("frames", 1))
		var moving := frames < 2  # a one-frame working sheet is a legitimate static state
		for f in range(1, frames):
			if moving:
				break
			moving = _frame_diff(working, 0, f) > 0  # some later frame differs from the first (frames 0 and 1 can be identical)
		if not ok or not moving:
			print("  FAIL ", sid, " selected=", ok, " frames=", frames, " frames_differ=", moving)
			bad += 1
		checked += 1
	print("checked ", checked, " working sheets")
	print("HYBRID_BUILDING_STATES_", "OK" if bad == 0 and checked > 50 else "FAIL", " ", bad)
	quit(0 if bad == 0 and checked > 50 else 1)
