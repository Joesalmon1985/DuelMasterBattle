extends SceneTree

## Map topology test (CORRECTIVE_PASS_PLAN Phase 7, brief §21/§29). Data-only:
## builds every area from WorldData, floods walkable tiles, and asserts
##  - every exit has a walkable landing on both sides;
##  - every exit's destination area exists and the spawn tile is walkable;
##  - every dungeon area (dd_*) except dead-end-by-design rooms has ≥2 exits
##    (no unrewarded dead ends);
##  - every walkable region of a dungeon area either contains an exit or a
##    reward/interaction (pickup, npc, enemy, sign, door, logs, corpse);
##  - trial_road's Burnt Wood branch and the gate are both reachable from spawn.

const Overworld := preload("res://client/world/overworld.gd")
const WorldData := preload("res://client/world/world_data.gd")

var _failures: Array[String] = []

## Rooms that end a route on purpose (and reward it). Everything else must loop.
const DEAD_END_OK := ["dd_vault_inner", "dd_igbut", "jane_placeholder", "dd_mirror", "dd_blood"]
const REWARD_KINDS := ["pickup", "npc", "enemy", "sign", "door", "logs", "corpse", "exit"]


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	for id in WorldData.area_ids():
		_check_area(str(id))
	_check_shortcuts()
	_check_reach("trial_road", Vector2i(10, 1), [Vector2i(18, 6), Vector2i(9, 1), Vector2i(13, 10)], "road spawn → Burnt Wood mouth, gate exit, fly")
	_check_reach("village", Vector2i(11, 6), [Vector2i(10, 16), Vector2i(14, 15), Vector2i(10, 9)], "village spawn → south exit, Ashby, staff")
	_check_reach("forest_deep", Vector2i(18, 12), [Vector2i(4, 10), Vector2i(8, 4)], "Burnt Wood mouth → pendant, shard (fires count as passable for topology)")
	_report()


func _walkable(rows: Array, p: Vector2i) -> bool:
	if p.y < 0 or p.y >= rows.size():
		return false
	var row: String = str(rows[p.y])
	if p.x < 0 or p.x >= row.length():
		return false
	var ch := row[p.x]
	return not (ch in Overworld.SOLID_TILES)


func _blocked_by_entity(area: Dictionary, p: Vector2i) -> bool:
	for e in area.get("entities", []):
		if str(e.get("kind", "")) in ["npc", "enemy", "pickup", "sign", "door", "logs", "corpse"] and e.has("pos"):
			if Vector2i(int(e["pos"][0]), int(e["pos"][1])) == p and str(e.get("kind")) != "pickup":
				return true
	return false


func _flood(area: Dictionary, start: Vector2i, ignore_entities: bool = false) -> Dictionary:
	var rows: Array = area["rows"]
	var seen := {}
	var q := [start]
	if not _walkable(rows, start):
		return seen
	seen[start] = true
	while not q.is_empty():
		var p: Vector2i = q.pop_front()
		for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var n: Vector2i = p + d
			if seen.has(n) or not _walkable(rows, n):
				continue
			if not ignore_entities and _blocked_by_entity(area, n):
				seen[n] = true  # reachable-to-interact, but not passable
				continue
			seen[n] = true
			q.append(n)
	return seen


func _check_area(id: String) -> void:
	var area: Dictionary = WorldData.get_area(id)
	var rows: Array = area["rows"]
	var exits: Array = []
	for e in area.get("entities", []):
		if str(e.get("kind", "")) == "exit":
			exits.append(e)
			var p := Vector2i(int(e["pos"][0]), int(e["pos"][1]))
			_check(_walkable(rows, p), "%s: exit at %s stands on a walkable tile" % [id, str(p)])
			var to: String = str(e.get("to_area", ""))
			_check(WorldData.area_ids().has(to), "%s: exit → '%s' exists" % [id, to])
			if WorldData.area_ids().has(to) and e.has("to_pos"):
				var dest: Dictionary = WorldData.get_area(to)
				var tp := Vector2i(int(e["to_pos"][0]), int(e["to_pos"][1]))
				_check(_walkable(dest["rows"], tp), "%s → %s: landing %s is walkable" % [id, to, str(tp)])
	if id.begins_with("dd_") and not (id in DEAD_END_OK):
		_check(exits.size() >= 2, "%s: dungeon room has ≥2 exits (has %d) — no unrewarded dead end" % [id, exits.size()])
	# Every walkable region must have a reason to exist.
	var covered := {}
	for y in range(rows.size()):
		for x in range(str(rows[y]).length()):
			var p := Vector2i(x, y)
			if covered.has(p) or not _walkable(rows, p):
				continue
			var region := _flood(area, p, true)
			for k in region.keys():
				covered[k] = true
			if region.size() < 4:
				continue  # decorative pockets
			var rewarded := false
			for e in area.get("entities", []):
				if str(e.get("kind", "")) in REWARD_KINDS and e.has("pos"):
					var ep := Vector2i(int(e["pos"][0]), int(e["pos"][1]))
					if region.has(ep) or region.has(ep + Vector2i(0, 1)) or region.has(ep + Vector2i(0, -1)) or region.has(ep + Vector2i(1, 0)) or region.has(ep + Vector2i(-1, 0)):
						rewarded = true
						break
				if str(e.get("kind", "")) == "trigger" and e.has("rect"):
					rewarded = true
			_check(rewarded, "%s: walkable region of %d tiles around %s has an exit/interaction" % [id, region.size(), str(p)])


## Brief §29: dungeon loops. Every "shortcut" exit must have a reciprocal exit
## in the destination area with the same requirement; at least 4 distinct
## shortcut pairs must exist.
func _check_shortcuts() -> void:
	var pairs := {}
	for id in WorldData.area_ids():
		var area: Dictionary = WorldData.get_area(str(id))
		for e in area.get("entities", []):
			if str(e.get("kind", "")) != "exit" or not bool(e.get("shortcut", false)):
				continue
			var to := str(e.get("to_area", ""))
			var req := str(e.get("requires_run_flag", ""))
			_check(req != "", "%s: shortcut → %s is gated by a run flag" % [id, to])
			var back := false
			for f in WorldData.get_area(to).get("entities", []):
				if str(f.get("kind", "")) == "exit" and str(f.get("to_area", "")) == str(id) and bool(f.get("shortcut", false)) and str(f.get("requires_run_flag", "")) == req:
					back = true
			_check(back, "%s ↔ %s: shortcut is reciprocal with the same gate (%s)" % [id, to, req])
			var key := [str(id), to]
			key.sort()
			pairs["%s|%s" % key] = true
	_check(pairs.size() >= 4, "at least 4 shortcut loops (found %d: %s)" % [pairs.size(), str(pairs.keys())])


func _check_reach(id: String, from: Vector2i, targets: Array, label: String) -> void:
	var area: Dictionary = WorldData.get_area(id)
	var region := _flood(area, from, true)
	for t in targets:
		_check(region.has(t), "%s: %s reaches %s" % [id, label, str(t)])


func _check(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)
		print("FAIL: " + msg)


func _report() -> void:
	if _failures.is_empty():
		print("TOPOLOGY: ALL PASSED")
		quit(0)
	else:
		print("TOPOLOGY: %d FAILURE(S)" % _failures.size())
		for f in _failures:
			print("  - " + f)
		quit(1)
