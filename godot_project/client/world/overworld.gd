extends Node2D
class_name Overworld

## Tile-based top-down exploration. Reads DmbWorldData, renders 16px tiles at
## TILE_SCALE, moves John one tile at a time, and hands battles to the
## `Adventure` autoload via `request_battle`. Story events live in
## `client/world/story_events.gd`.

const _World = preload("res://client/world/world_data.gd")
const _Dialogue = preload("res://client/world/dialogue_box.gd")
const _TouchPad = preload("res://client/world/touch_pad.gd")
const _Story = preload("res://client/world/story_events.gd")
const _VT = preload("res://client/scripts/visual_theme.gd")
const _SaveData = preload("res://client/scripts/save_data.gd")

const TILE := 16
const TILE_SCALE := 4
const TPX := TILE * TILE_SCALE           # tile size in screen px (64)
const STEP_SECONDS := 0.16
const PIXEL_ROOT := "res://assets/pixel/"

const SOLID_TILES := ["T", "#", "R", "f", "~", "r", " ", "X", "t"]

signal dialogue_started
signal dialogue_finished

var area_id: String = ""
var area: Dictionary = {}
var grid_w: int = 0
var grid_h: int = 0

var _tiles_root: Node2D
var _props_root: Node2D
var _actors_root: Node2D
var _fx_root: Node2D
var _camera: Camera2D
var _ui: Control
var _dialogue
var _touch
var _hud: Control
var _hud_spells: HBoxContainer
var _hud_weave_lbl: Label
var _hud_area_lbl: Label
var _prompt_lbl: Label
var _menu_btn: Button
var _magic_btn: Button
var _fader: ColorRect

var _john: Sprite2D
var _john_pos: Vector2i = Vector2i(6, 8)
var _john_facing: String = "down"
var _moving: bool = false
var _move_from: Vector2 = Vector2.ZERO
var _move_to: Vector2 = Vector2.ZERO
var _move_t: float = 0.0
var _anim_frame: int = 0
var _anim_time: float = 0.0
var _steps_taken: int = 0
var _input_locked: bool = false
var _held_dir: Vector2i = Vector2i.ZERO

var _entities: Array = []          # live entity dicts with "node" refs
var _entity_at: Dictionary = {}    # Vector2i -> entity
var _fire_frames: Array = []
var _fire_time: float = 0.0
var _story
var _tex_cache: Dictionary = {}
var _cutscene_actors: Dictionary = {}
var _scripted_running: bool = false
var test_mode: bool = false  # suppress scene changes (test harness drives scenes)


func _adv() -> Node:
	return get_node("/root/Adventure")


func _sfx() -> Node:
	return get_node_or_null("/root/Sfx")


# ---------------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------------

func _ready() -> void:
	_build_layers()
	_build_ui()
	_story = _Story.new()
	_story.setup(self)
	var adv := _adv()
	if not adv.is_active():
		adv.new_game()
	var pos: Array = adv.state["pos"]
	load_area(str(adv.state["area"]), Vector2i(int(pos[0]), int(pos[1])), str(adv.state.get("facing", "down")))
	adv.state_changed.connect(_refresh_hud)
	_refresh_hud()
	_fade_in()
	call_deferred("_after_ready")


func _after_ready() -> void:
	# Returning from a battle?
	var adv := _adv()
	if not adv.last_battle_result.is_empty():
		var r: Dictionary = adv.last_battle_result
		adv.last_battle_result = {}
		await _story.on_battle_result(r)
	elif not adv.flag("opening_seen"):
		adv.set_flag("opening_seen")
		await _story.opening_text()
	_maybe_autosave()


func _build_layers() -> void:
	_tiles_root = Node2D.new()
	_tiles_root.name = "Tiles"
	add_child(_tiles_root)
	_props_root = Node2D.new()
	_props_root.name = "Props"
	_props_root.y_sort_enabled = true
	add_child(_props_root)
	_actors_root = Node2D.new()
	_actors_root.name = "Actors"
	_actors_root.y_sort_enabled = true
	add_child(_actors_root)
	_fx_root = Node2D.new()
	_fx_root.name = "Fx"
	add_child(_fx_root)
	_camera = Camera2D.new()
	_camera.name = "Camera"
	_camera.position_smoothing_enabled = true
	_camera.position_smoothing_speed = 8.0
	add_child(_camera)
	_camera.make_current()
	_john = Sprite2D.new()
	_john.name = "John"
	_john.centered = false
	_john.scale = Vector2(TILE_SCALE, TILE_SCALE)
	_john.z_index = 10
	_actors_root.add_child(_john)


func _build_ui() -> void:
	var layer := CanvasLayer.new()
	layer.name = "UI"
	layer.layer = 10
	add_child(layer)
	var ui_root := Control.new()
	ui_root.name = "UIRoot"
	ui_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(ui_root)
	_ui = ui_root
	# HUD strip (top)
	_hud = PanelContainer.new()
	_hud.set_anchors_preset(Control.PRESET_TOP_WIDE)
	_hud.offset_left = 12
	_hud.offset_right = -12
	_hud.offset_top = 10
	_hud.add_theme_stylebox_override("panel", _VT.flat_panel_style(Color(0.08, 0.06, 0.14, 0.82), 12))
	_hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ui.add_child(_hud)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 12)
	_hud.add_child(h)
	_menu_btn = Button.new()
	_menu_btn.text = "≡"
	_menu_btn.custom_minimum_size = Vector2(52, 52)
	_VT.style_secondary_button(_menu_btn)
	_menu_btn.add_theme_font_size_override("font_size", 26)
	_menu_btn.pressed.connect(_on_menu)
	h.add_child(_menu_btn)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_theme_constant_override("separation", 2)
	h.add_child(v)
	_hud_area_lbl = Label.new()
	_VT.apply_label_secondary(_hud_area_lbl)
	_hud_area_lbl.add_theme_font_size_override("font_size", 20)
	v.add_child(_hud_area_lbl)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	v.add_child(row)
	_hud_spells = HBoxContainer.new()
	_hud_spells.add_theme_constant_override("separation", 4)
	row.add_child(_hud_spells)
	_hud_weave_lbl = Label.new()
	_VT.apply_label_caption(_hud_weave_lbl)
	_hud_weave_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.add_child(_hud_weave_lbl)
	_magic_btn = Button.new()
	_magic_btn.text = "Magic"
	_magic_btn.custom_minimum_size = Vector2(0, 52)
	_VT.style_secondary_button(_magic_btn)
	_magic_btn.add_theme_font_size_override("font_size", 18)
	_magic_btn.pressed.connect(_show_magic_sheet)
	h.add_child(_magic_btn)
	# Interaction prompt (above the touch pad)
	_prompt_lbl = Label.new()
	_prompt_lbl.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_prompt_lbl.offset_top = -330
	_prompt_lbl.offset_bottom = -290
	_prompt_lbl.offset_left = -220
	_prompt_lbl.offset_right = 220
	_prompt_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(_prompt_lbl)
	_prompt_lbl.add_theme_color_override("font_color", _VT.COLOR_ACCENT_GOLD)
	_prompt_lbl.add_theme_color_override("font_outline_color", Color.BLACK)
	_prompt_lbl.add_theme_constant_override("outline_size", 6)
	_prompt_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ui.add_child(_prompt_lbl)
	# Touch controls
	_touch = _TouchPad.new()
	_ui.add_child(_touch)
	_touch.direction_changed.connect(func(d): _held_dir = d)
	_touch.action_pressed.connect(_on_action)
	# Dialogue
	_dialogue = _Dialogue.new()
	_ui.add_child(_dialogue)
	_dialogue.opened.connect(func(): _input_locked = true; _touch.set_enabled(false); dialogue_started.emit())
	_dialogue.closed.connect(func():
		if not _scripted_running:
			_input_locked = false
			_touch.set_enabled(true)
		dialogue_finished.emit()
	)
	# Fader
	_fader = ColorRect.new()
	_fader.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_fader.color = Color.BLACK
	_fader.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ui.add_child(_fader)


# ---------------------------------------------------------------------------------
# Area loading
# ---------------------------------------------------------------------------------

func load_area(id: String, at: Vector2i, facing: String = "down") -> void:
	area_id = id
	area = _World.get_area(id)
	var rows: Array = area["rows"]
	grid_h = rows.size()
	grid_w = str(rows[0]).length()
	for c in _tiles_root.get_children():
		c.queue_free()
	for c in _props_root.get_children():
		c.queue_free()
	for c in _actors_root.get_children():
		if c != _john:
			c.queue_free()
	_entities.clear()
	_entity_at.clear()
	_fire_frames.clear()
	_cutscene_actors.clear()
	_build_tiles()
	_build_entities()
	_john_pos = at
	_john_facing = facing
	_john.position = Vector2(_john_pos) * TPX + Vector2(0, -8 * TILE_SCALE)
	_moving = false
	_update_john_sprite()
	_camera.position = _john.position + Vector2(TPX * 0.5, TPX * 0.5)
	_camera.reset_smoothing()
	_camera.limit_left = 0
	_camera.limit_top = 0
	_camera.limit_right = grid_w * TPX
	_camera.limit_bottom = grid_h * TPX
	_hud_area_lbl.text = str(area["name"])
	_adv().set_location(area_id, _john_pos.x, _john_pos.y, _john_facing)
	_update_prompt()


func _tile_char(x: int, y: int) -> String:
	if x < 0 or y < 0 or y >= grid_h or x >= grid_w:
		return " "
	return str(area["rows"][y])[x]


func _build_tiles() -> void:
	var tile_tex := {
		".": "tiles/grass.png", ",": "tiles/grass_dark.png", ":": "tiles/path.png", "~": "tiles/water.png",
		"=": "tiles/bridge.png", "#": "tiles/wall.png", "R": "tiles/roof.png", "D": "tiles/door.png",
		"f": "tiles/fence.png", "a": "tiles/ash.png", "T": "tiles/grass_dark.png", "t": "tiles/ash.png",
		"r": "tiles/grass.png", "L": "tiles/grass.png", "X": "tiles/ash.png",
	}
	for y in range(grid_h):
		for x in range(grid_w):
			var ch := _tile_char(x, y)
			if ch == " ":
				continue
			var s := Sprite2D.new()
			s.centered = false
			s.scale = Vector2(TILE_SCALE, TILE_SCALE)
			s.position = Vector2(x, y) * TPX
			s.texture = _tex(tile_tex.get(ch, "tiles/grass.png"))
			_tiles_root.add_child(s)
			if ch == "T":
				_add_prop(x, y, "props/tree_%d.png" % ((x * 7 + y * 13) % 4), Vector2(0, -16), 2)
			elif ch == "t":
				_add_prop(x, y, "props/tree_burnt_%d.png" % ((x + y) % 2), Vector2(0, -16), 2)
			elif ch == "r":
				_add_prop(x, y, "props/rock.png", Vector2.ZERO, 1)
			elif ch == "L":
				_add_prop(x, y, "props/logs.png", Vector2.ZERO, 1)


func _add_prop(x: int, y: int, path: String, offset_px: Vector2, _size_tiles: int) -> Sprite2D:
	var s := Sprite2D.new()
	s.centered = false
	s.scale = Vector2(TILE_SCALE, TILE_SCALE)
	s.position = Vector2(x, y) * TPX + offset_px * TILE_SCALE
	s.texture = _tex(path)
	s.z_index = 1
	_props_root.add_child(s)
	return s


func _tex(rel: String) -> Texture2D:
	if _tex_cache.has(rel):
		return _tex_cache[rel]
	var t := load(PIXEL_ROOT + rel)
	_tex_cache[rel] = t
	return t


func _entity_visible(e: Dictionary) -> bool:
	var adv := _adv()
	if e.has("requires_flag") and not adv.flag(str(e["requires_flag"])):
		return false
	if e.has("requires_spell") and not adv.progression.knows(int(e["requires_spell"])):
		return false
	if e.has("requires_defeated") and not adv.marked("defeated", str(e["requires_defeated"])):
		return false
	match e["kind"]:
		"fire":
			return not adv.marked("extinguished", str(e["id"]))
		"pickup":
			return not adv.marked("picked", str(e["id"]))
		"creature":
			return not adv.marked("defeated", str(e["id"]))
		"wizard":
			return true
	return true


func _build_entities() -> void:
	for raw in area["entities"]:
		var e: Dictionary = raw.duplicate(true)
		if e["kind"] in ["trigger", "exit"]:
			_entities.append(e)
			continue
		if not _entity_visible(e):
			continue
		_spawn_entity(e)


func _spawn_entity(e: Dictionary) -> void:
	var pos := Vector2i(int(e["pos"][0]), int(e["pos"][1]))
	var node: Sprite2D = null
	match e["kind"]:
		"fire":
			node = _add_prop(pos.x, pos.y, "props/fire_0.png", Vector2.ZERO, 1)
			node.z_index = 3
			_fire_frames.append(node)
		"burnt":
			node = _add_prop(pos.x, pos.y, "props/tree_burnt_0.png", Vector2(0, -16), 2)
		"pickup":
			node = _add_prop(pos.x, pos.y, "props/%s.png" % str(e["sprite"]), Vector2.ZERO, 1)
			node.z_index = 3
			_bob(node)
		"creature":
			var enemy := DmbBestiary.get_data(str(e["enemy_id"]))
			node = _add_actor(pos, "creatures/%s_world_0.png" % str(enemy["archetype"]), Vector2.ZERO)
			node.set_meta("frames", ["creatures/%s_world_0.png" % str(enemy["archetype"]), "creatures/%s_world_1.png" % str(enemy["archetype"])])
			_fire_frames.append(node)
		"wizard", "npc", "corpse":
			var spr := str(e.get("sprite", "villager_a"))
			var facing := str(e.get("facing", "down"))
			if e["kind"] == "wizard" and not _wizard_present(e):
				_entities.append(e)
				return
			node = _add_actor(pos, "chars/%s_%s_0.png" % [spr, facing], Vector2(0, -8))
			if e["kind"] == "corpse":
				# Lying body: rotate about the sprite centre so it stays on its tile.
				node.centered = true
				node.position = Vector2(pos) * TPX + Vector2(16, 8)
				node.rotation_degrees = 90
				node.z_index = 2
		"sign", "door", "logs":
			pass  # drawn by the tile map; interaction only
	e["node"] = node
	_entities.append(e)
	if e["kind"] in ["fire", "pickup", "creature", "wizard", "npc", "corpse", "sign", "door", "logs"]:
		_entity_at[pos] = e


func _wizard_present(e: Dictionary) -> bool:
	var adv := _adv()
	if adv.marked("defeated", str(e["id"])):
		return false
	return true


func _add_actor(pos: Vector2i, path: String, offset_px: Vector2) -> Sprite2D:
	var s := Sprite2D.new()
	s.centered = false
	s.scale = Vector2(TILE_SCALE, TILE_SCALE)
	s.position = Vector2(pos) * TPX + offset_px * TILE_SCALE
	s.texture = _tex(path)
	s.z_index = 5
	_actors_root.add_child(s)
	return s


func _bob(node: Node2D) -> void:
	var tw := node.create_tween().set_loops()
	tw.tween_property(node, "position:y", node.position.y - 6, 0.6).set_trans(Tween.TRANS_SINE)
	tw.tween_property(node, "position:y", node.position.y, 0.6).set_trans(Tween.TRANS_SINE)


# ---------------------------------------------------------------------------------
# Movement
# ---------------------------------------------------------------------------------

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode in [KEY_SPACE, KEY_ENTER, KEY_Z, KEY_E]:
			_on_action()
		elif event.keycode == KEY_ESCAPE:
			_on_menu()


func _process(delta: float) -> void:
	_fire_time += delta
	if _fire_time > 0.18:
		_fire_time = 0.0
		_anim_frame = (_anim_frame + 1) % 2
		for f in _fire_frames:
			if not is_instance_valid(f):
				continue
			if f.has_meta("frames"):
				f.texture = _tex(f.get_meta("frames")[_anim_frame])
			else:
				f.texture = _tex("props/fire_%d.png" % ((_anim_frame + int(f.position.x) / TPX) % 3))
	if _moving:
		_move_t += delta / STEP_SECONDS
		_anim_time += delta
		if _move_t >= 1.0:
			_moving = false
			_john.position = _move_to
			_arrived()
		else:
			_john.position = _move_from.lerp(_move_to, _move_t)
		_update_john_sprite(int(_anim_time * 8) % 2)
	elif not _input_locked:
		var dir := _keyboard_dir()
		if dir == Vector2i.ZERO:
			dir = _held_dir
		if dir != Vector2i.ZERO:
			_try_step(dir)
		else:
			_update_john_sprite(0)
	_camera.position = _john.position + Vector2(TPX * 0.5, TPX * 0.5)


func _keyboard_dir() -> Vector2i:
	if Input.is_key_pressed(KEY_LEFT) or Input.is_key_pressed(KEY_A):
		return Vector2i(-1, 0)
	if Input.is_key_pressed(KEY_RIGHT) or Input.is_key_pressed(KEY_D):
		return Vector2i(1, 0)
	if Input.is_key_pressed(KEY_UP) or Input.is_key_pressed(KEY_W):
		return Vector2i(0, -1)
	if Input.is_key_pressed(KEY_DOWN) or Input.is_key_pressed(KEY_S):
		return Vector2i(0, 1)
	return Vector2i.ZERO


static func _dir_name(d: Vector2i) -> String:
	if d.x < 0:
		return "left"
	if d.x > 0:
		return "right"
	if d.y < 0:
		return "up"
	return "down"


func is_walkable(p: Vector2i) -> bool:
	var ch := _tile_char(p.x, p.y)
	if ch in SOLID_TILES:
		return false
	if _entity_at.has(p):
		var e: Dictionary = _entity_at[p]
		if e["kind"] in ["fire", "creature", "wizard", "npc", "corpse", "pickup"]:
			return false
	return true


func _try_step(dir: Vector2i) -> void:
	_john_facing = _dir_name(dir)
	var target := _john_pos + dir
	if not is_walkable(target):
		_update_john_sprite(0)
		_update_prompt()
		return
	_moving = true
	_move_t = 0.0
	_move_from = _john.position
	_john_pos = target
	_move_to = Vector2(_john_pos) * TPX + Vector2(0, -8 * TILE_SCALE)
	_steps_taken += 1


func _arrived() -> void:
	_adv().set_location(area_id, _john_pos.x, _john_pos.y, _john_facing)
	_update_prompt()
	for e in _entities:
		match e["kind"]:
			"exit":
				if Vector2i(int(e["pos"][0]), int(e["pos"][1])) == _john_pos:
					_travel(str(e["to_area"]), Vector2i(int(e["to_pos"][0]), int(e["to_pos"][1])), str(e.get("facing", "down")))
					return
			"trigger":
				if _in_trigger(e) and not _adv().flag(str(e.get("once_flag", ""))) and _steps_taken >= int(e.get("requires_steps", 0)):
					if not bool(e.get("no_auto_flag", false)):
						_adv().set_flag(str(e["once_flag"]))
					_story.run_event(str(e["event"]))
					return


func _in_trigger(e: Dictionary) -> bool:
	if e.has("rect"):
		var r: Array = e["rect"]
		return _john_pos.x >= int(r[0]) and _john_pos.y >= int(r[1]) and _john_pos.x <= int(r[2]) and _john_pos.y <= int(r[3])
	return Vector2i(int(e["pos"][0]), int(e["pos"][1])) == _john_pos


func _travel(to_area: String, to_pos: Vector2i, facing: String) -> void:
	_input_locked = true
	_touch.set_enabled(false)
	var tw := create_tween()
	tw.tween_property(_fader, "modulate:a", 1.0, 0.25)
	await tw.finished
	load_area(to_area, to_pos, facing)
	_adv().save()
	_fade_in()
	_input_locked = false
	_touch.set_enabled(true)


func _fade_in() -> void:
	_fader.modulate.a = 1.0
	var tw := create_tween()
	tw.tween_property(_fader, "modulate:a", 0.0, 0.35)


func _update_john_sprite(frame: int = 0) -> void:
	var key := "john_staff" if _adv().progression.has_magic() else "john"
	_john.texture = _tex("chars/%s_%s_%d.png" % [key, _john_facing, frame])


func facing_pos() -> Vector2i:
	match _john_facing:
		"left":
			return _john_pos + Vector2i(-1, 0)
		"right":
			return _john_pos + Vector2i(1, 0)
		"up":
			return _john_pos + Vector2i(0, -1)
	return _john_pos + Vector2i(0, 1)


# ---------------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------------

func _facing_entity() -> Dictionary:
	var p := facing_pos()
	if _entity_at.has(p):
		return _entity_at[p]
	# forgiving range: also accept the tile John stands on (pickups) and one further
	if _entity_at.has(_john_pos):
		return _entity_at[_john_pos]
	return {}


func _update_prompt() -> void:
	var e := _facing_entity()
	var text := ""
	if e.is_empty():
		var ch := _tile_char(facing_pos().x, facing_pos().y)
		if ch == "D":
			text = "Door"
	else:
		match e["kind"]:
			"fire":
				text = "Douse the fire" if _adv().progression.knows(_World.SPELL_BLUE) else "Fire — too hot to pass"
			"pickup":
				text = "Take"
			"creature":
				text = "Face the %s" % DmbBestiary.get_data(str(e["enemy_id"]))["display_name"]
			"wizard":
				text = "Challenge %s" % DmbBestiary.get_data(str(e["enemy_id"]))["display_name"]
			"npc":
				text = "Talk to %s" % str(e.get("name", ""))
			"corpse", "sign", "door", "logs":
				text = "Look"
	_prompt_lbl.text = text
	_touch.set_action_label("✦" if text != "" else "")


func _on_action() -> void:
	if _input_locked or _moving:
		return
	var e := _facing_entity()
	if e.is_empty():
		var fp := facing_pos()
		if _tile_char(fp.x, fp.y) == "D":
			_dialogue.say("", "The door is shut.")
		return
	match e["kind"]:
		"sign", "door", "logs", "corpse":
			_dialogue.say("", str(e.get("text", "")))
		"fire":
			_interact_fire(e)
		"pickup":
			_interact_pickup(e)
		"npc":
			_interact_npc(e)
		"creature", "wizard":
			_interact_enemy(e)


func _interact_fire(e: Dictionary) -> void:
	var adv := _adv()
	if not adv.progression.knows(_World.SPELL_BLUE):
		_dialogue.say("", "The heat pushes you back. You are a woodcutter, not a firefighter.")
		return
	_input_locked = true
	_touch.set_enabled(false)
	var s := _sfx()
	if s:
		s.cast()
	_spawn_water_burst(Vector2i(int(e["pos"][0]), int(e["pos"][1])))
	await get_tree().create_timer(0.35).timeout
	if is_instance_valid(e.get("node")):
		var n: Node2D = e["node"]
		var tw := n.create_tween()
		tw.tween_property(n, "modulate:a", 0.0, 0.25)
		await tw.finished
		n.queue_free()
	adv.mark("extinguished", str(e["id"]))
	_entity_at.erase(Vector2i(int(e["pos"][0]), int(e["pos"][1])))
	_entities.erase(e)
	_input_locked = false
	_touch.set_enabled(true)
	_update_prompt()
	if not adv.flag("first_fire_out"):
		adv.set_flag("first_fire_out")
		_rebuild_entities()
		await _dialogue.say_async("", "The staff drinks the fire. Water answers you now.\n\nSomething in the ash behind you is moving.")
	adv.save()


func _spawn_water_burst(at: Vector2i) -> void:
	for i in range(8):
		var p := Sprite2D.new()
		p.texture = _tex("tiles/water.png")
		p.region_enabled = true
		p.region_rect = Rect2(4, 4, 3, 3)
		p.scale = Vector2(TILE_SCALE, TILE_SCALE)
		p.position = _john.position + Vector2(TPX * 0.5, TPX * 0.3)
		p.z_index = 20
		_fx_root.add_child(p)
		var target := Vector2(at) * TPX + Vector2(TPX * 0.5, TPX * 0.5) + Vector2(randf_range(-14, 14), randf_range(-14, 14))
		var tw := p.create_tween()
		tw.tween_property(p, "position", target, 0.25 + i * 0.02).set_trans(Tween.TRANS_QUAD)
		tw.tween_property(p, "modulate:a", 0.0, 0.15)
		tw.tween_callback(p.queue_free)


func _interact_pickup(e: Dictionary) -> void:
	var adv := _adv()
	var grant: Dictionary = e.get("grant", {})
	var s := _sfx()
	if s:
		s.ready_chime()
	adv.mark("picked", str(e["id"]))
	if e.has("set_flag"):
		adv.set_flag(str(e["set_flag"]))
	if is_instance_valid(e.get("node")):
		e["node"].queue_free()
	_entity_at.erase(Vector2i(int(e["pos"][0]), int(e["pos"][1])))
	_entities.erase(e)
	if grant.has("spell"):
		adv.learn_spell(int(grant["spell"]))
	if grant.has("weave"):
		adv.grow_weave(int(grant["weave"]))
	_update_john_sprite()
	_input_locked = true
	_touch.set_enabled(false)
	await _dialogue.say_async("", str(e.get("text", "")))
	if grant.has("spell") or grant.has("weave"):
		await _show_progression_card(grant)
	_input_locked = false
	_touch.set_enabled(true)
	adv.save()
	_rebuild_entities()
	_update_prompt()


func _interact_npc(e: Dictionary) -> void:
	var adv := _adv()
	var id := str(e["id"])
	var lines: Array = e.get("lines", [])
	if e.has("lines_flag"):
		for fl in e["lines_flag"].keys():
			if adv.flag(str(fl)):
				lines = e["lines_flag"][fl]
	# Elder-style grant: on a flag, first conversation grants a spell.
	var grant: Dictionary = e.get("grant_on_flag", {})
	var will_grant: bool = not grant.is_empty() and adv.flag(str(grant["flag"])) and not adv.flag(str(grant["set_flag"]))
	_input_locked = true
	_touch.set_enabled(false)
	_face_npc_toward_john(e)
	for line in lines:
		await _dialogue.say_async(str(e.get("name", "")), str(line))
	if will_grant:
		adv.learn_spell(int(grant["spell"]))
		adv.set_flag(str(grant["set_flag"]))
		var s := _sfx()
		if s:
			s.ready_chime()
		await _dialogue.say_async("", str(grant["text"]))
		await _show_progression_card({"spell": int(grant["spell"])})
	adv.bump_talk(id)
	_input_locked = false
	_touch.set_enabled(true)
	adv.save()
	_rebuild_entities()
	_update_prompt()


func _face_npc_toward_john(e: Dictionary) -> void:
	if not is_instance_valid(e.get("node")):
		return
	var d := _john_pos - Vector2i(int(e["pos"][0]), int(e["pos"][1]))
	var f := _dir_name(d)
	var spr := str(e.get("sprite", "villager_a"))
	e["node"].texture = _tex("chars/%s_%s_0.png" % [spr, f])


func _interact_enemy(e: Dictionary) -> void:
	var adv := _adv()
	var enemy := DmbBestiary.get_data(str(e["enemy_id"]))
	if e["kind"] == "wizard" and adv.marked("defeated", str(e["id"])):
		var after: Array = e.get("lines_after", [])
		for l in after:
			await _dialogue.say_async(str(enemy["display_name"]), str(l))
		return
	if e["kind"] == "wizard" and e.has("requires_flag") and not adv.flag(str(e["requires_flag"])):
		for l in e.get("lines_before", []):
			await _dialogue.say_async(str(enemy["display_name"]), str(l))
		return
	if not adv.progression.has_magic():
		_dialogue.say("", "You have an axe and no idea. Not yet.")
		return
	_input_locked = true
	_touch.set_enabled(false)
	await _dialogue.say_async("", str(e.get("intro", "")))
	var john: DmbProgression = adv.progression
	var warn := ""
	if john.weave_size < int(enemy["ward_size"]):
		warn = "Your weave holds %d. Their Ward has %d slots.\n\nYou cannot reach every slot — you cannot break this Ward. You can still fight, and learn." % [john.weave_size, int(enemy["ward_size"])]
	elif john.weave_size > int(enemy["ward_size"]):
		warn = "Your weave holds %d. Their Ward has %d slot%s.\n\nYour extra spells wrap round to the first slots — several attempts on one slot at once." % [john.weave_size, int(enemy["ward_size"]), "" if int(enemy["ward_size"]) == 1 else "s"]
	if warn != "":
		await _dialogue.say_async("", warn)
	var choice: String = await _dialogue.choose_async("Face %s?" % str(enemy["display_name"]), ["Fight", "Not yet"])
	if choice != "Fight":
		_input_locked = false
		_touch.set_enabled(true)
		return
	_start_battle(e)


func _start_battle(e: Dictionary) -> void:
	var req := {
		"enemy_id": str(e["enemy_id"]),
		"encounter_id": str(e["id"]),
		"kind": str(e["kind"]),
		"on_win_flag": str(e.get("on_win_flag", "")),
		"grant_on_win": e.get("grant_on_win", {}),
		"drops": str(e.get("drops", "")),
		"area": area_id,
		"return_pos": [_john_pos.x, _john_pos.y],
		"facing": _john_facing,
	}
	var tw := create_tween()
	tw.tween_property(_fader, "modulate:a", 1.0, 0.35)
	await tw.finished
	_adv().request_battle(req)
	if test_mode:
		return
	get_tree().change_scene_to_file("res://client/scenes/game_board.tscn")


func _rebuild_entities() -> void:
	# Re-evaluate visibility after flags changed (spawns/removes entities).
	var keep_pos := _john_pos
	var keep_face := _john_facing
	for c in _props_root.get_children():
		c.queue_free()
	for c in _actors_root.get_children():
		if c != _john:
			c.queue_free()
	_entities.clear()
	_entity_at.clear()
	_fire_frames.clear()
	# props from tiles
	for y in range(grid_h):
		for x in range(grid_w):
			var ch := _tile_char(x, y)
			if ch == "T":
				_add_prop(x, y, "props/tree_%d.png" % ((x * 7 + y * 13) % 4), Vector2(0, -16), 2)
			elif ch == "t":
				_add_prop(x, y, "props/tree_burnt_%d.png" % ((x + y) % 2), Vector2(0, -16), 2)
			elif ch == "r":
				_add_prop(x, y, "props/rock.png", Vector2.ZERO, 1)
			elif ch == "L":
				_add_prop(x, y, "props/logs.png", Vector2.ZERO, 1)
	_build_entities()
	_john_pos = keep_pos
	_john_facing = keep_face
	_update_john_sprite()
	_update_prompt()


# ---------------------------------------------------------------------------------
# Progression card, magic sheet, menu
# ---------------------------------------------------------------------------------

func _show_progression_card(grant: Dictionary) -> void:
	var adv := _adv()
	var lines: Array = []
	if grant.has("spell"):
		var id := int(grant["spell"])
		lines.append("NEW MAGIC: %s %s" % [DmbColourData.essence_symbol(id), DmbColourData.essence_name(id).to_upper()])
	if grant.has("weave"):
		lines.append("WEAVE: %d slot%s" % [int(grant["weave"]), "" if int(grant["weave"]) == 1 else "s"])
	var known: Array = []
	for s in adv.progression.spells_known:
		known.append(DmbColourData.essence_name(int(s)))
	lines.append("You know: %s\nWeave: %d" % [", ".join(PackedStringArray(known)), adv.progression.weave_size])
	await _dialogue.say_async("", "\n".join(PackedStringArray(lines)))
	_refresh_hud()


func _show_magic_sheet() -> void:
	if _input_locked:
		return
	var adv := _adv()
	var p: DmbProgression = adv.progression
	if not p.has_magic():
		_dialogue.say("Magic", "You know no magic. You know wood.")
		return
	var known: Array = []
	for s in p.spells_known:
		known.append("%s %s" % [DmbColourData.essence_symbol(int(s)), DmbColourData.essence_name(int(s))])
	_dialogue.say("Magic", "Spells known:\n%s\n\nWeave capacity: %d slot%s\n(spells you can cast at once — and the size of your own Ward)" % [
		"\n".join(PackedStringArray(known)), p.weave_size, "" if p.weave_size == 1 else "s"])


func _refresh_hud() -> void:
	for c in _hud_spells.get_children():
		c.queue_free()
	var adv := _adv()
	for s in adv.progression.spells_known:
		var t := TextureRect.new()
		t.custom_minimum_size = Vector2(30, 30)
		t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		t.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		t.texture = load("res://assets/icons/magic_%s.png" % DmbArt.ESSENCE_SLUGS[int(s)])
		_hud_spells.add_child(t)
	if adv.progression.has_magic():
		_hud_weave_lbl.text = "weave %d" % adv.progression.weave_size
	else:
		_hud_weave_lbl.text = "woodcutter"


func _on_menu() -> void:
	if _input_locked:
		return
	_input_locked = true
	_touch.set_enabled(false)
	_adv().save()
	var choice: String = await _dialogue.choose_async("Paused — progress saved.", ["Continue", "How to play", "Main menu"])
	match choice:
		"How to play":
			await _dialogue.say_async("How to play", "Move with the pad (or arrow keys). Tap ✦ (or Space) to talk, take, douse fires and face creatures.\n\nBattles: pick spells for each weave slot, then CAST when the ring is ready. Break their Ward before they break yours.")
			_input_locked = false
			_touch.set_enabled(true)
		"Main menu":
			get_tree().change_scene_to_file("res://client/scenes/main_menu.tscn")
		_:
			_input_locked = false
			_touch.set_enabled(true)


func _maybe_autosave() -> void:
	_adv().save()


# ---------------------------------------------------------------------------------
# Cutscene helpers (used by story_events.gd)
# ---------------------------------------------------------------------------------

func lock_input(on: bool) -> void:
	_scripted_running = on
	_input_locked = on
	_touch.set_enabled(not on)
	_held_dir = Vector2i.ZERO


func say(speaker: String, text: String) -> void:
	await _dialogue.say_async(speaker, text)


func spawn_actor(key: String, sprite: String, pos: Vector2i, facing: String = "down") -> Sprite2D:
	var n := _add_actor(pos, "chars/%s_%s_0.png" % [sprite, facing], Vector2(0, -8))
	n.set_meta("sprite", sprite)
	n.set_meta("facing", facing)
	_cutscene_actors[key] = n
	return n


func actor(key: String) -> Sprite2D:
	return _cutscene_actors.get(key)


func move_actor(key: String, to: Vector2i, seconds: float) -> void:
	var n: Sprite2D = actor(key)
	if n == null:
		return
	var dest := Vector2(to) * TPX + Vector2(0, -8 * TILE_SCALE)
	var d := dest - n.position
	var f := _dir_name(Vector2i(signi(int(d.x)), signi(int(d.y))) if absf(d.x) > absf(d.y) else Vector2i(0, signi(int(d.y))))
	n.texture = _tex("chars/%s_%s_0.png" % [n.get_meta("sprite"), f])
	var tw := n.create_tween()
	tw.tween_property(n, "position", dest, seconds)
	await tw.finished


func face_actor(key: String, facing: String) -> void:
	var n: Sprite2D = actor(key)
	if n:
		n.texture = _tex("chars/%s_%s_0.png" % [n.get_meta("sprite"), facing])


func remove_actor(key: String) -> void:
	var n = _cutscene_actors.get(key)
	if n and is_instance_valid(n):
		n.queue_free()
	_cutscene_actors.erase(key)


func face_john(facing: String) -> void:
	_john_facing = facing
	_update_john_sprite()


func flash(color: Color, seconds: float = 0.12) -> void:
	_fader.color = color
	_fader.modulate.a = 0.85
	var tw := create_tween()
	tw.tween_property(_fader, "modulate:a", 0.0, seconds)
	await tw.finished
	_fader.color = Color.BLACK


func shake(strength: float = 6.0, seconds: float = 0.4) -> void:
	var t := 0.0
	while t < seconds:
		_camera.offset = Vector2(randf_range(-strength, strength), randf_range(-strength, strength))
		await get_tree().process_frame
		t += get_process_delta_time()
	_camera.offset = Vector2.ZERO


func bolt(from: Vector2i, to: Vector2i, color: Color, seconds: float = 0.35) -> void:
	var p := Sprite2D.new()
	p.texture = _tex("props/fire_0.png")
	p.modulate = color
	p.scale = Vector2(TILE_SCALE * 0.6, TILE_SCALE * 0.6)
	p.centered = true
	p.position = Vector2(from) * TPX + Vector2(TPX * 0.5, TPX * 0.3)
	p.z_index = 30
	_fx_root.add_child(p)
	var tw := p.create_tween()
	tw.tween_property(p, "position", Vector2(to) * TPX + Vector2(TPX * 0.5, TPX * 0.4), seconds).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_callback(p.queue_free)
	await tw.finished


func wait(seconds: float) -> void:
	await get_tree().create_timer(seconds).timeout


func rebuild() -> void:
	_rebuild_entities()


func john_pos() -> Vector2i:
	return _john_pos


func set_john_pos(p: Vector2i, facing: String = "") -> void:
	_john_pos = p
	if facing != "":
		_john_facing = facing
	_john.position = Vector2(_john_pos) * TPX + Vector2(0, -8 * TILE_SCALE)
	_moving = false
	_update_john_sprite()
	_adv().set_location(area_id, _john_pos.x, _john_pos.y, _john_facing)


# --- test API -----------------------------------------------------------------------

func ui_step(dir: Vector2i) -> void:
	if not _moving and not _input_locked:
		_try_step(dir)


func ui_is_moving() -> bool:
	return _moving


func ui_action() -> void:
	_on_action()


func ui_dialogue_open() -> bool:
	return _dialogue.is_open()


func ui_dialogue_advance() -> void:
	_dialogue.advance()


func ui_dialogue_choose(label: String) -> void:
	_dialogue.pick(label)


func ui_dialogue_waiting_choice() -> bool:
	return _dialogue.is_waiting_choice()


func ui_prompt() -> String:
	return _prompt_lbl.text


func ui_input_locked() -> bool:
	return _input_locked


func ui_entity_exists(id: String) -> bool:
	for e in _entities:
		if str(e.get("id", "")) == id and e.get("node") != null and is_instance_valid(e["node"]):
			return true
	return false


func ui_tile_walkable(p: Vector2i) -> bool:
	return is_walkable(p)
