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
##    "exits": [[exit_tile, arrive_tile, facing] ...]}
##
## Tile vocabulary is the one Overworld already renders: "." grass, "," dark
## grass, ":" path, "a" ash, "T" tree, "t" burnt tree, "r" rock, "f" fence,
## "#" wall, "R" roof, "D" door.

const WILD_W := 17
const WILD_H := 13
const MIN_STEADING := Vector2i(25, 19)
const MAX_STEADING := Vector2i(31, 23)
const MIN_TOWN := Vector2i(33, 25)
const MAX_TOWN := Vector2i(45, 33)
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
	# Footprints plus door fronts, gaps, roads and terrain dressing (fields,
	# copses, rock): roughly a third of the interior is buildable.
	var need := float(cells) * 3.2
	var hh := int(ceil(sqrt(need / 1.4)))
	var ww := int(ceil(hh * 1.4))
	var lo := MIN_TOWN if town else MIN_STEADING
	var hi := MAX_TOWN if town else MAX_STEADING
	return Vector2i(clampi(ww, lo.x, hi.x), clampi(hh, lo.y, hi.y))


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
		var owned: bool = i < p["roads"].size() and str(p["roads"][i]["owner"]) != ""
		var path: Array = _corridor(c, Vector2i(slot[0][0], slot[0][1]))
		var paint: int = path.size() if (owned or wild) else 3
		for j in range(path.size()):
			var q: Vector2i = path[j]
			c.road[c.key(q.x, q.y)] = true
			c.solid.erase(c.key(q.x, q.y))
			if j < paint:
				c.put(q.x, q.y, ":")
			elif c.at(q.x, q.y) in ["#", "T", "t"]:
				c.put(q.x, q.y, c.floor_ch)
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
	var sectors := _sectors(c, hexes.size())
	if wild:
		var dg: Dictionary = p.get("dungeon", {})
		if not dg.is_empty():
			var b := _place(c, "dungeon", str(dg.get("kind", "cave")), Rect2i(c.interior.position.x, c.interior.position.y, c.interior.size.x, maxi(3, c.centre.y - 3)), true, -1)
			if not b.is_empty():
				buildings.append(b)
		for hi in range(hexes.size()):
			var hid := int(hexes[hi])
			_dress(c, sectors[hi], str(hex_terrains.get(hid, p.get("family", ""))), int(hex_demons.get(hid, 0)), wild)
	else:
		var core := _core_zone(c)
		if town:
			# Gate towers flank the north gate, inside the wall: claimed before
			# any other footprint so nothing can be built over the gate.
			for dx in [-1, 1]:
				var tx: int = c.centre.x + dx
				if c.is_open(tx, 2):
					c.put(tx, 2, "#")
					c.solid[c.key(tx, 2)] = true
					c.footprint[c.key(tx, 2)] = true
			var gate_front := Vector2i(c.centre.x + 1, 3)
			if c.is_open(gate_front.x, gate_front.y):
				c.taken[c.key(gate_front.x, gate_front.y)] = true
				buildings.append({"kind": "civic", "building": "gate_tower", "front": [gate_front.x, gate_front.y], "rect": Rect2i(c.centre.x - 1, 2, 3, 1), "hex": -1, "stand": []})
		# Civic works around the plaza, then the processing works, then the
		# production huts out in the land they work; the land itself is dressed
		# (fields, copses, rock) before the houses fill in what is left.
		for cv in p["civic"]:
			if FOOT.has(cv):
				var b := _place(c, "civic", str(cv), core, true, -1)
				if not b.is_empty():
					buildings.append(b)
		for pr_b in p["processing"]:
			var b := _place(c, "processing", str(pr_b), core, true, -1)
			if b.is_empty():
				b = _place(c, "processing", str(pr_b), c.interior, true, -1)
			if not b.is_empty():
				buildings.append(b)
		for hi in range(hexes.size()):
			for pr in p["production"]:
				if int(pr["hex"]) != int(hexes[hi]):
					continue
				for n in range(int(pr["n"])):
					var b := _place(c, "production", str(pr["building"]), sectors[hi], false, int(pr["hex"]))
					if b.is_empty():
						b = _place(c, "production", str(pr["building"]), c.interior, false, int(pr["hex"]))
					if b.is_empty():
						_clear_dressing_for(c, FOOT["production"])
						b = _place(c, "production", str(pr["building"]), c.interior, false, int(pr["hex"]))
					if not b.is_empty():
						b["worker"] = str(pr["worker"])
						b["idle"] = bool(pr.get("idle", false))
						buildings.append(b)
		for hi in range(hexes.size()):
			var hid := int(hexes[hi])
			var terrain := str(hex_terrains.get(hid, p.get("family", "")))
			var before := _mark_count(c, terrain)
			_dress(c, sectors[hi], terrain, int(hex_demons.get(hid, 0)), wild)
			if _mark_count(c, terrain) == before:
				_dress(c, c.interior, terrain, int(hex_demons.get(hid, 0)), wild)
		for i in range(int(p["housing"])):
			var b := _place(c, "house", "house", core, true, -1)
			if b.is_empty():
				b = _place(c, "house", "house", c.interior, true, -1)
			if b.is_empty():
				# People before scenery: fell a copse / lift a fence for the house.
				_clear_dressing_for(c, FOOT["house"])
				b = _place(c, "house", "house", c.interior, true, -1)
			if not b.is_empty():
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
	return out


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
	var mx := maxi(3, c.interior.size.x / 5)
	var my := maxi(2, c.interior.size.y / 5)
	return Rect2i(c.interior.position.x + mx, c.interior.position.y + my, c.interior.size.x - 2 * mx, c.interior.size.y - 2 * my)


## Three sectors for the three hexes that meet at this corner: west band, east
## band, south band. The north holds the main gate and Jane's house.
static func _sectors(c: Ctx, n: int) -> Array:
	var ix := c.interior.position.x
	var iy := c.interior.position.y
	var iw := c.interior.size.x
	var ih := c.interior.size.y
	var third := maxi(4, iw / 3)
	var out := [
		Rect2i(ix, iy, third, ih),
		Rect2i(ix + iw - third, iy, third, ih),
		Rect2i(ix + third, iy + ih - maxi(4, ih / 3), iw - 2 * third, maxi(4, ih / 3)),
	]
	while out.size() < n:
		out.append(c.interior)
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
static func _place(c: Ctx, kind: String, building: String, zone: Rect2i, near_centre: bool, hex: int) -> Dictionary:
	var f: Vector2i = FOOT[kind if kind != "civic" else building]
	var cands: Array = []
	var z := zone.intersection(c.interior)
	for y in range(z.position.y, z.end.y - f.y + 1):
		for x in range(z.position.x, z.end.x - f.x + 1):
			if _fits(c, Rect2i(x, y, f.x, f.y)):
				cands.append(Vector2i(x, y))
	if cands.is_empty():
		return {}
	if near_centre:
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


## Carve the shortest path from `from` to the existing road network across free
## interior floor (never through footprints, walls or planned entity tiles), and
## paint it. Returns false if no route exists.
static func _connect(c: Ctx, from: Vector2i) -> bool:
	if _next_to_road(c, from) or c.road.has(c.key(from.x, from.y)):
		if not c.road.has(c.key(from.x, from.y)):
			c.put(from.x, from.y, ":")
		return true
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


## The land the hex is: trees for forest, rock for hills and mountains, fenced
## paddocks for pasture, crop rows for fields, dead ground for desert. Demons
## scorch the sector: ash patches, and at two or more the trees are burnt.
static func _dress(c: Ctx, zone: Rect2i, terrain: String, demons: int, wild: bool) -> void:
	var free: Array = []
	for y in range(zone.position.y, zone.end.y):
		for x in range(zone.position.x, zone.end.x):
			if c.is_open(x, y) and not _next_to_taken(c, Vector2i(x, y)):
				free.append(Vector2i(x, y))
	if free.is_empty():
		return
	c.shuffle(free)
	var budget: int = maxi(4, free.size() / (3 if wild else 4))
	var used := 0
	match terrain:
		"forest":
			var i := 0
			while used < budget and i < free.size():
				var q: Vector2i = free[i]
				i += 1
				if c.is_open(q.x, q.y):
					c.put(q.x, q.y, "t" if demons >= 2 else "T")
					c.solid[c.key(q.x, q.y)] = true
					used += 1
					for dq in [Vector2i(1, 0), Vector2i(0, 1)]:
						var n: Vector2i = q + dq
						if used < budget and c.is_open(n.x, n.y) and not _next_to_taken(c, n) and c.jitter(2) > 0:
							c.put(n.x, n.y, "t" if demons >= 2 else "T")
							c.solid[c.key(n.x, n.y)] = true
							used += 1
		"hills", "mountains":
			var i := 0
			var rocks: int = maxi(2, budget / 2)
			while used < rocks and i < free.size():
				var q: Vector2i = free[i]
				i += 1
				if c.is_open(q.x, q.y):
					c.put(q.x, q.y, "r")
					c.solid[c.key(q.x, q.y)] = true
					used += 1
					if terrain == "mountains":
						var n := q + Vector2i(1, 0)
						if c.is_open(n.x, n.y) and not _next_to_taken(c, n):
							c.put(n.x, n.y, "r")
							c.solid[c.key(n.x, n.y)] = true
							used += 1
			while i < free.size() and used < budget:
				var q: Vector2i = free[i]
				i += 1
				if c.is_open(q.x, q.y):
					c.put(q.x, q.y, ",")
					used += 1
		"pasture", "fields":
			var rows_ch := "," if terrain == "fields" else "."
			var placed := 0
			var i := 0
			var strips: int = 1 if (wild or c.w < MIN_TOWN.x) else 2
			while placed < strips and i < free.size():
				var q: Vector2i = free[i]
				i += 1
				var r := Rect2i(q.x, q.y, 4 + c.jitter(2), 3)
				if not _clear_rect(c, r):
					r = Rect2i(q.x, q.y, 3, 3)
				if _clear_rect(c, r):
					for y in range(r.position.y, r.end.y):
						for x in range(r.position.x, r.end.x):
							var edge: bool = x == r.position.x or x == r.end.x - 1 or y == r.position.y or y == r.end.y - 1
							if edge and not (y == r.end.y - 1 and x == r.position.x + 1):
								c.put(x, y, "f")
								c.solid[c.key(x, y)] = true
							else:
								c.put(x, y, rows_ch if (terrain == "fields" and (y % 2 == 0)) else c.floor_ch)
					placed += 1
		"desert":
			var i := 0
			while used < budget and i < free.size():
				var q: Vector2i = free[i]
				i += 1
				c.put(q.x, q.y, "a")
				used += 1
	# Infection: ash patches sized by the number of demons.
	if demons > 0:
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
