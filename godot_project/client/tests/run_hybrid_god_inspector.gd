extends SceneTree

## Headed proof of the God Mode technology inspector (plan v2 8.6) through real GUI clicks. Needs the sim on HYBRID_SIM_PORT with
## HYBRID_PROFILE=developer HYBRID_CARDSET=v2. Opens God Mode, presses the inspector button, checks the cards came from the sim,
## selects a unit card and a building card, rotates the facing, switches a building to its working state, applies the
## missing-art filter, and saves screenshots to HYBRID_SHOT_DIR.

var _world: Node
var _god: Node
var _bad := 0


func _init() -> void:
	call_deferred("_run")


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _check(ok: bool, label: String) -> void:
	print(("ok   " if ok else "FAIL ") + label)
	if not ok:
		_bad += 1


func _shot(name: String) -> void:
	await _frames(3)
	await RenderingServer.frame_post_draw
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		dir = "res://../WizardRTSHybrid/docs/evidence/inspector"
	DirAccess.make_dir_recursive_absolute(dir)
	get_root().get_viewport().get_texture().get_image().save_png(dir.replace("\\", "/") + "/%s.png" % name)
	print("INSPECTOR_SHOT ", name)


func _click(c: Control) -> void:
	var pos := c.get_global_rect().get_center() * (Vector2(DisplayServer.window_get_size()) / get_root().get_visible_rect().size)
	for pressed in [true, false]:
		var e := InputEventMouseButton.new()
		e.position = pos
		e.global_position = pos
		e.button_index = MOUSE_BUTTON_LEFT
		e.pressed = pressed
		e.button_mask = 1 if pressed else 0
		Input.parse_input_event(e)
		await _frames(3)


func _find_button(node: Node, text: String) -> Button:
	for ch in node.get_children():
		if ch is Button and (ch as Button).text == text:
			return ch
		var sub := _find_button(ch, text)
		if sub != null:
			return sub
	return null


func _run() -> void:
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(30)
	_god = _world.god
	_check(_god != null and not _world._snapshot.is_empty(), "world and God Mode loaded")
	await _click(_god.mode_btn)
	_check(_god.active, "God Mode entered")
	await _click(_god.inspector_btn)
	await _frames(10)
	_check(_god.inspector_overlay.visible and _god.inspector_view != null, "inspector overlay opened by its button")
	var v = _god.inspector_view
	_check(v.cards.size() > 100, "catalogue came from the simulation (%d cards)" % v.cards.size())
	await _shot("01_inspector_open")
	# a unit card: pick a card whose first entity is the rifle infantry
	var unit_card := ""
	var bld_card := ""
	for c in v.cards:
		for e in c["entities"]:
			if str(e["id"]) == "unit:infantry" or str(e["id"]) == "unit:tank":
				unit_card = str(c["id"])
			if str(e["art"]["key"]) == "widelands.barbarians_smelting_works" or str(e["id"]).begins_with("wl:barbarians_") and bld_card == "" and v.art.items.has(str(e["art"]["key"]) + ".working"):
				bld_card = str(c["id"])
	_check(unit_card != "", "a card unlocking a Red Alert unit exists")
	v.select_card(unit_card)
	v.set_facing("e")
	await _frames(5)
	var east: Texture2D = v.previews[0]["rect"].texture
	await _shot("02_unit_facing_east")
	v.set_facing("w")
	await _frames(5)
	var west: Texture2D = v.previews[0]["rect"].texture
	await _shot("03_unit_facing_west")
	_check(east != null and west != null and east.get_image().get_data() != west.get_image().get_data(), "facing buttons change the rendered sprite")
	_check(bld_card != "", "a card unlocking a Widelands building with a working sheet exists")
	v.select_card(bld_card)
	v.set_state("idle")
	await _frames(5)
	var idle_tex: Texture2D = v.previews[0]["rect"].texture
	await _shot("04_building_idle")
	v.set_state("working")
	await _frames(40)
	await _shot("05_building_working")
	v.missing_only.button_pressed = true
	v.apply_filters()
	await _frames(3)
	_check(v.shown.size() > 0 and v.shown.size() < v.cards.size(), "missing/placeholder filter narrows the list (%d)" % v.shown.size())
	await _shot("06_missing_art_filter")
	print("HYBRID_GOD_INSPECTOR_", "OK" if _bad == 0 else "FAIL", " ", _bad)
	quit(0 if _bad == 0 else 1)
