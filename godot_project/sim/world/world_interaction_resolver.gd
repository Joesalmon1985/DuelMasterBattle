extends RefCounted
class_name WorldInteractionResolver

## Pure semantic interaction resolver. No rendering, no fixture names, no quests.
## Reads the generic semantic contract and WorldKnowledge. Never writes either.

const _Knowledge = preload("res://sim/world/world_knowledge.gd")


## `level_override` >= 0 supplies the knowledge level directly, for callers bound
## to filtered bridge views instead of the legacy Adventure knowledge bag.
static func resolve(semantic: Dictionary, adv: Node, in_range: bool = false, level_override: int = -1) -> Dictionary:
	var key := str(semantic.get("knowledge_key", ""))
	var level := 0
	if level_override >= 0:
		level = level_override
	elif adv != null and key != "":
		level = _Knowledge.get_level(adv, key)
	return {
		"label": _label_for(semantic.get("labels", []), level),
		"observe_far": str(semantic.get("observe_far", "")),
		"observe_near": str(semantic.get("observe_near", "")),
		"interaction": str(semantic.get("interaction", "")),
		"mode": "interact" if in_range and str(semantic.get("interaction", "")) != "" else "observe",
		"dismiss_on_move": bool(semantic.get("dismiss_on_move", true)),
	}


static func _label_for(labels, knowledge_level: int) -> String:
	if not (labels is Array) or (labels as Array).is_empty():
		return ""
	var best_text := ""
	var best_level := -1
	var lowest_text := ""
	var lowest_level := 0
	var have_lowest := false
	for raw in labels:
		if not (raw is Dictionary):
			continue
		var entry: Dictionary = raw
		var lv := int(entry.get("level", 0))
		var text := str(entry.get("text", ""))
		if not have_lowest or lv < lowest_level:
			lowest_text = text
			lowest_level = lv
			have_lowest = true
		if lv <= knowledge_level and lv > best_level:
			best_text = text
			best_level = lv
	if best_level < 0:
		return lowest_text
	return best_text
