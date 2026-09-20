extends SceneTree

## G05 cumulative runtime — Game Time, industry, carriers, mouse, SyncPose, solutions.
## godot --headless --path godot_project --script res://client/tests/run_g05_cumulative.gd

const Shell = preload("res://client/scenes/g05_shell.gd")
const VillageTestRunner = preload("res://client/scripts/village_test_runner.gd")


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	push_error(msg)
	print("G05_CUMULATIVE_FAIL %s" % msg)
	quit(1)


func _run() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-VILLAGE")
	OS.set_environment("DMB_SEED", "505")
	var shell = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 25000
	while Time.get_ticks_msec() < deadline and not shell.is_village_ready():
		await process_frame
	if not shell.is_village_ready():
		_fail("village not ready")
		return
	# Let ClockDriver land at least one AdvanceGame ack.
	var t0 := Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 800:
		await process_frame

	var mara_id := shell.mara_actor_id()
	var factory := shell.factory_id()
	if mara_id == "" or factory == "":
		_fail("missing mara/factory meta")
		return
	var area: Dictionary = VillageTestRunner.get_area()
	if _entity(area, mara_id).is_empty() or _entity(area, factory).is_empty():
		_fail("mara/factory not presented")
		return

	# Industry presence + initial blockage (real IndustryService).
	var ind: Dictionary = shell.probe_economy([
		"industry", "industry_workers", "industry_factories", "industry_connections",
		"fx_industry", "buildings", "clock"
	])
	var industry: Dictionary = ind.get("industry", {})
	var channels: Variant = industry.get("channels", {})
	var routes: Variant = industry.get("routes", {})
	var processors: Variant = industry.get("processors", {})
	if typeof(channels) != TYPE_DICTIONARY or (channels as Dictionary).is_empty():
		_fail("no IndustryService channels")
		return
	var routes_empty := typeof(routes) != TYPE_DICTIONARY or (routes as Dictionary).is_empty()
	var procs_empty := typeof(processors) != TYPE_DICTIONARY or (processors as Dictionary).is_empty()
	if routes_empty and procs_empty:
		_fail("no IndustryService routes/processors")
		return
	var initial_rate := _factory_rate(ind, factory)
	if initial_rate > 0.0:
		_fail("expected zero factory rate while demon blocks ore, got %s" % initial_rate)
		return
	var workers: Array = ind.get("industry_workers", [])
	if workers.is_empty():
		_fail("no industry_workers")
		return
	var carrier_ids: Array = []
	for w in workers:
		if typeof(w) == TYPE_DICTIONARY and str(w.get("role", "")) == "carrier":
			carrier_ids.append(str(w.get("person_id", "")))
	if carrier_ids.is_empty():
		_fail("no persistent carriers")
		return
	var connections: Array = ind.get("industry_connections", [])
	if connections.is_empty():
		_fail("no industry_connections")
		return

	# Fresh snapshot for Route B after Route A path mutates the world.
	var fresh_save: Dictionary = shell.save_slot("g05_cum_fresh")
	if str(fresh_save.get("status", "")) != "ACCEPTED":
		_fail("fresh save failed")
		return

	# Game Time advances while unpaused.
	var ms0 := shell.game_ms()
	t0 = Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 1800:
		await process_frame
	var ms1 := shell.game_ms()
	if ms1 <= ms0:
		# Force a probed sample if AdvanceGame replies were empty of clock.
		var clock_probe: Dictionary = shell.probe_player([])
		ms1 = int(clock_probe.get("clock", {}).get("game_ms", ms1))
	if ms1 <= ms0:
		_fail("game_ms did not advance (%s -> %s)" % [ms0, ms1])
		return

	# Pause freezes Game Time and carriers.
	var carrier0 := str(carrier_ids[0])
	shell.acquire_pause("test")
	var ms_p0 := shell.game_ms()
	if shell._workers != null:
		var wn = shell._workers.worker_for_person(carrier0)
		if wn != null:
			var paused_pos: Vector2 = wn.position
			shell._workers.set_frozen(true)
			shell._workers.tick(1.0)
			if wn.position.distance_to(paused_pos) > 0.01:
				_fail("carrier moved while paused")
				return
	t0 = Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 900:
		await process_frame
	var ms_p1 := shell.game_ms()
	if ms_p1 != ms_p0:
		_fail("game_ms advanced while paused (%s -> %s)" % [ms_p0, ms_p1])
		return
	shell.release_pause()

	# Grid movement + SyncPose (same path mouse hold uses via _movement_input).
	var ow = shell.overworld()
	var before: Vector2i = ow._john_pos
	ow.ui_hold_key_direction(Vector2i(0, -1))
	for i in range(10):
		if not ow._moving:
			ow._try_step(Vector2i(0, -1))
		await process_frame
	ow.ui_hold_key_direction(Vector2i.ZERO)
	t0 = Time.get_ticks_msec()
	while ow._moving and Time.get_ticks_msec() - t0 < 2000:
		await process_frame
	var after: Vector2i = ow._john_pos
	if after == before:
		_fail("player did not move")
		return
	shell._sync_pose(true)
	await process_frame
	await process_frame
	var player_view: Dictionary = shell.probe_player([])
	var ppos = player_view.get("player", {}).get("position", [0, 0])
	if int(round(float(ppos[0]))) != after.x or int(round(float(ppos[1]))) != after.y:
		_fail("SyncPose stale pose py=%s local=%s" % [ppos, after])
		return

	# Demon solution restores Route A via industry calculation.
	var demon: Dictionary = shell.resolve_demon_success("cube:demon")
	if str(demon.get("status", "")) != "ACCEPTED":
		_fail("demon resolve failed: %s" % demon)
		return
	t0 = Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 2200:
		await process_frame
	ind = shell.probe_economy([
		"industry", "industry_workers", "industry_factories", "fx_industry", "buildings"
	])
	var rate_a := _factory_rate(ind, factory)
	if rate_a <= 0.0:
		_fail("Route A rate still zero after demon clear: %s" % rate_a)
		return
	workers = ind.get("industry_workers", [])
	var carrying := 0
	for w in workers:
		if typeof(w) == TYPE_DICTIONARY and str(w.get("activity", "")) == "carrying":
			carrying += 1
	if carrying < 1:
		_fail("no carrying workers after production resumes")
		return
	if shell._workers == null:
		_fail("WorkerController missing")
		return
	shell._workers.set_frozen(false)
	var sample_node = null
	for w in workers:
		if typeof(w) != TYPE_DICTIONARY or str(w.get("role", "")) != "carrier":
			continue
		var node2 = shell._workers.worker_for_person(str(w.get("person_id", "")))
		if node2 != null:
			sample_node = node2
			break
	if sample_node == null:
		_fail("WorkerController has no carrier nodes")
		return
	var pos_a: Vector2 = sample_node.position
	var moved_carrier := false
	t0 = Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 1200:
		shell._workers.tick(0.05)
		await process_frame
	if sample_node.position.distance_to(pos_a) >= 0.5:
		moved_carrier = true
	else:
		var had_waypoints := false
		for w in workers:
			if typeof(w) == TYPE_DICTIONARY and str(w.get("role", "")) == "carrier":
				if (w.get("waypoints") or []).size() >= 2:
					had_waypoints = true
					break
		if not had_waypoints:
			_fail("carrier did not move and has no waypoints")
			return

	# Save/load preserves IDs and pose.
	var save_reply: Dictionary = shell.save_slot("g05_cumulative")
	if str(save_reply.get("status", "")) != "ACCEPTED":
		_fail("save failed")
		return
	var load_reply: Dictionary = shell.load_slot("g05_cumulative")
	if str(load_reply.get("status", "")) != "ACCEPTED":
		_fail("load failed")
		return
	await process_frame
	await process_frame
	if shell.mara_actor_id() != mara_id or shell.factory_id() != factory:
		_fail("ids changed after reload")
		return
	var area2: Dictionary = VillageTestRunner.get_area()
	if _entity(area2, mara_id).is_empty() or _entity(area2, factory).is_empty():
		_fail("presentation lost mara/factory after reload")
		return
	var pose_after: Vector2i = shell.overworld()._john_pos
	var py2 = shell.probe_player([]).get("player", {}).get("position", [0, 0])
	if int(round(float(py2[0]))) != pose_after.x or int(round(float(py2[1]))) != pose_after.y:
		_fail("pose mismatch after reload py=%s local=%s" % [py2, pose_after])
		return

	# Route B: restore fresh world, solve sluice through puzzle finish → IndustryService.
	var reloaded: Dictionary = shell.load_slot("g05_cum_fresh")
	if str(reloaded.get("status", "")) != "ACCEPTED":
		_fail("reload fresh failed")
		return
	await process_frame
	await process_frame
	ind = shell.probe_economy(["industry", "industry_factories"])
	if _factory_rate(ind, factory) > 0.0:
		_fail("fresh reload should still be blocked")
		return
	var sluice: Dictionary = shell.solve_sluice_via_bridge()
	if str(sluice.get("status", "")) != "ACCEPTED":
		_fail("sluice solve failed: %s" % sluice)
		return
	t0 = Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 1500:
		await process_frame
	ind = shell.probe_economy(["industry", "industry_factories", "hazards", "fx_industry"])
	var rate_b := _factory_rate(ind, factory)
	if rate_b <= 0.0:
		_fail("Route B rate still zero after sluice: %s" % rate_b)
		return
	var hview: Dictionary = shell.probe_player(["hazards"])
	var cubes: Dictionary = hview.get("hazards", {}).get("catastrophe", {}).get("cubes", {})
	if cubes.has("cube:demon") and not bool(cubes["cube:demon"].get("active", true)):
		_fail("sluice must not clear demon cube")
		return

	print(
		"G05_CUMULATIVE_OK game_ms=%s→%s rate_a=%s rate_b=%s carriers=%s moved=%s mara=%s factory=%s"
		% [ms0, ms1, rate_a, rate_b, carrier_ids.size(), moved_carrier, mara_id, factory]
	)
	quit(0)


func _factory_rate(view: Dictionary, factory_id: String) -> float:
	for row in view.get("industry_factories", []):
		if typeof(row) == TYPE_DICTIONARY and str(row.get("factory_id", "")) == factory_id:
			return float(row.get("rate_per_sec", 0))
	var rates: Dictionary = {}
	for event in view.get("industry", {}).get("events", []):
		if typeof(event) == TYPE_DICTIONARY and str(event.get("kind", "")) == "industry_rates":
			rates = event.get("rates", {})
	var raw = rates.get(factory_id, 0)
	if typeof(raw) == TYPE_DICTIONARY:
		return float(str(raw.get("numerator", 0))) / max(float(str(raw.get("denominator", 1))), 1.0)
	return float(raw)


func _entity(area: Dictionary, eid: String) -> Dictionary:
	for raw in area.get("entities", []):
		if typeof(raw) == TYPE_DICTIONARY and str(raw.get("id", "")) == eid:
			return raw
	return {}
