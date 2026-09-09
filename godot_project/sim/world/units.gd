class_name DmbUnits
extends RefCounted
## Champions and Heroes on the world board.
##
## * Champion: one per faction, named, persistent. Loses → retreats home and
##   recovers for a few turns instead of dying.
## * Hero: spawned when a faction plays a Knight card. Expendable.
##
## Units stand on nodes, move one edge per turn, may Treat (remove one demon)
## from any hex touching their node, and may Fight demons on such a hex.
## Fights resolve off-screen: unit weave size vs demon count. If weave size
## exceeds the demon count the unit wins outright; otherwise a seeded roll.
##
## Unit: {id, kind, faction, name, bestiary_id, node, alive, recovering}

const HERO_FORMS := ["steam_brute", "cinder_golem", "trog_champion", "rival_wizard"]
const DEMON_FORMS := {1: "flame_imp", 2: "moss_shade", 3: "mirror_demon"}
const RECOVERY_TURNS := 3

var board: DmbHexBoard
var catan: DmbCatanState
var infection: DmbInfection
var units: Array = []
var log: Array = []
var rng := RandomNumberGenerator.new()
var _next_id: int = 1


func _init(p_board: DmbHexBoard = null, p_catan: DmbCatanState = null, p_inf: DmbInfection = null, seed: int = 0) -> void:
	board = p_board
	catan = p_catan
	infection = p_inf
	rng.seed = seed


static func demon_form(demons: int) -> String:
	return DEMON_FORMS.get(clampi(demons, 0, 3), "")


# --- queries ----------------------------------------------------------------

func get_unit(uid: int) -> Dictionary:
	for u in units:
		if u["id"] == uid:
			return u
	return {}


func alive() -> Array:
	var out := []
	for u in units:
		if u["alive"]:
			out.append(u)
	return out


func alive_ids() -> Array:
	var out := []
	for u in alive():
		out.append(u["id"])
	return out


func units_at(nid: int) -> Array:
	var out := []
	for u in alive():
		if u["node"] == nid:
			out.append(u)
	return out


func champion_of(fid: String):
	for u in units:
		if u["kind"] == "champion" and u["faction"] == fid:
			return u
	return null


func heroes_of(fid: String) -> Array:
	var out := []
	for u in alive():
		if u["kind"] == "hero" and u["faction"] == fid:
			out.append(u)
	return out


func units_of(fid: String) -> Array:
	var out := []
	for u in alive():
		if u["faction"] == fid:
			out.append(u)
	return out


func home_node(fid: String) -> int:
	var owned := catan.nodes_of(fid)
	return -1 if owned.is_empty() else owned[0]


# --- spawning ---------------------------------------------------------------

func spawn_champion(fid: String, name: String, bestiary_id: String):
	var existing = champion_of(fid)
	if existing != null:
		return existing
	var home := home_node(fid)
	if home < 0:
		return null
	var u := _make("champion", fid, name, bestiary_id, home)
	log.append({"type": "champion_arrives", "unit": u["id"], "faction": fid, "node": home})
	return u


func spawn_hero(fid: String):
	var home := home_node(fid)
	if home < 0:
		return null
	var form: String = HERO_FORMS[rng.randi_range(0, HERO_FORMS.size() - 1)]
	var u := _make("hero", fid, "", form, home)
	log.append({"type": "hero_mustered", "unit": u["id"], "faction": fid, "node": home})
	return u


func _make(kind: String, fid: String, name: String, bestiary_id: String, node: int) -> Dictionary:
	var u := {
		"id": _next_id, "kind": kind, "faction": fid, "name": name,
		"bestiary_id": bestiary_id, "node": node, "alive": true, "recovering": 0,
	}
	_next_id += 1
	units.append(u)
	return u


# --- movement ---------------------------------------------------------------

func move(uid: int, to: int) -> bool:
	var u := get_unit(uid)
	if u.is_empty() or not u["alive"] or u["recovering"] > 0:
		return false
	if board.edge_between(u["node"], to) < 0:
		return false
	u["node"] = to
	return true


## Move one edge along the shortest path toward `target`. Returns true if moved.
func step_toward(uid: int, target: int) -> bool:
	var u := get_unit(uid)
	if u.is_empty() or u["node"] == target:
		return false
	var path := board.shortest_path(u["node"], target)
	if path.size() < 2:
		return false
	return move(uid, path[1])


# --- treating ---------------------------------------------------------------

func treatable_hexes(uid: int) -> Array:
	var u := get_unit(uid)
	var out := []
	if u.is_empty() or not u["alive"]:
		return out
	for hid in board.nodes[u["node"]]["hexes"]:
		if board.hexes[hid]["demons"] > 0:
			out.append(hid)
	return out


func treat(uid: int, hid: int) -> bool:
	var u := get_unit(uid)
	if u.is_empty() or not u["alive"] or u["recovering"] > 0:
		return false
	if not (hid in board.nodes[u["node"]]["hexes"]) or board.hexes[hid]["demons"] <= 0:
		return false
	infection.treat(hid)
	log.append({"type": "treat", "unit": uid, "faction": u["faction"], "hex": hid, "left": board.hexes[hid]["demons"]})
	return true


# --- combat -----------------------------------------------------------------

func weave_size(u: Dictionary) -> int:
	if DmbBestiary.has(u["bestiary_id"]):
		return int(DmbBestiary.get_data(u["bestiary_id"]).get("weave_size", 2))
	return 2


## Fight the demons on an adjacent hex. Returns {outcome: win|lose, ...}.
func fight(uid: int, hid: int) -> Dictionary:
	var u := get_unit(uid)
	var demons: int = board.hexes[hid]["demons"]
	if u.is_empty() or not u["alive"] or demons <= 0 or not (hid in board.nodes[u["node"]]["hexes"]):
		return {"outcome": "none"}
	var w := weave_size(u)
	var win := false
	if w > demons:
		win = true
	else:
		# Roll: unit strength vs demon strength, seeded.
		win = rng.randi_range(1, w + demons) <= w
	var entry := {"type": "fight", "unit": uid, "faction": u["faction"], "hex": hid,
		"demon_id": demon_form(demons), "demons": demons, "weave": w}
	if win:
		infection.treat(hid)
		entry["outcome"] = "win"
	else:
		entry["outcome"] = "lose"
		if u["kind"] == "champion":
			u["node"] = home_node(u["faction"]) if home_node(u["faction"]) >= 0 else u["node"]
			u["recovering"] = RECOVERY_TURNS
		else:
			u["alive"] = false
	log.append(entry)
	return entry


## Called once per world turn: recovering champions heal.
func tick() -> void:
	for u in units:
		if u["recovering"] > 0:
			u["recovering"] -= 1


# --- serialisation ----------------------------------------------------------

func to_dict() -> Dictionary:
	return {"units": alive().duplicate(true), "next_id": _next_id, "rng": rng.state}


static func from_dict(d: Dictionary, p_board: DmbHexBoard, p_catan: DmbCatanState, p_inf: DmbInfection) -> DmbUnits:
	var us := DmbUnits.new(p_board, p_catan, p_inf, 0)
	for raw in d.get("units", []):
		var u := {}
		for k in raw:
			u[k] = raw[k]
		for k in ["id", "node", "recovering"]:
			u[k] = int(u.get(k, 0))
		u["alive"] = true
		us.units.append(u)
	us._next_id = int(d.get("next_id", 1))
	us.rng.state = int(d.get("rng", 0))
	return us
