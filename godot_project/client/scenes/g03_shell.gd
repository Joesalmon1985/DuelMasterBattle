extends "res://client/scenes/g02_shell.gd"

const IndustryView = preload("res://client/debug/industry_view.gd")
const WorkerControllerScript = preload("res://client/world/worker_controller.gd")
const G03_SAVE_SLOT := "g03_playtest"

var _workers
var _worker_phase := 0.0
var _manual_path_block := false


func _ready() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-INDUSTRY")
	OS.set_environment("DMB_SEED", "303")
	super()
	if _economy:
		_economy.queue_free()
	_economy = IndustryView.new()
	_ui_root.add_child(_economy)
	_economy.bind_client(_client)
	_economy.action_requested.connect(_on_industry_action)
	_economy.worker_path_toggled.connect(func(blocked): _manual_path_block = blocked)
	_workers = WorkerControllerScript.new()
	_world_host.add_child(_workers)
	_set_status("Python-backed FX-INDUSTRY — production continues in unpaused Game Time")
	_prompt.text = "Walk through the worker's route; use the Industry panel for real damage, strike, and paid repair."


func _process(delta: float) -> void:
	super(delta)
	if _workers == null or _economy == null:
		return
	var view: Dictionary = _economy._last_view
	if view.is_empty():
		return
	var rows: Array = view.get("industry_workers", [])
	_workers.apply_projection(rows)
	_worker_phase = fmod(_worker_phase + delta * 0.7, 1.0)
	var wizard: Array = _area.wizard_grid() if _area else [99, 99]
	for row_variant in rows:
		var row: Dictionary = row_variant
		var person_id := str(row.get("person_id", ""))
		var worker: Node2D = _workers.worker_for_person(person_id)
		if worker == null:
			continue
		if worker.get_child_count() == 0:
			var body := Polygon2D.new()
			body.polygon = PackedVector2Array([
				Vector2(-13, -20), Vector2(13, -20), Vector2(17, 18), Vector2(-17, 18)
			])
			body.color = Color(0.95, 0.65, 0.18)
			worker.add_child(body)
			var tag := Label.new()
			tag.text = "Worker\n%s" % person_id.right(6)
			tag.position = Vector2(-32, -54)
			worker.add_child(tag)
		var path_x := 4.0 + _worker_phase * 5.0
		var standing_in_path: bool = abs(float(wizard[1]) - 3.0) < 0.8 and abs(float(wizard[0]) - path_x) < 1.0
		if _manual_path_block or standing_in_path:
			worker.position = Vector2(path_x * 64.0 + 32.0, 3.0 * 64.0 + 32.0)
			worker.set_meta("industry_cue", "idle")
		else:
			worker.position = Vector2(path_x * 64.0 + 32.0, 3.0 * 64.0 + 32.0)


func _on_industry_action(action: String) -> void:
	var reply := _cmd("Interact", {"action": action})
	if str(reply.get("status", "")) == "ACCEPTED":
		_prompt.text = "%s accepted by Python. Watch rates, carry, health, and worker cue." % action
	else:
		_prompt.text = "%s rejected: %s" % [action, reply.get("public_feedback", reply.get("code", "?"))]


func _on_save() -> void:
	_sync_pose()
	var reply := _cmd("Save", {"slot": G03_SAVE_SLOT})
	if str(reply.get("status", "")) == "ACCEPTED":
		_prompt.text = "Saved isolated slot %s" % G03_SAVE_SLOT


func _on_load() -> void:
	var reply := _cmd("Load", {"slot": G03_SAVE_SLOT})
	if str(reply.get("status", "")) == "ACCEPTED":
		_paused = false
		_bridge_down = false
		_refresh_counters(true)
		_apply_movement_gate()
		_prompt.text = "Loaded %s — worker ID/job and exact carry restored" % G03_SAVE_SLOT
