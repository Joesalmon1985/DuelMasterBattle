extends SceneTree

## Headless proof that every imported Mindustry block and unit in the art catalogue loads as a texture and that each of its animatable parts loads too.
func _init() -> void:
	var cat: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://client/hybrid/art/catalogue.json"))
	var bad := 0
	var blocks := 0
	var parts := 0
	for item in cat["items"]:
		if not str(item["id"]).begins_with("mindustry."):
			continue
		var tex = load(str(item["godot"]))
		if tex == null or tex.get_width() < 4:
			print("FAIL texture ", item["id"])
			bad += 1
			continue
		blocks += 1
		for p in item.get("parts", []):
			var pt = load(str(p["file"]))
			if pt == null or pt.get_width() < 1:
				print("FAIL part ", item["id"], " ", p["role"])
				bad += 1
			else:
				parts += 1
	print("mindustry entries ", blocks, " parts ", parts)
	print("HYBRID_MINDUSTRY_ART_OK" if bad == 0 else "HYBRID_MINDUSTRY_ART_FAIL %d" % bad)
	quit(0 if bad == 0 else 1)
