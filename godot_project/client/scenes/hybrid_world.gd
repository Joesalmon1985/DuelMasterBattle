extends Overworld

const HexCoords = preload("res://client/hybrid/hex_coords.gd")
const SimClient = preload("res://client/hybrid/sim_client.gd")
const DuelAdapter = preload("res://client/encounters/duel_lease_adapter.gd")
const HybridArt = preload("res://client/hybrid/hybrid_art.gd")
const GodMode = preload("res://client/hybrid/god_mode.gd")
const TerrainView = preload("res://client/hybrid/terrain_view.gd")
const WizardLabels = preload("res://client/hybrid/wizard_labels.gd")
const StoryUi = preload("res://client/hybrid/story_ui.gd")
const NetDuelSim = preload("res://client/duel/net_duel_sim.gd")
const GameBoardScene = preload("res://client/scenes/game_board.tscn")
const CharAppearance = preload("res://client/characters/character_appearance.gd")

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
var selected_ids: Dictionary = {}:
	set(v):
		selected_ids = v
		_art.selected = v

# ---- LAN multiplayer (docs/MOBILE_LAN_MULTIPLAYER.md). The host owns the clock; this client sends one `move` per tile and
# polls `state` asynchronously; other wizards are actors glided between polls; a Ward duel against another human is the
# retained board over DmbNetDuelSim (the host scores every cast).
var mp := false
var _mp_state_pending := false
var _mp_seq := 0
var _mp_players: Dictionary = {}  # id -> last row seen
var _mp_status: Label
var _mp_toast: Label
var _mp_toast_t := 0.0
var _mp_invite_panel: PanelContainer
var _mp_invite_lbl: Label
var _mp_invite: Dictionary = {}
var _mp_challenge_btn: Button
var _mp_reconnect_acc := 0.0
var _mp_lost := false
var _mp_polls := 0
var _mp_bytes_at_start := 0
var _mp_started_ms := 0
var _pvp_board: Node = null
var _pvp_sim = null
var _pvp_duel_id := ""
var _pvp_last_outcome := ""
const MP_SPRITES := ["red_mage", "hedge_mage", "blue_mage", "assassin"]


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
	mp = LanSession.is_multiplayer()
	if mp:
		if not _mp_connect():
			push_error("LAN host unreachable: %s" % LanSession.last_error)
			_hud_area_lbl.text = "Host unreachable"
			return
	else:
		var port := int(OS.get_environment("HYBRID_SIM_PORT"))
		if port <= 0:
			port = 8765
		if not _sim.connect_to(port):
			push_error("Hybrid sim server is not running on 127.0.0.1:%d" % port)
			_hud_area_lbl.text = "Sim server missing"
			return
	var tview = TerrainView.new()
	if tview.load_from(_sim.op({"op": "terrain"}, 20000)):
		terrain = tview
	var reply: Dictionary = _sim.op({"op": "state", "full": true}, 20000) if mp else _sim.op({"op": "snapshot"})
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
	if mp:
		_mp_build_ui()
		_mp_apply(reply)
		_mp_started_ms = Time.get_ticks_msec()
		_mp_bytes_at_start = _sim.bytes_in
	if mp or OS.has_feature("mobile"):
		_touch.set_action_visible(true)  # phones: the interact button is always on


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
	_art.industry.begin_frame(delta)
	if _camera_nudge != Vector2.ZERO:
		_camera.position += _camera_nudge
	if camera_focus != Vector2.INF:
		_camera.position = camera_focus
	if mp:
		_mp_process(delta)
		queue_redraw()
		return
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
	if mp and event is InputEventKey and event.pressed and not event.echo and _mp_key(event.keycode):
		get_viewport().set_input_as_handled()
		return
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
	if mp:
		# one validated step per tile; the host answers with the authoritative pose (a refusal snaps the avatar back)
		_mp_seq += 1
		_sim.request({"op": "move", "seq": _mp_seq, "tx": _john_pos.x, "ty": _john_pos.y, "facing": _john_facing}, Callable(self, "_on_move_reply"))
		var me: Dictionary = _snapshot.get("player", {})
		me["tx"] = _john_pos.x
		me["ty"] = _john_pos.y
		me["facing"] = _john_facing
		_update_prompt()
		_mp_update_challenge_button()
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
		CharAppearance.faction_tribes[str(f.get("name", ""))] = str(f.get("tribe", ""))
		CharAppearance.faction_colors[str(f.get("name", ""))] = Color.html(str(f.get("color", "#ffffff")))
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
	_art.crowd.player_tile = Vector2(_john_pos)
	for entity in rows:
		_art.draw_entity(self, entity, TPX)
	_art.draw_effects(self, _snapshot.get("effects", []), TPX)
	if god != null:
		god.draw_overlay(self)


# ---------------------------------------------------------------------------
# LAN multiplayer
# ---------------------------------------------------------------------------

func _mp_connect() -> bool:
	if LanSession.sim != null and LanSession.sim.connected():
		_sim = LanSession.sim
		return true
	var reply: Dictionary = LanSession.connect_and_hello(LanSession.host_address, LanSession.port, LanSession.join_code, LanSession.default_player_name(), LanSession.host_secret, LanSession.token)
	if str(reply.get("status", "")) != "ok":
		return false
	_sim = LanSession.sim
	return true


func _mp_build_ui() -> void:
	var layer := CanvasLayer.new()
	layer.name = "LanLayer"
	layer.layer = 12
	add_child(layer)
	_mp_status = Label.new()
	_mp_status.name = "LanStatus"
	_mp_status.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_mp_status.offset_left = -520
	_mp_status.offset_right = -12
	_mp_status.offset_top = 10
	_mp_status.offset_bottom = 40
	_mp_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_mp_status.add_theme_font_size_override("font_size", 20)
	_mp_status.add_theme_color_override("font_color", Color(0.75, 0.95, 1.0))
	_mp_status.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	_mp_status.add_theme_constant_override("outline_size", 4)
	_mp_status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_mp_status.text = "LAN"
	layer.add_child(_mp_status)
	_mp_toast = Label.new()
	_mp_toast.name = "LanToast"
	_mp_toast.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_mp_toast.offset_left = -360
	_mp_toast.offset_right = 360
	_mp_toast.offset_top = 150
	_mp_toast.offset_bottom = 200
	_mp_toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_mp_toast.add_theme_font_size_override("font_size", 26)
	_mp_toast.add_theme_color_override("font_color", Color(1.0, 0.85, 0.4))
	_mp_toast.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	_mp_toast.add_theme_constant_override("outline_size", 6)
	_mp_toast.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_mp_toast.visible = false
	layer.add_child(_mp_toast)
	_mp_challenge_btn = Button.new()
	_mp_challenge_btn.name = "ChallengeButton"
	_mp_challenge_btn.text = "⚔ Challenge"
	_mp_challenge_btn.focus_mode = Control.FOCUS_NONE
	_mp_challenge_btn.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_mp_challenge_btn.offset_left = -16 - 230
	_mp_challenge_btn.offset_right = -16
	_mp_challenge_btn.offset_top = -108 - 110 - 16 - 72
	_mp_challenge_btn.offset_bottom = -108 - 110 - 16
	_mp_challenge_btn.add_theme_font_size_override("font_size", 24)
	_mp_challenge_btn.add_theme_stylebox_override("normal", _VT.gem_button_style())
	_mp_challenge_btn.add_theme_stylebox_override("hover", _VT.gem_button_style())
	_mp_challenge_btn.add_theme_stylebox_override("pressed", _VT.gem_button_style(true))
	_mp_challenge_btn.add_theme_color_override("font_color", _VT.COLOR_ACCENT_GOLD)
	_mp_challenge_btn.pressed.connect(func(): mp_challenge())
	_mp_challenge_btn.visible = false
	layer.add_child(_mp_challenge_btn)
	_mp_invite_panel = PanelContainer.new()
	_mp_invite_panel.name = "InvitePanel"
	_mp_invite_panel.add_theme_stylebox_override("panel", _VT.panel_style(16))
	_mp_invite_panel.set_anchors_preset(Control.PRESET_CENTER)
	_mp_invite_panel.offset_left = -300
	_mp_invite_panel.offset_right = 300
	_mp_invite_panel.offset_top = -120
	_mp_invite_panel.offset_bottom = 120
	_mp_invite_panel.visible = false
	layer.add_child(_mp_invite_panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 16)
	_mp_invite_panel.add_child(v)
	_mp_invite_lbl = Label.new()
	_mp_invite_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_mp_invite_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_mp_invite_lbl.add_theme_font_size_override("font_size", 26)
	_VT.apply_label_primary(_mp_invite_lbl)
	v.add_child(_mp_invite_lbl)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 24)
	v.add_child(row)
	for spec in [["Accept", true], ["Decline", false]]:
		var b := Button.new()
		b.name = str(spec[0]) + "Button"
		b.text = str(spec[0])
		b.custom_minimum_size = Vector2(190, 68)
		b.add_theme_font_size_override("font_size", 26)
		if bool(spec[1]):
			_VT.style_primary_button(b)
		else:
			_VT.style_secondary_button(b)
		var accept: bool = bool(spec[1])
		b.pressed.connect(func(): mp_respond(accept))
		row.add_child(b)


func _mp_process(delta: float) -> void:
	_sim.poll()
	if _mp_toast_t > 0.0:
		_mp_toast_t -= delta
		if _mp_toast_t <= 0.0:
			_mp_toast.visible = false
	if not _sim.connected():
		_mp_lost = true
		_mp_state_pending = false
		_mp_reconnect_acc += delta
		_mp_status.text = "LAN · connection lost · reconnecting…"
		if _mp_reconnect_acc >= 2.0:
			_mp_reconnect_acc = 0.0
			var r: Dictionary = LanSession.connect_and_hello(LanSession.host_address, LanSession.port, LanSession.join_code, LanSession.default_player_name(), LanSession.host_secret, LanSession.token)
			if str(r.get("status", "")) == "ok":
				_sim = LanSession.sim
				_mp_lost = false
				var full: Dictionary = _sim.op({"op": "state", "full": true}, 20000)
				_apply_snapshot(full.get("snapshot", {}))
				_place_john_from_snapshot()  # the host's pose is the truth after a reconnect
				_mp_apply(full)
				_mp_toast_show("Reconnected")
		return
	_clock_acc += delta
	if _clock_acc >= POLL_SECONDS and not _mp_state_pending:
		_clock_acc = 0.0
		_mp_state_pending = true
		_sim.request({"op": "state", "seq": _mp_seq}, Callable(self, "_on_state_reply"))


func _on_state_reply(reply: Dictionary) -> void:
	_mp_state_pending = false
	if str(reply.get("status", "")) != "ok":
		return
	_mp_polls += 1
	_apply_snapshot(reply.get("snapshot", {}))
	_mp_apply(reply)


func _mp_apply(reply: Dictionary) -> void:
	_mp_apply_players(reply.get("snapshot", {}).get("players", []))
	for n in reply.get("notices", []):
		if typeof(n) == TYPE_DICTIONARY:
			_mp_notice(n)
	var inv: Dictionary = reply.get("invite", {}) if typeof(reply.get("invite", {})) == TYPE_DICTIONARY else {}
	if inv.is_empty() != _mp_invite.is_empty() or str(inv.get("duel_id", "")) != str(_mp_invite.get("duel_id", "")):
		_mp_invite = inv
		_mp_invite_panel.visible = not inv.is_empty() and not _duel_open
		if not inv.is_empty():
			var f: Dictionary = inv.get("format", {})
			_mp_invite_lbl.text = "%s challenges you to a Ward duel\n%d spells · %d colours · %d casts" % [str(inv.get("from_name", "A wizard")), int(f.get("slots", 3)), int(f.get("colours", 3)), int(f.get("max_casts", 10))]
	_mp_handle_duel(reply.get("duel", {}) if typeof(reply.get("duel", {})) == TYPE_DICTIONARY else {})
	_mp_status.text = _mp_status_text(reply)
	_mp_update_challenge_button()


func _mp_apply_players(rows: Array) -> void:
	var seen := {}
	for row in rows:
		if typeof(row) != TYPE_DICTIONARY:
			continue
		var pid := str(row.get("id", ""))
		if pid == "" or bool(row.get("you", false)):
			continue
		seen[pid] = true
		var tile := Vector2i(int(row.get("tx", 0)), int(row.get("ty", 0)))
		var facing := str(row.get("facing", "down"))
		var key := "lan:" + pid
		var node: Sprite2D = actor(key)
		if node == null:
			var idx := maxi(0, int(pid.substr(1)) - 2)
			node = spawn_actor(key, MP_SPRITES[idx % MP_SPRITES.size()], tile, facing)
			node.set_meta("tile", tile)
			var cv = _ActorVisual.view_of(node)
			if cv != null:  # every player is a wizard of their own cut and colour, stable for that player id on every client
				cv.set_look(CharAppearance.for_player(pid, str(row.get("name", pid)), str(row.get("colour", ""))))
			var lbl := Label.new()
			lbl.name = "Name"
			lbl.text = str(row.get("name", pid))
			lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			lbl.add_theme_font_size_override("font_size", 18)
			lbl.add_theme_color_override("font_color", Color.html(str(row.get("colour", "#ffffff"))))
			lbl.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
			lbl.add_theme_constant_override("outline_size", 5)
			lbl.size = Vector2(160, 24)
			lbl.scale = Vector2(1.0 / maxf(node.scale.x, 0.01), 1.0 / maxf(node.scale.y, 0.01))
			lbl.position = Vector2(16.0 - 80.0 / maxf(node.scale.x, 0.01), -17.0)
			node.add_child(lbl)
		else:
			var prev: Vector2i = node.get_meta("tile", tile)
			if prev != tile:
				node.set_meta("tile", tile)
				move_actor(key, tile, POLL_SECONDS)  # glide between polls (interpolation); facing follows the motion
			elif str(node.get_meta("facing", "")) != facing:
				face_actor(key, facing)
		node.modulate.a = 1.0 if bool(row.get("connected", true)) else 0.45
		_mp_players[pid] = row
	for pid in _mp_players.keys():
		if not seen.has(pid):
			remove_actor("lan:" + pid)
			_mp_players.erase(pid)


func _mp_handle_duel(view: Dictionary) -> void:
	if view.is_empty():
		if _pvp_board != null and _pvp_sim != null and _pvp_sim.result == null:
			_mp_close_pvp_board("cancelled")  # the host dropped the duel (a cycle reset)
		return
	var state := str(view.get("state", ""))
	var duel_id := str(view.get("duel_id", ""))
	if _pvp_board == null:
		if state in ["setup", "active"]:
			_mp_open_pvp_board(view)
		elif state == "finished" and duel_id != _pvp_duel_id:
			# finished while this screen had no board (a reconnect): acknowledge and tell the player
			_pvp_duel_id = duel_id
			var r: Dictionary = view.get("result", {})
			_mp_toast_show("Duel %s (%s)" % [str(r.get("outcome", "")), str(r.get("reason", ""))])
			_sim.op({"op": "pvp_leave"})
		return
	if _pvp_sim != null and duel_id == _pvp_duel_id:
		_pvp_sim.apply_view(view)


func _mp_open_pvp_board(view: Dictionary) -> void:
	_mp_invite_panel.visible = false
	_mp_invite = {}
	_pvp_duel_id = str(view.get("duel_id", ""))
	_pvp_sim = NetDuelSim.new(_sim, view)
	var board = GameBoardScene.instantiate()
	if not board.has_method("configure_from_network"):
		push_error("GameBoard missing configure_from_network")
		board.queue_free()
		return
	var request := {"lease_id": _pvp_duel_id, "duel_id": _pvp_duel_id, "kind": "pvp_ward_duel", "encounter": view.get("encounter", {}),
		"bot_seed": 0, "checkpoint": {}, "forced_defeat_by_cast": 0}
	board.configure_from_network(request, _pvp_sim, Callable(self, "_on_pvp_board_finished"))
	_pvp_board = board
	_duel_open = true
	_input_locked = true
	_held_dir = Vector2i.ZERO
	_touch.set_enabled(false)
	_duel_host.mouse_filter = Control.MOUSE_FILTER_STOP
	_duel_host.add_child(board)
	if board is Control:
		board.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_mp_toast_show("Ward duel with %s" % str(view.get("rival", {}).get("name", "a wizard")))


func _on_pvp_board_finished(outcome: String, _details: Dictionary) -> void:
	_pvp_last_outcome = outcome
	_sim.op({"op": "pvp_leave"})
	_mp_close_pvp_board(outcome)


func _mp_close_pvp_board(outcome: String) -> void:
	if _pvp_board != null and is_instance_valid(_pvp_board):
		_pvp_board.queue_free()
	_pvp_board = null
	_pvp_sim = null
	_duel_open = false
	_input_locked = false
	_touch.set_enabled(true)
	_duel_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud_area_lbl.text = "Duel %s" % outcome
	queue_redraw()


func _mp_nearby_player() -> Dictionary:
	var best := {}
	var best_d := 99
	for pid in _mp_players:
		var row: Dictionary = _mp_players[pid]
		if not bool(row.get("connected", true)) or bool(row.get("in_duel", false)):
			continue
		var d := absi(int(row.get("tx", 0)) - _john_pos.x) + absi(int(row.get("ty", 0)) - _john_pos.y)
		if d <= 2 and d < best_d:
			best = row
			best_d = d
	return best


func _mp_update_challenge_button() -> void:
	if _mp_challenge_btn == null:
		return
	var near := _mp_nearby_player()
	_mp_challenge_btn.visible = not near.is_empty() and not _duel_open and _mp_invite.is_empty()
	if not near.is_empty():
		_mp_challenge_btn.text = "⚔ Duel %s" % str(near.get("name", ""))


func mp_challenge() -> Dictionary:
	var near := _mp_nearby_player()
	if near.is_empty():
		_mp_toast_show("Walk up to the other wizard first")
		return {}
	var reply: Dictionary = _sim.op({"op": "pvp_challenge", "target": str(near.get("id", "")), "format": "three"})
	if str(reply.get("status", "")) == "ok":
		_mp_toast_show("Challenge sent to %s…" % str(near.get("name", "")))
	else:
		_mp_toast_show("Cannot challenge: %s" % str(reply.get("reason", "")))
	return reply


func mp_respond(accept: bool) -> Dictionary:
	if _mp_invite.is_empty():
		return {}
	var reply: Dictionary = _sim.op({"op": "pvp_respond", "duel_id": str(_mp_invite.get("duel_id", "")), "accept": accept})
	_mp_invite = {}
	_mp_invite_panel.visible = false
	if accept and str(reply.get("status", "")) == "ok":
		_mp_handle_duel(reply.get("duel", {}))
	elif accept:
		_mp_toast_show("Could not accept: %s" % str(reply.get("reason", "")))
	return reply


func _mp_notice(n: Dictionary) -> void:
	var who := str(n.get("name", n.get("by_name", "")))
	match str(n.get("kind", "")):
		"player_joined":
			_mp_toast_show("%s joined the world" % who)
		"player_left":
			_mp_toast_show("%s lost connection" % who)
		"player_reconnected":
			_mp_toast_show("%s is back" % who)
		"declined":
			_mp_toast_show("%s declined the duel" % who)
		"accepted":
			_mp_toast_show("%s accepted!" % who)
		"invite_expired":
			_mp_toast_show("No answer to your challenge")
		"cycle_reset":
			_mp_toast_show("A new cycle begins")


func _mp_toast_show(text: String) -> void:
	if _mp_toast == null:
		return
	_mp_toast.text = text
	_mp_toast.visible = true
	_mp_toast_t = 3.0


func _mp_status_text(reply: Dictionary) -> String:
	var online := int(reply.get("players_online", 0))
	var paused := bool(_snapshot.get("paused", false))
	return "LAN %s · %d online · %d ms%s" % ["host" if LanSession.is_host else "joined", online, _sim.last_round_trip_ms, "  ·  PAUSED" if paused else ""]


func _mp_key(keycode: int) -> bool:
	if _duel_open:
		return false
	match keycode:
		KEY_C:
			mp_challenge()
			return true
		KEY_Y:
			if not _mp_invite.is_empty():
				mp_respond(true)
				return true
		KEY_N:
			if not _mp_invite.is_empty():
				mp_respond(false)
				return true
	return false


func _on_move_reply(reply: Dictionary) -> void:
	if str(reply.get("status", "")) == "ok":
		_mp_seq = maxi(_mp_seq, int(reply.get("seq", _mp_seq)))
		return
	var reason := str(reply.get("reason", ""))
	if reason in ["stale_seq", "disconnected", "not_connected"] or not reply.has("tx"):
		return
	# the host refused the step: snap back to the authoritative tile
	set_john_pos(Vector2i(int(reply.get("tx", _john_pos.x)), int(reply.get("ty", _john_pos.y))), str(reply.get("facing", _john_facing)))
	_mp_seq = maxi(_mp_seq, int(reply.get("seq", _mp_seq)))
	if reason == "occupied":
		_mp_toast_show("Someone is standing there")
	elif reason == "in_duel":
		pass
	else:
		_mp_toast_show("You cannot walk there")


## Test and inspection API.
func ui_mp_players() -> Dictionary:
	return _mp_players.duplicate(true)


func ui_mp_board() -> Node:
	return _pvp_board


func ui_mp_sim():
	return _pvp_sim


func ui_mp_invite() -> Dictionary:
	return _mp_invite.duplicate(true)


func ui_mp_stats() -> Dictionary:
	var secs := maxf(0.001, float(Time.get_ticks_msec() - _mp_started_ms) / 1000.0)
	return {"polls": _mp_polls, "bytes_in": _sim.bytes_in - _mp_bytes_at_start, "bytes_per_s": float(_sim.bytes_in - _mp_bytes_at_start) / secs,
		"round_trip_ms": _sim.last_round_trip_ms, "fps": Engine.get_frames_per_second(), "lost": _mp_lost, "last_outcome": _pvp_last_outcome}


## The pause menu over the LAN: nothing to save here (the host owns the world); leaving tells the host and stops a local host.
func _on_menu() -> void:
	if not mp:
		super._on_menu()
		return
	if _input_locked:
		return
	_input_locked = true
	_touch.set_enabled(false)
	var title := "LAN game — you are hosting" if LanSession.is_host else "LAN game — joined %s" % LanSession.host_address
	var choice: String = await _dialogue.choose_async(title, ["Continue", "Leave game"])
	if choice == "Leave game":
		mp_leave()
		return
	_input_locked = false
	_touch.set_enabled(true)


func mp_leave() -> void:
	if _sim != null and _sim.connected():
		_sim.op({"op": "leave"}, 1000)
	LanSession.stop_local_host()
	LanSession.reset()
	get_tree().change_scene_to_file("res://client/scenes/main_menu.tscn")
