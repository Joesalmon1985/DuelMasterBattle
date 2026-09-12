extends Node
class_name VillageTestRunner

## Bootstrap/session state for disposable village test sessions.
## Holds ONLY data: the selected profile, the projected area, and session state.
## NOT a game engine — gameplay runs through the normal production scene (res://client/scenes/overworld.tscn).

const _Projection = preload("res://sim/world/village_composite_projection.gd")
const _Catalog = preload("res://sim/world/village_test_catalog.gd")
const _QuestRunner = preload("res://sim/world/village_quest_runner.gd")

static var selected_profile = ""
static var _area: Dictionary = {}
static var _initial_area: Dictionary = {}
static var _saved_adv_state: Dictionary = {}
static var _saved_adv_prog: Dictionary = {}
static var _has_saved_session := false
static var _debug_overlay_active := false
static var _show_anchors := false
static var _show_quest_story := false
static var _show_entity_ids := false

static func get_profile() -> String:
    return selected_profile

static func set_profile(profile_id: String) -> void:
    selected_profile = str(profile_id)
    _area = {}
    _initial_area = {}

static func clear() -> void:
    selected_profile = ""
    _area = {}
    _initial_area = {}
    _saved_adv_state = {}
    _saved_adv_prog = {}
    _has_saved_session = false
    _debug_overlay_active = false
    _show_anchors = false
    _show_quest_story = false
    _show_entity_ids = false
    _QuestRunner.reset()

static func has_pending() -> bool:
    return selected_profile != "" and _area.is_empty()

static func is_active() -> bool:
    return selected_profile != "" and not _area.is_empty()

static func profile_id() -> String:
    return selected_profile

static func get_area() -> Dictionary:
    if _area.is_empty():
        _area = _Projection.project(selected_profile)
        _initial_area = _area.duplicate(true)
    return _area

static func get_initial_area() -> Dictionary:
    if _initial_area.is_empty():
        _initial_area = _Projection.project(selected_profile)
    return _initial_area.duplicate(true)

## Begin the disposable session: snapshot campaign state, init area, seed Adventure prereqs.
## Returns the player start position as Vector2i.
static func begin(adv: Node) -> Vector2i:
    var area = get_area()
    _saved_adv_state = (adv.state as Dictionary).duplicate(true)
    _saved_adv_prog = adv.progression.to_dict()
    _has_saved_session = true
    adv.test_mode = true
    _seed_prereqs(adv, area)
    return Vector2i(int(area["player_start"][0]), int(area["player_start"][1]))

## End the session: restore the pre-test campaign snapshot, clear session state.
static func end(adv: Node) -> void:
    if _has_saved_session:
        adv.state = _saved_adv_state.duplicate(true)
        adv.progression = DmbProgression.from_dict(_saved_adv_prog.duplicate(true))
        adv.state_changed.emit()
        _has_saved_session = false
    _saved_adv_state = {}
    _saved_adv_prog = {}
    adv.test_mode = false
    _QuestRunner.reset()
    clear()

## Reset the current village test: restore the Adventure baseline captured at begin,
## fresh projected area, re-seed prereqs.
static func reset(adv: Node) -> Vector2i:
    _restore_baseline(adv)
    _area = _Projection.project(selected_profile)
    _initial_area = _area.duplicate(true)
    _seed_prereqs(adv, _area)
    _QuestRunner.reset()
    return Vector2i(int(_area["player_start"][0]), int(_area["player_start"][1]))

static func _restore_baseline(adv: Node) -> void:
    if not _has_saved_session:
        return
    adv.state = _saved_adv_state.duplicate(true)
    adv.progression = DmbProgression.from_dict(_saved_adv_prog.duplicate(true))
    adv.state_changed.emit()

static func _seed_prereqs(adv: Node, area: Dictionary) -> void:
    # Seed any Adventure state needed for quests/stories to work
    adv.state["village_test_profile"] = selected_profile
    adv.state["village_test_area_id"] = area["id"]
    adv.state["village_test_quest"] = area.get("quest_id", "")
    
    # Seed pilot story flags
    var fixture = _Catalog.load_fixture(selected_profile)
    var quest_data = fixture.get("quest", {})
    if quest_data.has("id"):
        adv.state["quest_" + quest_data["id"] + "_active"] = true
        adv.state["quest_" + quest_data["id"] + "_node"] = "talk_reve"

# Debug overlay toggles
static func toggle_debug_overlay() -> bool:
    _debug_overlay_active = not _debug_overlay_active
    return _debug_overlay_active

static func is_debug_overlay_active() -> bool:
    return _debug_overlay_active

static func toggle_anchors() -> bool:
    _show_anchors = not _show_anchors
    return _show_anchors

static func show_anchors() -> bool:
    return _show_anchors

static func toggle_quest_story() -> bool:
    _show_quest_story = not _show_quest_story
    return _show_quest_story

static func show_quest_story() -> bool:
    return _show_quest_story

static func toggle_entity_ids() -> bool:
    _show_entity_ids = not _show_entity_ids
    return _show_entity_ids

static func show_entity_ids() -> bool:
    return _show_entity_ids

static func get_debug_state() -> Dictionary:
    var quest_state = _QuestRunner.get_state()
    return {
        "overlay": _debug_overlay_active,
        "anchors": _show_anchors,
        "quest_story": _show_quest_story,
        "entity_ids": _show_entity_ids,
        "quest": quest_state
    }