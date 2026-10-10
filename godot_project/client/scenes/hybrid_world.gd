extends Overworld

const HexCoords = preload("res://client/hybrid/hex_coords.gd")
const SimClient = preload("res://client/hybrid/sim_client.gd")
const DuelAdapter = preload("res://client/encounters/duel_lease_adapter.gd")
const HybridArt = preload("res://client/hybrid/hybrid_art.gd")
const GodMode = preload("res://client/hybrid/god_mode.gd")
const TerrainView = preload("res://client/hybrid/terrain_view.gd")

## Continuous hybrid world. Movement, camera, and the retained duel board
## come from the existing Overworld and DmbDuelLeaseAdapter. The Python
## server owns stocks, clocks, and entity positions.

var _sim = SimClient.new()
var _adapter = DuelAdapter.new()
var _snapshot: Dictionary = {}
var _blocked: Dictionary = {}
var _seq := 0
var _clock_acc := 0.0
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
var terrain = null  # TerrainView once the sim has sent its terrain
var selected_ids: Dictionary = {}:
	set(v):
		selected_ids = v
		_art.selected = v


func _ready() -> void:
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


func _process(delta: float) -> void:
	super._process(delta)
	if _camera_nudge != Vector2.ZERO:
		_camera.position += _camera_nudge
	if camera_focus != Vector2.INF:
		_camera.position = camera_focus
	if _snapshot.is_empty() or _duel_open:
		queue_redraw()
		return
	_clock_acc += delta
	if _clock_acc >= 0.1:
		var ms := int(_clock_acc * 1000.0)
		_clock_acc = 0.0
		_seq += 1
		var reply := _sim.op({"op": "advance", "ms": ms, "sequence": _seq})
		if str(reply.get("status", "")) == "ok":
			_apply_snapshot(reply.get("snapshot", {}))
			_seq = int(_snapshot.get("clock_sequence", _seq))
	queue_redraw()


func _arrived() -> void:
	if _sim._peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return
	var reply := _sim.op({
		"op": "pose",
		"tx": _john_pos.x,
		"ty": _john_pos.y,
		"facing": _john_facing,
	})
	if str(reply.get("status", "")) == "ok":
		_apply_snapshot(reply.get("snapshot", {}))
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
	return not _blocked.has(p)


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
	_snapshot = snap
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
	for road in _snapshot.get("roads", {}).values():
		for tile in road:
			if tile is Array:
				_art.draw_road(self, tile, TPX)
	var rows: Array = _snapshot.get("entities", [])
	rows.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		var ay := int(a.get("ty", 0))
		var by := int(b.get("ty", 0))
		if ay == by:
			return int(a.get("tx", 0)) < int(b.get("tx", 0))
		return ay < by
	)
	for entity in rows:
		if typeof(entity) != TYPE_DICTIONARY:
			continue
		_art.draw_entity(self, entity, TPX)
	_art.draw_effects(self, _snapshot.get("effects", []), TPX)
	if god != null:
		god.draw_overlay(self)
