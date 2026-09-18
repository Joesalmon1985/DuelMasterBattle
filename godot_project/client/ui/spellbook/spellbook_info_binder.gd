extends RefCounted
class_name SpellbookInfoBinder

## Non-debug gameplay information binder — accepts plain dictionaries only.

const ModelScript = preload("res://client/ui/spellbook/spellbook_model.gd")


static func bind_player_info(model, info: Dictionary) -> void:
	## info keys: title, status, details (String), notes (String)
	if model == null:
		return
	model.title = str(info.get("title", "Chronicle"))
	model.set_live(
		str(info.get("status", "")),
		str(info.get("details", "")),
		str(info.get("notes", "")),
		bool(info.get("paused", false))
	)
	model.set_pages([{
		"id": "info",
		"title": "Info",
		"kind": "info",
		"body": str(info.get("body", info.get("details", ""))),
		"actions": [],
	}], "info")
	model.set_connection(ModelScript.ConnState.READY)
