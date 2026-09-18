extends SceneTree


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	var controller_script = load("res://client/world/worker_controller.gd")
	if controller_script == null:
		push_error("missing worker_controller")
		quit(1)
		return
	var controller = controller_script.new()
	root.add_child(controller)
	controller.apply_projection([
		{
			"person_id": "person:test",
			"name": "FX Worker",
			"job_id": "job:processor",
			"cue": "working",
			"activity": "working",
			"carry_resource": "berries",
			"waypoints": [
				{"id": "source:a", "kind": "source", "grid": [2, 2]},
				{"id": "processor", "kind": "processor", "grid": [6, 3]},
			],
		},
	])
	var worker = controller.worker_for_person("person:test")
	if worker == null:
		push_error("worker missing")
		quit(1)
		return
	var start: Vector2 = worker.position
	controller.set_frozen(false)
	controller.set_manual_path_block(false)
	controller.set_wizard_world_position(Vector2(9999, 9999))
	for _i in range(8):
		controller.tick(0.2)
	if worker.position.distance_to(start) <= 0.5:
		push_error("worker did not move along route")
		quit(1)
		return
	var mid: Vector2 = worker.position
	controller.set_manual_path_block(true)
	controller.tick(0.25)
	if str(worker.get_meta("industry_cue")) != "blocked":
		push_error("expected blocked cue")
		quit(1)
		return
	# Must not snap back to the start of the loop.
	if worker.position.distance_to(Vector2(2 * 64 + 32, 2 * 64 + 32)) < 4.0 and mid.distance_to(start) > 8.0:
		push_error("worker teleported to loop start while blocked")
		quit(1)
		return
	controller.set_manual_path_block(false)
	var frozen_pos: Vector2 = worker.position
	controller.set_frozen(true)
	controller.tick(1.0)
	if worker.position.distance_to(frozen_pos) > 0.01:
		push_error("frozen worker moved")
		quit(1)
		return
	controller.report_visual_route_failure("person:test", "blocked")
	if str(worker.get_meta("industry_cue")) != "waiting":
		push_error("route failure should idle/wait")
		quit(1)
		return
	print("T055_WORKER_CONTROLLER_OK")
	quit(0)
