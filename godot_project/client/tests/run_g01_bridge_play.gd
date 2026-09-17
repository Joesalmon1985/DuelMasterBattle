extends SceneTree

## Real sidecar bridge: walk spawn → NPC interact → exit travel → return.
## No teleporting, collision disable, or Travel-without-walking.

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
	var stats := {"advances": 0}
	clock.advance_requested.connect(func(delta_ms: int, sequence: int):
		var reply: Dictionary = client.send_command(
			"advance-%d" % sequence,
			"AdvanceGame",
			{"delta_ms": delta_ms, "clock_sequence": sequence}
		)
		if str(reply.get("status", "")) == "ACCEPTED":
			stats["advances"] = int(stats["advances"]) + 1
			area.apply_projections(client.request_view("player"))
	)
	area.set_movement_enabled(true)

	# Corridor / fixture sanity.
	if area.is_cell_blocked(Vector2i(7, 7)) == false:
		push_error("expected visible tree blocker at (7,7)")
		launcher.stop()
		quit(1)
		return
	for cell in [Vector2i(5, 5), Vector2i(9, 5), Vector2i(12, 5), Vector2i(4, 3), Vector2i(10, 4)]:
		if area.is_cell_blocked(cell):
			push_error("corridor cell blocked: %s" % cell)
			launcher.stop()
			quit(1)
			return

	var view0: Dictionary = client.request_view("player")
	var turn0 := int(view0.get("clock", {}).get("turn", -1))
	var start: Vector2 = area.wizard_position()

	# Collision: push into the south tree without teleporting.
	if not _walk_toward(area, clock, client, Vector2(7 * TILE + TILE * 0.5, 7 * TILE + TILE * 0.5), 4.0, 48.0):
		# Approaching is enough; confirm we cannot occupy the blocked cell centre.
		pass
	var near_tree := area.wizard_position()
	area._move_dir = Vector2(0, 1)
	for _i in range(30):
		_tick(area, clock, client, 0.05)
	if int(area.wizard_position().y / TILE) >= 7 and area.is_cell_blocked(Vector2i(7, 7)):
		# Still ok if we slid beside it; must not sit deep inside blocker.
		if area.is_cell_blocked(Vector2i(int(area.wizard_position().x / TILE), int(area.wizard_position().y / TILE))):
			push_error("wizard entered blocked tree cell")
			launcher.stop()
			quit(1)
			return
	area._move_dir = Vector2.ZERO

	# Walk to NPC from spawn path (re-route via open corridor).
	if not _walk_toward(area, clock, client, start, 3.0, 40.0):
		pass
	var npc_id := ""
	for id in area._npc_nodes.keys():
		npc_id = str(id)
		break
	if npc_id == "":
		push_error("no NPC in area")
		launcher.stop()
		quit(1)
		return
	var npc_pos: Vector2 = area._npc_nodes[npc_id].position
	if not _walk_toward(area, clock, client, npc_pos, 10.0, 50.0):
		push_error("could not walk to NPC from spawn")
		launcher.stop()
		quit(1)
		return
	var turn_after_walk := int(client.request_view("player").get("clock", {}).get("turn", -2))
	if turn_after_walk != turn0:
		push_error("walking advanced World Turn")
		launcher.stop()
		quit(1)
		return

	area.selected_entity = npc_id
	area._on_action()
	var inter := client.send_command("interact-bridge", "Interact", {"entity_id": npc_id})
	if str(inter.get("status", "")) != "ACCEPTED":
		push_error("interact failed: %s" % inter)
		launcher.stop()
		quit(1)
		return
	area.apply_projections(client.request_view("player"))

	# Walk to east exit without teleport.
	var exit_id := area.nearest_exit_id()
	if exit_id == "":
		push_error("no exit")
		launcher.stop()
		quit(1)
		return
	var exit_pos: Vector2 = area._exit_nodes[exit_id].position
	# Approach from the open corridor (stay on y≈5).
	var approach := Vector2(exit_pos.x - TILE * 0.8, 5 * TILE)
	if not _walk_toward(area, clock, client, approach, 12.0, 36.0):
		push_error("could not walk toward exit approach")
		launcher.stop()
		quit(1)
		return
	if not _walk_toward(area, clock, client, exit_pos, 4.0, 40.0):
		push_error("could not reach exit range by walking")
		launcher.stop()
		quit(1)
		return
	if not area.exit_in_range(exit_id):
		push_error("exit still out of range after walk")
		launcher.stop()
		quit(1)
		return

	client.send_command("pose-pre-travel", "SyncPose", {"position": area.wizard_grid(), "facing": area._facing})
	var pending := false
	area.exit_activated.connect(func(_n): pending = true)
	area._activate_exit(exit_id)
	if not pending and not area.travel_pending:
		push_error("exit did not go pending after walking into range")
		launcher.stop()
		quit(1)
		return
	var from_node := str(client.request_view("player").get("player", {}).get("node_id", "node:1"))
	var travel := client.send_command("travel-out", "Travel", {"from_node": from_node, "to_node": exit_id})
	if str(travel.get("status", "")) != "ACCEPTED":
		push_error("outbound travel rejected: %s" % travel)
		launcher.stop()
		quit(1)
		return
	var after_out := client.request_view("player")
	area.acknowledge_travel(exit_id, after_out)
	if str(after_out.get("player", {}).get("node_id", "")) != exit_id:
		push_error("outbound node not updated")
		launcher.stop()
		quit(1)
		return
	if int(after_out.get("clock", {}).get("turn", 0)) != turn0 + 1:
		push_error("outbound travel did not add exactly one World Turn")
		launcher.stop()
		quit(1)
		return
	if area.selected_entity != "":
		push_error("selection not cleared after travel")
		launcher.stop()
		quit(1)
		return

	# Return journey on adjacent area: walk to its exit.
	var back_id := area.nearest_exit_id()
	if back_id == "":
		push_error("no return exit")
		launcher.stop()
		quit(1)
		return
	var back_pos: Vector2 = area._exit_nodes[back_id].position
	var back_approach := Vector2(back_pos.x + TILE * 0.8, 5 * TILE)
	if not _walk_toward(area, clock, client, back_approach, 14.0, 36.0):
		push_error("could not walk toward return exit")
		launcher.stop()
		quit(1)
		return
	if not _walk_toward(area, clock, client, back_pos, 4.0, 40.0):
		push_error("could not reach return exit by walking")
		launcher.stop()
		quit(1)
		return
	client.send_command("pose-pre-return", "SyncPose", {"position": area.wizard_grid(), "facing": area._facing})
	area._activate_exit(back_id)
	var from2 := str(client.request_view("player").get("player", {}).get("node_id", ""))
	var travel2 := client.send_command("travel-back", "Travel", {"from_node": from2, "to_node": back_id})
	if str(travel2.get("status", "")) != "ACCEPTED":
		push_error("return travel rejected: %s" % travel2)
		launcher.stop()
		quit(1)
		return
	var after_back := client.request_view("player")
	area.acknowledge_travel(back_id, after_back)
	if str(after_back.get("player", {}).get("node_id", "")) != back_id:
		push_error("return node not updated")
		launcher.stop()
		quit(1)
		return
	if int(after_back.get("clock", {}).get("turn", 0)) != turn0 + 2:
		push_error("return travel did not add exactly one World Turn")
		launcher.stop()
		quit(1)
		return

	var moved := area.wizard_position().distance_to(start)
	print(
		"G01_BRIDGE_PLAY_OK walked=%.1f advances=%d turn=%s→%s nodes=%s→%s→%s"
		% [moved, int(stats["advances"]), turn0, turn0 + 2, from_node, exit_id, back_id]
	)
	launcher.stop()
	OS.delay_msec(100)
	quit(0)


func _tick(area, clock, client, dt: float) -> void:
	clock.tick_render(dt)
	area._process(dt)
	client.send_command(
		"pose-%s" % Time.get_ticks_msec(),
		"SyncPose",
		{"position": area.wizard_grid(), "facing": area._facing}
	)


func _walk_toward(area, clock, client, target: Vector2, timeout_s: float, arrive_px: float) -> bool:
	var elapsed := 0.0
	var stuck := 0
	var last: Vector2 = area.wizard_position()
	while elapsed < timeout_s:
		var pos: Vector2 = area.wizard_position()
		var delta_v: Vector2 = target - pos
		if delta_v.length() <= arrive_px:
			area._move_dir = Vector2.ZERO
			return true
		# One-pointer axis step (same as pad).
		if absf(delta_v.x) >= absf(delta_v.y):
			area._move_dir = Vector2(signf(delta_v.x), 0)
		else:
			area._move_dir = Vector2(0, signf(delta_v.y))
		_tick(area, clock, client, 0.05)
		elapsed += 0.05
		if area.wizard_position().distance_to(last) < 0.2:
			stuck += 1
			# Nudge around a blocker with an alternate axis.
			if stuck % 8 == 4:
				area._move_dir = Vector2(0, -1 if delta_v.y >= 0 else 1)
			elif stuck % 8 == 0:
				area._move_dir = Vector2(-1 if delta_v.x >= 0 else 1, 0)
		else:
			stuck = 0
		last = area.wizard_position()
		OS.delay_msec(5)
	area._move_dir = Vector2.ZERO
	return area.wizard_position().distance_to(target) <= arrive_px
