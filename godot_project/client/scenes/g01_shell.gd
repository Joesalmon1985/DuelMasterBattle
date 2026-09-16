extends Control

## G01 playable shell — Python owns durable world state (FX-CLOCK slice).
## Visible counters: World Turn, Game Time, current node.
## Actions: local move, observe, Travel, Wait, invalid travel, pause, save/load, bridge-fail.

const SidecarLauncher = preload("res://client/bridge/sidecar_launcher.gd")
const WorldClient = preload("res://client/bridge/world_client.gd")
const Migrated = preload("res://client/core/migrated_runtime.gd")
const ClockDriver = preload("res://client/core/clock_driver.gd")

const SAVE_SLOT := "g01_playtest"

var _launcher
var _client
var _clock
var _status: Label
var _counters: Label
var _local_lbl: Label
var _log: RichTextLabel
var _local_pos := Vector2(180, 140)
var _paused := false
var _wait_held := false
var _pending_travel := false
var _focus := true
var _pause_token := ""
var _current_node := "node:1"
var _project_root := ""
var _observe_near := false


func _ready() -> void:
	Migrated.enable()
	_build_ui()
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
		_set_status("Sidecar failed: %s — paused (no Godot sim fallback)" % started.get("error", "?"))
		_paused = true
		return
	if not _client.connect_sidecar(str(started["host"]), int(started["port"]), str(started["token"])):
		_set_status("Handshake failed — paused (no Godot sim fallback)")
		_paused = true
		return
	_refresh_view()
	_set_status("Connected to Python sidecar. Isolated save slot: %s" % SAVE_SLOT)


func _process(delta: float) -> void:
	if _paused or not _focus or _client == null:
		return
	_clock.tick_render(delta)
	_local_lbl.text = "Local position: (%.1f, %.1f)  observe=%s" % [
		_local_pos.x, _local_pos.y, "NEAR" if _observe_near else "FAR"
	]


func _build_ui() -> void:
	set_anchors_preset(PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0.10, 0.12, 0.16)
	bg.set_anchors_preset(PRESET_FULL_RECT)
	add_child(bg)

	var title := Label.new()
	title.text = "G01 FX-CLOCK — Python-backed runtime"
	title.position = Vector2(16, 8)
	title.add_theme_font_size_override("font_size", 20)
	add_child(title)

	_status = Label.new()
	_status.position = Vector2(16, 36)
	_status.size = Vector2(980, 24)
	add_child(_status)

	_counters = Label.new()
	_counters.position = Vector2(16, 64)
	_counters.size = Vector2(980, 48)
	_counters.add_theme_font_size_override("font_size", 18)
	add_child(_counters)

	_local_lbl = Label.new()
	_local_lbl.position = Vector2(16, 112)
	add_child(_local_lbl)

	var area := ColorRect.new()
	area.color = Color(0.18, 0.26, 0.20)
	area.position = Vector2(16, 140)
	area.size = Vector2(420, 300)
	area.gui_input.connect(_on_area_input)
	area.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(area)
	var hint := Label.new()
	hint.text = "Drag here = local movement only (does not change World Turn)"
	hint.position = Vector2(24, 148)
	add_child(hint)

	var row1 := HBoxContainer.new()
	row1.position = Vector2(16, 456)
	add_child(row1)
	_add_btn(row1, "Travel adjacent", _on_travel)
	_add_btn(row1, "Wait", _on_wait_press)
	_add_btn(row1, "Invalid travel", _on_invalid_travel)
	_add_btn(row1, "Observe", _on_observe)

	var row2 := HBoxContainer.new()
	row2.position = Vector2(16, 496)
	add_child(row2)
	_add_btn(row2, "Pause", _on_pause)
	_add_btn(row2, "Resume", _on_resume)
	_add_btn(row2, "Save (g01_playtest)", _on_save)
	_add_btn(row2, "Load", _on_load)
	_add_btn(row2, "Bridge fail", _on_bridge_fail)

	_log = RichTextLabel.new()
	_log.position = Vector2(460, 140)
	_log.size = Vector2(520, 400)
	_log.scroll_following = true
	add_child(_log)
	_append("Diagnostic log — World Turn / Game Time / node update above.")


func _add_btn(parent: HBoxContainer, text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.pressed.connect(cb)
	parent.add_child(b)
	return b


func _on_area_input(event: InputEvent) -> void:
	if _paused:
		return
	if event is InputEventScreenDrag:
		_local_pos += (event as InputEventScreenDrag).relative * 0.08
	elif event is InputEventMouseMotion and (event as InputEventMouseMotion).button_mask != 0:
		_local_pos += (event as InputEventMouseMotion).relative * 0.08
	_observe_near = _local_pos.distance_to(Vector2(320, 220)) < 48.0


func _refresh_view() -> void:
	if _client == null:
		return
	var view: Dictionary = _client.request_view("player")
	var player: Dictionary = view.get("player", {})
	var clock: Dictionary = view.get("clock", {})
	_current_node = str(player.get("node_id", _current_node))
	var turn := int(clock.get("turn", 0))
	var game_ms := int(clock.get("game_ms", 0))
	var paused := bool(clock.get("paused", false)) or _paused
	_counters.text = (
		"World Turn: %d    Game Time: %d ms (%.1f s)    Node: %s    paused=%s    world_version=%s"
		% [turn, game_ms, game_ms / 1000.0, _current_node, paused, view.get("world_version", 0)]
	)


func _on_clock_advance(delta_ms: int, sequence: int) -> void:
	if _paused or not _focus:
		return
	var reply: Dictionary = _client.send_command(
		"advance-%d" % sequence,
		"AdvanceGame",
		{"delta_ms": delta_ms, "clock_sequence": sequence}
	)
	if str(reply.get("status", "")) == "ACCEPTED":
		_refresh_view()


func _cmd(kind: String, payload: Dictionary) -> Dictionary:
	if _paused and kind not in ["Resume", "Load"]:
		_append("ignored while paused: %s" % kind)
		return {}
	var cid := "%s-%s" % [kind, Time.get_ticks_msec()]
	var reply: Dictionary = _client.send_command(cid, kind, payload)
	_append("%s → %s (%s)" % [kind, reply.get("status", "?"), reply.get("code", "")])
	_refresh_view()
	return reply


func _adjacent_target() -> String:
	if _current_node == "node:1":
		return "node:2"
	return "node:1"


func _on_travel() -> void:
	if _pending_travel:
		return
	_pending_travel = true
	var to_node := _adjacent_target()
	var from_node := _current_node
	_append("Travel requested %s → %s (waiting for ack; no speculative move)" % [from_node, to_node])
	var reply := _cmd("Travel", {"from_node": from_node, "to_node": to_node})
	if str(reply.get("status", "")) == "ACCEPTED":
		_append("Travel acknowledged; World Turn should +1")
	_pending_travel = false


func _on_invalid_travel() -> void:
	var reply := _cmd("Travel", {"from_node": _current_node, "to_node": "node:99"})
	if str(reply.get("status", "")) == "REJECTED":
		_append("Invalid travel rejected — node and turn unchanged")


func _on_wait_press() -> void:
	if _wait_held:
		_append("held Wait ignored (one turn per distinct press)")
		return
	_wait_held = true
	var press_id := "wait-%s-%s" % [Time.get_ticks_msec(), randi()]
	_cmd("Wait", {"current_node": _current_node, "press_id": press_id})
	# Re-arm only after button release simulation (~human release).
	await get_tree().create_timer(0.35).timeout
	_wait_held = false


func _on_observe() -> void:
	var entity := "person:near" if _observe_near else "person:far"
	var reply := _cmd("Observe", {"entity_id": entity})
	var payload: Dictionary = reply.get("payload", {})
	_append("Observe %s → known=%s label=%s" % [entity, payload.get("known", false), payload.get("label", "?")])


func _on_pause() -> void:
	var reply := _cmd("Pause", {"reason": "menu"})
	if str(reply.get("status", "")) == "ACCEPTED":
		_pause_token = str(reply.get("payload", {}).get("token", ""))
		_paused = true
		_clock.open_pause_screen()
		_append("Paused — Game Time frozen")


func _on_resume() -> void:
	var token := _pause_token if _pause_token != "" else "menu:client:1"
	var reply := _cmd("Resume", {"token": token})
	if str(reply.get("status", "")) == "ACCEPTED":
		_paused = false
		_pause_token = ""
		_clock.close_pause_screen()
		_clock.notify_focus(true)
		_append("Resumed — no catch-up backlog")


func _on_save() -> void:
	var reply := _cmd("Save", {"slot": SAVE_SLOT})
	if str(reply.get("status", "")) == "ACCEPTED":
		_append("Saved isolated slot '%s' under %s/.dmb_saves/" % [SAVE_SLOT, _project_root])


func _on_load() -> void:
	var reply := _cmd("Load", {"slot": SAVE_SLOT})
	if str(reply.get("status", "")) == "ACCEPTED":
		_paused = false
		_append("Loaded isolated slot '%s'" % SAVE_SLOT)
		_refresh_view()


func _on_bridge_fail() -> void:
	_append("Controlled bridge failure: stopping sidecar")
	if _launcher:
		_launcher.stop()
	_paused = true
	_set_status("BRIDGE FAILURE — paused; no Godot world-sim fallback. Relaunch to recover from last save.")
	_append("Recovery: close completely, relaunch play_g01.sh, press Load (slot %s)." % SAVE_SLOT)
	_refresh_view_safe()


func _refresh_view_safe() -> void:
	# After bridge fail, counters freeze at last known values.
	_counters.text = _counters.text + "  [BRIDGE DOWN]"


func _on_bridge_failed(reason: String) -> void:
	_paused = true
	_set_status("Bridge failed: %s — paused (no Godot sim fallback)" % reason)
	_append("bridge_failed: %s" % reason)


func _set_status(text: String) -> void:
	_status.text = text


func _append(text: String) -> void:
	_log.append_text(text + "\n")


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		_focus = false
		_clock.notify_focus(false)
		_append("Focus lost — Game Time frozen (no catch-up on return)")
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN:
		_focus = true
		_clock.notify_focus(true)
		_append("Focus restored — no backlog awarded")
	elif what == NOTIFICATION_WM_CLOSE_REQUEST:
		if _launcher:
			_launcher.stop()
