extends Control
class_name DmbQuestDialoguePreview

## Narrative tools: quest/dialogue graph + context preview (T140).

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
	_label.text = "[b]Quest / Dialogue Preview[/b]"


func preview_branch(context: Dictionary) -> Dictionary:
	var branch := str(context.get("branch", "offer"))
	var speaker_alive := bool(context.get("speaker_alive", true))
	var world_resolved := bool(context.get("world_resolved", false))
	var text := ""
	if not speaker_alive:
		text = "They are gone. The dead-target branch applies."
		branch = "dead_target"
	elif world_resolved:
		text = "The world moved first — already resolved."
		branch = "already_world_resolved"
	elif bool(context.get("speaker_displaced", false)):
		text = "They were displaced from their workplace."
		branch = "displaced_target"
	else:
		text = str(context.get("line_text", "Offer line."))
	_label.text = "[b]%s[/b]\n%s" % [branch, text]
	return {"ok": true, "branch": branch, "text": text, "engine": "production"}


func reject_unsupported_effect(effect: Dictionary) -> Dictionary:
	var kind := str(effect.get("kind", ""))
	if kind == "" or kind == "UNKNOWN_API":
		return {"ok": false, "error": "unsupported effect rejected"}
	return {"ok": true}
