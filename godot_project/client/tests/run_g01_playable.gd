extends SceneTree

## Assert local wizard movement survives projection refreshes and corridor is open.

const Migrated = preload("res://client/core/migrated_runtime.gd")
const FxArea = preload("res://client/world/fx_clock_area.gd")
const TILE := 64.0


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
	if not area.is_cell_blocked(Vector2i(7, 7)):
		push_error("fixture tree missing")
		quit(1)
		return
	for cell in [Vector2i(5, 5), Vector2i(9, 5), Vector2i(12, 5)]:
		if area.is_cell_blocked(cell):
			push_error("exit corridor blocked at %s" % cell)
			quit(1)
			return
	var start: Vector2 = area.wizard_position()
	area.set_movement_enabled(true)
	area._move_dir = Vector2(1, 0)
	for _i in range(30):
		area._process(0.05)
	var after_walk: Vector2 = area.wizard_position()
	if after_walk.x <= start.x + 8.0:
		push_error("wizard did not move with pad direction")
		quit(1)
		return
	for _j in range(5):
		area.apply_projections(stub.request_view("player"))
	if area.wizard_position().distance_to(after_walk) > 0.01:
		push_error("apply_projections reset wizard pose")
		quit(1)
		return
	# Walk the open corridor to the exit (axis pad, no teleport).
	var exit_id := area.nearest_exit_id()
	var exit_pos: Vector2 = area._exit_nodes[exit_id].position
	var approach := Vector2(exit_pos.x - TILE, 5.0 * TILE + TILE * 0.5)
	if not _walk_to(area, approach, 8.0, 40.0):
		push_error("could not walk corridor toward exit")
		quit(1)
		return
	if not _walk_to(area, exit_pos, 4.0, 50.0):
		push_error("could not reach exit by walking the open corridor (pos=%s exit=%s)" % [area.wizard_position(), exit_pos])
		quit(1)
		return
	if not area.exit_in_range(exit_id):
		push_error("exit still out of range")
		quit(1)
		return
	var hint := area.compute_action_hint()
	if hint != "Travel":
		push_error("expected Travel hint near exit, got %s" % hint)
		quit(1)
		return
	print("G01_PLAYABLE_OK moved=%.1f hint=%s" % [area.wizard_position().distance_to(start), hint])
	quit(0)


func _walk_to(area, target: Vector2, timeout_s: float, arrive_px: float) -> bool:
	var elapsed := 0.0
	while elapsed < timeout_s:
		var pos: Vector2 = area.wizard_position()
		var delta_v: Vector2 = target - pos
		if delta_v.length() <= arrive_px:
			area._move_dir = Vector2.ZERO
			return true
		if absf(delta_v.x) >= absf(delta_v.y):
			area._move_dir = Vector2(signf(delta_v.x), 0)
		else:
			area._move_dir = Vector2(0, signf(delta_v.y))
		area._process(0.05)
		elapsed += 0.05
	area._move_dir = Vector2.ZERO
	return area.wizard_position().distance_to(target) <= arrive_px
