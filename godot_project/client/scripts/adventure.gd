extends Node

## Autoload `Adventure`: the single authoritative save state for the story, plus
## the bridge between overworld and battle.
##
## Everything the overworld needs to rebuild itself lives in `state` and is written
## to one save slot (user://adventure.save). Flags are free-form strings so new
## content can add its own without schema changes.

const SAVE_PATH := "user://adventure.save"
const SAVE_VERSION := 2

## P2 dungeon-run state. John's magic (progression) and world flags are permanent;
## everything inside one Trial attempt lives in state["run"] and resets on fail.
## Persistent map knowledge lives in state["dungeon_knowledge"].
const RUN_GATE_AREA := "trial_gate"
const RUN_GATE_POS := [9, 6]
const RUN_START_AREA := "dd_entrance"
const RUN_START_POS := [10, 11]
const RUN_CONTESTANTS := {
	"knight": "ahead", "elf": "ahead", "throm": "ahead",
	"assassin": "ahead", "barbarian2": "ahead", "red_wizard": "ahead",
}

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
		"run": null,
		"dungeon_knowledge": {},
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
	# v1 → v2 migration: dungeon-run state did not exist yet.
	if int(state.get("version", 1)) < 2:
		state["version"] = 2
	if not state.has("run"):
		state["run"] = null
	if not state.has("dungeon_knowledge"):
		state["dungeon_knowledge"] = {}
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


# --- Dungeon-run state (P2) ---------------------------------------------------------

func run_active() -> bool:
	return state.get("run") != null and bool(state["run"].get("active", false))


func run_state() -> Dictionary:
	if state.get("run") == null:
		return {}
	return state["run"]


func start_run() -> void:
	state["run"] = {
		"active": true,
		"area": RUN_START_AREA,
		"pos": RUN_START_POS.duplicate(),
		"visited": [RUN_START_AREA],
		"inventory": [],
		"gems": [],
		"conditions": [],
		"contestants": RUN_CONTESTANTS.duplicate(),
		"flags": {},
		"fights": [],
	}
	set_location(RUN_START_AREA, int(RUN_START_POS[0]), int(RUN_START_POS[1]), "up")
	mark_visited(RUN_START_AREA)
	save()
	state_changed.emit()


func fail_run(_reason: String) -> void:
	# Knowledge persists; everything else about the attempt is wiped.
	for area_id in run_state().get("visited", []):
		if knowledge_status(str(area_id)) in ["unknown", "seen"]:
			state["dungeon_knowledge"][str(area_id)] = "entered"
	# Dungeon fights are re-fought next run; outside victories stand.
	for eid in run_state().get("fights", []):
		if eid in state.get("defeated", []):
			state["defeated"].erase(eid)
	state["run"] = {
		"active": false,
		"area": "",
		"pos": [],
		"visited": [],
		"inventory": [],
		"gems": [],
		"conditions": [],
		"contestants": RUN_CONTESTANTS.duplicate(),
		"flags": {},
		"fights": [],
	}
	set_location(RUN_GATE_AREA, int(RUN_GATE_POS[0]), int(RUN_GATE_POS[1]), "down")
	save()
	state_changed.emit()


func mark_visited(area_id: String) -> void:
	if run_active() and not area_id in run_state()["visited"]:
		state["run"]["visited"].append(area_id)
	if knowledge_status(area_id) == "unknown":
		state["dungeon_knowledge"][area_id] = "seen"


func knowledge_status(area_id: String) -> String:
	return str(state.get("dungeon_knowledge", {}).get(area_id, "unknown"))


## John's journal: persistent knowledge (never what he hasn't learned) + run state.
func notebook_text() -> String:
	var _World = load("res://client/world/world_data.gd")
	var lines := ["JOHN'S JOURNAL"]
	if run_active():
		var gems: Array = run_state().get("gems", [])
		var names := []
		for gm in gems:
			names.append(str(gm).capitalize())
		lines.append("Gems carried: " + (", ".join(PackedStringArray(names)) if not names.is_empty() else "none yet"))
		var conds: Array = run_state().get("conditions", [])
		if not conds.is_empty():
			lines.append("Ailing: " + ", ".join(PackedStringArray(conds)))
	var known: Array = state.get("dungeon_knowledge", {}).keys()
	if known.is_empty():
		lines.append("The dark below is still unknown.")
	else:
		lines.append("Known ground:")
		for id in known:
			var nm := str(id)
			if _World.area_ids().has(id):
				nm = str(_World.get_area(str(id)).get("name", id))
			lines.append("- %s (%s)" % [nm, knowledge_status(str(id))])
	if flag("diamond_clue"):
		lines.append("The Elf's clue: the final door wants gems. One is a diamond.")
	if run_active():
		var fell := []
		for cid in run_state().get("contestants", {}).keys():
			var st := str(run_state()["contestants"][cid])
			if st != "ahead":
				fell.append("%s: %s" % [cid, st])
		if not fell.is_empty():
			lines.append("Others: " + ", ".join(PackedStringArray(fell)))
	return "\n".join(PackedStringArray(lines))


func add_gem(gem: String) -> void:
	if run_active() and not gem in run_state()["gems"]:
		state["run"]["gems"].append(gem)
		state_changed.emit()


func has_gem(gem: String) -> bool:
	return run_active() and gem in run_state()["gems"]


func add_condition(cond: String) -> void:
	if run_active():
		state["run"]["conditions"].append(cond)
		state_changed.emit()


func clear_conditions() -> void:
	if run_active():
		state["run"]["conditions"] = []
		state_changed.emit()


func set_contestant(id: String, st: String) -> void:
	if run_active():
		state["run"]["contestants"][id] = st
		state_changed.emit()


func set_run_flag(name: String, value: bool = true) -> void:
	if run_active():
		state["run"]["flags"][name] = value
		state_changed.emit()


func run_flag(name: String) -> bool:
	return run_active() and bool(run_state().get("flags", {}).get(name, false))


## Duel modifiers from run conditions (John's combatant only).
func player_mods() -> Dictionary:
	var mods := {}
	if not run_active():
		return mods
	var wounds := 0
	for c in run_state().get("conditions", []):
		if str(c) == "wounded":
			wounds += 1
		elif str(c) == "poisoned":
			mods["min_cast_bonus"] = 2.0
		elif str(c) == "slowed":
			mods["max_cast_bonus"] = -10.0
	if wounds > 0:
		mods["max_casts"] = maxi(6, 10 - wounds)
	return mods


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
		if run_active():
			state["run"]["fights"].append(str(pending_battle["encounter_id"]))
	pending_battle = {}
	save()
