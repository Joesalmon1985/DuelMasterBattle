extends SceneTree

## G05 cumulative runtime — generated world, unique actors, live economy, solutions.
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
	OS.set_environment("DMB_SEED", "507")
	var shell = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 25000
	while Time.get_ticks_msec() < deadline and not shell.is_village_ready():
		await process_frame
	if not shell.is_village_ready():
		_fail("village not ready")
		return
	var t0 := Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 800:
		await process_frame

	var mara_id := shell.mara_actor_id()
	var factory := shell.factory_id()
	var fx: Dictionary = shell.fx_meta()
	if mara_id == "" or factory == "" or fx.is_empty():
		_fail("missing fx meta")
		return
	var area: Dictionary = VillageTestRunner.get_area()
	if _entity(area, mara_id).is_empty() or _entity(area, factory).is_empty():
		_fail("mara/factory not presented")
		return

	# --- Generated world integrity ---
	var ind: Dictionary = shell.probe_economy([
		"industry", "industry_workers", "industry_factories", "industry_connections",
		"fx_industry", "fx_village", "buildings", "clock", "hazards"
	])
	var player: Dictionary = shell.probe_player([])
	var board_view: Dictionary = player
	# Pull topology via economy/player merge if present.
	var topo_check: Dictionary = shell.probe_player(["fx_village"])
	if int(fx.get("topology_hexes", 0)) != 19 or int(fx.get("topology_nodes", 0)) != 54:
		_fail("board topology meta missing/wrong: %s" % fx)
		return
	if str(fx.get("node_id", "")) == "" or str(fx.get("settlement_id", "")) == "":
		_fail("settlement/node missing from fx meta")
		return
	if str(fx.get("faction_id", "")) == "":
		_fail("faction missing")
		return

	var industry: Dictionary = ind.get("industry", {})
	var channels: Variant = industry.get("channels", {})
	if typeof(channels) != TYPE_DICTIONARY or (channels as Dictionary).is_empty():
		_fail("no IndustryService channels")
		return
	var workers: Array = ind.get("industry_workers", [])
	if workers.is_empty():
		_fail("no industry_workers")
		return

	# One actor per person: Overworld entities ∩ WorkerController.
	var overworld_people := {}
	for raw in area.get("entities", []):
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var eid := str(raw.get("id", ""))
		if str(raw.get("kind", "")) == "npc" and eid.begins_with("person:"):
			if overworld_people.has(eid):
				_fail("duplicate Overworld person %s" % eid)
				return
			overworld_people[eid] = true
	var worker_people := {}
	if shell._workers != null:
		for pid in shell._workers.person_ids():
			var p := str(pid)
			if worker_people.has(p):
				_fail("duplicate WorkerController person %s" % p)
				return
			worker_people[p] = true
			if overworld_people.has(p):
				_fail("person %s presented twice (Overworld + WorkerController)" % p)
				return
	if not overworld_people.has(mara_id):
		_fail("Mara missing from Overworld actors")
		return
	if worker_people.has(mara_id):
		_fail("Mara must not also be a WorkerController actor")
		return

	# Live economy before quest resolve.
	var work_id := str(fx.get("factory_work_id", ""))
	var rate_work := _factory_rate(ind, work_id)
	var rate_short := _factory_rate(ind, factory)
	if rate_work <= 0.0:
		_fail("unaffected factory should produce before quest solve")
		return
	if rate_short > 0.0:
		_fail("shortage factory should be zero before solve")
		return
	var carrying := 0
	var waiting := 0
	for w in workers:
		if typeof(w) != TYPE_DICTIONARY:
			continue
		if str(w.get("role", "")) != "carrier":
			continue
		var act := str(w.get("activity", ""))
		if act == "carrying":
			carrying += 1
		elif act == "waiting":
			waiting += 1
	if carrying < 1:
		_fail("expected moving/carrying workers on working chain")
		return
	if waiting < 1:
		_fail("expected waiting carriers on blocked shortage chain")
		return

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
		var clock_probe: Dictionary = shell.probe_player([])
		ms1 = int(clock_probe.get("clock", {}).get("game_ms", ms1))
	if ms1 <= ms0:
		_fail("game_ms did not advance (%s -> %s)" % [ms0, ms1])
		return

	shell.acquire_pause("test")
	var ms_p0 := shell.game_ms()
	t0 = Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 700:
		await process_frame
	if shell.game_ms() != ms_p0:
		_fail("game_ms advanced while paused")
		return
	shell.release_pause()

	# Movement + SyncPose.
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
	var ppos = shell.probe_player([]).get("player", {}).get("position", [0, 0])
	if int(round(float(ppos[0]))) != after.x or int(round(float(ppos[1]))) != after.y:
		_fail("SyncPose stale pose py=%s local=%s" % [ppos, after])
		return

	# --- Semantic interaction: workers + buildings (pointer) ---
	if not await _assert_worker_semantics(shell, ow):
		return
	if not await _assert_building_semantics(shell, ow, fx, factory, work_id):
		return
	if not await _assert_real_travel(shell, ow, fx):
		return

	# Route A via real industry.
	var demon_cube := str(fx.get("demon_cube_id", "cube:demon"))
	var demon: Dictionary = shell.resolve_demon_success(demon_cube)
	if str(demon.get("status", "")) != "ACCEPTED":
		_fail("demon resolve failed: %s" % demon)
		return
	t0 = Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 2200:
		await process_frame
	ind = shell.probe_economy(["industry", "industry_workers", "industry_factories"])
	var rate_a := _factory_rate(ind, factory)
	if rate_a <= 0.0:
		_fail("Route A rate still zero after demon clear")
		return

	# Save/load IDs + pose.
	if str(shell.save_slot("g05_cumulative").get("status", "")) != "ACCEPTED":
		_fail("save failed")
		return
	if str(shell.load_slot("g05_cumulative").get("status", "")) != "ACCEPTED":
		_fail("load failed")
		return
	await process_frame
	await process_frame
	if shell.mara_actor_id() != mara_id or shell.factory_id() != factory:
		_fail("ids changed after reload")
		return
	if str(shell.fx_meta().get("settlement_id", "")) != str(fx.get("settlement_id", "")):
		_fail("settlement id lost after reload")
		return

	# Route B on fresh world.
	if str(shell.load_slot("g05_cum_fresh").get("status", "")) != "ACCEPTED":
		_fail("reload fresh failed")
		return
	await process_frame
	await process_frame
	var sluice: Dictionary = shell.solve_sluice_via_bridge()
	if str(sluice.get("status", "")) != "ACCEPTED":
		_fail("sluice solve failed: %s" % sluice)
		return
	t0 = Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 1500:
		await process_frame
	ind = shell.probe_economy(["industry", "industry_factories"])
	var rate_b := _factory_rate(ind, factory)
	if rate_b <= 0.0:
		_fail("Route B rate still zero after sluice")
		return
	var hview: Dictionary = shell.probe_player(["hazards"])
	var cubes: Dictionary = hview.get("hazards", {}).get("catastrophe", {}).get("cubes", {})
	if cubes.has(demon_cube) and not bool(cubes[demon_cube].get("active", true)):
		_fail("sluice must not clear demon cube")
		return

	print(
		"G05_CUMULATIVE_OK seed=%s node=%s settlement=%s faction=%s game_ms=%s→%s rate_work=%s rate_a=%s rate_b=%s mara=%s"
		% [fx.get("seed"), fx.get("node_id"), fx.get("settlement_id"), fx.get("faction_id"), ms0, ms1, rate_work, rate_a, rate_b, mara_id]
	)
	quit(0)


func _assert_worker_semantics(shell, ow) -> bool:
	if shell._workers == null:
		_fail("WorkerController missing")
		return false
	var carrier_id := ""
	for pid in shell._workers.person_ids():
		carrier_id = str(pid)
		break
	if carrier_id == "":
		_fail("no WorkerController actors")
		return false
	var actor: Node2D = shell._workers.worker_for_person(carrier_id)
	if actor == null:
		_fail("carrier actor missing")
		return false
	var spr: Sprite2D = actor.get_node_or_null("Sprite")
	if spr == null or spr.scale != Vector2(ow.TILE_SCALE, ow.TILE_SCALE):
		_fail("worker sprite scale must match Overworld TILE_SCALE=%s got=%s" % [ow.TILE_SCALE, spr.scale if spr else null])
		return false
	var lbl = ow.ui_semantic_label(carrier_id)
	if lbl == null:
		_fail("moving worker missing WorldInteractionLabel")
		return false
	if str(lbl.display_text()).strip_edges() == "":
		_fail("worker passive label empty")
		return false
	await _pointer_press_control(lbl)
	await process_frame
	await process_frame
	var e: Dictionary = ow._entity_by_id(carrier_id)
	var far := str(e.get("semantic", {}).get("observe_far", ""))
	if far.strip_edges() == "":
		_fail("worker observe_far empty")
		return false
	var grid := Vector2i(int(floor(actor.position.x / float(ow.TPX))), int(floor(actor.position.y / float(ow.TPX))))
	ow._john_pos = grid + Vector2i(0, 1)
	ow._john.position = Vector2(ow._john_pos) * ow.TPX + Vector2(0, -8 * ow.TILE_SCALE)
	await process_frame
	if lbl.has_method("press"):
		lbl.press()
	await process_frame
	var talk: Dictionary = shell._cmd("Interact", {"action": "talk", "entity_id": carrier_id})
	if str(talk.get("status", "")) != "ACCEPTED":
		_fail("worker talk rejected")
		return false
	var text := str(talk.get("payload", {}).get("text", talk.get("public_feedback", "")))
	if text.strip_edges() == "":
		_fail("worker talk empty")
		return false
	if shell._workers.worker_for_person(carrier_id) == null:
		_fail("person_id disappeared after talk")
		return false
	return true


func _assert_building_semantics(shell, ow, fx: Dictionary, factory: String, work_id: String) -> bool:
	var ids: Array = [
		str(fx.get("primary_wood_id", "")),
		str(fx.get("processor_work_id", "")),
		work_id,
		factory,
	]
	var buildings: Dictionary = shell.probe_player(["buildings"]).get("buildings", {})
	for bid in buildings.keys():
		var b: Dictionary = buildings[bid]
		if str(b.get("slot_kind", "")) == "warehouse" and str(b.get("node_id", "")) == str(fx.get("node_id", "")):
			ids.insert(0, str(bid))
			break
	for bid_v in ids:
		var bid := str(bid_v)
		if bid == "":
			continue
		var e: Dictionary = ow._entity_by_id(bid)
		if e.is_empty():
			e = _entity(VillageTestRunner.get_area(), bid)
		if e.is_empty():
			_fail("building %s not presented" % bid)
			return false
		var sem: Dictionary = e.get("semantic", {})
		var label := ""
		var labels = sem.get("labels", [])
		if labels is Array and labels.size() > 0 and typeof(labels[0]) == TYPE_DICTIONARY:
			label = str(labels[0].get("text", ""))
		if label.strip_edges() == "":
			label = str(e.get("text", ""))
		if label.strip_edges() == "":
			_fail("building %s label empty" % bid)
			return false
		var far := str(sem.get("observe_far", ""))
		var near := str(sem.get("observe_near", ""))
		if far.strip_edges() == "" or near.strip_edges() == "":
			_fail("building %s observation empty far=%s near=%s" % [bid, far, near])
			return false
		var lbl = ow.ui_semantic_label(bid)
		if lbl != null and str(lbl.display_text()).strip_edges() == "":
			_fail("building %s passive label widget empty" % bid)
			return false
	var work_e: Dictionary = _entity(VillageTestRunner.get_area(), work_id)
	var short_e: Dictionary = _entity(VillageTestRunner.get_area(), factory)
	var work_far := str(work_e.get("semantic", {}).get("observe_far", ""))
	var short_far := str(short_e.get("semantic", {}).get("observe_far", ""))
	if work_far == short_far:
		_fail("working and blocked factories must communicate different states")
		return false
	var quietish := short_far.to_lower()
	if "quiet" not in quietish and "waiting" not in quietish and "stopped" not in quietish:
		_fail("blocked factory observation should sound quiet: %s" % short_far)
		return false
	return true


func _assert_real_travel(shell, ow, fx: Dictionary) -> bool:
	var home := str(fx.get("node_id", "node:35"))
	var full: Dictionary = shell.probe_player([])
	var nodes_view: Dictionary = full.get("board", {}).get("nodes", {})
	var home_rec: Dictionary = nodes_view.get(home, {})
	var exits: Dictionary = home_rec.get("exits", {})
	if exits.is_empty():
		_fail("home node has no topology exits")
		return false
	var dest := ""
	for k in exits.keys():
		dest = str(k)
		break
	var turn0 := int(full.get("clock", {}).get("turn", 0))
	var mara := str(shell.mara_actor_id())
	var factory := str(shell.factory_id())
	if not shell.travel_to_node(home, dest):
		_fail("Travel to adjacent node failed")
		return false
	await process_frame
	await process_frame
	var after: Dictionary = shell.probe_player([])
	if str(after.get("player", {}).get("node_id", "")) != dest:
		_fail("player node not %s after travel" % dest)
		return false
	var turn1 := int(after.get("clock", {}).get("turn", turn0))
	if turn1 != turn0 + 1:
		_fail("Travel must increment World Turn exactly once (%s→%s)" % [turn0, turn1])
		return false
	if VillageTestRunner.get_area().is_empty():
		_fail("destination area missing")
		return false
	if not shell.travel_to_node(dest, home):
		_fail("return Travel failed")
		return false
	await process_frame
	await process_frame
	var back: Dictionary = shell.probe_player([])
	if str(back.get("player", {}).get("node_id", "")) != home:
		_fail("failed to return to %s" % home)
		return false
	if str(shell.mara_actor_id()) != mara or str(shell.factory_id()) != factory:
		_fail("IDs rerolled after round-trip travel")
		return false
	if str(shell.fx_meta().get("settlement_id", "")) != str(fx.get("settlement_id", "")):
		_fail("settlement rerolled after travel")
		return false
	return true


func _pointer_press_control(lbl) -> void:
	if lbl == null or not is_instance_valid(lbl):
		return
	var btn: Control = null
	if "_button" in lbl:
		btn = lbl._button
	if btn == null:
		btn = lbl
	var rect: Rect2 = btn.get_global_rect()
	var center: Vector2 = rect.position + rect.size * 0.5
	var ev_down := InputEventMouseButton.new()
	ev_down.button_index = MOUSE_BUTTON_LEFT
	ev_down.pressed = true
	ev_down.position = center
	ev_down.global_position = center
	Input.parse_input_event(ev_down)
	await process_frame
	var ev_up := InputEventMouseButton.new()
	ev_up.button_index = MOUSE_BUTTON_LEFT
	ev_up.pressed = false
	ev_up.position = center
	ev_up.global_position = center
	Input.parse_input_event(ev_up)
	if lbl.has_method("press"):
		lbl.press()


func _factory_rate(view: Dictionary, factory_id: String) -> float:
	if factory_id == "":
		return 0.0
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
