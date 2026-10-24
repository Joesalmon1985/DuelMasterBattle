extends SceneTree

## Headed evidence of the living villages in every age (docs/PLAN_GOD_WORLD_LIVING.md): for each age the island is opened by the ordinary scene with the
## developer start age set (DMB_GOD_START_AGE: a fresh world whose villages begin in that age; the planner builds the networks as in normal play), the
## camera is placed over a working village and the view captured close, at village scale and with the logical overlay. The future age's shot waits for
## the belts to carry packets and the factory to muster a unit. Shots go to HYBRID_SHOT_DIR (default docs/evidence/god_world/headed_ages).
## Prints GOD_AGES_OK.

var _fails: Array[String] = []
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("AGES %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _settle() -> void:
	await _frames(3)
	await RenderingServer.frame_post_draw


func _shot(name: String) -> void:
	await _settle()
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("AGES_SHOT %s" % name)


func _wait_until(pred: Callable, seconds: float) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if pred.call():
			return true
		await _frames(5)
	return false


func _village_with(world: Node, pred: Callable) -> Dictionary:
	for v in world.snapshot.get("villages", []):
		if str(v.get("status", "")) == "operational" and pred.call(v):
			return v
	return {}


func _run_age(age: int) -> void:
	OS.set_environment("DMB_GOD_START_AGE", str(age))
	var lan: Node = get_root().get_node("LanSession")
	lan.reset()
	change_scene_to_file("res://client/scenes/god_world.tscn")
	await _frames(3)
	var world: Node = current_scene
	var ok := await _wait_until(func(): return world.ui_state()["state"] == "playing", 90.0)
	_check(ok, "age %d: the scene is playing (%s)" % [age, str(world.ui_state()["status"])])
	if not ok:
		return
	ok = await _wait_until(func(): return int(world.snapshot.get("age", 0)) == age and world.snapshot.get("villages", []).size() >= 12, 30.0)
	_check(ok, "age %d: the world opened in that age with every faction's villages" % age)
	# a village with the living picture (sites and agents) in the window
	world.set_speed(4)
	var target := {}
	ok = await _wait_until(func():
		target = _village_with(world, func(v): return v.has("ops") and not bool(v["ops"].get("lean", false)) and v["ops"].get("sites", []).size() >= 4)
		return not target.is_empty(), 30.0)
	_check(ok, "age %d: a village has its network planned" % age)
	if target.is_empty():
		return
	world.camera_ctl.focus_on(world.view.bu(float(target["x"]), float(target["y"])), 0.62)
	await _settle()
	ok = await _wait_until(func():
		var v: Dictionary = _village_with(world, func(x): return str(x["id"]) == str(target["id"]))
		if v.is_empty() or not v.has("ops"):
			return false
		var ops: Dictionary = v["ops"]
		if age <= 2:
			return ops.get("agents", []).any(func(a): return str(a.get("cargo", "")) != "")
		if age == 3:
			return ops.get("agents", []).any(func(a): return str(a.get("kind", "")) == "truck" and str(a.get("cargo", "")) != "")
		return ops.get("segments", []).any(func(g): return g.get("items", []).size() > 0), 90.0)
	_check(ok, "age %d: goods are moving in the village (%s)" % [age, str(target.get("name", ""))])
	await _shot("age%d_village_close" % age)
	world.camera_ctl.set_zoom(0.36)
	await _settle()
	await _shot("age%d_village" % age)
	world.view.show_overlay = true
	world.view.queue_redraw()
	await _settle()
	await _shot("age%d_overlay" % age)
	world.view.show_overlay = false
	if age == 4:
		ok = await _wait_until(func():
			var v: Dictionary = _village_with(world, func(x): return str(x["id"]) == str(target["id"]))
			return not v.is_empty() and v.has("ops") and int(v["ops"].get("units_made", 0)) >= 1, 240.0)
		_check(ok, "age 4: the ground factory mustered a unit from silicon and lead")
		world.camera_ctl.set_zoom(0.62)
		await _settle()
		await _shot("age4_factory_unit")
		var v4: Dictionary = _village_with(world, func(x): return str(x["id"]) == str(target["id"]))
		var pipes := 0
		var wet := 0
		for g in v4.get("ops", {}).get("segments", []):
			if str(g.get("kind", "")) == "pipe":
				pipes += 1
				if float(g.get("fill", 0.0)) > 0.0:
					wet += 1
		print("AGES_WATER pipes=%d carrying=%d" % [pipes, wet])
	_check(world.ui_state()["missing_art"].is_empty(), "age %d: no missing art (%s)" % [age, str(world.ui_state()["missing_art"])])
	world.set_speed(1)
	lan.stop_local_host()
	lan.reset()
	await _frames(10)


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = ProjectSettings.globalize_path("res://").path_join("../docs/evidence/god_world/headed_ages")
	var runs := OS.get_environment("DMB_RUNS_DIR")
	if runs == "":
		OS.set_environment("DMB_RUNS_DIR", OS.get_user_data_dir().path_join("god_world_ages_runs_%d" % (Time.get_ticks_msec() % 100000)))
	preload("res://client/scripts/save_data.gd").set_setting("god_zoom", 0.5)
	get_root().size = Vector2i(450, 800)
	DisplayServer.window_set_size(Vector2i(450, 800))
	var ages_wanted := OS.get_environment("HYBRID_AGES")
	var ages: Array = [2, 3, 4] if ages_wanted == "" else Array(ages_wanted.split(",")).map(func(s): return int(s))
	for age in ages:
		await _run_age(int(age))
	OS.set_environment("DMB_GOD_START_AGE", "")
	if _fails.is_empty():
		print("GOD_AGES_OK")
	else:
		print("GOD_AGES_FAILED %s" % str(_fails))
	quit()
