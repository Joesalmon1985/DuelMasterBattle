extends RefCounted
class_name DmbCombatMath

## Shared combat math with Python sim/dmb/military/math.py (C07 / T060).

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


static func default_hostility(units: Dictionary) -> Dictionary:
	## Distinct faction IDs alone are not enough — use explicit graph.
	## Baseline battle: every listed faction is hostile to every other.
	var factions: Dictionary = {}
	for uid in units.keys():
		var f := str(units[uid].get("faction_id", ""))
		if f != "":
			factions[f] = true
	var keys: Array = factions.keys()
	keys.sort()
	var out: Dictionary = {}
	for f in keys:
		var enemies: Array = []
		for o in keys:
			if str(o) != str(f):
				enemies.append(str(o))
		out[str(f)] = enemies
	return out


static func is_hostile(attacker_faction: String, other_faction: String, hostiles: Dictionary) -> bool:
	if attacker_faction == "" or other_faction == "":
		return false
	if attacker_faction == other_faction:
		return false
	if hostiles.is_empty():
		return false
	var enemies = hostiles.get(attacker_faction, [])
	if enemies is Array:
		return other_faction in enemies
	return false


static func has_line_of_sight(a: Vector2, b: Vector2, blockers: Array = []) -> bool:
	if blockers.is_empty():
		return true
	for block_any in blockers:
		var block: Dictionary = block_any
		if not bool(block.get("blocks_los", true)):
			continue
		var xmin: float
		var ymin: float
		var xmax: float
		var ymax: float
		if block.has("min") and block.has("max"):
			xmin = float(block["min"][0])
			ymin = float(block["min"][1])
			xmax = float(block["max"][0])
			ymax = float(block["max"][1])
		else:
			var pos := _to_vec2(block.get("position", [block.get("x", 0), block.get("y", 0)]))
			var half := float(block.get("half", 0.45))
			xmin = pos.x - half
			xmax = pos.x + half
			ymin = pos.y - half
			ymax = pos.y + half
		if _point_in_aabb(a.x, a.y, xmin, ymin, xmax, ymax) or _point_in_aabb(b.x, b.y, xmin, ymin, xmax, ymax):
			continue
		if _segment_hits_aabb(a.x, a.y, b.x, b.y, xmin, ymin, xmax, ymax):
			return false
	return true


static func choose_target(
	attacker: Dictionary,
	candidates: Array,
	hostiles: Dictionary = {},
	blockers: Array = []
) -> Variant:
	if not bool(attacker.get("alive", true)):
		return null
	var attacker_id := str(attacker.get("id", ""))
	var faction := str(attacker.get("faction_id", ""))
	var pos := _to_vec2(attacker.get("position", [0, 0]))
	var range_tiles := float(attacker.get("range_tiles", 1))
	var extra_range := float(attacker.get("extra_range", 0))
	range_tiles += extra_range
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
		if not is_hostile(faction, other_faction, hostiles):
			continue
		var tpos := _to_vec2(cand.get("position", [0, 0]))
		if not in_range(pos, tpos, range_tiles):
			continue
		if not has_line_of_sight(pos, tpos, blockers):
			continue
		eligible.append({
			"dist": distance(pos, tpos),
			"health": int(cand.get("current_health", 0)),
			"id": cid,
		})
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


static func approach_targets(
	units: Dictionary,
	hostiles: Dictionary,
	blockers: Array,
	step_ms: int
) -> void:
	var living: Array = []
	for uid in units.keys():
		var u: Dictionary = units[uid]
		if bool(u.get("alive", true)) and int(u.get("current_health", 0)) > 0:
			living.append(u)
	for unit in living:
		var faction := str(unit.get("faction_id", ""))
		var enemies: Array = []
		for e in living:
			if is_hostile(faction, str(e.get("faction_id", "")), hostiles) and str(e.get("id")) != str(unit.get("id")):
				enemies.append(e)
		if enemies.is_empty():
			continue
		var pos := _to_vec2(unit.get("position", [0, 0]))
		var rng := float(unit.get("range_tiles", 1)) + float(unit.get("extra_range", 0))
		enemies.sort_custom(func(a, b):
			var da := distance(pos, _to_vec2(a.get("position", [0, 0])))
			var db := distance(pos, _to_vec2(b.get("position", [0, 0])))
			if da != db:
				return da < db
			return str(a.get("id")) < str(b.get("id"))
		)
		var nearest: Dictionary = enemies[0]
		var tpos := _to_vec2(nearest.get("position", [0, 0]))
		var dist := distance(pos, tpos)
		if dist <= rng + 0.000000001:
			continue
		if not has_line_of_sight(pos, tpos, blockers) and dist > rng:
			# Sidestep around blocker toward open tile.
			tpos = Vector2(tpos.x + 0.5, tpos.y)
			dist = distance(pos, tpos)
		var speed := float(unit.get("speed_tiles_per_s", 2.0)) * (float(step_ms) / 1000.0)
		if dist <= 0.0000001:
			continue
		var step_len := minf(speed, dist - rng)
		var dir := (tpos - pos) / dist
		var next := pos + dir * step_len
		if _blocked_at(next, blockers):
			next = pos + Vector2(-dir.y, dir.x) * step_len
			if _blocked_at(next, blockers):
				continue
		unit["position"] = [snapped(next.x, 0.01), snapped(next.y, 0.01)]
		units[str(unit["id"])] = unit


static func gather_step_damage(
	units: Dictionary,
	cover_by_target: Dictionary = {},
	hostiles: Dictionary = {},
	blockers: Array = [],
	buildings: Dictionary = {}
) -> Dictionary:
	var living: Dictionary = {}
	for uid in units.keys():
		var u: Dictionary = units[uid]
		if bool(u.get("alive", true)) and int(u.get("current_health", 0)) > 0:
			living[uid] = u
	var targets: Array = living.values()
	for bid in buildings.keys():
		var b: Dictionary = buildings[bid]
		if bool(b.get("alive", true)) and int(b.get("current_health", b.get("health", 0))) > 0:
			targets.append(b)
	var damages: Dictionary = {}
	var keys: Array = living.keys()
	keys.sort()
	for uid in keys:
		var attacker: Dictionary = living[uid]
		if int(attacker.get("remaining_attack_cooldown_ms", 0)) > 0:
			continue
		var tid = choose_target(attacker, targets, hostiles, blockers)
		if tid == null:
			continue
		var target: Dictionary = {}
		for t in targets:
			if str(t.get("id", "")) == str(tid):
				target = t
				break
		var cover := float(cover_by_target.get(str(tid), target.get("cover", COVER_NONE)))
		var dmg := compute_damage(
			float(attacker.get("base_attack", 0)),
			float(attacker.get("era_factor", 1)),
			float(attacker.get("attack_modifier", 1.0)),
			cover,
			float(target.get("armour", 0))
		)
		damages[str(tid)] = int(damages.get(str(tid), 0)) + dmg
	return damages


static func apply_simultaneous(units: Dictionary, damages: Dictionary, buildings: Dictionary = {}) -> Array:
	var events: Array = []
	var keys: Array = damages.keys()
	keys.sort()
	for tid in keys:
		var amount := int(damages[tid])
		if units.has(tid):
			var unit: Dictionary = units[tid]
			if not bool(unit.get("alive", true)):
				continue
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
		elif buildings.has(tid):
			var b: Dictionary = buildings[tid]
			var before_b := int(b.get("current_health", b.get("health", 0)))
			var after_b := maxi(0, before_b - amount)
			b["current_health"] = after_b
			b["health"] = after_b
			if after_b <= 0:
				b["alive"] = false
			buildings[tid] = b
			events.append({
				"unit_id": tid,
				"damage": amount,
				"health_before": before_b,
				"health_after": after_b,
				"killed": after_b <= 0,
				"building": true,
			})
	return events


static func resolve_combat_step(
	units: Dictionary,
	step_ms: int = 50,
	cover_by_target: Dictionary = {},
	hostiles: Dictionary = {},
	blockers: Array = [],
	buildings: Dictionary = {}
) -> Dictionary:
	var living_at_start: Dictionary = {}
	for uid in units.keys():
		var u: Dictionary = units[uid]
		if bool(u.get("alive", true)) and int(u.get("current_health", 0)) > 0:
			var cd := maxi(0, int(u.get("remaining_attack_cooldown_ms", 0)) - step_ms)
			u["remaining_attack_cooldown_ms"] = cd
			units[uid] = u
			living_at_start[uid] = u.duplicate(true)
	var damages := gather_step_damage(living_at_start, cover_by_target, hostiles, blockers, buildings)
	var fired: Array = []
	var keys: Array = living_at_start.keys()
	keys.sort()
	var targets: Array = living_at_start.values()
	for bid in buildings.keys():
		targets.append(buildings[bid])
	for uid in keys:
		var attacker: Dictionary = living_at_start[uid]
		if int(attacker.get("remaining_attack_cooldown_ms", 0)) > 0:
			continue
		if choose_target(attacker, targets, hostiles, blockers) != null:
			fired.append(uid)
	var events := apply_simultaneous(units, damages, buildings)
	for uid in fired:
		if not units.has(uid):
			continue
		var unit: Dictionary = units[uid]
		if not bool(unit.get("alive", true)):
			continue
		var period := int(unit.get("period_ms", 1000))
		var freq := float(unit.get("attack_frequency_mult", 1.0))
		if freq > 0.0:
			period = int(round(float(period) / freq))
		unit["remaining_attack_cooldown_ms"] = maxi(1, period)
		units[uid] = unit
	return {"damages": damages, "events": events, "fired": fired}


static func _to_vec2(value) -> Vector2:
	if value is Vector2:
		return value
	if value is Array and value.size() >= 2:
		return Vector2(float(value[0]), float(value[1]))
	return Vector2.ZERO


static func _blocked_at(pos: Vector2, blockers: Array) -> bool:
	for block_any in blockers:
		var block: Dictionary = block_any
		if not bool(block.get("blocks_move", true)):
			continue
		var bpos := _to_vec2(block.get("position", [0, 0]))
		var half := float(block.get("half", 0.45))
		if abs(pos.x - bpos.x) <= half and abs(pos.y - bpos.y) <= half:
			return true
	return false


static func _point_in_aabb(x: float, y: float, xmin: float, ymin: float, xmax: float, ymax: float) -> bool:
	return xmin <= x and x <= xmax and ymin <= y and y <= ymax


static func _segment_hits_aabb(
	x0: float, y0: float, x1: float, y1: float,
	xmin: float, ymin: float, xmax: float, ymax: float
) -> bool:
	var dx := x1 - x0
	var dy := y1 - y0
	var p := [-dx, dx, -dy, dy]
	var q := [x0 - xmin, xmax - x0, y0 - ymin, ymax - y0]
	var u1 := 0.0
	var u2 := 1.0
	for i in range(4):
		var pi: float = p[i]
		var qi: float = q[i]
		if abs(pi) < 0.000000000001:
			if qi < 0.0:
				return false
			continue
		var t: float = qi / pi
		if pi < 0.0:
			u1 = maxf(u1, t)
		else:
			u2 = minf(u2, t)
		if u1 > u2:
			return false
	return true
