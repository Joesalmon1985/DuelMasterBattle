extends Node2D
class_name DmbFxClockArea

## Playable FX-CLOCK local area: wizard, terrain, NPC, exits.
## Local motion is Godot-owned; Travel/Wait/Observe/Interact go through WorldClient.

signal exit_activated(to_node: String)
signal entity_selected(entity_id: String)
signal request_interact(entity_id: String)
signal request_observe(entity_id: String)

const PIXEL := "res://assets/pixel/"
const TILE := 64
const GRID_W := 14
const GRID_H := 10
const INTERACT_RANGE_PX := 72.0
const OBSERVE_RANGE_PX := 280.0

var client  # DmbWorldClient
var current_node: String = "node:1"
var selected_entity: String = ""
var travel_pending: bool = false

var _wizard: Sprite2D
var _camera: Camera2D
var _tiles: Node2D
var _actors: Node2D
var _labels: Node2D
var _npc_nodes: Dictionary = {}  # entity_id -> Sprite2D
var _exit_nodes: Dictionary = {}  # to_node -> Area2D marker
var _move_dir := Vector2.ZERO
var _facing := "down"
var _anim_t := 0.0
var _anim_frame := 0
var _blockers: Dictionary = {}  # Vector2i -> true
var _touch  # TouchPad
var _feedback: Label
var _area_title: Label


func setup(world_client, touch_pad) -> void:
	client = world_client
	_touch = touch_pad
	if _touch:
		_touch.direction_changed.connect(_on_dir)
		_touch.action_pressed.connect(_on_action)
	_build_roots()
	rebuild_from_view(client.request_view("player"))


func _build_roots() -> void:
	_tiles = Node2D.new()
	add_child(_tiles)
	_actors = Node2D.new()
	add_child(_actors)
	_labels = Node2D.new()
	add_child(_labels)
	_wizard = Sprite2D.new()
	_wizard.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_wizard.scale = Vector2(4, 4)
	_actors.add_child(_wizard)
	_camera = Camera2D.new()
	_camera.position_smoothing_enabled = true
	_wizard.add_child(_camera)
	_camera.call_deferred("make_current")
	_feedback = Label.new()
	_feedback.position = Vector2(8, -28)
	_feedback.z_index = 20
	_wizard.add_child(_feedback)
	_area_title = Label.new()
	_area_title.z_index = 5
	_area_title.position = Vector2(16, 8)
	_area_title.add_theme_font_size_override("font_size", 22)
	add_child(_area_title)
	_set_wizard_texture("down", 0)


func rebuild_from_view(view: Dictionary) -> void:
	var player: Dictionary = view.get("player", {})
	current_node = str(player.get("node_id", current_node))
	var pos = player.get("position", [4, 5])
	if typeof(pos) == TYPE_ARRAY or typeof(pos) == TYPE_PACKED_FLOAT32_ARRAY:
		_wizard.position = Vector2(float(pos[0]) * TILE + TILE * 0.5, float(pos[1]) * TILE + TILE * 0.5)
	_facing = str(player.get("facing", _facing))
	_set_wizard_texture(_facing, _anim_frame)
	_rebuild_tiles()
	_rebuild_people(view.get("people", {}))
	_rebuild_exits(view.get("board", {}).get("nodes", {}))
	var node_info: Dictionary = view.get("board", {}).get("nodes", {}).get(current_node, {})
	_area_title.text = str(node_info.get("label", current_node))


func _theme() -> String:
	# Distinct themes so adjacent nodes look different.
	return "grass" if current_node == "node:1" else "path"


func _rebuild_tiles() -> void:
	for c in _tiles.get_children():
		c.queue_free()
	_blockers.clear()
	var theme := _theme()
	var ground := "tiles/dirt.png" if theme == "grass" else "tiles/path.png"
	var wall := "tiles/wood.png"
	for y in range(GRID_H):
		for x in range(GRID_W):
			var edge := x == 0 or y == 0 or x == GRID_W - 1 or y == GRID_H - 1
			# Leave an exit gap on the east for home, west for road.
			var exit_gap := false
			if current_node == "node:1" and x == GRID_W - 1 and y in [4, 5]:
				exit_gap = true
			if current_node == "node:2" and x == 0 and y in [4, 5]:
				exit_gap = true
			var spr := Sprite2D.new()
			spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
			spr.centered = false
			spr.position = Vector2(x * TILE, y * TILE)
			spr.scale = Vector2(TILE / 16.0, TILE / 16.0)
			if edge and not exit_gap:
				spr.texture = load(PIXEL + wall)
				_blockers[Vector2i(x, y)] = true
			else:
				spr.texture = load(PIXEL + ground)
				if theme == "grass" and (x + y) % 7 == 0 and not edge:
					# Sparse trees as blockers / readable obstacles.
					var tree := Sprite2D.new()
					tree.texture = load(PIXEL + "props/tree_1.png")
					tree.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
					tree.centered = false
					tree.position = Vector2(x * TILE, y * TILE - 16)
					tree.scale = Vector2(TILE / 16.0, TILE / 16.0)
					_tiles.add_child(tree)
					_blockers[Vector2i(x, y)] = true
			_tiles.add_child(spr)
	# Sign near exit
	var sign := Sprite2D.new()
	sign.texture = load(PIXEL + "props/sign.png")
	sign.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sign.scale = Vector2(3, 3)
	if current_node == "node:1":
		sign.position = Vector2((GRID_W - 2) * TILE, 4 * TILE)
	else:
		sign.position = Vector2(2 * TILE, 4 * TILE)
	_tiles.add_child(sign)


func _rebuild_people(people: Dictionary) -> void:
	for id in _npc_nodes.keys():
		_npc_nodes[id].queue_free()
	_npc_nodes.clear()
	for c in _labels.get_children():
		c.queue_free()
	for entity_id in people.keys():
		var info: Dictionary = people[entity_id]
		var grid := _person_grid_from_info(info)
		if grid.x < 0:
			continue
		var spr := Sprite2D.new()
		spr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		spr.scale = Vector2(4, 4)
		spr.position = Vector2(grid.x * TILE + TILE * 0.5, grid.y * TILE + TILE * 0.5)
		DmbActorVisual.apply(spr, PIXEL, "villager_a", "down", 0, "person")
		spr.set_meta("entity_id", entity_id)
		_actors.add_child(spr)
		_npc_nodes[entity_id] = spr
		var lbl := Label.new()
		lbl.text = _label_for(info)
		lbl.position = spr.position + Vector2(-30, -48)
		lbl.add_theme_font_size_override("font_size", 16)
		lbl.set_meta("entity_id", entity_id)
		_labels.add_child(lbl)



func _person_grid_from_info(info: Dictionary) -> Vector2i:
	if str(info.get("node_id", "")) != current_node:
		return Vector2i(-1, -1)
	var grid = info.get("grid", [])
	if typeof(grid) == TYPE_ARRAY and grid.size() >= 2:
		return Vector2i(int(grid[0]), int(grid[1]))
	return Vector2i(-1, -1)


func _label_for(info: Dictionary) -> String:
	if not bool(info.get("known", false)):
		return "unknown"
	if info.get("name") != null and str(info.get("name")) != "":
		return str(info["name"])
	if info.get("role") != null:
		return str(info["role"])
	return str(info.get("label", "unknown"))


func _rebuild_exits(nodes: Dictionary) -> void:
	for id in _exit_nodes.keys():
		_exit_nodes[id].queue_free()
	_exit_nodes.clear()
	var info: Dictionary = nodes.get(current_node, {})
	for to_node in info.get("exits", []):
		var marker := Area2D.new()
		var col := CollisionShape2D.new()
		var shape := RectangleShape2D.new()
		shape.size = Vector2(TILE * 1.2, TILE * 2.2)
		col.shape = shape
		marker.add_child(col)
		var glow := ColorRect.new()
		glow.size = Vector2(TILE, TILE * 2)
		glow.position = Vector2(-TILE * 0.5, -TILE)
		glow.color = Color(0.95, 0.85, 0.2, 0.35) if current_node == "node:1" else Color(0.3, 0.7, 1.0, 0.35)
		marker.add_child(glow)
		var tip := Label.new()
		tip.text = "Exit → %s" % ("Road" if to_node == "node:2" else "Home")
		tip.position = Vector2(-40, -TILE - 24)
		marker.add_child(tip)
		if current_node == "node:1":
			marker.position = Vector2((GRID_W - 1) * TILE + TILE * 0.5, 5 * TILE)
		else:
			marker.position = Vector2(TILE * 0.5, 5 * TILE)
		marker.set_meta("to_node", to_node)
		marker.input_pickable = true
		marker.monitoring = true
		marker.monitorable = true
		marker.input_event.connect(_on_exit_input.bind(str(to_node)))
		add_child(marker)
		_exit_nodes[str(to_node)] = marker


func try_use_exit() -> void:
	for to_node in _exit_nodes.keys():
		if _wizard.position.distance_to(_exit_nodes[to_node].position) <= TILE * 1.8:
			_activate_exit(to_node)
			return
	_feedback.text = "No exit in range"


func _on_exit_input(_viewport, event: InputEvent, _shape_idx: int, to_node: String) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_activate_exit(to_node)
	elif event is InputEventScreenTouch and event.pressed:
		_activate_exit(to_node)


func _activate_exit(to_node: String) -> void:
	if travel_pending:
		return
	if _wizard.position.distance_to(_exit_nodes[to_node].position) > TILE * 1.8:
		_feedback.text = "Move closer to the exit"
		return
	travel_pending = true
	_feedback.text = "Travel pending…"
	exit_activated.emit(to_node)


func acknowledge_travel(to_node: String, view: Dictionary) -> void:
	travel_pending = false
	_feedback.text = ""
	rebuild_from_view(view)


func reject_travel(reason: String) -> void:
	travel_pending = false
	_feedback.text = "Travel rejected: %s" % reason


func _on_dir(dir: Vector2i) -> void:
	_move_dir = Vector2(dir)


func _on_action() -> void:
	# Prefer exit when standing on it; else observe/interact selection.
	for to_node in _exit_nodes.keys():
		if _wizard.position.distance_to(_exit_nodes[to_node].position) <= TILE * 1.8:
			_activate_exit(to_node)
			return
	if selected_entity == "":
		_pick_nearest()
	if selected_entity == "":
		_feedback.text = "Nothing selected"
		return
	var dist := _distance_to(selected_entity)
	if dist < 0:
		return
	if dist <= INTERACT_RANGE_PX:
		request_interact.emit(selected_entity)
	elif dist <= OBSERVE_RANGE_PX:
		request_observe.emit(selected_entity)
	else:
		_feedback.text = "Too far"


func _pick_nearest() -> void:
	var best := ""
	var best_d := INF
	for entity_id in _npc_nodes.keys():
		var d := _wizard.position.distance_to(_npc_nodes[entity_id].position)
		if d < best_d:
			best_d = d
			best = entity_id
	if best != "" and best_d <= OBSERVE_RANGE_PX:
		selected_entity = best
		entity_selected.emit(best)


func _distance_to(entity_id: String) -> float:
	if not _npc_nodes.has(entity_id):
		return -1.0
	return _wizard.position.distance_to(_npc_nodes[entity_id].position)


func _process(delta: float) -> void:
	if client == null or travel_pending:
		return
	# Pointer / pad movement
	var step := _move_dir
	if step == Vector2.ZERO:
		# Drag / click-to-nudge on open ground via one pointer: mouse held.
		if Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
			var local := get_global_mouse_position()
			var delta_v := local - _wizard.global_position
			if delta_v.length() > 12:
				step = delta_v.normalized()
	if step != Vector2.ZERO:
		if abs(step.x) > abs(step.y):
			_facing = "right" if step.x > 0 else "left"
		else:
			_facing = "down" if step.y > 0 else "up"
		var speed := 140.0
		var nxt := _wizard.position + step.normalized() * speed * delta
		if not _blocked(nxt):
			_wizard.position = nxt
		_anim_t += delta
		if _anim_t > 0.16:
			_anim_t = 0.0
			_anim_frame = 1 - _anim_frame
			_set_wizard_texture(_facing, _anim_frame)
	# Highlight selection
	for entity_id in _npc_nodes.keys():
		var spr: Sprite2D = _npc_nodes[entity_id]
		spr.modulate = Color(1.3, 1.3, 0.7) if entity_id == selected_entity else Color.WHITE


func _blocked(world_pos: Vector2) -> bool:
	var gx := int(world_pos.x / TILE)
	var gy := int(world_pos.y / TILE)
	return bool(_blockers.get(Vector2i(gx, gy), false))


func _set_wizard_texture(facing: String, frame: int) -> void:
	var path := PIXEL + "chars/john_staff_%s_%d.png" % [facing, frame]
	if not ResourceLoader.exists(path):
		path = PIXEL + "chars/john_%s_%d.png" % [facing, frame]
	if ResourceLoader.exists(path):
		_wizard.texture = load(path)


func wizard_grid() -> Array:
	return [snapped(_wizard.position.x / TILE - 0.5, 0.01), snapped(_wizard.position.y / TILE - 0.5, 0.01)]


func _unhandled_input(event: InputEvent) -> void:
	# Tap entities to select / observe.
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var gp := get_global_mouse_position()
		for entity_id in _npc_nodes.keys():
			if _npc_nodes[entity_id].global_position.distance_to(gp) < 40:
				selected_entity = entity_id
				entity_selected.emit(entity_id)
				var d := _distance_to(entity_id)
				if d <= INTERACT_RANGE_PX:
					request_interact.emit(entity_id)
				elif d <= OBSERVE_RANGE_PX:
					request_observe.emit(entity_id)
				get_viewport().set_input_as_handled()
				return
