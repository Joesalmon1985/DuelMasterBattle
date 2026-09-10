extends RefCounted
class_name WorldFlow
## Client bridge to the headless world sim. Owns: creating/restoring the sim from
## the adventure save, advancing one world turn per node→node walk, and applying
## John's victories as treatments. Overworld only ever *reads* areas from here.

var sim: DmbWorldSim
var _adv: Node


func setup(adv: Node) -> void:
	_adv = adv
	if sim != null:
		return
	var packed := str(adv.state.get("world", ""))
	if packed != "":
		var d = str_to_var(packed)
		if typeof(d) == TYPE_DICTIONARY:
			sim = DmbWorldSim.from_dict(d)
	if sim == null:
		sim = DmbWorldSim.new(int(adv.state.get("world_seed", 7)))
		sim.setup()
		_store()


func _store() -> void:
	_adv.state["world"] = var_to_str(sim.to_dict())


static func is_world_area(id: String) -> bool:
	return id == "wn_home" or DmbNodeProjection.is_world_area(id)


func resolve(id: String) -> int:
	if id == "wn_home":
		return sim.player_home_node()
	return DmbNodeProjection.node_of(id)


## Entering a node. Moving to a *different* node costs one world turn; re-entering
## the same node (reload, return from battle) does not.
func enter(id: String) -> Dictionary:
	var nid := resolve(id)
	var last: int = int(_adv.state.get("world_node", -1))
	if last >= 0 and last != nid:
		sim.advance_turn()
	_adv.state["world_node"] = nid
	_store()
	return DmbNodeProjection.area_for(sim, nid, _adv.state)


func area_for(id: String) -> Dictionary:
	return DmbNodeProjection.area_for(sim, resolve(id), _adv.state)


## John beat a demon standing for hex `world_hex`: one piece leaves the board.
func on_victory(req: Dictionary) -> void:
	var hid := int(req.get("world_hex", -1))
	if hid < 0:
		return
	sim.infection.treat(hid)
	_store()


func last_events_text() -> Array:
	var out: Array = []
	for e in sim.last_events:
		out.append(sim.describe(e))
	return out
