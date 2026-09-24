extends Control
class_name DmbPuzzleEditor

## Puzzle layout / state / solution trace inspector (T140).

@export var release_mode: bool = false

var _label: RichTextLabel


func _ready() -> void:
	if release_mode:
		visible = false
		return
	_label = RichTextLabel.new()
	_label.fit_content = true
	_label.bbcode_enabled = true
	add_child(_label)
	_label.text = "[b]Puzzle Editor[/b]\nSolution traces from dungeon puzzle.json."


func load_trace(puzzle: Dictionary) -> Dictionary:
	var trace: Array = puzzle.get("solution_trace", [])
	var recovery: Array = puzzle.get("recovery_trace", [])
	if trace.is_empty():
		return {"ok": false, "error": "missing solution_trace"}
	_label.text = "[b]Solution[/b]\n%s\n[b]Recovery[/b]\n%s" % [str(trace), str(recovery)]
	return {"ok": true, "steps": trace.size(), "recovery_steps": recovery.size()}
