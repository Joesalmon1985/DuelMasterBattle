extends Node2D
class_name PuzzleTestRoom

## Puzzle Test Room - runs a single puzzle from the catalogue in isolation
## Uses placeholder graphics (colored rectangles) to clearly communicate puzzle state

const _VT = preload("res://client/scripts/visual_theme.gd")
const _PuzzleKit = preload("res://sim/world/puzzle_kit.gd")
const _PuzzleLogic = preload("res://sim/world/puzzle_logic.gd")
const _Items = preload("res://sim/world/items.gd")
const _Runner = preload("res://client/scripts/puzzle_test_runner.gd")

@onready var grid_container = $GridContainer
@onready var ui_layer = $UILayer
@onready var hud = $UILayer/HUD
@onready var puzzle_title = $UILayer/HUD/PuzzleTitle
@onready var puzzle_desc = $UILayer/HUD/PuzzleDesc
@onready var state_label = $UILayer/HUD/StateLabel
@onready var control_hint = $UILayer/HUD/ControlHint
@onready var inventory_panel = $UILayer/InventoryPanel
@onready var inventory_grid = $UILayer/InventoryPanel/InventoryGrid
@onready var player = $GridContainer/Player
@onready var player_sprite = $GridContainer/Player/PlayerSprite

var current_puzzle: Dictionary = {}
var puzzle_state: Dictionary = {}
var grid_size = Vector2i(16, 10)
var cell_size = 64
var player_grid_pos = Vector2i(2, 5)
var entities: Dictionary = {}  # entity_id -> {node, data}
var inventory: Array = []
var selected_inventory_index: int = -1
var is_solved = false

func _ready() -> void:
	_load_puzzle()
	_build_grid()
	_build_puzzle_entities()
	_update_hud()
	_setup_input()
	_center_camera()

func _load_puzzle() -> void:
	var runner_puzzle = _Runner.get_puzzle()
	if runner_puzzle.is_empty():
		# Fallback: create a default offerings puzzle for testing
		current_puzzle = {
			"id": "test_p1",
			"type": "offerings",
			"title": "The Two Offerings",
			"slots": [
				{"id": "test_p1_s0", "item": "clay_idol"},
				{"id": "test_p1_s1", "item": "brass_gear", "keep": true}
			],
			"items": ["clay_idol"],
			"clue": "Two niches, two shapes cut into the stone. One shape is in this room. The other was made somewhere else."
		}
		inventory = ["clay_idol", "brass_gear"]
	else:
		current_puzzle = runner_puzzle.duplicate(true)
		# Give player the items needed for this puzzle
		inventory = current_puzzle.get("items", []).duplicate()
		# Add some extra items for variety
		for item in ["clay_idol", "grey_stone", "tallow_candle", "mirror_shard"]:
			if item not in inventory:
				inventory.append(item)

	puzzle_state = _PuzzleLogic.fresh_state(current_puzzle)
	is_solved = false

func _build_grid() -> void:
	# Clear existing grid children except player
	for child in grid_container.get_children():
		if child != player:
			child.queue_free()

	# Create floor tiles
	for y in range(grid_size.y):
		for x in range(grid_size.x):
			var tile = ColorRect.new()
			tile.position = Vector2(x * cell_size, y * cell_size)
			tile.custom_minimum_size = Vector2(cell_size, cell_size)
			
			# Checkerboard pattern
			if (x + y) % 2 == 0:
				tile.color = Color(0.15, 0.12, 0.25, 1)
			else:
				tile.color = Color(0.12, 0.10, 0.22, 1)
			
			# Wall borders
			if x == 0 or x == grid_size.x - 1 or y == 0 or y == grid_size.y - 1:
				tile.color = Color(0.3, 0.25, 0.45, 1)
			
			grid_container.add_child(tile)

	# Position player
	player.position = Vector2(player_grid_pos.x * cell_size + cell_size / 2, player_grid_pos.y * cell_size + cell_size / 2)

func _build_puzzle_entities() -> void:
	entities.clear()
	var pid = current_puzzle["id"]
	var cx = int(grid_size.x / 2)
	var cy = int(grid_size.y / 2)
	var base = {"puzzle_key": "test/%s" % pid}

	match str(current_puzzle["type"]):
		"offerings":
			_build_offerings(base, pid, cx, cy)
		"exchange":
			_build_exchange(base, pid, cx, cy)
		"switch_chain":
			_build_switch_chain(base, pid, cx, cy)
		"plate_hold":
			_build_plate_hold(base, pid, cx, cy)
		"timed_gate":
			_build_timed_gate(base, pid, cx, cy)
		"mosaic":
			_build_mosaic(base, pid, cx, cy)
		"magic_target":
			_build_magic_target(base, pid, cx, cy)
		"two_levers":
			_build_two_levers(base, pid, cx, cy)
		_:
			# Catalogue puzzles not in the generator - build generic versions
			_build_catalogue_puzzle(base, pid, cx, cy)

	_update_entity_visuals()

func _build_offerings(base, pid, cx, cy):
	for i in range(current_puzzle["slots"].size()):
		var sl = current_puzzle["slots"][i]
		var filled = puzzle_state.get("filled", {}).has(str(sl["id"]))
		var ent = _create_log_entity(
			"%s_%s" % [pid, sl["id"]],
			Vector2i(cx - 3 + i * 3, cy - 2),
			"idol" if filled else "box",
			{"kind": "place", "slot": str(sl["id"])},
			"A niche" + (" — filled." if filled else ", shaped for something.")
		)
		entities[ent.id] = ent

	for it in current_puzzle["items"]:
		var ent = _create_pickup_entity(
			"%s_%s_item_%s" % [pid, pid, it],
			Vector2i(cx + 4, cy + 1),
			_Items.sprite_of(it),
			{"item": it},
			_Items.describe(it)
		)
		entities[ent.id] = ent

func _build_exchange(base, pid, cx, cy):
	var taken = puzzle_state.get("key_taken", false)
	var ent = _create_log_entity(
		"%s_%s" % [pid, current_puzzle["pedestal"]],
		Vector2i(cx, cy),
		"ring" if not taken else "box",
		{"kind": "exchange"},
		"A plate on a pedestal." + (" A key rests on it." if not taken else " Bare.")
	)
	entities[ent.id] = ent

	for it in current_puzzle["items"]:
		ent = _create_pickup_entity(
			"%s_%s_item_%s" % [pid, pid, it],
			Vector2i(cx - 3, cy + 1),
			_Items.sprite_of(it),
			{"item": it},
			_Items.describe(it)
		)
		entities[ent.id] = ent

func _build_switch_chain(base, pid, cx, cy):
	for i in range(3):
		var ent = _create_log_entity(
			"%s_%s" % [pid, current_puzzle["levers"][i]],
			Vector2i(cx - 3 + i * 2, cy),
			"staff",
			{"kind": "pull", "index": i},
			"Lever %s." % ["one", "two", "three"][i]
		)
		entities[ent.id] = ent

func _build_plate_hold(base, pid, cx, cy):
	var ent = _create_log_entity(
		"%s_%s" % [pid, current_puzzle["plate"]],
		Vector2i(cx, cy),
		"ring",
		{"kind": "place"},
		"A pressure plate."
	)
	entities[ent.id] = ent

	for it in current_puzzle["items"]:
		ent = _create_pickup_entity(
			"%s_%s_item_%s" % [pid, pid, it],
			Vector2i(cx - 3, cy + 1),
			_Items.sprite_of(it),
			{"item": it},
			_Items.describe(it)
		)
		entities[ent.id] = ent

func _build_timed_gate(base, pid, cx, cy):
	var open = puzzle_state.get("open", false)
	var ent = _create_log_entity(
		"%s_%s" % [pid, current_puzzle["lever"]],
		Vector2i(2, cy + 2),
		"staff",
		{"kind": "pull"},
		"A lever, and a rope that runs up into the dark."
	)
	entities[ent.id] = ent

	var gate_ent = _create_log_entity(
		"%s_%s_gate" % [pid, pid],
		Vector2i(cx, 1),
		"door_stone",
		{"kind": "pass"},
		"A gate of iron bars." + (" Lifted — and counting." if open else " Down.")
	)
	entities[gate_ent.id] = gate_ent

func _build_mosaic(base, pid, cx, cy):
	for i in range(4):
		var colors = ["red", "blue", "green", "grey"]
		var ent = _create_log_entity(
			"%s_%s_tile%d" % [pid, pid, i],
			Vector2i(cx - 3 + i * 2, cy),
			"stone_shard",
			{"kind": "tread", "index": i},
			"A %s stone, set in the floor." % colors[i]
		)
		entities[ent.id] = ent

func _build_magic_target(base, pid, cx, cy):
	var spell = int(current_puzzle["spell"])
	var marker = "fire_0" if spell == 1 else ("rock" if spell == 6 else "mirror")
	var ent = _create_log_entity(
		"%s_%s" % [pid, current_puzzle["target"]],
		Vector2i(cx, cy),
		marker,
		{"kind": "cast"},
		"The way is blocked by %s." % str(current_puzzle["desc"])
	)
	entities[ent.id] = ent

func _build_two_levers(base, pid, cx, cy):
	for i in range(2):
		var ent = _create_log_entity(
			"%s_%s" % [pid, current_puzzle["levers"][i]],
			Vector2i(cx - 2 + i * 4, cy),
			"staff",
			{"kind": "pull", "index": i},
			"The %s lever." % ["left", "right"][i]
		)
		entities[ent.id] = ent

func _build_catalogue_puzzle(base, pid, cx, cy):
	# Generic handler for catalogue puzzles not in the generator
	var ptype = str(current_puzzle["type"])
	var desc = current_puzzle.get("desc", "A puzzle room.")

	var ent = _create_log_entity(
		"%s_main" % pid,
		Vector2i(cx, cy),
		"box",
		{"kind": "interact"},
		"%s\n\n%s" % [current_puzzle["title"], desc]
	)
	entities[ent.id] = ent

func _create_log_entity(id, pos, marker, action, text) -> Dictionary:
	var node = ColorRect.new()
	node.name = id
	node.position = Vector2(pos.x * cell_size, pos.y * cell_size)
	node.custom_minimum_size = Vector2(cell_size, cell_size)
	node.color = _marker_color(marker)
	grid_container.add_child(node)

	# Add label
	var label = Label.new()
	label.text = _marker_label(marker)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 18)
	label.add_theme_color_override("font_color", Color(1, 1, 1, 1))
	label.set_anchors_preset(Control.PRESET_FULL_RECT)
	node.add_child(label)

	return {"id": id, "node": node, "pos": pos, "marker": marker, "puzzle_action": action, "text": text, "type": "logs"}

func _create_pickup_entity(id, pos, sprite, grant, text) -> Dictionary:
	var node = ColorRect.new()
	node.name = id
	node.position = Vector2(pos.x * cell_size, pos.y * cell_size)
	node.custom_minimum_size = Vector2(cell_size, cell_size)
	node.color = _Items.color_of(grant["item"])
	grid_container.add_child(node)

	var label = Label.new()
	label.text = _Items.glyph_of(grant["item"])
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.add_theme_font_size_override("font_size", 28)
	label.add_theme_color_override("font_color", Color(1, 1, 1, 1))
	label.set_anchors_preset(Control.PRESET_FULL_RECT)
	node.add_child(label)

	return {"id": id, "node": node, "pos": pos, "sprite": sprite, "grant": grant, "text": text, "type": "pickup"}

func _marker_color(marker: String) -> Color:
	match marker:
		"idol": return Color(0.8, 0.6, 0.2)
		"box": return Color(0.4, 0.35, 0.5)
		"ring": return Color(0.6, 0.6, 0.8)
		"staff": return Color(0.7, 0.5, 0.3)
		"door_stone": return Color(0.5, 0.4, 0.4)
		"stone_shard": return Color(0.7, 0.4, 0.4)
		"fire_0": return Color(0.9, 0.4, 0.2)
		"rock": return Color(0.5, 0.5, 0.55)
		"mirror": return Color(0.4, 0.7, 0.8)
		_: return Color(0.5, 0.5, 0.5)

func _marker_label(marker: String) -> String:
	match marker:
		"idol": return "🗿"
		"box": return "▢"
		"ring": return "⬭"
		"staff": return "⎯"
		"door_stone": return "⛋"
		"stone_shard": return "◇"
		"fire_0": return "🜂"
		"rock": return "▲"
		"mirror": return "◆"
		_: return "?"

func _update_entity_visuals() -> void:
	for ent_data in entities.values():
		var ent = ent_data
		var node = ent.node
		if not is_instance_valid(node):
			continue
		
		var filled = false
		var marker = ent.get("marker", "")
		
		if ent.type == "logs":
			if current_puzzle["type"] == "offerings":
				filled = puzzle_state.get("filled", {}).has(str(ent.id))
				if filled:
					node.color = Color(0.8, 0.6, 0.2)
					var label = node.get_children()[0] if node.get_child_count() > 0 else null
					if label:
						label.text = "🗿"
			elif current_puzzle["type"] == "exchange":
				var taken = puzzle_state.get("key_taken", false)
				if taken:
					node.color = Color(0.4, 0.35, 0.5)
					var label = node.get_children()[0] if node.get_child_count() > 0 else null
					if label:
						label.text = "▢"
			elif current_puzzle["type"] == "timed_gate" and ent.id.ends_with("_gate"):
				var open = puzzle_state.get("open", false)
				if open:
					node.color = Color(0.3, 0.6, 0.3)
					var label = node.get_children()[0] if node.get_child_count() > 0 else null
					if label:
						label.text = "⛋"
				else:
					node.color = Color(0.5, 0.4, 0.4)

func _update_hud() -> void:
	puzzle_title.text = current_puzzle.get("title", "PUZZLE TEST ROOM")
	puzzle_desc.text = current_puzzle.get("clue", current_puzzle.get("desc", "Select a puzzle from the menu"))
	
	var state_text = "State: "
	if is_solved:
		state_text += "SOLVED ✓"
	elif current_puzzle["type"] == "offerings":
		var filled = puzzle_state.get("filled", {}).size()
		var total = current_puzzle["slots"].size()
		state_text += "Offerings: %d/%d filled" % [filled, total]
	elif current_puzzle["type"] == "exchange":
		var taken = puzzle_state.get("key_taken", false)
		var placed = puzzle_state.get("placed", "") != ""
		state_text += "Key taken: %s | Item placed: %s" % [taken, placed]
	elif current_puzzle["type"] in ["switch_chain", "mosaic"]:
		var prog = puzzle_state.get("progress", 0)
		var total = current_puzzle.get("n", 4) if current_puzzle["type"] == "switch_chain" else 4
		state_text += "Progress: %d/%d" % [prog, total]
	elif current_puzzle["type"] == "plate_hold":
		var held = puzzle_state.get("held_by", "") != ""
		state_text += "Plate held by: %s" % [puzzle_state.get("held_by", "nothing") if held else "nothing"]
	elif current_puzzle["type"] == "timed_gate":
		var open = puzzle_state.get("open", false)
		var steps = puzzle_state.get("steps_left", 0)
		state_text += "Gate: %s (%d steps left)" % ["OPEN" if open else "CLOSED", steps]
	elif current_puzzle["type"] == "two_levers":
		var wrong = puzzle_state.get("wrong_pulls", 0)
		state_text += "Wrong pulls: %d" % wrong
	
	state_label.text = state_text
	_update_inventory_ui()

func _update_inventory_ui() -> void:
	# Clear inventory grid
	for child in inventory_grid.get_children():
		child.queue_free()
	
	for i in range(inventory.size()):
		var item = inventory[i]
		var btn = Button.new()
		btn.text = _Items.glyph_of(item) + " " + _Items.name_of(item)
		btn.tooltip_text = _Items.describe(item)
		btn.custom_minimum_size = Vector2(0, 50)
		_VT.style_secondary_button(btn)
		btn.add_theme_font_size_override("font_size", 14)
		btn.pressed.connect(_on_inventory_item_pressed.bind(i))
		inventory_grid.add_child(btn)
		
		if i == selected_inventory_index:
			btn.add_theme_stylebox_override("normal", _make_selection_style())

func _make_selection_style() -> StyleBoxFlat:
	var s = StyleBoxFlat.new()
	s.bg_color = Color(0.4, 0.3, 0.6)
	s.set_corner_radius_all(8)
	s.border_color = Color(0.9, 0.7, 0.3)
	s.set_border_width_all(2)
	s.content_margin_left = 12
	s.content_margin_right = 12
	s.content_margin_top = 8
	s.content_margin_bottom = 8
	return s

func _on_inventory_item_pressed(index: int) -> void:
	selected_inventory_index = index
	_update_inventory_ui()

func _setup_input() -> void:
	pass  # Input handling will be done in _unhandled_input

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_W, KEY_UP:
				_try_move(Vector2i(0, -1))
			KEY_S, KEY_DOWN:
				_try_move(Vector2i(0, 1))
			KEY_A, KEY_LEFT:
				_try_move(Vector2i(-1, 0))
			KEY_D, KEY_RIGHT:
				_try_move(Vector2i(1, 0))
			KEY_SPACE, KEY_ENTER:
				_interact_at_player()
			KEY_I:
				inventory_panel.visible = not inventory_panel.visible
			KEY_ESCAPE:
				get_tree().change_scene_to_file("res://client/scenes/puzzle_test_menu.tscn")
	
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		# Click to move/interact
		var local_pos = grid_container.to_local(event.global_position)
		var target = Vector2i(int(local_pos.x / cell_size), int(local_pos.y / cell_size))
		_try_pathfind_to(target)

func _try_move(dir: Vector2i) -> void:
	var new_pos = player_grid_pos + dir
	
	# Check bounds
	if new_pos.x < 1 or new_pos.x >= grid_size.x - 1 or new_pos.y < 1 or new_pos.y >= grid_size.y - 1:
		return
	
	# Check for entity collision
	for ent_data in entities.values():
		if ent_data.pos == new_pos and ent_data.type != "pickup":
			# Try to interact instead
			_interact_with_entity(ent_data)
			return
	
	player_grid_pos = new_pos
	_animate_player_move()
	_check_pickups()
	
	# Timed gate step tick
	if current_puzzle["type"] == "timed_gate" and puzzle_state.get("open", false):
		_tick_timed_gate()

func _animate_player_move() -> void:
	var target_pos = Vector2(player_grid_pos.x * cell_size + cell_size / 2, player_grid_pos.y * cell_size + cell_size / 2)
	var tween = create_tween()
	tween.set_parallel(true)
	tween.tween_property(player, "position", target_pos, 0.15).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)

func _try_pathfind_to(target: Vector2i) -> void:
	# Simple pathfinding - just try direct move for now
	var dx = target.x - player_grid_pos.x
	var dy = target.y - player_grid_pos.y
	
	if abs(dx) > abs(dy):
		_try_move(Vector2i(sign(dx), 0))
	else:
		_try_move(Vector2i(0, sign(dy)))

func sign(v: int) -> int:
	return 1 if v > 0 else (-1 if v < 0 else 0)

func _check_pickups() -> void:
	for ent_id in entities.keys():
		var ent = entities[ent_id]
		if ent.type == "pickup" and ent.pos == player_grid_pos:
			# Pick up item
			var grant = ent.grant
			if grant.has("item"):
				var item = str(grant["item"])
				if item not in inventory and inventory.size() < 8:
					inventory.append(item)
					ent.node.queue_free()
					entities.erase(ent_id)
					_update_hud()

func _interact_at_player() -> void:
	# Check for entity at player position or adjacent
	for ent_data in entities.values():
		var dist = (ent_data.pos - player_grid_pos).length()
		if dist <= 1.5:
			_interact_with_entity(ent_data)
			return

func _interact_with_entity(ent: Dictionary) -> void:
	if is_solved:
		return
	# Pickups are collected by walking onto them, not by interacting.
	if not ent.has("puzzle_action"):
		return
	var action = (ent["puzzle_action"] as Dictionary).duplicate()
	var ctx = {"items": inventory, "spells": [0, 1, 6]}  # All three starter spells
	
	# Handle inventory selection for place actions
	if action.get("kind") == "place" and not action.has("item"):
		if selected_inventory_index >= 0 and selected_inventory_index < inventory.size():
			action["item"] = inventory[selected_inventory_index]
		else:
			# Show inventory panel
			inventory_panel.visible = true
			return
	
	var r = _PuzzleLogic.act(current_puzzle, puzzle_state, action, ctx)
	
	# Apply results
	for item in r.consume:
		inventory.erase(item)
	
	if str(r.grant) != "":
		if str(r.grant) not in inventory and inventory.size() < 8:
			inventory.append(str(r.grant))
	
	if str(r.spawn_enemy) != "":
		state_label.text = "State: ENEMY SPAWNED - %s" % r.spawn_enemy
		state_label.add_theme_color_override("font_color", Color(1, 0.3, 0.3))
	
	if str(r.text) != "":
		puzzle_desc.text = str(r.text)
	
	if r.solved_now:
		is_solved = true
		state_label.text = "State: SOLVED ✓"
		state_label.add_theme_color_override("font_color", Color(0.6, 1, 0.6))
		puzzle_desc.text = str(r.text) + "\n\nPuzzle solved! Press Esc to return to menu."
	
	_update_entity_visuals()
	_update_hud()

func _tick_timed_gate() -> void:
	var r = _PuzzleLogic.act(current_puzzle, puzzle_state, {"kind": "step"}, {})
	if r.reset:
		state_label.text = "State: Gate dropped!"
		state_label.add_theme_color_override("font_color", Color(1, 0.3, 0.3))
		puzzle_desc.text = str(r.text)
		_update_entity_visuals()
	_update_hud()

func _center_camera() -> void:
	# Center camera on grid
	var camera_pos = Vector2(grid_size.x * cell_size / 2, grid_size.y * cell_size / 2)
	get_viewport().canvas_transform = Transform2D(0, camera_pos)