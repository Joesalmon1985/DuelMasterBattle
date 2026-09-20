extends Control

## G05 FX-VILLAGE playable host — Python sidecar + production Overworld presentation.

const SidecarLauncher = preload("res://client/bridge/sidecar_launcher.gd")
const WorldClient = preload("res://client/bridge/world_client.gd")
const Migrated = preload("res://client/core/migrated_runtime.gd")
const VillageTestRunner = preload("res://client/scripts/village_test_runner.gd")
const OverworldScene = preload("res://client/scenes/overworld.tscn")
const DuelLeaseAdapter = preload("res://client/encounters/duel_lease_adapter.gd")

const G05_SAVE := "g05_village"

var _launcher
var _client
var _overworld: Node = null
var _boot_done := false
var _village_ready := false
var _project_root := ""
var _duel_adapter
var _duel_host: Control
var _fx_meta: Dictionary = {}
var _cmd_seq := 0
var _status: Label


func _ready() -> void:
	Migrated.enable()
	OS.set_environment("DMB_FIXTURE", "FX-VILLAGE")
	if OS.get_environment("DMB_SEED") == "":
		OS.set_environment("DMB_SEED", "505")
	if OS.get_environment("DMB_SAVE_SLOT") == "":
		OS.set_environment("DMB_SAVE_SLOT", G05_SAVE)
	set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_status = Label.new()
	_status.set_anchors_preset(PRESET_TOP_WIDE)
	_status.offset_left = 8
	_status.offset_top = 4
	_status.offset_right = -8
	_status.offset_bottom = 36
	_status.add_theme_font_size_override("font_size", 12)
	_status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_status.text = "G05 FX-VILLAGE — starting…"
	add_child(_status)
	_launcher = SidecarLauncher.new()
	add_child(_launcher)
	_client = WorldClient.new()
	add_child(_client)
	_duel_adapter = DuelLeaseAdapter.new()
	_duel_adapter.finished.connect(_on_duel_finished)
	_duel_host = Control.new()
	_duel_host.name = "DuelHost"
	_duel_host.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	_duel_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_duel_host.visible = false
	add_child(_duel_host)
	_project_root = ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if _project_root.ends_with("godot_project"):
		_project_root = _project_root.get_base_dir()
	call_deferred("_boot")


func _boot() -> void:
	var started: Dictionary = _launcher.start(_project_root)
	if not started.get("ok", false):
		_status.text = "G05 sidecar failed — no Godot sim fallback"
		return
	if not _client.connect_sidecar(str(started["host"]), int(started["port"]), str(started["token"])):
		_status.text = "G05 handshake failed"
		return
	VillageTestRunner.set_bridge_hooks(
		Callable(self, "_bridge_cmd"),
		Callable(self, "_bridge_view"),
		self
	)
	var view: Dictionary = _client.request_view("player", ["overworld_area", "fx_village", "buildings", "hazards", "items", "quests"])
	var area: Dictionary = view.get("overworld_area", {})
	if typeof(area) != TYPE_DICTIONARY or area.is_empty():
		# Frozen MappingProxy may arrive as Dictionary via JSON; retry coalesce.
		area = _coerce_dict(view.get("overworld_area"))
	if area.is_empty():
		_status.text = "G05 — overworld_area missing from Python view"
		return
	_fx_meta = _coerce_dict(view.get("fx_village"))
	if _fx_meta.is_empty():
		_fx_meta = _coerce_dict(area.get("fx_village"))
	VillageTestRunner.set_prepared_area(area, "FX-VILLAGE")
	_overworld = OverworldScene.instantiate()
	_overworld.name = "Overworld"
	add_child(_overworld)
	_status.text = "G05 FX-VILLAGE — find Mara at the quiet factory"
	_boot_done = true
	_village_ready = true
	# Keep status readable briefly then fade.
	await get_tree().create_timer(2.5).timeout
	if is_instance_valid(_status):
		_status.modulate.a = 0.55


func _coerce_dict(value) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}


func _bridge_cmd(command_id: String, kind: String, payload: Dictionary = {}) -> Dictionary:
	if _client == null:
		return {"status": "REJECTED", "code": "NO_CLIENT"}
	_cmd_seq += 1
	var cid := command_id if command_id != "" else "g05-%s-%d" % [kind, _cmd_seq]
	return _client.send_command(cid, kind, payload)


func _bridge_view(scope: String = "player", fields: Array = []) -> Dictionary:
	if _client == null:
		return {}
	return _client.request_view(scope, fields)


func _cmd(kind: String, payload: Dictionary = {}) -> Dictionary:
	return _bridge_cmd("g05-%s-%d" % [kind, Time.get_ticks_msec()], kind, payload)


func reproject_from_python() -> void:
	var view: Dictionary = _bridge_view("player", ["overworld_area", "fx_village", "buildings", "hazards", "items", "quests"])
	var area: Dictionary = _coerce_dict(view.get("overworld_area"))
	if area.is_empty():
		return
	_fx_meta = _coerce_dict(view.get("fx_village"))
	if _fx_meta.is_empty():
		_fx_meta = _coerce_dict(area.get("fx_village"))
	VillageTestRunner.replace_area(area)
	if _overworld != null and _overworld.has_method("_finish_village_build"):
		var start: Array = area.get("player_start", [0, 0])
		_overworld._finish_village_build(Vector2i(int(start[0]), int(start[1])), str(area.get("player_facing", "down")))


func start_demon_challenge(cube_id: String) -> bool:
	var reply := _cmd("StartHazardDuel", {"cube_id": cube_id})
	if str(reply.get("status", "")) != "ACCEPTED":
		_status.text = "Challenge rejected: %s" % reply.get("public_feedback", reply.get("code", "?"))
		_status.modulate.a = 1.0
		return false
	_duel_host.visible = true
	_duel_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_duel_host.move_to_front()
	var ok: bool = _duel_adapter.begin_from_start_reply(_duel_host, reply, Callable(self, "_cmd"))
	if not ok:
		_duel_host.visible = false
		_status.text = "Failed to host retained GameBoard duel"
		return false
	_status.text = "Retained Ward duel — GameBoard / DmbBattleSim"
	_status.modulate.a = 1.0
	return true


func _on_duel_finished(outcome: String, payload: Dictionary) -> void:
	_duel_host.visible = false
	var status := str(payload.get("payload", {}).get("status", payload.get("status", outcome)))
	if status in ["success", "idempotent"] or outcome in ["win", "victory", "success"]:
		_status.text = "Manifestation cleared — factory route may reopen"
		_cmd("Interact", {"action": "confirm_village_quest"})
	else:
		_status.text = "Duel ended (%s)" % outcome
	_status.modulate.a = 1.0
	reproject_from_python()


func enter_sluice() -> void:
	var reply := _cmd("Interact", {"action": "enter_sluice"})
	if str(reply.get("status", "")) != "ACCEPTED":
		_status.text = str(reply.get("public_feedback", "cannot enter"))
		return
	var area: Dictionary = _coerce_dict(reply.get("payload", {}).get("area"))
	if area.is_empty():
		reproject_from_python()
		return
	VillageTestRunner.replace_area(area)
	if _overworld != null and _overworld.has_method("_finish_village_build"):
		var start: Array = area.get("player_start", [8, 9])
		_overworld._finish_village_build(Vector2i(int(start[0]), int(start[1])), "up")
	_status.text = "Sluice works — find the handle, box, receptor, gate"


func return_village() -> void:
	var reply := _cmd("Interact", {"action": "return_village"})
	if str(reply.get("status", "")) != "ACCEPTED":
		reproject_from_python()
		return
	var area: Dictionary = _coerce_dict(reply.get("payload", {}).get("area"))
	if not area.is_empty():
		VillageTestRunner.replace_area(area)
		if _overworld != null and _overworld.has_method("_finish_village_build"):
			var start: Array = area.get("player_start", [28, 32])
			_overworld._finish_village_build(Vector2i(int(start[0]), int(start[1])), "up")
	else:
		reproject_from_python()
	_status.text = "Back in the village"


func talk_to(entity_id: String) -> Dictionary:
	return _cmd("Interact", {"action": "talk", "entity_id": entity_id})


func pickup_item(item_id: String) -> Dictionary:
	return _cmd("Interact", {"action": "pickup", "item_id": item_id})


func puzzle_act(lease_id: String, mechanism_id: String, mech_action: String, lease_version: int, item_id: String = "") -> Dictionary:
	var payload := {
		"action": "puzzle_act",
		"lease_id": lease_id,
		"mechanism_id": mechanism_id,
		"mechanism_action": mech_action,
		"expected_version": lease_version,
	}
	if item_id != "":
		payload["item_id"] = item_id
	return _cmd("Interact", payload)


func fx_meta() -> Dictionary:
	return _fx_meta.duplicate(true)


func is_booted() -> bool:
	return _boot_done


func is_village_ready() -> bool:
	return _village_ready and _overworld != null and is_instance_valid(_overworld)


func overworld() -> Node:
	return _overworld


func mara_actor_id() -> String:
	return str(_fx_meta.get("mara_id", ""))


func factory_id() -> String:
	return str(_fx_meta.get("factory_id", ""))


func _exit_tree() -> void:
	VillageTestRunner.clear()
	if _launcher != null:
		_launcher.stop()
