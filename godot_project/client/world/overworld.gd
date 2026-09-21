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
var _world_flow := WorldFlow.new()
var _play := WorldPlay.new()
const _SaveData = preload("res://client/scripts/save_data.gd")
const _Runner = preload("res://client/scripts/puzzle_test_runner.gd")
const _VRunner = preload("res://client/scripts/village_test_runner.gd")
const _ActorVisual = preload("res://client/world/actor_visual.gd")
const _VQuest = preload("res://sim/world/village_quest_runner.gd")
const _SemanticLabel = preload("res://client/world/world_interaction_label.gd")
const _Resolver = preload("res://sim/world/world_interaction_resolver.gd")
const _Adapter = preload("res://sim/world/semantic_adapter.gd")

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
var _items_btn: Button
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
var _bridge_runtime = null  # G05 shell host when Python-backed
var _mouse_steer_held := false
var _pointer_on_entity := false

var _entities: Array = []          # live entity dicts with "node" refs
var _entity_at: Dictionary = {}    # Vector2i -> entity
var _semantic_labels: Array = []
var _semantic_root: Control
var _semantic_layer: CanvasLayer
var _semantic_focus_layer: CanvasLayer
var _semantic_focus_root: Control
var _semantic_syncing := false
var _move_dismiss_armed := true
var _test_key_dir := Vector2i.ZERO
var _semantic_focus := ""
var _semantic_press_frame := -1
var _present_label = null
var _present_cancelled := false
var _fire_frames: Array = []
var _fire_time: float = 0.0
var _story
var _tex_cache: Dictionary = {}
var _cutscene_actors: Dictionary = {}
var _scripted_running: bool = false
var test_mode: bool = false  # suppress scene changes (test harness drives scenes)
var _kit_tick_acc: float = 0.0  # deterministic quantum accumulator for kit ticks


func _adv() -> Node:
	return get_node("/root/Adventure")


func _sfx() -> Node:
	return get_node_or_null("/root/Sfx")


func set_bridge_runtime(host) -> void:
	## G05 shell: clock/SyncPose/WorkerController owner.
	_bridge_runtime = host


func bridge_runtime():
	return _bridge_runtime


# ---------------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------------

func _ready() -> void:
	_build_layers()
	_build_ui()
	_story = _Story.new()
	_story.setup(self)
	var adv := _adv()
	if _Runner.has_pending() or _Runner.is_active():
		_boot_kit_session(adv)
		return
	if _VRunner.has_pending():
		_boot_village_test(adv)
		return
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
	# Fixture E17A must not play or consume campaign story (Trial Day, pending
	# battle aftermath). last_battle_result stays put so exit still has it.
	if _VRunner.isolates_campaign_story():
		_maybe_autosave()
		return
	if not adv.last_battle_result.is_empty():
		var r: Dictionary = adv.last_battle_result
		adv.last_battle_result = {}
		if _Runner.is_active():
			await _after_kit_battle(r)
			return
		var req: Dictionary = r.get("request", {})
		if str(r.get("outcome", "")) == "victory" and req.has("world_hex") and WorldFlow.is_world_area(area_id):
			_world_flow.setup(adv)
			_world_flow.on_victory(req)
			area = _world_flow.area_for(area_id)
		await _story.on_battle_result(r)
		if adv.state.has("pending_quest") and WorldFlow.is_world_area(area_id):
			_world_flow.setup(adv)
			_play.setup(self, adv, _world_flow)
			await _play.after_battle(str(r.get("outcome", "")))
	elif not adv.flag("opening_seen") and not _Runner.is_active():
		adv.set_flag("opening_seen")
		await _story.prologue_open()
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
	var semantic_layer := CanvasLayer.new()
	semantic_layer.name = "SemanticLabels"
	semantic_layer.layer = 8
	add_child(semantic_layer)
	_semantic_layer = semantic_layer
	_semantic_root = Control.new()
	_semantic_root.name = "SemanticRoot"
	_semantic_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_semantic_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	semantic_layer.add_child(_semantic_root)
	# Active conversation sits above the HUD and D-pad so neither can cover or
	# intercept speech and response clicks. Passive labels stay on layer 8.
	_semantic_focus_layer = CanvasLayer.new()
	_semantic_focus_layer.name = "SemanticFocus"
	_semantic_focus_layer.layer = 12
	add_child(_semantic_focus_layer)
	_semantic_focus_root = Control.new()
	_semantic_focus_root.name = "SemanticFocusRoot"
	_semantic_focus_root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_semantic_focus_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_semantic_focus_layer.add_child(_semantic_focus_root)
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
	_items_btn = Button.new()
	_items_btn.text = "Pockets"
	_items_btn.custom_minimum_size = Vector2(0, 52)
	_VT.style_secondary_button(_items_btn)
	_items_btn.add_theme_font_size_override("font_size", 18)
	_items_btn.pressed.connect(_show_inventory)
	_items_btn.visible = false
	h.add_child(_items_btn)
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
	_prompt_lbl.visible = false
	_ui.add_child(_prompt_lbl)
	# Touch controls
	_touch = _TouchPad.new()
	_ui.add_child(_touch)
	_touch.direction_changed.connect(func(d): _held_dir = d)
	_touch.action_pressed.connect(_on_action)
	_touch.set_action_visible(false)
	# Dialogue — optional spellbook surface for real village conversations.
	if OS.get_environment("DMB_SPELLBOOK_DIALOGUE") == "1":
		_dialogue = load("res://client/ui/spellbook/spellbook_dialogue_presenter.gd").new()
	else:
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
	if _Runner.is_active() and id == _Runner.room_id():
		_load_kit_area(at, facing)
		return
	if WorldFlow.is_world_area(id):
		_world_flow.setup(_adv())
		_play.setup(self, _adv(), _world_flow)
		area = _world_flow.enter(id)
		area_id = str(area["id"])
	elif DmbDungeonMap.is_dungeon_area(id):
		_world_flow.setup(_adv())
		_play.setup(self, _adv(), _world_flow)
		area = _play.dungeon_area(id)
		area_id = id
	else:
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


func _is_dungeon() -> bool:
	return str(area.get("id", "")).begins_with("dd_") or DmbDungeonMap.is_dungeon_area(str(area.get("id", ""))) or str(area.get("theme", "")) == "dungeon"


func _build_tiles() -> void:
	var tile_tex := {
		".": "tiles/grass.png", ",": "tiles/grass_dark.png", ":": "tiles/path.png", "~": "tiles/water.png",
		"=": "tiles/bridge.png", "#": "tiles/wall.png", "R": "tiles/roof.png", "D": "tiles/door.png",
		"f": "tiles/fence.png", "a": "tiles/ash.png", "T": "tiles/grass_dark.png", "t": "tiles/ash.png",
		"r": "tiles/grass.png", "L": "tiles/grass.png", "X": "tiles/ash.png",
	}
	var dungeon := _is_dungeon()
	if dungeon:
		tile_tex["."] = "tiles/cave_floor.png"
		tile_tex[":"] = "tiles/cave_floor.png"
		tile_tex["T"] = "tiles/cave_wall.png"
		tile_tex["r"] = "tiles/cave_floor.png"
		tile_tex["#"] = "tiles/cave_wall.png"  # catalogue puzzle walls read as dungeon walls
		tile_tex["L"] = "tiles/cave_floor.png"
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
			_add_tile_prop(x, y, ch, dungeon)


## Decorative prop implied by a map character (trees, rocks, logs).
func _add_tile_prop(x: int, y: int, ch: String, dungeon: bool) -> void:
	if ch == "T":
		if not dungeon:
			_add_prop(x, y, "props/tree_%d.png" % ((x * 7 + y * 13) % 4), Vector2(0, -16), 2)
	elif ch == "t":
		_add_prop(x, y, "props/tree_burnt_%d.png" % ((x + y) % 2), Vector2(0, -16), 2)
	elif ch == "r":
		_add_prop(x, y, "props/stalagmite.png" if dungeon else "props/rock.png", Vector2.ZERO, 1)
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
	if e.has("puzzle_room"):
		return true  # kit projection is already state-derived; no campaign filtering
	var adv := _adv()
	if e.has("requires_flag") and not adv.flag(str(e["requires_flag"])):
		return false
	if e.has("requires_run_flag") and not adv.run_flag(str(e["requires_run_flag"])):
		return false
	if e.has("blocked_by_run_flag") and adv.run_flag(str(e["blocked_by_run_flag"])):
		return false
	if e.has("requires_spell") and not adv.progression.knows(int(e["requires_spell"])):
		return false
	if e.has("requires_defeated") and not adv.marked("defeated", str(e["requires_defeated"])):
		return false
	if e.has("requires_dungeon_solved") and not _play.dungeon_solved(str(e["requires_dungeon_solved"])):
		return false
	if e.has("grant") and e["grant"].has("item") and adv.has_item(str(e["grant"]["item"])):
		return false
	match e["kind"]:
		"fire":
			return not adv.marked("extinguished", str(e["id"]))
		"pickup":
			if bool(e.get("run_pickup", false)):
				return not adv.run_flag("picked_" + str(e["id"]))
			return not adv.marked("picked", str(e["id"]))
		"creature":
			return not adv.marked("defeated", str(e["id"]))
		"wizard":
			return true
	return true


func _build_entities() -> void:
	_clear_semantic_labels()
	for raw in area["entities"]:
		var e: Dictionary = raw.duplicate(true)
		if e["kind"] in ["trigger", "exit"]:
			_entities.append(e)
			_maybe_label_exit(e)
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
			node = _add_actor(pos, "chars/%s_%s_0.png" % [spr, facing], Vector2(0, -8), spr, facing, str(e.get("name", spr)))
			if e["kind"] == "corpse":
				# Lying body: rotate about the sprite centre so it stays on its tile.
				node.centered = true
				node.position = Vector2(pos) * TPX + Vector2(16, 8)
				node.rotation_degrees = 90
				node.z_index = 2
		"sign", "door", "logs":
			# Visible marker so interactables read as objects, not empty floor.
			# Village/forest doors and log piles are already drawn by the tile map.
			var marker := ""
			var marker_off := Vector2.ZERO
			if e.has("marker"):
				marker = "props/%s.png" % str(e["marker"])
				marker_off = Vector2(0, -16)  # 32x32 tall props stand a tile up
			elif e["kind"] == "sign":
				marker = "props/sign.png"
			elif _is_dungeon() and not e.has("marker"):
						marker = "props/door_dungeon.png" if e["kind"] == "door" else "props/box.png"
			if marker != "":
				node = _add_prop(pos.x, pos.y, marker, marker_off, 1)
				node.z_index = 2
		"hazard":
			# Geometric HazardActor mounted by WorldLayerPresenters; still register for Challenge.
			e["node"] = null
			_entities.append(e)
			_entity_at[pos] = e
			_ensure_semantic(e, null)
			return
		"cart", "soldier", "construction":
			# Geometric presenters own the Node2D; register for inspect/focus.
			e["node"] = null
			_entities.append(e)
			_entity_at[pos] = e
			_ensure_semantic(e, null)
			return
		"deco", "nature":
				# Dense natural-world props: register for walk-through only.
				# Geometric WorldLayerPresenters owns the visible Node2D.
				e["node"] = null
				_entities.append(e)
				_ensure_semantic(e, null)
				return
	e["node"] = node
	_entities.append(e)
	if e["kind"] in ["fire", "pickup", "creature", "wizard", "npc", "corpse", "sign", "door", "logs"]:
		_entity_at[pos] = e
	if node != null and e.get("semantic") is Dictionary:
		_attach_semantic_label(e, node)
	_ensure_semantic(e, node)


func _wizard_present(e: Dictionary) -> bool:
	var adv := _adv()
	if adv.marked("defeated", str(e["id"])):
		return false
	return true


func _add_actor(pos: Vector2i, path: String, offset_px: Vector2, sprite: String = "", facing: String = "down", label: String = "") -> Sprite2D:
	var s := Sprite2D.new()
	s.centered = false
	s.position = Vector2(pos) * TPX + offset_px * TILE_SCALE
	s.z_index = 5
	_actors_root.add_child(s)
	if sprite != "":
		_apply_char(s, sprite, facing, 0, label)
	else:
		s.scale = Vector2(TILE_SCALE, TILE_SCALE)
		s.texture = _tex(path)
	return s


## Character art goes through one path: a real sprite, or a geometric stand-in
## if that resource is missing. Tile and prop loads stay on `_tex`.
func _apply_char(node: Sprite2D, sprite: String, facing: String, frame: int, label: String) -> void:
	if node == null:
		return
	_ActorVisual.apply(node, PIXEL_ROOT, sprite, facing, frame, label)
	for e in _entities:
		if e.get("node") == node and e.get("semantic") is Dictionary:
			_hide_name_fallback(node)
			return


func _bob(node: Node2D) -> void:
	var tw := node.create_tween().set_loops()
	tw.tween_property(node, "position:y", node.position.y - 6, 0.6).set_trans(Tween.TRANS_SINE)
	tw.tween_property(node, "position:y", node.position.y, 0.6).set_trans(Tween.TRANS_SINE)


# ---------------------------------------------------------------------------------
# Movement
# ---------------------------------------------------------------------------------

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
	if not _VRunner.is_bridge_mode():
		_tick_workers(delta)
	_tick_kit(delta)
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
	elif not _input_locked or _semantic_any_expanded():
		if not _scripted_running:
			_poll_move_dismiss_arm()
			var dir := _movement_input()
			if dir != Vector2i.ZERO and not _carried_move_blocked():
				_try_step(dir)
			else:
				_update_john_sprite(0)
	_camera.position = _john.position + Vector2(TPX * 0.5, TPX * 0.5)
	_sync_semantic_stack()


func _keyboard_dir() -> Vector2i:
	if _test_key_dir != Vector2i.ZERO:
		return _test_key_dir
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
	if _play.is_kit_puzzle_area(area):
		return not _play.kit_blocks(p)  # kit: true = blocked; walkable = NOT blocked
	if _entity_at.has(p):
		var e: Dictionary = _entity_at[p]
		if e["kind"] in ["fire", "creature", "wizard", "npc", "corpse", "pickup", "sign", "door", "logs"]:
			return false
	return true


func _try_step(dir: Vector2i) -> void:
	if _carried_move_blocked():
		return
	_john_facing = _dir_name(dir)
	var target := _john_pos + dir
	if not is_walkable(target):
		_update_john_sprite(0)
		_update_prompt()
		return
	_dismiss_semantic_on_move()
	_moving = true
	_move_t = 0.0
	_move_from = _john.position
	_john_pos = target
	_move_to = Vector2(_john_pos) * TPX + Vector2(0, -8 * TILE_SCALE)
	_steps_taken += 1
	if DmbDungeonMap.is_dungeon_area(area_id):
		_play.on_step(area)


func _arrived() -> void:
	if _play.is_kit_puzzle_area(area):
		_arrived_kit()
		return
	_adv().set_location(area_id, _john_pos.x, _john_pos.y, _john_facing)
	if _VRunner.is_bridge_mode() and _bridge_runtime != null and _bridge_runtime.has_method("notify_local_step"):
		_bridge_runtime.notify_local_step()
	_update_prompt()
	for e in _entities:
		match e["kind"]:
			"exit":
				if Vector2i(int(e["pos"][0]), int(e["pos"][1])) == _john_pos and _entity_visible(e):
					if _VRunner.is_bridge_mode() and bool(e.get("bridge_travel", false)):
						await _bridge_travel_exit(e)
						return
					_travel(str(e["to_area"]), Vector2i(int(e["to_pos"][0]), int(e["to_pos"][1])), str(e.get("facing", "down")), str(e.get("travel_text", "")))
					return
			"trigger":
				if e.has("requires_phase") and _adv().story_phase() != str(e["requires_phase"]):
					continue
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


## A readable's text, with run-flag keyed variants ("text_run_flag": {flag: text}).
func _entity_text(e: Dictionary) -> String:
	var text := str(e.get("text", ""))
	if e.has("text_run_flag"):
		for fl in e["text_run_flag"].keys():
			if _adv().run_flag(str(fl)):
				text = str(e["text_run_flag"][fl])
	return text


func _travel(to_area: String, to_pos: Vector2i, facing: String, travel_text: String = "") -> void:
	_input_locked = true
	_touch.set_enabled(false)
	if travel_text != "":
		await _dialogue.say_async("", travel_text)
	var tw := create_tween()
	tw.tween_property(_fader, "modulate:a", 1.0, 0.25)
	await tw.finished
	var was_world := WorldFlow.is_world_area(area_id)
	load_area(to_area, to_pos, facing)
	_adv().mark_visited(to_area)
	_adv().save()
	_fade_in()
	# The world moved while you walked: say so when something visible changed.
	if was_world and WorldFlow.is_world_area(to_area):
		var news := _world_flow.notable_events_text()
		if not news.is_empty():
			await _dialogue.say_async("", "Word on the road:\n" + "\n".join(PackedStringArray(news)))
	_input_locked = false
	_touch.set_enabled(true)


func _fade_in() -> void:
	_fader.modulate.a = 1.0
	var tw := create_tween()
	tw.tween_property(_fader, "modulate:a", 0.0, 0.35)


func _update_john_sprite(frame: int = 0) -> void:
	# The controllable sprite follows the story's protagonist (Halvard in the
	# prologue, John afterwards). Halvard is always drawn as the Blue mage.
	var key := "john_staff" if _adv().progression.has_magic() else "john"
	if _adv().protagonist() == "halvard":
		key = "blue_mage"
	_apply_char(_john, key, _john_facing, frame, "John")


## Test/inspection API: which way is the player sprite drawn as facing.
func ui_player_facing() -> String:
	return _john_facing


## Test/inspection API: facing of a cutscene actor or a placed entity, read
## back from the texture actually assigned (so it catches orientation bugs
## that coordinate maths alone would not).
func ui_actor_facing(key: String) -> String:
	var n: Sprite2D = _john if key == "john" else actor(key)
	if n == null:
		for e in _entities:
			if str(e.get("id", "")) == key and is_instance_valid(e.get("node")):
				n = e["node"]
				break
	if n == null or n.texture == null:
		return ""
	var path := n.texture.resource_path
	for f in ["left", "right", "up", "down"]:
		if path.ends_with("_%s_0.png" % f) or path.ends_with("_%s_1.png" % f):
			return f
	return ""


## Two characters confronting one another: the one on the left faces right and
## vice versa. Works for cutscene actors ("red") and the player ("john").
func face_each_other(a: String, b: String) -> void:
	var pa := _actor_or_player_pos(a)
	var pb := _actor_or_player_pos(b)
	var a_face := "right" if pa.x < pb.x else ("left" if pa.x > pb.x else ("down" if pa.y < pb.y else "up"))
	var b_face := _opposite(a_face)
	_set_facing(a, a_face)
	_set_facing(b, b_face)


func _actor_or_player_pos(key: String) -> Vector2i:
	if key == "john":
		return _john_pos
	var n: Sprite2D = actor(key)
	if n != null:
		return Vector2i(roundi(n.position.x / TPX), roundi((n.position.y + 8 * TILE_SCALE) / TPX))
	for e in _entities:
		if str(e.get("id", "")) == key:
			return Vector2i(int(e["pos"][0]), int(e["pos"][1]))
	return _john_pos


func _set_facing(key: String, facing: String) -> void:
	if key == "john":
		face_john(facing)
		return
	if actor(key) != null:
		face_actor(key, facing)
		return
	for e in _entities:
		if str(e.get("id", "")) == key and is_instance_valid(e.get("node")):
			_apply_char(e["node"], str(e.get("sprite", "villager_a")), facing, 0, str(e.get("name", "")))
			e["facing"] = facing


func _opposite(f: String) -> String:
	match f:
		"left": return "right"
		"right": return "left"
		"up": return "down"
	return "up"


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
	elif e.has("puzzle_room"):
		text = str(e.get("prompt", "Examine"))
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
				if e.has("puzzle_action"):
					text = "Examine"
				elif e.has("dungeon_id"):
					text = "Enter"
	_prompt_lbl.text = text
	_touch.set_action_label("✦" if text != "" else "")


func _on_action() -> void:
	if _input_locked or _moving:
		return
	if Engine.get_process_frames() == _semantic_press_frame:
		return
	var e := _facing_entity()
	if e.is_empty():
		var fp := facing_pos()
		if _tile_char(fp.x, fp.y) == "D":
			_dialogue.say("", "The door is shut.")
		return
	if _semantic_key(e) != "":
		_on_semantic_interact(_semantic_key(e))
		return
	await _perform_entity_action(e)


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
	if _VRunner.is_bridge_mode() and bool(e.get("bridge_pickup", false)):
		await _interact_bridge_pickup(e)
		return
	var adv := _adv()
	var grant: Dictionary = e.get("grant", {})
	if e.has("dungeon_reward"):
		_input_locked = true
		_touch.set_enabled(false)
		await _play.take_reward(e)
		_input_locked = false
		_touch.set_enabled(true)
		_update_prompt()
		return
	if grant.has("item"):
		_input_locked = true
		_touch.set_enabled(false)
		if str(e.get("text", "")) != "":
			await _dialogue.say_async("", str(e["text"]))
		var took: bool = await _play.grant_item(str(grant["item"]))
		if took:
			if e.has("set_flag"):
				adv.set_flag(str(e["set_flag"]))
			adv.save()
			_rebuild_entities()
		_input_locked = false
		_touch.set_enabled(true)
		_update_prompt()
		return
	var s := _sfx()
	if s:
		s.ready_chime()
	if bool(e.get("run_pickup", false)):
		adv.set_run_flag("picked_" + str(e["id"]))
	else:
		adv.mark("picked", str(e["id"]))
	if e.has("set_flag"):
		adv.set_flag(str(e["set_flag"]))
	if grant.has("spell"):
		adv.learn_spell(int(grant["spell"]))
	for sp in grant.get("spells", []):
		adv.learn_spell(int(sp))
	if grant.has("weave"):
		adv.grow_weave(int(grant["weave"]))
	if grant.has("item"):
		adv.add_item(str(grant["item"]))
	if grant.has("gem"):
		adv.add_gem(str(grant["gem"]))
	if grant.has("run_flag"):
		adv.set_run_flag(str(grant["run_flag"]))
	if bool(e.get("clear_conditions", false)):
		adv.clear_conditions()
	if e.has("inflict"):
		adv.add_condition(str(e["inflict"]))
	_update_john_sprite()
	_input_locked = true
	_touch.set_enabled(false)
	await _dialogue.say_async("", str(e.get("text", "")))
	if e.has("choice_event"):
		await _story.run_event(str(e["choice_event"]))
	if grant.has("spell") or grant.has("spells") or grant.has("weave"):
		await _show_progression_card(grant)
	_input_locked = false
	_touch.set_enabled(true)
	adv.save()
	_rebuild_entities()
	_update_prompt()


func _interact_npc(e: Dictionary) -> void:
	var adv := _adv()
	var id := str(e["id"])
	if _VRunner.is_bridge_mode() and bool(e.get("bridge_talk", false)):
		await _interact_bridge_npc(e)
		return
	if _VRunner.is_active() and e.has("village_test_story"):
		await _interact_village_npc(e)
		return
	if e.has("quest_node") and str(e.get("choice_event", "")) == "settlement_quest":
		_input_locked = true
		_touch.set_enabled(false)
		_face_npc_toward_john(e)
		await _play.run_quest(e)
		adv.bump_talk(id)
		_input_locked = false
		_touch.set_enabled(true)
		_update_prompt()
		return
	var lines: Array = e.get("lines", [])
	# Story-phase keyed lines win over defaults; flag-keyed lines win over those.
	if e.has("lines_phase") and e["lines_phase"].has(adv.story_phase()):
		lines = e["lines_phase"][adv.story_phase()]
	if e.has("lines_flag"):
		for fl in e["lines_flag"].keys():
			if adv.flag(str(fl)):
				lines = e["lines_flag"][fl]
	if e.has("lines_run_flag"):
		for fl in e["lines_run_flag"].keys():
			if adv.run_flag(str(fl)):
				lines = e["lines_run_flag"][fl]
	# Elder-style grant: on a flag, first conversation grants a spell.
	var grant: Dictionary = e.get("grant_on_flag", {})
	var will_grant: bool = not grant.is_empty() and adv.flag(str(grant["flag"])) and not adv.flag(str(grant["set_flag"]))
	_input_locked = true
	_touch.set_enabled(false)
	_face_npc_toward_john(e)
	for line in lines:
		await _dialogue.say_async(str(e.get("name", "")), str(line))
		if _present_cancelled:
			_input_locked = false
			_touch.set_enabled(true)
			return
	if e.has("choice_event"):
		await _story.run_event(str(e["choice_event"]))
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
	_apply_char(e["node"], str(e.get("sprite", "villager_a")), f, 0, str(e.get("name", "")))


func _interact_enemy(e: Dictionary) -> void:
	if _VRunner.is_bridge_mode() and bool(e.get("bridge_challenge", false)):
		await _interact_bridge_challenge(e)
		return
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
	# Brief §26: declining is not a defeat. "Walk away" is the neutral label.
	var choice: String = await _dialogue.choose_async("Face %s?" % str(enemy["display_name"]), ["Fight", "Walk away"])
	if choice != "Fight":
		_input_locked = false
		_touch.set_enabled(true)
		return
	_start_battle(e)


## P5: exploration knowledge that weakens a specific enemy's Ward.
## Exploration knowledge/items that weaken a specific enemy's Ward. Data lives
## in WARD_BANS: enemy_id → [run_flag, banned spell]. Brief §28 "clues which
## actually alter enemy Ward possibilities".
const WARD_BANS := {
	"bloodbeast": [["blood_weakness", 6]],                          # the prisoner's warning: no Vine
	"manticore": [["has_elf_charm", 6], ["riddle_right", 4]],     # elf's charm: no Vine; old man: no Light
}


func _ward_ban_for(enemy_id: String) -> Array:
	var out: Array = []
	for rule in WARD_BANS.get(enemy_id, []):
		if _adv().run_flag(str(rule[0])):
			out.append(int(rule[1]))
	return out


## P5: story events start scripted battles through here (no entity needed).
## Story events start battles through here with an entity-shaped dict
## ({"id", "enemy_id", "kind", "training", "grant_on_defeat", ...}) so they get
## the same encounter numbering and policy plumbing as map creatures.
func start_battle_request(req: Dictionary) -> void:
	if req.has("enemy_id") and req.has("id"):
		await _start_battle(req)
		return
	var tw := create_tween()
	tw.tween_property(_fader, "modulate:a", 1.0, 0.35)
	await tw.finished
	_adv().request_battle(req)
	if test_mode:
		return
	get_tree().change_scene_to_file("res://client/scenes/game_board.tscn")


func _start_battle(e: Dictionary) -> void:
	var adv := _adv()
	var n: int = adv.begin_encounter(str(e["id"]))
	var req := {
		"enemy_id": str(e["enemy_id"]),
		"encounter_id": str(e["id"]),
		"encounter_index": n,
		"optimal": adv.is_optimal_encounter(str(e["id"])),
		"kind": str(e["kind"]),
		"training": bool(e.get("training", false)),
		"on_win_flag": str(e.get("on_win_flag", "")),
		"on_win_run_flag": str(e.get("on_win_run_flag", "")),
		"on_defeat_flag": str(e.get("on_defeat_flag", "")),
		"grant_on_win": e.get("grant_on_win", {}),
		"grant_on_defeat": e.get("grant_on_defeat", {}),
		"enemy_overrides": e.get("enemy_overrides", {}),
		"drops": str(e.get("drops", "")),
		"area": area_id,
		"return_pos": [_john_pos.x, _john_pos.y],
		"facing": _john_facing,
		"player_mods": adv.player_mods(),
		"ward_ban": _ward_ban_for(str(e["enemy_id"])),
	}
	if e.has("policy"):
		req["policy"] = str(e["policy"])
	if e.has("player_combatant"):
		req["player_combatant"] = e["player_combatant"]
	if e.has("forced_defeat_by_cast"):
		req["forced_defeat_by_cast"] = int(e["forced_defeat_by_cast"])
	if e.has("intro"):
		req["intro"] = str(e["intro"])
	if e.has("world_hex"):
		req["world_hex"] = int(e["world_hex"])
	if bool(req["optimal"]):
		# Every-third-battle rule: the sharp tier. Hard, not perfect — capped
		# minimax with a mid-size sample (see CORRECTIVE_PASS_PLAN Phase 4).
		var ov: Dictionary = req["enemy_overrides"].duplicate()
		ov["bot_logic"] = "capped_minimax"
		ov["bot_solver_cap"] = maxi(int(ov.get("bot_solver_cap", 0)), 100)
		ov["bot_mistake_rate"] = 0.0
		req["enemy_overrides"] = ov
	var tw := create_tween()
	tw.tween_property(_fader, "modulate:a", 1.0, 0.35)
	await tw.finished
	adv.request_battle(req)
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
	var dungeon := _is_dungeon()
	for y in range(grid_h):
		for x in range(grid_w):
			_add_tile_prop(x, y, _tile_char(x, y), dungeon)
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
	var new_ids: Array = []
	if grant.has("spell"):
		new_ids.append(int(grant["spell"]))
	for sp in grant.get("spells", []):
		new_ids.append(int(sp))
	for id in new_ids:
		lines.append("NEW MAGIC: %s %s" % [DmbColourData.essence_symbol(id), DmbColourData.essence_name(id).to_upper()])
	if grant.has("weave"):
		lines.append("WEAVE: %d slot%s" % [int(grant["weave"]), "" if int(grant["weave"]) == 1 else "s"])
	var known: Array = []
	for s in adv.progression.spells_known:
		known.append(DmbColourData.essence_name(int(s)))
	lines.append("You know: %s\nWeave: %d" % [", ".join(PackedStringArray(known)), adv.progression.weave_size])
	await _dialogue.say_async("", "\n".join(PackedStringArray(lines)))
	_refresh_hud()


func _show_inventory() -> void:
	if _input_locked:
		return
	_input_locked = true
	_touch.set_enabled(false)
	_play.setup(self, _adv(), _world_flow)
	await _play.show_inventory()
	_input_locked = false
	_touch.set_enabled(true)


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
	if _items_btn:
		_items_btn.visible = adv.story_phase() == "post_trial_recovery" or not adv.items().is_empty()
		_items_btn.text = "Pockets %d/%d" % [adv.items().size(), DmbItems.MAX_SLOTS] if not adv.items().is_empty() else "Pockets"


func _on_menu() -> void:
	if _input_locked:
		return
	_input_locked = true
	_touch.set_enabled(false)
	if _Runner.is_active():
		await _kit_menu()
		return
	if _VRunner.is_active():
		await _village_menu()
		return
	_adv().save()
	while true:
		var choice: String = await _dialogue.choose_async("Paused — progress saved.", ["Continue", "Journal", "How to play", "Main menu"])
		match choice:
			"How to play":
				await _dialogue.say_async("How to play", "Move with the pad (or arrow keys). Tap a name in the world to look, and tap it again up close to talk, take, open, or face a creature.\n\nBattles: pick spells for each weave slot, then CAST when the ring is ready. Break their Ward before they break yours.")
			"Journal":
				await _dialogue.say_async("", _adv().notebook_text())
			"Main menu":
				get_tree().change_scene_to_file("res://client/scenes/main_menu.tscn")
				return
			_:
				_input_locked = false
				_touch.set_enabled(true)
				return


## Pause menu inside a kit session: test save writes stay suppressed; the
## campaign snapshot is restored byte-for-byte on exit.
func _kit_menu() -> void:
	while true:
		var choice: String = await _dialogue.choose_async("Paused — puzzle test (%s)." % _Runner.room_id(), ["Continue", "Reset puzzle", "Puzzle menu"])
		match choice:
			"Reset puzzle":
				_finish_kit_build(_Runner.reset(_adv()), "down")
				_input_locked = false
				_touch.set_enabled(true)
				return
			"Puzzle menu":
				await _exit_kit_to_menu()
				return
			_:
				_input_locked = false
				_touch.set_enabled(true)
				return


## Pause menu inside a village test session: test save writes stay suppressed; the
## campaign snapshot is restored byte-for-byte on exit.
func _village_menu() -> void:
	while true:
		var profile = _VRunner.profile_id()
		var choice: String = await _dialogue.choose_async("Paused — village test (%s)." % profile, ["Continue", "Reset Village", "Context", "Show Anchors", "Show Quest/Story Markers", "Show Entity IDs", "Exit Test"])
		match choice:
			"Context":
				await _dialogue.say_async("Village test", _VRunner.context_text())
				continue
			"Reset Village":
				_finish_village_build(_VRunner.reset(_adv()), _VRunner.session_facing())
				_input_locked = false
				_touch.set_enabled(true)
				return
			"Show Anchors":
				_VRunner.toggle_anchors()
				_update_debug_markers()
				continue
			"Show Quest/Story Markers":
				_VRunner.toggle_quest_story()
				_update_debug_markers()
				continue
			"Show Entity IDs":
				_VRunner.toggle_entity_ids()
				_update_debug_markers()
				continue
			"Exit Test":
				await _exit_village_test()
				return
			_:
				_input_locked = false
				_touch.set_enabled(true)
				return


func _update_debug_markers() -> void:
	# Refresh visual debug markers based on runner state
	pass


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
	var n := _add_actor(pos, "chars/%s_%s_0.png" % [sprite, facing], Vector2(0, -8), sprite, facing, key)
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
	_apply_char(n, str(n.get_meta("sprite")), f, 0, str(n.get_meta("label", "")))
	var tw := n.create_tween()
	tw.tween_property(n, "position", dest, seconds)
	await tw.finished


func face_actor(key: String, facing: String) -> void:
	var n: Sprite2D = actor(key)
	if n:
		_apply_char(n, str(n.get_meta("sprite")), facing, 0, str(n.get_meta("label", "")))


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


## Fade to black and stay there. load_area does NOT fade back in — callers that
## fade out around a load_area must call fade_in() afterwards.
func fade_out(seconds: float = 0.5) -> void:
	_fader.color = Color.BLACK
	var tw := create_tween()
	tw.tween_property(_fader, "modulate:a", 1.0, seconds)
	await tw.finished


## Bring the view back after fade_out.
func fade_in(seconds: float = 0.35) -> void:
	_fader.color = Color.BLACK
	var tw := create_tween()
	tw.tween_property(_fader, "modulate:a", 0.0, seconds)
	await tw.finished


## Test/inspection API: how dark the screen fader currently is (0 = clear).
func ui_fader_alpha() -> float:
	return _fader.modulate.a


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
	# World and dungeon areas are projections of state: re-project so changed
	# state (quest outcomes, solved rooms, moods) shows up, not just visibility.
	if WorldFlow.is_world_area(area_id):
		area = _world_flow.area_for(area_id)
		_build_tiles_only()
	elif DmbDungeonMap.is_dungeon_area(area_id):
		area = _play.dungeon_area(area_id)
		_build_tiles_only()
	_rebuild_entities()


## Ambient work loops (design doc §14): a worker NPC with a `workplace` walks
## between its post and its building and back, pausing at each end. Movement is
## tile-locked and never onto John or a solid entity, so interaction stays clean.
func _tick_workers(delta: float) -> void:
	if _input_locked or _scripted_running:
		return
	var moved := false
	for e in _entities:
		if e["kind"] != "npc" or not e.has("workplace") or not is_instance_valid(e.get("node")):
			continue
		var t: float = float(e.get("_work_t", 0.0)) + delta
		var wait: float = float(e.get("_work_wait", 1.6 + (int(e["pos"][0]) % 3) * 0.7))
		if t < wait:
			e["_work_t"] = t
			continue
		e["_work_t"] = 0.0
		e["_work_wait"] = 1.4 + randf() * 1.2
		var here := Vector2i(int(e["pos"][0]), int(e["pos"][1]))
		var post: Vector2i = e.get("_post", here)
		e["_post"] = post
		var work := Vector2i(int(e["workplace"][0]), int(e["workplace"][1]))
		var goal: Vector2i = work if not bool(e.get("_to_post", false)) else post
		# One tile toward the goal (stop adjacent to the building — it is solid).
		var d := goal - here
		var step := Vector2i(signi(d.x), 0) if abs(d.x) >= abs(d.y) else Vector2i(0, signi(d.y))
		if d.length_squared() <= 1 or step == Vector2i.ZERO:
			e["_to_post"] = not bool(e.get("_to_post", false))
			continue
		var next := here + step
		if next == _john_pos or not is_walkable(next):
			e["_to_post"] = not bool(e.get("_to_post", false))
			continue
		_entity_at.erase(here)
		e["pos"] = [next.x, next.y]
		_entity_at[next] = e
		_apply_char(e["node"], str(e.get("sprite", "villager_a")), _dir_name(step), 0, str(e.get("name", "")))
		var spr_node: Sprite2D = e["node"]
		var tw: Tween = spr_node.create_tween()
		tw.tween_property(spr_node, "position", Vector2(next) * TPX + Vector2(0, -8) * TILE_SCALE, STEP_SECONDS * 1.6)
		moved = true
	if moved:
		_update_prompt()


func _build_tiles_only() -> void:
	for c in _tiles_root.get_children():
		c.queue_free()
	_build_tiles()


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
	_update_prompt()


# --- test API -----------------------------------------------------------------------

func ui_step(dir: Vector2i) -> void:
	if _moving:
		return
	if _input_locked and not _semantic_any_expanded():
		return
	_try_step(dir)


func ui_is_moving() -> bool:
	return _moving


func ui_action() -> void:
	_on_action()


func ui_semantic_labels() -> Array:
	var out: Array = []
	for raw in _semantic_labels:
		if not is_instance_valid(raw):
			continue
		out.append({
			"key": raw.knowledge_key(),
			"text": raw.display_text(),
			"state": raw.interaction_state(),
			"entity_id": raw.entity_id(),
		})
	return out


func ui_visible_rect() -> Rect2:
	return get_viewport().get_visible_rect()


func ui_world_to_screen(world: Vector2) -> Vector2:
	if _camera == null:
		return world
	if _camera.has_method("force_update_scroll"):
		_camera.force_update_scroll()
	var view := ui_visible_rect().size
	return (world - _camera.get_screen_center_position()) * _camera.zoom + view * 0.5


func ui_entity_screen_rect(entity_id: String) -> Rect2:
	for e in _entities:
		if str(e.get("id", "")) != entity_id:
			continue
		var node = e.get("node")
		if node is Sprite2D and is_instance_valid(node):
			var tex_size := Vector2(16, 16)
			if node.texture != null:
				tex_size = node.texture.get_size()
			var world := Rect2(node.global_position, tex_size * node.scale)
			return Rect2(ui_world_to_screen(world.position), world.size * _camera.zoom)
	return Rect2()


func ui_semantic_label(key: String):
	for raw in _semantic_labels:
		if is_instance_valid(raw) and raw.knowledge_key() == key:
			return raw
	return null


func _clear_semantic_labels() -> void:
	for raw in _semantic_labels:
		if is_instance_valid(raw):
			raw.queue_free()
	_semantic_labels.clear()


func _attach_semantic_label(e: Dictionary, node: Node2D) -> void:
	if _semantic_root == null:
		return
	var lbl = _SemanticLabel.new()
	lbl.name = "Semantic_%s" % str(e.get("id", ""))
	_semantic_root.add_child(lbl)
	var semantic: Dictionary = e.get("semantic", {})
	if _VRunner.is_bridge_mode():
		lbl.bind_bridge(semantic, str(e.get("id", "")), node, _camera, Vector2(TPX * 0.5, -40))
		var label_text := str(e.get("text", ""))
		var labels = semantic.get("labels", [])
		if labels is Array and (labels as Array).size() > 0 and typeof(labels[0]) == TYPE_DICTIONARY:
			label_text = str(labels[0].get("text", label_text))
		var view := {
			"known": false,
			"name": "",
			"label": label_text,
			"description": str(semantic.get("observe_far", label_text)),
		}
		var nm := str(e.get("name", ""))
		if nm != "" and not nm.begins_with("person:") and str(e.get("kind", "")) == "npc":
			view["known"] = true
			view["name"] = nm
			view["label"] = nm
		lbl.set_bridge_view(view)
	else:
		lbl.bind(_adv(), semantic, str(e.get("id", "")), node, _camera, Vector2(TPX * 0.5, -40))
	if not lbl.activated.is_connected(_on_semantic_activated):
		lbl.activated.connect(_on_semantic_activated)
	if not lbl.interact_requested.is_connected(_on_semantic_interact):
		lbl.interact_requested.connect(_on_semantic_interact)
	if not lbl.response_chosen.is_connected(_on_semantic_response):
		lbl.response_chosen.connect(_on_semantic_response)
	if not lbl.presentation_entered.is_connected(_on_semantic_entered):
		lbl.presentation_entered.connect(_on_semantic_entered)
	if not lbl.conversation_dismissed.is_connected(_on_semantic_dismissed):
		lbl.conversation_dismissed.connect(_on_semantic_dismissed)
	if not lbl.line_done.is_connected(_on_semantic_line_done):
		lbl.line_done.connect(_on_semantic_line_done)
	_semantic_labels.append(lbl)


## Register a moving industry person as ONE shared Overworld semantic actor.
func register_dynamic_person(person_id: String, actor: Node2D, row: Dictionary) -> void:
	if not is_instance_valid(actor) or person_id == "":
		return
	unregister_dynamic_person(person_id)
	var role := str(row.get("public_role", row.get("role", "Worker")))
	if role == "" or role.begins_with("person:"):
		role = "Worker"
	var known := false
	var display := role
	# Prefer revealed personal name when knowledge already present on the row.
	var personal := str(row.get("known_name", ""))
	if personal != "" and not personal.begins_with("person:"):
		known = true
		display = personal
	var far := str(row.get("observe_far", "A worker is here."))
	var near := str(row.get("observe_near", far))
	var semantic := {
		"knowledge_key": person_id,
		"interaction": "npc",
		"dismiss_on_move": true,
		"labels": [
			{"level": 0, "text": role},
			{"level": 1, "text": display},
		],
		"observe_far": far,
		"observe_near": near,
	}
	var e := {
		"kind": "npc",
		"id": person_id,
		"pos": _actor_tile_pos(actor),
		"name": display if known else role,
		"bridge_entity": true,
		"bridge_talk": true,
		"dynamic": true,
		"node": actor,
		"semantic": semantic,
	}
	_entities.append(e)
	_attach_semantic_label(e, actor)
	_hide_name_fallback(actor)


func _actor_tile_pos(actor: Node2D) -> Array:
	if not is_instance_valid(actor):
		return [0, 0]
	var gx := int(floor(actor.position.x / float(TPX)))
	var gy := int(floor(actor.position.y / float(TPX)))
	return [gx, gy]


func sync_dynamic_person_poses() -> void:
	"""Keep semantic range in sync with moving Person actors."""
	for e in _entities:
		if not bool(e.get("dynamic", false)):
			continue
		var actor = e.get("node")
		if actor != null and is_instance_valid(actor):
			e["pos"] = _actor_tile_pos(actor)


func update_dynamic_person(person_id: String, row: Dictionary) -> void:
	var e := _entity_by_id(person_id)
	if e.is_empty():
		return
	var actor = e.get("node")
	if actor != null and is_instance_valid(actor):
		e["pos"] = _actor_tile_pos(actor)
	var role := str(row.get("public_role", row.get("occupation", row.get("role", "Worker"))))
	if role == "" or role.begins_with("person:"):
		role = "Worker"
	var far := str(row.get("observe_far", e.get("semantic", {}).get("observe_far", "")))
	var near := str(row.get("observe_near", e.get("semantic", {}).get("observe_near", far)))
	var semantic: Dictionary = e.get("semantic", {})
	semantic["observe_far"] = far
	semantic["observe_near"] = near
	if semantic.get("labels") is Array and (semantic["labels"] as Array).size() > 0:
		semantic["labels"][0]["text"] = role
	e["semantic"] = semantic
	var lbl = ui_semantic_label(person_id)
	if lbl != null:
		if lbl.has_method("update_semantic"):
			lbl.update_semantic(semantic)
		if lbl.has_method("set_bridge_view"):
			lbl.set_bridge_view({
				"known": false,
				"name": "",
				"label": role,
				"description": far,
			})


func unregister_dynamic_person(person_id: String) -> void:
	var keep: Array = []
	for e in _entities:
		if str(e.get("id", "")) == person_id and bool(e.get("dynamic", false)):
			continue
		keep.append(e)
	_entities = keep
	var lbl = ui_semantic_label(person_id)
	if lbl != null and is_instance_valid(lbl):
		_semantic_labels.erase(lbl)
		lbl.queue_free()


func _entity_by_id(entity_id: String) -> Dictionary:
	for e in _entities:
		if str(e.get("id", "")) == entity_id:
			return e
	return {}


func _dismiss_semantic_on_move() -> void:
	for raw in _semantic_labels:
		if is_instance_valid(raw):
			raw.notify_player_moved()


func _on_semantic_dismissed(key: String) -> void:
	_present_cancelled = true
	if _dialogue != null:
		_dialogue.release_redirect()
	if _semantic_focus == key:
		_update_prompt()
	_sync_semantic_stack()


func _on_semantic_line_done() -> void:
	if _dialogue != null and _dialogue.is_redirecting() and _dialogue.is_open() and not _dialogue.is_waiting_choice():
		_dialogue.advance()


func _on_semantic_activated(key: String) -> void:
	# Focus only. Speech and responses are handled by their own signals.
	_claim_semantic(key)
	_semantic_press_frame = Engine.get_process_frames()
	_sync_semantic_stack()


func _on_semantic_interact(key: String) -> void:
	_claim_semantic(key)
	var e := _entity_by_semantic_key(key)
	var lbl = ui_semantic_label(key)
	if lbl == null or e.is_empty():
		return
	var resolved: Dictionary = _Resolver.resolve(e["semantic"], _adv(), _semantic_in_range(e))
	if str(resolved.get("mode", "")) != "interact":
		lbl.open_observation()
		return
	match str(resolved.get("interaction", "")):
		"npc":
			if _VRunner.is_active() and e.has("village_test_story"):
				_start_semantic_conversation(e, lbl)
			else:
				_start_semantic_use(e, lbl)
		_:
			_start_semantic_use(e, lbl)


func _on_semantic_response(key: String, index: int) -> void:
	_claim_semantic(key)
	_semantic_press_frame = Engine.get_process_frames()
	if _dialogue != null and _dialogue.is_waiting_choice():
		var offered: Array = _dialogue.redirect_options()
		if index >= 0 and index < offered.size():
			_dialogue.pick(str(offered[index]))
		return
	if _present_label != null:
		return
	var e := _entity_by_semantic_key(key)
	var lbl = ui_semantic_label(key)
	if lbl == null or e.is_empty() or index < 0:
		return
	if str(e.get("semantic", {}).get("interaction", "")) == "enemy":
		if index == 0:
			_start_battle(e)
		else:
			lbl.collapse()
		return
	if not (_VRunner.is_active() and e.has("village_test_story")):
		return
	var result: Dictionary = _VQuest.respond_to(str(e.get("id", "")), index)
	var shown: Dictionary = _reply_from_choice(result)
	lbl.present_committed_reply(shown.get("lines", []), shown.get("options", []))
	_update_prompt()
	_sync_semantic_stack()


## Snapshot the authored reply before any acknowledgement animation. Later
## presentation must not rebuild this from quest state.
func _reply_from_choice(result: Dictionary) -> Dictionary:
	var lines: Array = _turn_texts(result.get("turns", []))
	var options: Array = []
	if bool(result.get("return_options", false)) or bool(result.get("inquiry", false)):
		options = result.get("options", [])
	elif bool(result.get("success", false)):
		lines.append_array(_semantic_followup_lines())
	elif str(result.get("error", "")) != "":
		lines = [str(result["error"])]
	return {
		"lines": lines,
		"options": options,
		"inquiry": bool(result.get("inquiry", false)),
		"success": bool(result.get("success", false)),
	}


func _on_semantic_entered(state: String) -> void:
	if state in ["OBSERVATION", "SPEECH", "RESPONSES"]:
		_move_dismiss_armed = false


func _movement_input() -> Vector2i:
	var key := _keyboard_dir()
	if key != Vector2i.ZERO:
		return key
	if _held_dir != Vector2i.ZERO:
		return _held_dir
	if _VRunner.is_bridge_mode():
		return _mouse_steer_dir()
	return Vector2i.ZERO


func _mouse_steer_dir() -> Vector2i:
	## G03 fx_clock_area parity: LMB hold on empty world steers John (grid dominant axis).
	if not Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		_mouse_steer_held = false
		return Vector2i.ZERO
	if _gui_blocks_world_pointer():
		return Vector2i.ZERO
	if _pointer_on_entity:
		return Vector2i.ZERO
	_mouse_steer_held = true
	var mouse := get_global_mouse_position()
	var john_center := _john.global_position + Vector2(TPX * 0.5, TPX * 0.5)
	var delta_v := mouse - john_center
	if delta_v.length() < 18.0:
		return Vector2i.ZERO
	if absf(delta_v.x) >= absf(delta_v.y):
		return Vector2i(1 if delta_v.x > 0 else -1, 0)
	return Vector2i(0, 1 if delta_v.y > 0 else -1)


func _gui_blocks_world_pointer() -> bool:
	var hovered = get_viewport().gui_get_hovered_control()
	if hovered == null:
		return false
	# Touch pad / dialogue / semantic focus / inventory chrome.
	var n: Control = hovered
	while n != null:
		var nm := str(n.name)
		if nm in ["TouchPad", "UIRoot", "SemanticFocus", "SemanticFocusRoot", "Dialogue", "SpellHost", "DuelHost"]:
			return true
		if n.mouse_filter == Control.MOUSE_FILTER_STOP and n is Button:
			return true
		n = n.get_parent() as Control
	return false


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		_pointer_on_entity = _entity_under_pointer(event.position) != null
	if _is_empty_pointer_press(event):
		if Engine.get_process_frames() != _semantic_press_frame:
			_semantic_focus = ""
		# Do not consume — mouse steer needs the button held in _process.
		if not (_VRunner.is_bridge_mode() and event is InputEventMouseButton):
			get_viewport().set_input_as_handled()
		return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode in [KEY_SPACE, KEY_ENTER, KEY_Z, KEY_E]:
			_on_action()
		elif event.keycode == KEY_ESCAPE:
			_on_menu()


func _entity_under_pointer(screen_pos: Vector2) -> Variant:
	var world := get_canvas_transform().affine_inverse() * screen_pos
	var cell := Vector2i(int(floor(world.x / float(TPX))), int(floor(world.y / float(TPX))))
	if _entity_at.has(cell):
		return _entity_at[cell]
	return null


func _poll_move_dismiss_arm() -> void:
	if _move_dismiss_armed or not _semantic_any_expanded():
		return
	if _movement_input() == Vector2i.ZERO:
		_move_dismiss_armed = true


func _carried_move_blocked() -> bool:
	if _semantic_choice_acknowledging():
		return true
	return _semantic_any_expanded() and not _move_dismiss_armed


func _semantic_choice_acknowledging() -> bool:
	for raw in _semantic_labels:
		if is_instance_valid(raw) and raw.is_acknowledging():
			return true
	return false


func ui_hold_touch_direction(dir: Vector2i) -> void:
	_held_dir = dir


func ui_hold_key_direction(dir: Vector2i) -> void:
	_test_key_dir = dir


func ui_move_dismiss_armed() -> bool:
	return _move_dismiss_armed


func _semantic_owns_talk(e: Dictionary) -> bool:
	var semantic = e.get("semantic", {})
	if not (semantic is Dictionary):
		return false
	if str(semantic.get("interaction", "")) != "npc":
		return false
	return ui_semantic_label(str(semantic.get("knowledge_key", ""))) != null


func _semantic_in_range(e: Dictionary) -> bool:
	if bool(e.get("dynamic", false)):
		var actor = e.get("node")
		if actor != null and is_instance_valid(actor):
			e["pos"] = _actor_tile_pos(actor)
	var pos: Array = e.get("pos", [-99, -99])
	if pos.size() < 2:
		return false
	var d: Vector2i = (_john_pos - Vector2i(int(pos[0]), int(pos[1]))).abs()
	return d.x + d.y <= 1


func _semantic_talk_from_action(e: Dictionary) -> void:
	if not _semantic_in_range(e):
		return
	var semantic: Dictionary = e["semantic"]
	var lbl = ui_semantic_label(str(semantic.get("knowledge_key", "")))
	if lbl == null:
		return
	if str(lbl.interaction_state()) in ["SPEECH", "RESPONSES"]:
		return
	_start_semantic_conversation(e, lbl)


func _start_semantic_use(e: Dictionary, lbl) -> void:
	_begin_present(lbl)
	await _perform_entity_action(e)
	_end_present()


func _perform_entity_action(e: Dictionary) -> void:
	if e.has("puzzle_room") and e.has("puzzle_eid"):
		await _do_kit_action(e)
		return
	if _VRunner.is_active() and e.has("village_quest_node"):
		await _interact_village_anchor(e)
		return
	if _VRunner.is_bridge_mode() and bool(e.get("bridge_entity", false)):
		await _interact_bridge_entity(e)
		return
	match str(e.get("kind", "")):
		"sign", "door", "logs", "corpse":
			if e.has("puzzle_action"):
				_input_locked = true
				_touch.set_enabled(false)
				await _play.interact_puzzle(e)
				_input_locked = false
				_touch.set_enabled(true)
				_update_prompt()
			elif e.has("dungeon_id"):
				_input_locked = true
				_touch.set_enabled(false)
				await _dialogue.say_async("", _entity_text(e))
				if not _present_cancelled:
					await _play.enter_dungeon(e)
				_input_locked = false
				_touch.set_enabled(true)
				_update_prompt()
			elif e.has("choice_event"):
				_input_locked = true
				_touch.set_enabled(false)
				await _dialogue.say_async("", _entity_text(e))
				if not _present_cancelled:
					await _story.run_event(str(e["choice_event"]))
				_input_locked = false
				_touch.set_enabled(true)
			else:
				await _inspect_semantic(e)
		"fire":
			_interact_fire(e)
		"pickup":
			_interact_pickup(e)
		"npc":
			await _interact_npc(e)
		"creature", "wizard":
			await _interact_enemy(e)
		"exit":
			await _inspect_semantic(e)
		_:
			await _inspect_semantic(e)


func _inspect_semantic(e: Dictionary) -> void:
	var text := str(e.get("semantic", {}).get("observe_near", ""))
	if text == "":
		text = str(e.get("semantic", {}).get("label", "Nothing remarkable."))
	await _dialogue.say_async("", text)


func _begin_present(lbl) -> void:
	_present_label = lbl
	_present_cancelled = false
	if _dialogue != null:
		_dialogue.set_semantic_redirect(self)


func _end_present() -> void:
	_present_label = null
	if _dialogue != null:
		if _dialogue.is_redirecting() and (_dialogue.is_open() or _dialogue.is_waiting_choice()):
			_dialogue.release_redirect()
		_dialogue.set_semantic_redirect(null)


func semantic_cancelled() -> bool:
	return _present_cancelled


func semantic_present_choices(options: Array) -> void:
	if _present_cancelled or _present_label == null:
		return
	var labels: Array = []
	for i in options.size():
		labels.append({"index": i, "label": str(options[i])})
	_present_label.present_choices(labels)
	_semantic_focus = str(_present_label.knowledge_key())
	_sync_semantic_stack()


func semantic_say_now(_speaker: String, text: String) -> void:
	if _present_cancelled or _present_label == null:
		return
	_present_label.present_line(text)
	_semantic_focus = str(_present_label.knowledge_key())
	_sync_semantic_stack()


func semantic_say(_speaker: String, text: String) -> void:
	if _present_cancelled or _present_label == null:
		return
	_present_label.present_line(text)
	_semantic_focus = str(_present_label.knowledge_key())
	_sync_semantic_stack()
	await _present_label.line_done
	if _present_label != null and _present_label.is_talking():
		_present_label.collapse()


func semantic_choose(_prompt: String, options: Array) -> String:
	if _present_cancelled or _present_label == null or options.is_empty():
		return ""
	var labels: Array = []
	for i in options.size():
		labels.append({"index": i, "label": str(options[i])})
	_present_label.present_choices(labels)
	_semantic_focus = str(_present_label.knowledge_key())
	_sync_semantic_stack()
	var index: int = await _present_label.presentation_result
	if index < 0 or index >= options.size():
		return ""
	return str(options[index])


func _ensure_semantic(e: Dictionary, existing) -> void:
	if e.get("semantic") is Dictionary and _label_for_entity(e) != null:
		_hide_name_fallback(existing)
		return
	var semantic: Dictionary = _Adapter.adapt(e, area_id)
	if semantic.is_empty():
		return
	e["semantic"] = semantic
	var node = existing
	if not is_instance_valid(node):
		node = _make_semantic_anchor(e)
	_attach_semantic_label(e, node)
	_hide_name_fallback(node)


func _maybe_label_exit(e: Dictionary) -> void:
	var semantic: Dictionary = _Adapter.adapt(e, area_id)
	if semantic.is_empty():
		return
	e["semantic"] = semantic
	_attach_semantic_label(e, _make_semantic_anchor(e))


func _make_semantic_anchor(e: Dictionary) -> Node2D:
	var node := Node2D.new()
	node.position = Vector2(int(e["pos"][0]), int(e["pos"][1])) * TPX
	_actors_root.add_child(node)
	e["node"] = node
	return node


func _semantic_key(e: Dictionary) -> String:
	var semantic = e.get("semantic", {})
	if not (semantic is Dictionary):
		return ""
	return str(semantic.get("knowledge_key", ""))


func _label_for_entity(e: Dictionary):
	var key := _semantic_key(e)
	if key == "":
		return null
	return ui_semantic_label(key)


func _hide_name_fallback(node) -> void:
	if not is_instance_valid(node):
		return
	var direct = node.get_node_or_null("fallback_label")
	if direct != null:
		direct.visible = false
	var visual = node.get_node_or_null("Visual")
	if visual == null:
		return
	var fallback = visual.get_node_or_null("fallback_label")
	if fallback != null:
		fallback.visible = false


func _start_semantic_conversation(e: Dictionary, lbl) -> void:
	if str(lbl.interaction_state()) in ["SPEECH", "RESPONSES"]:
		return
	_present_cancelled = false
	_face_npc_toward_john(e)
	var lines: Array = []
	var options: Array = []
	if _VRunner.is_active() and e.has("village_test_story"):
		var result: Dictionary = _VQuest.interact_npc(str(e.get("id", "")))
		if not bool(result.get("success", false)):
			var err := str(result.get("error", ""))
			if err != "":
				lines = [err]
		else:
			lines = _turn_texts(result.get("turns", []))
			if lines.is_empty() and str(result.get("type", "")) in ["ambient", "conversation"]:
				lines = _npc_authored_lines(e)
			var offered: Array = result.get("options", [])
			if not offered.is_empty():
				options = offered
	else:
		lines = _npc_authored_lines(e)
	_adv().bump_talk(str(e.get("id", "")))
	lbl.begin_speech(lines, options)
	_update_prompt()
	_sync_semantic_stack()


func _semantic_followup_lines() -> Array:
	if _VQuest.is_complete():
		return []
	var extra: Array = []
	var guard := 0
	while guard < 16:
		guard += 1
		var node: Dictionary = _VQuest.current_node()
		if node.is_empty():
			return extra
		var node_type := str(node.get("type", ""))
		if node_type in ["branch", "choice"]:
			return extra
		if node_type in ["conclude", "set_flag"]:
			var result: Dictionary = _VQuest.execute_current()
			if bool(result.get("success", false)):
				extra.append_array(_turn_texts(result.get("turns", [])))
			if node_type == "conclude":
				return extra
			continue
		return extra
	return extra


func _turn_texts(turns) -> Array:
	var out: Array = []
	if not (turns is Array):
		return out
	for raw in turns:
		if raw is Dictionary and str((raw as Dictionary).get("text", "")).strip_edges() != "":
			out.append(str((raw as Dictionary).get("text", "")))
	return out


func _npc_authored_lines(e: Dictionary) -> Array:
	var adv := _adv()
	var lines: Array = e.get("lines", [])
	if e.has("lines_phase") and e["lines_phase"].has(adv.story_phase()):
		lines = e["lines_phase"][adv.story_phase()]
	if e.has("lines_flag"):
		for fl in e["lines_flag"].keys():
			if adv.flag(str(fl)):
				lines = e["lines_flag"][fl]
	if e.has("lines_run_flag"):
		for fl in e["lines_run_flag"].keys():
			if adv.run_flag(str(fl)):
				lines = e["lines_run_flag"][fl]
	var out: Array = []
	for line in lines:
		if str(line).strip_edges() != "":
			out.append(str(line))
	return out


func _entity_by_semantic_key(key: String) -> Dictionary:
	for e in _entities:
		var semantic = e.get("semantic", {})
		if semantic is Dictionary and str(semantic.get("knowledge_key", "")) == key:
			return e
	return {}


func _is_empty_pointer_press(event: InputEvent) -> bool:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		return true
	if event is InputEventScreenTouch and event.pressed:
		return true
	return false


func ui_semantic_focus() -> String:
	return _semantic_focus


func ui_tap_semantic(key: String) -> void:
	var lbl = ui_semantic_label(key)
	if lbl == null:
		return
	lbl.press()


func ui_semantic_responses(key: String) -> Array:
	var lbl = ui_semantic_label(key)
	if lbl == null:
		return []
	return lbl.response_labels()


func ui_semantic_selected(key: String) -> int:
	var lbl = ui_semantic_label(key)
	if lbl == null:
		return -1
	return int(lbl.selected_response())


func ui_tap_semantic_response(key: String, index: int) -> void:
	var lbl = ui_semantic_label(key)
	if lbl == null:
		return
	lbl.press_response(index)


func ui_clear_semantic_focus() -> void:
	_semantic_focus = ""


func ui_dialogue_open() -> bool:
	return _dialogue.is_open()


func ui_dialogue_panel_visible() -> bool:
	return _dialogue != null and _dialogue.visible


func ui_dialogue_advance() -> void:
	# Test harness taps are deliberate; skip the human-tap debounce.
	_dialogue._ignore_until_msec = 0
	_dialogue.advance()


func ui_dialogue_choose(label: String) -> void:
	_dialogue.pick(label)


func ui_dialogue_choose_index(i: int) -> void:
	_dialogue.pick_index(i)


func ui_action_button_visible() -> bool:
	return _touch != null and _touch.action_visible()


func ui_prompt_visible() -> bool:
	return _prompt_lbl != null and _prompt_lbl.visible


func _claim_semantic(key: String) -> void:
	if key == "":
		return
	if _semantic_focus != "" and _semantic_focus != key:
		var prev = ui_semantic_label(_semantic_focus)
		if prev != null and prev.is_expanded():
			prev.collapse()
	_semantic_focus = key


## One expanded interaction owns the foreground. RESPONSES hide every other label
## so a neighbour cannot cover or intercept the decision. Spawn order does not.
func _sync_semantic_stack() -> void:
	if _semantic_syncing or _semantic_focus_root == null:
		return
	_semantic_syncing = true
	var owner = _foreground_semantic_owner()
	var talking := owner != null and str(owner.interaction_state()) in ["SPEECH", "RESPONSES"]
	var to_release: Array = []
	for raw in _semantic_labels:
		if not is_instance_valid(raw) or raw == owner:
			continue
		if owner != null and raw.is_expanded():
			to_release.append(raw)
	for raw in to_release:
		raw.collapse()
	for raw in _semantic_labels:
		if not is_instance_valid(raw):
			continue
		var owns: bool = raw == owner
		if owns:
			if raw.get_parent() != _semantic_focus_root:
				raw.reparent(_semantic_focus_root)
			raw.set_foreground(true)
			raw.set_passive_suppressed(false)
			raw.move_to_front()
		else:
			if raw.get_parent() != _semantic_root and _semantic_root != null:
				raw.reparent(_semantic_root)
			raw.set_foreground(false)
			raw.set_passive_suppressed(talking and not raw.is_expanded())
	_semantic_syncing = false


func _foreground_semantic_owner():
	var focused = ui_semantic_label(_semantic_focus)
	if focused != null and focused.is_expanded() and focused.target_on_screen():
		return focused
	if _present_label != null and is_instance_valid(_present_label) and _present_label.is_expanded() and _present_label.target_on_screen():
		return _present_label
	var best = null
	var best_rank := 0
	for raw in _semantic_labels:
		if not is_instance_valid(raw) or not raw.target_on_screen():
			continue
		var rank: int = int(raw.focus_rank())
		if rank > best_rank:
			best_rank = rank
			best = raw
	return best


func _semantic_any_expanded() -> bool:
	if _scripted_running:
		return false
	for raw in _semantic_labels:
		if is_instance_valid(raw) and str(raw.interaction_state()) in ["OBSERVATION", "SPEECH", "RESPONSES"]:
			return true
	return false


func ui_items_button_visible() -> bool:
	return _items_btn != null and _items_btn.visible


func ui_entity_has_choice_event(id: String) -> bool:
	for e in _entities:
		if str(e.get("id", "")) == id:
			return e.has("choice_event")
	return false


func ui_dialogue_waiting_choice() -> bool:
	return _dialogue.is_waiting_choice()


func ui_prompt() -> String:
	return _prompt_lbl.text


func ui_input_locked() -> bool:
	return _input_locked


## Test/inspection: the sprite key currently drawn for the controllable character.
func ui_player_sprite_key() -> String:
	var path := _john.texture.resource_path if _john.texture else ""
	var base := path.get_file()
	for f in ["_left_", "_right_", "_up_", "_down_"]:
		var i := base.find(f)
		if i > 0:
			return base.substr(0, i)
	return base


## Test/inspection: tile position of a cutscene actor or entity.
func ui_actor_pos(key: String) -> Vector2i:
	return _actor_or_player_pos(key)


## Test/inspection: the lines an NPC would say right now (phase/flag resolved).
func ui_npc_lines_for(id: String) -> Array:
	var adv := _adv()
	for e in _entities:
		if str(e.get("id", "")) != id:
			continue
		var lines: Array = e.get("lines", [])
		if e.has("lines_phase") and e["lines_phase"].has(adv.story_phase()):
			lines = e["lines_phase"][adv.story_phase()]
		if e.has("lines_flag"):
			for fl in e["lines_flag"].keys():
				if adv.flag(str(fl)):
					lines = e["lines_flag"][fl]
		return lines
	return []


func ui_entity_exists(id: String) -> bool:
	for e in _entities:
		if str(e.get("id", "")) == id and e.get("node") != null and is_instance_valid(e["node"]):
			return true
	return false


func ui_tile_walkable(p: Vector2i) -> bool:
	return is_walkable(p)


func ui_is_exit(p: Vector2i) -> bool:
	# Test pathfinding must route around exits: stepping on one mid-path
	# triggers area travel and aborts the walk. (The engine rightly allows
	# stepping on exits; this is a test-harness concern.)
	for e in _entities:
		if str(e.get("kind", "")) == "exit" and Vector2i(int(e["pos"][0]), int(e["pos"][1])) == p:
			return true
	return false

# ---------------------------------------------------------------------------------
# Catalogue puzzle-test sessions (PuzzleTestRunner + DmbPuzzleKit + WorldPlay).
# Generic: no per-puzzle branches. The sim owns rules/blocking; this builds art,
# moves John, shows dialogue, and launches real battles.
# ---------------------------------------------------------------------------------

## Boot a pending puzzle-test session instead of the campaign area.
func _boot_kit_session(adv: Node) -> void:
	if not adv.is_active():
		adv.new_game()
	_play.setup(self, adv, _world_flow)
	var start := _Runner.begin(adv)
	_finish_kit_build(start, "down")
	adv.state_changed.connect(_refresh_hud)
	_refresh_hud()
	_fade_in()
	call_deferred("_after_ready")


## Load (or reload) the projected kit area. Used by load_area routing, rebuilds,
## reset and post-battle return - always through WorldPlay.puzzle_area().
func _load_kit_area(at: Vector2i, facing: String = "down") -> void:
	_finish_kit_build(at, facing)


func _finish_kit_build(at: Vector2i, facing: String) -> void:
	var adv := _adv()
	_play.setup(self, adv, _world_flow)
	_play.kit_sync(adv)
	area = _play.puzzle_area()
	area_id = str(area["id"])
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
	adv.set_location(area_id, _john_pos.x, _john_pos.y, _john_facing)
	_update_prompt()


## Re-project the kit area after sim state changed, keeping Johns tile.
func _rebuild_kit_area() -> void:
	_finish_kit_build(_john_pos, _john_facing)


## John arrived on a tile in a kit area: run sim on-step rules, apply the
## result generically (relocate / text / solved), rebuild visuals on change.
func _arrived_kit() -> void:
	var adv := _adv()
	adv.set_location(area_id, _john_pos.x, _john_pos.y, _john_facing)
	var r: Dictionary = _play.kit_on_step(adv, _john_pos)
	_apply_kit_relocate(r)
	for line in r.get("text", []):
		await _dialogue.say_async("", str(line))
	if bool(r.get("changed", false)):
		_rebuild_kit_area()
	else:
		_update_prompt()
	if bool(r.get("solved_now", false)):
		await _on_kit_solved()


## Facing interaction with a projected kit entity: real dialogue UI, sim action,
## Adventure transaction, relocate/battle/rebuild/solved handled generically.
func _do_kit_action(e: Dictionary) -> void:
	_input_locked = true
	_touch.set_enabled(false)
	var r: Dictionary = await _play.interact_kit_puzzle(e)
	_apply_kit_relocate(r)
	if str(r.get("battle", "")) != "":
		_Runner.set_battle_eid(str(e.get("puzzle_eid", "")))
		_start_battle(_play.kit_battle_entity(e, str(r["battle"])))
		return
	if bool(r.get("changed", false)):
		_rebuild_kit_area()
	else:
		_update_prompt()
	if bool(r.get("solved_now", false)):
		await _on_kit_solved()
	_input_locked = false
	_touch.set_enabled(true)
	_update_prompt()


## Apply a sim relocation (teleport / pit / reset-to-start / sequence move).
func _apply_kit_relocate(r: Dictionary) -> void:
	var rel = r.get("relocate")
	if rel == null:
		return
	_john_pos = Vector2i(int(rel[0]), int(rel[1]))
	_john.position = Vector2(_john_pos) * TPX + Vector2(0, -8 * TILE_SCALE)
	_camera.position = _john.position + Vector2(TPX * 0.5, TPX * 0.5)
	_moving = false


## Deterministic kit tick quantum; rebuild only when the sim reports change.
func _tick_kit(delta: float) -> void:
	if not _Runner.is_active() or not _play.is_kit_puzzle_area(area):
		_kit_tick_acc = 0.0
		return
	if _input_locked or _scripted_running:
		return
	_kit_tick_acc += delta
	if _kit_tick_acc < 0.5:
		return
	_kit_tick_acc = 0.0
	var r: Dictionary = _play.kit_tick(_adv(), 0.5)
	if bool(r.get("changed", false)):
		var keep := _john_pos
		var keep_f := _john_facing
		_rebuild_kit_area()
		_john_pos = keep
		_john_facing = keep_f
		_john.position = Vector2(_john_pos) * TPX + Vector2(0, -8 * TILE_SCALE)


## Return from a production battle inside a kit session: same puzzle, kit
## state preserved, guardian defeat recorded generically from its entity.
func _after_kit_battle(r: Dictionary) -> void:
	var adv := _adv()
	var eid := _Runner.take_battle_eid()
	var victory := str(r.get("outcome", "")) == "victory"
	if victory and eid != "":
		_play.kit_on_battle_result(eid, true)
	_play.setup(self, adv, _world_flow)
	_finish_kit_build(_john_pos, _john_facing)
	_refresh_hud()
	_fade_in()
	if victory:
		await _dialogue.say_async("", "The guardian falls. The way responds.")
		if bool(_Runner.kit_state().get("solved", false)):
			await _on_kit_solved()
	else:
		await _dialogue.say_async("", "You withdraw, study the room, and try again.")
	_input_locked = false
	_touch.set_enabled(true)


## Solved fanfare with production-styled Reset / Menu / Next options.
func _on_kit_solved() -> void:
	var adv := _adv()
	var options := ["Keep exploring", "Next puzzle", "Reset puzzle", "Puzzle menu"]
	var choice: String = await _dialogue.choose_async("Solved - the room holds still, as if listening.", options)
	match choice:
		"Reset puzzle":
			_finish_kit_build(_Runner.reset(adv), "down")
		"Puzzle menu":
			await _exit_kit_to_menu()
		"Next puzzle":
			var nid := _Runner.next_puzzle_id()
			if nid == "":
				await _dialogue.say_async("", "That was the last room in the catalogue.")
			else:
				_Runner.set_puzzle(nid)
				_Runner.end(adv)
				_play.setup(self, adv, _world_flow)
				_finish_kit_build(_Runner.begin(adv), "down")


## Leave the session: restore the exact pre-test campaign snapshot, no residue.
func _exit_kit_to_menu() -> void:
	_Runner.end(_adv())
	get_tree().change_scene_to_file("res://client/scenes/puzzle_test_menu.tscn")


## Parse a projection tint (Color, hex string, or RGB array) for Sprite2D.
func _parse_tint(v) -> Color:
	if v is Color:
		return v
	if v is String:
		return Color(str(v))
	if v is Array and (v as Array).size() >= 3:
		var a: Array = v
		return Color(float(a[0]), float(a[1]), float(a[2]))
	return Color.WHITE



## Test Village quest interaction. The runner owns canonical story state; this
## layer only presents it through the production dialogue UI.
func _play_village_turns(npc_name: String, turns: Array) -> void:
	for raw in turns:
		if not (raw is Dictionary):
			continue
		var turn: Dictionary = raw
		var text := str(turn.get("text", ""))
		if text == "":
			continue
		var speaker := str(turn.get("speaker", "npc"))
		if speaker.to_lower() == "john":
			speaker = "John"
		elif speaker == "npc":
			speaker = npc_name
		await _dialogue.say_async(speaker, text)


func _village_present_choice(payload: Dictionary, npc_name: String, npc_id: String = "") -> void:
	var options: Array = payload.get("options", [])
	if options.is_empty():
		return
	var labels: Array = []
	for raw in options:
		if raw is Dictionary:
			labels.append(str((raw as Dictionary).get("label", "Continue")))
	if labels.is_empty():
		return
	var picked: String = await _dialogue.choose_async(str(payload.get("prompt", "What do you do?")), labels)
	if picked == "":
		return
	var index := labels.find(picked)
	if index < 0:
		return
	var result: Dictionary = _VQuest.respond_to(npc_id, index) if npc_id != "" else _VQuest.make_choice(index)
	if bool(result.get("return_options", false)) or bool(result.get("inquiry", false)):
		await _play_village_turns(npc_name, result.get("turns", []))
		await _village_present_choice(result, npc_name, npc_id)
		return
	if bool(result.get("success", false)):
		await _play_village_turns(npc_name, result.get("turns", []))
	elif str(result.get("error", "")) != "":
		await _dialogue.say_async("", str(result["error"]))


func _village_resolve_pending_nodes(npc_name: String = "") -> void:
	# Collapse data-only branch/set/conclude nodes after the interaction that
	# reached them. NPC-bound choices still require talking to that NPC.
	var guard := 0
	while guard < 16:
		guard += 1
		var node: Dictionary = _VQuest.current_node()
		if node.is_empty():
			return
		var node_type := str(node.get("type", ""))
		if node_type in ["branch", "choice"]:
			if node_type == "choice" and str(node.get("npc", "")) != "":
				return
			var payload: Dictionary = _VQuest.current_choice_payload()
			await _village_present_choice(payload, npc_name)
			continue
		if node_type in ["conclude", "set_flag"]:
			var result: Dictionary = _VQuest.execute_current()
			if bool(result.get("success", false)):
				await _play_village_turns(npc_name, result.get("turns", []))
			if node_type == "conclude":
				return
			continue
		return


func _interact_village_npc(e: Dictionary) -> void:
	_input_locked = true
	_touch.set_enabled(false)
	_face_npc_toward_john(e)
	var id := str(e.get("id", ""))
	var name := str(e.get("name", id))
	var result: Dictionary = _VQuest.interact_npc(id)
	if not bool(result.get("success", false)):
		var err := str(result.get("error", "That conversation is not available yet."))
		if err != "":
			await _dialogue.say_async("", err)
	else:
		var turns: Array = result.get("turns", [])
		if turns.is_empty() and str(result.get("type", "")) == "ambient":
			for line in e.get("lines", []):
				turns.append({"speaker": "npc", "text": str(line)})
		await _play_village_turns(name, turns)
		if not result.get("options", []).is_empty():
			await _village_present_choice(result, name, id)
		elif bool(result.get("progression", false)):
			await _village_resolve_pending_nodes(name)
	_adv().bump_talk(id)
	_input_locked = false
	_touch.set_enabled(true)
	_update_prompt()


func _interact_village_anchor(e: Dictionary) -> void:
	_input_locked = true
	_touch.set_enabled(false)
	var anchor := str(e.get("village_quest_anchor", ""))
	var result: Dictionary = _VQuest.interact_anchor(anchor)
	if bool(result.get("success", false)):
		await _play_village_turns("", result.get("turns", []))
		await _village_resolve_pending_nodes("")
	elif str(e.get("text", "")) != "":
		await _dialogue.say_async("", str(e["text"]))
	_input_locked = false
	_touch.set_enabled(true)
	_update_prompt()

## Boot a pending village-test session instead of the campaign area.
func _boot_village_test(adv: Node) -> void:
	if not adv.is_active():
		adv.new_game()
	_play.setup(self, adv, _world_flow)
	var start := _VRunner.begin(adv)
	_finish_village_build(start, _VRunner.session_facing())
	adv.state_changed.connect(_refresh_hud)
	_refresh_hud()
	_fade_in()
	call_deferred("_after_ready")


## Load (or reload) the projected village test area.
func _finish_village_build(at: Vector2i, facing: String) -> void:
	var adv := _adv()
	area = _VRunner.get_area()
	area_id = str(area["id"])
	if _VRunner.is_generated():
		# Generated mode: the runner has written the projected world into the
		# (disposable) adventure state; WorldFlow restores the same sim from it,
		# so talking, quests, exits and dungeons all run the production path.
		_world_flow.sim = null
		_world_flow.setup(adv)
	_play.setup(self, adv, _world_flow)
	var rows: Array = area["rows"]
	grid_h = rows.size()
	grid_w = str(rows[0]).length()
	for c in _tiles_root.get_children():
		c.queue_free()
	for c in _props_root.get_children():
		c.queue_free()
	for c in _actors_root.get_children():
		if c == _john:
			continue
		# Preserve G05 WorkerController / activity presenters mounted under actors.
		if str(c.name) == "WorkerController" or c.is_in_group("dmb_person_presenter"):
			continue
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
	adv.set_location(area_id, _john_pos.x, _john_pos.y, _john_facing)
	_update_prompt()


func _bridge_host():
	return _VRunner.bridge_host()


func _interact_bridge_npc(e: Dictionary) -> void:
	var host = _bridge_host()
	var id := str(e["id"])
	_input_locked = true
	_touch.set_enabled(false)
	_face_npc_toward_john(e)
	var reply: Dictionary = {}
	if host != null and host.has_method("talk_to"):
		reply = host.talk_to(id)
	else:
		reply = _VRunner.bridge_command("talk-%s" % id, "Interact", {"action": "talk", "entity_id": id})
	var payload: Dictionary = reply.get("payload", {}) if typeof(reply.get("payload", {})) == TYPE_DICTIONARY else {}
	var text := str(payload.get("text", reply.get("public_feedback", "")))
	var speaker := str(payload.get("speaker_name", e.get("name", "Worker")))
	if text == "":
		text = "…"
	# Formal dialogue: Pause Game Time while choices are open.
	var session: Dictionary = payload.get("session", {}) if typeof(payload.get("session", {})) == TYPE_DICTIONARY else {}
	var choices: Array = payload.get("choices", [])
	var pause_token := ""
	if choices.size() > 0:
		if _bridge_runtime != null and _bridge_runtime.has_method("acquire_pause"):
			pause_token = str(_bridge_runtime.acquire_pause("choice"))
		else:
			var pause_reply: Dictionary = _VRunner.bridge_command("pause-dlg", "Pause", {"reason": "choice"})
			if str(pause_reply.get("status", "")) == "ACCEPTED":
				pause_token = str(pause_reply.get("payload", {}).get("token", ""))
	await _dialogue.say_async(speaker, text)
	if choices.size() > 0 and not _present_cancelled:
		var labels: Array = []
		for c in choices:
			if typeof(c) == TYPE_DICTIONARY:
				labels.append(str(c.get("label", c.get("id", "…"))))
			else:
				labels.append(str(c))
		labels.append("Walk away")
		var picked: String = await _dialogue.choose_async("Respond", labels)
		if picked != "Walk away" and picked != "":
			var choice_id := ""
			for c in choices:
				if typeof(c) == TYPE_DICTIONARY and str(c.get("label", "")) == picked:
					choice_id = str(c.get("id", ""))
					break
			if choice_id != "":
				var choose_reply: Dictionary = _VRunner.bridge_command(
					"choose-%s" % choice_id,
					"Interact",
					{"action": "choose_dialogue", "session_id": str(session.get("id", "")), "choice_id": choice_id}
				)
				var next_text := str(choose_reply.get("payload", {}).get("session", {}).get("text", choose_reply.get("public_feedback", "")))
				if next_text != "":
					await _dialogue.say_async(speaker, next_text)
		_VRunner.bridge_command(
			"close-dlg",
			"Interact",
			{"action": "close_dialogue", "session_id": str(session.get("id", ""))}
		)
	if pause_token != "":
		if _bridge_runtime != null and _bridge_runtime.has_method("release_pause"):
			_bridge_runtime.release_pause()
		else:
			_VRunner.bridge_command("resume-dlg", "Resume", {"token": pause_token})
	_input_locked = false
	_touch.set_enabled(true)
	_update_prompt()


func _interact_bridge_challenge(e: Dictionary) -> void:
	var host = _bridge_host()
	var cube_id := str(e.get("cube_id", e.get("id", "")))
	_input_locked = true
	_touch.set_enabled(false)
	await _dialogue.say_async("", "A dangerous manifestation fouls this ground.")
	var choice: String = await _dialogue.choose_async("Challenge the manifestation?", ["Challenge", "Walk away"])
	if choice == "Challenge" and host != null:
		if host.has_method("start_hazard_challenge"):
			host.start_hazard_challenge(cube_id)
		elif host.has_method("start_demon_challenge"):
			host.start_demon_challenge(cube_id)
	_input_locked = false
	_touch.set_enabled(true)
	_update_prompt()


func _interact_bridge_pickup(e: Dictionary) -> void:
	var host = _bridge_host()
	_input_locked = true
	_touch.set_enabled(false)
	var reply: Dictionary = {}
	if host != null and host.has_method("pickup_item"):
		reply = host.pickup_item(str(e["id"]))
	else:
		reply = _VRunner.bridge_command("pickup", "Interact", {"action": "pickup", "item_id": str(e["id"])})
	await _dialogue.say_async("", str(reply.get("public_feedback", "Taken.")))
	if host != null and host.has_method("reproject_from_python"):
		host.reproject_from_python()
	_input_locked = false
	_touch.set_enabled(true)
	_update_prompt()


func _interact_bridge_entity(e: Dictionary) -> void:
	if bool(e.get("bridge_talk", false)):
		await _interact_bridge_npc(e)
		return
	if bool(e.get("bridge_challenge", false)):
		await _interact_bridge_challenge(e)
		return
	var host = _bridge_host()
	if bool(e.get("bridge_enter", false)) or str(e.get("dungeon_id", "")) == "dungeon.sluice":
		_input_locked = true
		_touch.set_enabled(false)
		await _dialogue.say_async("", str(e.get("text", "Sluice works")))
		if host != null and host.has_method("enter_sluice"):
			host.enter_sluice()
		_input_locked = false
		_touch.set_enabled(true)
		_update_prompt()
		return
	if bool(e.get("bridge_return_village", false)) or str(e.get("to_area", "")) == "area.village":
		_input_locked = true
		_touch.set_enabled(false)
		if host != null and host.has_method("return_village"):
			host.return_village()
		_input_locked = false
		_touch.set_enabled(true)
		_update_prompt()
		return
	if bool(e.get("bridge_travel", false)) and str(e.get("to_node", "")) != "":
		await _bridge_travel_exit(e)
		return
	if bool(e.get("bridge_puzzle", false)):
		await _interact_bridge_puzzle(e)
		return
	if bool(e.get("bridge_pickup", false)):
		await _interact_bridge_pickup(e)
		return
	# Buildings / generic bridge entities: player-safe observation, then Inspect nearby.
	var semantic: Dictionary = e.get("semantic", {})
	var far := str(semantic.get("observe_far", ""))
	var near := str(semantic.get("observe_near", ""))
	if far == "":
		far = str(e.get("text", "Nothing remarkable."))
	if near == "":
		near = far
	_input_locked = true
	_touch.set_enabled(false)
	if _semantic_in_range(e):
		var options: Array = ["Inspect"]
		if str(semantic.get("interaction", "")) == "building":
			options.append("Observe")
		var choice: String = await _dialogue.choose_async(far if far != near else "Look closer?", options)
		if choice == "Inspect" or choice == "Observe":
			await _dialogue.say_async("", near)
	else:
		await _dialogue.say_async("", far)
	_input_locked = false
	_touch.set_enabled(true)
	_update_prompt()


func _bridge_travel_exit(e: Dictionary) -> void:
	var host = _bridge_host()
	var to_node := str(e.get("to_node", ""))
	var from_node := str(e.get("from_node", ""))
	if to_node == "" or host == null or not host.has_method("travel_to_node"):
		await _dialogue.say_async("", str(e.get("travel_text", "The path goes nowhere useful.")))
		return
	_input_locked = true
	_touch.set_enabled(false)
	var travel_text := str(e.get("travel_text", ""))
	if travel_text != "":
		await _dialogue.say_async("", travel_text)
	var choice: String = await _dialogue.choose_async("Leave this place?", ["Travel", "Stay"])
	if choice != "Travel":
		_input_locked = false
		_touch.set_enabled(true)
		_update_prompt()
		return
	var tw := create_tween()
	tw.tween_property(_fader, "modulate:a", 1.0, 0.25)
	await tw.finished
	var ok: bool = host.travel_to_node(from_node, to_node)
	_fade_in()
	if not ok:
		await _dialogue.say_async("", "You cannot travel that way right now.")
	_input_locked = false
	_touch.set_enabled(true)
	_update_prompt()


func _interact_bridge_puzzle(e: Dictionary) -> void:
	var host = _bridge_host()
	var mid := str(e.get("mechanism_id", e.get("id", "")))
	var kind := str(e.get("mechanism_kind", ""))
	var lease_id := str(e.get("lease_id", _VRunner.get_area().get("puzzle_lease_id", "")))
	var lease_version := int(e.get("lease_version", _VRunner.get_area().get("puzzle_lease_version", 1)))
	_input_locked = true
	_touch.set_enabled(false)
	var options: Array = ["Inspect"]
	var default_action := "toggle"
	if kind == "movable_box":
		options = ["Push", "Inspect"]
		default_action = "push"
	elif kind == "item_receptor":
		options = ["Place handle", "Inspect"]
		default_action = "place"
	elif kind == "gate":
		options = ["Open", "Inspect"]
		default_action = "open"
	elif kind == "switch":
		options = ["Activate", "Inspect"]
		default_action = "on"
	options.append("Walk away")
	var picked: String = await _dialogue.choose_async(str(e.get("text", mid)), options)
	if picked == "Walk away" or picked == "Inspect" or picked == "":
		if picked == "Inspect":
			await _dialogue.say_async("", str(e.get("text", mid)))
		_input_locked = false
		_touch.set_enabled(true)
		_update_prompt()
		return
	var mech_action := default_action
	if picked == "Push":
		mech_action = "push"
	elif picked == "Place handle":
		mech_action = "place"
	elif picked == "Open":
		mech_action = "open"
	elif picked == "Activate":
		mech_action = "on"
	var item_id := ""
	if mech_action == "place":
		item_id = "item:sluice_handle"
	var reply: Dictionary = {}
	if mech_action == "push":
		reply = _VRunner.bridge_command(
			"push-%s" % mid,
			"Interact",
			{"action": "puzzle_push", "lease_id": lease_id, "mechanism_id": mid, "expected_version": lease_version}
		)
	elif host != null and host.has_method("puzzle_act"):
		reply = host.puzzle_act(lease_id, mid, mech_action, lease_version, item_id)
	else:
		var payload := {
			"action": "puzzle_act",
			"lease_id": lease_id,
			"mechanism_id": mid,
			"mechanism_action": mech_action,
			"expected_version": lease_version,
		}
		if item_id != "":
			payload["item_id"] = item_id
		reply = _VRunner.bridge_command("puzzle-%s" % mid, "Interact", payload)
	await _dialogue.say_async("", str(reply.get("public_feedback", "Done.")))
	var finish: Dictionary = reply.get("payload", {}).get("finish", {}) if typeof(reply.get("payload", {})) == TYPE_DICTIONARY else {}
	if str(finish.get("status", "")) == "applied" or bool(reply.get("payload", {}).get("solved_now", false)):
		_VRunner.bridge_command("confirm-quest", "Interact", {"action": "confirm_village_quest"})
	if host != null and host.has_method("reproject_from_python"):
		host.reproject_from_python()
	_input_locked = false
	_touch.set_enabled(true)
	_update_prompt()


## Leave the village test session: restore the exact pre-test campaign snapshot.
func _exit_village_test() -> void:
	if _VRunner.is_bridge_mode():
		# Hosted under G05 shell — do not bounce to Village Test Menu.
		_VRunner.end(_adv())
		return
	_VRunner.end(_adv())
	get_tree().change_scene_to_file("res://client/scenes/village_test_menu.tscn")
