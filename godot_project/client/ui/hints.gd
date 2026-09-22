extends RefCounted
class_name DmbHints

## Optional contextual hints. Turning off never blocks required actions.

const HINTS_PATH := "res://content/source/dialogue/tutorial/hints.json"

var _enabled := true
var _show_spoilers := false
var _lines: Array = []


func _init() -> void:
	_load()


func set_enabled(on: bool) -> void:
	_enabled = on


func set_spoilers(on: bool) -> void:
	_show_spoilers = on


func is_enabled() -> bool:
	return _enabled


func lines_for(topic: String = "") -> Array:
	if not _enabled:
		return []
	var out: Array = []
	for raw in _lines:
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var row: Dictionary = raw
		if bool(row.get("spoiler", false)) and not _show_spoilers:
			continue
		if topic != "" and str(row.get("topic", "")) != topic:
			continue
		out.append(row)
	return out


func _load() -> void:
	if not FileAccess.file_exists(HINTS_PATH):
		_lines = []
		return
	var f := FileAccess.open(HINTS_PATH, FileAccess.READ)
	var data = JSON.parse_string(f.get_as_text())
	if typeof(data) == TYPE_DICTIONARY:
		_lines = data.get("lines", [])
	else:
		_lines = []
