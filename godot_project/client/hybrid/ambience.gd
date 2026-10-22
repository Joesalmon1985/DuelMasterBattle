extends RefCounted

## The world's "watching" layer (docs/POLISH_WATCHING_FEEL.md): presentation only, nothing here feeds anything back to the simulation. It watches
## the snapshots the sim sends and turns the small completions of the economy into small moments: a ware set down at a door (a puff of dust, the
## ware's own icon drifting up into the building, a soft wooden clack), a building finishing (a gold ring, sparks, a chime), a tree felled (chips and
## a chop), a new worker stepping out (a white ring), chimney smoke over every building that is working, a thin gold arc filling over a site under
## construction, and a faint hollow crate pulsing over a building that is waiting for something. Sounds come only from what is on screen and are
## rationed, so ten minutes of watching never asks to be muted. Everything is drawn; the only loaded images are the Widelands ware icons the art
## catalogue already carries (asset reuse, through hybrid_art's own texture cache).

const MAX_PARTICLES := 360
const SMOKE_EVERY := 1.35  # seconds between puffs from one working building (at time scale 1)
const WAIT_AFTER := 6.0  # seconds a building must be waiting before its crate shows (a cycle's natural pause is not a bottleneck)
const SOUND_GAP := 0.28  # seconds between two economy sounds
const SOUND_PER_SECOND := 3

var world: Node
var art = null
var view_bounds := Rect2i(-1000000, -1000000, 2000000, 2000000)  # tiles the camera can see, set by the world's draw
var enabled := true
var _parts: Array = []  # {kind, pos (tiles, float), vel (tiles/s), t, life, size, col, tex}
var _seen: Dictionary = {}  # entity id -> {cargo, constructing, working, tile, cls, stage}
var _smoke_acc: Dictionary = {}  # building id -> seconds since its last puff
var _waiting: Dictionary = {}  # building id -> seconds it has been waiting
var _first := true
var _sound_gap := 0.0
var _sound_window := 0.0
var _sounds_this_second := 0
var _time := 0.0
var _rng := RandomNumberGenerator.new()
var stats := {"delivered": 0, "picked": 0, "completed": 0, "felled": 0, "stepped_out": 0, "sounds": 0}  # for tests and the evidence ledger


func setup(p_world: Node, p_art) -> void:
	world = p_world
	art = p_art
	_rng.seed = 7
	enabled = OS.get_environment("HYBRID_NO_AMBIENCE") == ""


## Advance the particles. `time_scale` is the sim's (a fast-forwarded world smokes faster, as it works faster).
func step(delta: float, time_scale: float = 1.0) -> void:
	_time += delta
	_sound_gap = maxf(0.0, _sound_gap - delta)
	_sound_window += delta
	if _sound_window >= 1.0:
		_sound_window = 0.0
		_sounds_this_second = 0
	var ts := maxf(time_scale, 1.0)
	var keep: Array = []
	for p in _parts:
		p["t"] += delta * (ts if str(p["kind"]) == "smoke" else 1.0)
		if p["t"] < p["life"]:
			p["pos"] += p["vel"] * delta
			keep.append(p)
	_parts = keep
	# chimneys: every working building in view puffs on its own slow clock
	for id in _smoke_acc.keys():
		var s: Dictionary = _seen.get(id, {})
		if s.is_empty() or not bool(s.get("working", false)):
			_smoke_acc.erase(id)
			continue
		var tile: Vector2i = s["tile"]
		if not view_bounds.has_point(tile):
			continue
		_smoke_acc[id] = float(_smoke_acc[id]) + delta * ts
		if float(_smoke_acc[id]) >= SMOKE_EVERY:
			_smoke_acc[id] = _rng.randf_range(0.0, 0.3)
			_puff_smoke(s)


## Compare this snapshot with the last one and raise the moments. Called by the world for every snapshot it applies (solo and LAN alike).
func observe(snap: Dictionary) -> void:
	if not enabled or snap.is_empty():
		return
	var now: Dictionary = {}
	for e in snap.get("entities", []):
		if typeof(e) != TYPE_DICTIONARY:
			continue
		var id := str(e.get("id", ""))
		var cls := str(e.get("class", ""))
		var tile := Vector2i(int(e.get("tx", 0)), int(e.get("ty", 0)))
		var rec := {"cls": cls, "tile": tile}
		match cls:
			"carrier", "worker":
				rec["cargo"] = str(e.get("cargo", e.get("carrying", "")))
				rec["inside"] = bool(e.get("inside", false))
			"building":
				rec["constructing"] = e.has("constructing")
				rec["working"] = bool(e.get("working", false))
				rec["destroyed"] = bool(e.get("destroyed", false))
				rec["status"] = str(e.get("status_text", ""))
				rec["operational"] = bool(e.get("operational", true))
				rec["hp"] = float(e.get("hp", 1))
				rec["max_hp"] = float(e.get("max_hp", 1))
				rec["faction"] = str(e.get("faction_name", ""))
			"tree":
				rec["stage"] = str(e.get("stage", ""))
			"unit":
				pass
			_:
				continue
		now[id] = rec
		if _first:
			continue
		var was: Dictionary = _seen.get(id, {})
		match cls:
			"carrier", "worker":
				_watch_cargo(id, was, rec)
			"building":
				_watch_building(id, was, rec)
			"tree":
				if not was.is_empty() and str(was.get("stage", "")) != "felled" and str(rec["stage"]) == "felled":
					_felled(tile)
				elif was.is_empty() and str(rec["stage"]) == "sapling":
					_planted(tile)
			"unit":
				if was.is_empty():
					_stepped_out(tile)
	_seen = now
	_first = false


func _watch_cargo(id: String, was: Dictionary, rec: Dictionary) -> void:
	var before := str(was.get("cargo", ""))
	var after := str(rec.get("cargo", ""))
	if before == after:
		return
	var pos := _visual_tile(id, rec["tile"])
	if before != "" and after == "":
		stats["delivered"] += 1
		_delivered(pos, before)
	elif before == "" and after != "" and not was.is_empty():
		stats["picked"] += 1
		_picked(pos)


func _watch_building(id: String, was: Dictionary, rec: Dictionary) -> void:
	var tile: Vector2i = rec["tile"]
	if not was.is_empty() and bool(was.get("constructing", false)) and not bool(rec["constructing"]) and not bool(rec["destroyed"]):
		stats["completed"] += 1
		_completed(tile)
	if bool(rec["working"]) and not _smoke_acc.has(id):
		_smoke_acc[id] = _rng.randf_range(0.0, SMOKE_EVERY)
	if not was.is_empty() and not bool(was.get("working", false)) and bool(rec["working"]):
		_waiting.erase(id)
	elif _is_waiting(rec):
		if not _waiting.has(id):
			_waiting[id] = _time  # when the wait began
	else:
		_waiting.erase(id)


static func _is_waiting(rec: Dictionary) -> bool:
	if bool(rec.get("working", false)) or bool(rec.get("destroyed", false)):
		return false
	var s := str(rec.get("status", "")).to_lower()
	return s.find("waiting") >= 0 or s.find("no road") >= 0 or s.find("needs") >= 0 or s.find("lacks") >= 0


## The smoothed position the art layer draws the figure at (a snapshot tile would put the puff a step behind the feet).
func _visual_tile(id: String, tile: Vector2i) -> Vector2:
	if art != null and art._vis.has(id):
		return art._vis[id]["pos"]
	return Vector2(tile)


# ---------------------------------------------------------------- the moments

func _add(p: Dictionary) -> void:
	if _parts.size() >= MAX_PARTICLES:
		_parts.pop_front()
	_parts.append(p)


func _in_view(pos: Vector2) -> bool:
	return view_bounds.has_point(Vector2i(int(floor(pos.x)), int(floor(pos.y))))


func _sound(kind: String) -> void:
	if not _in_view_sound_ok():
		return
	var sfx: Node = world.get_node_or_null("/root/Sfx") if world != null else null
	if sfx == null or not sfx.has_method(kind):
		return
	sfx.call(kind)
	stats["sounds"] += 1
	_sound_gap = SOUND_GAP
	_sounds_this_second += 1


func _in_view_sound_ok() -> bool:
	return _sound_gap <= 0.0 and _sounds_this_second < SOUND_PER_SECOND


func _delivered(pos: Vector2, ware: String) -> void:
	if not _in_view(pos):
		return
	for i in 5:  # dust at the feet
		var a := _rng.randf_range(0.0, TAU)
		_add({"kind": "dust", "pos": pos + Vector2(0.5, 0.75), "vel": Vector2(cos(a), sin(a) * 0.4) * _rng.randf_range(0.25, 0.6), "t": 0.0,
			"life": _rng.randf_range(0.35, 0.6), "size": _rng.randf_range(0.05, 0.1), "col": Color(0.62, 0.52, 0.38, 0.7)})
	var tex: Texture2D = null
	if art != null:
		var icon: Dictionary = art.items.get("widelands.ware.%s" % ware, {})
		if not icon.is_empty():
			tex = art._tex(str(icon.get("id", "")))
	_add({"kind": "ware", "pos": pos + Vector2(0.5, 0.1), "vel": Vector2(0.0, -0.55), "t": 0.0, "life": 0.9, "size": 0.42, "col": Color(1, 1, 1, 1), "tex": tex})
	_sound("clack")


func _picked(pos: Vector2) -> void:
	if not _in_view(pos):
		return
	_add({"kind": "ring", "pos": pos + Vector2(0.5, 0.3), "vel": Vector2.ZERO, "t": 0.0, "life": 0.3, "size": 0.35, "col": Color(0.95, 0.9, 0.7, 0.6)})


func _completed(tile: Vector2i) -> void:
	var pos := Vector2(tile) + Vector2(0.5, 0.2)
	if not _in_view(pos):
		return
	_add({"kind": "ring", "pos": pos, "vel": Vector2.ZERO, "t": 0.0, "life": 0.9, "size": 1.6, "col": Color(1.0, 0.85, 0.4, 0.9)})
	for i in 14:
		var a := float(i) * TAU / 14.0 + _rng.randf_range(-0.2, 0.2)
		_add({"kind": "spark", "pos": pos, "vel": Vector2(cos(a), sin(a)) * _rng.randf_range(1.2, 2.4) - Vector2(0, 0.6), "t": 0.0,
			"life": _rng.randf_range(0.5, 0.9), "size": _rng.randf_range(0.06, 0.11), "col": Color(1.0, 0.8, 0.35, 1.0)})
	_sound("complete")


func _felled(tile: Vector2i) -> void:
	var pos := Vector2(tile) + Vector2(0.5, 0.6)
	stats["felled"] += 1
	if not _in_view(pos):
		return
	for i in 9:
		var a := _rng.randf_range(-PI, 0.0)
		_add({"kind": "chip", "pos": pos, "vel": Vector2(cos(a), sin(a)) * _rng.randf_range(0.8, 1.8), "t": 0.0, "life": _rng.randf_range(0.4, 0.7),
			"size": _rng.randf_range(0.05, 0.09), "col": Color(0.78, 0.6, 0.35, 1.0)})
	_sound("chop")


func _planted(tile: Vector2i) -> void:
	var pos := Vector2(tile) + Vector2(0.5, 0.6)
	if not _in_view(pos):
		return
	for i in 4:
		_add({"kind": "spark", "pos": pos + Vector2(_rng.randf_range(-0.2, 0.2), 0.0), "vel": Vector2(0, -0.5), "t": 0.0, "life": 0.6, "size": 0.05, "col": Color(0.55, 0.9, 0.45, 0.9)})


func _stepped_out(tile: Vector2i) -> void:
	var pos := Vector2(tile) + Vector2(0.5, 0.5)
	stats["stepped_out"] += 1
	if not _in_view(pos):
		return
	_add({"kind": "ring", "pos": pos, "vel": Vector2.ZERO, "t": 0.0, "life": 0.5, "size": 0.8, "col": Color(0.95, 0.95, 1.0, 0.8)})


func _puff_smoke(s: Dictionary) -> void:
	var tile: Vector2i = s["tile"]
	var pos := Vector2(tile) + Vector2(0.62 + _rng.randf_range(-0.08, 0.08), -0.55)
	_add({"kind": "smoke", "pos": pos, "vel": Vector2(_rng.randf_range(0.08, 0.2), -0.32), "t": 0.0, "life": _rng.randf_range(2.2, 3.0),
		"size": _rng.randf_range(0.1, 0.16), "col": Color(0.82, 0.8, 0.78, 0.55)})


# ---------------------------------------------------------------- drawing

## Over the entities, in world space. `tpx` is the tile size on screen.
func draw(canvas: CanvasItem, tpx: int) -> void:
	if not enabled:
		return
	var t := float(tpx)
	# the markers of state: a construction arc, a waiting crate
	for id in _seen:
		var s: Dictionary = _seen[id]
		if str(s.get("cls", "")) != "building":
			continue
		var tile: Vector2i = s["tile"]
		if not view_bounds.has_point(tile):
			continue
		var c := Vector2((float(tile.x) + 0.5) * t, (float(tile.y) - 0.35) * t)
		if bool(s.get("constructing", false)) and float(s.get("max_hp", 0)) > 0.0:
			var ratio := clampf(float(s["hp"]) / float(s["max_hp"]), 0.0, 1.0)
			canvas.draw_arc(c, t * 0.34, -PI * 0.5, -PI * 0.5 + TAU, 28, Color(0.1, 0.08, 0.14, 0.45), maxf(2.0, t * 0.07))
			if ratio > 0.01:
				canvas.draw_arc(c, t * 0.34, -PI * 0.5, -PI * 0.5 + TAU * ratio, 28, Color(1.0, 0.85, 0.4, 0.9), maxf(2.0, t * 0.07))
		elif _waiting.has(id) and _time - float(_waiting[id]) >= WAIT_AFTER:
			var pulse := 0.5 + 0.5 * sin(_time * 2.2)
			var a := 0.28 + 0.22 * pulse
			var r := t * 0.17
			var box := Rect2(c - Vector2(r, r + t * 0.06 * pulse), Vector2(r * 2.0, r * 2.0))
			canvas.draw_rect(box, Color(0.95, 0.85, 0.55, a), false, maxf(1.5, t * 0.04))
			canvas.draw_line(box.position + Vector2(0, r), box.position + Vector2(r * 2.0, r), Color(0.95, 0.85, 0.55, a * 0.7), maxf(1.0, t * 0.03))
	for p in _parts:
		var k: float = float(p["t"]) / float(p["life"])
		var pos: Vector2 = p["pos"] * t
		var size: float = float(p["size"]) * t
		var col: Color = p["col"]
		match str(p["kind"]):
			"smoke":
				canvas.draw_circle(pos, size * (1.0 + 2.2 * k), Color(col.r, col.g, col.b, col.a * (1.0 - k) * (1.0 - k)))
			"dust", "chip", "spark":
				var fade := 1.0 - k
				canvas.draw_rect(Rect2(pos - Vector2(size, size) * 0.5, Vector2(size, size)), Color(col.r, col.g, col.b, col.a * fade), true)
			"ring":
				var rr: float = size * (0.3 + 0.7 * k)
				canvas.draw_arc(pos, rr, 0.0, TAU, 32, Color(col.r, col.g, col.b, col.a * (1.0 - k)), maxf(1.5, t * 0.05))
			"ware":
				var fade := 1.0 - maxf(0.0, (k - 0.55) / 0.45)
				var tex: Texture2D = p.get("tex")
				if tex != null:
					var sz := Vector2(tex.get_width(), tex.get_height())
					var sc: float = size / maxf(sz.x, sz.y)
					var dims := sz * sc
					canvas.draw_circle(pos, maxf(dims.x, dims.y) * 0.6, Color(0.05, 0.05, 0.05, 0.4 * fade))
					canvas.draw_texture_rect(tex, Rect2(pos - dims * 0.5, dims), false, Color(1, 1, 1, fade))
				else:
					canvas.draw_circle(pos, size * 0.3, Color(0.9, 0.8, 0.5, fade))


func particle_count() -> int:
	return _parts.size()
