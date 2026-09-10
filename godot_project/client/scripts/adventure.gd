extends Node

## Autoload `Adventure`: the single authoritative save state for the story, plus
## the bridge between overworld and battle.
##
## Everything the overworld needs to rebuild itself lives in `state` and is written
## to one save slot (user://adventure.save). Flags are free-form strings so new
## content can add its own without schema changes.

const SAVE_PATH := "user://adventure.save"
const SAVE_VERSION := 4

## Story state machine (CORRECTIVE_PASS_PLAN Phase 0). One authoritative field;
## local event flags remain in state["flags"].
const PHASES := ["halvard_prologue", "john_intro", "ashby_training", "pre_trial", "trial", "post_trial_recovery"]
const PHASE_NEXT := {
	"halvard_prologue": ["john_intro"],
	"john_intro": ["ashby_training"],
	"ashby_training": ["pre_trial", "post_trial_recovery"],
	"pre_trial": ["trial", "post_trial_recovery"],
	"trial": ["post_trial_recovery"],
	"post_trial_recovery": [],
}
## Battle-result policy categories. The combat UI reports; the story layer decides.
const POLICY_PROLOGUE := "PROLOGUE_FORCED_DEFEAT"
const POLICY_TRAINING := "TRAINING_CONTINUE"
const POLICY_STORY := "STORY_DEFEAT_TRANSITION"
const POLICY_TRIAL := "TRIAL_STORY_RESULT"
const POLICY_QUICK := "QUICK_DUEL"
const OPTIMAL_EVERY := 3

## The single Trial attempt. John's magic and world flags are permanent; the
## attempt's gems/conditions/contestant states live in state["run"]. There is no
## reset: defeat is handled by the story-defeat policy, not by restarting the run.
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
		"pos": [11, 6],
		"facing": "down",
		"flags": {},
		"defeated": [],
		"watching": [],
		"picked": [],
		"extinguished": [],
		"talked": {},
		"play_seconds": 0.0,
		"run": null,
		"dungeon_knowledge": {},
		"world": "",
		"world_seed": 7,
		"world_node": -1,
		"items": [],
		"puzzles": {},
		"quests": {},
		"story": {
			"phase": "halvard_prologue",
			"protagonist": "halvard",
			"encounters": {},
			"encounter_index": 0,
			"story_defeats": 0,
			"left_for_dead_used": false,
			"recovery_pending": false,
		},
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
	f.close()
	if typeof(data) != TYPE_DICTIONARY or not data.has("state"):
		return false
	# Saves older than v3 predate the story state machine (protagonist, phase,
	# defeat policy). Migrating them would produce impossible states, so they are
	# invalidated explicitly rather than guessed at.
	if int(data["state"].get("version", 1)) < SAVE_VERSION or not data["state"].has("story"):
		push_warning("Adventure: save predates v%d — discarded" % SAVE_VERSION)
		delete_save()
		return false
	state = data["state"]
	# JSON gives floats; normalise the bits we index with.
	state["pos"] = [int(state["pos"][0]), int(state["pos"][1])]
	for k in ["defeated", "picked", "extinguished", "watching"]:
		if not state.has(k):
			state[k] = []
	for k in ["flags", "talked"]:
		if not state.has(k):
			state[k] = {}
	if not state.has("run"):
		state["run"] = null
	if not state.has("dungeon_knowledge"):
		state["dungeon_knowledge"] = {}
	state["story"]["encounter_index"] = int(state["story"].get("encounter_index", 0))
	state["story"]["story_defeats"] = int(state["story"].get("story_defeats", 0))
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


# --- inventory (Next Pass §2): at most DmbItems.MAX_SLOTS quest/puzzle items ---

func items() -> Array:
	if not state.has("items"):
		state["items"] = []
	return state["items"]


func has_item(id: String) -> bool:
	return id in items()


func add_item(id: String) -> bool:
	if not DmbItems.known(id) or has_item(id):
		return false
	if items().size() >= DmbItems.MAX_SLOTS:
		return false
	items().append(id)
	save()
	state_changed.emit()
	return true


func remove_item(id: String) -> bool:
	if not has_item(id):
		return false
	items().erase(id)
	save()
	state_changed.emit()
	return true


func inventory_full() -> bool:
	return items().size() >= DmbItems.MAX_SLOTS


## Persistent puzzle state, keyed "<dungeon>/<puzzle>".
func puzzle_state(key: String) -> Dictionary:
	if not state.has("puzzles"):
		state["puzzles"] = {}
	return state["puzzles"].get(key, {})


func set_puzzle_state(key: String, st: Dictionary) -> void:
	if not state.has("puzzles"):
		state["puzzles"] = {}
	state["puzzles"][key] = st
	state_changed.emit()


func dungeon_solved_count(dungeon_id: String) -> int:
	var n := 0
	for k in state.get("puzzles", {}):
		if str(k).begins_with(dungeon_id + "/") and bool(state["puzzles"][k].get("solved", false)):
			n += 1
	return n


## Quest outcome per settlement node: "" = not done; else outcome id.
func quest_outcome(node_id: int) -> String:
	if not state.has("quests"):
		state["quests"] = {}
	return str(state["quests"].get(str(node_id), ""))


func set_quest_outcome(node_id: int, outcome: String) -> void:
	if not state.has("quests"):
		state["quests"] = {}
	state["quests"][str(node_id)] = outcome
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


# --- Story state machine ------------------------------------------------------------

func _story() -> Dictionary:
	return state.get("story", {})


func story_phase() -> String:
	return str(_story().get("phase", "halvard_prologue"))


func protagonist() -> String:
	return str(_story().get("protagonist", "john"))


func advance_phase(to: String) -> bool:
	if not (to in PHASES):
		return false
	var allowed: Array = PHASE_NEXT.get(story_phase(), [])
	if not (to in allowed):
		return false
	state["story"]["phase"] = to
	if to != "halvard_prologue":
		state["story"]["protagonist"] = "john"
	state_changed.emit()
	return true


## Authoritative Trial-entry check (brief §14). Normal progression satisfies it;
## the gate refuses abnormal routes/saves diegetically.
func trial_ready() -> bool:
	return flag("has_staff") and progression.weave_size >= 3 and progression.spells_known.size() >= 4


## Battle-result policy: explicit `policy` on the request wins; `training`
## requests continue; anything else in an active adventure is a story battle.
func battle_policy_for(request: Dictionary) -> String:
	if request.has("policy"):
		return str(request["policy"])
	if not _active:
		return POLICY_QUICK
	if bool(request.get("training", false)):
		return POLICY_TRAINING
	if story_phase() == "halvard_prologue":
		return POLICY_PROLOGUE
	return POLICY_STORY


## Story defeat bookkeeping (brief §24). Returns "left_for_dead" the first time,
## "recovery" afterwards. Training and prologue defeats never call this.
## Brief (Next Pass §1): story defeats before the third colour do not count
## towards Jane — the forest is a school until the pendant. After the third
## colour, the first defeat is "left for dead", the second moves John to Jane's
## house whether or not he ever reached the Trial.
func record_story_defeat() -> String:
	if progression.spells_known.size() < 3 and story_phase() in ["pre_trial", "ashby_training"]:
		state["story"]["soft_defeats"] = int(_story().get("soft_defeats", 0)) + 1
		save()
		state_changed.emit()
		return "wait"
	state["story"]["story_defeats"] = int(_story().get("story_defeats", 0)) + 1
	var outcome := "recovery"
	if not bool(_story().get("left_for_dead_used", false)):
		state["story"]["left_for_dead_used"] = true
		outcome = "left_for_dead"
	else:
		state["story"]["recovery_pending"] = true
		if story_phase() != "post_trial_recovery":
			advance_phase("post_trial_recovery")
	save()
	state_changed.emit()
	return outcome


func left_for_dead_used() -> bool:
	return bool(_story().get("left_for_dead_used", false))


func post_trial_recovery_pending() -> bool:
	return bool(_story().get("recovery_pending", false))


## Every-third-battle rule (brief §9). Numbers John's encounters once each; the
## prologue does not count. Re-challenging an encounter keeps its number.
func begin_encounter(encounter_id: String) -> int:
	if story_phase() == "halvard_prologue":
		return 0
	var seq: Dictionary = state["story"].get("encounters", {})
	if seq.has(encounter_id):
		return int(seq[encounter_id])
	var n := int(_story().get("encounter_index", 0)) + 1
	seq[encounter_id] = n
	state["story"]["encounters"] = seq
	state["story"]["encounter_index"] = n
	state_changed.emit()
	return n


func is_optimal_encounter(encounter_id: String) -> bool:
	var n := int(state["story"].get("encounters", {}).get(encounter_id, 0))
	return n > 0 and n % OPTIMAL_EVERY == 0


# --- Trial attempt state ---------------------------------------------------------------

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
		"notes": [],
		"contestants": RUN_CONTESTANTS.duplicate(),
		"flags": {},
	}
	set_location(RUN_START_AREA, int(RUN_START_POS[0]), int(RUN_START_POS[1]), "up")
	mark_visited(RUN_START_AREA)
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
		var notes: Array = run_state().get("notes", [])
		if not notes.is_empty():
			lines.append("Learned:")
			for n in notes:
				lines.append("- " + str(n))
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


func has_condition(cond: String) -> bool:
	return run_active() and cond in run_state().get("conditions", [])


## A discovery made during the attempt (brief §28): appears in the journal.
func add_knowledge(note: String) -> void:
	if run_active():
		if not state["run"].has("notes"):
			state["run"]["notes"] = []
		if not note in state["run"]["notes"]:
			state["run"]["notes"].append(note)
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
	pending_battle = {}
	save()
