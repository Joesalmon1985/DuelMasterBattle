extends RefCounted
class_name DmbSettlementLayout
## Deterministic tile layout for one board node, laid out from the canonical
## DmbSettlementProfile. Pure function of (world seed, node, profile): the same
## inputs always give the same rows and the same spots. Nothing here reads or
## writes world state; DmbNodeProjection asks for a layout and dresses it with
## entities.
##
## Output of build():
##   {"rows": [String], "w": int, "h": int,
##    "plaza": Rect2i, "well": [x,y], "sign": [x,y], "player_start": [x,y],
##    "home_door": [x,y] or [],
##    "buildings": [{"kind": "production"|"processing"|"civic"|"house"|"dungeon",
##                   "building": id, "front": [x,y], "rect": Rect2i, "hex": hid or -1,
##                   "stand": [x,y] or []}],
##    "npc_spots": [[x,y] ...] (free tiles beside the roads, nearest the plaza first),
##    "cart_spots": [[x,y] ...],
##    "demon_spots": {hid: [x,y]},
##    "exits": [[exit_tile, arrive_tile, facing] ...],
##    "core": [x, y, w, h], "outer": [x, y, w, h],
##    "features": {trees, fields, pasture, mines, clay, camps}}
##
## Tile vocabulary is the one Overworld already renders: "." grass, "," dark
## grass, ":" path, "a" ash, "T" tree, "t" burnt tree, "r" rock, "f" fence,
## "#" wall, "R" roof, "D" door.

const WILD_W := 17
const WILD_H := 13
const MIN_STEADING := Vector2i(49, 37)
const MAX_STEADING := Vector2i(73, 55)
const MIN_TOWN := Vector2i(81, 61)
const MAX_TOWN := Vector2i(113, 85)
const INSET := 2   # interior starts here: border ring + (for towns) the wall ring
## Building footprints, width x height (the bottom row is wall with a door).
const FOOT := {
	"production": Vector2i(2, 2), "processing": Vector2i(3, 2), "house": Vector2i(2, 2),
	"shrine": Vector2i(2, 2), "hall": Vector2i(4, 3), "market": Vector2i(3, 2), "dungeon": Vector2i(3, 2),
}
const FLOOR := {"forest": ".", "hills": ",", "mountains": ",", "pasture": ".", "fields": ".", "desert": "a", "": "."}
const WALKABLE := [".", ",", ":", "a", "D", "="]

## Jane's house at the player's home node. Kept at a fixed spot because the
## authored jane_placeholder area arrives at [3, 5] (DmbWorldData).
const HOME_RECT := Rect2i(2, 1, 4, 3)
const HOME_DOOR := [3, 4]
const HOME_ARRIVE := [3, 5]


class Ctx:
	var w: int
	var h: int
	var grid: Array = []          # Array[Array[String]]
	var footprint := {}           # "x,y" -> true : building tiles, never walked or carved
	var solid := {}               # "x,y" -> true : border, wall, footprint
	var road := {}                # "x,y" -> true : plaza + corridors + carved paths (walk network)
	var taken := {}               # "x,y" -> true : an entity will stand here (blocks walking)
	var decor_ok := {}            # "x,y" -> true : free floor that decor may use
	var features := {"trees": 0, "fields": 0, "pasture": 0, "mines": 0, "clay": 0, "camps": 0}
	var house_fronts: Array = []
	var core: Rect2i
	var rng := RandomNumberGenerator.new()
	var floor_ch := "."
	var interior: Rect2i
	var plaza: Rect2i
	var centre: Vector2i

	func key(x: int, y: int) -> String:
		return "%d,%d" % [x, y]

	func inside(x: int, y: int) -> bool:
		return x >= interior.position.x and y >= interior.position.y and x < interior.end.x and y < interior.end.y

	func at(x: int, y: int) -> String:
		return grid[y][x]

	func put(x: int, y: int, ch: String) -> void:
		grid[y][x] = ch

	func is_open(x: int, y: int) -> bool:
		## Free interior floor: no footprint, road, wall, or planned entity.
		if not inside(x, y):
			return false
		var k := key(x, y)
		return not solid.has(k) and not road.has(k) and not taken.has(k)

	func jitter(n: int) -> int:
		return rng.randi_range(0, n)

	func shuffle(a: Array) -> Array:
		for i in range(a.size() - 1, 0, -1):
			var j := rng.randi_range(0, i)
			var t = a[i]
			a[i] = a[j]
			a[j] = t
		return a


static func dims(p: Dictionary) -> Vector2i:
	if str(p.get("kind", "wild")) == "wild":
		return Vector2i(WILD_W, WILD_H)
	var town: bool = str(p["kind"]) == "town"
	var cells := 0
	for pr in p["production"]:
		cells += int(pr["n"]) * _cells("production")
	cells += p["processing"].size() * _cells("processing")
	cells += int(p["housing"]) * _cells("house")
	for cv in p["civic"]:
		if FOOT.has(cv):
			cells += _cells(cv)
	var plaza := Vector2i(7, 5) if town else Vector2i(5, 3)
	cells += plaza.x * plaza.y
	# Map how much is built into the size band. Quiet places sit near the floor;
	# busy ones use the larger canvas. This only chooses width and height.
	var lo := MIN_TOWN if town else MIN_STEADING
	var hi := MAX_TOWN if town else MAX_STEADING
	var span := 140.0 if town else 70.0
	var base := 50.0 if town else 24.0
	var t := clampf((float(cells) - base) / span, 0.0, 1.0)
	var ww := lo.x + int(round(t * float(hi.x - lo.x)))
	var hh := lo.y + int(round(t * float(hi.y - lo.y)))
	return Vector2i(ww, hh)


static func _cells(kind: String) -> int:
	var f: Vector2i = FOOT[kind]
	return (f.x + 1) * (f.y + 1)


## Exit slots for a map of this size: [exit tile, arrival tile, facing on arrival].
## Slot 0 leaves north, 1 south-west, 2 south-east — the same order every node
## uses, so neighbour i of this node and the way back both resolve by index.
static func exit_slots(d: Vector2i) -> Array:
	var cx := d.x / 2
	var qx := d.x / 4
	return [
		[[cx, 0], [cx, 1], "down"],
		[[qx, d.y - 1], [qx, d.y - 2], "up"],
		[[d.x - 1 - qx, d.y - 1], [d.x - 1 - qx, d.y - 2], "up"],
	]


## `hexes` are the node's hex ids in board order; `hex_terrains` / `hex_demons`
## are keyed by hex id and come straight off the board.
static func build(world_seed: int, nid: int, p: Dictionary, exits: int, home: bool, hexes: Array, hex_terrains: Dictionary, hex_demons: Dictionary) -> Dictionary:
	var c := Ctx.new()
	var d := dims(p)
	c.w = d.x
	c.h = d.y
	c.rng.seed = hash("%d:%d" % [world_seed, nid])
	var kind := str(p.get("kind", "wild"))
	var town := kind == "town"
	var wild := kind == "wild"
	c.floor_ch = str(FLOOR.get(str(p.get("family", "")), "."))
	c.interior = Rect2i(INSET, INSET, c.w - 2 * INSET, c.h - 2 * INSET)
	var edge_ch := "t" if str(p.get("family", "")) == "desert" else "T"
	for y in range(c.h):
		var row: Array = []
		for x in range(c.w):
			var edge: bool = x == 0 or y == 0 or x == c.w - 1 or y == c.h - 1
			row.append(edge_ch if edge else c.floor_ch)
			if edge:
				c.solid[c.key(x, y)] = true
		c.grid.append(row)
	# Jane's house first: the wall ring skips its footprint.
	var out := {"home_door": []}
	if home:
		_stamp_rect(c, HOME_RECT, -1)
		c.taken[c.key(HOME_DOOR[0], HOME_DOOR[1])] = true
		out["home_door"] = HOME_DOOR
	if town:
		for x in range(1, c.w - 1):
			for y in [1, c.h - 2]:
				if not c.footprint.has(c.key(x, y)):
					c.put(x, y, "#")
					c.solid[c.key(x, y)] = true
		for y in range(1, c.h - 1):
			for x in [1, c.w - 2]:
				if not c.footprint.has(c.key(x, y)):
					c.put(x, y, "#")
					c.solid[c.key(x, y)] = true
	# Plaza: the crossing itself. Towns pave it; steadings tread it bare with a
	# paved cross once development reaches 3.
	var pw := 7 if town else (5 if not wild else 3)
	var ph := 5 if town else (3 if not wild else 1)
	c.centre = Vector2i(c.w / 2, c.h / 2)
	c.plaza = Rect2i(c.centre.x - pw / 2, c.centre.y - ph / 2, pw, ph)
	var paved: bool = town or int(p.get("development", 0)) >= 3
	for y in range(c.plaza.position.y, c.plaza.end.y):
		for x in range(c.plaza.position.x, c.plaza.end.x):
			var cross: bool = x == c.centre.x or y == c.centre.y
			c.put(x, y, ":" if (paved or cross or wild) else ",")
			c.road[c.key(x, y)] = true
	# Exit corridors: straight in from the edge, then along the centre row to the plaza.
	var slots := exit_slots(d)
	var slot_out: Array = []
	for i in range(mini(exits, slots.size())):
		var slot: Array = slots[i]
		var path: Array = _corridor(c, Vector2i(slot[0][0], slot[0][1]))
		for j in range(path.size()):
			var q: Vector2i = path[j]
			_paint_road(c, q.x, q.y)
		if not wild:
			_widen_main(c, path)
		slot_out.append(slot)
	out["exits"] = slot_out
	# Fixed plaza spots.
	out["well"] = [c.centre.x, c.centre.y]
	out["sign"] = [c.plaza.end.x - 1, c.centre.y] if not wild else [c.centre.x + 1, c.centre.y]
	out["player_start"] = [c.centre.x, c.plaza.end.y - 1] if not wild else [c.centre.x, c.centre.y + 1]
	for k in ["well", "sign", "player_start"]:
		c.taken[c.key(out[k][0], out[k][1])] = true
	if home:
		_connect(c, Vector2i(HOME_DOOR[0], HOME_DOOR[1]))
	var buildings: Array = []
	c.core = _core_zone(c)
	var sectors := _sectors(c, hexes.size())
	if wild:
		var dg: Dictionary = p.get("dungeon", {})
		if not dg.is_empty():
			var b := _place(c, "dungeon", str(dg.get("kind", "cave")), Rect2i(c.interior.position.x, c.interior.position.y, c.interior.size.x, maxi(3, c.centre.y - 3)), true, -1)
			if not b.is_empty():
				buildings.append(b)
		for hi in range(hexes.size()):
			var hid := int(hexes[hi])
			_dress(c, sectors[hi], str(hex_terrains.get(hid, p.get("family", ""))), int(hex_demons.get(hid, 0)), true, 1)
	else:
		if town:
			# Gate towers sit just outside the 3-wide north road, not on it.
			for dx in [-2, 2]:
				var tx: int = c.centre.x + dx
				if c.is_open(tx, 2):
					c.put(tx, 2, "#")
					c.solid[c.key(tx, 2)] = true
					c.footprint[c.key(tx, 2)] = true
			var gate_front := Vector2i(c.centre.x + 2, 3)
			if not c.is_open(gate_front.x, gate_front.y):
				gate_front = Vector2i(c.centre.x, 3)
			if c.is_open(gate_front.x, gate_front.y) or c.road.has(c.key(gate_front.x, gate_front.y)):
				if c.is_open(gate_front.x, gate_front.y):
					c.taken[c.key(gate_front.x, gate_front.y)] = true
				buildings.append({"kind": "civic", "building": "gate_tower", "front": [gate_front.x, gate_front.y], "rect": Rect2i(c.centre.x - 2, 2, 5, 1), "hex": -1, "stand": []})
		# Civic and processing stay in the built core. Production huts go out
		# into the work band of the hex they draw from.
		for cv in p["civic"]:
			if FOOT.has(cv):
				var b := _place(c, "civic", str(cv), c.core, true, -1)
				if b.is_empty():
					b = _place(c, "civic", str(cv), _grown_core(c, 2), true, -1)
				if not b.is_empty():
					buildings.append(b)
		for pr_b in p["processing"]:
			var b := _place(c, "processing", str(pr_b), c.core, true, -1)
			if b.is_empty():
				b = _place(c, "processing", str(pr_b), _grown_core(c, 3), true, -1)
			if not b.is_empty():
				buildings.append(b)
		for hi in range(hexes.size()):
			var camp_at := Vector2i(-1, -1)
			var camp_n := 0
			for pr in p["production"]:
				if int(pr["hex"]) != int(hexes[hi]):
					continue
				camp_n = maxi(camp_n, int(pr["n"]))
				for n in range(int(pr["n"])):
					var b := _place(c, "production", str(pr["building"]), sectors[hi], false, int(pr["hex"]))
					if b.is_empty():
						b = _place(c, "production", str(pr["building"]), _outer_band(c), false, int(pr["hex"]))
					if b.is_empty():
						_clear_dressing_for(c, FOOT["production"])
						b = _place(c, "production", str(pr["building"]), _outer_band(c), false, int(pr["hex"]))
					if b.is_empty():
						b = _place(c, "production", str(pr["building"]), c.interior, false, int(pr["hex"]))
					if not b.is_empty():
						b["worker"] = str(pr["worker"])
						b["idle"] = bool(pr.get("idle", false))
						buildings.append(b)
						if camp_at == Vector2i(-1, -1):
							camp_at = Vector2i(int(b["front"][0]), int(b["front"][1]))
			if camp_n >= 2 and camp_at != Vector2i(-1, -1):
				var camp := _place_camp(c, camp_at, sectors[hi])
				if not camp.is_empty():
					buildings.append(camp)
		for hi in range(hexes.size()):
			var hid := int(hexes[hi])
			var terrain := str(hex_terrains.get(hid, p.get("family", "")))
			var strength := _strength(p, hid, terrain)
			var before := _mark_count(c, terrain)
			_dress(c, sectors[hi], terrain, int(hex_demons.get(hid, 0)), false, strength)
			if _mark_count(c, terrain) == before and strength > 0:
				_dress(c, _outer_band(c), terrain, int(hex_demons.get(hid, 0)), false, strength)
		for i in range(int(p["housing"])):
			var house_zone := c.core
			var b := _place(c, "house", "house", house_zone, false, -1, true)
			if b.is_empty():
				b = _place(c, "house", "house", _grown_core(c, 3), false, -1, true)
			if b.is_empty():
				_clear_dressing_for(c, FOOT["house"])
				b = _place(c, "house", "house", _grown_core(c, 4), false, -1, true)
			if not b.is_empty():
				c.house_fronts.append(Vector2i(int(b["front"][0]), int(b["front"][1])))
				buildings.append(b)
	out["buildings"] = buildings
	# Standing room beside the roads, nearest the plaza first: rulers, units,
	# quest folk, carts. Demons stand in the sector of the hex they came from.
	var beside := _beside_roads(c)
	out["demon_spots"] = {}
	for hi in range(hexes.size()):
		var hid := int(hexes[hi])
		if int(hex_demons.get(hid, 0)) <= 0:
			continue
		var spot := _pick_in(c, beside, sectors[hi])
		if spot == Vector2i(-1, -1):
			spot = _pick_in(c, beside, c.interior)
		if spot != Vector2i(-1, -1):
			c.taken[c.key(spot.x, spot.y)] = true
			out["demon_spots"][hid] = [spot.x, spot.y]
	var npc_spots: Array = []
	var cart_spots: Array = []
	for q in beside:
		if c.taken.has(c.key(q.x, q.y)):
			continue
		if npc_spots.size() < 10:
			npc_spots.append([q.x, q.y])
			c.taken[c.key(q.x, q.y)] = true
		elif cart_spots.size() < 4:
			cart_spots.append([q.x, q.y])
			c.taken[c.key(q.x, q.y)] = true
		else:
			break
	out["rows"] = []
	for y in range(c.h):
		out["rows"].append("".join(PackedStringArray(c.grid[y])))
	# Final guarantee: every standing spot and every building front is
	# approachable from John's spawn. Anything boxed in by later footprints or
	# dressing is dropped (spots) or relocated to a reachable neighbour (fronts).
	var blocked := {}
	for q in npc_spots + cart_spots:
		blocked[c.key(int(q[0]), int(q[1]))] = true
	for hid in out["demon_spots"]:
		blocked[c.key(int(out["demon_spots"][hid][0]), int(out["demon_spots"][hid][1]))] = true
	for b in buildings:
		blocked[c.key(int(b["front"][0]), int(b["front"][1]))] = true
		if not b["stand"].is_empty():
			blocked[c.key(int(b["stand"][0]), int(b["stand"][1]))] = true
	blocked[c.key(out["sign"][0], out["sign"][1])] = true
	blocked[c.key(out["well"][0], out["well"][1])] = true
	var reach := reachable(out["rows"], Vector2i(out["player_start"][0], out["player_start"][1]), blocked)
	var approachable := func(q: Array, rr: Dictionary) -> bool:
		for dq in [Vector2i(0, 1), Vector2i(0, -1), Vector2i(1, 0), Vector2i(-1, 0)]:
			if rr.has(c.key(int(q[0]) + dq.x, int(q[1]) + dq.y)):
				return true
		return false
	var kept_npc: Array = []
	for q in npc_spots:
		if approachable.call(q, reach):
			kept_npc.append(q)
	var kept_cart: Array = []
	for q in cart_spots:
		if approachable.call(q, reach):
			kept_cart.append(q)
	# Demons must stay (one creature per infected hex): relocate a boxed-in one
	# to the nearest reachable open tile instead of dropping it.
	var kept_demons := {}
	for hid in out["demon_spots"]:
		var spot: Array = out["demon_spots"][hid]
		if not approachable.call(spot, reach):
			for q in beside:
				var k := c.key(q.x, q.y)
				if not blocked.has(k) and reach.has(k):
					spot = [q.x, q.y]
					blocked[k] = true
					break
		kept_demons[hid] = spot
	out["demon_spots"] = kept_demons
	for b in buildings:
		if not b["stand"].is_empty() and not approachable.call(b["stand"], reach):
			# Dressing (trees, rock, fences) sealed the pocket the worker stands
			# in: carve a path from the stand to the reachable network through
			# dressing only (never through footprints or walls), then re-check.
			var stand := Vector2i(int(b["stand"][0]), int(b["stand"][1]))
			if _carve_to(c, stand, reach, blocked):
				out["rows"] = []
				for y in range(c.h):
					out["rows"].append("".join(PackedStringArray(c.grid[y])))
				reach = reachable(out["rows"], Vector2i(out["player_start"][0], out["player_start"][1]), blocked)
			if not approachable.call(b["stand"], reach):
				b["stand"] = []
		if str(b["kind"]) == "production" and b["stand"].is_empty():
			# Nowhere beside the door: the worker stands on the nearest reachable
			# free floor within a few tiles, off the road, facing the works.
			var fr := Vector2i(int(b["front"][0]), int(b["front"][1]))
			var best := Vector2i(-1, -1)
			var best_d := 99
			for dy in range(-3, 4):
				for dx in range(-3, 4):
					var q2 := fr + Vector2i(dx, dy)
					var k2 := c.key(q2.x, q2.y)
					if not reach.has(k2) or c.road.has(k2) or c.taken.has(k2) or blocked.has(k2) or c.footprint.has(k2) or not c.inside(q2.x, q2.y):
						continue
					var dd: int = absi(dx) + absi(dy)
					if dd < best_d or (dd == best_d and (q2.y < best.y or (q2.y == best.y and q2.x < best.x))):
						best_d = dd
						best = q2
			if best != Vector2i(-1, -1):
				b["stand"] = [best.x, best.y]
				c.taken[c.key(best.x, best.y)] = true
				blocked[c.key(best.x, best.y)] = true
	out["npc_spots"] = kept_npc
	out["cart_spots"] = kept_cart
	out["w"] = c.w
	out["h"] = c.h
	out["plaza"] = c.plaza
	out["core"] = [c.core.position.x, c.core.position.y, c.core.size.x, c.core.size.y]
	out["outer"] = [c.interior.position.x, c.interior.position.y, c.interior.size.x, c.interior.size.y]
	out["features"] = c.features.duplicate()
	return out


static func _paint_road(c: Ctx, x: int, y: int) -> void:
	if x < 0 or y < 0 or x >= c.w or y >= c.h:
		return
	if c.footprint.has(c.key(x, y)):
		return
	c.road[c.key(x, y)] = true
	c.solid.erase(c.key(x, y))
	c.put(x, y, ":")


## Broaden a main exit road to three tiles. Only the interior and the town
## wall ring widen; the map edge stays a single gate so the border stays shut.
static func _widen_main(c: Ctx, path: Array) -> void:
	for i in range(path.size()):
		var q: Vector2i = path[i]
		if q.x == 0 or q.y == 0 or q.x == c.w - 1 or q.y == c.h - 1:
			continue
		var dir := Vector2i(0, 1)
		if i + 1 < path.size():
			var nxt: Vector2i = path[i + 1]
			dir = nxt - q
		elif i > 0:
			var prev: Vector2i = path[i - 1]
			dir = q - prev
		if dir == Vector2i.ZERO:
			dir = Vector2i(0, 1)
		var side := Vector2i(-dir.y, dir.x)
		for s in [-1, 1]:
			var n: Vector2i = q + side * s
			if n.x <= 0 or n.y <= 0 or n.x >= c.w - 1 or n.y >= c.h - 1:
				continue
			if c.footprint.has(c.key(n.x, n.y)) or c.taken.has(c.key(n.x, n.y)):
				continue
			_paint_road(c, n.x, n.y)


static func _strength(p: Dictionary, hex: int, terrain: String) -> int:
	var n := 0
	for pr in p["production"]:
		if int(pr["hex"]) == hex and str(pr["terrain"]) == terrain:
			n += int(pr["n"])
	return n


## A roofed cottage near a strong production hut. Scenery only: not a house,
## not a change to population. Kind "camp" is ignored by the economy projection.
static func _place_camp(c: Ctx, near: Vector2i, zone: Rect2i) -> Dictionary:
	var best := Vector2i(-1, -1)
	var best_d := 99
	var z := zone.intersection(c.interior)
	for y in range(z.position.y, z.end.y - 1):
		for x in range(z.position.x, z.end.x - 1):
			if c.core.has_point(Vector2i(x, y)):
				continue
			var ok := true
			for yy in range(y, y + 2):
				for xx in range(x, x + 2):
					if not c.is_open(xx, yy) or _next_to_taken(c, Vector2i(xx, yy)):
						ok = false
			if not ok:
				continue
			var d := absi(x - near.x) + absi(y - near.y)
			if d < 3 or d > 8:
				continue
			if d < best_d:
				best_d = d
				best = Vector2i(x, y)
	if best == Vector2i(-1, -1):
		return {}
	for y in range(best.y, best.y + 2):
		for x in range(best.x, best.x + 2):
			c.put(x, y, "R")
			c.footprint[c.key(x, y)] = true
			c.solid[c.key(x, y)] = true
	var front := Vector2i(best.x, best.y + 2)
	if c.is_open(front.x, front.y):
		_connect(c, front)
	c.features["camps"] = int(c.features["camps"]) + 1
	return {"kind": "camp", "building": "worker_camp", "front": [front.x, front.y], "rect": Rect2i(best.x, best.y, 2, 2), "hex": -1, "stand": []}


static func _corridor(c: Ctx, exit_tile: Vector2i) -> Array:
	var path: Array = [exit_tile]
	var q := exit_tile
	var dir := Vector2i(0, 1) if exit_tile.y == 0 else Vector2i(0, -1)
	# Straight in until the centre row of the plaza, then sideways to it.
	while true:
		q += dir
		if q.y == c.centre.y or (c.plaza.has_point(q)):
			break
		path.append(q)
		if q.y <= 0 or q.y >= c.h - 1:
			break
	if not c.plaza.has_point(q):
		path.append(q)
		var step := 1 if q.x < c.centre.x else -1
		while not c.plaza.has_point(q):
			q.x += step
			if c.plaza.has_point(q):
				break
			path.append(q)
	return path


static func _core_zone(c: Ctx) -> Rect2i:
	var iw := c.interior.size.x
	var ih := c.interior.size.y
	var cw := clampi(int(float(iw) * 0.46), 16, iw - 8)
	var ch := clampi(int(float(ih) * 0.46), 12, ih - 6)
	var x := c.centre.x - cw / 2
	var y := c.centre.y - ch / 2
	return Rect2i(x, y, cw, ch).intersection(c.interior)


## Core grown a few tiles, still well clear of the map edge. Houses may use
## this if the strict core is full. They do not spill to the boundary.
static func _grown_core(c: Ctx, step: int) -> Rect2i:
	var r := Rect2i(c.core.position.x - step, c.core.position.y - step, c.core.size.x + step * 2, c.core.size.y + step * 2)
	var limit := Rect2i(5, 5, c.w - 10, c.h - 10)
	return r.intersection(limit).intersection(c.interior)


## Interior minus a margin: the work landscape around the core. Used when a
## sector is too tight for one more hut.
static func _outer_band(c: Ctx) -> Rect2i:
	return Rect2i(c.interior.position.x + 1, c.interior.position.y + 1, c.interior.size.x - 2, c.interior.size.y - 2)


## Three outer work sectors for the three hexes that meet here: west band,
## east band, south band. They stop at the built core rather than covering it.
static func _sectors(c: Ctx, n: int) -> Array:
	var ix := c.interior.position.x
	var iy := c.interior.position.y
	var iw := c.interior.size.x
	var ih := c.interior.size.y
	var west_w := maxi(6, c.core.position.x - ix)
	var east_w := maxi(6, c.interior.end.x - c.core.end.x)
	var south_h := maxi(5, c.interior.end.y - c.core.end.y)
	var out := [
		Rect2i(ix, iy, west_w, ih),
		Rect2i(c.interior.end.x - east_w, iy, east_w, ih),
		Rect2i(ix, c.core.end.y, iw, south_h),
	]
	while out.size() < n:
		out.append(_outer_band(c))
	return out


static func _stamp_rect(c: Ctx, r: Rect2i, door_x: int) -> void:
	for y in range(r.position.y, r.end.y):
		for x in range(r.position.x, r.end.x):
			var bottom: bool = y == r.end.y - 1
			c.put(x, y, ("D" if x == door_x else "#") if bottom else "R")
			c.footprint[c.key(x, y)] = true
			c.solid[c.key(x, y)] = true


## Place one footprint inside `zone`: no overlap with anything solid or any
## road, a one-tile gap from other footprints, and a clear front tile that the
## road network can be carved to. Returns {} when nothing fits.
static func _place(c: Ctx, kind: String, building: String, zone: Rect2i, near_centre: bool, hex: int, spread: bool = false) -> Dictionary:
	var f: Vector2i = FOOT[kind if kind != "civic" else building]
	var cands: Array = []
	var z := zone.intersection(c.interior)
	for y in range(z.position.y, z.end.y - f.y + 1):
		for x in range(z.position.x, z.end.x - f.x + 1):
			if _fits(c, Rect2i(x, y, f.x, f.y)):
				cands.append(Vector2i(x, y))
	if cands.is_empty():
		return {}
	if spread:
		var scored: Array = []
		for q in cands:
			var front := Vector2i(q.x + f.x / 2, q.y + f.y)
			var nearest := 99
			for h in c.house_fronts:
				nearest = mini(nearest, absi(front.x - h.x) + absi(front.y - h.y))
			var edge := mini(front.x, mini(front.y, mini(c.w - 1 - front.x, c.h - 1 - front.y)))
			scored.append([-nearest, -edge, q.y, q.x, q])
		scored.sort_custom(func(a, b):
			for i in range(4):
				if a[i] != b[i]:
					return a[i] < b[i]
			return false)
		cands = []
		for s in scored:
			cands.append(s[4])
	elif near_centre:
		var scored: Array = []
		for q in cands:
			var mid := Vector2i(q.x + f.x / 2, q.y + f.y / 2)
			scored.append([absi(mid.x - c.centre.x) + absi(mid.y - c.centre.y) + c.jitter(4), q])
		scored.sort_custom(func(a, b): return a[0] < b[0] if a[0] != b[0] else (a[1].y < b[1].y if a[1].y != b[1].y else a[1].x < b[1].x))
		cands = []
		for s in scored:
			cands.append(s[1])
	else:
		c.shuffle(cands)
	for q in cands:
		var r := Rect2i(q.x, q.y, f.x, f.y)
		var door_x: int = q.x + f.x / 2
		var front := Vector2i(door_x, r.end.y)
		# The front tile carries the door entity, which blocks movement: it must
		# be free floor, never a road tile, or the door would sever the road.
		if not c.is_open(front.x, front.y):
			continue
		_stamp_rect(c, r, door_x)
		c.taken[c.key(front.x, front.y)] = true
		var road_before := c.road.duplicate()
		var grid_before: Array = []
		for y in range(c.h):
			grid_before.append(c.grid[y].duplicate())
		if not _connect(c, front):
			# Could not reach the roads (boxed in): undo and try the next spot.
			_unstamp(c, r, front, grid_before, road_before)
			continue
		# Worker stand: an open tile beside the door, preferring one that touches
		# the road just carved so the worker reads as "at work", falling back to
		# any free neighbour. Chosen after _connect so the road exists.
		var stand := Vector2i(-1, -1)
		for pass_i in range(2):
			for dq in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1)]:
				var s: Vector2i = front + dq
				# pass 0: open floor touching a road; pass 1: any open floor.
				var ok: bool = c.is_open(s.x, s.y) and (pass_i == 1 or _next_to_road(c, s))
				if ok and _has_way_out(c, s, front):
					stand = s
					break
			if stand != Vector2i(-1, -1):
				break
		var stand_out: Array = []
		if kind == "production":
			if stand == Vector2i(-1, -1):
				# A works with nowhere for its worker to stand is no use: try elsewhere.
				_unstamp(c, r, front, grid_before, road_before)
				continue
			c.taken[c.key(stand.x, stand.y)] = true
			stand_out = [stand.x, stand.y]
		return {"kind": kind, "building": building, "front": [front.x, front.y], "rect": r, "hex": hex, "stand": stand_out}
	return {}


## Breadth-first from `from` through dressing tiles (trees, rock, fence, ash,
## floor) until a tile of `reach` is met; clears the dressing on the way to
## plain floor. Footprints, walls and entity tiles are never crossed.
static func _carve_to(c: Ctx, from: Vector2i, reach: Dictionary, blocked: Dictionary) -> bool:
	var prev := {}
	var start := c.key(from.x, from.y)
	prev[start] = ""
	var queue: Array = [from]
	var goal := ""
	while not queue.is_empty() and goal == "":
		var q: Vector2i = queue.pop_front()
		for dq in [Vector2i(0, 1), Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1)]:
			var n: Vector2i = q + dq
			var k := c.key(n.x, n.y)
			if prev.has(k) or not c.inside(n.x, n.y) or blocked.has(k) or c.footprint.has(k):
				continue
			var ch := c.at(n.x, n.y)
			if ch == "#" or ch == "D":
				continue
			prev[k] = c.key(q.x, q.y)
			if reach.has(k):
				goal = k
				break
			queue.append(n)
	if goal == "":
		return false
	var k := str(prev[goal])
	while k != "" and k != start:
		var parts := k.split(",")
		var x := int(parts[0])
		var y := int(parts[1])
		if c.at(x, y) in ["T", "t", "r", "f"]:
			c.put(x, y, c.floor_ch)
			c.solid.erase(k)
		k = str(prev[k])
	return true


## Remove dressing (trees, rock, fences) from the first interior window that
## could hold a footprint of size `f` plus its front row and gap, so a later
## _place can succeed. Deterministic scan order; footprints/roads untouched.
static func _clear_dressing_for(c: Ctx, f: Vector2i) -> void:
	var z := c.interior
	for y in range(z.position.y, z.end.y - f.y):
		for x in range(z.position.x, z.end.x - f.x + 1):
			var ok := true
			for yy in range(y - 1, y + f.y + 2):
				for xx in range(x - 1, x + f.x + 1):
					if not c.inside(xx, yy):
						continue
					var k := c.key(xx, yy)
					if c.footprint.has(k) or c.road.has(k) or c.taken.has(k):
						ok = false
			if not ok:
				continue
			for yy in range(y, y + f.y + 1):
				for xx in range(x, x + f.x):
					if c.at(xx, yy) in ["T", "t", "r", "f"]:
						c.put(xx, yy, c.floor_ch)
						c.solid.erase(c.key(xx, yy))
			return


## Undo a footprint (and any road carved for it) so another spot can be tried.
static func _unstamp(c: Ctx, r: Rect2i, front: Vector2i, grid_before: Array, road_before: Dictionary) -> void:
	for y in range(c.h):
		c.grid[y] = grid_before[y].duplicate()
	c.road = road_before
	for y in range(r.position.y, r.end.y):
		for x in range(r.position.x, r.end.x):
			c.footprint.erase(c.key(x, y))
			c.solid.erase(c.key(x, y))
	c.taken.erase(c.key(front.x, front.y))


static func _fits(c: Ctx, r: Rect2i) -> bool:
	for y in range(r.position.y - 1, r.end.y + 1):
		for x in range(r.position.x - 1, r.end.x + 1):
			var in_r: bool = r.has_point(Vector2i(x, y))
			if in_r:
				if not c.inside(x, y):
					return false
				var k := c.key(x, y)
				if c.solid.has(k) or c.road.has(k) or c.taken.has(k):
					return false
			else:
				if c.footprint.has(c.key(x, y)):
					return false
	# The front row must exist and stay clear of footprints.
	var fy := r.end.y
	if fy >= c.interior.end.y:
		return false
	for x in range(r.position.x, r.end.x):
		if c.footprint.has(c.key(x, fy)):
			return false
	return true


## A standing tile is only usable if it can be walked up to from somewhere
## other than the building's own door tile (which an entity will occupy).
static func _has_way_out(c: Ctx, q: Vector2i, front: Vector2i) -> bool:
	for dq in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		var n: Vector2i = q + dq
		if n == front:
			continue
		var k := c.key(n.x, n.y)
		if c.road.has(k) or (c.is_open(n.x, n.y)):
			return true
	return false


## Number of road tiles orthogonally adjacent: a dead-end spur is 1, a straight
## run 2, a junction 3+. Standing on a junction would sever routes.
static func _road_degree(c: Ctx, q: Vector2i) -> int:
	var n := 0
	for dq in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		if c.road.has(c.key(q.x + dq.x, q.y + dq.y)):
			n += 1
	return n


static func _next_to_road(c: Ctx, q: Vector2i) -> bool:
	for dq in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		if c.road.has(c.key(q.x + dq.x, q.y + dq.y)):
			return true
	return false


## Prefer a straight spur to the nearest road. A short detour is allowed only
## if the straight line is blocked. This is a branch, not a street maze.
static func _connect(c: Ctx, from: Vector2i) -> bool:
	if _next_to_road(c, from) or c.road.has(c.key(from.x, from.y)):
		if not c.road.has(c.key(from.x, from.y)):
			c.put(from.x, from.y, ":")
		return true
	var target := _nearest_road(c, from)
	if target == Vector2i(-1, -1):
		return false
	if _spur(c, from, target, true) or _spur(c, from, target, false):
		return true
	return _connect_around(c, from)


static func _nearest_road(c: Ctx, from: Vector2i) -> Vector2i:
	var best := Vector2i(-1, -1)
	var best_d := 9999
	for y in range(c.interior.position.y, c.interior.end.y):
		for x in range(c.interior.position.x, c.interior.end.x):
			if not c.road.has(c.key(x, y)):
				continue
			var d := absi(x - from.x) + absi(y - from.y)
			if d < best_d:
				best_d = d
				best = Vector2i(x, y)
	return best


## Straight line: one axis, then the other, only across open floor.
static func _spur(c: Ctx, from: Vector2i, target: Vector2i, x_first: bool) -> bool:
	var tiles: Array = [from]
	var q := from
	var order: Array = [Vector2i(1, 0), Vector2i(0, 1)] if x_first else [Vector2i(0, 1), Vector2i(1, 0)]
	for axis in order:
		var delta := target - q
		var step := Vector2i.ZERO
		if axis.x != 0 and delta.x != 0:
			step = Vector2i(1 if delta.x > 0 else -1, 0)
		elif axis.y != 0 and delta.y != 0:
			step = Vector2i(0, 1 if delta.y > 0 else -1)
		if step == Vector2i.ZERO:
			continue
		var guard := 0
		while guard < 80:
			guard += 1
			var nxt: Vector2i = q + step
			if nxt == target or c.road.has(c.key(nxt.x, nxt.y)):
				tiles.append(nxt)
				q = nxt
				break
			if not c.is_open(nxt.x, nxt.y):
				return false
			tiles.append(nxt)
			q = nxt
			if (axis.x != 0 and q.x == target.x) or (axis.y != 0 and q.y == target.y):
				break
	if not c.road.has(c.key(q.x, q.y)) and not _next_to_road(c, q):
		return false
	for t in tiles:
		if c.road.has(c.key(t.x, t.y)):
			continue
		c.put(t.x, t.y, ":")
		c.road[c.key(t.x, t.y)] = true
	return true


static func _connect_around(c: Ctx, from: Vector2i) -> bool:
	var prev := {}
	var start := c.key(from.x, from.y)
	prev[start] = ""
	var queue: Array = [from]
	var goal := Vector2i(-1, -1)
	while not queue.is_empty():
		var q: Vector2i = queue.pop_front()
		for dq in [Vector2i(0, 1), Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1)]:
			var n: Vector2i = q + dq
			var k := c.key(n.x, n.y)
			if prev.has(k) or not c.inside(n.x, n.y):
				continue
			if c.solid.has(k):
				continue
			if c.taken.has(k) and not c.road.has(k):
				continue
			prev[k] = c.key(q.x, q.y)
			if c.road.has(k):
				goal = n
				break
			if c.taken.has(k):
				continue
			queue.append(n)
		if goal != Vector2i(-1, -1):
			break
	if goal == Vector2i(-1, -1):
		return false
	var k: String = str(prev[c.key(goal.x, goal.y)])
	while k != "" and k != start:
		var parts := str(k).split(",")
		var x := int(parts[0])
		var y := int(parts[1])
		c.put(x, y, ":")
		c.road[k] = true
		k = str(prev[k])
	c.put(from.x, from.y, ":")
	return true


static func _beside_roads(c: Ctx) -> Array:
	var out: Array = []
	for y in range(c.interior.position.y, c.interior.end.y):
		for x in range(c.interior.position.x, c.interior.end.x):
			var q := Vector2i(x, y)
			if c.is_open(x, y) and _next_to_road(c, q):
				out.append(q)
	out.sort_custom(func(a, b):
		var da: int = absi(a.x - c.centre.x) + absi(a.y - c.centre.y)
		var db: int = absi(b.x - c.centre.x) + absi(b.y - c.centre.y)
		return da < db if da != db else (a.y < b.y if a.y != b.y else a.x < b.x))
	return out


static func _pick_in(c: Ctx, cands: Array, zone: Rect2i) -> Vector2i:
	var pool: Array = []
	for q in cands:
		if zone.has_point(q) and not c.taken.has(c.key(q.x, q.y)):
			pool.append(q)
	if pool.is_empty():
		return Vector2i(-1, -1)
	# The far end of the sector reads better for what came out of the ground.
	return pool[pool.size() - 1 - c.jitter(mini(2, pool.size() - 1))]


## Dress one hex sector. Settlements scale with production strength. Crossings
## use a fixed modest pattern so the terrain is visible without moving the roads.
static func _dress(c: Ctx, zone: Rect2i, terrain: String, demons: int, wild: bool, strength: int) -> void:
	var n := 1 if wild else strength
	if n <= 0 and not wild:
		_scorch(c, zone, demons)
		return
	match terrain:
		"forest":
			_dress_wood(c, zone, n, demons, wild)
		"fields":
			_dress_fields(c, zone, n, wild)
		"pasture":
			_dress_pasture(c, zone, n, wild)
		"mountains":
			_dress_ore(c, zone, n, wild)
		"hills":
			_dress_clay(c, zone, n, wild)
		"desert":
			_dress_desert(c, zone, n)
	_scorch(c, zone, demons)


static func _free_tiles(c: Ctx, zone: Rect2i) -> Array:
	var free: Array = []
	for y in range(zone.position.y, zone.end.y):
		for x in range(zone.position.x, zone.end.x):
			if c.is_open(x, y) and not _next_to_taken(c, Vector2i(x, y)) and not c.core.has_point(Vector2i(x, y)):
				free.append(Vector2i(x, y))
	if free.is_empty():
		for y in range(zone.position.y, zone.end.y):
			for x in range(zone.position.x, zone.end.x):
				if c.is_open(x, y) and not _next_to_taken(c, Vector2i(x, y)):
					free.append(Vector2i(x, y))
	c.shuffle(free)
	return free


static func _stamp_solid(c: Ctx, x: int, y: int, ch: String) -> bool:
	if not c.is_open(x, y) or _next_to_taken(c, Vector2i(x, y)):
		return false
	c.put(x, y, ch)
	c.solid[c.key(x, y)] = true
	return true


## Wood: tree/copse count follows production. Crossings get one modest copse.
static func _dress_wood(c: Ctx, zone: Rect2i, n: int, demons: int, wild: bool) -> void:
	var free := _free_tiles(c, zone)
	var budget := 6 if wild else (4 + n * 7)
	var ch := "t" if demons >= 2 else "T"
	var used := 0
	var i := 0
	while used < budget and i < free.size():
		var q: Vector2i = free[i]
		i += 1
		if not _stamp_solid(c, q.x, q.y, ch):
			continue
		used += 1
		for dq in [Vector2i(1, 0), Vector2i(0, 1), Vector2i(1, 1)]:
			if used >= budget:
				break
			var p: Vector2i = q + dq
			if _stamp_solid(c, p.x, p.y, ch):
				used += 1
	c.features["trees"] = int(c.features["trees"]) + used


## Grain: more production, more and larger field strips.
static func _dress_fields(c: Ctx, zone: Rect2i, n: int, wild: bool) -> void:
	var strips := 1 if wild else (1 + n)
	var w := 3 if wild else (4 + n)
	var h := 2 if wild else (3 + n / 2)
	var placed := _stamp_strips(c, zone, strips, w, h, true)
	c.features["fields"] = int(c.features["fields"]) + placed


## Pasture: fenced open paddocks. More wool, more fencing.
static func _dress_pasture(c: Ctx, zone: Rect2i, n: int, wild: bool) -> void:
	var strips := 1 if wild else (1 + n)
	var w := 3 if wild else (3 + n)
	var h := 2 if wild else (2 + n)
	var placed := _stamp_strips(c, zone, strips, w, h, false)
	c.features["pasture"] = int(c.features["pasture"]) + placed


static func _stamp_strips(c: Ctx, zone: Rect2i, strips: int, w: int, h: int, crops: bool) -> int:
	var free := _free_tiles(c, zone)
	var placed := 0
	var tiles := 0
	var i := 0
	while placed < strips and i < free.size():
		var q: Vector2i = free[i]
		i += 1
		var r := Rect2i(q.x, q.y, w, h)
		if not _clear_rect(c, r):
			r = Rect2i(q.x, q.y, mini(3, w), mini(2, h))
		if not _clear_rect(c, r):
			continue
		for y in range(r.position.y, r.end.y):
			for x in range(r.position.x, r.end.x):
				var edge: bool = x == r.position.x or x == r.end.x - 1 or y == r.position.y or y == r.end.y - 1
				if edge and not (y == r.end.y - 1 and x == r.position.x + 1):
					c.put(x, y, "f")
					c.solid[c.key(x, y)] = true
					tiles += 1
				elif crops and (y % 2 == 0):
					c.put(x, y, ",")
					tiles += 1
		placed += 1
	return tiles


## Ore: rock and a mine mouth. Strength adds mouths and rock, not a new building.
static func _dress_ore(c: Ctx, zone: Rect2i, n: int, wild: bool) -> void:
	var mouths := 1 if wild else maxi(1, n)
	var rocks := 4 if wild else (6 + n * 5)
	var free := _free_tiles(c, zone)
	var used := 0
	var i := 0
	var opened := 0
	while opened < mouths and i < free.size():
		var q: Vector2i = free[i]
		i += 1
		if not _stamp_mine_mouth(c, q):
			continue
		opened += 1
		used += 5
	while used < rocks and i < free.size():
		var q: Vector2i = free[i]
		i += 1
		if _stamp_solid(c, q.x, q.y, "r"):
			used += 1
	c.features["mines"] = int(c.features["mines"]) + opened


static func _stamp_mine_mouth(c: Ctx, q: Vector2i) -> bool:
	var cells := [q + Vector2i(-1, 0), q + Vector2i(1, 0), q + Vector2i(0, -1), q + Vector2i(-1, -1), q + Vector2i(1, -1)]
	if not c.is_open(q.x, q.y):
		return false
	for p in cells:
		if not c.inside(p.x, p.y) or not c.is_open(p.x, p.y):
			return false
	c.put(q.x, q.y, ",")
	for p in cells:
		c.put(p.x, p.y, "r")
		c.solid[c.key(p.x, p.y)] = true
	return true


## Clay: dug pits, distinct from a mine. Strength adds pits and makes them larger.
static func _dress_clay(c: Ctx, zone: Rect2i, n: int, wild: bool) -> void:
	var pits := 1 if wild else maxi(1, n)
	var pw := 3 if wild else (3 + n)
	var ph := 2 if wild else (2 + n / 2)
	var free := _free_tiles(c, zone)
	var placed := 0
	var tiles := 0
	var i := 0
	while placed < pits and i < free.size():
		var q: Vector2i = free[i]
		i += 1
		var r := Rect2i(q.x, q.y, pw, ph)
		if not _clear_rect(c, r):
			continue
		for y in range(r.position.y, r.end.y):
			for x in range(r.position.x, r.end.x):
				c.put(x, y, ",")
				tiles += 1
		if _stamp_solid(c, r.position.x, r.position.y - 1, "r"):
			tiles += 1
		elif r.size.y > 0:
			c.put(r.position.x, r.position.y, "r")
			c.solid[c.key(r.position.x, r.position.y)] = true
			tiles += 1
		if _stamp_solid(c, r.end.x - 1, r.position.y - 1, "r"):
			tiles += 1
		elif r.size.x > 1:
			c.put(r.end.x - 1, r.position.y, "r")
			c.solid[c.key(r.end.x - 1, r.position.y)] = true
			tiles += 1
		placed += 1
	c.features["clay"] = int(c.features["clay"]) + tiles


static func _dress_desert(c: Ctx, zone: Rect2i, n: int) -> void:
	var free := _free_tiles(c, zone)
	var budget := 3 + n * 2
	var i := 0
	var used := 0
	while used < budget and i < free.size():
		var q: Vector2i = free[i]
		i += 1
		c.put(q.x, q.y, "a")
		used += 1


static func _scorch(c: Ctx, zone: Rect2i, demons: int) -> void:
	if demons <= 0:
		return
	var free := _free_tiles(c, zone)
	var ash: int = 2 + demons * 3
	var j := 0
	var i := 0
	while j < ash and i < free.size():
		var q: Vector2i = free[i]
		i += 1
		if c.is_open(q.x, q.y) and c.at(q.x, q.y) in [".", ","]:
			c.put(q.x, q.y, "a")
			j += 1


## How much of a terrain's signature mark is already on the map.
static func _mark_count(c: Ctx, terrain: String) -> int:
	var ch: String = str({"forest": "T", "fields": "f", "pasture": "f", "hills": "r", "mountains": "r", "desert": "a"}.get(terrain, ""))
	if ch == "":
		return 0
	var n := 0
	for y in range(c.h):
		for x in range(c.w):
			if c.grid[y][x] == ch:
				n += 1
	return n


static func _clear_rect(c: Ctx, r: Rect2i) -> bool:
	for y in range(r.position.y, r.end.y):
		for x in range(r.position.x, r.end.x):
			if not c.is_open(x, y) or _next_to_taken(c, Vector2i(x, y)):
				return false
	return true


static func _next_to_taken(c: Ctx, q: Vector2i) -> bool:
	for dq in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		if c.taken.has(c.key(q.x + dq.x, q.y + dq.y)):
			return true
	return false


## Every tile John can reach from `start` on a finished area (walkable chars,
## not standing on a blocking entity). Shared by tests and the report tool.
static func reachable(rows: Array, start: Vector2i, blocked: Dictionary) -> Dictionary:
	var seen := {}
	var w := str(rows[0]).length()
	var h := rows.size()
	var queue: Array = [start]
	seen["%d,%d" % [start.x, start.y]] = true
	while not queue.is_empty():
		var q: Vector2i = queue.pop_front()
		for dq in [Vector2i(0, 1), Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1)]:
			var n: Vector2i = q + dq
			if n.x < 0 or n.y < 0 or n.x >= w or n.y >= h:
				continue
			var k := "%d,%d" % [n.x, n.y]
			if seen.has(k) or blocked.has(k):
				continue
			if not (str(rows[n.y])[n.x] in WALKABLE):
				continue
			seen[k] = true
			queue.append(n)
	return seen
