extends RefCounted
class_name DmbDungeons
## Settlement-driven dungeon registry (brief §6–§7). Every settlement that exists
## when the world is created spawns a TOWER on a suitable nearby node; settlements
## founded later spawn a CAVE. The chosen node is reserved from settlement/city
## development. Each dungeon holds four puzzles drawn from the catalogue, and at
## least one of them needs a key item produced by an EARLIER dungeon or by the
## founding settlement — dependencies only ever point backwards in creation
## order, so the graph is a DAG by construction and the game stays solvable.

const REWARD_COLOURS := [3, 6, 2, 4, 5]   # Stone, Vine, Storm, Light, Shadow — offered in order, skipping known

var board: DmbHexBoard
var catan: DmbCatanState
var rng := RandomNumberGenerator.new()
var dungeons: Array = []            # [{id, kind, node, settlement, faction, seed, puzzles, needs, provides, reward}]
var reserved: Dictionary = {}       # nid -> dungeon id


func _init(p_board: DmbHexBoard, p_catan: DmbCatanState, seed: int) -> void:
	board = p_board
	catan = p_catan
	rng.seed = seed


# --- creation -----------------------------------------------------------------

## Called once after Catan setup: one tower per founding settlement.
func seed_towers() -> void:
	var nids := catan.settlements.keys()
	nids.sort()
	for nid in nids:
		spawn_for_settlement(int(nid), "tower")


## Called when a settlement is founded later: one cave. Returns the dungeon or {}.
func spawn_for_settlement(snid: int, kind: String) -> Dictionary:
	for d in dungeons:
		if int(d["settlement"]) == snid:
			return {}
	var nid := _pick_node(snid)
	if nid < 0:
		return {}
	var owner := str(catan.settlements.get(snid, {}).get("owner", ""))
	var idx := dungeons.size()
	var d := {
		"id": "%s_%d" % [kind, nid], "kind": kind, "node": nid, "settlement": snid, "faction": owner,
		"seed": int(rng.randi()), "index": idx,
		"provides": "sigil_%s" % _sigil_word(idx),
		"needs": _dependency(idx, owner),
		"reward": {},
	}
	d["puzzles"] = DmbPuzzleGen.generate(d)
	dungeons.append(d)
	reserved[nid] = d["id"]
	return d


## Nearest free node to the settlement: not a settlement, not reserved, and not
## adjacent to a settlement (so Catan's distance rule is preserved both ways).
## Ties broken by node id for determinism.
func _pick_node(snid: int) -> int:
	var best := -1
	var best_d := 99
	var frontier: Array = [snid]
	var dist := {snid: 0}
	while not frontier.is_empty():
		var cur: int = frontier.pop_front()
		var dcur: int = dist[cur]
		if dcur > 3:
			continue
		for nb in board.node_neighbors(cur):
			if dist.has(nb):
				continue
			dist[nb] = dcur + 1
			frontier.append(nb)
	var cands := dist.keys()
	cands.sort()
	for nid in cands:
		var dn: int = dist[nid]
		if dn == 0 or dn > best_d:
			continue
		if catan.settlements.has(nid) or reserved.has(nid):
			continue
		var adjacent_settlement := false
		for nb in board.node_neighbors(nid):
			if catan.settlements.has(nb) and nb != snid and dn == 1:
				adjacent_settlement = true
		if adjacent_settlement:
			continue
		if dn < best_d or best < 0:
			best_d = dn
			best = nid
	return best


## Dungeon 0 depends on the founding settlement's token (a quest reward there);
## every later dungeon depends on the sigil of an earlier one. Always backwards.
func _dependency(idx: int, owner: String) -> Dictionary:
	if idx == 0 or dungeons.is_empty():
		return {"item": "token_%s" % owner, "from": "settlement"}
	var src: Dictionary = dungeons[rng.randi_range(0, dungeons.size() - 1)]
	return {"item": str(src["provides"]), "from": str(src["id"])}


static func _sigil_word(idx: int) -> String:
	const WORDS := ["ash", "salt", "iron", "moss", "bone", "tide", "ember", "root", "glass", "frost", "lime", "tallow"]
	return WORDS[idx % WORDS.size()] + ("" if idx < WORDS.size() else str(idx / WORDS.size()))


# --- queries ------------------------------------------------------------------

func is_reserved(nid: int) -> bool:
	return reserved.has(nid)


func at_node(nid: int) -> Dictionary:
	for d in dungeons:
		if int(d["node"]) == nid:
			return d
	return {}


func get_dungeon(id: String) -> Dictionary:
	for d in dungeons:
		if str(d["id"]) == id:
			return d
	return {}


func by_settlement(snid: int) -> Dictionary:
	for d in dungeons:
		if int(d["settlement"]) == snid:
			return d
	return {}


## Reward on completion: the next colour John does not know, else a cure fragment.
static func reward_for(d: Dictionary, spells_known: Array) -> Dictionary:
	for c in REWARD_COLOURS:
		if not (c in spells_known):
			return {"spell": c}
	return {"item": "cure_fragment_%d" % (int(d["index"]) + 1)}


## Solvability: dependency sources must exist and precede the dependant.
func validate() -> Array:
	var problems: Array = []
	for i in range(dungeons.size()):
		var d: Dictionary = dungeons[i]
		var need: Dictionary = d["needs"]
		if str(need["from"]) == "settlement":
			continue
		var src := get_dungeon(str(need["from"]))
		if src.is_empty():
			problems.append("%s needs %s from missing %s" % [d["id"], need["item"], need["from"]])
		elif int(src["index"]) >= i:
			problems.append("%s depends forward on %s" % [d["id"], src["id"]])
		elif str(src["provides"]) != str(need["item"]):
			problems.append("%s needs %s but %s provides %s" % [d["id"], need["item"], src["id"], src["provides"]])
	return problems


# --- save ---------------------------------------------------------------------

func to_dict() -> Dictionary:
	var res := {}
	for nid in reserved:
		res[str(nid)] = reserved[nid]
	return {"rng": rng.state, "dungeons": dungeons.duplicate(true), "reserved": res}


static func from_dict(d: Dictionary, p_board: DmbHexBoard, p_catan: DmbCatanState) -> DmbDungeons:
	var r := DmbDungeons.new(p_board, p_catan, 0)
	r.rng.state = int(d.get("rng", 0))
	for raw in d.get("dungeons", []):
		var dd: Dictionary = raw.duplicate(true)
		dd["node"] = int(dd["node"])
		dd["settlement"] = int(dd["settlement"])
		dd["index"] = int(dd["index"])
		dd["seed"] = int(dd["seed"])
		r.dungeons.append(dd)
	for k in d.get("reserved", {}):
		r.reserved[int(k)] = str(d["reserved"][k])
	return r
