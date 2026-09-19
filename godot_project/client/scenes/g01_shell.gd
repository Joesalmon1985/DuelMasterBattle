extends Control

## G01 host: playable FX-CLOCK area + screen-space HUD/controls.
## Python owns durable world state via WorldClient.

const SidecarLauncher = preload("res://client/bridge/sidecar_launcher.gd")
const WorldClient = preload("res://client/bridge/world_client.gd")
const Migrated = preload("res://client/core/migrated_runtime.gd")
const ClockDriver = preload("res://client/core/clock_driver.gd")
const FxArea = preload("res://client/world/fx_clock_area.gd")
const TouchPadScript = preload("res://client/world/touch_pad.gd")
const SpellbookModel = preload("res://client/ui/spellbook/spellbook_model.gd")
const SpellbookHost = preload("res://client/ui/spellbook/spellbook_host.gd")
const SpellbookBinder = preload("res://client/ui/spellbook/spellbook_gate_binder.gd")
const PeoplePresenterScript = preload("res://client/world/bridge_interaction_presenter.gd")

const SAVE_SLOT := "g01_playtest"

var _launcher
var _client
var _clock
var _area
var _touch
var _ui_layer: CanvasLayer
var _ui_root: Control
var _status: Label
var _counters: Label
var _prompt: Label
var _diag_panel: Control
var _diag_log: RichTextLabel
var _diag_open := false
var _paused := false
var _focus := true
var _bridge_down := false
var _wait_held := false
var _pause_token := ""
var _project_root := ""
var _world_host: Node2D
var _pose_sync_acc := 0.0
var _clock_inflight_id := ""
var _clock_inflight_seq := -1
var _player_refresh_id := ""
var _counters_rebuild := false
var _recovering := false
var _action_bar_scroll: ScrollContainer
var _spell_model
var _spell_host
var _spell_binder
var _classic_hud := false
var _people_presenter


func _ready() -> void:
	Migrated.enable()
	set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_build_chrome()
	_setup_spellbook()
	_clock = ClockDriver.new()
	_clock.advance_requested.connect(_on_clock_advance)
	_launcher = SidecarLauncher.new()
	add_child(_launcher)
	_client = WorldClient.new()
	add_child(_client)
	_client.bridge_failed.connect(_on_bridge_failed)
	_client.request_finished.connect(_on_client_finished)
	_project_root = ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if _project_root.ends_with("godot_project"):
		_project_root = _project_root.get_base_dir()
	var started: Dictionary = _launcher.start(_project_root)
	if not started.get("ok", false):
		_set_status("Sidecar failed — paused (no Godot sim fallback)")
		_set_interaction_blocked(true)
		if _spell_binder:
			_spell_binder.set_error("Sidecar failed")
		return
	if not _client.connect_sidecar(str(started["host"]), int(started["port"]), str(started["token"])):
		_set_status("Handshake failed — paused (no Godot sim fallback)")
		_set_interaction_blocked(true)
		if _spell_binder:
			_spell_binder.set_error("Handshake failed")
		return
	_area = FxArea.new()
	_world_host.add_child(_area)
	_touch = TouchPadScript.new()
	_ui_root.add_child(_touch)
	_area.setup(_client, _touch)
	_area.exit_activated.connect(_on_exit)
	_area.request_observe.connect(_on_observe)
	_area.request_interact.connect(_on_interact)
	_area.entity_selected.connect(func(id): _prompt.text = "Selected %s" % id; _sync_spell_live())
	_area.action_hint_changed.connect(func(hint): _prompt.text = "Action: %s" % hint; _sync_spell_live())
	_area.people_presentation_changed.connect(_on_people_presentation_changed)
	_people_presenter = PeoplePresenterScript.new()
	_ui_root.add_child(_people_presenter)
	_people_presenter.setup(_ui_root, null, Callable(self, "_cmd"))
	_fit_world_host()
	_refresh_counters(false)
	_apply_movement_gate()
	_set_status("Python-backed FX-CLOCK — pad/drag to move; action button shows Observe/Interact/Travel")
	if _spell_binder:
		_spell_binder.set_ready()
		_sync_spell_live()
	_apply_classic_hud_visibility()


func _build_chrome() -> void:
	var bg := ColorRect.new()
	bg.color = Color(0.05, 0.06, 0.09)
	bg.set_anchors_preset(PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)

	_world_host = Node2D.new()
	_world_host.name = "WorldHost"
	add_child(_world_host)

	_ui_layer = CanvasLayer.new()
	_ui_layer.layer = 20
	_ui_layer.name = "UILayer"
	add_child(_ui_layer)

	_ui_root = Control.new()
	_ui_root.name = "UIRoot"
	_ui_root.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	_ui_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ui_layer.add_child(_ui_root)

	_status = Label.new()
	_status.set_anchors_preset(PRESET_TOP_WIDE)
	_status.offset_left = 12
	_status.offset_top = 8
	_status.offset_right = -12
	_status.offset_bottom = 32
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ui_root.add_child(_status)

	_counters = Label.new()
	_counters.set_anchors_preset(PRESET_TOP_WIDE)
	_counters.offset_left = 12
	_counters.offset_top = 34
	_counters.offset_right = -12
	_counters.offset_bottom = 62
	_counters.add_theme_font_size_override("font_size", 16)
	_counters.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_counters.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ui_root.add_child(_counters)

	_prompt = Label.new()
	_prompt.set_anchors_preset(PRESET_TOP_WIDE)
	_prompt.offset_left = 12
	_prompt.offset_top = 64
	_prompt.offset_right = -12
	_prompt.offset_bottom = 92
	_prompt.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_prompt.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ui_root.add_child(_prompt)

	var bar_scroll := ScrollContainer.new()
	bar_scroll.name = "ActionBarScroll"
	bar_scroll.set_anchors_preset(PRESET_BOTTOM_WIDE)
	bar_scroll.offset_left = 4
	bar_scroll.offset_right = -4
	bar_scroll.offset_top = -78
	bar_scroll.offset_bottom = -4
	bar_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	bar_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_ui_root.add_child(bar_scroll)
	_action_bar_scroll = bar_scroll
	var bar := HBoxContainer.new()
	bar.name = "ActionBar"
	bar.add_theme_constant_override("separation", 6)
	bar.alignment = BoxContainer.ALIGNMENT_CENTER
	bar_scroll.add_child(bar)
	_btn(bar, "Wait", _on_wait)
	_btn(bar, "Invalid exit", _on_invalid)
	_btn(bar, "Pause", _on_pause)
	_btn(bar, "Resume", _on_resume)
	_btn(bar, "Save", _on_save)
	_btn(bar, "Load", _on_load)
	_btn(bar, "Bridge fail", _on_bridge_fail)
	_btn(bar, "Dev panel", _toggle_diag)
	_btn(bar, "Menu", _on_back)

	_diag_panel = PanelContainer.new()
	_diag_panel.visible = false
	_diag_panel.set_anchors_preset(PRESET_TOP_RIGHT)
	_diag_panel.offset_left = -320
	_diag_panel.offset_top = 96
	_diag_panel.offset_right = -8
	_diag_panel.offset_bottom = 360
	_ui_root.add_child(_diag_panel)
	var dv := VBoxContainer.new()
	_diag_panel.add_child(dv)
	var dl := Label.new()
	dl.text = "Development diagnostics (collapsible)"
	dv.add_child(dl)
	_diag_log = RichTextLabel.new()
	_diag_log.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_diag_log.custom_minimum_size = Vector2(260, 200)
	_diag_log.scroll_following = true
	_diag_log.fit_content = false
	dv.add_child(_diag_log)


func _setup_spellbook() -> void:
	_spell_model = SpellbookModel.new()
	_spell_binder = SpellbookBinder.new()
	_spell_binder.setup(_spell_model, "g01", "G01 Spellbook")
	_configure_spellbook()
	_spell_host = SpellbookHost.new()
	_spell_host.name = "SpellbookHost"
	_ui_root.add_child(_spell_host)
	_spell_host.bind_model(_spell_model)
	_spell_host.action_requested.connect(_on_spell_action)
	_spell_host.exit_menu_requested.connect(_on_back)
	_spell_host.classic_hud_toggled.connect(_on_classic_hud_toggled)
	_spell_host.world_target_needed.connect(func(_active): _apply_movement_gate())
	_spell_model.changed.connect(func(): _apply_movement_gate())
	_apply_classic_hud_visibility()


func _configure_spellbook() -> void:
	_spell_binder.build_g01_pages()
	_spell_binder.register("wait", func(_p): return _spell_wait())
	_spell_binder.register("invalid_exit", func(_p): return _spell_invalid())
	_spell_binder.register("pause", func(_p): return _spell_pause())
	_spell_binder.register("resume", func(_p): return _spell_resume())
	_spell_binder.register("save", func(_p): return _spell_save())
	_spell_binder.register("load", func(_p): return _spell_load())
	_spell_binder.register("bridge_fail", func(_p): return _spell_bridge_fail())
	_spell_binder.register("toggle_diag", func(_p): _toggle_diag(); return {"status": "OK", "message": "Dev panel %s" % ("open" if _diag_open else "closed")})


func _on_spell_action(action_id: String, payload: Dictionary, token: String) -> void:
	_spell_binder.handle_action(action_id, payload, token)
	_sync_spell_live()


func _on_classic_hud_toggled(enabled: bool) -> void:
	_classic_hud = enabled
	_apply_classic_hud_visibility()


func _apply_classic_hud_visibility() -> void:
	if _action_bar_scroll:
		_action_bar_scroll.visible = _classic_hud
	_apply_mode_chrome_visibility()


func _apply_mode_chrome_visibility() -> void:
	pass


func _sync_spell_live() -> void:
	if _spell_binder == null:
		return
	_spell_binder.sync_live(
		_status.text if _status else "",
		_counters.text if _counters else "",
		_prompt.text if _prompt else "",
		_paused or _bridge_down
	)


func _spell_wait() -> Dictionary:
	if _wait_held:
		_prompt.text = "Hold ignored — one Wait per distinct press"
		_sync_spell_live()
		return {"status": "REJECTED", "message": _prompt.text}
	_wait_held = true
	var node := str(_client.request_view("player").get("player", {}).get("node_id", "node:1"))
	var reply := _cmd("Wait", {"current_node": node, "press_id": "wait-%s" % Time.get_ticks_msec()})
	_prompt.text = "Wait accepted — World Turn +1" if str(reply.get("status", "")) == "ACCEPTED" else "Wait %s" % reply.get("status", "?")
	_sync_spell_live()
	get_tree().create_timer(0.4).timeout.connect(func(): _wait_held = false)
	return {"status": reply.get("status", "?"), "message": _prompt.text}


func _spell_invalid() -> Dictionary:
	var node := str(_client.request_view("player").get("player", {}).get("node_id", "node:1"))
	var reply := _cmd("Travel", {"from_node": node, "to_node": "node:99"})
	if str(reply.get("status", "")) == "REJECTED":
		_prompt.text = "Invalid travel rejected — node/turn unchanged"
	else:
		_prompt.text = "Unexpected status %s" % reply.get("status", "?")
	_sync_spell_live()
	return {"status": reply.get("status", "?"), "message": _prompt.text}


func _spell_pause() -> Dictionary:
	var reply := _cmd("Pause", {"reason": "menu"})
	if str(reply.get("status", "")) == "ACCEPTED":
		_pause_token = str(reply.get("payload", {}).get("token", ""))
		_paused = true
		_clock.open_pause_screen()
		_prompt.text = "Paused — Game Time frozen"
		_apply_movement_gate()
	_sync_spell_live()
	return {"status": reply.get("status", "?"), "message": _prompt.text}


func _spell_resume() -> Dictionary:
	var token := _pause_token if _pause_token != "" else "menu:client:1"
	var reply := _cmd("Resume", {"token": token})
	if str(reply.get("status", "")) == "ACCEPTED":
		_paused = false
		_pause_token = ""
		_clock.close_pause_screen()
		_clock.notify_focus(true)
		_prompt.text = "Resumed — no catch-up"
		_apply_movement_gate()
	_sync_spell_live()
	return {"status": reply.get("status", "?"), "message": _prompt.text}


func _spell_save() -> Dictionary:
	_sync_pose()
	var reply := _cmd("Save", {"slot": SAVE_SLOT})
	if str(reply.get("status", "")) == "ACCEPTED":
		_prompt.text = "Saved isolated slot %s → %s/.dmb_saves/" % [SAVE_SLOT, _project_root]
	_sync_spell_live()
	return {"status": reply.get("status", "?"), "message": _prompt.text}


func _spell_load() -> Dictionary:
	var reply := _cmd("Load", {"slot": SAVE_SLOT})
	if str(reply.get("status", "")) == "ACCEPTED":
		_paused = false
		_pause_token = ""
		_bridge_down = false
		_clock.close_pause_screen()
		_clock.notify_focus(true)
		_refresh_counters(true)
		_apply_movement_gate()
		_prompt.text = "Loaded %s" % SAVE_SLOT
	_sync_spell_live()
	return {"status": reply.get("status", "?"), "message": _prompt.text}


func _spell_bridge_fail() -> Dictionary:
	_on_bridge_fail()
	_sync_spell_live()
	return {"status": "OK", "message": _prompt.text}


func _fit_world_host() -> void:
	if _world_host == null or _area == null:
		return
	var vp := get_viewport_rect().size
	if vp.x < 32 or vp.y < 32:
		return
	var top_reserve := 96.0
	var bottom_reserve := 190.0
	if vp.y < 700:
		bottom_reserve = 175.0
	if vp.y < 520:
		top_reserve = 84.0
		bottom_reserve = 160.0
	# Prefer filling width on landscape; leave a little breathing room for pads.
	var side_pad := 16.0 if vp.x >= 900.0 else 8.0
	var avail := Vector2(max(64.0, vp.x - side_pad * 2.0), max(64.0, vp.y - top_reserve - bottom_reserve))
	var world: Vector2 = _area.world_pixel_size()
	var s := minf(avail.x / world.x, avail.y / world.y)
	s = clampf(s, 0.28, 1.6)
	_world_host.scale = Vector2(s, s)
	_world_host.position = Vector2(
		(vp.x - world.x * s) * 0.5,
		top_reserve + max(0.0, (avail.y - world.y * s) * 0.35)
	)


func _btn(parent: HBoxContainer, text: String, cb: Callable) -> void:
	var b := Button.new()
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.pressed.connect(cb)
	parent.add_child(b)


func _apply_movement_gate() -> void:
	var book_blocks: bool = _spell_host != null and _spell_host.is_blocking_world()
	var allow: bool = not _paused and _focus and not _bridge_down and _client != null and not book_blocks
	if _area:
		_area.set_movement_enabled(allow)
	if _touch:
		var targeting: bool = _spell_host != null and _spell_host.is_targeting()
		_touch.set_enabled(allow and not targeting)


func _set_interaction_blocked(blocked: bool) -> void:
	_paused = blocked
	_bridge_down = blocked or _bridge_down
	_apply_movement_gate()


func _sync_pose() -> void:
	if _client == null or _area == null or _area.travel_pending:
		return
	_client.enqueue_command(
		"pose-%s" % Time.get_ticks_msec(),
		"SyncPose",
		{
			"position": _area.wizard_grid(),
			"facing": _area._facing,
			"node_id": _area.current_node,
			"pose_generation": _area.pose_generation,
		},
		{"replaceable": true, "coalesce_key": "SyncPose"}
	)


func _process(delta: float) -> void:
	if _paused or not _focus or _bridge_down or _client == null:
		return
	_clock.tick_render(delta)
	_pump_clock()
	_pose_sync_acc += delta
	if _pose_sync_acc >= 0.5 and _area != null and not _area.travel_pending:
		_pose_sync_acc = 0.0
		_sync_pose()


func _pump_clock() -> void:
	if _clock_inflight_id != "":
		return
	var step: Dictionary = _clock.peek_pending()
	if step.is_empty():
		return
	var sequence := int(step.get("clock_sequence", 0))
	var delta_ms := int(step.get("delta_ms", 100))
	_clock_inflight_seq = sequence
	_clock_inflight_id = _client.enqueue_command(
		"advance-%d" % sequence,
		"AdvanceGame",
		{"delta_ms": delta_ms, "clock_sequence": sequence},
		{"replaceable": false, "coalesce_key": ""}
	)


func _on_clock_advance(_delta_ms: int, _sequence: int) -> void:
	pass


func _on_client_finished(request_id: String, reply: Dictionary) -> void:
	if request_id == _clock_inflight_id:
		var seq := _clock_inflight_seq
		_clock_inflight_id = ""
		_clock_inflight_seq = -1
		_clock.ack_pending(seq)
		if str(reply.get("status", "")) == "ACCEPTED":
			_apply_cached_counters(false)
			_request_player_view(false)
		_pump_clock()
		return
	if request_id == _player_refresh_id:
		_player_refresh_id = ""
		if str(reply.get("status", "")) == "ACCEPTED":
			_apply_view_to_counters(reply.get("view", {}), _counters_rebuild)
			_counters_rebuild = false


func _cmd(kind: String, payload: Dictionary) -> Dictionary:
	if _bridge_down and kind not in ["Load"]:
		_log("ignored while bridge down: %s" % kind)
		return {}
	if _paused and kind not in ["Resume", "Load", "Save"]:
		_log("ignored while paused: %s" % kind)
		return {}
	var reply: Dictionary = _client.send_command("%s-%s" % [kind, Time.get_ticks_msec()], kind, payload)
	_log("%s → %s" % [kind, reply.get("status", "?")])
	_request_player_view(false)
	return reply


func _request_player_view(rebuild_world: bool) -> void:
	if _client == null:
		return
	_counters_rebuild = rebuild_world or _counters_rebuild
	_player_refresh_id = _client.enqueue_view(
		"player",
		[],
		{"replaceable": true, "coalesce_key": "view:player"}
	)


func _refresh_counters(rebuild_world: bool) -> void:
	if _client == null:
		return
	if _client.has_player_cache():
		_apply_view_to_counters(_client.cached_player_view(), rebuild_world)
	_request_player_view(rebuild_world)


func _apply_cached_counters(rebuild_world: bool) -> void:
	if _client != null and _client.has_player_cache():
		_apply_view_to_counters(_client.cached_player_view(), rebuild_world)


func _apply_view_to_counters(view: Dictionary, rebuild_world: bool) -> void:
	if view.is_empty():
		return
	var clock: Dictionary = view.get("clock", {})
	var player: Dictionary = view.get("player", {})
	_counters.text = "World Turn: %s   |   Game Time: %s ms (%.1fs)   |   Node: %s   |   paused=%s" % [
		clock.get("turn", 0),
		clock.get("game_ms", 0),
		float(clock.get("game_ms", 0)) / 1000.0,
		player.get("node_id", "?"),
		bool(clock.get("paused", false)) or _paused,
	]
	_sync_spell_live()
	if _area == null or _area.travel_pending:
		return
	if rebuild_world:
		_area.rebuild_from_view(view)
	else:
		_area.apply_projections(view)


func _on_exit(to_node: String) -> void:
	var from_node := "node:1"
	if _client.has_player_cache():
		from_node = str(_client.cached_player_view().get("player", {}).get("node_id", from_node))
	else:
		from_node = str(_client.request_view("player").get("player", {}).get("node_id", "node:1"))
	_prompt.text = "Travel pending %s → %s (waiting for acknowledgement)" % [from_node, to_node]
	_sync_pose()
	var reply := _cmd("Travel", {"from_node": from_node, "to_node": to_node})
	if str(reply.get("status", "")) == "ACCEPTED":
		var view: Dictionary = _client.request_view("player")
		_area.acknowledge_travel(to_node, view)
		_prompt.text = "Travel acknowledged — arrived %s facing %s" % [
			view.get("player", {}).get("position", []),
			view.get("player", {}).get("facing", "?"),
		]
		_refresh_counters(false)
	else:
		_area.reject_travel(str(reply.get("code", reply.get("public_feedback", "rejected"))))
		_prompt.text = "Travel rejected — stayed in %s (%s)" % [from_node, reply.get("code", "?")]


func _on_observe(entity_id: String) -> void:
	var reply := _cmd("Observe", {"entity_id": entity_id})
	var payload: Dictionary = reply.get("payload", {})
	_prompt.text = "Observed %s → %s" % [entity_id, payload.get("label", "unknown")]
	var anchor = _area.selectable_actor(entity_id) if _area else null
	if _people_presenter != null and anchor != null:
		_people_presenter.show_observation(entity_id, anchor, payload)
	_refresh_counters(false)


func _on_interact(entity_id: String) -> void:
	var reply := _cmd("Interact", {"entity_id": entity_id})
	var payload: Dictionary = reply.get("payload", {})
	if str(reply.get("status", "")) == "ACCEPTED":
		var name := str(payload.get("name", payload.get("role", payload.get("label", "?"))))
		_prompt.text = "Interacted: %s" % name
		var anchor = _area.selectable_actor(entity_id) if _area else null
		if _people_presenter != null and anchor != null:
			var lines: Array = payload.get("lines", [])
			if typeof(lines) != TYPE_ARRAY or lines.is_empty():
				lines = ["Hello. I'm %s." % name]
			_people_presenter.begin_talk(entity_id, anchor, lines, payload.get("responses", []))
			var lbl = _people_presenter.label_for(entity_id)
			if lbl != null:
				lbl.set_bridge_view({
					"known": true,
					"name": name,
					"label": name,
					"description": str(payload.get("description", "")),
				})
	else:
		_prompt.text = "Interact failed: %s" % reply.get("code", "?")
	_refresh_counters(false)


func _on_people_presentation_changed(people: Dictionary) -> void:
	if _people_presenter == null or _area == null:
		return
	_people_presenter.sync_people(people, _area)


func _on_wait() -> void:
	if _wait_held:
		_log("held Wait ignored")
		_prompt.text = "Hold ignored — one Wait per distinct press"
		return
	_wait_held = true
	var node := str(_client.request_view("player").get("player", {}).get("node_id", "node:1"))
	_cmd("Wait", {"current_node": node, "press_id": "wait-%s" % Time.get_ticks_msec()})
	_prompt.text = "Wait accepted — World Turn +1"
	await get_tree().create_timer(0.4).timeout
	_wait_held = false


func _on_invalid() -> void:
	var node := str(_client.request_view("player").get("player", {}).get("node_id", "node:1"))
	var reply := _cmd("Travel", {"from_node": node, "to_node": "node:99"})
	if str(reply.get("status", "")) == "REJECTED":
		_prompt.text = "Invalid travel rejected — node/turn unchanged"


func _on_pause() -> void:
	var reply := _cmd("Pause", {"reason": "menu"})
	if str(reply.get("status", "")) == "ACCEPTED":
		_pause_token = str(reply.get("payload", {}).get("token", ""))
		_paused = true
		_clock.open_pause_screen()
		_prompt.text = "Paused — Game Time frozen"
		_apply_movement_gate()


func _on_resume() -> void:
	var token := _pause_token if _pause_token != "" else "menu:client:1"
	var reply := _cmd("Resume", {"token": token})
	if str(reply.get("status", "")) == "ACCEPTED":
		_paused = false
		_pause_token = ""
		_clock.close_pause_screen()
		_clock.notify_focus(true)
		_prompt.text = "Resumed — no catch-up"
		_apply_movement_gate()


func _on_save() -> void:
	_sync_pose()
	var reply := _cmd("Save", {"slot": SAVE_SLOT})
	if str(reply.get("status", "")) == "ACCEPTED":
		_prompt.text = "Saved isolated slot %s → %s/.dmb_saves/" % [SAVE_SLOT, _project_root]


func _on_load() -> void:
	var reply := _cmd("Load", {"slot": SAVE_SLOT})
	if str(reply.get("status", "")) == "ACCEPTED":
		_paused = false
		_pause_token = ""
		_bridge_down = false
		_clock.close_pause_screen()
		_clock.notify_focus(true)
		_refresh_counters(true)
		_apply_movement_gate()
		_prompt.text = "Loaded %s" % SAVE_SLOT


func _on_bridge_fail() -> void:
	_log("Controlled bridge failure — writing recovery then restarting")
	_sync_pose()
	# Ensure a recovery checkpoint exists before killing the sidecar.
	_client.send_command("save-pre-fail", "Save", {"slot": "_recovery"})
	if _launcher:
		_launcher.stop()
	_bridge_down = true
	_paused = true
	_apply_movement_gate()
	_set_status("BRIDGE FAILURE — recovering from checkpoint…")
	var recovered := _attempt_bridge_recovery()
	if recovered.get("ok", false):
		_bridge_down = false
		_paused = false
		_apply_movement_gate()
		_refresh_counters(true)
		var roll := int(recovered.get("rollback_ms", 0))
		_prompt.text = "Recovered from checkpoint (rollback %s ms). Progress since checkpoint was not kept." % roll
		_set_status("Python-backed FX-CLOCK — recovered after bridge failure")
	else:
		_prompt.text = "Recovery failed (%s). Use Load on slot %s after relaunch." % [
			recovered.get("error", "?"), SAVE_SLOT
		]
		_counters.text = _counters.text + "  [BRIDGE DOWN]"


func _attempt_bridge_recovery() -> Dictionary:
	if _recovering:
		return {"ok": false, "error": "recovery_reentry"}
	_recovering = true
	if _launcher == null:
		_recovering = false
		return {"ok": false, "error": "no_launcher"}
	var started: Dictionary = _launcher.start(_project_root)
	if not started.get("ok", false):
		_recovering = false
		return {"ok": false, "error": "sidecar_restart"}
	if _client != null:
		if _client.bridge_failed.is_connected(_on_bridge_failed):
			_client.bridge_failed.disconnect(_on_bridge_failed)
		_client.queue_free()
	_client = WorldClient.new()
	add_child(_client)
	_client.request_finished.connect(_on_client_finished)
	_clock_inflight_id = ""
	_player_refresh_id = ""
	if not _client.connect_sidecar(str(started["host"]), int(started["port"]), str(started["token"])):
		_client.bridge_failed.connect(_on_bridge_failed)
		_recovering = false
		return {"ok": false, "error": "handshake"}
	var reply: Dictionary = _client.send_command("recover-1", "RecoverCheckpoint", {})
	if str(reply.get("status", "")) != "ACCEPTED":
		reply = _client.send_command("recover-load", "Load", {"slot": "_recovery"})
		if str(reply.get("status", "")) != "ACCEPTED":
			_client.bridge_failed.connect(_on_bridge_failed)
			_recovering = false
			return {"ok": false, "error": str(reply.get("code", "recover_failed"))}
	_client.bridge_failed.connect(_on_bridge_failed)
	_recovering = false
	var payload: Dictionary = reply.get("payload", {})
	return {"ok": true, "rollback_ms": int(payload.get("rollback_ms", 0)), "payload": payload}


func _on_bridge_failed(reason: String) -> void:
	if _recovering:
		_log("bridge_failed during recovery ignored: %s" % reason)
		return
	_bridge_down = true
	_paused = true
	_apply_movement_gate()
	_set_status("Bridge failed: %s — attempting checkpoint recovery" % reason)
	_log("bridge_failed %s" % reason)
	var recovered := _attempt_bridge_recovery()
	if recovered.get("ok", false):
		_bridge_down = false
		_paused = false
		_apply_movement_gate()
		_refresh_counters(true)
		_prompt.text = "Auto-recovered (rollback %s ms)" % int(recovered.get("rollback_ms", 0))
		_set_status("Python-backed FX-CLOCK — recovered")
	else:
		_prompt.text = "Auto-recovery failed (%s)" % recovered.get("error", "?")


func _toggle_diag() -> void:
	_diag_open = not _diag_open
	_diag_panel.visible = _diag_open


func _on_back() -> void:
	if _launcher:
		_launcher.stop()
	get_tree().change_scene_to_file("res://client/scenes/main_menu.tscn")


func _set_status(t: String) -> void:
	_status.text = t
	_sync_spell_live()


func _log(t: String) -> void:
	if _diag_log:
		_diag_log.append_text(t + "\n")
	if _spell_binder:
		_spell_binder.append_log(t)


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		_focus = false
		_clock.notify_focus(false)
		_apply_movement_gate()
		_log("focus lost")
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN:
		_focus = true
		_clock.notify_focus(true)
		_apply_movement_gate()
		_log("focus restored — no backlog")
	elif what == NOTIFICATION_WM_CLOSE_REQUEST or what == NOTIFICATION_PREDELETE:
		if _launcher:
			_launcher.stop()
	elif what == NOTIFICATION_RESIZED:
		_fit_world_host()
		_layout_diag()


func _layout_diag() -> void:
	if _diag_panel == null:
		return
	var w := get_viewport_rect().size.x
	_diag_panel.offset_left = -min(420.0, max(220.0, w * 0.55))


func _force_playable_focus() -> void:
	_focus = true
	_bridge_down = false
	if not _paused:
		_apply_movement_gate()
	_fit_world_host()


func _exit_tree() -> void:
	if _launcher:
		_launcher.stop()
	if _client:
		_client.queue_free()
