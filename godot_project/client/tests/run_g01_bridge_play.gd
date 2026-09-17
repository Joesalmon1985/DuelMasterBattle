extends SceneTree

## Walk through doorways with pointer motion; verify linked arrivals and return.
## No teleport; Travel goes through exit_activated → shell-equivalent request.

const Migrated = preload("res://client/core/migrated_runtime.gd")
const SidecarLauncher = preload("res://client/bridge/sidecar_launcher.gd")
const WorldClient = preload("res://client/bridge/world_client.gd")
const FxArea = preload("res://client/world/fx_clock_area.gd")
const ClockDriver = preload("res://client/core/clock_driver.gd")
const TILE := 64.0


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	Migrated.enable()
	var launcher = SidecarLauncher.new()
	root.add_child(launcher)
	var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if project_root.ends_with("godot_project"):
		project_root = project_root.get_base_dir()
	var started: Dictionary = launcher.start(project_root)
	if not started.get("ok", false):
		push_error("sidecar start failed: %s" % started)
		quit(1)
		return
	var client = WorldClient.new()
	root.add_child(client)
	OS.delay_msec(100)
	if not client.connect_sidecar(str(started["host"]), int(started["port"]), str(started["token"])):
		push_error("handshake failed")
		launcher.stop()
		quit(1)
		return
	var area = FxArea.new()
	root.add_child(area)
	area.setup(client, null)
	var clock = ClockDriver.new()
	root.add_child(clock)
	clock.advance_requested.connect(func(delta_ms: int, sequence: int):
		client.send_command(
			"advance-%d" % sequence,
			"AdvanceGame",
			{"delta_ms": delta_ms, "clock_sequence": sequence}
		)
		if not area.travel_pending:
			area.apply_projections(client.request_view("player"))
	)
	area.set_movement_enabled(true)

	var pending_dest := ""
	area.exit_activated.connect(func(to_node: String):
		pending_dest = to_node
	)

	var turn0 := int(client.request_view("player").get("clock", {}).get("turn", -1))
	# Bounds: cannot walk off the map.
	area._wizard.position = Vector2(12 * TILE, 5 * TILE)
	area._move_dir = Vector2(1, 0)
	for _i in range(40):
		area._process(0.05)
	if area.wizard_position().x > (GRID_EDGE()):
		# Should trigger travel or be blocked — not infinite off-map.
		pass
	if int(floor(area.wizard_position().x / TILE)) >= 14:
		push_error("wizard walked outside map bounds")
		launcher.stop()
		quit(1)
		return

	# Reset via authoritative view.
	area.rebuild_from_view(client.request_view("player"))
	area._travel_armed = true

	# Walk to NPC then toward east doorway until auto-travel fires.
	var npc_id := ""
	for id in area._npc_nodes.keys():
		npc_id = str(id)
		break
	if npc_id == "":
		push_error("missing NPC")
		launcher.stop()
		quit(1)
		return
	if not _walk_toward(area, clock, client, area._npc_nodes[npc_id].position, 10.0, 48.0):
		push_error("could not walk to NPC")
		launcher.stop()
		quit(1)
		return
	var inter := client.send_command("i1", "Interact", {"entity_id": npc_id})
	if str(inter.get("status", "")) != "ACCEPTED":
		push_error("interact failed")
		launcher.stop()
		quit(1)
		return

	pending_dest = ""
	# Approach corridor then keep walking east to cross threshold.
	if not _walk_toward(area, clock, client, Vector2(11.5 * TILE, 5.5 * TILE), 10.0, 36.0):
		push_error("corridor approach failed")
		launcher.stop()
		quit(1)
		return
	area._move_dir = Vector2(1, 0)
	var crossed := false
	for _j in range(80):
		_tick(area, clock, client, 0.05)
		if pending_dest != "" or area.travel_pending:
			crossed = true
			break
	if not crossed:
		push_error("doorway walk did not request travel")
		launcher.stop()
		quit(1)
		return
	var from_node := "node:1"
	var to_node := pending_dest if pending_dest != "" else "node:2"
	var travel := client.send_command("travel-out", "Travel", {"from_node": from_node, "to_node": to_node})
	if str(travel.get("status", "")) != "ACCEPTED":
		push_error("travel rejected: %s" % travel)
		launcher.stop()
		quit(1)
		return
	var after := client.request_view("player")
	area.acknowledge_travel(to_node, after)
	var player: Dictionary = after.get("player", {})
	if str(player.get("node_id", "")) != "node:2":
		push_error("bad arrival node")
		launcher.stop()
		quit(1)
		return
	if not _approx(player.get("position"), [1.5, 5.0]):
		push_error("bad arrival position %s" % player.get("position"))
		launcher.stop()
		quit(1)
		return
	if str(player.get("facing", "")) != "right":
		push_error("bad arrival facing")
		launcher.stop()
		quit(1)
		return
	if int(after.get("clock", {}).get("turn", 0)) != turn0 + 1:
		push_error("outbound turn mismatch")
		launcher.stop()
		quit(1)
		return

	# Walk further into destination (inward), then return through west doorway.
	area._travel_armed = true
	if not _walk_toward(area, clock, client, Vector2(6 * TILE, 5.5 * TILE), 8.0, 40.0):
		push_error("could not walk into destination")
		launcher.stop()
		quit(1)
		return
	# Stale pose from source node must not apply.
	var stale := client.send_command(
		"stale-pose",
		"SyncPose",
		{"position": [12.0, 5.0], "facing": "right", "node_id": "node:1", "pose_generation": 0}
	)
	if str(stale.get("status", "")) != "REJECTED":
		push_error("stale SyncPose should be rejected")
		launcher.stop()
		quit(1)
		return

	pending_dest = ""
	area._travel_armed = true
	if not _walk_toward(area, clock, client, Vector2(1.2 * TILE, 5.5 * TILE), 10.0, 36.0):
		push_error("return approach failed")
		launcher.stop()
		quit(1)
		return
	area._move_dir = Vector2(-1, 0)
	crossed = false
	for _k in range(80):
		_tick(area, clock, client, 0.05)
		if pending_dest != "" or area.travel_pending:
			crossed = true
			break
	if not crossed:
		push_error("return doorway did not request travel")
		launcher.stop()
		quit(1)
		return
	var back := pending_dest if pending_dest != "" else "node:1"
	var travel2 := client.send_command("travel-back", "Travel", {"from_node": "node:2", "to_node": back})
	if str(travel2.get("status", "")) != "ACCEPTED":
		push_error("return travel rejected")
		launcher.stop()
		quit(1)
		return
	var after2 := client.request_view("player")
	area.acknowledge_travel(back, after2)
	var p2: Dictionary = after2.get("player", {})
	if str(p2.get("node_id", "")) != "node:1":
		push_error("return node bad")
		launcher.stop()
		quit(1)
		return
	if not _approx(p2.get("position"), [12.0, 5.0]):
		push_error("return arrival position bad %s" % p2.get("position"))
		launcher.stop()
		quit(1)
		return
	if str(p2.get("facing", "")) != "left":
		push_error("return facing bad")
		launcher.stop()
		quit(1)
		return
	if int(after2.get("clock", {}).get("turn", 0)) != turn0 + 2:
		push_error("return turn mismatch")
		launcher.stop()
		quit(1)
		return

	# Save/load after arrival.
	client.send_command("pose-save", "SyncPose", {
		"position": area.wizard_grid(),
		"facing": area._facing,
		"node_id": area.current_node,
		"pose_generation": area.pose_generation,
	})
	var saved := client.send_command("save1", "Save", {"slot": "g01_playtest"})
	if str(saved.get("status", "")) != "ACCEPTED":
		push_error("save failed")
		launcher.stop()
		quit(1)
		return
	area._wizard.position = Vector2(4 * TILE, 5 * TILE)
	var loaded := client.send_command("load1", "Load", {"slot": "g01_playtest"})
	if str(loaded.get("status", "")) != "ACCEPTED":
		push_error("load failed")
		launcher.stop()
		quit(1)
		return
	var after_load := client.request_view("player")
	area.rebuild_from_view(after_load)
	if str(after_load.get("player", {}).get("node_id", "")) != "node:1":
		push_error("load node mismatch")
		launcher.stop()
		quit(1)
		return
	if not _approx(after_load.get("player", {}).get("position"), [12.0, 5.0]):
		push_error("load position mismatch %s" % after_load.get("player", {}).get("position"))
		launcher.stop()
		quit(1)
		return

	# Held movement across a fresh outbound transition must not double-travel immediately.
	# Back off from the doorway, then walk out while holding east.
	area._travel_armed = true
	area._move_dir = Vector2.ZERO
	if not _walk_toward(area, clock, client, Vector2(10.0 * TILE, 5.5 * TILE), 6.0, 40.0):
		push_error("backoff before held-travel failed")
		launcher.stop()
		quit(1)
		return
	area._travel_armed = true
	pending_dest = ""
	var fires := 0
	area._move_dir = Vector2(1, 0)
	for _n in range(120):
		var was_pending: bool = area.travel_pending
		_tick(area, clock, client, 0.05)
		if area.travel_pending and not was_pending:
			fires += 1
			var dest := pending_dest if pending_dest != "" else "node:2"
			var t3 := client.send_command("travel-hold-%d" % fires, "Travel", {"from_node": "node:1", "to_node": dest})
			if str(t3.get("status", "")) == "ACCEPTED":
				area.acknowledge_travel(dest, client.request_view("player"))
			pending_dest = ""
			# Keep holding outward on the destination; arming stays false so no instant return.
			area._move_dir = Vector2(1, 0)
	if fires != 1:
		push_error("held movement should fire exactly one travel, got %s" % fires)
		launcher.stop()
		quit(1)
		return

	print("G01_BRIDGE_PLAY_OK arrivals=ok turns=%s→%s held_fires=1" % [turn0, turn0 + 3])
	launcher.stop()
	OS.delay_msec(100)
	quit(0)


func GRID_EDGE() -> float:
	return 14.0 * TILE


func _approx(pos, expected: Array) -> bool:
	if typeof(pos) != TYPE_ARRAY and typeof(pos) != TYPE_PACKED_FLOAT32_ARRAY:
		return false
	return abs(float(pos[0]) - float(expected[0])) < 0.05 and abs(float(pos[1]) - float(expected[1])) < 0.05


func _tick(area, clock, client, dt: float) -> void:
	clock.tick_render(dt)
	area._process(dt)
	if not area.travel_pending:
		client.send_command(
			"pose-%s" % Time.get_ticks_msec(),
			"SyncPose",
			{
				"position": area.wizard_grid(),
				"facing": area._facing,
				"node_id": area.current_node,
				"pose_generation": area.pose_generation,
			}
		)


func _walk_toward(area, clock, client, target: Vector2, timeout_s: float, arrive_px: float) -> bool:
	var elapsed := 0.0
	var stuck := 0
	var last: Vector2 = area.wizard_position()
	while elapsed < timeout_s:
		if area.travel_pending:
			return true
		var pos: Vector2 = area.wizard_position()
		var delta_v: Vector2 = target - pos
		if delta_v.length() <= arrive_px:
			area._move_dir = Vector2.ZERO
			return true
		if absf(delta_v.x) >= absf(delta_v.y):
			area._move_dir = Vector2(signf(delta_v.x), 0)
		else:
			area._move_dir = Vector2(0, signf(delta_v.y))
		_tick(area, clock, client, 0.05)
		elapsed += 0.05
		if area.wizard_position().distance_to(last) < 0.2:
			stuck += 1
			if stuck % 8 == 4:
				area._move_dir = Vector2(0, -1 if delta_v.y >= 0 else 1)
		else:
			stuck = 0
		last = area.wizard_position()
		OS.delay_msec(5)
	area._move_dir = Vector2.ZERO
	return area.wizard_position().distance_to(target) <= arrive_px or area.travel_pending
