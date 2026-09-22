extends Control
class_name DmbSemanticKnowledgeInspector

## Observer knowledge selector for dialogue/content preview (T140).

@export var release_mode: bool = false

var _label: RichTextLabel
var _observer := "player"


func _ready() -> void:
	if release_mode:
		visible = false
		return
	_label = RichTextLabel.new()
	_label.fit_content = true
	add_child(_label)
	_refresh()


func set_observer(observer_id: String) -> void:
	_observer = observer_id
	_refresh()


func _refresh() -> void:
	_label.text = "Observer: %s\nDebug knowledge views never leak into release UI." % _observer


func filter_facts(facts: Array, allowed: Array) -> Array:
	var out: Array = []
	for f in facts:
		if f in allowed:
			out.append(f)
	return out
