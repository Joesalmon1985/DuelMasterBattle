extends Node

## Bootstrap/session state for disposable puzzle-test sessions.
## Holds ONLY data: the selected catalogue room id, the room dict, and the
## authoritative DmbPuzzleKit state. NOT a game engine — gameplay runs through
## the normal production scene (res://client/scenes/overworld.tscn).

static var selected_puzzle = ""
static var _room: Dictionary = {}
static var _kit_state: Dictionary = {}
static var _saved_adv_state: Dictionary = {}
static var _saved_adv_prog: Dictionary = {}
static var _has_saved_session := false


static func get_puzzle():
	return selected_puzzle


static func set_puzzle(puzzle) -> void:
	selected_puzzle = str(puzzle)
	_room = {}
	_kit_state = {}


static func clear() -> void:
	selected_puzzle = ""
	_room = {}
	_kit_state = {}


## Pending launch: a puzzle was chosen in the menu and overworld must boot it.
static func has_pending() -> bool:
	return selected_puzzle != "" and _kit_state.is_empty()


static func is_active() -> bool:
	return selected_puzzle != "" and not _kit_state.is_empty()


static func room_id() -> String:
	return selected_puzzle


## Begin the disposable session: snapshot campaign state, init kit state,
## seed Adventure prereqs. Returns the kit start pos as Vector2i.
static func begin(adv: Node) -> Vector2i:
	_room = _find_room(selected_puzzle)
	_kit_state = DmbPuzzleKit.fresh_state(_room)
	_saved_adv_state = (adv.state as Dictionary).duplicate(true)
	_saved_adv_prog = adv.progression.to_dict()
	_has_saved_session = true
	adv.test_mode = true
	_seed_prereqs(adv, _room)
	return Vector2i(int(_room["start"][0]), int(_room["start"][1]))


## End the session: restore the pre-test campaign snapshot, clear kit state.
static func end(adv: Node) -> void:
	if _has_saved_session:
		adv.state = _saved_adv_state.duplicate(true)
		adv.progression = DmbProgression.from_dict(_saved_adv_prog.duplicate(true))
		adv.state_changed.emit()
		_has_saved_session = false
	_saved_adv_state = {}
	_saved_adv_prog = {}
	adv.test_mode = false
	clear()


## Reset the current puzzle: fresh kit state, re-seed prereqs, start pos.
static func reset(adv: Node) -> Vector2i:
	_room = _find_room(selected_puzzle)
	_kit_state = DmbPuzzleKit.fresh_state(_room)
	_seed_prereqs(adv, _room)
	return Vector2i(int(_room["start"][0]), int(_room["start"][1]))


static func kit_room() -> Dictionary:
	if _room.is_empty():
		_room = _find_room(selected_puzzle)
	return _room


static func kit_state() -> Dictionary:
	if _kit_state.is_empty() and selected_puzzle != "":
		_room = _find_room(selected_puzzle)
		_kit_state = DmbPuzzleKit.fresh_state(_room)
	return _kit_state


static func _find_room(rid: String) -> Dictionary:
	for r in DmbPuzzleRooms.all():
		if str(r["id"]) == rid:
			return (r as Dictionary).duplicate(true)
	return {}


## Seed John's production Adventure with whatever the catalogue room needs:
## every spell any response in the room can require, plus any declared
## start_items. Generic — derived from room data, no per-room code.
static func _seed_prereqs(adv: Node, room: Dictionary) -> void:
	if room.is_empty():
		return
	for e in room.get("entities", []):
		if (e as Dictionary).has("responses"):
			for k in (e as Dictionary)["responses"].keys():
				adv.learn_spell(int(k))
	for item_id in room.get("start_items", []):
		adv.add_item(str(item_id))
