extends RefCounted
class_name DmbQuests
## Settlement quest templates: short binary-decision trees with persistent
## outcomes and world effects (brief §5). A template is instantiated per
## settlement from sim state (faction, terrain, infection), so the same script
## reads differently in a sheep steading under outbreak than in a mining town.
##
## Tree shape: nodes keyed by id; each has speaker, text, and either two
## `choices` [{label, next}] or an `outcome` id. Outcomes carry `effects`:
##   {"item": id}                 -> grant an inventory item
##   {"weight": [fid, key, delta]} -> nudge the owning faction's AI weights
##   {"treat": hid}               -> remove one demon from the settlement's hex
##   {"resource": [fid, res, n]}  -> give/take faction resources
##   {"mood": word}               -> settlement presentation state
##   {"fight": enemy_id}          -> a duel before the outcome lands
## The outcome id is persisted per settlement; NPC lines and map dressing read it.

const TEMPLATES := ["missing_flock", "tainted_well", "road_toll"]


static func pick_template(sim: DmbWorldSim, snid: int) -> String:
	var s: Dictionary = sim.catan.settlements.get(snid, {})
	if s.is_empty():
		return ""
	var terrains := terrain_counts(sim, snid)
	var infected := infected_hexes(sim, snid)
	if not infected.is_empty():
		return "tainted_well"
	if int(terrains.get("pasture", 0)) > 0:
		return "missing_flock"
	return "road_toll"


static func terrain_counts(sim: DmbWorldSim, snid: int) -> Dictionary:
	var out := {}
	for hid in sim.board.nodes[snid]["hexes"]:
		var t := str(sim.board.hexes[hid]["terrain"])
		out[t] = int(out.get(t, 0)) + 1
	return out


static func infected_hexes(sim: DmbWorldSim, snid: int) -> Array:
	var out: Array = []
	for hid in sim.board.nodes[snid]["hexes"]:
		if int(sim.board.hexes[hid]["demons"]) > 0:
			out.append(int(hid))
	return out


## Build a concrete quest for a settlement. Names are drawn deterministically
## from the node id so the same steading keeps the same people.
static func build(sim: DmbWorldSim, snid: int) -> Dictionary:
	var tid := pick_template(sim, snid)
	if tid == "":
		return {}
	return build_template(sim, snid, tid)


## Build a specific template for a settlement (tests; forced stories).
static func build_template(sim: DmbWorldSim, snid: int, tid: String) -> Dictionary:
	var s: Dictionary = sim.catan.settlements[snid]
	var fid := str(s["owner"])
	var names := _names(snid)
	var infected := infected_hexes(sim, snid)
	var hid: int = infected[0] if not infected.is_empty() else int(sim.board.nodes[snid]["hexes"][0])
	var q := {"id": "%s_%d" % [tid, snid], "template": tid, "settlement": snid, "faction": fid,
		"npcs": [], "nodes": {}, "outcomes": {}}
	match tid:
		"missing_flock":
			q["title"] = "The Missing Flock"
			q["npcs"] = [{"id": "shepherd", "name": names[0], "sprite": "shepherd", "role": "shepherd"},
				{"id": "reeve", "name": names[1], "sprite": "official", "role": "reeve"},
				{"id": "child", "name": names[2], "sprite": "child", "role": "child"}]
			q["start"] = "shepherd"
			q["nodes"] = {
				"root": {"speaker": "shepherd", "text": "%s. Forty head, gone off the high walk in the night. No blood. The reeve says wolves. The reeve has never seen a wolf." % names[0],
					"choices": [{"label": "Ask the reeve", "next": "reeve"}, {"label": "Walk the high pasture", "next": "walk"}]},
				"reeve": {"speaker": "reeve", "text": "Wolves. Write it down as wolves. If it goes down as demons the Wardens send a champion and the champion eats for a month at our cost.",
					"choices": [{"label": "Write it down as wolves", "next": "out_wolves"}, {"label": "Report the truth", "next": "out_truth"}]},
				"walk": {"speaker": "child", "text": "%s (whispering): I saw. They walked into the ground. The ground opened for them like a mouth. Don't tell my mother I was up there." % names[2],
					"choices": [{"label": "Face what is in the ground", "next": "out_fight"}, {"label": "Bring the child home and say nothing", "next": "out_quiet"}]},
			}
			q["outcomes"] = {
				"out_wolves": {"text": "The reeve writes 'wolves'. The shepherd spits. The books balance, and the ground keeps whatever it took.",
					"effects": [{"weight": [fid, "treat", -0.2]}, {"mood": "uneasy"}, {"item": "token_%s" % fid}]},
				"out_truth": {"text": "The reeve writes what you tell him and hates you for it. A rider goes out that night. The steading eats thin for a month — and the ground gets watched.",
					"effects": [{"weight": [fid, "treat", 0.3]}, {"resource": [fid, "grain", -1]}, {"mood": "watched"}, {"item": "token_%s" % fid}]},
				"out_fight": {"text": "Whatever took the flock did not expect the flock to be followed. You come back down the walk with ash on your boots. The child is a hero for a week.",
					"effects": [{"fight": "flame_imp"}, {"treat": hid}, {"mood": "grateful"}, {"item": "token_%s" % fid}]},
				"out_quiet": {"text": "You take the child home. You say nothing. Some nights the high walk glows a little, and nobody goes up to look.",
					"effects": [{"item": "token_%s" % fid}, {"mood": "uneasy"}, {"item": "black_seed"}]},
			}
		"tainted_well":
			q["title"] = "The Tainted Well"
			q["npcs"] = [{"id": "healer", "name": names[0], "sprite": "elder", "role": "healer"},
				{"id": "digger", "name": names[1], "sprite": "dwarf", "role": "well-digger"},
				{"id": "mother", "name": names[2], "sprite": "villager_b", "role": "mother"}]
			q["start"] = "healer"
			q["nodes"] = {
				"root": {"speaker": "healer", "text": "%s. The well water has gone sweet. Sweet is wrong. Three children sick and the digger wants to seal it and dig another, which takes a month we do not have." % names[0],
					"choices": [{"label": "Look at the well yourself", "next": "well"}, {"label": "Talk to the mother", "next": "mother"}]},
				"well": {"speaker": "digger", "text": "There is something at the bottom. It hums. I am not going down. Seal it, or you go down.",
					"choices": [{"label": "Go down", "next": "out_fight"}, {"label": "Seal it and dig new", "next": "out_seal"}]},
				"mother": {"speaker": "mother", "text": "The healer says boil it. The digger says seal it. I say the Wardens should send someone who knows and they have not. Do you know?",
					"choices": [{"label": "Send for the faction's champion", "next": "out_champion"}, {"label": "Treat the water with magic", "next": "out_magic"}]},
			}
			q["outcomes"] = {
				"out_fight": {"text": "You come up out of the well with something's teeth in your sleeve and nothing's teeth in the water. The digger buys you a drink. From a different well.",
					"effects": [{"fight": "steam_sprite"}, {"treat": hid}, {"mood": "grateful"}, {"item": "token_%s" % fid}]},
				"out_seal": {"text": "The well is capped. The new one takes six weeks. Two of the three children get better. The steading remembers the third.",
					"effects": [{"item": "token_%s" % fid}, {"resource": [fid, "brick", -1]}, {"mood": "mourning"}, {"item": "cure_note"}]},
				"out_champion": {"text": "The rider goes. The champion comes, eventually, and the thing in the well is dealt with — in the ledgers, by the steading, at the champion's rates.",
					"effects": [{"weight": [fid, "fight", 0.3]}, {"resource": [fid, "wool", -1]}, {"treat": hid}, {"mood": "watched"}, {"item": "token_%s" % fid}]},
				"out_magic": {"text": "Water answers Water. The sweetness goes out of the well like a held breath let go. The healer watches you very carefully after that.",
					"effects": [{"treat": hid}, {"mood": "wary"}, {"item": "token_%s" % fid}]},
			}
		_:
			q["template"] = "road_toll"
			q["id"] = "road_toll_%d" % snid
			q["title"] = "The Road Toll"
			q["npcs"] = [{"id": "carter", "name": names[0], "sprite": "villager_b", "role": "carter"},
				{"id": "tollman", "name": names[1], "sprite": "knight", "role": "tollman"},
				{"id": "smith", "name": names[2], "sprite": "dwarf", "role": "smith"}]
			q["start"] = "carter"
			q["nodes"] = {
				"root": {"speaker": "carter", "text": "%s. There's a toll on the road now. The tollman says it's for the faction. The faction has never heard of him." % names[0],
					"choices": [{"label": "Confront the tollman", "next": "toll"}, {"label": "Ask the smith", "next": "smith"}]},
				"toll": {"speaker": "tollman", "text": "Toll's a coin a cart. Roads don't mend themselves. You want to see my warrant? Here's my warrant.",
					"choices": [{"label": "Fight him", "next": "out_fight"}, {"label": "Pay, and carry word to the ruler", "next": "out_report"}]},
				"smith": {"speaker": "smith", "text": "He's my brother. He was a soldier and now he isn't, and nobody has told him what to be instead. Take him on as a road-warden. Officially.",
					"choices": [{"label": "Make him road-warden", "next": "out_warden"}, {"label": "Tell the ruler to remove him", "next": "out_remove"}]},
			}
			q["outcomes"] = {
				"out_fight": {"text": "He is a better soldier than a tollman. Not by enough. The carts roll free, and the smith does not speak to you again.",
					"effects": [{"fight": "flame_wisp"}, {"mood": "uneasy"}, {"item": "token_%s" % fid}]},
				"out_report": {"text": "The ruler hears. The tollman is gone in a week, and the road gets a proper post — and a proper toll, which the carters like even less.",
					"effects": [{"weight": [fid, "roads", 0.3]}, {"resource": [fid, "ore", 1]}, {"mood": "watched"}, {"item": "token_%s" % fid}]},
				"out_warden": {"text": "He takes the job like a man handed a rope on a cliff. The road is the safest in the country within the season.",
					"effects": [{"weight": [fid, "roads", 0.2]}, {"weight": [fid, "fight", 0.1]}, {"mood": "grateful"}, {"item": "token_%s" % fid}]},
				"out_remove": {"text": "Soldiers come for him. The smith closes his shutters. The toll is gone; so is the smith, by spring.",
					"effects": [{"item": "token_%s" % fid}, {"resource": [fid, "ore", -1]}, {"mood": "mourning"}, {"item": "brass_gear"}]},
			}
	return q


## Apply an outcome's world effects to the sim. Returns text lines describing
## anything the player would notice. `fight` is handled by the client before
## calling this.
static func apply_effects(sim: DmbWorldSim, q: Dictionary, outcome_id: String) -> Array:
	var notes: Array = []
	var out: Dictionary = q["outcomes"].get(outcome_id, {})
	for eff in out.get("effects", []):
		if eff.has("weight"):
			var w: Array = eff["weight"]
			sim.ruler_adjust(str(w[0]), str(w[1]), float(w[2]))
			notes.append("%s will weigh %s differently now." % [DmbFactions.name_of(str(w[0])), str(w[1])])
		elif eff.has("treat"):
			var hid := int(eff["treat"])
			if int(sim.board.hexes[hid]["demons"]) > 0:
				sim.infection.treat(hid)
				notes.append("The ground here breathes easier.")
		elif eff.has("resource"):
			var r: Array = eff["resource"]
			var fid := str(r[0])
			var res := str(r[1])
			var n := int(r[2])
			sim.catan.hands[fid][res] = maxi(0, int(sim.catan.hands[fid].get(res, 0)) + n)
	sim.settlement_moods[int(q["settlement"])] = str(_mood(out))
	return notes


static func _mood(out: Dictionary) -> String:
	for eff in out.get("effects", []):
		if eff.has("mood"):
			return str(eff["mood"])
	return ""


static func item_grants(q: Dictionary, outcome_id: String) -> Array:
	var items: Array = []
	for eff in q["outcomes"].get(outcome_id, {}).get("effects", []):
		if eff.has("item"):
			items.append(str(eff["item"]))
	return items


static func fight_for(q: Dictionary, outcome_id: String) -> String:
	for eff in q["outcomes"].get(outcome_id, {}).get("effects", []):
		if eff.has("fight"):
			return str(eff["fight"])
	return ""


## Every root→outcome path, for tests: proves each tree is binary and total.
static func all_paths(q: Dictionary) -> Array:
	var paths: Array = []
	_walk(q, "root", [], paths)
	return paths


static func _walk(q: Dictionary, node_id: String, so_far: Array, paths: Array) -> void:
	if q["outcomes"].has(node_id):
		var p := so_far.duplicate()
		p.append(node_id)
		paths.append(p)
		return
	var n: Dictionary = q["nodes"].get(node_id, {})
	for c in n.get("choices", []):
		var p := so_far.duplicate()
		p.append(node_id)
		_walk(q, str(c["next"]), p, paths)


static func _names(snid: int) -> Array:
	const A := ["Maud", "Tobin", "Wenna", "Hal", "Bryda", "Osric", "Tamsin", "Garet", "Ysolt", "Piran", "Edda", "Colm"]
	var out: Array = []
	for i in range(3):
		out.append(A[(snid * 3 + i * 5) % A.size()])
	return out
