extends SceneTree

## Disposable-scene oracle challenge: boot, harvest, mutate presentation nodes, reharvest.
## Mutates only WorldLayerPresenters actors with sim_id meta — not Overworld john sprite.

const Driver = preload("res://client/tests/auto_gate_driver.gd")
const Harvester = preload("res://client/tests/visual_sim_harvester.gd")

func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var out_dir := OS.get_environment("DMB_VISUAL_SIM_OUT").strip_edges()
	if out_dir == "":
		out_dir = ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir().path_join(
			"qa/visual_sim/out/oracle_challenge"
		)
	DirAccess.make_dir_recursive_absolute(out_dir)
	var driver = Driver.new(self)
	var ok: bool = await driver.launch_fixture("VISUAL_SIM", "FX-MVP", 507, "visual_sim_oracle")
	if not ok:
		print("VISUAL_SIM_ORACLE_FAIL boot")
		quit(1)
		return
	await driver.force_size(Vector2i(1280, 720))
	# Freeze shell so projection cannot restore mutated presentation mid-challenge.
	if driver.shell != null:
		driver.shell.set_process(false)
		driver.shell.set_physics_process(false)
	var healthy: Dictionary = Harvester.harvest(driver.shell)
	_write(out_dir.path_join("healthy.json"), healthy)
	var target: Node = _find_sim_body(driver.shell)
	var failures: Array = []
	if target == null:
		failures.append("no_sim_body")
	else:
		var sid := str(target.get_meta("sim_id"))
		var parent: Node = target.get_parent()
		var layers = driver.shell.get("_layers")
		# Duplicate body
		var clone: Node = target.duplicate()
		clone.set_meta("sim_id", sid)
		clone.set_meta("sim_kind", str(target.get_meta("sim_kind")) if target.has_meta("sim_kind") else "entity")
		clone.set_meta("sim_role", "body")
		parent.add_child(clone)
		await process_frame
		var dup_h: Dictionary = Harvester.harvest(driver.shell)
		var dup_count := _count_body(dup_h, sid)
		if dup_count < 2:
			failures.append("duplicate_not_detected_in_harvest")
		clone.queue_free()
		if clone.get_parent() != null:
			clone.get_parent().remove_child(clone)
		clone.free()
		await process_frame
		await process_frame
		# Hide all layer bodies with this sim_id (disposable instance only).
		for n in parent.get_children():
			if n.has_meta("sim_id") and str(n.get_meta("sim_id")) == sid and n is CanvasItem:
				(n as CanvasItem).visible = false
		await process_frame
		var hid_h: Dictionary = Harvester.harvest(driver.shell)
		for e2 in hid_h.get("entities", []):
			if str(e2.get("source")) != "layers":
				continue
			if str(e2.get("sim_id")) == sid and str(e2.get("role")) == "body" and bool(e2.get("visible_in_tree", true)):
				failures.append("hide_not_reflected")
				break
		for n2 in parent.get_children():
			if n2.has_meta("sim_id") and str(n2.get_meta("sim_id")) == sid and n2 is CanvasItem:
				(n2 as CanvasItem).visible = true
		# Move
		if target is Node2D:
			var orig: Vector2 = (target as Node2D).position
			(target as Node2D).position = orig + Vector2(640, 640)
			await process_frame
			var mov_h: Dictionary = Harvester.harvest(driver.shell)
			var moved := false
			for e4 in mov_h.get("entities", []):
				if str(e4.get("source")) != "layers":
					continue
				if str(e4.get("sim_id")) == sid and str(e4.get("role")) == "body":
					var g = e4.get("grid")
					if g != null and (abs(float(g[0]) - orig.x / 64.0) > 2.0 or abs(float(g[1]) - orig.y / 64.0) > 2.0):
						moved = true
			if not moved:
				failures.append("move_not_reflected")
			(target as Node2D).position = orig
		# Remove from presenter map + free all matching layer bodies.
		if layers != null and layers.get("_by_id") != null:
			layers._by_id.erase(sid)
		var doomed: Array = []
		for n3 in parent.get_children():
			if n3.has_meta("sim_id") and str(n3.get_meta("sim_id")) == sid:
				doomed.append(n3)
		for n4 in doomed:
			if n4.get_parent() != null:
				n4.get_parent().remove_child(n4)
			n4.free()
		await process_frame
		await process_frame
		var miss_h: Dictionary = Harvester.harvest(driver.shell)
		if _count_body(miss_h, sid) > 0:
			failures.append("remove_not_reflected")
		_write(out_dir.path_join("challenge.json"), {
			"sim_id": sid,
			"dup_count": dup_count,
			"failures": failures,
			"healthy_count": healthy.get("entity_count"),
			"missing_count": miss_h.get("entity_count"),
		})
	if driver.shell.get("_launcher") != null:
		driver.shell._launcher.stop()
	driver.shell.queue_free()
	if failures.is_empty():
		print("VISUAL_SIM_ORACLE_CHALLENGE_OK")
		quit(0)
	else:
		print("VISUAL_SIM_ORACLE_CHALLENGE_FAIL %s" % str(failures))
		quit(1)


func _find_sim_body(shell) -> Node:
	var layers = shell.get("_layers")
	if layers != null and layers.get("_by_id") != null:
		var by: Dictionary = layers._by_id
		for id in by.keys():
			var n = by[id]
			if n != null and is_instance_valid(n) and n.has_meta("sim_id"):
				return n
	return null


func _count_body(harvest: Dictionary, sid: String) -> int:
	var n := 0
	for e in harvest.get("entities", []):
		if str(e.get("source")) != "layers":
			continue
		if str(e.get("sim_id")) == sid and str(e.get("role", "body")) == "body":
			n += 1
	return n


func _write(path: String, data: Dictionary) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(data, "\t"))
		f.close()
