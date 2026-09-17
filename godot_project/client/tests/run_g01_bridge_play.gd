extends SceneTree

## Real sidecar bridge: walk across clock/pose-sync intervals without World Turn advance.

const Migrated = preload("res://client/core/migrated_runtime.gd")
const SidecarLauncher = preload("res://client/bridge/sidecar_launcher.gd")
const WorldClient = preload("res://client/bridge/world_client.gd")
const FxArea = preload("res://client/world/fx_clock_area.gd")
const ClockDriver = preload("res://client/core/clock_driver.gd")


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
	var view0: Dictionary = client.request_view("player")
	var turn0 := int(view0.get("clock", {}).get("turn", -1))
	var start: Vector2 = area.wizard_position()
	var clock = ClockDriver.new()
	root.add_child(clock)
	var stats := {"advances": 0, "last_status": ""}
	clock.advance_requested.connect(func(delta_ms: int, sequence: int):
		var reply: Dictionary = client.send_command(
			"advance-%d" % sequence,
			"AdvanceGame",
			{"delta_ms": delta_ms, "clock_sequence": sequence}
		)
		stats["last_status"] = str(reply.get("status", "?"))
		if str(reply.get("status", "")) == "ACCEPTED":
			stats["advances"] = int(stats["advances"]) + 1
			area.apply_projections(client.request_view("player"))
	)
	area.set_movement_enabled(true)
	area._move_dir = Vector2(1, 0)
	# ~1.2s of continuous motion spanning multiple AdvanceGame + SyncPose cycles.
	var elapsed := 0.0
	while elapsed < 1.2:
		var dt := 0.05
		elapsed += dt
		clock.tick_render(dt)
		area._process(dt)
		if int(elapsed * 20.0) % 10 == 0:
			client.send_command(
				"pose-%s" % Time.get_ticks_msec(),
				"SyncPose",
				{"position": area.wizard_grid(), "facing": area._facing}
			)
		OS.delay_msec(10)
	var mid: Vector2 = area.wizard_position()
	if mid.x <= start.x + 20.0:
		push_error("bridge walk did not move wizard (start=%s mid=%s)" % [start, mid])
		launcher.stop()
		quit(1)
		return
	var view1: Dictionary = client.request_view("player")
	var turn1 := int(view1.get("clock", {}).get("turn", -2))
	if turn1 != turn0:
		push_error("walking advanced World Turn from %s to %s" % [turn0, turn1])
		launcher.stop()
		quit(1)
		return
	if int(stats["advances"]) < 1:
		push_error("expected AdvanceGame during walk; last_status=%s count=%s" % [str(stats["last_status"]), str(stats["advances"])])
		launcher.stop()
		quit(1)
		return
	var advance_count := int(stats["advances"])
	# Collision: push into wall/blocker briefly then verify still movable on open ground.
	area._move_dir = Vector2(-1, 0)
	for _i in range(40):
		area._process(0.05)
	area._move_dir = Vector2(0, 1)
	var before_down := area.wizard_position()
	for _j in range(20):
		area._process(0.05)
	if area.wizard_position().distance_to(before_down) < 4.0:
		push_error("wizard stuck after collision recovery")
		launcher.stop()
		quit(1)
		return
	# Travel acknowledgement path.
	var from_node := str(view1.get("player", {}).get("node_id", "node:1"))
	var to_node := "node:2" if from_node == "node:1" else "node:1"
	# Place near exit for activation distance.
	if from_node == "node:1":
		area._wizard.position = Vector2(13 * 64 + 32, 5 * 64)
	else:
		area._wizard.position = Vector2(32, 5 * 64)
	area.travel_pending = false
	var pending := false
	area.exit_activated.connect(func(_n): pending = true)
	area._activate_exit(to_node)
	if not pending and not area.travel_pending:
		push_error("exit did not go pending")
		launcher.stop()
		quit(1)
		return
	var travel := client.send_command("travel-bridge", "Travel", {"from_node": from_node, "to_node": to_node})
	if str(travel.get("status", "")) != "ACCEPTED":
		push_error("travel rejected: %s" % travel)
		launcher.stop()
		quit(1)
		return
	var after_travel := client.request_view("player")
	area.acknowledge_travel(to_node, after_travel)
	if str(after_travel.get("player", {}).get("node_id", "")) != to_node:
		push_error("travel node not updated")
		launcher.stop()
		quit(1)
		return
	if int(after_travel.get("clock", {}).get("turn", 0)) != turn0 + 1:
		push_error("travel did not add exactly one World Turn")
		launcher.stop()
		quit(1)
		return
	var moved := mid.x - start.x
	print("G01_BRIDGE_PLAY_OK moved=%.1f advances=%d turn=%s→%s node=%s" % [moved, advance_count, turn0, turn0 + 1, to_node])
	launcher.stop()
	OS.delay_msec(100)
	quit(0)
