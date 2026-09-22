extends Control

## G05 full Prehistoric world — Overworld hosts G01–G04 presentation layers.

const SidecarLauncher = preload("res://client/bridge/sidecar_launcher.gd")
const WorldClient = preload("res://client/bridge/world_client.gd")
const Migrated = preload("res://client/core/migrated_runtime.gd")
const ClockDriver = preload("res://client/core/clock_driver.gd")
const VillageTestRunner = preload("res://client/scripts/village_test_runner.gd")
const OverworldScene = preload("res://client/scenes/overworld.tscn")
const DuelLeaseAdapter = preload("res://client/encounters/duel_lease_adapter.gd")
const WorkerControllerScript = preload("res://client/world/worker_controller.gd")
const WorldLayerPresenters = preload("res://client/world/world_layer_presenters.gd")
const WorldMapPanel = preload("res://client/ui/world_map_panel.gd")

const LocalBattle = preload("res://client/combat/local_battle.gd")
const EncounterHost = preload("res://client/encounters/encounter_host.gd")

const G05_SAVE := "g05_village"
const INDUSTRY_FIELDS := [
	"overworld_area", "fx_village", "fx_industry", "industry", "buildings",
	"industry_workers", "industry_connections", "industry_factories",
	"hazards", "items", "units", "carts", "orders", "player", "clock",
	"presentation", "battles", "world_map",
]

var _launcher
var _client
var _clock
var _overworld: Node = null
var _workers
var _layers
var _map_panel
var _time_hud: Label
var _boot_done := false
var _village_ready := false
var _project_root := ""
var _duel_adapter
var _duel_host: Control
var _fx_meta: Dictionary = {}
var _cmd_seq := 0
var _status: Label
var _paused := false
var _focus := true
var _bridge_down := false
var _pause_token := ""
var _clock_inflight_id := ""
var _clock_inflight_seq := -1
var _pose_sync_acc := 0.0
var _industry_acc := 0.0
var _last_industry: Dictionary = {}
var _game_ms_sample := 0
var _map_pause_token := ""
var _long_world := false
var _long_speed := 1
var _long_autorun := false
var _long_event_log: RichTextLabel
var _long_panel: VBoxContainer
var _battle
var _battle_host
var _spectator_node := ""
var _follow_major := false
var _last_travel_feedback := ""


func _ready() -> void:
	Migrated.enable()
	if OS.get_environment("DMB_FIXTURE") == "":
		OS.set_environment("DMB_FIXTURE", "FX-VILLAGE")
	if OS.get_environment("DMB_SEED") == "":
		OS.set_environment("DMB_SEED", "507")
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
	_status.text = "Prehistoric world — walk the board"
	add_child(_status)
	_time_hud = Label.new()
	_time_hud.set_anchors_preset(PRESET_TOP_RIGHT)
	_time_hud.offset_left = -220
	_time_hud.offset_top = 4
	_time_hud.offset_right = -8
	_time_hud.offset_bottom = 40
	_time_hud.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_time_hud.add_theme_font_size_override("font_size", 12)
	_time_hud.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_time_hud.text = "Turn — · Game Time: …"
	add_child(_time_hud)
	_clock = ClockDriver.new()
	_clock.advance_requested.connect(_on_clock_advance)
	_launcher = SidecarLauncher.new()
	add_child(_launcher)
	_client = WorldClient.new()
	add_child(_client)
	_client.request_finished.connect(_on_client_finished)
	_client.bridge_failed.connect(_on_bridge_failed)
	_duel_adapter = DuelLeaseAdapter.new()
	_duel_adapter.finished.connect(_on_duel_finished)
	_duel_host = Control.new()
	_duel_host.name = "DuelHost"
	_duel_host.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	_duel_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_duel_host.visible = false
	add_child(_duel_host)
	_map_panel = WorldMapPanel.new()
	_map_panel.name = "WorldMap"
	_map_panel.closed.connect(_on_map_closed)
	add_child(_map_panel)
	_project_root = ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if _project_root.ends_with("godot_project"):
		_project_root = _project_root.get_base_dir()
	call_deferred("_boot")


func _boot() -> void:
	var started: Dictionary = _launcher.start(_project_root)
	if not started.get("ok", false):
		_status.text = "G05 sidecar failed — no Godot sim fallback"
		_bridge_down = true
		return
	if not _client.connect_sidecar(str(started["host"]), int(started["port"]), str(started["token"])):
		_status.text = "G05 handshake failed"
		_bridge_down = true
		return
	VillageTestRunner.set_bridge_hooks(
		Callable(self, "_bridge_cmd"),
		Callable(self, "_bridge_view"),
		self
	)
	var view: Dictionary = _client.request_view("player", INDUSTRY_FIELDS)
	var area: Dictionary = _coerce_dict(view.get("overworld_area"))
	if area.is_empty():
		_status.text = "G05 — overworld_area missing from Python view"
		return
	_fx_meta = _coerce_dict(view.get("fx_village"))
	if _fx_meta.is_empty():
		_fx_meta = _coerce_dict(area.get("fx_village"))
	_last_industry = view
	var fixture_name := str(OS.get_environment("DMB_FIXTURE"))
	if fixture_name == "":
		fixture_name = "FX-VILLAGE"
	VillageTestRunner.set_prepared_area(area, fixture_name)
	_overworld = OverworldScene.instantiate()
	_overworld.name = "Overworld"
	add_child(_overworld)
	if _overworld.has_method("set_bridge_runtime"):
		_overworld.set_bridge_runtime(self)
	_workers = WorkerControllerScript.new()
	_workers.name = "WorkerController"
	# Mount under Overworld actors so y-sort/camera match.
	if _overworld.get("_actors_root") != null:
		_overworld._actors_root.add_child(_workers)
	else:
		_overworld.add_child(_workers)
	if _workers.has_signal("person_spawned"):
		_workers.person_spawned.connect(_on_worker_spawned)
		_workers.person_updated.connect(_on_worker_updated)
		_workers.person_removed.connect(_on_worker_removed)
	_layers = WorldLayerPresenters.new()
	_layers.name = "WorldLayerPresenters"
	if _overworld.get("_actors_root") != null:
		_layers.bind_host(_overworld._actors_root)
		_overworld._actors_root.add_child(_layers)
	else:
		_layers.bind_host(_overworld)
		_overworld.add_child(_layers)
	_apply_workers(view)
	_apply_world_layers(area)
	_refresh_time_hud(view)
	_long_world = str(OS.get_environment("DMB_FIXTURE")) == "FX-LONG-WORLD"
	if _long_world:
		_setup_long_world_observer()
		_status.text = "LONG-WORLD observer — fast-forward / event log (dev only)"
	else:
		_status.text = "Explore — M map · paths lead to neighbouring places"

	_boot_done = true
	_village_ready = true
	_sync_pose(true)
	await get_tree().create_timer(2.0).timeout
	if is_instance_valid(_status) and not _long_world:
		_status.modulate.a = 0.55


func _process(delta: float) -> void:
	if not _boot_done or _bridge_down or _client == null:
		return
	if _paused or not _focus:
		if _workers:
			_workers.set_frozen(true)
		return
	_clock.tick_render(delta)
	_pump_clock()
	_pose_sync_acc += delta
	if _pose_sync_acc >= 0.5:
		_pose_sync_acc = 0.0
		_sync_pose(false)
	_industry_acc += delta
	if _industry_acc >= 0.35:
		_industry_acc = 0.0
		_request_industry_view()
	if _workers != null:
		_workers.set_frozen(false)
		if _overworld != null and _overworld.get("_john") != null:
			_workers.set_wizard_world_position(_overworld._john.global_position)
		_workers.tick(delta)
		if _overworld != null and _overworld.has_method("sync_dynamic_person_poses"):
			_overworld.sync_dynamic_person_poses()
	_maybe_host_local_battle()
	if _long_world and _long_autorun:
		_long_world_tick(delta)


func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT:
		_focus = false
		if _clock:
			_clock.notify_focus(false)
	elif what == NOTIFICATION_APPLICATION_FOCUS_IN:
		_focus = true
		if _clock:
			_clock.notify_focus(true)


func _pump_clock() -> void:
	if _clock_inflight_id != "" or _duel_adapter != null and _duel_adapter.is_active():
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
			var payload: Dictionary = reply.get("payload", {})
			var clock_view: Dictionary = payload.get("clock", {})
			if clock_view.is_empty() and reply.has("view"):
				clock_view = reply.get("view", {}).get("clock", {})
			if not clock_view.is_empty():
				_game_ms_sample = int(clock_view.get("game_ms", _game_ms_sample))
			elif _client.has_player_cache():
				var cached: Dictionary = _client.cached_player_view()
				if cached.has("clock"):
					_game_ms_sample = int(cached.get("clock", {}).get("game_ms", _game_ms_sample))
		_pump_clock()
		return
	if str(reply.get("status", "")) == "ACCEPTED" and reply.has("view"):
		var v: Dictionary = reply.get("view", {})
		if v.has("industry_workers") or v.has("industry"):
			_last_industry = _client.merge_player_view(_last_industry, v, INDUSTRY_FIELDS) if _client.has_method("merge_player_view") else v
			_apply_workers(_last_industry)


func _request_industry_view() -> void:
	if _client == null or _paused:
		return
	_client.enqueue_view("economy", INDUSTRY_FIELDS, {"replaceable": true, "coalesce_key": "g05_industry"})


func _apply_workers(view: Dictionary) -> void:
	if _workers == null:
		return
	var rows: Array = view.get("industry_workers", [])
	# Only present workers on the player's current node.
	var player: Dictionary = _coerce_dict(view.get("player"))
	var node_id := str(player.get("node_id", _fx_meta.get("node_id", "")))
	if node_id != "":
		var filtered: Array = []
		for row_v in rows:
			if typeof(row_v) != TYPE_DICTIONARY:
				continue
			if str(row_v.get("node_id", node_id)) == node_id:
				filtered.append(row_v)
		rows = filtered
	_workers.apply_projection(rows)
	if _workers.has_method("draw_connections"):
		_workers.draw_connections(view.get("industry_connections", []))
	var area: Dictionary = _coerce_dict(view.get("overworld_area"))
	if area.is_empty():
		area = VillageTestRunner.get_area()
	_apply_world_layers(area)
	_refresh_time_hud(view)


func _on_worker_spawned(person_id: String, actor: Node2D, row: Dictionary) -> void:
	if _overworld != null and _overworld.has_method("register_dynamic_person"):
		_overworld.register_dynamic_person(person_id, actor, row)


func _on_worker_updated(person_id: String, actor: Node2D, row: Dictionary) -> void:
	if _overworld == null:
		return
	if _overworld.has_method("update_dynamic_person"):
		# After area rebuild, dynamic entities are wiped — re-register if needed.
		var existing: Dictionary = {}
		if _overworld.has_method("_entity_by_id"):
			existing = _overworld._entity_by_id(person_id)
		if existing.is_empty() and _overworld.has_method("register_dynamic_person"):
			_overworld.register_dynamic_person(person_id, actor, row)
		else:
			_overworld.update_dynamic_person(person_id, row)


func _on_worker_removed(person_id: String) -> void:
	if _overworld != null and _overworld.has_method("unregister_dynamic_person"):
		_overworld.unregister_dynamic_person(person_id)


func _sync_pose(force: bool = false) -> void:
	if _client == null or _overworld == null:
		return
	if _paused and not force:
		return
	var pos: Vector2i = _overworld._john_pos if "_john_pos" in _overworld else Vector2i.ZERO
	var facing := str(_overworld._john_facing) if "_john_facing" in _overworld else "down"
	var player: Dictionary = _coerce_dict(_last_industry.get("player"))
	var node_id := str(player.get("node_id", _fx_meta.get("node_id", "node:village")))
	var area_id := str(player.get("area_id", VillageTestRunner.get_area().get("id", "area.village")))
	_client.enqueue_command(
		"pose-%s" % Time.get_ticks_msec(),
		"SyncPose",
		{
			"position": [float(pos.x), float(pos.y)],
			"facing": facing,
			"node_id": node_id,
			"area_id": area_id,
		},
		{"replaceable": true, "coalesce_key": "SyncPose"}
	)


func notify_local_step() -> void:
	## Called by Overworld after a grid step in bridge mode.
	_sync_pose(false)


func acquire_pause(reason: String = "choice") -> String:
	if _pause_token != "":
		return _pause_token
	var reply := _cmd("Pause", {"reason": reason})
	if str(reply.get("status", "")) == "ACCEPTED":
		_pause_token = str(reply.get("payload", {}).get("token", ""))
		_paused = true
		if _clock:
			_clock.open_pause_screen()
		if _workers:
			_workers.set_frozen(true)
	return _pause_token


func release_pause() -> void:
	if _pause_token == "":
		_paused = false
		return
	_cmd("Resume", {"token": _pause_token})
	_pause_token = ""
	_paused = false
	if _clock:
		_clock.close_pause_screen()
		_clock.notify_focus(true)
	if _workers:
		_workers.set_frozen(false)


func _on_bridge_failed(_reason: String) -> void:
	_bridge_down = true
	_paused = true
	_status.text = "Bridge failed — Game Time paused"
	_status.modulate.a = 1.0


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
	return _client.request_view(scope, fields if fields.size() > 0 else INDUSTRY_FIELDS)


func _cmd(kind: String, payload: Dictionary = {}) -> Dictionary:
	return _bridge_cmd("g05-%s-%d" % [kind, Time.get_ticks_msec()], kind, payload)


func reproject_from_python() -> void:
	var view: Dictionary = _bridge_view("player", INDUSTRY_FIELDS)
	_last_industry = view
	var area: Dictionary = _coerce_dict(view.get("overworld_area"))
	if area.is_empty():
		return
	_fx_meta = _coerce_dict(view.get("fx_village"))
	if _fx_meta.is_empty():
		_fx_meta = _coerce_dict(area.get("fx_village"))
	VillageTestRunner.replace_area(area)
	if _overworld != null and _overworld.has_method("_finish_village_build"):
		var start: Array = area.get("player_start", [0, 0])
		# Prefer live Python pose when present.
		var player: Dictionary = _coerce_dict(view.get("player"))
		var ppos = player.get("position", start)
		var facing := str(player.get("facing", area.get("player_facing", "down")))
		_overworld._finish_village_build(Vector2i(int(ppos[0]), int(ppos[1])), facing)
	_apply_workers(view)
	_apply_world_layers(area)
	_refresh_time_hud(view)


func _apply_world_layers(area: Dictionary) -> void:
	if _layers != null and _layers.has_method("apply_area"):
		_layers.apply_area(area)


func _refresh_time_hud(view: Dictionary = {}) -> void:
	if _time_hud == null:
		return
	var clock: Dictionary = _coerce_dict(view.get("clock")) if not view.is_empty() else {}
	if clock.is_empty() and not _last_industry.is_empty():
		clock = _coerce_dict(_last_industry.get("clock"))
	var turn := int(clock.get("turn", 0))
	var running := not _paused and _focus and not _bridge_down
	var state_txt := "paused" if _paused or not _focus else "running"
	_time_hud.text = "Turn %s · Game Time: %s" % [turn, state_txt]
	if clock.has("game_ms"):
		_game_ms_sample = int(clock.get("game_ms", _game_ms_sample))


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_M:
			_toggle_world_map()
			get_viewport().set_input_as_handled()


func _toggle_world_map() -> void:
	if _map_panel == null or _client == null:
		return
	if _map_panel.visible:
		_map_panel.hide_map()
		return
	_map_pause_token = acquire_pause("world_map")
	var view: Dictionary = _client.request_view("player", ["world_map", "clock", "player"])
	var payload: Dictionary = _coerce_dict(view.get("world_map"))
	_map_panel.show_map(payload)
	_map_panel.move_to_front()


func _on_map_closed() -> void:
	if _map_pause_token != "":
		release_pause()
		_map_pause_token = ""


func start_hazard_challenge(cube_id: String) -> bool:
	## G04 retained duel path — Challenge a catastrophe cube.
	acquire_pause("duel")
	var reply := _cmd("StartHazardDuel", {"cube_id": cube_id})
	if str(reply.get("status", "")) != "ACCEPTED":
		release_pause()
		_status.text = "Challenge rejected: %s" % reply.get("public_feedback", reply.get("code", "?"))
		_status.modulate.a = 1.0
		return false
	_duel_host.visible = true
	_duel_host.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_duel_host.move_to_front()
	var ok: bool = _duel_adapter.begin_from_start_reply(_duel_host, reply, Callable(self, "_cmd"))
	if not ok:
		_duel_host.visible = false
		release_pause()
		_status.text = "Failed to host retained GameBoard duel"
		return false
	_status.text = "Hazard Challenge — retained GameBoard / DmbBattleSim"
	_status.modulate.a = 1.0
	return true


func start_demon_challenge(cube_id: String) -> bool:
	## Compatibility alias for archived quest / older tests.
	return start_hazard_challenge(cube_id)


func resolve_hazard_success(cube_id: String) -> Dictionary:
	## Headless/integration path: Start + Resolve without mounting GameBoard UI.
	acquire_pause("duel")
	var start_reply := _cmd("StartHazardDuel", {"cube_id": cube_id})
	if str(start_reply.get("status", "")) != "ACCEPTED":
		release_pause()
		return start_reply
	var payload: Dictionary = start_reply.get("payload", {})
	var duel: Dictionary = payload.get("duel", {})
	var public: Dictionary = payload.get("public", {})
	var duel_id := str(public.get("duel_id", duel.get("id", "")))
	if duel_id == "":
		release_pause()
		return {"status": "REJECTED", "code": "NO_DUEL_ID", "payload": payload}
	var resolve_reply := _cmd("ResolveHazardDuel", {"duel_id": duel_id, "success": true})
	release_pause()
	reproject_from_python()
	_request_industry_view()
	return resolve_reply


func resolve_demon_success(cube_id: String = "cube:demon") -> Dictionary:
	## Archived-quest alias — prefer resolve_hazard_success.
	return resolve_hazard_success(cube_id)


func solve_sluice_via_bridge() -> Dictionary:
	## Archived FX-VILLAGE-QUEST helper only — not part of baseline G05.
	if str(OS.get_environment("DMB_FIXTURE")) != "FX-VILLAGE-QUEST":
		return {"status": "REJECTED", "code": "QUEST_ARCHIVED", "public_feedback": "sluice quest not active"}
	acquire_pause("sluice")
	var enter := _cmd("Interact", {"action": "enter_sluice"})
	if str(enter.get("status", "")) != "ACCEPTED":
		release_pause()
		return enter
	var area: Dictionary = _coerce_dict(enter.get("payload", {}).get("area"))
	var lease_id := str(area.get("puzzle_lease_id", ""))
	var ver := int(area.get("puzzle_lease_version", 1))
	if lease_id == "":
		var view: Dictionary = _bridge_view("player", INDUSTRY_FIELDS)
		area = _coerce_dict(view.get("overworld_area"))
		lease_id = str(area.get("puzzle_lease_id", ""))
		ver = int(area.get("puzzle_lease_version", 1))
	if lease_id == "":
		release_pause()
		return {"status": "REJECTED", "code": "NO_LEASE"}
	var pick := _cmd("Interact", {"action": "pickup", "item_id": "item:sluice_handle"})
	if str(pick.get("status", "")) not in ["ACCEPTED", "REJECTED"]:
		release_pause()
		return pick
	var push := _cmd("Interact", {
		"action": "puzzle_push",
		"lease_id": lease_id,
		"mechanism_id": "box.sluice",
		"expected_version": ver,
		"position": [0.0, 0.0],
	})
	if str(push.get("status", "")) == "ACCEPTED":
		ver = int(push.get("payload", {}).get("version", ver + 1))
	var place := puzzle_act(lease_id, "receptor.sluice", "place", ver, "item:sluice_handle")
	if str(place.get("status", "")) == "ACCEPTED":
		ver = int(place.get("payload", {}).get("version", ver + 1))
	var result: Dictionary = place
	if not bool(place.get("payload", {}).get("lease", {}).get("checkpoint", {}).get("solved", false)):
		var gate := puzzle_act(lease_id, "gate.final", "open", ver)
		if str(gate.get("status", "")) == "ACCEPTED":
			ver = int(gate.get("payload", {}).get("version", ver + 1))
		result = puzzle_act(lease_id, "sluice.actuator", "on", ver)
	_cmd("Interact", {"action": "return_village"})
	release_pause()
	reproject_from_python()
	return result


func _on_duel_finished(outcome: String, payload: Dictionary) -> void:
	_duel_host.visible = false
	release_pause()
	var status := str(payload.get("payload", {}).get("status", payload.get("status", outcome)))
	if status in ["success", "idempotent"] or outcome in ["win", "victory", "success"]:
		_status.text = "Manifestation cleared — blocked sources should resume"
	else:
		_status.text = "Duel ended (%s)" % outcome
	_status.modulate.a = 1.0
	reproject_from_python()


func enter_sluice() -> void:
	if str(OS.get_environment("DMB_FIXTURE")) != "FX-VILLAGE-QUEST":
		_status.text = "No sluice entrance in the baseline world"
		return
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


func save_slot(slot: String = G05_SAVE) -> Dictionary:
	acquire_pause("save")
	_sync_pose(true)
	var reply := _cmd("Save", {"slot": slot})
	release_pause()
	return reply


func load_slot(slot: String = G05_SAVE) -> Dictionary:
	acquire_pause("load")
	var reply := _cmd("Load", {"slot": slot})
	release_pause()
	if str(reply.get("status", "")) == "ACCEPTED":
		reproject_from_python()
	return reply


func travel_to_node(from_node: String, to_node: String) -> bool:
	## Authoritative G01 Travel: SyncPose, Travel once, reproject destination.
	if from_node == "" or to_node == "":
		return false
	_sync_pose(true)
	# Flush pose before Travel so from_node matches Python player pose.
	var turn_before := -1
	var before: Dictionary = _bridge_view("player", ["clock", "player", "fx_village"])
	turn_before = int(before.get("clock", {}).get("turn", -1))
	var reply: Dictionary = _cmd("Travel", {"from_node": from_node, "to_node": to_node})
	if str(reply.get("status", "")) != "ACCEPTED":
		_last_travel_feedback = str(reply.get("public_feedback", reply.get("code", "rejected")))
		_status.text = "Travel rejected: %s" % _last_travel_feedback
		_status.modulate.a = 1.0
		return false
	_last_travel_feedback = ""
	reproject_from_python()
	var after: Dictionary = _bridge_view("player", ["clock", "player"])
	var turn_after := int(after.get("clock", {}).get("turn", turn_before))
	var player: Dictionary = _coerce_dict(after.get("player"))
	if str(player.get("node_id", "")) != to_node:
		_status.text = "Travel failed to land on %s" % to_node
		return false
	if turn_before >= 0 and turn_after != turn_before + 1:
		_status.text = "Travel turn mismatch %s→%s" % [turn_before, turn_after]
		# Still accept projection — report but do not soft-fail play.
	var dest_name := to_node
	var area2: Dictionary = VillageTestRunner.get_area()
	if not area2.is_empty():
		dest_name = str(area2.get("name", to_node))
		if dest_name.begins_with("node:"):
			dest_name = str(area2.get("node_kind", "wilderness")).capitalize()
	_status.text = "Arrived: %s (turn %s)" % [dest_name, turn_after]
	_status.modulate.a = 1.0
	_refresh_time_hud(after)
	return true


func last_travel_feedback() -> String:
	return _last_travel_feedback


func fx_meta() -> Dictionary:
	return _fx_meta.duplicate(true)


func last_industry_view() -> Dictionary:
	return _last_industry.duplicate(true)


func game_ms() -> int:
	## Prefer the last AdvanceGame sample to avoid sync request_view deadlocks
	## while ClockDriver has an in-flight AdvanceGame.
	if _clock_inflight_id != "" or not _paused:
		return _game_ms_sample
	if _client == null:
		return _game_ms_sample
	var full: Dictionary = _client.request_view("player", [])
	_game_ms_sample = int(full.get("clock", {}).get("game_ms", _game_ms_sample))
	return _game_ms_sample


func probe_economy(fields: Array = []) -> Dictionary:
	## Sync economy view with Game Time paused so the bridge queue cannot deadlock.
	var token := ""
	if not _paused:
		token = acquire_pause("probe")
	var view: Dictionary = {}
	if _client != null:
		view = _client.request_view(
			"economy",
			fields if fields.size() > 0 else INDUSTRY_FIELDS
		)
		_last_industry = _client.merge_player_view(_last_industry, view, INDUSTRY_FIELDS) if _client.has_method("merge_player_view") else view
		_apply_workers(_last_industry)
	if token != "":
		release_pause()
	return view


func probe_player(fields: Array = []) -> Dictionary:
	var token := ""
	if not _paused:
		token = acquire_pause("probe")
	var view: Dictionary = {}
	if _client != null:
		view = _client.request_view("player", fields)
		if view.has("clock"):
			_game_ms_sample = int(view.get("clock", {}).get("game_ms", _game_ms_sample))
	if token != "":
		release_pause()
	return view


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


func is_game_time_paused() -> bool:
	return _paused


func _setup_long_world_observer() -> void:
	_long_panel = VBoxContainer.new()
	_long_panel.name = "LongWorldControls"
	_long_panel.set_anchors_preset(PRESET_BOTTOM_LEFT)
	_long_panel.offset_left = 8
	_long_panel.offset_top = -220
	_long_panel.offset_right = 320
	_long_panel.offset_bottom = -8
	_long_panel.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_long_panel)
	var title := Label.new()
	title.text = "Dev observer — Wait/AdvanceGame only"
	_long_panel.add_child(title)
	var row := HBoxContainer.new()
	_long_panel.add_child(row)
	for item in [["Pause", 0], ["1x", 1], ["10x", 10], ["50x", 50]]:
		var btn := Button.new()
		btn.text = str(item[0])
		var spd := int(item[1])
		btn.pressed.connect(func(): _set_long_speed(spd))
		row.add_child(btn)
	var row2 := HBoxContainer.new()
	_long_panel.add_child(row2)
	for item in [["+1 Turn", 1], ["+10 Turns", 10], ["+50 Turns", 50]]:
		var btn2 := Button.new()
		btn2.text = str(item[0])
		var n := int(item[1])
		btn2.pressed.connect(func(): _run_long_turns(n))
		row2.add_child(btn2)
	var follow := CheckButton.new()
	follow.text = "Follow major events"
	follow.toggled.connect(func(on: bool): _follow_major = on)
	_long_panel.add_child(follow)
	_long_event_log = RichTextLabel.new()
	_long_event_log.custom_minimum_size = Vector2(300, 110)
	_long_event_log.scroll_following = true
	_long_event_log.bbcode_enabled = true
	_long_event_log.fit_content = false
	_long_panel.add_child(_long_event_log)
	_long_autorun = true
	_long_speed = 10
	_append_long_event("Observer ready — seed 507 FX-LONG-WORLD")


func _set_long_speed(speed: int) -> void:
	_long_speed = speed
	_long_autorun = speed > 0
	if speed == 0:
		acquire_pause("long_world_pause")
	elif _pause_token != "":
		release_pause()
	_append_long_event("Speed %sx" % speed)


func _run_long_turns(n: int) -> void:
	for _i in n:
		_submit_long_wait()
		for _q in range(max(1, _long_speed)):
			_submit_long_advance()
	reproject_from_python()
	_refresh_long_map()


var _long_tick_acc := 0.0


func _long_world_tick(delta: float) -> void:
	_long_tick_acc += delta * float(max(1, _long_speed))
	while _long_tick_acc >= 0.35:
		_long_tick_acc -= 0.35
		_submit_long_wait()
		for _q in range(max(1, mini(_long_speed, 10))):
			_submit_long_advance()
		reproject_from_python()
		_refresh_long_map()


func _submit_long_wait() -> void:
	if _client == null:
		return
	var player: Dictionary = _coerce_dict(_last_industry.get("player"))
	var node_id := str(player.get("node_id", _fx_meta.get("node_id", "")))
	_cmd_seq += 1
	_client.enqueue_command(
		"long-wait-%s" % _cmd_seq,
		"Wait",
		{"current_node": node_id, "press_id": "long-%s" % _cmd_seq},
		{"replaceable": false}
	)


func _submit_long_advance() -> void:
	if _client == null:
		return
	_cmd_seq += 1
	_client.enqueue_command(
		"long-adv-%s" % _cmd_seq,
		"AdvanceGame",
		{"delta_ms": 100, "clock_sequence": _cmd_seq},
		{"replaceable": true, "coalesce_key": "AdvanceGame"}
	)


func _refresh_long_map() -> void:
	if _map_panel == null or not _map_panel.visible:
		return
	var view: Dictionary = _client.request_view("player", ["world_map", "clock", "battles", "player"])
	_map_panel.show_map(_coerce_dict(view.get("world_map")))
	_note_major_events(view)


func _note_major_events(view: Dictionary) -> void:
	var battles: Dictionary = _coerce_dict(view.get("battles"))
	for bid in battles.keys():
		var b: Dictionary = _coerce_dict(battles[bid])
		var st := str(b.get("state", ""))
		if st in ["PENDING", "ACTIVE", "LOCAL", "OFFSCREEN", "READY"]:
			_append_long_event("Battle %s at %s (%s)" % [bid, b.get("node_id", "?"), st])
			if _follow_major:
				_spectator_node = str(b.get("node_id", ""))


func _append_long_event(text: String) -> void:
	if _long_event_log == null:
		return
	_long_event_log.append_text(text + "\n")


func _maybe_host_local_battle() -> void:
	## When the viewed node has an active battle, mount LocalBattle (G04 reuse).
	if _client == null or _overworld == null:
		return
	var battles: Dictionary = _coerce_dict(_last_industry.get("battles"))
	if battles.is_empty():
		return
	var player: Dictionary = _coerce_dict(_last_industry.get("player"))
	var node_id := str(player.get("node_id", ""))
	if _spectator_node != "":
		node_id = _spectator_node
	var active_id := ""
	for bid in battles.keys():
		var b: Dictionary = _coerce_dict(battles[bid])
		if str(b.get("node_id", "")) != node_id:
			continue
		if str(b.get("state", "")) in ["PENDING", "ACTIVE", "LOCAL", "OFFSCREEN", "READY"]:
			active_id = str(bid)
			break
	if active_id == "":
		return
	if _battle != null and is_instance_valid(_battle):
		return
	_battle = LocalBattle.new()
	_battle.name = "LocalBattleHost"
	_battle_host = EncounterHost.new()
	if _overworld.get("_actors_root") != null:
		_overworld._actors_root.add_child(_battle)
	else:
		add_child(_battle)
	_append_long_event("Hosting LocalBattle for %s" % active_id)


func _exit_tree() -> void:
	VillageTestRunner.clear()
	if _launcher != null:
		_launcher.stop()
