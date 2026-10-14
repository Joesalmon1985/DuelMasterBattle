extends Overworld

const HexCoords = preload("res://client/hybrid/hex_coords.gd")
const SimClient = preload("res://client/hybrid/sim_client.gd")
const DuelAdapter = preload("res://client/encounters/duel_lease_adapter.gd")
const HybridArt = preload("res://client/hybrid/hybrid_art.gd")
const GodMode = preload("res://client/hybrid/god_mode.gd")
const TerrainView = preload("res://client/hybrid/terrain_view.gd")
const WizardLabels = preload("res://client/hybrid/wizard_labels.gd")
const StoryUi = preload("res://client/hybrid/story_ui.gd")

## Continuous hybrid world. Movement, camera, and the retained duel board
## come from the existing Overworld and DmbDuelLeaseAdapter. The Python
## server owns stocks, clocks, and entity positions.

var _sim = SimClient.new()
var _adapter = DuelAdapter.new()
var _snapshot: Dictionary = {}
var _blocked: Dictionary = {}
var _seq := 0
const POLL_SECONDS := 0.2  # the simulation steps in 100 ms quanta; the art layer glides between polls, so a poll is not needed every frame
var _static_rows: Dictionary = {}  # trees and rocks, kept locally and updated from the sim's deltas
var _solid: Dictionary = {}  # Vector2i -> id of a standing tree or a rock there: the wizard walks round them (P1.1, same rule as world.set_pose)
var _solid_tile_of: Dictionary = {}  # id -> Vector2i, so a delta can clear the tile it used to block
const WALKABLE_TREE_STAGES := ["sapling", "felled", "stump"]
var _clock_acc := 0.0
var paused := false  # spectator pause: the client stops asking the sim to advance (the world clock does not move)
var _duel_open := false
var _hex_crossings := 0
var _last_hex := Vector2i(999999, 999999)
var _duel_layer: CanvasLayer
var _duel_host: Control
var _font: Font
var _art = HybridArt.new()
var _camera_nudge := Vector2.ZERO
var camera_focus := Vector2.INF
var god: Node
var wizard_labels: Node  # semantic labels and fire magic (Wizard Mode)
var era_hud: Label  # era, victory points and cycle: a developer read-out of the simulation's own state
var story_ui: Node  # the wizard's story: people, dialogue, dungeon, duel (placeholders over the Python ops)
var terrain = null  # TerrainView once the sim has sent its terrain
var autosave_seconds := 300.0  # real seconds of play between autosaves; the client times it, the simulation reads no wall clock (HYBRID_AUTOSAVE_SECONDS overrides)
var autosave_count := 0
var _autosave_acc := 0.0
var _menu_open := false  # the pause menu is showing
var selected_ids: Dictionary = {}:
	set(v):
		selected_ids = v
		_art.selected = v


func _ready() -> void:
	if OS.get_environment("HYBRID_AUTOSAVE_SECONDS") != "":
		autosave_seconds = maxf(1.0, float(OS.get_environment("HYBRID_AUTOSAVE_SECONDS")))
	_build_layers()
	_build_ui()
	_font = ThemeDB.fallback_font
	var adv := _adv()
	if not adv.is_active():
		adv.new_game()
	area_id = "hybrid"
	area = {"id": "hybrid", "name": "Wizard RTS", "rows": ["."]}
	grid_w = 2000
	grid_h = 2000
	test_mode = true
	_camera.zoom = Vector2(0.48, 0.48)
	_art.load_catalogue()
	_camera.position_smoothing_enabled = false
	# Overworld leaves the scene fader opaque until an area fade. This scene
	# does not load an area, so hide it or the world is covered.
	if _fader != null:
		_fader.modulate.a = 0.0
	_duel_layer = CanvasLayer.new()
	_duel_layer.name = "DuelHost"
	_duel_layer.layer = 20
	add_child(_duel_layer)
	_duel_host = Control.new()
	_duel_host.name = "DuelHost"
	_duel_host.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_duel_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_duel_layer.add_child(_duel_host)
	_adapter.finished.connect(_on_duel_finished)
	var port := int(OS.get_environment("HYBRID_SIM_PORT"))
	if port <= 0:
		port = 8765
	if not _sim.connect_to(port):
		push_error("Hybrid sim server is not running on 127.0.0.1:%d" % port)
		_hud_area_lbl.text = "Sim server missing"
		return
	var tview = TerrainView.new()
	if tview.load_from(_sim.op({"op": "terrain"})):
		terrain = tview
	var reply := _sim.op({"op": "snapshot"})
	_apply_snapshot(reply.get("snapshot", {}))
	_place_john_from_snapshot()
	_update_john_sprite(0)
	_hud_area_lbl.text = "Wizard RTS"
	god = GodMode.new()
	god.name = "GodMode"
	add_child(god)
	god.setup(self)
	wizard_labels = WizardLabels.new()
	wizard_labels.name = "WizardLabels"
	add_child(wizard_labels)
	wizard_labels.setup(self)
	story_ui = StoryUi.new()
	story_ui.name = "StoryUi"
	add_child(story_ui)
	story_ui.setup(self)
	var hud_layer := CanvasLayer.new()
	hud_layer.name = "EraHudLayer"
	hud_layer.layer = 5
	add_child(hud_layer)
	era_hud = Label.new()
	era_hud.name = "EraHud"
	era_hud.position = Vector2(16, 104)
	era_hud.add_theme_font_size_override("font_size", 24)
	era_hud.add_theme_color_override("font_color", Color(0.95, 0.9, 0.7))
	era_hud.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	era_hud.add_theme_constant_override("outline_size", 4)
	era_hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud_layer.add_child(era_hud)


func _era_text(snap: Dictionary) -> String:
	var era: Dictionary = snap.get("era", {})
	if era.is_empty():
		return ""
	var hist: Dictionary = snap.get("history", {})
	var vp: Dictionary = era.get("vp", {})
	var parts: PackedStringArray = []
	for f in ["Red", "Blue", "Green", "Yellow", "Purple", "Orange"]:
		if vp.has(f):
			parts.append("%s %d" % [f.substr(0, 1), int(vp[f])])
	var txt := "Cycle %d  |  Era: %s  |  VP %s  |  era progress %d/%d" % [int(hist.get("cycle", 0)), str(era.get("era", "")), " ".join(parts), int(era.get("progress", 0)), int(era.get("threshold", 0))]
	if bool(hist.get("cycle_pending", false)):
		txt += "  |  THE CYCLE ENDS"
	return txt


func _process(delta: float) -> void:
	super._process(delta)
	_autosave_tick(delta)
	_art.industry.begin_frame(delta)
	if _camera_nudge != Vector2.ZERO:
		_camera.position += _camera_nudge
	if camera_focus != Vector2.INF:
		_camera.position = camera_focus
	if _snapshot.is_empty() or _duel_open:
		queue_redraw()
		return
	_clock_acc += delta
	if paused:
		_clock_acc = 0.0
	if _clock_acc >= POLL_SECONDS:
		var ms := int(_clock_acc * 1000.0)
		_clock_acc = 0.0
		_seq += 1
		var reply := _sim.op({"op": "advance", "ms": ms, "sequence": _seq, "tree_delta": true})
		if str(reply.get("status", "")) == "ok":
			_apply_snapshot(reply.get("snapshot", {}))
			_seq = int(_snapshot.get("clock_sequence", _seq))
	queue_redraw()


## Painter's order: a multi-tile machine is drawn by the bottom row of its footprint, so a unit standing beside it is not hidden under it.
func _sort_y(e: Dictionary) -> int:
	var y := int(e.get("ty", 0))
	if e.has("ground_footprint") and str(e.get("definition", "")).begins_with("mindustry."):
		for p in e["ground_footprint"]:
			y = max(y, int(p[1]))
	return y


func _unhandled_input(event: InputEvent) -> void:
	# Wizard Mode: a left click on any entity opens its label (description far away, fire magic close up)
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT and story_ui != null and not _duel_open and not story_ui.dialog.visible:
		if story_ui.try_click(event.position):
			get_viewport().set_input_as_handled()
			return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT and wizard_labels != null and not _duel_open:
		if wizard_labels.try_click(event.position):
			get_viewport().set_input_as_handled()
			return
	super._unhandled_input(event)


func _arrived() -> void:
	if _sim._peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return
	# light reply: the clock only needs to know where he stands, not the whole world back on every tile
	var reply := _sim.op({
		"op": "pose",
		"tx": _john_pos.x,
		"ty": _john_pos.y,
		"facing": _john_facing,
		"light": true,
	})
	if str(reply.get("status", "")) == "ok":
		var hx: Array = reply.get("hex", [0, 0])
		var hex := Vector2i(int(hx[0]), int(hx[1]))
		if _last_hex.x != 999999 and hex != _last_hex:
			_hex_crossings += 1
		_last_hex = hex
		var player: Dictionary = _snapshot.get("player", {})
		player["tx"] = _john_pos.x
		player["ty"] = _john_pos.y
		player["facing"] = _john_facing
		player["hex"] = [hex.x, hex.y]
	_update_prompt()


func tile_ground(x: int, y: int) -> bool:
	if terrain != null:
		return terrain.ground(x, y)
	return HexCoords.tile_in_map(x, y)


func _tile_char(_x: int, _y: int) -> String:
	if not tile_ground(_x, _y):
		return " "
	return "."


func is_walkable(p: Vector2i) -> bool:
	if not tile_ground(p.x, p.y):
		return false
	return not _blocked.has(p) and not _solid.has(p)


## A standing tree (not a sapling, stump or field crop) or a rock blocks the wizard's tile.
func _note_solid(row: Dictionary) -> void:
	var id := str(row.get("id", ""))
	_unnote_solid(id)
	var cls := str(row.get("class", ""))
	if cls == "tree" and (not bool(row.get("solid", true)) or str(row.get("stage", "")) in WALKABLE_TREE_STAGES):
		return  # the simulation says which trees are solid (world.tree_solid); fields, crops, bushes and saplings are not
	if cls != "tree" and cls != "rock":
		return
	var t := Vector2i(int(row.get("tx", 0)), int(row.get("ty", 0)))
	_solid[t] = id
	_solid_tile_of[id] = t


func _unnote_solid(id: String) -> void:
	if _solid_tile_of.has(id):
		var t: Vector2i = _solid_tile_of[id]
		if str(_solid.get(t, "")) == id:
			_solid.erase(t)
		_solid_tile_of.erase(id)


func _on_action() -> void:
	if _duel_open or _snapshot.is_empty():
		return
	var reply := _sim.op({"op": "interact"})
	if str(reply.get("status", "")) != "started":
		_hud_area_lbl.text = "Walk up to the hazard"
		return
	_apply_snapshot(reply.get("snapshot", {}))
	_duel_open = true
	_input_locked = true
	_duel_host.mouse_filter = Control.MOUSE_FILTER_STOP
	var ok := _adapter.begin_from_start_reply(_duel_host, reply, Callable(self, "_cmd"))
	if not ok:
		_duel_open = false
		_input_locked = false
		push_error("Retained duel failed to open")


func _cmd(kind: String, payload: Dictionary = {}) -> Dictionary:
	if kind != "ResolveHazardDuel":
		return {}
	return _sim.op({
		"op": "resolve",
		"duel_id": str(payload.get("duel_id", "")),
		"success": bool(payload.get("success", false)),
		"command_id": "godot:%s" % str(payload.get("duel_id", "")),
	})


func _on_duel_finished(outcome: String, _payload: Dictionary) -> void:
	_duel_open = false
	_input_locked = false
	_duel_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var reply := _sim.op({"op": "snapshot"})
	_apply_snapshot(reply.get("snapshot", {}))
	_hud_area_lbl.text = "Duel %s" % outcome
	queue_redraw()


func _apply_snapshot(snap: Dictionary) -> void:
	if snap.is_empty():
		return
	if snap.has("tree_delta"):
		var d: Dictionary = snap["tree_delta"]
		if bool(d.get("full", false)):
			_static_rows.clear()
			_solid.clear()
			_solid_tile_of.clear()
		for row in d.get("upsert", []):
			_static_rows[str(row["id"])] = row
			_note_solid(row)
		for id in d.get("removed", []):
			_static_rows.erase(str(id))
			_unnote_solid(str(id))
		snap["entities"] = snap.get("entities", []) + _static_rows.values()
	else:
		_static_rows.clear()
		_solid.clear()
		_solid_tile_of.clear()
		for e in snap.get("entities", []):
			if typeof(e) == TYPE_DICTIONARY and str(e.get("class", "")) in ["tree", "rock"]:
				_static_rows[str(e["id"])] = e
				_note_solid(e)
	_snapshot = snap
	if era_hud != null:
		era_hud.text = _era_text(snap)
		era_hud.visible = god == null or not god.active  # in God Mode the spectator HUD shows the era with its reasons
	_blocked.clear()
	for item in snap.get("blocked", []):
		if item is Array and item.size() >= 2:
			_blocked[Vector2i(int(item[0]), int(item[1]))] = true
	for f in snap.get("factions", []):
		_art.faction_colors[str(f.get("name", ""))] = Color.html(str(f.get("color", "#ffffff")))
	var player: Dictionary = snap.get("player", {})
	var hex := Vector2i(int(player.get("hex", [0, 0])[0]), int(player.get("hex", [0, 0])[1]))
	if _last_hex.x != 999999 and hex != _last_hex:
		_hex_crossings += 1
	_last_hex = hex


func _place_john_from_snapshot() -> void:
	var player: Dictionary = _snapshot.get("player", {})
	_john_pos = Vector2i(int(player.get("tx", 0)), int(player.get("ty", 0)))
	_john_facing = str(player.get("facing", "down"))
	_john.position = Vector2(_john_pos) * TPX + Vector2(0, -8 * TILE_SCALE)
	_camera.position = _john.position + Vector2(TPX * 0.5, TPX * 0.5)
	_camera.reset_smoothing()


func _draw() -> void:
	var cam_tile := Vector2i(int(_camera.position.x / TPX), int(_camera.position.y / TPX))
	if terrain != null:
		texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		terrain.draw(self, TPX)
		terrain.refresh_resources(_sim, TPX, self)
	else:
		_art.draw_terrain(self, cam_tile, 36, TPX)
	# draw only what the camera can see (a map of thousands of trees must not cost a draw call each)
	var xf: Transform2D = get_viewport().get_canvas_transform().affine_inverse()
	var vp: Vector2 = get_viewport_rect().size
	var tl: Vector2 = xf * Vector2.ZERO
	var br: Vector2 = xf * vp
	var margin := 6
	var vx0 := int(floor(tl.x / TPX)) - margin
	var vy0 := int(floor(tl.y / TPX)) - margin
	var vx1 := int(ceil(br.x / TPX)) + margin
	var vy1 := int(ceil(br.y / TPX)) + margin
	for road in _snapshot.get("roads", {}).values():
		for tile in road:
			if tile is Array and int(tile[0]) >= vx0 and int(tile[0]) <= vx1 and int(tile[1]) >= vy0 and int(tile[1]) <= vy1:
				_art.draw_road(self, tile, TPX)
	_art.draw_regions(self, _snapshot, TPX)
	_art.industry.draw_belts(self, _snapshot.get("industry", {}), TPX, vx0, vy0, vx1, vy1)
	_art.industry.draw_links(self, _snapshot, TPX)
	var rows: Array = []
	for entity in _snapshot.get("entities", []):
		if typeof(entity) != TYPE_DICTIONARY:
			continue
		var ex := int(entity.get("tx", 0))
		var ey := int(entity.get("ty", 0))
		if entity.has("footprint"):
			ex = int(entity["anchor"][0])
			ey = int(entity["anchor"][1])
		if ex < vx0 or ex > vx1 or ey < vy0 or ey > vy1:
			continue
		rows.append(entity)
	rows.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		var ay := _sort_y(a)
		var by := _sort_y(b)
		if ay == by:
			return int(a.get("tx", 0)) < int(b.get("tx", 0))
		return ay < by
	)
	_art.begin_frame(float(_snapshot.get("time_scale", 1)))
	for entity in rows:
		_art.draw_entity(self, entity, TPX)
	_art.draw_effects(self, _snapshot.get("effects", []), TPX)
	if god != null:
		god.draw_overlay(self)


# ---------------------------------------------------------------- save, load, pause menu and autosave (Wizard Mode; the Python server owns the files)

const SAVE_SLOTS := {"Manual save": "manual", "Quit save": "quit", "Autosave": "auto"}


## A save is a pure read of the world on the server: slot names are "manual" (pause menu), "quit" (on leaving) and "auto" (timed here).
func save_slot(slot: String) -> Dictionary:
	var reply: Dictionary = _sim.op({"op": "save", "slot": slot})
	if str(reply.get("status", "")) == "ok":
		_hud_area_lbl.text = "Saved (%s)" % slot
	return reply


## Load a slot and rebuild everything the client drew from the old world: terrain, entity rows, the wizard's place, labels and story panels.
func load_slot(slot: String, prev := false) -> Dictionary:
	var reply: Dictionary = _sim.op({"op": "load", "slot": slot, "prev": prev})
	if str(reply.get("status", "")) != "ok":
		return reply
	var tview = TerrainView.new()
	if tview.load_from(reply):
		terrain = tview
	if story_ui != null:
		story_ui.close_dialog()
	if wizard_labels != null:
		wizard_labels._clear_all()
	_art._vis.clear()
	selected_ids = {}
	_static_rows.clear()
	_solid.clear()
	_solid_tile_of.clear()
	_apply_snapshot(reply.get("snapshot", {}))
	_seq = int(_snapshot.get("clock_sequence", 0))
	_clock_acc = 0.0
	_place_john_from_snapshot()
	_update_john_sprite(0)
	if story_ui != null:
		story_ui.refresh()
	_hud_area_lbl.text = "Loaded (%s)" % slot
	queue_redraw()
	return reply


## Why an autosave has to wait ("" when the moment is quiet): a duel board, a dialogue, a dungeon view, the pause menu or a summoned worker.
func autosave_wait_reason() -> String:
	if _snapshot.is_empty():
		return "no_world"
	if _duel_open:
		return "duel"
	if _menu_open:
		return "menu"
	if story_ui != null:
		if story_ui.dialog.visible:
			return "dialogue"
		if story_ui.dungeon.visible:
			return "dungeon"
		var st = _snapshot.get("story", {})
		if typeof(st) == TYPE_DICTIONARY and not (st.get("summoned", []) as Array).is_empty():
			return "summoned"
	if _input_locked:
		return "locked"
	return ""


func _autosave_tick(delta: float) -> void:
	if _snapshot.is_empty():
		return
	_autosave_acc += delta
	if _autosave_acc < autosave_seconds or autosave_wait_reason() != "":
		return  # not due yet, or sent at the next quiet moment
	_autosave_acc = 0.0
	if str(save_slot("auto").get("status", "")) == "ok":
		autosave_count += 1


## Escape and the menu button: Continue, Save game, Load game, Save and quit.
func _on_menu() -> void:
	if _input_locked or _duel_open or _snapshot.is_empty():
		return
	_input_locked = true
	_menu_open = true
	_touch.set_enabled(false)
	while true:
		var choice: String = await _dialogue.choose_async("Paused.", ["Continue", "Save game", "Load game", "Save and quit"])
		if choice == "Save game":
			var r := save_slot("manual")
			await _dialogue.say_async("", "Game saved." if str(r.get("status", "")) == "ok" else "The game could not be saved (%s)." % str(r.get("reason", "")))
		elif choice == "Load game":
			var pick: String = await _dialogue.choose_async("Load which save?", SAVE_SLOTS.keys() + ["Back"])
			if SAVE_SLOTS.has(pick):
				var r := load_slot(str(SAVE_SLOTS[pick]))
				if str(r.get("status", "")) == "ok":
					break
				await _dialogue.say_async("", "That save cannot be loaded (%s)." % str(r.get("reason", "")))
		elif choice == "Save and quit":
			save_slot("quit")
			get_tree().quit()
			return
		else:
			break
	_menu_open = false
	_input_locked = false
	_touch.set_enabled(true)


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST and not _snapshot.is_empty():
		save_slot("quit")  # closing the window saves first
