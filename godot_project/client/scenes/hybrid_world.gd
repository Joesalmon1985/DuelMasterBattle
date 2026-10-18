extends Overworld

const HexCoords = preload("res://client/hybrid/hex_coords.gd")
const SimClient = preload("res://client/hybrid/sim_client.gd")
const DuelAdapter = preload("res://client/encounters/duel_lease_adapter.gd")
const HybridArt = preload("res://client/hybrid/hybrid_art.gd")
const GodMode = preload("res://client/hybrid/god_mode.gd")
const TerrainView = preload("res://client/hybrid/terrain_view.gd")
const WizardLabels = preload("res://client/hybrid/wizard_labels.gd")
const StoryUi = preload("res://client/hybrid/story_ui.gd")
const CampaignUi = preload("res://client/hybrid/campaign_ui.gd")
const TrialMode = preload("res://client/hybrid/trial_mode.gd")
const CampaignHud = preload("res://client/ui/campaign_hud.gd")
const NarrativeCard = preload("res://client/ui/narrative_card.gd")
const ResponsiveModal = preload("res://client/ui/responsive_modal.gd")
const SaveData = preload("res://client/scripts/save_data.gd")
const NetDuelSim = preload("res://client/duel/net_duel_sim.gd")
const GameBoardScene = preload("res://client/scenes/game_board.tscn")

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
var era_hud: Label  # era, victory points and cycle: the stats read-out inside the campaign HUD (shown when the HUD title is tapped)
var hud: Control  # the campaign HUD: era and cycle, the current objective, a journal button
var menu_card: Control  # the pause menu (a DmbNarrativeCard)
var campaign_ui: Node  # the opening campaign's scenes and the Game Over screen (campaign_ui.gd)
var story_ui: Node  # the wizard's story: people, dialogue, dungeon, duel (placeholders over the Python ops)
var trial_mode: Node  # the Trial of Champions: zone mode (trial_mode.gd); `trial_mode.active` is "inside"
var terrain = null  # TerrainView once the sim has sent its terrain
## Camera zoom is stored as PHYSICAL pixels per map tile (so "how close" means the same on a phone and a monitor) and converted with the stretch scale.
const ZOOM_DEFAULT_PX := 52.0
const ZOOM_MIN_PX := 26.0
const ZOOM_MAX_PX := 128.0
const ZOOM_STEP := 1.15
var zoom_px := ZOOM_DEFAULT_PX
var _touches: Dictionary = {}  # screen-touch index -> position, for the two-finger pinch
var _pinch_dist := 0.0
var _pinch_active := false
var _pinch_seen := false  # a pinch happened since the last press: that press is not a click
var _pinch_block_until := 0
var _press: Dictionary = {}  # the left press that may become a click: {"pos", "target"}
var autosave_seconds := 300.0  # real seconds of play between autosaves; the client times it, the simulation reads no wall clock (HYBRID_AUTOSAVE_SECONDS overrides)
var autosave_count := 0
var _autosave_acc := 0.0
var _menu_open := false  # the pause menu is showing
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
# ---- mortal apprentices (plan M1): the dead spectate, bodies lie in the world, resurrection is a channel beside the body, the game ends only when no human is left
var _dead_mode := false  # this wizard is dead: the avatar is hidden, the controls are off, the banner is up
var _dead_banner: Label
var _dead_info: Dictionary = {}  # the host's `you_dead`
var _watch_btn: Button  # a dead wizard may follow the survivor with the camera
var _watching := ""  # the player id the camera follows while dead ("" = stay at the body)
var _res_fx: Dictionary = {}  # the resurrection channel in progress near us: {tile, left_ms, total_ms, name}
var _res_label: Label
var _ending: Dictionary = {}  # the session has ended for the humans (every one of them dead)
var _ending_shown := false
var _pest_fx: Dictionary = {}  # a rat breaking apart beside the wizard: {tile, t}


func _ready() -> void:
	if OS.get_environment("HYBRID_AUTOSAVE_SECONDS") != "":
		autosave_seconds = maxf(1.0, float(OS.get_environment("HYBRID_AUTOSAVE_SECONDS")))
	_build_layers()
	_build_ui()
	_font = ThemeDB.fallback_font
	var adv := _adv()
	if not adv.is_active():
		adv.test_mode = true  # the old adventure's autoload is only a dependency here (spells, items): Wizard World must never write over or depend on its save file
		adv.new_game()
	area_id = "hybrid"
	area = {"id": "hybrid", "name": "Wizard RTS", "rows": ["."]}
	grid_w = 2000
	grid_h = 2000
	test_mode = true
	zoom_px = clampf(float(SaveData.get_setting("hybrid_zoom_px", ZOOM_DEFAULT_PX)), ZOOM_MIN_PX, ZOOM_MAX_PX)
	apply_zoom()
	get_viewport().size_changed.connect(apply_zoom)
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
	trial_mode = TrialMode.new()
	trial_mode.name = "TrialMode"
	add_child(trial_mode)
	trial_mode.setup(self)
	campaign_ui = CampaignUi.new()  # after the story panels: it sees the keyboard first while a scene or the Game Over screen is up
	campaign_ui.name = "CampaignUi"
	add_child(campaign_ui)
	campaign_ui.setup(self, story_ui)
	var hud_layer := CanvasLayer.new()
	hud_layer.name = "HudLayer"
	hud_layer.layer = 6
	add_child(hud_layer)
	hud = CampaignHud.new()
	hud_layer.add_child(hud)
	hud.setup(self)
	hud.journal_requested.connect(func() -> void: story_ui.set_journal_visible(not story_ui.journal.visible))
	if mp:
		hud.journal_button.visible = false  # no journal in Wizard World: if you forget what somebody asked, ask them again
	era_hud = hud.stats_label
	var menu_layer := CanvasLayer.new()
	menu_layer.name = "MenuLayer"
	menu_layer.layer = 16
	add_child(menu_layer)
	menu_card = NarrativeCard.new()
	menu_layer.add_child(menu_card)
	menu_card.setup(self, "modal", "PauseMenu")
	menu_card.choice_pressed.connect(_on_menu_choice)
	if mp:
		_mp_build_ui()
		_mp_apply(reply)
		_mp_started_ms = Time.get_ticks_msec()
		_mp_bytes_at_start = _sim.bytes_in
	if mp or OS.has_feature("mobile"):
		_touch.set_action_visible(true)  # phones: the interact button is always on
	if mp:
		_mp_build_mortality_ui()


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
	if hud != null and story_ui != null:
		hud.set_covered(story_ui.covering() or (campaign_ui != null and campaign_ui.covering()) or _duel_open or _menu_open or (god != null and god.active) or (trial_mode != null and trial_mode.covering()))
	_autosave_tick(delta)
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


## Pinch-to-zoom and click suppression. A pinch (two touches) zooms the world and can never select anything; the touches also arrive as an emulated
## mouse press for the first finger, so a press that turned into a pinch is not a click (clicks are taken on release, see _unhandled_input).
func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		if event.pressed:
			_touches[event.index] = event.position
			if _touches.size() >= 2 and not _pinch_active:
				_pinch_active = true
				_pinch_seen = true
				_press = {}
				_pinch_dist = _touch_distance()
		else:
			_touches.erase(event.index)
			if _pinch_active and _touches.size() < 2:
				_pinch_active = false
				_pinch_block_until = Time.get_ticks_msec() + 250
	elif event is InputEventScreenDrag:
		_touches[event.index] = event.position
		if _pinch_active and _touches.size() >= 2:
			var d := _touch_distance()
			if _pinch_dist > 1.0 and d > 1.0:
				zoom_by(d / _pinch_dist)
			_pinch_dist = d
			get_viewport().set_input_as_handled()
			return
	elif event is InputEventMagnifyGesture:
		zoom_by(event.factor)
		get_viewport().set_input_as_handled()
		return
	if (_pinch_active or Time.get_ticks_msec() < _pinch_block_until) and (event is InputEventMouseButton or event is InputEventMouseMotion):
		get_viewport().set_input_as_handled()


func _touch_distance() -> float:
	var pts: Array = _touches.values()
	return (pts[0] as Vector2).distance_to(pts[1] as Vector2) if pts.size() >= 2 else 0.0


func _stretch_scale() -> float:
	return float(ResponsiveModal.window_info(self)["scale"])


## Re-lay-out every narrative panel (the viewport's size_changed does it in play; a test that simulates another window size calls this).
func relayout_ui() -> void:
	for c in [hud, menu_card, wizard_labels.panel if wizard_labels != null else null, story_ui.dialog_card if story_ui != null else null,
			story_ui.opening_card if story_ui != null else null, story_ui.journal if story_ui != null else null]:
		if c != null:
			c.relayout()
	_mp_relayout()
	apply_zoom()


func apply_zoom() -> void:
	var z := zoom_px / (float(TPX) * _stretch_scale())
	_camera.zoom = Vector2(z, z)


func set_zoom_px(v: float, persist := true) -> void:
	zoom_px = clampf(v, ZOOM_MIN_PX, ZOOM_MAX_PX)
	apply_zoom()
	if persist:
		SaveData.set_setting("hybrid_zoom_px", zoom_px)


func zoom_by(factor: float) -> void:
	set_zoom_px(zoom_px * factor)


## Zoom keys and the mouse wheel only act when nothing else owns the screen (no conversation, menu, journal, duel or God Mode).
func _zoom_input_ok() -> bool:
	return not _duel_open and not _menu_open and (story_ui == null or not story_ui.covering()) and (god == null or not god.active)


func _click_target(pos: Vector2) -> String:
	if story_ui != null:
		var lm: Dictionary = story_ui.person_at(pos)
		if not lm.is_empty():
			return "landmark:" + str(lm["id"])
	if wizard_labels != null and wizard_labels.enabled:
		var e: Dictionary = wizard_labels.pick(pos)
		if not e.is_empty():
			return str(e["id"])
	return ""


func _unhandled_input(event: InputEvent) -> void:
	if _menu_open:
		if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ESCAPE:
			_close_menu()
			get_viewport().set_input_as_handled()
		return
	if mp and event is InputEventKey and event.pressed and not event.echo and _mp_key(event.keycode):
		get_viewport().set_input_as_handled()
		return
	if event is InputEventKey and event.pressed and not event.echo and _zoom_input_ok():
		if event.keycode in [KEY_PLUS, KEY_EQUAL, KEY_KP_ADD]:
			zoom_by(ZOOM_STEP)
			get_viewport().set_input_as_handled()
			return
		if event.keycode in [KEY_MINUS, KEY_KP_SUBTRACT]:
			zoom_by(1.0 / ZOOM_STEP)
			get_viewport().set_input_as_handled()
			return
	if event is InputEventMouseButton and event.pressed and _zoom_input_ok() and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
		zoom_by(ZOOM_STEP if event.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / ZOOM_STEP)
		get_viewport().set_input_as_handled()
		return
	# Wizard Mode: a left click on anything opens its inspect card. The press only remembers what is under the pointer; the click happens on release,
	# and not at all if a pinch or a drag happened in between.
	if trial_mode != null and trial_mode.active and event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed and not _duel_open:
		if trial_mode.tap(event.position):
			get_viewport().set_input_as_handled()
			return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not _duel_open and story_ui != null and not story_ui.covering():
		if event.pressed:
			_pinch_seen = false
			var target := _click_target(event.position)
			if target != "":
				_press = {"pos": event.position, "target": target}
				get_viewport().set_input_as_handled()
				return
		else:
			var had: Dictionary = _press
			_press = {}
			if not had.is_empty():
				var moved: float = (had["pos"] as Vector2).distance_to(event.position)
				if not _pinch_seen and moved < 24.0:
					var t := str(had["target"])
					if t.begins_with("landmark:"):
						for e in _snapshot.get("entities", []):
							if str(e.get("id", "")) == t.trim_prefix("landmark:"):
								story_ui.use_entity(e)
					else:
						wizard_labels.open(t)
				get_viewport().set_input_as_handled()
				return
			if wizard_labels != null and wizard_labels.panel.visible and not _pinch_seen:
				wizard_labels.close()  # a click on empty ground puts the inspect card away
	super._unhandled_input(event)


func _arrived() -> void:
	if _sim._peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return
	if trial_mode != null and trial_mode.active:
		trial_mode.arrived()
		_update_prompt()
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
	if trial_mode != null and trial_mode.active:
		return super._tile_char(_x, _y)  # a zone: the legacy area's rows (cave walls, floor, water)
	if not tile_ground(_x, _y):
		return " "
	return "."


func is_walkable(p: Vector2i) -> bool:
	if trial_mode != null and trial_mode.active:  # a zone: the legacy rule (cave walls, things standing on tiles) plus the other wizard
		return super.is_walkable(p) and not trial_mode.blocked(p)
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
	if trial_mode != null and trial_mode.active:
		trial_mode.interact()
		return
	if mp and story_ui != null:  # Wizard World's action button: the nearest person or landmark (the gate), as E does
		var near: Dictionary = story_ui.nearest_interactive()
		if not near.is_empty():
			story_ui.use_entity(near)
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


## A story Ward Duel (a lesson or a quest): the board is the retained one, hosted by the same adapter as the route hazard, over a Python lease.
## `lease` is the server's reply to the choice that began it: {"status": "started", "payload": {"public": ..., "duel": ...}}.
var _story_duel_id := ""
var _story_follow_up: Variant = null


func open_story_duel(lease: Dictionary) -> bool:
	if _duel_open:
		return false
	_story_duel_id = str(lease.get("payload", {}).get("duel", {}).get("id", ""))
	_story_follow_up = null
	_duel_open = true
	_input_locked = true
	_duel_host.mouse_filter = Control.MOUSE_FILTER_STOP
	if not _adapter.begin_from_start_reply(_duel_host, lease, Callable(self, "_cmd")):
		_duel_open = false
		_input_locked = false
		_duel_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_story_duel_id = ""
		push_error("Story duel failed to open")
		return false
	return true


## What the board saw, for the server to verify: every cast with its feedback, and the enemy's Ward (revealed by the end of a duel).
func _story_duel_report(payload: Dictionary) -> Dictionary:
	var report := {"op": "duel_resolve", "duel_id": _story_duel_id, "outcome": str(payload.get("outcome", "")),
		"player_casts": int(payload.get("player_casts", 0)), "enemy_casts": int(payload.get("enemy_casts", 0)), "history": [], "enemy_ward": []}
	var board = _adapter._board
	if board != null and is_instance_valid(board) and board.get("game") != null:
		var g = board.game
		for rec in g.player_history:
			report["history"].append({"pattern": Array(rec.pattern_by_locus), "fracture": int(rec.fracture_count), "echo": int(rec.echo_count), "broke": bool(rec.broke_ward)})
		report["enemy_ward"] = Array(g.get_enemy_ward())
	return report


func _cmd(kind: String, payload: Dictionary = {}) -> Dictionary:
	if _story_duel_id != "":
		if kind == "HazardDuelCheckpoint":
			return _sim.op({"op": "duel_checkpoint", "duel_id": _story_duel_id, "checkpoint": payload.get("checkpoint", {})})
		if kind == "ResolveHazardDuel":
			var reply: Dictionary = _sim.op(_story_duel_report(payload))
			_story_follow_up = reply.get("follow_up", null)
			_story_duel_id = ""
			var trial = reply.get("trial", null)
			if typeof(trial) == TYPE_DICTIONARY and trial_mode != null:
				trial_mode.after_duel(trial)
			var pest = reply.get("pest", null)
			if typeof(pest) == TYPE_DICTIONARY and not (pest as Dictionary).is_empty():
				if bool(pest.get("killed", false)):
					_pest_fx = {"tile": _john_pos, "t": 0.9}
					_sfx().fracture(3)
					if mp:
						_mp_toast_show("The rat breaks apart. %d left." % int(pest.get("left", 0)) if int(pest.get("left", 0)) > 0 else "The rat breaks apart. The warehouse is quiet.", 4.0)
				else:
					_sfx().denied()
					if mp:
						_mp_toast_show("It got away under the floor. You are hurt: one cast fewer next time.", 4.0)
			return reply
		return {}
	if kind != "ResolveHazardDuel":
		return {}
	return _sim.op({
		"op": "resolve",
		"duel_id": str(payload.get("duel_id", "")),
		"success": bool(payload.get("success", false)),
		"command_id": "godot:%s" % str(payload.get("duel_id", "")),
	})


## Bring the picture of the world up to date after the client stood still for a moment (a scene, a duel board): the classic server answers `snapshot`,
## a hosted world answers the same `state` poll it always does.
func refresh_snapshot() -> void:
	if mp:
		var full: Dictionary = _sim.op({"op": "state", "seq": _mp_seq}, 20000)
		if str(full.get("status", "")) == "ok":
			_apply_snapshot(full.get("snapshot", {}))
			_mp_apply(full)
		return
	_apply_snapshot(_sim.op({"op": "snapshot"}).get("snapshot", {}))


## Is there a game of one's own to save, load and restart? A private (single-player) session has; a shared world belongs to both players.
func is_solo_session() -> bool:
	return not mp or LanSession.private_session


func _on_duel_finished(outcome: String, _payload: Dictionary) -> void:
	_duel_open = false
	_input_locked = false
	_duel_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	refresh_snapshot()
	_hud_area_lbl.text = "Duel %s" % outcome
	if story_ui != null and _story_follow_up != null:
		story_ui.show_follow_up(_story_follow_up)  # the teacher answers
		_story_follow_up = null
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
	_update_hud(snap)
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
	if trial_mode != null and trial_mode.active:
		return  # a zone is tile sprites and actors (the Overworld's builders); the hex world is not drawn behind it
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
	_draw_resurrection()
	_draw_pest_fx()
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
	_adopt_world(reply)
	_hud_area_lbl.text = "Loaded (%s)" % slot
	return reply


## The Game Over screen's New game: the server replaces the world with a fresh one (the same switches as at launch), and the client starts over.
func new_game() -> bool:
	var reply: Dictionary = _sim.op({"op": "new_game"})
	if str(reply.get("status", "")) != "ok":
		return false
	_adopt_world(reply)
	_hud_area_lbl.text = "New game"
	if story_ui != null:
		story_ui.reset_for_new_game()
	return true


func _adopt_world(reply: Dictionary) -> void:
	var tview = TerrainView.new()
	if tview.load_from(reply):
		terrain = tview
	if story_ui != null:
		story_ui.close_dialog()
	if wizard_labels != null:
		wizard_labels.close()
	_art._vis.clear()
	selected_ids = {}
	_static_rows.clear()
	_solid.clear()
	_solid_tile_of.clear()
	camera_focus = Vector2.INF
	paused = false
	_input_locked = false
	_apply_snapshot(reply.get("snapshot", {}))
	_seq = int(_snapshot.get("clock_sequence", 0))
	_clock_acc = 0.0
	_place_john_from_snapshot()
	_update_john_sprite(0)
	if story_ui != null:
		story_ui.refresh()
	queue_redraw()


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
	if campaign_ui != null and campaign_ui.covering():
		return "scene"
	if _input_locked:
		return "locked"
	return ""


func _autosave_tick(delta: float) -> void:
	if _snapshot.is_empty() or not is_solo_session():
		return
	_autosave_acc += delta
	if _autosave_acc < autosave_seconds or autosave_wait_reason() != "":
		return  # not due yet, or sent at the next quiet moment
	_autosave_acc = 0.0
	if str(save_slot("auto").get("status", "")) == "ok":
		autosave_count += 1


## Escape and the menu button: Continue, Save game, Load game, Save and quit (a card of the same style as every other narrative panel).
func _on_menu() -> void:
	if mp and not LanSession.private_session:
		_mp_on_menu()  # a shared world: the host owns it. Continue or Leave, nothing to save here
		return
	if _input_locked or _duel_open or _snapshot.is_empty() or _menu_open or (campaign_ui != null and campaign_ui.covering()):
		return
	_input_locked = true
	_menu_open = true
	_touch.set_enabled(false)
	_show_menu_root("")


func _show_menu_root(note: String) -> void:
	var items: Array = [{"id": "continue", "text": "Continue", "kind": "primary"}, {"id": "save", "text": "Save game"}]
	if not mp:
		items.append({"id": "load", "text": "Load game"})  # loading swaps the world: only the classic server does that (a hosted game continues from the main menu)
		items.append({"id": "quit", "text": "Save and quit"})
	else:
		items.append({"id": "quit", "text": "Save and leave"})
	menu_card.show_card("Paused", "", note, items, [])


func _close_menu() -> void:
	_menu_open = false
	menu_card.hide_card()
	_input_locked = false
	_touch.set_enabled(true)


func _on_menu_choice(id: String) -> void:
	match id:
		"ending_leave":
			mp_leave()
			return
		"continue":
			_close_menu()
		"save":
			var r := save_slot("manual")
			_show_menu_root("Game saved." if str(r.get("status", "")) == "ok" else "The game could not be saved (%s)." % str(r.get("reason", "")))
		"load":
			var items: Array = []
			for label in SAVE_SLOTS:
				items.append({"id": "slot:" + str(SAVE_SLOTS[label]), "text": str(label)})
			items.append({"id": "back", "text": "Back"})
			menu_card.show_card("Load which save?", "", "", items, [])
		"back":
			_show_menu_root("")
		"quit":
			save_slot("quit")
			if mp:
				mp_leave()  # back to the main menu: the campaign is saved and "Continue" is waiting there
			else:
				get_tree().quit()
		_:
			if id.begins_with("slot:"):
				var r := load_slot(id.trim_prefix("slot:"))
				if str(r.get("status", "")) == "ok":
					_close_menu()
				else:
					_show_menu_root("That save cannot be loaded (%s)." % str(r.get("reason", "")))


## The HUD: era and cycle first, the current objective under it, the full read-out behind the title.
var _progress := {}  # what the journal showed last time: lessons done, quest status, notes (for the "something changed" notice)


func _notice_progress() -> void:
	if mp:
		return  # Wizard World: no "new in your journal" flashes
	var j: Dictionary = story_ui.journal_data() if story_ui != null else {}
	if j.is_empty():
		return
	var done := 0
	var last_title := ""
	for l in j.get("lessons", []):
		if bool(l.get("done", false)):
			done += 1
			last_title = str(l.get("title", ""))
	var status := ""
	var title := ""
	for q in j.get("quests", []):
		status = str(q.get("status", ""))
		title = str(q.get("title", ""))
	var notes: int = (j.get("notes", []) as Array).size()
	if not _progress.is_empty():
		if done > int(_progress["done"]):
			hud.flash("Lesson learned: %s." % last_title)
		elif status != str(_progress["status"]) and status != "":
			hud.flash({"offered": "New in your journal: %s." % title, "active": "%s: you are getting to the bottom of it." % title,
				"done": "%s is settled. It is in your journal." % title, "interrupted": "%s can no longer be settled." % title}.get(status, ""))
		elif notes > int(_progress["notes"]):
			hud.flash("A note was added to your journal.")
	_progress = {"done": done, "status": status, "notes": notes}


func reset_progress_notice() -> void:
	_progress = {}


func _update_hud(snap: Dictionary) -> void:
	if hud == null:
		return
	_notice_progress()
	var era: Dictionary = snap.get("era", {})
	var hist: Dictionary = snap.get("history", {})
	var title := "%s - Cycle %d" % [str(era.get("era", "")).capitalize(), int(hist.get("cycle", 0))] if not era.is_empty() else "Wizard RTS"
	if bool(hist.get("cycle_pending", false)):
		title += " - the cycle ends"
	hud.set_state(title, _era_text(snap), story_ui.objective_text() if (story_ui != null and not mp) else "")  # no objective line in Wizard World (plan amendment 11): people say what matters


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST and not _snapshot.is_empty() and is_solo_session():
		save_slot("quit")  # closing the window saves first
	elif what == NOTIFICATION_APPLICATION_PAUSED and not _snapshot.is_empty() and mp and LanSession.private_session and autosave_wait_reason() == "":
		save_slot("quit")  # a phone can be closed by the system once the app is in the background: the campaign is already safe

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
	_mp_status.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_mp_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_mp_status.add_theme_color_override("font_color", Color(0.75, 0.95, 1.0))
	_mp_status.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	_mp_status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_mp_status.text = "LAN"
	layer.add_child(_mp_status)
	_mp_relayout()
	get_viewport().size_changed.connect(_mp_relayout)
	_mp_toast = Label.new()
	_mp_toast.name = "LanToast"
	_mp_toast.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_mp_toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_mp_toast.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART  # an AI wizard's line is a sentence, not a word
	_mp_toast.offset_left = -330
	_mp_toast.offset_right = 330
	_mp_toast.offset_top = 250  # below the objective card, clear of the top bar
	_mp_toast.offset_bottom = 350
	_mp_toast.add_theme_font_size_override("font_size", 24)
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


## The LAN status line sits under the top bar, to the right of the campaign HUD card (never over either), sized in physical pixels like the HUD.
func _mp_relayout() -> void:
	if _mp_status == null:
		return
	var info := ResponsiveModal.window_info(self)
	var m := ResponsiveModal.metrics(info, "sheet")
	var k: float = info["k"]
	var vis: Vector2 = info["vis"]
	var margin := float(m["margin"]) * k
	var gap := float(m["gap"]) * k
	var left := margin
	if hud != null and hud.panel != null:
		left = hud.panel.position.x + hud.panel.custom_minimum_size.x + gap
	var top := 58.0 * k
	if _hud != null and is_instance_valid(_hud):
		# the bar's minimum size is known before its first layout pass; its rect only after
		var bar_bottom := maxf(_hud.get_global_rect().end.y, _hud.offset_top + _hud.get_combined_minimum_size().y)
		top = maxf(top, bar_bottom + gap)
	var font := int(round(float(m["small"]) * k * 0.95))
	_mp_status.add_theme_font_size_override("font_size", font)
	_mp_status.add_theme_constant_override("outline_size", int(round(4.0 * k)))
	_mp_status.offset_left = left - vis.x
	_mp_status.offset_right = -margin
	_mp_status.offset_top = top
	_mp_status.offset_bottom = top + float(font) * 2.6  # room for two wrapped lines on a narrow portrait window



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
	if trial_mode != null:
		var tv = reply.get("trial", {})
		trial_mode.apply(tv if typeof(tv) == TYPE_DICTIONARY else {})
	if trial_mode == null or not trial_mode.active:
		_mp_apply_players(reply.get("snapshot", {}).get("players", []))
	for n in reply.get("notices", []):
		if typeof(n) == TYPE_DICTIONARY:
			_mp_notice(n)
	_mp_apply_mortality(reply)
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
		if bool(row.get("dead", false)):  # a dead wizard is a body on the ground (an npc row the art layer draws), not a standing avatar
			_mp_players[pid] = row
			seen[pid] = true
			if actor("lan:" + pid) != null:
				remove_actor("lan:" + pid)
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
			lbl.position = Vector2(8.0 - 80.0 / maxf(node.scale.x, 0.01), -7.0)
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
	if trial_mode != null and trial_mode.active:  # inside the Trial: the wizards in this zone, on the zone's tiles
		for o in trial_mode.view.get("others", []):
			if bool(o.get("dead", false)):
				continue
			var dz := absi(int(o.get("x", 0)) - _john_pos.x) + absi(int(o.get("y", 0)) - _john_pos.y)
			if dz <= 2 and dz < best_d:
				best = {"id": str(o.get("id", o.get("seat", ""))), "name": str(o.get("name", ""))}
				best_d = dz
		return best
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
	var reply: Dictionary = _sim.op({"op": "pvp_challenge", "target": str(near.get("id", "")), "format": "auto"})  # the host picks three colours, or four once both have played three duels
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
		"ai_says":
			_mp_toast_show("%s: %s" % [who, str(n.get("text", ""))], 6.0)  # an AI wizard speaking in its own voice
		"rung":
			# the world's magic ladder reached a rung (narrative/progression.py): a card in the speaker's name, over whatever we were doing
			var gain := str(n.get("gain", "more magic"))
			var roles: Dictionary = {"mentor": "Your mentor", "mira": "Your fellow apprentice", "voice": "Your own %s" % str(n.get("name", "voice"))}
			var role: String = str(roles.get(str(n.get("speaker", "")), ""))
			var title: String = str(n.get("name", ""))
			var body := str(n.get("text", "")) + "\n\n" + ("The weave of this world: %d colours, %d slots. (%s)" % [int((n.get("colours", []) as Array).size()), int(n.get("weave", 3)), gain])
			if campaign_ui != null:
				campaign_ui.show_notice("rung", title, role, body)
			else:
				_mp_toast_show("New magic: %s" % gain, 6.0)
		"inner_voice":
			if campaign_ui != null:
				campaign_ui.show_notice("inner_voice", str(n.get("aspect", "A voice")), "says, from somewhere behind your eyes", str(n.get("text", "")))
			else:
				_mp_toast_show("%s: %s" % [str(n.get("aspect", "")), str(n.get("text", ""))], 7.0)
		"pests_noticed":
			_mp_toast_show("Rats in the Central Warehouse: %d of them. The journal has it." % int(n.get("count", 0)), 5.0)
		"pest_scorched":
			if str(n.get("seat", "")) != LanSession.player_id:
				_mp_toast_show("%s scorched the big rat; it bolts." % who, 4.0)
		"pests_scattered":
			_mp_toast_show("The warehouse is a ruin. The rats have scattered.", 5.0)
		"pest_killed":
			if str(n.get("how", "")) == "burned" and str(n.get("seat", "")) != LanSession.player_id:
				_mp_toast_show("%s burned a rat." % who, 4.0)
		"wizard_died":
			if str(n.get("seat", "")) != LanSession.player_id:
				_mp_toast_show("%s has fallen." % who, 5.0)
		"resurrection_started":
			if str(n.get("by", "")) != LanSession.player_id:
				_mp_toast_show("%s is trying to bring %s back…" % [str(n.get("by_name", "Someone")), who], 5.0)
			_sfx().ready_chime()
		"wizard_resurrected":
			_mp_toast_show("%s lives again." % who, 5.0)
			if campaign_ui != null:
				campaign_ui.flash.color = Color(0.85, 0.95, 1.0, 0.8)
			_sfx().victory()
		"resurrection_abandoned":
			if str(n.get("by", "")) == LanSession.player_id:
				_mp_toast_show("The weave slipped: stay beside the body.", 4.0)
		"conversation":
			# somebody walked up and started talking to us (the mother, usually): the same card as any conversation we open ourselves
			if story_ui != null and typeof(n.get("reply")) == TYPE_DICTIONARY and not _duel_open:
				story_ui.show_follow_up(n["reply"])
				if wizard_labels != null:
					wizard_labels.close()


func _mp_toast_show(text: String, seconds: float = 3.0) -> void:
	if _mp_toast == null:
		return
	_mp_toast.text = text
	_mp_toast.visible = true
	_mp_toast_t = seconds


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
	elif reason == "in_duel" or reason == "dead":
		pass
	elif reason == "grounded":  # the mother's words are the reason: shown as her speech, never as a system message
		_mp_toast_show("%s: %s" % [str(reply.get("name", "Your mother")), str(reply.get("line", "Not one step further."))], 6.0)
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
func _mp_on_menu() -> void:
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


# ---------------------------------------------------------------------------
# Mortal apprentices (plan M1): dead mode, the resurrection channel, the ending
# ---------------------------------------------------------------------------

func _mp_build_mortality_ui() -> void:
	var layer: CanvasLayer = get_node_or_null("LanLayer")
	if layer == null:
		return
	_dead_banner = Label.new()
	_dead_banner.name = "DeadBanner"
	_dead_banner.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_dead_banner.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_dead_banner.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_dead_banner.offset_left = -340
	_dead_banner.offset_right = 340
	_dead_banner.offset_top = 120
	_dead_banner.offset_bottom = 200
	_dead_banner.add_theme_font_size_override("font_size", 28)
	_dead_banner.add_theme_color_override("font_color", Color(0.92, 0.9, 1.0))
	_dead_banner.add_theme_color_override("font_outline_color", Color(0.05, 0.0, 0.1, 0.95))
	_dead_banner.add_theme_constant_override("outline_size", 7)
	_dead_banner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dead_banner.visible = false
	layer.add_child(_dead_banner)
	_watch_btn = Button.new()
	_watch_btn.name = "WatchButton"
	_watch_btn.text = "Watch"
	_watch_btn.focus_mode = Control.FOCUS_NONE
	_watch_btn.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_watch_btn.offset_left = -120
	_watch_btn.offset_right = 120
	_watch_btn.offset_top = 206
	_watch_btn.offset_bottom = 266
	_watch_btn.add_theme_font_size_override("font_size", 22)
	_watch_btn.add_theme_stylebox_override("normal", _VT.gem_button_style())
	_watch_btn.add_theme_stylebox_override("hover", _VT.gem_button_style())
	_watch_btn.add_theme_stylebox_override("pressed", _VT.gem_button_style(true))
	_watch_btn.add_theme_color_override("font_color", _VT.COLOR_ACCENT_GOLD)
	_watch_btn.pressed.connect(_toggle_watch)
	_watch_btn.visible = false
	layer.add_child(_watch_btn)
	_res_label = Label.new()
	_res_label.name = "ResurrectionLabel"
	_res_label.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_res_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_res_label.offset_left = -300
	_res_label.offset_right = 300
	_res_label.offset_top = -330
	_res_label.offset_bottom = -280
	_res_label.add_theme_font_size_override("font_size", 24)
	_res_label.add_theme_color_override("font_color", Color(0.8, 0.95, 1.0))
	_res_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	_res_label.add_theme_constant_override("outline_size", 6)
	_res_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_res_label.visible = false
	layer.add_child(_res_label)


func _mp_apply_mortality(reply: Dictionary) -> void:
	var dead = reply.get("you_dead", {})
	var is_dead := typeof(dead) == TYPE_DICTIONARY and not (dead as Dictionary).is_empty()
	if is_dead and not _dead_mode:
		_enter_dead_mode(dead)
	elif not is_dead and _dead_mode:
		_leave_dead_mode()
	if _dead_mode:
		_dead_info = dead
		_dead_banner.text = _dead_text()
		_watch_btn.visible = _survivor_id() != ""
		_watch_btn.text = ("Stay with your body" if _watching != "" else "Watch %s" % _survivor_name())
		if _watching != "" and _mp_players.has(_watching):
			var row: Dictionary = _mp_players[_watching]
			camera_focus = Vector2((float(row.get("tx", 0)) + 0.5) * float(TPX), (float(row.get("ty", 0)) + 0.5) * float(TPX))
		elif _watching != "":
			_watching = ""
			camera_focus = Vector2.INF
	var res = reply.get("resurrection", {})
	_res_fx = res if typeof(res) == TYPE_DICTIONARY else {}
	if _res_label != null:
		_res_label.visible = not _res_fx.is_empty()
		if _res_label.visible:
			_res_label.text = "Bringing %s back… %d" % [str(_res_fx.get("name", "")), int(ceil(float(_res_fx.get("left_ms", 0)) / 1000.0))]
	var ending = reply.get("ending", {})
	if typeof(ending) == TYPE_DICTIONARY and not (ending as Dictionary).is_empty():
		_ending = ending
		_show_ending()


func _dead_text() -> String:
	var by := str(_dead_info.get("by", ""))
	var killer := ""
	if by != "" and _mp_players.has(by):
		killer = str(_mp_players[by].get("name", ""))
	var who := _survivor_name()
	var line := "You are dead."
	if killer != "":
		line = "%s killed you." % killer
	if str(_dead_info.get("cause", "")) == "duel" and killer == "" and str(_dead_info.get("by", "")) != "":
		line = "You walked out of a duel to the death. The duel did not walk out of you."
	if who != "":
		line += "\n%s can bring you back." % who
	elif str(_dead_info.get("rescuer", "")) != "":
		line += "\n%s is coming." % str(_dead_info.get("rescuer", ""))
	else:
		line += "\nNobody is left to bring you back."
	return line


func _survivor_id() -> String:
	for pid in _mp_players:
		var row: Dictionary = _mp_players[pid]
		if not bool(row.get("dead", false)) and bool(row.get("connected", true)):
			return pid
	return ""


func _survivor_name() -> String:
	var pid := _survivor_id()
	return str(_mp_players[pid].get("name", pid)) if pid != "" else ""


func _enter_dead_mode(dead: Dictionary) -> void:
	_dead_mode = true
	_dead_info = dead
	_john.visible = false  # the body on the ground is drawn by the art layer (an npc row); the standing avatar goes
	_held_dir = Vector2i.ZERO
	_input_locked = true
	_touch.set_enabled(false)
	if story_ui != null:
		story_ui.close_dialog()
	if wizard_labels != null:
		wizard_labels.close()
	_dead_banner.visible = true
	_sfx().defeat()
	_hud_area_lbl.text = "Dead"


func _leave_dead_mode() -> void:
	_dead_mode = false
	_dead_info = {}
	_watching = ""
	camera_focus = Vector2.INF
	_john.visible = true
	_dead_banner.visible = false
	_watch_btn.visible = false
	if _ending.is_empty():
		_input_locked = false
		_touch.set_enabled(true)
	if trial_mode != null and trial_mode.active:
		trial_mode.apply(trial_mode.view)  # stood up beside the body, inside the zone
	else:
		_place_john_from_snapshot()  # the host stood us up where the body lay
	_hud_area_lbl.text = "Alive again"


func _toggle_watch() -> void:
	_watching = "" if _watching != "" else _survivor_id()


func _draw_resurrection() -> void:
	if _res_fx.is_empty() or not _res_fx.has("tile"):
		return
	var t: Array = _res_fx["tile"]
	var c := Vector2((float(t[0]) + 0.5) * float(TPX), (float(t[1]) + 0.5) * float(TPX))
	var total := maxf(1.0, float(_res_fx.get("total_ms", 6000)))
	var done := clampf(1.0 - float(_res_fx.get("left_ms", 0)) / total, 0.0, 1.0)
	var time_s := Time.get_ticks_msec() / 1000.0
	draw_arc(c, 40.0, 0.0, TAU, 40, Color(0.5, 0.8, 1.0, 0.35), 3.0)
	draw_arc(c, 40.0, -PI * 0.5, -PI * 0.5 + TAU * done, 40, Color(0.75, 0.95, 1.0, 0.95), 5.0)
	for k in 3:  # the three colours orbit the body and close in as the weave takes
		var a := time_s * 2.4 + float(k) * TAU / 3.0
		var r := 34.0 - 18.0 * done
		var col: Color = [Color(1.0, 0.45, 0.2), Color(0.4, 0.75, 1.0), Color(0.45, 0.9, 0.4)][k]
		draw_circle(c + Vector2(cos(a), sin(a)) * r, 7.0 + 3.0 * done, col)
	draw_circle(c, 6.0 + 10.0 * done, Color(1.0, 1.0, 1.0, 0.25 + 0.5 * done))


func _show_ending() -> void:
	if _ending_shown:
		return
	_ending_shown = true
	_input_locked = true
	_menu_open = true
	_touch.set_enabled(false)
	if story_ui != null:
		story_ui.close_dialog()
	if wizard_labels != null:
		wizard_labels.close()
	var kind := str(_ending.get("kind", ""))
	var title := "You died."
	var body := "Your story ends here. The world goes on without you: the village, its people and everything that happened are kept, and a new apprentice can enter it from the menu."
	if kind == "all_dead":
		title = "Both of you died."
		body = "Nobody is left to bring the other back. The world goes on without you both; it is saved as it is, and new apprentices can enter it from the menu."
	menu_card.show_card(title, "", body, [{"id": "ending_leave", "text": "Leave", "kind": "primary"}], [])


## Test and inspection API (mortality).
func ui_dead() -> bool:
	return _dead_mode


func ui_dead_info() -> Dictionary:
	return _dead_info.duplicate(true)


func ui_resurrection() -> Dictionary:
	return _res_fx.duplicate(true)


func ui_ending() -> Dictionary:
	return _ending.duplicate(true)


func ui_resurrect(target: String) -> Dictionary:
	return _sim.op({"op": "resurrect", "target": target})


func _draw_pest_fx() -> void:
	if _pest_fx.is_empty():
		return
	var t: float = float(_pest_fx.get("t", 0.0)) - get_process_delta_time()
	if t <= 0.0:
		_pest_fx = {}
		return
	_pest_fx["t"] = t
	var tile: Vector2i = _pest_fx["tile"]
	var c := Vector2((float(tile.x) + 0.5) * float(TPX), (float(tile.y) + 0.5) * float(TPX))
	var k := 1.0 - t / 0.9
	for i in 8:  # bits of shell flying off
		var a := float(i) * TAU / 8.0 + 0.4
		canvas_item_draw_bit(c + Vector2(cos(a), sin(a)) * (10.0 + 50.0 * k), 5.0 * (1.0 - k), Color(0.35, 0.33, 0.3, 1.0 - k))
	draw_circle(c, 6.0 + 30.0 * k, Color(1.0, 0.6, 0.2, 0.6 * (1.0 - k)))


func canvas_item_draw_bit(at: Vector2, r: float, col: Color) -> void:
	draw_rect(Rect2(at - Vector2(r, r), Vector2(r * 2.0, r * 2.0)), col, true)
