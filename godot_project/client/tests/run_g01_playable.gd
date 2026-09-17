extends SceneTree

## Assert local wizard movement survives projection refreshes (no full rebuild).

const Migrated = preload("res://client/core/migrated_runtime.gd")
const FxArea = preload("res://client/world/fx_clock_area.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	Migrated.enable()
	var stub = Node.new()
	stub.set_script(load("res://client/tests/g01_view_stub.gd"))
	root.add_child(stub)
	var area = FxArea.new()
	root.add_child(area)
	area.client = stub
	area._build_roots()
	area.rebuild_from_view(stub.request_view("player"))
	if area._wizard == null or area._wizard.texture == null:
		push_error("wizard missing texture")
		quit(1)
		return
	if area._exit_nodes.is_empty():
		push_error("no exits")
		quit(1)
		return
	var start: Vector2 = area.wizard_position()
	area.set_movement_enabled(true)
	area._move_dir = Vector2(1, 0)
	# Simulate several frames of walking.
	for _i in range(30):
		area._process(0.05)
	var after_walk: Vector2 = area.wizard_position()
	if after_walk.x <= start.x + 8.0:
		push_error("wizard did not move with pad direction")
		quit(1)
		return
	var turn_before := int(stub.request_view("player").get("clock", {}).get("turn", 0))
	# Projection refresh must not snap pose back.
	for _j in range(5):
		area.apply_projections(stub.request_view("player"))
	var after_refresh: Vector2 = area.wizard_position()
	if after_refresh.distance_to(after_walk) > 0.01:
		push_error("apply_projections reset wizard pose")
		quit(1)
		return
	var turn_after := int(stub.request_view("player").get("clock", {}).get("turn", 0))
	if turn_after != turn_before:
		push_error("local walk advanced World Turn")
		quit(1)
		return
	# Blocked movement when disabled.
	area.set_movement_enabled(false)
	area._move_dir = Vector2(1, 0)
	var paused_pos := area.wizard_position()
	area._process(0.2)
	if area.wizard_position().distance_to(paused_pos) > 0.01:
		push_error("movement continued while disabled")
		quit(1)
		return
	# Deliberate rebuild restores authoritative pose.
	area.rebuild_from_view(stub.request_view("player"))
	if area.wizard_position().distance_to(start) > 1.0:
		push_error("rebuild_from_view did not restore authoritative pose")
		quit(1)
		return
	print("G01_PLAYABLE_OK moved=%.1f turn=%s" % [after_walk.x - start.x, turn_after])
	quit(0)
