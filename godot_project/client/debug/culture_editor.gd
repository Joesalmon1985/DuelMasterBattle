extends Control
class_name DmbCultureEditor

## Developer-only culture/era definition form (T139).
## Validates before compile; release player UI stays minimal.

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
	_label.text = "[b]Culture Editor[/b]\nAuthoring-only. Preview uses the same WorldSim runtime."


func preview_culture(data: Dictionary) -> Dictionary:
	if data.is_empty():
		return {"ok": false, "error": "empty culture payload"}
	if not data.has("era_id"):
		return {"ok": false, "error": "missing era_id"}
	return {"ok": true, "era_id": data["era_id"], "live_save": false}


func commit_forbidden_live_save(_data: Dictionary) -> Dictionary:
	return {"ok": false, "error": "culture edits cannot replace live save fields"}
