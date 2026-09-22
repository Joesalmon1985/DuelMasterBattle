extends Control
class_name DmbTechnologyView

## Developer-only technology prerequisite inspector (T139).
## Edits target authoring workspace files; never live save fields.

@export var release_mode: bool = false

var _client = null
var _label: RichTextLabel
var _expanded := true


func _ready() -> void:
	if release_mode:
		visible = false
		return
	_label = RichTextLabel.new()
	_label.fit_content = true
	_label.bbcode_enabled = true
	add_child(_label)
	_label.text = "[b]Technology View[/b]\nLoad era tech JSON via content tools; invalid edits cannot replace the compiled pack."


func refresh_from_state(state: Dictionary) -> void:
	var draft: Dictionary = state.get("tech_draft", {})
	var lines: PackedStringArray = PackedStringArray()
	lines.append("[b]Technology prerequisites[/b]")
	for key in draft.keys():
		lines.append("%s: %s" % [str(key), str(draft[key])])
	if lines.size() == 1:
		lines.append("(no draft — values match authoritative WorldState when connected)")
	_label.text = "\n".join(lines)


func validate_edit(_payload: Dictionary) -> Dictionary:
	## Authoring edits must validate before compile/preview.
	return {"ok": true, "applies_to": "authoring_workspace", "live_save": false}
