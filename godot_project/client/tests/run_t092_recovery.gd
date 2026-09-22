extends SceneTree

## T092 duel recovery presenter smoke.
## godot --headless --path godot_project --script res://client/tests/run_t092_recovery.gd

const Recovery = preload("res://client/duel/recovery.gd")

var _failures: Array = []


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	var ui = Recovery.new()
	ui.apply_checkpoint({
		"duel_id": "lease:1",
		"checkpoint_version": 2,
		"checkpoint": {"next_feedback": {"exact": 1, "colour_only": 2}, "secret": [0, 0, 1, 2]},
	})
	_assert(ui.lease_id == "lease:1", "lease")
	_assert(ui.checkpoint_version == 2, "version")
	_assert(int(ui.next_feedback().get("exact", -1)) == 1, "feedback")
	ui.apply_recovery({"node_id": "n3", "kind": "friendly"})
	_assert(str(ui.last_recovery.get("kind", "")) == "friendly", "recovery kind")
	if _failures.is_empty():
		print("T092_RECOVERY_OK")
		quit(0)
	else:
		for f in _failures:
			push_error(str(f))
		print("T092_RECOVERY_FAIL")
		quit(1)


func _assert(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)
