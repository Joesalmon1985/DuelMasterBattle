extends RefCounted
class_name WorldFlow

const Migrated = preload("res://client/core/migrated_runtime.gd")
## Client bridge to the headless world sim. Owns: creating/restoring the sim from
## the adventure save, advancing one world turn per node→node walk, and applying
## John's victories as treatments. Overworld only ever *reads* areas from here.
##
## In the G01 migrated runtime (Migrated.active) strategic tick and
## campaign world-save writers are disabled; Python owns durable world state.

var sim: DmbWorldSim
var _adv: Node
## Optional fixture hook: Callable(area: Dictionary, nid: int) -> Dictionary.
## Used by the dungeon-world spatial test only; production leaves this empty.
static var test_augment: Callable = Callable()


func setup(adv: Node) -> void:
	_adv = adv
	if Migrated.active:
		sim = null
		return
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
	if Migrated.active:
		push_error("WorldFlow._store blocked: migrated runtime disables Godot world saves")
		return
	_adv.state["world"] = var_to_str(sim.to_dict())


static func is_world_area(id: String) -> bool:
	return id == "wn_home" or DmbNodeProjection.is_world_area(id)


func resolve(id: String) -> int:
	if Migrated.active:
		push_error("WorldFlow.resolve blocked in migrated runtime")
		return -1
	if id == "wn_home":
		return sim.player_home_node()
	return DmbNodeProjection.node_of(id)


## Entering a node. Moving to a *different* node costs one world turn; re-entering
## the same node (reload, return from battle) does not.
func enter(id: String) -> Dictionary:
	if Migrated.active:
		push_error("WorldFlow.enter/advance_turn blocked: Python owns strategic turns")
		return {}
	var nid := resolve(id)
	var last: int = int(_adv.state.get("world_node", -1))
	if last >= 0 and last != nid:
		sim.advance_turn()
	_adv.state["world_node"] = nid
	_store()
	return _maybe_augment(DmbNodeProjection.area_for(sim, nid, _adv.state), nid)


func area_for(id: String) -> Dictionary:
	if Migrated.active:
		return {}
	var nid := resolve(id)
	return _maybe_augment(DmbNodeProjection.area_for(sim, nid, _adv.state), nid)


func _maybe_augment(area: Dictionary, nid: int) -> Dictionary:
	if test_augment.is_valid():
		return test_augment.call(area, nid)
	return area


## John beat a demon standing for hex `world_hex`: one piece leaves the board.
func on_victory(req: Dictionary) -> void:
	if Migrated.active:
		push_error("WorldFlow.on_victory blocked in migrated runtime")
		return
	var hid := int(req.get("world_hex", -1))
	if hid < 0:
		return
	sim.infection.treat(hid)
	_store()


func last_events_text() -> Array:
	if Migrated.active or sim == null:
		return []
	var out: Array = []
	for e in sim.last_events:
		out.append(sim.describe(e))
	return out


## Only the events a traveller would hear about: places founded, walled or opened.
func notable_events_text() -> Array:
	if Migrated.active or sim == null:
		return []
	var out: Array = []
	for e in sim.last_events:
		if str(e["type"]) in ["settlement", "city", "cave", "epidemic"]:
			out.append(sim.describe(e))
	return out
