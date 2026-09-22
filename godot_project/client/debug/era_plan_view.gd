extends Control
class_name DmbEraPlanView

## Era before/after assignment inspector (T140).

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
	_label.text = "[b]Era Plan View[/b]"


func show_assignment(before: Dictionary, after: Dictionary) -> Dictionary:
	var conserved := true
	for key in before.keys():
		if key.begins_with("person:") or key.begins_with("quest:"):
			if not after.has(key):
				conserved = false
	_label.text = "[b]Before[/b] %s\n[b]After[/b] %s\nconserved=%s" % [str(before), str(after), conserved]
	return {"ok": true, "conserved": conserved}
