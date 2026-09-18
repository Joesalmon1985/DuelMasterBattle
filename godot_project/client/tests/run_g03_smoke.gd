extends SceneTree

const G03Shell = preload("res://client/scenes/g03_shell.gd")


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-INDUSTRY")
	OS.set_environment("DMB_SEED", "303")
	var shell: Control = G03Shell.new()
	shell._paused = true
	root.add_child(shell)
	await create_timer(2.0).timeout
	if shell._client == null or shell._area == null:
		push_error("G03 shell failed to boot")
		quit(1)
		return
	var initial: Dictionary = shell._client.request_view("economy", [
		"fx_industry", "industry", "industry_workers", "industry_connections",
		"industry_factories", "buildings", "stocks", "units"
	])
	var sites: Array = initial.get("fx_industry", {}).get("layout", {}).get("sites", [])
	if sites.size() < 6:
		push_error("G03 layout sites missing")
		quit(1)
		return
	var connections: Array = initial.get("industry_connections", [])
	if connections.size() < 5:
		push_error("G03 connections missing")
		quit(1)
		return
	var raw_labels := {}
	for conn_variant in connections:
		var conn: Dictionary = conn_variant
		if str(conn.get("kind", "")) == "raw_input":
			raw_labels[str(conn.get("resource_label", ""))] = true
	if not raw_labels.has("Foraged berries and nuts") or not raw_labels.has("Flint"):
		push_error("G03 raw input carriers missing distinct resources")
		quit(1)
		return
	var workers: Array = initial.get("industry_workers", [])
	var carriers: Array = []
	for worker_variant in workers:
		var worker: Dictionary = worker_variant
		if str(worker.get("role", "")) == "carrier":
			carriers.append(worker)
	if carriers.is_empty():
		push_error("G03 carriers missing")
		quit(1)
		return
	for carrier_variant in carriers:
		var carrier: Dictionary = carrier_variant
		var waypoints: Array = carrier.get("waypoints", [])
		if waypoints.size() != 2:
			push_error("carrier must use a single directed connection")
			quit(1)
			return
	var meters_before: Dictionary = initial.get("industry", {}).get("factories", {})
	shell._manual_path_block = true
	if shell._workers:
		shell._workers.set_manual_path_block(true)
		shell._workers.set_frozen(false)
		shell._workers.tick(0.2)
	await create_timer(0.2).timeout
	var mid: Dictionary = shell._client.request_view("economy", ["industry"])
	# Path block must not alter authoritative meters.
	if mid.get("industry", {}).get("factories", {}) != meters_before:
		# Allow event appends but meters must match.
		for factory_id in meters_before.keys():
			if mid.get("industry", {}).get("factories", {}).get(factory_id, {}).get("meter") != meters_before[factory_id].get("meter"):
				push_error("path block altered production meters")
				quit(1)
				return
	shell._manual_path_block = false
	if shell._workers:
		shell._workers.set_manual_path_block(false)
	# Pause freeze
	if shell._workers:
		var worker_id0: String = str(carriers[0].get("person_id", ""))
		var worker_node: Node2D = shell._workers.worker_for_person(worker_id0)
		var pos_before: Vector2 = worker_node.position if worker_node else Vector2.ZERO
		shell._workers.set_frozen(true)
		shell._workers.tick(1.0)
		if worker_node and worker_node.position.distance_to(pos_before) > 0.01:
			push_error("paused worker moved")
			quit(1)
			return
		shell._workers.set_frozen(false)
	var worker_id: String = str(carriers[0].get("person_id", ""))
	var seq := int(initial.get("clock", {}).get("clock_sequence", 0))
	for index in range(10):
		seq += 1
		var reply: Dictionary = shell._client.send_command(
			"g03-advance-%d" % index, "AdvanceGame",
			{"delta_ms": 10000, "clock_sequence": seq}
		)
		if str(reply.get("status", "")) != "ACCEPTED":
			push_error("G03 advance failed")
			quit(1)
			return
	var after: Dictionary = shell._client.request_view("economy", [
		"fx_industry", "industry", "industry_workers", "buildings", "stocks"
	])
	var factory_count := 0
	for factory in after.get("industry", {}).get("factories", {}).values():
		if factory.get("meter") == {"numerator": "0", "denominator": "1"}:
			factory_count += 1
	if factory_count != 3:
		push_error("G03 100-second oracle failed")
		quit(1)
		return
	var finite_id := str(after.get("fx_industry", {}).get("finite_layer_id", ""))
	var finite: Dictionary = after.get("industry", {}).get("layers", {}).get(finite_id, {}).get("finite_balance", {})
	if str(finite.get("numerator", "")) != "590":
		push_error("G03 finite consumption oracle failed")
		quit(1)
		return
	if str(after.get("industry_workers", [])[0].get("person_id", "")) != worker_id:
		push_error("worker identity changed")
		quit(1)
		return
	var damage: Dictionary = shell._client.send_command("g03-damage", "Interact", {"action": "industry_damage"})
	var repair: Dictionary = shell._client.send_command("g03-repair", "Interact", {"action": "industry_repair"})
	if str(damage.get("status", "")) != "ACCEPTED" or str(repair.get("status", "")) != "ACCEPTED":
		push_error("damage/paid repair controls failed")
		quit(1)
		return
	shell._client.send_command("g03-save", "Save", {"slot": "g03_smoke"})
	var loaded: Dictionary = shell._client.send_command("g03-load", "Load", {"slot": "g03_smoke"})
	if str(loaded.get("status", "")) != "ACCEPTED":
		push_error("G03 save/load failed")
		quit(1)
		return
	print("G03_SMOKE_OK worker=", worker_id, " factories=", factory_count, " finite=590")
	if shell._launcher:
		shell._launcher.stop()
	quit(0)
