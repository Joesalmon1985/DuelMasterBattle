extends DmbTestCase
## P0 canon regression tests: the five known deathtrap_ff pack corruptions must
## never re-enter the game as canon, and every used passage carries a verification
## status enforced here. See docs/DEATHTRAP_OVERHAUL_PLAN.md P0 and DD/ report §19.

const CANON_PATH := "res://content/dd_canon.json"
const PASSAGES_DIR := "res://content/dd_passages"
const VALID_STATUSES := [
	"BOOK_VERIFIED",
	"BOOK_VERIFIED_OCR_MESSY",
	"NEEDS_PAGE_IMAGE_CHECK",
	"NOT_YET_VERIFIED",
]

var _canon: Dictionary = {}


func run() -> void:
	_load_canon()
	if _canon.is_empty():
		return
	_check_schema()
	_check_known_corruptions()
	_check_gems_and_lock()
	_check_roster()
	_check_spell_placements()
	_check_passage_files()


func _load_canon() -> void:
	if not FileAccess.file_exists(CANON_PATH):
		_failures.append("canon file missing: %s" % CANON_PATH)
		return
	var text := FileAccess.get_file_as_string(CANON_PATH)
	var data = JSON.parse_string(text)
	if typeof(data) != TYPE_DICTIONARY:
		_failures.append("canon file is not a JSON object")
		return
	_canon = data


func _node(passage: int) -> Dictionary:
	for n in _canon.get("nodes", []):
		if int(n.get("passage", -1)) == passage:
			return n
	_failures.append("canon node missing for passage %d" % passage)
	return {}


func _edges(n: Dictionary) -> Array:
	var out: Array = []
	for e in n.get("edges", []):
		var t = e.get("to")
		if typeof(t) == TYPE_ARRAY:
			for x in t:
				out.append(int(x))
		else:
			out.append(int(t))
	return out


func _check_schema() -> void:
	for key in ["nodes", "required_items", "contestants", "passage_status", "roster", "spell_placements"]:
		assert_true(_canon.has(key), "canon has '%s'" % key)


func _check_known_corruptions() -> void:
	# p.22 must be the Throm/Barbarian alliance, never a Giant Spider.
	var n22 := _node(22)
	if not n22.is_empty():
		var beat := str(n22.get("beat", ""))
		assert_true(beat.contains("Throm") or beat.contains("Barbarian"), "p.22 beat is Throm alliance")
		assert_true(not beat.contains("Spider"), "p.22 beat is not a spider")
		var e22 := _edges(n22)
		for t in [63, 184, 311]:
			assert_true(t in e22, "p.22 edge to %d" % t)
	# p.60 must expose BOTH branches: attack-Dwarf (179) and persuade (365).
	var n60 := _node(60)
	if not n60.is_empty():
		var e60 := _edges(n60)
		assert_true(179 in e60, "p.60 exposes attack-Dwarf branch (179)")
		assert_true(365 in e60, "p.60 exposes persuade-Throm branch (365)")
	# p.281 must be the dying Elf / diamond clue, never a Skeleton.
	var n281 := _node(281)
	if not n281.is_empty():
		var beat281 := str(n281.get("beat", ""))
		assert_true(beat281.contains("Elf"), "p.281 beat is the dying Elf")
		assert_true(not beat281.contains("Skeleton"), "p.281 beat is not a skeleton")
		var e281 := _edges(n281)
		assert_true(399 in e281 or 192 in e281, "p.281 continues via bread/mirror route")
	# p.302 must be the forced Throm confrontation, never a Giant Spider.
	var n302 := _node(302)
	if not n302.is_empty():
		var beat302 := str(n302.get("beat", ""))
		assert_true(beat302.contains("Throm"), "p.302 beat is forced Throm fight")
		assert_true(not beat302.contains("Spider"), "p.302 beat is not a spider")
		assert_true(379 in _edges(n302), "p.302 edge to 379")
	# p.399 must continue to 192 (Elf bread), never a death ending.
	var n399 := _node(399)
	if not n399.is_empty():
		assert_true(192 in _edges(n399), "p.399 continues to 192")
		assert_true(not str(n399.get("beat", "")).contains("death"), "p.399 is not a death")


func _check_gems_and_lock() -> void:
	var items: Dictionary = _canon.get("required_items", {})
	for gem in ["emerald", "sapphire", "diamond"]:
		assert_true(items.has(gem), "required gem: %s" % gem)
	# p.62 gem lock must expose six permutations with positional feedback.
	var n62 := _node(62)
	if not n62.is_empty():
		var e62 := _edges(n62)
		assert_eq(e62.size(), 6, "p.62 exposes six gem permutations")


func _check_roster() -> void:
	# Decision: five book contestants + Red Wizard + John = seven entrants.
	var roster: Dictionary = _canon.get("roster", {})
	var entrants: Array = roster.get("entrants", [])
	assert_eq(entrants.size(), 7, "seven Trial entrants")
	for id in ["knight", "elf", "throm", "assassin", "second_barbarian", "red_wizard", "john"]:
		assert_true(id in entrants, "entrant: %s" % id)


func _check_spell_placements() -> void:
	# Decisions: Fire = red book, Stone = Dwarf test, Vine = Elf charm,
	# Light = Mirror Demon, Shadow = Bloodbeast lair.
	var sp: Dictionary = _canon.get("spell_placements", {})
	assert_eq(str(sp.get("fire", {}).get("source", "")), "red_book", "Fire from the red book")
	assert_eq(str(sp.get("stone", {}).get("source", "")), "dwarf_test", "Stone from the Dwarf test")
	assert_eq(str(sp.get("vine", {}).get("source", "")), "elf_charm", "Vine from the Elf charm")
	assert_eq(str(sp.get("light", {}).get("source", "")), "mirror_demon", "Light from Mirror Demon")
	assert_eq(str(sp.get("shadow", {}).get("source", "")), "bloodbeast_lair", "Shadow from Bloodbeast lair")


func _check_passage_files() -> void:
	var statuses: Dictionary = _canon.get("passage_status", {})
	# p.149 (betrayal route) is explicitly unverified: no invented content.
	assert_eq(str(statuses.get("149", "")), "NEEDS_PAGE_IMAGE_CHECK", "p.149 needs page check")
	for key in statuses.keys():
		var status := str(statuses[key])
		assert_true(status in VALID_STATUSES, "p.%s has valid status (got %s)" % [key, status])
		assert_true(status != "INFERRED_AS_CANON", "p.%s never inferred-as-canon" % key)
		var path := "%s/%s.json" % [PASSAGES_DIR, key]
		assert_true(FileAccess.file_exists(path), "passage file exists: %s" % path)
		if FileAccess.file_exists(path):
			var data = JSON.parse_string(FileAccess.get_file_as_string(path))
			assert_true(typeof(data) == TYPE_DICTIONARY, "p.%s file is a JSON object" % key)
			if typeof(data) == TYPE_DICTIONARY:
				assert_eq(str(data.get("status", "")), status, "p.%s file status agrees" % key)
				assert_eq(int(data.get("passage", -1)), int(key), "p.%s file passage agrees" % key)
