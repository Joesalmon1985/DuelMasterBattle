extends RefCounted
class_name DmbLocalBattle

## Leased local tactical encounter (C07 / T063).
## 50 ms steps; sprites bind persistent unit IDs; checkpoints/casualties.

const CombatMath = preload("res://client/combat/combat_math.gd")
const STEP_MS := 50

var lease_id: String = ""
var lease_version: int = 0
var step_index: int = 0
var units: Dictionary = {}  # unit_id -> state dict
var buildings: Dictionary = {}
var cover_by_target: Dictionary = {}
var blockers: Array = []
var pending_destructions: Array = []
var pending_reinforcements: Array = []
var closed: bool = false


func bind_lease(grant: Dictionary) -> void:
	lease_id = str(grant.get("lease_id", ""))
	lease_version = int(grant.get("version", 0))
	var snap: Dictionary = grant.get("snapshot", grant.get("checkpoint", {}))
	units = (snap.get("units", {}) as Dictionary).duplicate(true)
	buildings = (snap.get("buildings", {}) as Dictionary).duplicate(true)
	cover_by_target = (snap.get("cover_by_target", {}) as Dictionary).duplicate(true)
	blockers = (snap.get("blockers", []) as Array).duplicate(true)
	step_index = 0
	closed = false


func unit_ids() -> Array:
	return units.keys()


func step() -> Dictionary:
	if closed:
		return {"error": "closed"}
	# Apply pending destruction at 50 ms boundary.
	for target_id in pending_destructions:
		_destroy_local(str(target_id))
	pending_destructions.clear()
	for rein in pending_reinforcements:
		var uid := str(rein.get("id", ""))
		if uid != "" and not units.has(uid):
			units[uid] = rein.duplicate(true)
	pending_reinforcements.clear()

	var result: Dictionary = CombatMath.resolve_combat_step(units, STEP_MS, cover_by_target)
	step_index += 1
	return {
		"lease_id": lease_id,
		"step_index": step_index,
		"damages": result.get("damages", {}),
		"events": result.get("events", []),
		"fired": result.get("fired", []),
	}


func queue_destruction(target_id: String) -> void:
	pending_destructions.append(target_id)


func queue_reinforcement(unit_state: Dictionary) -> void:
	pending_reinforcements.append(unit_state.duplicate(true))


func checkpoint() -> Dictionary:
	return {
		"lease_id": lease_id,
		"version": lease_version + 1,
		"step_index": step_index,
		"units": units.duplicate(true),
		"buildings": buildings.duplicate(true),
		"casualties": _casualty_ids(),
		"building_damage": _building_damage(),
	}


func close(result: Dictionary = {}) -> Dictionary:
	closed = true
	var cp := checkpoint()
	cp["result"] = result
	return cp


func _destroy_local(target_id: String) -> void:
	if units.has(target_id):
		var u: Dictionary = units[target_id]
		u["alive"] = false
		u["current_health"] = 0
		u["status"] = "dead"
		units[target_id] = u
	elif buildings.has(target_id):
		var b: Dictionary = buildings[target_id]
		b["alive"] = false
		b["current_health"] = 0
		b["health"] = 0
		buildings[target_id] = b


func _casualty_ids() -> Array:
	var out: Array = []
	for uid in units.keys():
		var u: Dictionary = units[uid]
		if not bool(u.get("alive", true)) or int(u.get("current_health", 0)) <= 0:
			out.append(uid)
	out.sort()
	return out


func _building_damage() -> Dictionary:
	var out: Dictionary = {}
	for bid in buildings.keys():
		var b: Dictionary = buildings[bid]
		out[bid] = {
			"current_health": int(b.get("current_health", b.get("health", 0))),
			"alive": bool(b.get("alive", true)),
		}
	return out
