extends RefCounted
class_name DmbSemanticLabels

## Client-side label helpers aligned with SemanticResolver public names (T079).

const REQUIRED_KINDS := [
	"person",
	"building",
	"unit",
	"cart",
	"road",
	"item",
	"mechanism",
	"entrance",
	"hazard",
]


static func label_for(view: Dictionary) -> String:
	if view.has("label") and str(view.get("label")) != "":
		return str(view["label"])
	if bool(view.get("unknown_identity", false)):
		return _kind_fallback(str(view.get("kind", "")))
	if not bool(view.get("known", true)):
		return "Unknown"
	if view.get("name") != null and str(view.get("name")) != "":
		return str(view["name"])
	var fac := str(view.get("faction_id", ""))
	var colour := _faction_colour(fac)
	var arch := str(view.get("archetype", ""))
	if arch != "":
		return ("%s %s" % [colour, _archetype_label(arch)]).strip_edges()
	if view.get("role") != null:
		return str(view["role"])
	return str(view.get("display_name", _kind_fallback(str(view.get("kind", "")))))


static func _kind_fallback(kind: String) -> String:
	match kind:
		"person":
			return "Person"
		"building":
			return "Building"
		"unit":
			return "Soldier"
		"cart":
			return "Cart"
		"road":
			return "Road"
		"item":
			return "Item"
		"mechanism":
			return "Mechanism"
		"entrance":
			return "Door"
		"hazard":
			return "Hazard"
		_:
			return "Unknown"


static func is_targetable(view: Dictionary) -> bool:
	if view.has("targetable"):
		return bool(view["targetable"])
	# Unknown identity remains targetable when the entity still exists.
	if bool(view.get("refresh", false)) and not bool(view.get("ok", true)):
		return false
	return bool(view.get("ok", true)) or bool(view.get("unknown_identity", false))


static func needs_refresh(view: Dictionary) -> bool:
	return bool(view.get("refresh", false)) or str(view.get("reason", "")) in ["stale_world", "missing_entity"]


static func strip_hidden_keys(view: Dictionary) -> Dictionary:
	var out := view.duplicate(true)
	for key in ["stocks", "stock", "economy", "production_rate", "army_strength", "unit_count", "formation_strength", "hidden_strength", "secret_inventory", "leases", "command_receipts", "rng", "knowledge_raw"]:
		out.erase(key)
	return out


static func kind_supported(kind: String) -> bool:
	return REQUIRED_KINDS.has(kind)


static func _faction_colour(faction_id: String) -> String:
	match faction_id:
		"faction:red":
			return "Red"
		"faction:blue":
			return "Blue"
		_:
			if faction_id.begins_with("faction:"):
				return faction_id.substr(8).capitalize()
			return ""


static func _archetype_label(archetype: String) -> String:
	match archetype:
		"line":
			return "Line"
		"skirmisher":
			return "Skirmisher"
		"heavy":
			return "Heavy"
		_:
			return archetype.capitalize()


static func tile_distance(a: Variant, b: Variant) -> float:
	if typeof(a) != TYPE_ARRAY and typeof(a) != TYPE_PACKED_FLOAT32_ARRAY and typeof(a) != TYPE_PACKED_FLOAT64_ARRAY:
		if typeof(a) != TYPE_VECTOR2:
			return -1.0
	if typeof(b) != TYPE_ARRAY and typeof(b) != TYPE_PACKED_FLOAT32_ARRAY and typeof(b) != TYPE_PACKED_FLOAT64_ARRAY:
		if typeof(b) != TYPE_VECTOR2:
			return -1.0
	var ax := 0.0
	var ay := 0.0
	var bx := 0.0
	var by := 0.0
	if typeof(a) == TYPE_VECTOR2:
		ax = a.x
		ay = a.y
	else:
		ax = float(a[0])
		ay = float(a[1])
	if typeof(b) == TYPE_VECTOR2:
		bx = b.x
		by = b.y
	else:
		bx = float(b[0])
		by = float(b[1])
	return maxf(absf(ax - bx), absf(ay - by))


static func in_interaction_range(wizard_pos: Variant, target_pos: Variant, range_tiles: float = 2.0) -> bool:
	var d := tile_distance(wizard_pos, target_pos)
	if d < 0.0:
		return false
	return d <= range_tiles
