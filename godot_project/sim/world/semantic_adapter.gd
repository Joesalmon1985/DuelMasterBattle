extends RefCounted
class_name SemanticAdapter

## Generic semantic contract for meaningful Overworld interactables.
## Authored entity["semantic"] always wins. Fallbacks use only already-visible fields.
## No fixture names. No invented lore.

const _Bestiary = preload("res://sim/bestiary.gd")

const SKIP_KINDS := ["trigger", "deco", "burnt"]


static func adapt(entity: Dictionary, area_id: String = "") -> Dictionary:
	if entity.get("semantic") is Dictionary and not (entity["semantic"] as Dictionary).is_empty():
		return (entity["semantic"] as Dictionary).duplicate(true)
	var kind := str(entity.get("kind", ""))
	if kind == "" or kind in SKIP_KINDS:
		return {}
	if kind == "exit" and not _exit_is_meaningful(entity):
		return {}
	var label := _label_text(entity, kind)
	if label == "":
		return {}
	var key := "sem:%s:%s:%s" % [area_id, kind, str(entity.get("id", label.to_lower()))]
	return {
		"knowledge_key": key,
		"labels": [{"level": 0, "text": label}],
		"observe_far": _observe(entity, kind, label),
		"observe_near": "",
		"interaction": _interaction(entity, kind),
		"dismiss_on_move": true,
	}


static func _exit_is_meaningful(entity: Dictionary) -> bool:
	if str(entity.get("travel_text", "")) != "":
		return true
	if str(entity.get("to_area", "")) != "":
		return true
	return str(entity.get("id", "")).ends_with("_door")


static func _interaction(entity: Dictionary, kind: String) -> String:
	match kind:
		"npc":
			return "npc"
		"creature", "wizard":
			return "enemy"
		"door":
			return "entrance" if str(entity.get("dungeon_id", "")) != "" else "door"
		"exit":
			return "entrance"
		"sign":
			if entity.has("puzzle_room") or entity.has("puzzle_eid"):
				return "puzzle"
			return "sign"
		"pickup":
			if entity.has("puzzle_room") or entity.has("puzzle_eid") or entity.has("puzzle_action"):
				return "puzzle"
			return "pickup"
		"fire":
			return "fire"
		"logs":
			if entity.has("puzzle_action") or entity.has("puzzle_room") or entity.has("puzzle_eid"):
				return "puzzle"
			if str(entity.get("building", "")) != "":
				return "building"
			return "object"
		"corpse":
			return "object"
		_:
			return "object"


static func _label_text(entity: Dictionary, kind: String) -> String:
	match kind:
		"npc":
			return _short(str(entity.get("name", "Person")), "Person")
		"creature", "wizard":
			var enemy_id := str(entity.get("enemy_id", entity.get("bestiary_id", "")))
			if enemy_id != "" and _Bestiary.ids().has(enemy_id):
				var enemy := _Bestiary.get_data(enemy_id)
				return _short(str(enemy.get("display_name", "")), "Creature")
			return "Creature"
		"door":
			if str(entity.get("dungeon_id", "")) != "":
				return "Dungeon"
			var building := _title(str(entity.get("building", "")))
			return building if building != "" else "Door"
		"exit":
			return "Door" if str(entity.get("id", "")).ends_with("_door") else "Path"
		"sign":
			return _sign_label(str(entity.get("text", "")))
		"pickup":
			return _short(_title(str(entity.get("sprite", "object")).replace("_", " ")), "Object")
		"fire":
			return "Fire"
		"logs":
			var named := _title(str(entity.get("building", "")))
			if named != "":
				return named
			if entity.has("puzzle_action") or entity.has("puzzle_room"):
				return "Mechanism"
			return "Object"
		"corpse":
			return "Body"
		_:
			return _short(str(entity.get("name", "")), "")


static func _observe(entity: Dictionary, kind: String, label: String) -> String:
	var text := str(entity.get("text", "")).strip_edges()
	if text == "" and kind in ["creature", "wizard"]:
		text = str(entity.get("intro", "")).strip_edges()
	if text == "" and kind == "exit":
		text = str(entity.get("travel_text", "")).strip_edges()
	if text != "" and text.length() <= 180:
		return text
	if text != "":
		return text.substr(0, 177).strip_edges() + "..."
	return "A %s." % label.to_lower()


static func _sign_label(text: String) -> String:
	var line := text.split("\n")[0].strip_edges()
	if line == "":
		return "Sign"
	if line.length() <= 24:
		return _title_if_caps(line)
	return "Sign"


static func _title_if_caps(text: String) -> String:
	if text == text.to_upper():
		return _title(text.to_lower().replace("_", " "))
	return text


static func _title(text: String) -> String:
	var cleaned := text.strip_edges().replace("_", " ")
	if cleaned == "":
		return ""
	var parts := cleaned.split(" ", false)
	var out: Array = []
	for part in parts:
		var s := str(part)
		if s == "":
			continue
		out.append(s.substr(0, 1).to_upper() + s.substr(1))
	return " ".join(out)


static func _short(text: String, fallback: String) -> String:
	var cleaned := text.strip_edges()
	if cleaned == "" or cleaned == "...":
		return fallback
	if cleaned.length() > 24:
		return fallback if fallback != "" else cleaned.substr(0, 24)
	return cleaned
