extends RefCounted
class_name WorldKnowledge

## Canonical World Understanding knowledge. Levels live in Adventure.state["knowledge"],
## keyed by stable semantic ids. Learning only raises a level; it never lowers one.


static func get_level(adv: Node, key: String) -> int:
	var bag := _bag(adv)
	if bag == null or not bag.has(key):
		return 0
	return int(bag[key])


## Raise knowledge to `level` when that is higher than the stored level.
## Returns true only when canonical state changed.
static func learn(adv: Node, key: String, level: int) -> bool:
	if key == "" or level <= get_level(adv, key):
		return false
	if not adv.state.has("knowledge") or not (adv.state["knowledge"] is Dictionary):
		adv.state["knowledge"] = {}
	adv.state["knowledge"][key] = int(level)
	if adv.has_signal("state_changed"):
		adv.state_changed.emit()
	return true


static func knows(adv: Node, key: String, minimum_level: int) -> bool:
	return get_level(adv, key) >= minimum_level


static func _bag(adv: Node) -> Dictionary:
	if adv == null or not (adv.state is Dictionary):
		return {}
	var bag = adv.state.get("knowledge", {})
	if bag is Dictionary:
		return bag
	return {}
