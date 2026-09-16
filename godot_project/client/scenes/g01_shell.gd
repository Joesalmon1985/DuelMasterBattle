extends Control

## Minimal G01 playable shell over the Python sidecar.
## One pointer: move locally, observe, Travel/Wait, pause, save/load, bridge-fail.

const SidecarLauncher = preload("res://client/bridge/sidecar_launcher.gd")
const WorldClient = preload("res://client/bridge/world_client.gd")
const Migrated = preload("res://client/core/migrated_runtime.gd")

var _launcher
var _client
var _status: Label
var _node_lbl: Label
var _turn_lbl: Label
var _log: RichTextLabel
var _local_pos := Vector2(0, 0)
var _paused := false
var _wait_armed := true
var _pending_travel := false
var _bridge_fail_btn: Button


func _ready() -> void:
	Migrated.enable()
	_build_ui()
	_launcher = SidecarLauncher.new()
	add_child(_launcher)
	_client = WorldClient.new()
	add_child(_client)
	_client.bridge_failed.connect(_on_bridge_failed)
	var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	# godot_project/ -> repo root
	if project_root.ends_with("godot_project"):
		project_root = project_root.get_base_dir()
	var started: Dictionary = _launcher.start(project_root)
	if not started.get("ok", false):
		_set_status("Sidecar failed: %s" % started.get("error", "?"))
		_paused = true
		return
	if not _client.connect_sidecar(str(started["host"]), int(started["port"]), str(started["token"])):
		_set_status("Handshake failed — paused")
		_paused = true
		return
	_refresh_view()
	_set_status("Connected. Drag to move. Use Travel/Wait.")


func _build_ui() -> void:
	set_anchors_preset(PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.color = Color(0.12, 0.14, 0.18)
	bg.set_anchors_preset(PRESET_FULL_RECT)
	add_child(bg)
	_status = Label.new()
	_status.position = Vector2(16, 12)
	_status.size = Vector2(900, 24)
	add_child(_status)
	_node_lbl = Label.new()
	_node_lbl.position = Vector2(16, 40)
	add_child(_node_lbl)
	_turn_lbl = Label.new()
	_turn_lbl.position = Vector2(16, 64)
	add_child(_turn_lbl)
	var area := ColorRect.new()
	area.color = Color(0.2, 0.28, 0.22)
	area.position = Vector2(16, 100)
	area.size = Vector2(420, 320)
	area.gui_input.connect(_on_area_input)
	area.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(area)
	var actions := HBoxContainer.new()
	actions.position = Vector2(16, 440)
	add_child(actions)
	_add_btn(actions, "Travel → node:2", _on_travel)
	_add_btn(actions, "Wait", _on_wait)
	_add_btn(actions, "Observe far", _on_observe_far)
	_add_btn(actions, "Pause", _on_pause)
	_add_btn(actions, "Resume", _on_resume)
	_add_btn(actions, "Save", _on_save)
	_add_btn(actions, "Load", _on_load)
	_bridge_fail_btn = _add_btn(actions, "Bridge fail", _on_bridge_fail)
	_log = RichTextLabel.new()
	_log.position = Vector2(460, 100)
	_log.size = Vector2(500, 360)
	add_child(_log)


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
		_local_pos += (event as InputEventScreenDrag).relative * 0.05
		_append("moved to %s" % _local_pos)
	elif event is InputEventMouseMotion and (event as InputEventMouseMotion).button_mask != 0:
		_local_pos += (event as InputEventMouseMotion).relative * 0.05


func _refresh_view() -> void:
	var view: Dictionary = _client.request_view("player")
	var player: Dictionary = view.get("player", {})
	var clock: Dictionary = view.get("clock", {})
	_node_lbl.text = "Node: %s  local=%s" % [player.get("node_id", "?"), _local_pos]
	_turn_lbl.text = "Turn: %s  game_ms: %s  version: %s" % [
		clock.get("turn", 0), clock.get("game_ms", 0), view.get("world_version", 0)
	]


func _cmd(kind: String, payload: Dictionary) -> Dictionary:
	if _paused and kind not in ["Resume", "Load"]:
		_append("ignored while paused")
		return {}
	var cid := "%s-%s" % [kind, Time.get_ticks_msec()]
	var reply: Dictionary = _client.send_command(cid, kind, payload)
	_append("%s → %s" % [kind, reply.get("status", "?")])
	_refresh_view()
	return reply


func _on_travel() -> void:
	if _pending_travel:
		return
	_pending_travel = true
	var reply := _cmd("Travel", {"from_node": "node:1", "to_node": "node:2"})
	# Speculative destination mutation is forbidden until acknowledgement.
	if str(reply.get("status", "")) == "ACCEPTED":
		_append("travel acknowledged")
	_pending_travel = false


func _on_wait() -> void:
	if not _wait_armed:
		_append("held Wait ignored")
		return
	_wait_armed = false
	_cmd("Wait", {"current_node": str(_client.request_view().get("player", {}).get("node_id", "node:1")), "press_id": "ui-wait-1"})
	# Re-arm only after release simulation: next frame.
	await get_tree().create_timer(0.05).timeout
	_wait_armed = true


func _on_observe_far() -> void:
	_cmd("Observe", {"entity_id": "person:far"})


func _on_pause() -> void:
	_cmd("Pause", {"reason": "menu"})
	_paused = true


func _on_resume() -> void:
	# Resume uses last pause token from view if present; shell sends generic token request.
	var reply := _cmd("Resume", {"token": "menu:client:1"})
	if str(reply.get("status", "")) == "ACCEPTED":
		_paused = false


func _on_save() -> void:
	_cmd("Save", {"slot": "g01"})


func _on_load() -> void:
	_cmd("Load", {"slot": "g01"})
	_paused = false


func _on_bridge_fail() -> void:
	_launcher.stop()
	_paused = true
	_set_status("Bridge failure — paused (no Godot sim fallback)")
	_append("sidecar stopped; legacy writers blocked=%s" % _client.legacy_writers_blocked())


func _on_bridge_failed(reason: String) -> void:
	_paused = true
	_set_status("Bridge failed: %s" % reason)


func _set_status(text: String) -> void:
	_status.text = text


func _append(text: String) -> void:
	_log.append_text(text + "\n")


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		if _launcher:
			_launcher.stop()
