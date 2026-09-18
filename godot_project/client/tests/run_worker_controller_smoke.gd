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
			"person_id": "person:berry",
			"name": "Carrier-berry",
			"job_id": "job:carrier",
			"role": "carrier",
			"cue": "carrying",
			"activity": "carrying",
			"resource_label": "Foraged berries and nuts",
			"marker": {"symbol": "B", "label": "Berries"},
			"from_id": "source:woodland",
			"to_id": "processor:fx-industry",
			"waypoints": [
				{"id": "source:woodland", "kind": "from", "grid": [2, 3]},
				{"id": "processor:fx-industry", "kind": "to", "grid": [6, 4]},
			],
			"return_waypoints": [
				{"id": "processor:fx-industry", "kind": "to", "grid": [6, 4]},
				{"id": "source:woodland", "kind": "from", "grid": [2, 3]},
			],
		},
		{
			"person_id": "person:flint",
			"name": "Carrier-flint",
			"job_id": "job:carrier",
			"role": "carrier",
			"cue": "carrying",
			"activity": "carrying",
			"resource_label": "Flint",
			"marker": {"symbol": "F", "label": "Flint"},
			"from_id": "source:ore",
			"to_id": "processor:fx-industry",
			"waypoints": [
				{"id": "source:ore", "kind": "from", "grid": [11, 3]},
				{"id": "processor:fx-industry", "kind": "to", "grid": [6, 4]},
			],
			"return_waypoints": [
				{"id": "processor:fx-industry", "kind": "to", "grid": [6, 4]},
				{"id": "source:ore", "kind": "from", "grid": [11, 3]},
			],
		},
	])
	var berry = controller.worker_for_person("person:berry")
	var flint = controller.worker_for_person("person:flint")
	if berry == null or flint == null:
		push_error("carriers missing")
		quit(1)
		return
	var berry_start: Vector2 = berry.position
	controller.set_frozen(false)
	controller.set_manual_path_block(false)
	controller.set_wizard_world_position(Vector2(9999, 9999))
	for _i in range(10):
		controller.tick(0.2)
	if berry.position.distance_to(berry_start) <= 0.5:
		push_error("berry carrier did not move")
		quit(1)
		return
	# Must not teleport to the flint origin.
	if berry.position.distance_to(flint.position) < 8.0:
		push_error("carriers collapsed onto one tour")
		quit(1)
		return
	controller.set_manual_path_block(true)
	controller.tick(0.2)
	if str(berry.get_meta("industry_cue")) != "blocked":
		push_error("expected blocked cue")
		quit(1)
		return
	var frozen_pos: Vector2 = berry.position
	controller.set_frozen(true)
	controller.tick(1.0)
	if berry.position.distance_to(frozen_pos) > 0.01:
		push_error("frozen carrier moved")
		quit(1)
		return
	print("T055_WORKER_CONTROLLER_OK")
	quit(0)
