extends SceneTree

## T079 semantic label helpers cover all required kinds.
## godot --headless --path godot_project --script res://client/tests/run_t079_semantic_labels.gd

const Labels = preload("res://client/ui/semantic_labels.gd")

var _failures: Array = []


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	for kind in Labels.REQUIRED_KINDS:
		_assert(Labels.kind_supported(kind), "kind not supported: %s" % kind)
		var fallback := Labels.label_for({"kind": kind, "unknown_identity": true})
		_assert(fallback != "", "fallback empty for %s" % kind)

	var unknown := {"ok": true, "unknown_identity": true, "kind": "person", "targetable": true}
	_assert(Labels.is_targetable(unknown), "unknown identity must remain targetable")
	_assert(Labels.label_for(unknown) == "Person", "unknown person fallback")

	var stale := {"ok": false, "refresh": true, "reason": "stale_world", "targetable": false}
	_assert(Labels.needs_refresh(stale), "stale must need refresh")
	_assert(not Labels.is_targetable(stale), "stale not targetable")

	var dirty := {
		"ok": true,
		"label": "Mill",
		"stocks": {"ore": 9},
		"army_strength": 99,
		"production_rate": 1.5,
	}
	var clean := Labels.strip_hidden_keys(dirty)
	_assert(not clean.has("stocks"), "stocks stripped")
	_assert(not clean.has("army_strength"), "army_strength stripped")
	_assert(not clean.has("production_rate"), "production_rate stripped")
	_assert(clean.get("label") == "Mill", "label retained")

	if _failures.is_empty():
		print("T079_SEMANTIC_LABELS_OK")
		quit(0)
	else:
		for f in _failures:
			push_error(str(f))
		print("T079_SEMANTIC_LABELS_FAIL count=", _failures.size())
		quit(1)


func _assert(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)
