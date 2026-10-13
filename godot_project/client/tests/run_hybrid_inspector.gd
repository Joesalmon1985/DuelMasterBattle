extends SceneTree

const InspectorPanel = preload("res://client/hybrid/inspector_panel.gd")

## Inspector proof (plan v2 8.6): for every card of the sim's catalogue the panel resolves a real texture for each unlocked entity
## (or, for a placeholder or missing one, says so), its preview uses the art item the catalogue names, facing changes the frame of a
## directional sprite, and the "missing or placeholder art" filter lists exactly the cards with such entities. Server-free: the
## catalogue is the JSON the Python inspector produced (scripts/export_inspector_fixture.py).


func _init() -> void:
	call_deferred("_run")


func _image_hash(tex: Texture2D) -> int:
	if tex == null:
		return -1
	var img := tex.get_image()
	return hash(img.get_data()) if img != null else -1


func _run() -> void:
	var bad := 0
	var f := FileAccess.open("res://client/tests/fixtures/inspector_catalogue.json", FileAccess.READ)
	var data: Dictionary = JSON.parse_string(f.get_as_text())
	var panel = InspectorPanel.new()
	root.add_child(panel)
	await process_frame
	panel.load_catalogue(data)
	var cards: Array = data["cards"]
	var entities := 0
	var imported := 0
	var rendered := 0
	for c in cards:
		panel.select_card(str(c["id"]))
		if panel.previews.size() != c["entities"].size():
			print("FAIL preview count ", c["id"])
			bad += 1
		for p in panel.previews:
			entities += 1
			var art_info: Dictionary = p["entity"]["art"]
			if art_info["status"] == "imported":
				imported += 1
				if p["item"].is_empty() or str(p["item"].get("id", "")) != str(art_info["key"]):
					print("FAIL item for ", p["entity"]["id"], " key ", art_info["key"])
					bad += 1
				var tex: Texture2D = panel.preview_texture(p["item"], 0.0)
				if tex == null or tex.get_width() < 4:
					print("FAIL no texture for ", p["entity"]["id"])
					bad += 1
				else:
					rendered += 1
	print("entities ", entities, " imported ", imported, " with a rendered preview ", rendered)
	# facing changes the frame of a directional sprite (the same code path the world uses)
	var inf: Dictionary = panel.art.items.get("openra.e1", {})
	panel.facing = "e"
	var east := _image_hash(panel.preview_texture(inf))
	panel.facing = "w"
	var west := _image_hash(panel.preview_texture(inf))
	if east == west or east == -1:
		print("FAIL facing does not change the preview")
		bad += 1
	# a layered tank: aiming the turret changes the picture, the hull stays
	var tank: Dictionary = panel.art.items.get("openra.3tnk", {})
	panel.facing = "e"
	panel.turret_slot = 0
	var aim_n := _image_hash(panel.preview_texture(tank))
	panel.turret_slot = 8
	var aim_w := _image_hash(panel.preview_texture(tank))
	panel.turret_slot = -1
	if aim_n == aim_w or aim_n == -1:
		print("FAIL turret aim does not change the preview")
		bad += 1
	# building state: a working sheet is selected and differs from idle
	panel.state = "idle"
	var bld: Dictionary = panel.art.items.get("widelands.barbarians_lumberjacks_hut", {})
	var idle_hash := _image_hash(panel.preview_texture(bld))
	var found_state := false
	for id in panel.art.items.keys():
		if String(id).ends_with(".working"):
			var base := String(id).trim_suffix(".working")
			var item: Dictionary = panel.art.items.get(base, {})
			panel.state = "working"
			var w := _image_hash(panel.preview_texture(item, 0.0))
			panel.state = "idle"
			var i := _image_hash(panel.preview_texture(item, 0.0))
			if w != i and w != -1:
				found_state = true
				break
	if not found_state:
		print("FAIL working state preview never differs from idle")
		bad += 1
	# the missing/placeholder filter equals the python list
	panel.missing_only.button_pressed = true
	panel.apply_filters()
	var expect := 0
	for c in cards:
		for e in c["entities"]:
			if e["art"]["status"] in ["missing", "alias_placeholder"]:
				expect += 1
				break
	if panel.shown.size() != expect:
		print("FAIL missing filter ", panel.shown.size(), " vs ", expect)
		bad += 1
	print("missing-art cards ", panel.shown.size())
	print("HYBRID_INSPECTOR_", "OK" if bad == 0 and rendered > 100 else "FAIL", " ", bad)
	quit(0 if bad == 0 and rendered > 100 else 1)
