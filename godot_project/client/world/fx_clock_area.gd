extends Node2D
class_name DmbFxClockArea

## Playable FX-CLOCK local area: wizard, terrain, NPC, exits.
## Local motion is Godot-owned; Travel/Wait/Observe/Interact go through WorldClient.

signal exit_activated(to_node: String)
signal entity_selected(entity_id: String)
signal request_interact(entity_id: String)
signal request_observe(entity_id: String)
signal action_hint_changed(hint: String)

const PIXEL := "res://assets/pixel/"
const TILE := 64
const GRID_W := 14
const GRID_H := 10
const INTERACT_RANGE_PX := 72.0
const OBSERVE_RANGE_PX := 280.0

# Fixture interior blockers (full-tile trees). Keep row y=5 and the NPC approach clear.
# Spawn [4,5] → NPC [10,3] → east exit (13,4–5) and the return path stay open.
const FIXTURE_TREES_HOME := [
	Vector2i(2, 2),
	Vector2i(7, 7),
	Vector2i(11, 7),
]
const FIXTURE_TREES_ROAD := [
	Vector2i(3, 2),
	Vector2i(8, 7),
	Vector2i(11, 3),
]

var client  # DmbWorldClient
var current_node: String = "node:1"
var selected_entity: String = ""
var travel_pending: bool = false
var movement_enabled: bool = true

var _wizard: Sprite2D
var _ground: Node2D
var _props: Node2D
var _actors: Node2D
var _labels: Node2D
var _npc_nodes: Dictionary = {}  # entity_id -> Sprite2D
var _exit_nodes: Dictionary = {}  # to_node -> Node2D marker
var _label_nodes: Dictionary = {}  # entity_id -> Label
var _move_dir := Vector2.ZERO
var _facing := "down"
var _anim_t := 0.0
var _anim_frame := 0
var _blockers: Dictionary = {}  # Vector2i -> true
var _touch  # TouchPad
var _feedback: Label
var _area_title: Label
var _built := false
var _last_hint := ""


func setup(world_client, touch_pad) -> void:
	client = world_client
	_touch = touch_pad
	if _touch:
		_touch.direction_changed.connect(_on_dir)
		_touch.action_pressed.connect(_on_action)
	_build_roots()
	rebuild_from_view(client.request_view("player"))
	_refresh_action_hint()


func set_movement_enabled(on: bool) -> void:
	movement_enabled = on
	if not on:
		_move_dir = Vector2.ZERO
	_refresh_action_hint()


func _build_roots() -> void:
	if _built:
		return
	_built = true
	_ground = Node2D.new()
	_ground.name = "Ground"
	_ground.z_index = 0
	add_child(_ground)
	_props = Node2D.new()
	_props.name = "Props"
	_props.z_index = 1
	add_child(_props)
	_actors = Node2D.new()
	_actors.name = "Actors"
	_actors.z_index = 2
	add_child(_actors)
	_labels = Node2D.new()
	_labels.name = "Labels"
	_labels.z_index = 3
	add_child(_labels)
	_wizard = Sprite2D.new()
	_wizard.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_wizard.scale = Vector2(4, 4)
	_actors.add_child(_wizard)
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
	## Full scene construction / deliberate pose restore (load, travel, bootstrap).
	if not _built:
		_build_roots()
	var player: Dictionary = view.get("player", {})
	current_node = str(player.get("node_id", current_node))
	_restore_wizard_pose(player)
	_rebuild_tiles()
	_rebuild_people(view.get("people", {}))
	_rebuild_exits(view.get("board", {}).get("nodes", {}))
	var node_info: Dictionary = view.get("board", {}).get("nodes", {}).get(current_node, {})
	_area_title.text = str(node_info.get("label", current_node))
	_refresh_action_hint()


func apply_projections(view: Dictionary) -> void:
	## HUD/knowledge refresh only — never resets Godot-owned local pose.
	if not _built or _wizard == null:
		return
	var player: Dictionary = view.get("player", {})
	var node_id := str(player.get("node_id", current_node))
	if node_id != current_node:
		rebuild_from_view(view)
		return
	var people: Dictionary = view.get("people", {})
	for entity_id in _label_nodes.keys():
		if people.has(entity_id):
			_label_nodes[entity_id].text = _label_for(people[entity_id])
	var node_info: Dictionary = view.get("board", {}).get("nodes", {}).get(current_node, {})
	if _area_title:
		_area_title.text = str(node_info.get("label", current_node))
	_refresh_action_hint()


func _restore_wizard_pose(player: Dictionary) -> void:
	var pos = player.get("position", [4, 5])
	if typeof(pos) == TYPE_ARRAY or typeof(pos) == TYPE_PACKED_FLOAT32_ARRAY:
		_wizard.position = Vector2(float(pos[0]) * TILE + TILE * 0.5, float(pos[1]) * TILE + TILE * 0.5)
	_facing = str(player.get("facing", _facing))
	_set_wizard_texture(_facing, _anim_frame)


func _theme() -> String:
	return "grass" if current_node == "node:1" else "path"


func _fixture_trees() -> Array:
	return FIXTURE_TREES_HOME if current_node == "node:1" else FIXTURE_TREES_ROAD


func _rebuild_tiles() -> void:
	for c in _ground.get_children():
		c.queue_free()
	for c in _props.get_children():
		c.queue_free()
	_blockers.clear()
	var theme := _theme()
	var ground_tex := "tiles/dirt.png" if theme == "grass" else "tiles/path.png"
	var wall_tex := "tiles/wood.png"
	# Pass 1: ground / walls only (readable floor first).
	for y in range(GRID_H):
		for x in range(GRID_W):
			var edge := x == 0 or y == 0 or x == GRID_W - 1 or y == GRID_H - 1
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
				spr.texture = load(PIXEL + wall_tex)
				_blockers[Vector2i(x, y)] = true
			else:
				spr.texture = load(PIXEL + ground_tex)
			_ground.add_child(spr)
	# Pass 2: full-tile tree obstacles — sprite and collision share the same cell.
	for cell in _fixture_trees():
		if bool(_blockers.get(cell, false)):
			continue
		var tree := Sprite2D.new()
		tree.texture = load(PIXEL + "props/tree_1.png")
		tree.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		tree.centered = false
		# Fit tree art to the full tile so it matches the blocker footprint.
		tree.position = Vector2(cell.x * TILE, cell.y * TILE)
		tree.scale = Vector2(TILE / 16.0, TILE / 16.0)
		_props.add_child(tree)
		_blockers[cell] = true
	# Decorative sign (non-blocking) beside the exit approach.
	var sign := Sprite2D.new()
	sign.texture = load(PIXEL + "props/sign.png")
	sign.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	sign.centered = false
	sign.scale = Vector2(TILE / 16.0 * 0.75, TILE / 16.0 * 0.75)
	if current_node == "node:1":
		sign.position = Vector2(12 * TILE + 8, 3 * TILE + 8)
	else:
		sign.position = Vector2(1 * TILE + 8, 3 * TILE + 8)
	_props.add_child(sign)


func _rebuild_people(people: Dictionary) -> void:
	for id in _npc_nodes.keys():
		_npc_nodes[id].queue_free()
	_npc_nodes.clear()
	for id in _label_nodes.keys():
		_label_nodes[id].queue_free()
	_label_nodes.clear()
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
		_label_nodes[entity_id] = lbl


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
		var glow := Polygon2D.new()
		glow.polygon = PackedVector2Array([
			Vector2(-TILE * 0.5, -TILE),
			Vector2(TILE * 0.5, -TILE),
			Vector2(TILE * 0.5, TILE),
			Vector2(-TILE * 0.5, TILE),
		])
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


func nearest_exit_id() -> String:
	var best := ""
	var best_d := INF
	for to_node in _exit_nodes.keys():
		var d := _wizard.position.distance_to(_exit_nodes[to_node].position)
		if d < best_d:
			best_d = d
			best = str(to_node)
	return best


func exit_in_range(to_node: String = "") -> bool:
	if to_node == "":
		to_node = nearest_exit_id()
	if to_node == "" or not _exit_nodes.has(to_node):
		return false
	return _wizard.position.distance_to(_exit_nodes[to_node].position) <= TILE * 1.8


func compute_action_hint() -> String:
	if travel_pending:
		return "Travel…"
	if exit_in_range():
		return "Travel"
	if selected_entity == "":
		_pick_nearest(false)
	if selected_entity != "":
		var dist := _distance_to(selected_entity)
		if dist < 0:
			return "✦"
		if dist <= INTERACT_RANGE_PX:
			return "Interact"
		if dist <= OBSERVE_RANGE_PX:
			return "Observe"
		return "Move closer"
	if nearest_exit_id() != "":
		return "Move closer"
	return "✦"


func _refresh_action_hint() -> void:
	var hint := compute_action_hint()
	if hint == _last_hint:
		return
	_last_hint = hint
	if _touch and _touch.has_method("set_action_label"):
		_touch.set_action_label(hint)
	action_hint_changed.emit(hint)


func try_use_exit() -> void:
	for to_node in _exit_nodes.keys():
		if exit_in_range(to_node):
			_activate_exit(to_node)
			return
	_feedback.text = "No exit in range"


func _on_exit_input(_viewport, event: InputEvent, _shape_idx: int, to_node: String) -> void:
	if not movement_enabled:
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_activate_exit(to_node)
	elif event is InputEventScreenTouch and event.pressed:
		_activate_exit(to_node)


func _activate_exit(to_node: String) -> void:
	if travel_pending or not movement_enabled:
		return
	if not exit_in_range(to_node):
		_feedback.text = "Move closer to the exit"
		_refresh_action_hint()
		return
	travel_pending = true
	_feedback.text = "Travel pending…"
	_refresh_action_hint()
	exit_activated.emit(to_node)


func acknowledge_travel(to_node: String, view: Dictionary) -> void:
	travel_pending = false
	selected_entity = ""
	_feedback.text = ""
	_last_hint = ""
	rebuild_from_view(view)


func reject_travel(reason: String) -> void:
	travel_pending = false
	_feedback.text = "Travel rejected: %s" % reason
	_refresh_action_hint()


func _on_dir(dir: Vector2i) -> void:
	if not movement_enabled:
		_move_dir = Vector2.ZERO
		return
	_move_dir = Vector2(dir)


func _on_action() -> void:
	if not movement_enabled:
		return
	if exit_in_range():
		_activate_exit(nearest_exit_id())
		return
	if selected_entity == "":
		_pick_nearest(true)
	if selected_entity == "":
		_feedback.text = "Nothing selected"
		_refresh_action_hint()
		return
	var dist := _distance_to(selected_entity)
	if dist < 0:
		return
	if dist <= INTERACT_RANGE_PX:
		request_interact.emit(selected_entity)
	elif dist <= OBSERVE_RANGE_PX:
		request_observe.emit(selected_entity)
	else:
		_feedback.text = "Move closer"
	_refresh_action_hint()


func _pick_nearest(emit_signal: bool = true) -> void:
	var best := ""
	var best_d := INF
	for entity_id in _npc_nodes.keys():
		var d := _wizard.position.distance_to(_npc_nodes[entity_id].position)
		if d < best_d:
			best_d = d
			best = entity_id
	if best != "" and best_d <= OBSERVE_RANGE_PX:
		selected_entity = best
		if emit_signal:
			entity_selected.emit(best)


func _distance_to(entity_id: String) -> float:
	if not _npc_nodes.has(entity_id):
		return -1.0
	return _wizard.position.distance_to(_npc_nodes[entity_id].position)


func _gui_blocks_world_pointer() -> bool:
	var hovered := get_viewport().gui_get_hovered_control()
	return hovered != null


func _process(delta: float) -> void:
	if client == null:
		return
	if travel_pending or not movement_enabled:
		_refresh_action_hint()
		return
	var step := _move_dir
	if step == Vector2.ZERO and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		if not _gui_blocks_world_pointer():
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
	for entity_id in _npc_nodes.keys():
		var spr: Sprite2D = _npc_nodes[entity_id]
		spr.modulate = Color(1.3, 1.3, 0.7) if entity_id == selected_entity else Color.WHITE
	_refresh_action_hint()


func _blocked(world_pos: Vector2) -> bool:
	var gx := int(world_pos.x / TILE)
	var gy := int(world_pos.y / TILE)
	return bool(_blockers.get(Vector2i(gx, gy), false))


func is_cell_blocked(cell: Vector2i) -> bool:
	return bool(_blockers.get(cell, false))


func _set_wizard_texture(facing: String, frame: int) -> void:
	var path := PIXEL + "chars/john_staff_%s_%d.png" % [facing, frame]
	if not ResourceLoader.exists(path):
		path = PIXEL + "chars/john_%s_%d.png" % [facing, frame]
	if ResourceLoader.exists(path):
		_wizard.texture = load(path)


func wizard_grid() -> Array:
	return [snapped(_wizard.position.x / TILE - 0.5, 0.01), snapped(_wizard.position.y / TILE - 0.5, 0.01)]


func world_pixel_size() -> Vector2:
	return Vector2(GRID_W * TILE, GRID_H * TILE)


func wizard_position() -> Vector2:
	return _wizard.position if _wizard else Vector2.ZERO


func _unhandled_input(event: InputEvent) -> void:
	if not movement_enabled:
		return
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
				_refresh_action_hint()
				return
