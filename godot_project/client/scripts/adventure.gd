extends Node

## Autoload `Adventure`: the single authoritative save state for the story, plus
## the bridge between overworld and battle.
##
## Everything the overworld needs to rebuild itself lives in `state` and is written
## to one save slot (user://adventure.save). Flags are free-form strings so new
## content can add its own without schema changes.

const SAVE_PATH := "user://adventure.save"
const SAVE_VERSION := 1

const _Progression = preload("res://sim/progression.gd")

signal state_changed
signal battle_requested(request: Dictionary)

var progression: DmbProgression = _Progression.new()
var state: Dictionary = {}

## Set by the overworld before a battle; read by the battle screen.
var pending_battle: Dictionary = {}
## Written by the battle screen when it ends; consumed by the overworld.
var last_battle_result: Dictionary = {}

var _active: bool = false


func _ready() -> void:
	pass


# --- Lifecycle ------------------------------------------------------------------

func is_active() -> bool:
	return _active


func new_game() -> void:
	progression = _Progression.new()
	state = {
		"version": SAVE_VERSION,
		"area": "village",
		"pos": [7, 10],
		"facing": "down",
		"flags": {},
		"defeated": [],
		"picked": [],
		"extinguished": [],
		"talked": {},
		"play_seconds": 0.0,
	}
	pending_battle = {}
	last_battle_result = {}
	_active = true
	save()
	state_changed.emit()


func has_save() -> bool:
	return FileAccess.file_exists(SAVE_PATH)


func save() -> void:
	if not _active:
		return
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if f == null:
		push_warning("Adventure: cannot write save")
		return
	var payload := {"state": state, "progression": progression.to_dict()}
	f.store_string(JSON.stringify(payload))


func load_game() -> bool:
	if not has_save():
		return false
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		return false
	var data = JSON.parse_string(f.get_as_text())
	if typeof(data) != TYPE_DICTIONARY or not data.has("state"):
		return false
	state = data["state"]
	# JSON gives floats; normalise the bits we index with.
	state["pos"] = [int(state["pos"][0]), int(state["pos"][1])]
	for k in ["defeated", "picked", "extinguished"]:
		if not state.has(k):
			state[k] = []
	for k in ["flags", "talked"]:
		if not state.has(k):
			state[k] = {}
	progression = _Progression.from_dict(data.get("progression", {}))
	pending_battle = {}
	last_battle_result = {}
	_active = true
	state_changed.emit()
	return true


func delete_save() -> void:
	if has_save():
		DirAccess.remove_absolute(ProjectSettings.globalize_path(SAVE_PATH))


func save_summary() -> String:
	if not has_save():
		return ""
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	if f == null:
		return ""
	var data = JSON.parse_string(f.get_as_text())
	if typeof(data) != TYPE_DICTIONARY:
		return ""
	var p = data.get("progression", {})
	var st = data.get("state", {})
	var spells: Array = p.get("spells_known", [])
	var names: Array = []
	for s in spells:
		names.append(DmbColourData.essence_name(int(s)))
	var area := str(st.get("area", "")).replace("_", " ").capitalize()
	if names.is_empty():
		return "%s · no magic yet" % area
	return "%s · %s · %d-slot weave" % [area, ", ".join(PackedStringArray(names)), int(p.get("weave_size", 0))]


# --- Flags & world state --------------------------------------------------------

func flag(name: String) -> bool:
	return bool(state.get("flags", {}).get(name, false))


func set_flag(name: String, value: bool = true) -> void:
	state["flags"][name] = value
	state_changed.emit()


func mark(list_name: String, id: String) -> void:
	if not (id in state[list_name]):
		state[list_name].append(id)
		state_changed.emit()


func marked(list_name: String, id: String) -> bool:
	return id in state.get(list_name, [])


func talk_count(npc_id: String) -> int:
	return int(state.get("talked", {}).get(npc_id, 0))


func bump_talk(npc_id: String) -> void:
	state["talked"][npc_id] = talk_count(npc_id) + 1


func set_location(area: String, x: int, y: int, facing: String) -> void:
	state["area"] = area
	state["pos"] = [x, y]
	state["facing"] = facing


# --- Progression ------------------------------------------------------------------

func learn_spell(spell_id: int) -> bool:
	var ok := progression.learn_spell(spell_id)
	if ok:
		state_changed.emit()
	return ok


func grow_weave(to: int) -> bool:
	var ok := progression.grow_weave(to)
	if ok:
		state_changed.emit()
	return ok


# --- Battle bridge ----------------------------------------------------------------

## request: {"enemy_id": String, "encounter_id": String, "intro": String, "on_win_flag": String, ...}
func request_battle(request: Dictionary) -> void:
	pending_battle = request.duplicate(true)
	last_battle_result = {}
	save()
	battle_requested.emit(pending_battle)


func clear_pending_battle() -> void:
	pending_battle = {}


func report_battle_result(outcome: String, details: Dictionary = {}) -> void:
	last_battle_result = {"outcome": outcome, "request": pending_battle.duplicate(true)}
	for k in details.keys():
		last_battle_result[k] = details[k]
	if outcome == "victory" and pending_battle.has("encounter_id"):
		mark("defeated", str(pending_battle["encounter_id"]))
	pending_battle = {}
	save()
