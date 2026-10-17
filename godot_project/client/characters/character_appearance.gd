extends RefCounted
class_name DmbCharAppearance

## Who looks like what.  Named people have a fixed look; every other inhabitant gets one derived from its stable id
## (a hash, not a random generator), the job its definition names and the tribe of its faction.

const Lib = preload("res://client/characters/character_library.gd")
const Look = preload("res://client/characters/character_look.gd")

const WIZARD_OUTFITS := ["wizard", "wizard_hooded", "wizard_battle", "wizard_witch", "wizard_druid", "wizard_fire"]
const TRIBES := ["barbarians", "empire", "atlanteans", "frisians", "amazons"]

static var faction_tribes: Dictionary = {}   # faction name -> tribe, filled from the snapshot
static var faction_colors: Dictionary = {}   # faction name -> Color
static var unmapped: Dictionary = {}         # definitions that fell back to the generic worker (a test asserts this stays empty)


## A person who is the same in every conversation, location and session.
static func named(name: String) -> Look:
	var d := Lib.data()
	var table: Dictionary = d.get("named", {})
	if not table.has(name):
		return null
	var ck := "named:" + name
	var hit := Look.cached(ck)
	if hit != null:
		return hit
	var spec: Dictionary = table[name]
	var look := Look.make(ck, str(spec["outfit"]), Lib.stable_hash(ck), spec)
	look.display_name = name
	return Look.store(look)


static func has_named(name: String) -> bool:
	return Lib.data().get("named", {}).has(name)


## For the legacy actor keys ("john", "blue_mage", "farmer", ...). Unknown keys still get a real character, never a rectangle.
static func for_sprite(sprite: String, label: String = "") -> Look:
	var n := named(sprite)
	if n != null:
		return n
	var person := Look.cached(sprite)
	if person != null:
		return person
	var key := "sprite:%s:%s" % [sprite, label]
	var hit := Look.cached(key)
	if hit != null:
		return hit
	var h := Lib.stable_hash(key)
	var outfit := sprite if Lib.has_outfit(sprite) else "carrier"
	if not Lib.has_outfit(sprite):
		var o: Array = ["carrier", "farmer", "builder", "digger", "merchant", "herder"]
		outfit = o[h % o.size()]
	var look := Look.make(key, outfit, h, {"tribe": TRIBES[(h >> 5) % TRIBES.size()]})
	look.display_name = label
	return Look.store(look)


const OCCUPATION_WORDS := {
	"farm": "farmer", "bak": "baker", "wood": "woodcutter", "lumber": "woodcutter", "forest": "forester", "ranger": "forester", "mine": "miner", "smith": "smith",
	"smelt": "smith", "build": "builder", "mason": "mason", "stone": "mason", "fish": "fisher", "hunt": "hunter", "cook": "cook", "brew": "brewer", "mill": "miller",
	"carpent": "carpenter", "saw": "carpenter", "weav": "weaver", "herd": "herder", "shepherd": "herder", "garden": "gardener", "scout": "scout", "merchant": "merchant",
	"trader": "merchant", "guard": "spearman", "soldier": "spearman", "child": "child", "elder": "elder", "carrier": "carrier", "porter": "carrier", "worker": "carrier"}


## A key under which `for_sprite` yields the person of this id and occupation (used by the legacy village projections).
static func person_key(person_id: String, occupation: String) -> String:
	var occ := occupation.to_lower()
	var outfit := ""
	for word in OCCUPATION_WORDS:
		if occ.contains(word):
			outfit = OCCUPATION_WORDS[word]
			break
	if outfit == "":
		var pool := ["carrier", "farmer", "builder", "digger", "herder", "gardener"]
		outfit = pool[Lib.stable_hash(person_id) % pool.size()]
	var ck := "person:%s" % person_id
	if Look.cached(ck) == null:
		var h := Lib.stable_hash(person_id)
		var look := Look.make(ck, outfit, h, {"tribe": TRIBES[(h >> 5) % TRIBES.size()]})
		look.display_name = occupation
		Look.store(look)
	return ck


static func parse_job(definition: String) -> Dictionary:
	var s := definition
	var dot := s.find(".")
	var ns := s.substr(0, dot) if dot >= 0 else ""
	if dot >= 0:
		s = s.substr(dot + 1)
	if s.ends_with("_worker"):
		s = s.substr(0, s.length() - 7)
	var tribe := ""
	for t in TRIBES:
		if s.begins_with(t + "_"):
			tribe = t
			s = s.substr(t.length() + 1)
			break
	return {"ns": ns, "job": s, "tribe": tribe}


## The outfit a simulation definition stands for ("" when it is not a person, e.g. an animal or a vehicle).
static func outfit_for_definition(definition: String, tribe: String) -> String:
	var d := Lib.data()
	var p := parse_job(definition)
	var job := str(p["job"])
	match str(p["ns"]):
		"openra":
			return str(d.get("openra", {}).get(job, ""))
		"dmb":
			return str(d.get("dmb", {}).get(job, ""))
		"widelands":
			if job == "soldier":
				return str(d.get("soldiers", {}).get(tribe if tribe != "" else str(p["tribe"]), "soldier_empire"))
			if d.get("jobs", {}).has(job):
				return str(d["jobs"][job])
			return ""
	return ""


static func is_animal_definition(definition: String) -> bool:
	var job := str(parse_job(definition)["job"])
	return job in ["ox", "donkey", "horse", "tapir", "reindeer", "bunny", "deer", "dog"]


static func for_entity(e: Dictionary) -> Look:
	var id := str(e.get("id", ""))
	var definition := str(e.get("definition", ""))
	var faction := str(e.get("faction_name", ""))
	var tribe := str(faction_tribes.get(faction, ""))
	var p := parse_job(definition)
	if str(p["tribe"]) != "":
		tribe = str(p["tribe"])  # a barbarian miner wears barbarian colours even when a rival faction employs it
	var kind := str(e.get("kind", ""))
	var ck := "ent:%s:%s:%s" % [id, definition, tribe]
	var hit := Look.cached(ck)
	if hit != null:
		return hit
	var h := Lib.stable_hash(id + "|" + definition)
	var outfit := ""
	var spec := {"tribe": tribe if tribe != "" else TRIBES[h % TRIBES.size()]}
	if kind == "npc" or str(e.get("class", "")) == "npc":
		outfit = "healer" if str(e.get("role", "")) == "healer" else "miner"
		var nm := str(e.get("label", ""))
		h = Lib.stable_hash(id + "|npc")
		if outfit == "miner":
			spec["beard"] = ["short", "long", "braided", "mustache"][h % 4]
			spec["pal"] = {"a": [120, 112, 130], "b": [70, 64, 80]}
		var look_npc := Look.make(ck, outfit, h, spec)
		look_npc.display_name = nm
		return Look.store(look_npc)
	outfit = outfit_for_definition(definition, tribe)
	if outfit == "":
		unmapped[definition] = true
		outfit = "carrier"
	var mil := outfit.begins_with("soldier") or outfit in ["e1", "e2", "e3", "e4", "e6", "e7", "spy", "thief", "medic", "mechanic", "shock", "zombie", "clubman", "spearman", "slinger"]
	if mil and faction_colors.has(faction):
		var fc: Color = faction_colors[faction]
		spec["pal"] = {"c": [int(fc.r * 255.0), int(fc.g * 255.0), int(fc.b * 255.0)]}
	var look := Look.make(ck, outfit, h, spec)
	look.display_name = str(e.get("label", ""))
	return Look.store(look)


## A wizard on the LAN: one of six wizard cuts chosen by the player's stable id, dressed in that player's own colour.
static func for_player(pid: String, name: String, colour_hex: String) -> Look:
	var ck := "player:%s:%s" % [pid, colour_hex]
	var hit := Look.cached(ck)
	if hit != null:
		return hit
	var h := Lib.stable_hash("wiz|" + pid)
	var idx := maxi(0, int(pid.substr(1)) - 1) if pid.length() > 1 and pid.substr(1).is_valid_int() else (h % WIZARD_OUTFITS.size())
	var outfit: String = WIZARD_OUTFITS[idx % WIZARD_OUTFITS.size()]
	var c := Color.html(colour_hex) if colour_hex != "" else Color(0.4, 0.5, 0.9)
	var a := [int(c.r * 255.0), int(c.g * 255.0), int(c.b * 255.0)]
	var b := [int(c.r * 150.0), int(c.g * 150.0), int(c.b * 150.0)]
	var acc := [clampi(int(c.r * 120.0 + 135.0), 0, 255), clampi(int(c.g * 120.0 + 125.0), 0, 255), clampi(int(c.b * 100.0 + 60.0), 0, 255)]
	var look := Look.make(ck, outfit, h, {"pal": {"a": a, "b": b, "c": acc}, "tribe": "empire"})
	look.display_name = name
	return Look.store(look)


## Which look a story person (talk target) has: by entity first, by name otherwise.
static func for_story_person(npc: Dictionary) -> Look:
	var nm := str(npc.get("name", npc.get("label", ""))).to_lower()
	if has_named(nm):
		return named(nm)
	return for_entity(npc)
