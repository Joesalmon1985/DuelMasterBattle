class_name WorkerController
extends Node2D

## Disposable worker presentation keyed by persistent Python person IDs.
## Navigation and culling never report production commands.

signal layout_diagnostic(person_id: String, message: String)

var _workers: Dictionary = {}


func apply_projection(rows: Array) -> void:
	var present: Dictionary = {}
	for row_variant in rows:
		var row: Dictionary = row_variant
		var person_id := str(row.get("person_id", ""))
		if person_id.is_empty():
			continue
		present[person_id] = true
		var worker: Node2D = _workers.get(person_id)
		if worker == null:
			worker = Node2D.new()
			worker.name = "Worker_%s" % person_id.validate_node_name()
			worker.set_meta("person_id", person_id)
			add_child(worker)
			_workers[person_id] = worker
		worker.set_meta("industry_cue", str(row.get("cue", "idle")))
	for person_id in _workers.keys():
		if not present.has(person_id):
			_workers[person_id].queue_free()
			_workers.erase(person_id)


func report_visual_route_failure(person_id: String, detail: String) -> void:
	var worker: Node2D = _workers.get(person_id)
	if worker != null:
		worker.set_meta("industry_cue", "idle")
	layout_diagnostic.emit(person_id, "worker_layout_route_failed:%s" % detail)


func worker_for_person(person_id: String) -> Node2D:
	return _workers.get(person_id)
