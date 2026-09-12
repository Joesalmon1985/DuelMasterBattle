extends Node
class_name VillageTestRunner

## Bootstrap/session state for disposable village test sessions.
## Holds ONLY data: selected fixture, projected area and campaign snapshot.
## Gameplay remains in the production Overworld.
##
## Two selection modes share one session lifecycle:
##   * authored fixture  — profile id like "E36B", projected by VillageCompositeProjection;
##   * generated         — "gen:<seed>:<node>:<turns>", the production path
##                          DmbWorldSim -> DmbSettlementProfile -> DmbNodeProjection.

const _Projection = preload("res://sim/world/village_composite_projection.gd")
const _Catalog = preload("res://sim/world/village_test_catalog.gd")
const _QuestRunner = preload("res://sim/world/village_quest_runner.gd")

static var selected_profile := ""
static var _area: Dictionary = {}
static var _initial_area: Dictionary = {}
static var _saved_adv_state: Dictionary = {}
static var _saved_adv_prog: Dictionary = {}
static var _has_saved_session := false
static var _debug_overlay_active := false
static var _show_anchors := false
static var _show_quest_story := false
static var _show_entity_ids := false
## Generated mode: the deterministic world behind the selected node.
static var _gen: Dictionary = {}          # {"seed", "node", "turns"} or empty
static var _gen_sim: DmbWorldSim = null

const GEN_PREFIX := "gen:"
const DEFAULT_TURNS := 30


static func get_profile() -> String:
    return selected_profile


static func set_profile(profile_id: String) -> void:
    selected_profile = str(profile_id)
    _area = {}
    _initial_area = {}
    _gen = {}
    _gen_sim = null
    _QuestRunner.clear()
    if selected_profile.begins_with(GEN_PREFIX):
        var parts := selected_profile.substr(GEN_PREFIX.length()).split(":")
        if parts.size() >= 2:
            _gen = {"seed": int(parts[0]), "node": int(parts[1]), "turns": int(parts[2]) if parts.size() > 2 else DEFAULT_TURNS}


## Select a production settlement by world seed + node (+ turns advanced).
static func set_generated(world_seed: int, node: int, turns: int = DEFAULT_TURNS) -> void:
    set_profile(generated_id(world_seed, node, turns))


static func generated_id(world_seed: int, node: int, turns: int = DEFAULT_TURNS) -> String:
    return "%s%d:%d:%d" % [GEN_PREFIX, world_seed, node, turns]


static func is_generated() -> bool:
    return not _gen.is_empty()


static func generated_params() -> Dictionary:
    return _gen.duplicate()


## The deterministic world for the selection: built once per session, rebuilt
## byte-identically on reset. Pure function of (seed, turns).
static func build_generated_sim(world_seed: int, turns: int) -> DmbWorldSim:
    var sim := DmbWorldSim.new(world_seed)
    sim.setup()
    for i in range(turns):
        sim.advance_turn()
    return sim


## Settlement/town nodes a world offers after `turns` turns: [{node, kind, owner, summary}].
static func generated_choices(world_seed: int, turns: int = DEFAULT_TURNS) -> Array:
    var sim := build_generated_sim(world_seed, turns)
    var out: Array = []
    var ids: Array = sim.catan.settlements.keys()
    ids.sort()
    for nid in ids:
        var p := DmbSettlementProfile.describe(sim, int(nid))
        out.append({"node": int(nid), "kind": str(p["kind"]), "owner": str(p["owner"]), "summary": DmbSettlementProfile.summary(p),
            "home": int(nid) == sim.player_home_node(), "name": DmbNodeProjection.node_name(sim, int(nid))})
    return out


static func generated_sim() -> DmbWorldSim:
    return _gen_sim


static func _project() -> Dictionary:
    if is_generated():
        _gen_sim = build_generated_sim(int(_gen["seed"]), int(_gen["turns"]))
        if not _gen_sim.catan.settlements.has(int(_gen["node"])):
            push_error("VillageTestRunner: node %d is not a settlement in world %d after %d turns" % [int(_gen["node"]), int(_gen["seed"]), int(_gen["turns"])])
        return DmbNodeProjection.area_for(_gen_sim, int(_gen["node"]))
    return _Projection.project(selected_profile)


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
    _gen = {}
    _gen_sim = null
    _QuestRunner.clear()


static func has_pending() -> bool:
    return selected_profile != "" and _area.is_empty()


static func is_active() -> bool:
    return selected_profile != "" and not _area.is_empty()


static func profile_id() -> String:
    return selected_profile


static func get_area() -> Dictionary:
    if _area.is_empty():
        _area = _project()
        _initial_area = _area.duplicate(true)
    return _area


static func get_initial_area() -> Dictionary:
    if _initial_area.is_empty():
        _initial_area = _project()
    return _initial_area.duplicate(true)


static func begin(adv: Node) -> Vector2i:
    var area := get_area()
    if area.is_empty():
        push_error("VillageTestRunner: projected area is empty for " + selected_profile)
        return Vector2i.ZERO
    _saved_adv_state = (adv.state as Dictionary).duplicate(true)
    _saved_adv_prog = adv.progression.to_dict()
    _has_saved_session = true
    adv.test_mode = true
    _seed_prereqs(adv, area)
    return Vector2i(int(area["player_start"][0]), int(area["player_start"][1]))


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


static func reset(adv: Node) -> Vector2i:
    _restore_baseline(adv)
    _QuestRunner.clear()
    _area = _project()
    _initial_area = _area.duplicate(true)
    _seed_prereqs(adv, _area)
    return Vector2i(int(_area["player_start"][0]), int(_area["player_start"][1]))


static func _restore_baseline(adv: Node) -> void:
    if not _has_saved_session:
        return
    adv.state = _saved_adv_state.duplicate(true)
    adv.progression = DmbProgression.from_dict(_saved_adv_prog.duplicate(true))
    adv.state_changed.emit()


static func _seed_prereqs(adv: Node, area: Dictionary) -> void:
    adv.state["village_test_profile"] = selected_profile
    adv.state["village_test_area_id"] = area.get("id", "")
    adv.state["village_test_quest"] = area.get("quest_id", "")
    if is_generated():
        # The production Overworld reads the world through WorldFlow, which
        # restores DmbWorldSim from adv.state["world"]: hand it the very sim the
        # area was projected from, so exits, quests and dungeons resolve against
        # the same canonical state. Prologue/intro flags are set so the test
        # opens straight onto the settlement; the snapshot restores them on exit.
        adv.state["world"] = var_to_str(_gen_sim.to_dict())
        adv.state["world_seed"] = int(_gen["seed"])
        adv.state["world_node"] = int(_gen["node"])
        adv.state["area"] = str(area.get("id", ""))
        adv.state["pos"] = area.get("player_start", [0, 0]).duplicate()
        adv.state["facing"] = "down"
        for f in ["opening_seen", "jane_placeholder_seen"]:
            adv.set_flag(f)
        adv.state["village_test_seed"] = int(_gen["seed"])
        adv.state["village_test_node"] = int(_gen["node"])
        adv.state["village_test_turns"] = int(_gen["turns"])
        return
    var fixture: Dictionary = _Catalog.load_fixture(selected_profile)
    var quest_data: Dictionary = fixture.get("quest", {})
    if quest_data.has("id"):
        var qid := str(quest_data["id"])
        adv.state["quest_" + qid + "_active"] = true
        adv.state["quest_" + qid + "_node"] = str(quest_data.get("start_node", ""))


static func quest_state() -> Dictionary:
    return _QuestRunner.get_state()


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
    return {
        "overlay": _debug_overlay_active,
        "anchors": _show_anchors,
        "quest_story": _show_quest_story,
        "entity_ids": _show_entity_ids,
        "quest": _QuestRunner.get_state(),
        "generated": _gen.duplicate(),
    }


## One-screen diagnostic for the pause menu: seed/node/turn and the canonical
## profile behind what is on screen.
static func context_text() -> String:
    if not is_generated() or _gen_sim == null:
        return "Fixture %s" % selected_profile
    var nid := int(_gen["node"])
    var p := DmbSettlementProfile.describe(_gen_sim, nid)
    var a := get_area()
    var lay: Dictionary = a.get("layout", {})
    return "seed %d  node %d  turn %d  (%s)\n%s\nmap %dx%d, %d entities, %d houses" % [int(_gen["seed"]), nid, _gen_sim.turn, selected_profile,
        DmbSettlementProfile.summary(p), int(lay.get("w", 0)), int(lay.get("h", 0)), a["entities"].size(), int(p["housing"])]
