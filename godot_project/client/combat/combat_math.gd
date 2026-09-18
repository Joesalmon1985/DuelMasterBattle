extends RefCounted
class_name DmbCombatMath

## Shared combat math with Python sim/dmb/military/math.py (C07 / T060).
## Golden cases live in res://content/fixtures/combat_math.json.

const COVER_NONE := 0.0
const COVER_PARTIAL := 0.25


static func round_half_up(value: float) -> int:
	if value >= 0.0:
		return int(floor(value + 0.5))
	return int(ceil(value - 0.5))


static func compute_damage(
	base_attack: float,
	era_factor: float = 1.0,
	attack_modifiers: float = 1.0,
	cover: float = 0.0,
	armour: float = 0.0
) -> int:
	if abs(cover - COVER_NONE) > 0.0000001 and abs(cover - COVER_PARTIAL) > 0.0000001:
		push_error("cover must be 0 or 0.25")
		return 1
	var raw: float = base_attack * era_factor * attack_modifiers * (1.0 - cover) - armour
	return maxi(1, round_half_up(raw))


static func distance(a: Vector2, b: Vector2) -> float:
	return a.distance_to(b)


static func in_range(attacker_pos: Vector2, target_pos: Vector2, range_tiles: float) -> bool:
	return distance(attacker_pos, target_pos) <= range_tiles + 0.000000001


static func choose_target(attacker: Dictionary, candidates: Array) -> Variant:
	if not bool(attacker.get("alive", true)):
		return null
	var attacker_id := str(attacker.get("id", ""))
	var faction := str(attacker.get("faction_id", ""))
	var pos := _to_vec2(attacker.get("position", [0, 0]))
	var range_tiles := float(attacker.get("range_tiles", 1))
	var eligible: Array = []
	for cand_any in candidates:
		var cand: Dictionary = cand_any
		var cid := str(cand.get("id", ""))
		if cid == attacker_id:
			continue
		if not bool(cand.get("alive", true)):
			continue
		if bool(cand.get("is_wizard", false)) or str(cand.get("kind", "")) == "wizard":
			continue
		var other_faction := str(cand.get("faction_id", ""))
		if other_faction == faction:
			continue
		var tpos := _to_vec2(cand.get("position", [0, 0]))
		if not in_range(pos, tpos, range_tiles):
			continue
		var dist := distance(pos, tpos)
		var health := int(cand.get("current_health", 0))
		eligible.append({"dist": dist, "health": health, "id": cid})
	if eligible.is_empty():
		return null
	eligible.sort_custom(func(a, b):
		if a["dist"] != b["dist"]:
			return a["dist"] < b["dist"]
		if a["health"] != b["health"]:
			return a["health"] < b["health"]
		return str(a["id"]) < str(b["id"])
	)
	return eligible[0]["id"]


static func gather_step_damage(units: Dictionary, cover_by_target: Dictionary = {}) -> Dictionary:
	var living: Dictionary = {}
	for uid in units.keys():
		var u: Dictionary = units[uid]
		if bool(u.get("alive", true)) and int(u.get("current_health", 0)) > 0:
			living[uid] = u
	var targets: Array = living.values()
	var damages: Dictionary = {}
	var keys: Array = living.keys()
	keys.sort()
	for uid in keys:
		var attacker: Dictionary = living[uid]
		if int(attacker.get("remaining_attack_cooldown_ms", 0)) > 0:
			continue
		var tid = choose_target(attacker, targets)
		if tid == null:
			continue
		var target: Dictionary = living[str(tid)] if living.has(str(tid)) else {}
		for t in targets:
			if str(t.get("id", "")) == str(tid):
				target = t
				break
		var cover := float(cover_by_target.get(str(tid), target.get("cover", COVER_NONE)))
		var dmg := compute_damage(
			float(attacker.get("base_attack", 0)),
			float(attacker.get("era_factor", 1)),
			1.0,
			cover,
			float(target.get("armour", 0))
		)
		damages[str(tid)] = int(damages.get(str(tid), 0)) + dmg
	return damages


static func apply_simultaneous(units: Dictionary, damages: Dictionary) -> Array:
	var events: Array = []
	var keys: Array = damages.keys()
	keys.sort()
	for tid in keys:
		if not units.has(tid):
			continue
		var unit: Dictionary = units[tid]
		if not bool(unit.get("alive", true)):
			continue
		var amount := int(damages[tid])
		var before := int(unit.get("current_health", 0))
		var after := maxi(0, before - amount)
		unit["current_health"] = after
		var killed := after <= 0
		if killed:
			unit["alive"] = false
			unit["status"] = "dead"
			unit["target_id"] = null
		units[tid] = unit
		events.append({
			"unit_id": tid,
			"damage": amount,
			"health_before": before,
			"health_after": after,
			"killed": killed,
		})
	return events


static func resolve_combat_step(units: Dictionary, step_ms: int = 50, cover_by_target: Dictionary = {}) -> Dictionary:
	var living_at_start: Dictionary = {}
	for uid in units.keys():
		var u: Dictionary = units[uid]
		if bool(u.get("alive", true)) and int(u.get("current_health", 0)) > 0:
			var cd := maxi(0, int(u.get("remaining_attack_cooldown_ms", 0)) - step_ms)
			u["remaining_attack_cooldown_ms"] = cd
			units[uid] = u
			living_at_start[uid] = u.duplicate(true)
	var damages := gather_step_damage(living_at_start, cover_by_target)
	var fired: Array = []
	var keys: Array = living_at_start.keys()
	keys.sort()
	for uid in keys:
		var attacker: Dictionary = living_at_start[uid]
		if int(attacker.get("remaining_attack_cooldown_ms", 0)) > 0:
			continue
		if choose_target(attacker, living_at_start.values()) != null:
			fired.append(uid)
	var events := apply_simultaneous(units, damages)
	for uid in fired:
		if not units.has(uid):
			continue
		var unit: Dictionary = units[uid]
		if not bool(unit.get("alive", true)):
			continue
		unit["remaining_attack_cooldown_ms"] = int(unit.get("period_ms", 1000))
		units[uid] = unit
	return {"damages": damages, "events": events, "fired": fired}


static func _to_vec2(value) -> Vector2:
	if value is Vector2:
		return value
	if value is Array and value.size() >= 2:
		return Vector2(float(value[0]), float(value[1]))
	return Vector2.ZERO
