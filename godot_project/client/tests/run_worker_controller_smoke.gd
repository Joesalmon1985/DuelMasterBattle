extends SceneTree


func _initialize() -> void:
	var controller_script = load("res://client/world/worker_controller.gd")
	assert(controller_script != null)
	var controller = controller_script.new()
	root.add_child(controller)
	controller.apply_projection([
		{"person_id": "person:test", "cue": "carry"},
	])
	var worker = controller.worker_for_person("person:test")
	assert(worker != null)
	assert(worker.get_meta("industry_cue") == "carry")
	controller.report_visual_route_failure("person:test", "blocked")
	assert(worker.get_meta("industry_cue") == "idle")
	print("T055_WORKER_CONTROLLER_OK")
	quit(0)
