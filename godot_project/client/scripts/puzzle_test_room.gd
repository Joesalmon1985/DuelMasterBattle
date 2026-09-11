extends Node2D
## Isolated driver for one DmbPuzzleRooms catalogue room (pz_01..pz_50).
## Thin renderer over DmbPuzzleKit: the kit owns ALL simulation; this file only
## draws tiles/entity states as placeholder rects, moves the player through
## Kit.blocks/on_step, forwards interactions via Kit.actions_for/act, and pumps
## Kit.tick for hazards/teleporters. No puzzle logic lives here.

const Kit = preload("res://sim/world/puzzle_kit.gd")
const Rooms = preload("res://sim/world/puzzle_rooms.gd")
const Items = preload("res://sim/world/items.gd")
const Runner = preload("res://client/scripts/puzzle_test_runner.gd")

const TILE := 44.0
const GRID_ORIGIN := Vector2(24, 300)

@onready var grid_node = $GridContainer
@onready var player_node = $GridContainer/Player
@onready var player_sprite = $GridContainer/Player/PlayerSprite
@onready var title_label = $UILayer/HUD/PuzzleTitle
@onready var desc_label = $UILayer/HUD/PuzzleDesc
@onready var state_label = $UILayer/HUD/StateLabel
@onready var hint_label = $UILayer/HUD/ControlHint
@onready var inv_panel = $UILayer/InventoryPanel
@onready var inv_label = $UILayer/InventoryPanel/InventoryLabel
@onready var inv_grid = $UILayer/InventoryPanel/InventoryGrid

var room_id := "pz_01"
var room: Dictionary = {}
var st: Dictionary = {}
var inventory: Array = []
var extra_spells: Array = []
var tile_nodes: Array = []
var ent_nodes: Dictionary = {}
var last_dir := Vector2i(0, 1)
var action_index := 0
var last_target_id := ""
var messages: Array = []
var is_solved := false

func _ready() -> void:
	var sel = Runner.get_puzzle()
	if sel is String and str(sel) != "":
		room_id = str(sel)
	elif sel is Dictionary and str(sel.get("id", "")) != "":
		room_id = str(sel["id"])
	room = Rooms.get_room(room_id)
	if room.is_empty():
		room_id = "pz_01"
		room = Rooms.get_room(room_id)
	_reset_room()
	title_label.text = "%s — %s" % [room_id, str(room.get("title", ""))]
	desc_label.text = "%s\n%s" % [str(room.get("mechanics", "")), str(room.get("hint", ""))]
	hint_label.text = "Move WASD/Arrows · Space interact · Tab cycle choice · T throw · D drop · I bag · R reset · Esc menu"
	_ensure_player_body()
	_add_touch_controls()
	_build_tiles()
	_redraw()
	_say("Find the way through. Read plaques (?), pull levers, carry things to niches.")
	_refresh_text()

func _reset_room() -> void:
	st = Kit.fresh_state(room)
	inventory = (room.get("items", []) as Array).duplicate()
	extra_spells = []
	Kit.sync_inventory(st, inventory)
	action_index = 0
	last_target_id = ""
	messages = []
	is_solved = false
	inv_panel.visible = false

func _ctx() -> Dictionary:
	var spells: Array = (room.get("spells", []) as Array).duplicate()
	for s in extra_spells:
		if not spells.has(s):
			spells.append(s)
	return {"items": inventory, "spells": spells}

# --- rendering ---

func _tile_color(ch: String) -> Color:
	match ch:
		"#":
			return Color(0.16, 0.14, 0.22)
		"~", "^":
			return Color(0.35, 0.16, 0.12)
		_:
			return Color(0.23, 0.21, 0.32)

func _build_tiles() -> void:
	for n in tile_nodes:
		n.queue_free()
	tile_nodes.clear()
	var rows: Array = room["rows"]
	for y in range(rows.size()):
		var line: String = rows[y]
		for x in range(line.length()):
			var r := ColorRect.new()
			r.color = _tile_color(line[x])
			r.position = GRID_ORIGIN + Vector2(x, y) * TILE
			r.size = Vector2(TILE - 1, TILE - 1)
			grid_node.add_child(r)
			tile_nodes.append(r)

func _entity_draw_pos(e: Dictionary) -> Vector2i:
	var id := str(e.get("id", ""))
	match str(e.get("kind", "")):
		"npc":
			if st["npcs"].has(id):
				return Kit._pos(st["npcs"][id]["pos"])
		"critter":
			if st["critters"].has(id):
				return Kit._pos(st["critters"][id]["pos"])
		"hazard":
			if st["hazards"].has(id):
				return Kit.hazard_pos(e, st)
	if e.has("pos"):
		return Kit._pos(e["pos"])
	return Vector2i(-1, -1)

func _redraw() -> void:
	for k in ent_nodes:
		ent_nodes[k].queue_free()
	ent_nodes.clear()
	var vmap: Dictionary = Kit.visual_map(room, st)
	# Static entities carry state/color/label in vmap but their tile lives on
	# the room entity (only hazards/npcs/critters/world-items/beams get pos in
	# vmap), so merge: pos from the room entity, looks from vmap.
	var by_id := {}
	for e in room["entities"]:
		if e is Dictionary and str(e.get("id", "")) != "":
			by_id[str(e["id"])] = e
	for vid in vmap:
		var v: Dictionary = vmap[vid]
		if not bool(v.get("visible", true)):
			continue
		var p := Vector2i(-1, -1)
		if v.has("pos"):
			p = Kit._pos(v["pos"])
		elif by_id.has(vid) and (by_id[vid] as Dictionary).has("pos"):
			p = Kit._pos((by_id[vid] as Dictionary)["pos"])
		if p.x < 0 or p.y < 0:
			continue
		var col: Color = v.get("color", Color.MAGENTA)
		col.a = float(v.get("alpha", 1.0))
		var r := ColorRect.new()
		r.color = col
		var shape := str(v.get("shape", "block"))
		if shape == "pad":
			r.position = GRID_ORIGIN + Vector2(p) * TILE + Vector2(4, TILE - 16)
			r.size = Vector2(TILE - 8, 12)
		elif shape == "beam":
			r.position = GRID_ORIGIN + Vector2(p) * TILE + Vector2(8, 8)
			r.size = Vector2(TILE - 16, TILE - 16)
		else:
			r.position = GRID_ORIGIN + Vector2(p) * TILE + Vector2(5, 5)
			r.size = Vector2(TILE - 10, TILE - 10)
		var lab: Label = Label.new()
		lab.text = str(v.get("label", ""))
		lab.add_theme_font_size_override("font_size", 20)
		lab.add_theme_color_override("font_color", Color.WHITE)
		lab.set_anchors_preset(Control.PRESET_FULL_RECT)
		lab.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lab.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		lab.mouse_filter = Control.MOUSE_FILTER_IGNORE
		r.add_child(lab)
		r.tooltip_text = "%s (%s)" % [vid, str(v.get("state", ""))]
		grid_node.add_child(r)
		ent_nodes[vid] = r
	var pp := Kit._pos(st["player"])
	player_node.position = GRID_ORIGIN + Vector2(pp) * TILE + Vector2(TILE, TILE) * 0.5
	_refresh_inventory()

func _say(t: String) -> void:
	messages.append(t)
	while messages.size() > 4:
		messages.pop_front()

func _refresh_text() -> void:
	var lines: Array = []
	if is_solved:
		lines.append("SOLVED — Esc for menu, R to replay.")
	lines.append_array(messages)
	state_label.text = "\n".join(lines)

func _refresh_inventory() -> void:
	for c in inv_grid.get_children():
		c.queue_free()
	for it in inventory:
		var l := Label.new()
		l.text = Items.name_of(str(it))
		l.add_theme_font_size_override("font_size", 18)
		inv_grid.add_child(l)

# --- player body + touch controls (human-playable, mobile-friendly) ---

func _ensure_player_body() -> void:
	# The scene's Sprite2D ships with no texture, so the player is invisible.
	# Add a plain green body + "P" tag once; harmless if a texture is set later.
	if player_sprite.texture != null:
		return
	if player_node.has_node("Body"):
		return
	var body := ColorRect.new()
	body.name = "Body"
	body.color = Color(0.35, 1.0, 0.45)
	body.size = Vector2(30, 30)
	body.position = Vector2(-15, -15)
	player_node.add_child(body)
	var lab := Label.new()
	lab.text = "P"
	lab.add_theme_font_size_override("font_size", 20)
	lab.add_theme_color_override("font_color", Color(0.05, 0.15, 0.08))
	lab.set_anchors_preset(Control.PRESET_FULL_RECT)
	lab.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lab.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	lab.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(lab)

func _touch_btn(label: String, dir: Vector2i, is_use: bool, parent: Control, pos: Vector2) -> void:
	var b := Button.new()
	b.text = label
	b.custom_minimum_size = Vector2(72, 72)
	b.position = pos
	b.focus_mode = Control.FOCUS_NONE
	b.add_theme_font_size_override("font_size", 28)
	if is_use:
		b.pressed.connect(_interact)
	else:
		b.pressed.connect(func() -> void: _try_move(dir))
	parent.add_child(b)

func _add_touch_controls() -> void:
	# On-screen D-pad (bottom-left) + USE button (bottom-right). Buttons work
	# with mouse clicks too, and tap-to-move already works via click.
	var ui := $UILayer
	var pad := Control.new()
	pad.name = "TouchPad"
	pad.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	pad.position = Vector2(16, -260)
	pad.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(pad)
	_touch_btn("▲", Vector2i(0, -1), false, pad, Vector2(76, 0))
	_touch_btn("◀", Vector2i(-1, 0), false, pad, Vector2(0, 76))
	_touch_btn("▼", Vector2i(0, 1), false, pad, Vector2(76, 76))
	_touch_btn("▶", Vector2i(1, 0), false, pad, Vector2(152, 76))
	var use := Control.new()
	use.name = "TouchUse"
	use.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	use.position = Vector2(-104, -260)
	use.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(use)
	_touch_btn("E", Vector2i.ZERO, true, use, Vector2(0, 0))
	hint_label.text = "Move WASD/Arrows/D-pad/tap · Space/E interact · Tab cycle · T throw · D drop · I bag · R reset · Esc menu"

# --- simulation plumbing ---

func _apply_result(r: Dictionary) -> void:
	for t in r.get("text", []):
		_say(str(t))
	for c in r.get("grant", []):
		inventory.append(str(c))
	for c in r.get("consume", []):
		inventory.erase(str(c))
	Kit.sync_inventory(st, inventory)
	if int(r.get("learn", -1)) >= 0:
		var sp := int(r["learn"])
		if not extra_spells.has(sp):
			extra_spells.append(sp)
		_say("Learned %s (added to casts)." % Kit.spell_name(sp))
	if str(r.get("battle", "")) != "":
		_say("A fight with %s would start here (out of test scope)." % str(r["battle"]))
	if bool(r.get("solved_now", false)) or Kit.is_solved(st):
		if not is_solved:
			is_solved = true
			_say("Solved!")
	_refresh_text()

func _try_move(d: Vector2i) -> void:
	if is_solved:
		return
	last_dir = d
	var pp := Kit._pos(st["player"])
	var target := pp + d
	if Kit.blocks(room, st, target):
		_say("Blocked.")
		_refresh_text()
		return
	var r: Dictionary = Kit.on_step(room, st, target, _ctx())
	_apply_result(r)
	_redraw()

func _target_entity() -> Dictionary:
	var pp := Kit._pos(st["player"])
	var e: Dictionary = Kit.entity_at(room, st, pp)
	if e.is_empty():
		e = Kit.entity_at(room, st, pp + last_dir)
	return e

func _interact() -> void:
	if is_solved:
		return
	var e := _target_entity()
	if e.is_empty():
		_say("Nothing to use here.")
		_refresh_text()
		return
	var eid := str(e.get("id", e.get("kind", "")))
	if eid != last_target_id:
		last_target_id = eid
		action_index = 0
	var acts: Array = Kit.actions_for(room, st, e, _ctx())
	if acts.is_empty():
		_say("Nothing to do with that right now.")
		_refresh_text()
		return
	action_index = action_index % acts.size()
	var names: Array = []
	for a in acts:
		names.append(str(a["label"]))
	_say("“%s”: %s" % [str(e.get("id", e.get("kind", ""))), " / ".join(names)])
	var r: Dictionary = Kit.act(room, st, e, acts[action_index]["action"], _ctx())
	_apply_result(r)
	_redraw()

func _cycle_action() -> void:
	action_index += 1
	var e := _target_entity()
	if e.is_empty():
		return
	var acts: Array = Kit.actions_for(room, st, e, _ctx())
	if acts.is_empty():
		return
	action_index = action_index % acts.size()
	_say("Chosen: %s" % str(acts[action_index]["label"]))
	_refresh_text()

func _throw_first() -> void:
	if inventory.is_empty():
		_say("Bag is empty.")
		_refresh_text()
		return
	var r: Dictionary = Kit.throw(room, st, str(inventory[0]), last_dir, _ctx())
	_apply_result(r)
	_redraw()

func _drop_first() -> void:
	if inventory.is_empty():
		return
	var r: Dictionary = Kit.drop(room, st, str(inventory[0]), _ctx())
	_apply_result(r)
	_redraw()

func _process(delta: float) -> void:
	if room.is_empty() or st.is_empty():
		return
	var r: Dictionary = Kit.tick(room, st, delta)
	if bool(r.get("changed", false)):
		_apply_result(r)
		_redraw()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_W, KEY_UP:
				_try_move(Vector2i(0, -1))
			KEY_S, KEY_DOWN:
				_try_move(Vector2i(0, 1))
			KEY_A, KEY_LEFT:
				_try_move(Vector2i(-1, 0))
			KEY_D, KEY_RIGHT:
				_try_move(Vector2i(1, 0))
			KEY_SPACE, KEY_E:
				_interact()
			KEY_TAB:
				_cycle_action()
			KEY_T:
				_throw_first()
			KEY_G:
				_drop_first()
			KEY_I:
				inv_panel.visible = not inv_panel.visible
			KEY_R:
				_reset_room()
				_redraw()
				_say("Room reset.")
				_refresh_text()
			KEY_ESCAPE:
				get_tree().change_scene_to_file("res://client/scenes/puzzle_test_menu.tscn")
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var local: Vector2 = grid_node.get_global_mouse_position() - GRID_ORIGIN
		var cell := Vector2i(int(floor(local.x / TILE)), int(floor(local.y / TILE)))
		var pp := Kit._pos(st["player"])
		var d := cell - pp
		if absi(d.x) + absi(d.y) == 1:
			_try_move(d)
		elif d == Vector2i.ZERO:
			_interact()
