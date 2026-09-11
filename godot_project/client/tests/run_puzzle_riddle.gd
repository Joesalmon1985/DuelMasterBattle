extends SceneTree

## Riddle-first interaction order through the REAL production path.
## Drives WorldPlay.interact_kit_puzzle (the same function the Overworld calls
## on facing interaction) with real Runner statics, the real pz_01 room, real
## Kit state and real projection output. Only the dialogue UI and Adventure are
## lightweight stubs, so assertions observe genuine production behaviour:
## the riddle must be read BEFORE any offering decision, even carrying one
## object; Leave installs nothing; wrong is rejected and kept; right installs.
##
## godot --headless --path godot_project --script res://client/tests/run_puzzle_riddle.gd

const _Runner = preload("res://client/scripts/puzzle_test_runner.gd")
const _WorldPlay = preload("res://client/world/world_play.gd")
const _Projection = preload("res://sim/world/puzzle_projection.gd")
const _Items = preload("res://sim/world/items.gd")
const _Kit = preload("res://sim/world/puzzle_kit.gd")

var _failures: Array = []


class FakeDialogue extends RefCounted:
	var tree: SceneTree
	var say_log: Array = []
	var choose_log: Array = []
	var next_pick := ""

	func say_async(_speaker: String, text: String) -> void:
		say_log.append(text)
		await tree.process_frame

	func choose_async(prompt: String, options: Array) -> String:
		choose_log.append({"prompt": prompt, "options": options.duplicate()})
		await tree.process_frame
		return next_pick


class FakeProg extends RefCounted:
	var spells_known: Array = []


class FakeAdv extends Node:
	var items_list: Array = []
	var progression = FakeProg.new()

	func items() -> Array:
		return items_list

	func has_item(id: String) -> bool:
		return id in items_list

	func add_item(id: String) -> void:
		items_list.append(id)

	func remove_item(id: String) -> void:
		items_list.erase(id)

	func learn_spell(_s: int) -> void:
		pass


class FakeWorld extends Node:
	var _dialogue: RefCounted


func _init() -> void:
	call_deferred("_run")


func _check(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func _run() -> void:
	await process_frame
	var dlg := FakeDialogue.new()
	dlg.tree = self
	var adv := FakeAdv.new()
	var world := FakeWorld.new()
	world._dialogue = dlg
	var wp: RefCounted = _WorldPlay.new()
	wp.setup(world, adv, null)

	_Runner.set_puzzle("pz_01")
	var room: Dictionary = _Runner.kit_room()
	var st: Dictionary = _Runner.kit_state()
	var e := _projected(room, st, "o1")  # mirror alcove
	_check(e.get("text", "").contains("never move"), "projected alcove carries the riddle")

	# 1. Single carried object, player walks away: riddle read, choice shown,
	#    nothing installed, nothing taken.
	adv.items_list = ["glass_bead"]
	dlg.say_log.clear()
	dlg.choose_log.clear()
	dlg.next_pick = "Leave"
	await wp.interact_kit_puzzle(e)
	_check(dlg.say_log.size() >= 1 and str(dlg.say_log[0]).contains("never move"),
		"riddle is read before the offering decision (got %s)" % str(dlg.say_log))
	_check(dlg.choose_log.size() == 1, "offering decision presented with one carried object")
	_check(str(dlg.choose_log[0]["options"][-1]) == "Leave", "Leave is offered")
	_check(str(st["rec"].get("o1", "")) == "", "Leave installs nothing")
	_check(adv.has_item("glass_bead"), "carried object kept after Leave")

	# 2. Wrong offering: rejected, kept, no flag.
	dlg.say_log.clear()
	dlg.choose_log.clear()
	dlg.next_pick = "Place %s" % _Items.name_of("glass_bead")
	await wp.interact_kit_puzzle(e)
	_check(str(st["rec"].get("o1", "")) == "", "wrong offering sets nothing")
	_check(adv.has_item("glass_bead"), "wrong offering is not lost")
	_check(not bool(_Kit.flags_now(room, st).get("o1", false)), "wrong offering sets no flag")

	# 3. Correct offering: installed, consumed, flag set.
	adv.items_list = ["mirror_shard"]
	dlg.say_log.clear()
	dlg.choose_log.clear()
	dlg.next_pick = "Place %s" % _Items.name_of("mirror_shard")
	await wp.interact_kit_puzzle(e)
	_check(str(st["rec"].get("o1", "")) == "mirror_shard", "correct offering installed")
	_check(not adv.has_item("mirror_shard"), "correct offering leaves inventory")

	_Runner.clear()
	if _failures.is_empty():
		print("PUZZLE RIDDLE: PASS")
	else:
		print("PUZZLE RIDDLE: FAIL")
		for f in _failures:
			print("  - %s" % f)
	quit(1 if not _failures.is_empty() else 0)


func _projected(room: Dictionary, st: Dictionary, eid: String) -> Dictionary:
	var area: Dictionary = _Projection.area_for(room, st)
	for ent in area["entities"]:
		var parts := str(ent.get("puzzle_eid", "")).split("_")
		if parts[-1] == eid and str(ent.get("kind", "")) == "logs":
			return ent
	return {}
