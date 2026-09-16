extends Control

## G01 host: playable FX-CLOCK area + HUD + collapsible diagnostics.
## Python owns durable world state via WorldClient.

const SidecarLauncher = preload("res://client/bridge/sidecar_launcher.gd")
const WorldClient = preload("res://client/bridge/world_client.gd")
const Migrated = preload("res://client/core/migrated_runtime.gd")
const ClockDriver = preload("res://client/core/clock_driver.gd")
const FxArea = preload("res://client/world/fx_clock_area.gd")
const TouchPadScript = preload("res://client/world/touch_pad.gd")

const SAVE_SLOT := "g01_playtest"

var _launcher
var _client
var _clock
var _area
var _touch
var _status: Label
var _counters: Label
var _prompt: Label
var _diag_panel: Control
var _diag_log: RichTextLabel
var _diag_open := false
var _paused := false
var _focus := true
var _wait_held := false
var _pause_token := ""
var _project_root := ""
var _pose_sync_acc := 0.0


func _ready() -> void:
	Migrated.enable()
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_build_chrome()
	_clock = ClockDriver.new()
	_clock.advance_requested.connect(_on_clock_advance)
	_launcher = SidecarLauncher.new()
	add_child(_launcher)
	_client = WorldClient.new()
	add_child(_client)
	_client.bridge_failed.connect(_on_bridge_failed)
	_project_root = ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if _project_root.ends_with("godot_project"):
		_project_root = _project_root.get_base_dir()
	var started: Dictionary = _launcher.start(_project_root)
	if not started.get("ok", false):
		_set_status("Sidecar failed — paused (no Godot sim fallback)")
		_paused = true
		return
	if not _client.connect_sidecar(str(started["host"]), int(started["port"]), str(started["token"])):
		_set_status("Handshake failed — paused (no Godot sim fallback)")
		_paused = true
		return
	_area = FxArea.new()
	$WorldHost.add_child(_area)
	_touch = TouchPadScript.new()
	add_child(_touch)
	_area.setup(_client, _touch)
	_area.exit_activated.connect(_on_exit)
	_area.request_observe.connect(_on_observe)
	_area.request_interact.connect(_on_interact)
	_area.entity_selected.connect(func(id): _prompt.text = "Selected %s — ✦ to observe/interact" % id)
	_refresh_counters()
	_set_status("Python-backed FX-CLOCK — move with pad/drag; ✦ observe/interact near targets")


func _build_chrome() -> void:
	var bg := ColorRect.new()
	bg.color = Color(0.05, 0.06, 0.09)
	bg.set_anchors_preset(PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)

	var host := Node2D.new()
	host.name = "WorldHost"
	host.position = Vector2(24, 100)
	add_child(host)

	_status = Label.new()
	_status.position = Vector2(12, 8)
	_status.size = Vector2(900, 24)
	_status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_status)

	_counters = Label.new()
	_counters.position = Vector2(12, 36)
	_counters.size = Vector2(1000, 28)
	_counters.add_theme_font_size_override("font_size", 18)
	_counters.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_counters)

	_prompt = Label.new()
	_prompt.position = Vector2(12, 68)
	_prompt.size = Vector2(900, 24)
	_prompt.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_prompt)

	var bar := HBoxContainer.new()
	bar.set_anchors_preset(PRESET_BOTTOM_WIDE)
	bar.offset_top = -110
	bar.offset_bottom = -16
	bar.offset_left = 16
	bar.offset_right = -16
	bar.add_theme_constant_override("separation", 8)
	add_child(bar)
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
	_diag_panel.offset_left = -420
	_diag_panel.offset_top = 96
	_diag_panel.offset_right = -12
	_diag_panel.offset_bottom = 420
	add_child(_diag_panel)
	var dv := VBoxContainer.new()
	_diag_panel.add_child(dv)
	var dl := Label.new()
	dl.text = "Development diagnostics (collapsible)"
	dv.add_child(dl)
	_diag_log = RichTextLabel.new()
	_diag_log.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_diag_log.custom_minimum_size = Vector2(380, 280)
	_diag_log.scroll_following = true
	dv.add_child(_diag_log)


func _btn(parent: HBoxContainer, text: String, cb: Callable) -> void:
	var b := Button.new()
	b.text = text
	b.pressed.connect(cb)
	parent.add_child(b)


func _process(delta: float) -> void:
	if _paused or not _focus or _client == null:
		return
	_clock.tick_render(delta)
	_pose_sync_acc += delta
	if _pose_sync_acc >= 0.5 and _area != null and not _area.travel_pending:
		_pose_sync_acc = 0.0
		_client.send_command(
			"pose-%s" % Time.get_ticks_msec(),
			"SyncPose",
			{"position": _area.wizard_grid(), "facing": _area._facing}
		)


func _on_clock_advance(delta_ms: int, sequence: int) -> void:
	if _paused or not _focus:
		return
	var reply: Dictionary = _client.send_command(
		"advance-%d" % sequence, "AdvanceGame", {"delta_ms": delta_ms, "clock_sequence": sequence}
	)
	if str(reply.get("status", "")) == "ACCEPTED":
		_refresh_counters()


func _cmd(kind: String, payload: Dictionary) -> Dictionary:
	if _paused and kind not in ["Resume", "Load"]:
		_log("ignored while paused: %s" % kind)
		return {}
	var reply: Dictionary = _client.send_command("%s-%s" % [kind, Time.get_ticks_msec()], kind, payload)
	_log("%s → %s" % [kind, reply.get("status", "?")])
	_refresh_counters()
	return reply


func _refresh_counters() -> void:
	if _client == null:
		return
	var view: Dictionary = _client.request_view("player")
	var clock: Dictionary = view.get("clock", {})
	var player: Dictionary = view.get("player", {})
	_counters.text = "World Turn: %s   |   Game Time: %s ms (%.1fs)   |   Node: %s   |   paused=%s" % [
		clock.get("turn", 0),
		clock.get("game_ms", 0),
		float(clock.get("game_ms", 0)) / 1000.0,
		player.get("node_id", "?"),
		bool(clock.get("paused", false)) or _paused,
	]
	if _area != null and not _area.travel_pending:
		_area.rebuild_from_view(view)


func _on_exit(to_node: String) -> void:
	var from_node := str(_client.request_view("player").get("player", {}).get("node_id", "node:1"))
	_prompt.text = "Travel pending %s → %s (waiting for acknowledgement)" % [from_node, to_node]
	var reply := _cmd("Travel", {"from_node": from_node, "to_node": to_node})
	if str(reply.get("status", "")) == "ACCEPTED":
		var view: Dictionary = _client.request_view("player")
		_area.acknowledge_travel(to_node, view)
		_prompt.text = "Travel acknowledged — World Turn +1"
	else:
		_area.reject_travel(str(reply.get("code", "rejected")))
		_prompt.text = "Travel rejected — position unchanged"


func _on_observe(entity_id: String) -> void:
	var reply := _cmd("Observe", {"entity_id": entity_id})
	var payload: Dictionary = reply.get("payload", {})
	_prompt.text = "Observed %s → %s" % [entity_id, payload.get("label", "unknown")]
	_refresh_counters()


func _on_interact(entity_id: String) -> void:
	var reply := _cmd("Interact", {"entity_id": entity_id})
	var payload: Dictionary = reply.get("payload", {})
	if str(reply.get("status", "")) == "ACCEPTED":
		_prompt.text = "Interacted: %s" % payload.get("name", payload.get("role", payload.get("label", "?")))
	else:
		_prompt.text = "Interact failed: %s" % reply.get("code", "?")
	_refresh_counters()


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
		if _touch:
			_touch.set_enabled(false)


func _on_resume() -> void:
	var token := _pause_token if _pause_token != "" else "menu:client:1"
	var reply := _cmd("Resume", {"token": token})
	if str(reply.get("status", "")) == "ACCEPTED":
		_paused = false
		_pause_token = ""
		_clock.close_pause_screen()
		_clock.notify_focus(true)
		_prompt.text = "Resumed — no catch-up"
		if _touch:
			_touch.set_enabled(true)


func _on_save() -> void:
	# Sync pose into authoritative state before save.
	_client.send_command("pose-pre-save", "SyncPose", {"position": _area.wizard_grid(), "facing": _area._facing})
	var reply := _cmd("Save", {"slot": SAVE_SLOT})
	if str(reply.get("status", "")) == "ACCEPTED":
		_prompt.text = "Saved isolated slot %s → %s/.dmb_saves/" % [SAVE_SLOT, _project_root]


func _on_load() -> void:
	var reply := _cmd("Load", {"slot": SAVE_SLOT})
	if str(reply.get("status", "")) == "ACCEPTED":
		_paused = false
		_refresh_counters()
		_prompt.text = "Loaded %s" % SAVE_SLOT


func _on_bridge_fail() -> void:
	_log("Controlled bridge failure")
	if _launcher:
		_launcher.stop()
	_paused = true
	if _touch:
		_touch.set_enabled(false)
	_set_status("BRIDGE FAILURE — paused; no Godot world-sim fallback")
	_prompt.text = "Recover: close game, relaunch, Load slot %s" % SAVE_SLOT
	_counters.text = _counters.text + "  [BRIDGE DOWN]"


func _on_bridge_failed(reason: String) -> void:
	_paused = true
	_set_status("Bridge failed: %s" % reason)
	_log("bridge_failed %s" % reason)


func _toggle_diag() -> void:
	_diag_open = not _diag_open
	_diag_panel.visible = _diag_open


func _on_back() -> void:
	if _launcher:
		_launcher.stop()
	get_tree().change_scene_to_file("res://client/scenes/main_menu.tscn")


func _set_status(t: String) -> void:
	_status.text = t


func _log(t: String) -> void:
	if _diag_log:
		_diag_log.append_text(t + "\n")


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		_focus = false
		_clock.notify_focus(false)
		_log("focus lost")
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN:
		_focus = true
		_clock.notify_focus(true)
		_log("focus restored — no backlog")
	elif what == NOTIFICATION_WM_CLOSE_REQUEST or what == NOTIFICATION_PREDELETE:
		if _launcher:
			_launcher.stop()


func _exit_tree() -> void:
	if _launcher:
		_launcher.stop()
	if _client:
		_client.queue_free()
