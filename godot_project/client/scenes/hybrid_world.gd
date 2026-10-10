extends Overworld

const HexCoords = preload("res://client/hybrid/hex_coords.gd")
const SimClient = preload("res://client/hybrid/sim_client.gd")
const DuelAdapter = preload("res://client/encounters/duel_lease_adapter.gd")

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
	_camera.zoom = Vector2(0.18, 0.18)
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
	var reply := _sim.op({"op": "snapshot"})
	_apply_snapshot(reply.get("snapshot", {}))
	_place_john_from_snapshot()
	_update_john_sprite(0)
	_hud_area_lbl.text = "Wizard RTS"


func _process(delta: float) -> void:
	super._process(delta)
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


func _tile_char(_x: int, _y: int) -> String:
	if not HexCoords.tile_in_map(_x, _y):
		return " "
	return "."


func is_walkable(p: Vector2i) -> bool:
	if not HexCoords.tile_in_map(p.x, p.y):
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
	var radius := 48
	for ty in range(_john_pos.y - radius, _john_pos.y + radius + 1):
		for tx in range(_john_pos.x - radius, _john_pos.x + radius + 1):
			if not HexCoords.tile_in_map(tx, ty):
				continue
			var hex: Vector2i = HexCoords.tile_to_hex(tx, ty)
			var shade := 0.18 + float((hex.x + hex.y) % 3) * 0.06
			draw_rect(Rect2(tx * TPX, ty * TPX, TPX - 2, TPX - 2), Color(0.15, shade, 0.18), true)
	for road in _snapshot.get("roads", {}).values():
		for tile in road:
			if tile is Array and tile.size() >= 2:
				draw_rect(Rect2(int(tile[0]) * TPX + 18, int(tile[1]) * TPX + 18, 28, 28), Color(0.45, 0.36, 0.22), true)
	for entity in _snapshot.get("entities", []):
		if typeof(entity) != TYPE_DICTIONARY:
			continue
		var tx := int(entity.get("tx", 0))
		var ty := int(entity.get("ty", 0))
		var kind := str(entity.get("kind", ""))
		var color := Color(0.9, 0.9, 0.9)
		var faction := str(entity.get("faction_name", ""))
		if faction == "Red":
			color = Color(0.85, 0.25, 0.2)
		elif faction == "Blue":
			color = Color(0.25, 0.4, 0.9)
		if kind == "hazard":
			color = Color(0.75, 0.2, 0.85)
		elif kind == "carrier":
			color = Color(0.95, 0.8, 0.2)
		var size := 48.0 if kind in ["warehouse", "producer", "processor"] else 28.0
		draw_rect(Rect2(tx * TPX + 8, ty * TPX + 8, size, size), color, true)
		if _font != null:
			draw_string(_font, Vector2(tx * TPX, ty * TPX - 4), str(entity.get("label", kind)), HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(1, 1, 1))
	var player: Dictionary = _snapshot.get("player", {})
	var hex_text := "hex %s  game_ms %s  crossings %d" % [str(player.get("hex", [])), str(_snapshot.get("game_ms", 0)), _hex_crossings]
	if _font != null:
		draw_string(_font, _camera.position + Vector2(-280, -180), hex_text, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color(1, 1, 0.7))
