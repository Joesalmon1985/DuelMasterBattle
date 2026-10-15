extends SceneTree

## Headed camera test: the default view is close enough to see people (about 52 physical pixels per map tile, in any window size), + - = and the numpad
## zoom, the mouse wheel zooms, a two-finger pinch zooms (and never selects or interacts with anything), zoom stops at sensible limits, the choice is
## remembered, narrative panels do not change size with the camera, nothing zooms while a conversation is open, the wizard stays in the middle of the
## picture, and clicks still pick the figure under the pointer at near, default and far zoom.

const SaveData = preload("res://client/scripts/save_data.gd")
const ResponsiveModal = preload("res://client/ui/responsive_modal.gd")

var _world: Node
var _ui: Node
var _fails: Array[String] = []
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("CAM %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _settle() -> void:
	await _frames(3)
	await RenderingServer.frame_post_draw


func _shot(name: String) -> void:
	await _settle()
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("CAM_SHOT %s" % name)


func _key(code: int) -> void:
	for pressed in [true, false]:
		var e := InputEventKey.new()
		e.keycode = code
		e.physical_keycode = code
		e.pressed = pressed
		Input.parse_input_event(e)
		await _frames(1)
	await _frames(2)


func _wheel(up: bool) -> void:
	var e := InputEventMouseButton.new()
	e.button_index = MOUSE_BUTTON_WHEEL_UP if up else MOUSE_BUTTON_WHEEL_DOWN
	e.pressed = true
	e.position = Vector2(300, 300)
	Input.parse_input_event(e)
	await _frames(2)


func _touch(index: int, pressed: bool, pos: Vector2) -> void:
	var e := InputEventScreenTouch.new()
	e.index = index
	e.pressed = pressed
	e.position = pos
	Input.parse_input_event(e)
	await _frames(1)


func _drag(index: int, pos: Vector2, rel: Vector2) -> void:
	var e := InputEventScreenDrag.new()
	e.index = index
	e.position = pos
	e.relative = rel
	Input.parse_input_event(e)
	await _frames(1)


func _px_per_tile() -> float:
	var info: Dictionary = ResponsiveModal.window_info(_world)
	return float(_world.TPX) * _world._camera.zoom.x * float(info["scale"])


func _win(pos: Vector2) -> Vector2:
	return pos * (Vector2(DisplayServer.window_get_size()) / get_root().get_visible_rect().size)


func _mouse(vpos: Vector2, pressed: bool) -> void:
	var pos := _win(vpos)
	var e := InputEventMouseButton.new()
	e.position = pos
	e.global_position = pos
	e.button_index = MOUSE_BUTTON_LEFT
	e.pressed = pressed
	e.button_mask = 1 if pressed else 0
	Input.parse_input_event(e)


func _by_id(id: String) -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("id", "")) == id:
			return e
	return {}


## Click where the figure is drawn at the current zoom (real mouse press and release).
func _click_figure(id: String) -> void:
	var e := _by_id(id)
	var pos := Vector2(float(e["tx"]), float(e["ty"]))
	var vis: Dictionary = _world._art._vis.get(id, {})
	if not vis.is_empty():
		pos = vis["pos"]
	var wp: Vector2 = (pos + Vector2(0.5, 0.35)) * float(_world.TPX)
	_world.camera_focus = wp
	await _settle()
	var sp: Vector2 = _world.get_canvas_transform() * wp
	var m := InputEventMouseMotion.new()
	m.position = _win(sp)
	m.global_position = _win(sp)
	Input.parse_input_event(m)
	await _frames(1)
	_mouse(sp, true)
	await _frames(1)
	_mouse(sp, false)
	await _frames(6)
	_world.camera_focus = Vector2.INF


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/narrative/polish"
	SaveData.set_setting("hybrid_zoom_px", 52.0)  # a clean start: no zoom remembered from an earlier run
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(40)
	_ui = _world.story_ui
	_ui.finish_opening()
	_world.paused = true
	await _settle()

	# ---- the default view
	var d := _px_per_tile()
	_check(absf(d - 52.0) < 1.5, "the default view is %.1f physical px per tile (52 wanted); it used to be 17" % d)
	await _shot("camera_default")
	var info: Dictionary = ResponsiveModal.window_info(_world)
	var john_screen: Vector2 = _world.get_canvas_transform() * (_world._john.position + Vector2(_world.TPX * 0.5, _world.TPX * 0.5))
	_check(john_screen.distance_to(Vector2(info["vis"]) * 0.5) < 8.0, "the wizard is in the middle of the picture (%s of %s)" % [str(john_screen), str(Vector2(info["vis"]) * 0.5)])

	# ---- keyboard
	var z0: float = _world.zoom_px
	await _key(KEY_PLUS)
	_check(_world.zoom_px > z0, "+ zooms in (%.1f -> %.1f)" % [z0, _world.zoom_px])
	var z1: float = _world.zoom_px
	await _key(KEY_MINUS)
	_check(_world.zoom_px < z1 and absf(_world.zoom_px - z0) < 0.01, "- zooms out again (%.1f)" % _world.zoom_px)
	await _key(KEY_EQUAL)
	_check(_world.zoom_px > z0, "= zooms in too (%.1f)" % _world.zoom_px)
	await _key(KEY_KP_SUBTRACT)
	await _key(KEY_KP_ADD)
	await _key(KEY_KP_ADD)
	_check(_world.zoom_px > z0, "the numpad + and - work (%.1f)" % _world.zoom_px)
	_world.set_zoom_px(z0)

	# ---- mouse wheel
	await _wheel(true)
	_check(_world.zoom_px > z0, "the wheel up zooms in (%.1f)" % _world.zoom_px)
	await _wheel(false)
	await _wheel(false)
	_check(_world.zoom_px < z0, "the wheel down zooms out (%.1f)" % _world.zoom_px)
	_world.set_zoom_px(z0)

	# ---- limits
	for _i in 40:
		await _key(KEY_PLUS)
	_check(is_equal_approx(_world.zoom_px, _world.ZOOM_MAX_PX), "zoom stops at the maximum (%.0f px per tile)" % _world.zoom_px)
	await _shot("camera_max")
	for _i in 80:
		await _key(KEY_MINUS)
	_check(is_equal_approx(_world.zoom_px, _world.ZOOM_MIN_PX), "zoom stops at the minimum (%.0f px per tile)" % _world.zoom_px)
	await _shot("camera_min")
	_world.set_zoom_px(z0)

	# ---- pinch: fingers apart zoom in, together zoom out, and nothing is selected
	var worker := ""
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "worker" and str(e.get("faction_name", "")) == "Red" and not bool(e.get("inside", false)):
			worker = str(e["id"])
			break
	var wsp: Vector2 = Vector2(info["vis"]) * 0.5
	if worker != "":
		var we := _by_id(worker)
		var wv: Dictionary = _world._art._vis.get(worker, {})
		var wpos := Vector2(float(we["tx"]), float(we["ty"]))
		if not wv.is_empty():
			wpos = wv["pos"]
		wsp = _world.get_canvas_transform() * ((wpos + Vector2(0.5, 0.35)) * float(_world.TPX))
	var zp: float = _world.zoom_px
	await _touch(0, true, wsp)  # the first finger lands ON a worker
	await _touch(1, true, wsp + Vector2(120, 0))
	for i in 6:
		await _drag(1, wsp + Vector2(120 + 30 * (i + 1), 0), Vector2(30, 0))
	_check(_world.zoom_px > zp * 1.3, "fingers moving apart zoom in (%.1f -> %.1f)" % [zp, _world.zoom_px])
	var zin: float = _world.zoom_px
	for i in 6:
		await _drag(1, wsp + Vector2(300 - 40 * (i + 1), 0), Vector2(-40, 0))
	_check(_world.zoom_px < zin * 0.8, "fingers moving together zoom out (%.1f -> %.1f)" % [zin, _world.zoom_px])
	await _touch(1, false, wsp + Vector2(60, 0))
	await _touch(0, false, wsp)
	await _frames(10)
	_check(not _world.wizard_labels.panel.visible and not _ui.dialog.visible, "the pinch did not select or open anything")
	_check(_world._press.is_empty(), "and left no half-finished click behind")
	_world.set_zoom_px(z0)

	# ---- remembered
	_world.set_zoom_px(70.0)
	_check(is_equal_approx(float(SaveData.get_setting("hybrid_zoom_px", 0.0)), 70.0), "the zoom is remembered in the settings (%s)" % str(SaveData.get_setting("hybrid_zoom_px", 0.0)))
	_world.set_zoom_px(z0)

	# ---- the interface does not change size with the camera
	_ui._show_dialog({"status": "ok", "npc": "worker:none", "name": "Test Person", "subtitle": "Lumberjack", "lines": ["Hello."], "choices": [{"id": "a", "text": "A choice", "available": true}], "ends": false})
	await _settle()
	var card_a: Vector2 = _ui.dialog_card.panel.size
	_world.set_zoom_px(_world.ZOOM_MAX_PX, false)
	await _settle()
	var card_b: Vector2 = _ui.dialog_card.panel.size
	_world.set_zoom_px(_world.ZOOM_MIN_PX, false)
	await _settle()
	var card_c: Vector2 = _ui.dialog_card.panel.size
	_check(card_a.is_equal_approx(card_b) and card_a.is_equal_approx(card_c), "a conversation card is the same size at every zoom (%s, %s, %s)" % [str(card_a), str(card_b), str(card_c)])
	# ---- nothing zooms while a conversation owns the screen
	var zc: float = _world.zoom_px
	await _key(KEY_PLUS)
	await _wheel(true)
	_check(is_equal_approx(_world.zoom_px, zc), "zoom keys and the wheel do nothing while a conversation is open")
	_ui.close_dialog()
	_world.set_zoom_px(z0)

	# ---- clicking picks the right figure at near, default and far zoom
	if worker != "":
		for zoom in [_world.ZOOM_MAX_PX, z0, _world.ZOOM_MIN_PX + 8.0]:
			_world.set_zoom_px(zoom, false)
			_world.wizard_labels.close()
			await _click_figure(worker)
			_check(_world.wizard_labels.panel.visible and _world.wizard_labels.current_id == worker, "at %.0f px per tile a click on the worker inspects the worker" % zoom)
			_world.wizard_labels.close()
	_world.set_zoom_px(z0)

	# ---- the same physical closeness in a different window
	DisplayServer.window_set_size(Vector2i(450, 800))
	var t0 := Time.get_ticks_msec()
	while Vector2i(get_root().get_window().size) != Vector2i(450, 800) and Time.get_ticks_msec() - t0 < 3000:
		await _frames(5)
	await _frames(15)
	_check(absf(_px_per_tile() - _world.zoom_px) < 1.5, "in a 450 x 800 window a tile is still %.1f physical px (%.1f wanted)" % [_px_per_tile(), _world.zoom_px])
	await _shot("camera_portrait")

	if _fails.is_empty():
		print("HYBRID_CAMERA_OK")
		quit(0)
	else:
		print("HYBRID_CAMERA_FAIL ", ", ".join(_fails))
		quit(1)
