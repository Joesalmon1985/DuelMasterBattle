extends Control
class_name DmbPolicyView

## Developer-only faction legal candidate / policy scores (T139).

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
	_label.text = "[b]Policy View[/b]\nLegal candidate scores from authoritative state."


func render_scores(state: Dictionary) -> void:
	var factions: Variant = state.get("factions", {})
	var text := "[b]Policy / legal candidates[/b]\n"
	if typeof(factions) == TYPE_DICTIONARY:
		for fid in factions.keys():
			text += "%s\n" % str(fid)
	else:
		text += "(connect to WorldState for live scores)\n"
	text += "Debug-only knowledge never leaks into release UI."
	_label.text = text
