extends RefCounted
class_name VillageQuestRunner

## Portable quest graph executor for Test Village Mode.
## Quest/content data owns NPC ids, node ids, flags, variants and branches.
## This class deliberately contains no E36B/E17A-specific names.

const Catalog = preload("res://sim/world/village_test_catalog.gd")

static var _current_quest: Dictionary = {}
static var _current_profile := ""
static var _flags: Dictionary = {}
static var _current_node := ""
static var _dialogue_index: Dictionary = {}
static var _completed_endings: Array = []
static var _epilogue_variant := "normal"


static func begin(profile_id: String) -> void:
    _current_profile = profile_id
    var fixture: Dictionary = Catalog.load_fixture(profile_id)
    if fixture.is_empty():
        push_error("VillageQuestRunner: Failed to load fixture " + profile_id)
        _current_quest = {}
        _current_node = ""
        _dialogue_index = {}
        return
    _current_quest = fixture.get("quest", {})
    _flags = {}
    _current_node = str(_current_quest.get("start_node", ""))
    _dialogue_index = _build_dialogue_index(fixture.get("dialogue", {}))
    _completed_endings = []
    _epilogue_variant = "normal"


static func reset() -> void:
    _flags.clear()
    _completed_endings.clear()
    _epilogue_variant = "normal"
    _current_node = str(_current_quest.get("start_node", "")) if not _current_quest.is_empty() else ""


static func clear() -> void:
    _current_quest = {}
    _current_profile = ""
    _flags = {}
    _current_node = ""
    _dialogue_index = {}
    _completed_endings = []
    _epilogue_variant = "normal"


static func get_state() -> Dictionary:
    return {
        "profile": _current_profile,
        "quest_id": str(_current_quest.get("id", "")),
        "quest_title": str(_current_quest.get("title", "")),
        "current_node": _current_node,
        "current_type": str(current_node().get("type", "")),
        "flags": _flags.duplicate(true),
        "completed_endings": _completed_endings.duplicate(),
        "epilogue_variant": _epilogue_variant,
        "complete": is_complete(),
    }


static func current_node_id() -> String:
    return _current_node


static func current_node() -> Dictionary:
    return _current_quest.get("nodes", {}).get(_current_node, {})


static func quest_id() -> String:
    return str(_current_quest.get("id", ""))


static func quest_title() -> String:
    return str(_current_quest.get("title", ""))


static func is_complete() -> bool:
    return not _completed_endings.is_empty()


static func get_flags() -> Dictionary:
    return _flags.duplicate(true)


static func expected_npc() -> String:
    return str(current_node().get("npc", ""))


static func expected_anchor() -> String:
    return str(current_node().get("anchor", ""))


static func objective_text() -> String:
    if is_complete():
        return "Story complete — talk to villagers for aftermath dialogue."
    var node := current_node()
    if node.is_empty():
        return ""
    var t := str(node.get("type", ""))
    if t == "talk" or t == "choice":
        var npc := str(node.get("npc", ""))
        var anchor := str(node.get("anchor", ""))
        return "Talk to %s%s" % [npc, " at " + anchor if anchor != "" else ""]
    if t == "investigate" or t == "travel":
        return "Go to " + str(node.get("anchor", "the marked location"))
    if t == "branch":
        return "Choose how to proceed"
    if t == "conclude":
        return "Resolve the story"
    return t


static func is_node_accessible(node_id: String) -> bool:
    var node: Dictionary = _current_quest.get("nodes", {}).get(node_id, {})
    if node.is_empty():
        return false
    for req in node.get("requires", []):
        if not _flags.has(str(req)):
            return false
    return true


static func _apply_sets(values: Array) -> void:
    for flag in values:
        _flags[str(flag)] = true


static func _entry_key(npc_id: String, node_id: String, variant: String) -> String:
    return npc_id + "|" + quest_id() + "|" + node_id + "|" + variant


static func _entry(npc_id: String, node_id: String, variant: String = "default") -> Dictionary:
    var key := _entry_key(npc_id, node_id, variant)
    if _dialogue_index.has(key):
        return (_dialogue_index[key] as Dictionary).duplicate(true)
    if variant != "default":
        var fallback := _entry_key(npc_id, node_id, "default")
        if _dialogue_index.has(fallback):
            return (_dialogue_index[fallback] as Dictionary).duplicate(true)
    return {}


static func _entry_turns(entry: Dictionary) -> Array:
    if entry.has("turns") and entry["turns"] is Array:
        return (entry["turns"] as Array).duplicate(true)
    var turns: Array = []
    for line in entry.get("lines", []):
        turns.append({"speaker": "npc", "text": str(line)})
    return turns


static func _ambient_result(npc_id: String) -> Dictionary:
    var entry := _entry(npc_id, "__ambient__", "default")
    if entry.is_empty() and is_complete():
        entry = _entry(npc_id, "__epilogue__", _epilogue_variant)
    return {
        "success": true,
        "type": "ambient",
        "turns": _entry_turns(entry),
        "current_node": _current_node,
        "objective": objective_text(),
    }


## Interact with an NPC using the current quest node. Wrong NPCs remain ambient;
## they never advance the story merely because the player spoke to them.
static func interact_npc(npc_id: String) -> Dictionary:
    if _current_quest.is_empty():
        return {"success": false, "error": "No active village quest"}
    if is_complete():
        return _ambient_result(npc_id)
    var node := current_node()
    if node.is_empty():
        return {"success": false, "error": "Current node not found: " + _current_node}
    var node_type := str(node.get("type", "talk"))
    if node_type not in ["talk", "choice"]:
        return _ambient_result(npc_id)
    if str(node.get("npc", "")) != npc_id:
        return _ambient_result(npc_id)
    if not is_node_accessible(_current_node):
        return {"success": false, "type": "locked", "turns": [], "error": "Requirements not met"}

    if node_type == "choice":
        return current_choice_payload()

    var node_id := _current_node
    var entry := _entry(npc_id, node_id, "default")
    var turns := _entry_turns(entry)
    if turns.is_empty() and str(node.get("text", "")) != "":
        turns.append({"speaker": "npc", "text": str(node["text"])})
    _apply_sets(node.get("sets", []))
    _current_node = str(node.get("next", ""))
    return {
        "success": true,
        "type": "talk",
        "npc": npc_id,
        "node_id": node_id,
        "turns": turns,
        "next_node": _current_node,
        "objective": objective_text(),
    }


## Interact with a semantic anchor for investigate/travel nodes.
static func interact_anchor(anchor: String) -> Dictionary:
    if is_complete():
        return {"success": true, "type": "ambient", "turns": []}
    var node := current_node()
    if node.is_empty():
        return {"success": false, "error": "No current quest node"}
    var node_type := str(node.get("type", ""))
    if node_type not in ["investigate", "travel"] or str(node.get("anchor", "")) != anchor:
        return {"success": false, "type": "wrong_anchor", "turns": []}
    if not is_node_accessible(_current_node):
        return {"success": false, "type": "locked", "turns": []}
    var node_id := _current_node
    _apply_sets(node.get("sets", []))
    _current_node = str(node.get("next", ""))
    var turns: Array = []
    if str(node.get("text", "")) != "":
        turns.append({"speaker": "", "text": str(node["text"])})
    return {
        "success": true,
        "type": node_type,
        "node_id": node_id,
        "turns": turns,
        "next_node": _current_node,
        "objective": objective_text(),
    }


static func current_choice_payload() -> Dictionary:
    var node := current_node()
    var node_type := str(node.get("type", ""))
    if node_type not in ["choice", "branch"]:
        return {"success": false, "error": "Current node is not a choice/branch"}
    var npc_id := str(node.get("npc", ""))
    var options_out: Array = []
    var options: Array = node.get("options", [])
    for i in range(options.size()):
        var option: Dictionary = options[i]
        var variant := str(option.get("variant", "default"))
        var entry := _entry(npc_id, _current_node, variant) if npc_id != "" else {}
        var label := str(entry.get("choice_label", option.get("label", option.get("fallback_label", "Option %d" % [i + 1]))))
        options_out.append({
            "index": i,
            "label": label,
            "variant": variant,
            "branch": str(option.get("branch", "")),
        })
    return {
        "success": true,
        "type": node_type,
        "node_id": _current_node,
        "npc": npc_id,
        "prompt": str(node.get("prompt", "What do you do?")),
        "options": options_out,
        "objective": objective_text(),
    }


## Resolve a choice or branch by index and return the selected branch's authored
## dialogue turns. The actual story transition remains wholly data-driven.
static func make_choice(choice_index: int) -> Dictionary:
    var node := current_node()
    var node_type := str(node.get("type", ""))
    if node_type not in ["choice", "branch"]:
        return {"success": false, "error": "Not at a choice/branch node"}
    var options: Array = node.get("options", [])
    if choice_index < 0 or choice_index >= options.size():
        return {"success": false, "error": "Invalid choice index"}
    var option: Dictionary = options[choice_index]
    _apply_sets(option.get("sets", []))
    var ending_hint := str(option.get("ending_hint", ""))
    if ending_hint in ["normal", "tragic"]:
        _epilogue_variant = ending_hint
    var old_node := _current_node
    var npc_id := str(node.get("npc", ""))
    var variant := str(option.get("variant", "default"))
    var entry := _entry(npc_id, old_node, variant) if npc_id != "" else {}
    var turns := _entry_turns(entry)
    _current_node = str(option.get("next", ""))
    return {
        "success": true,
        "type": node_type,
        "node_id": old_node,
        "variant": variant,
        "turns": turns,
        "next_node": _current_node,
        "objective": objective_text(),
    }


## Execute a non-interactive current node. Overworld uses this to collapse branch
## and conclude plumbing after a player interaction without creating fake map UI.
static func execute_current() -> Dictionary:
    var node := current_node()
    if node.is_empty():
        return {"success": false, "error": "No current node"}
    var node_type := str(node.get("type", ""))
    if node_type == "conclude":
        _apply_sets(node.get("sets", []))
        var ending := str(node.get("final_state", _epilogue_variant))
        if ending == "":
            ending = _epilogue_variant
        _completed_endings.append(ending)
        var turns: Array = []
        if str(node.get("text", "")) != "":
            turns.append({"speaker": "", "text": str(node["text"])})
        return {
            "success": true,
            "type": "conclude",
            "turns": turns,
            "ending_state": ending,
            "objective": objective_text(),
        }
    if node_type == "set_flag":
        _apply_sets(node.get("sets", []))
        _current_node = str(node.get("next", ""))
        return {"success": true, "type": "set_flag", "turns": [], "next_node": _current_node}
    return {"success": false, "error": "Current node requires player interaction", "type": node_type}


## Compatibility API used by projection and older fixture code.
static func get_dialogue(npc_id: String, quest_id_value: String, node_id: String = "") -> Array:
    if quest_id_value != quest_id():
        return []
    var entry := _entry(npc_id, node_id, "default")
    var out: Array = []
    for turn in _entry_turns(entry):
        if str(turn.get("speaker", "npc")) in ["npc", ""]:
            out.append(str(turn.get("text", "")))
    return out


static func get_available_next_nodes() -> Array:
    var out: Array = []
    var node := current_node()
    var nxt := str(node.get("next", ""))
    if nxt != "" and is_node_accessible(nxt):
        out.append(nxt)
    for option in node.get("options", []):
        var target := str(option.get("next", ""))
        if target != "" and is_node_accessible(target):
            out.append(target)
    return out


static func _build_dialogue_index(dialogue_data: Dictionary) -> Dictionary:
    var index: Dictionary = {}
    for raw in dialogue_data.get("dialogue", []):
        if not (raw is Dictionary):
            continue
        var d: Dictionary = raw
        var key := str(d.get("npc_id", "")) + "|" + str(d.get("quest_id", "")) + "|" + str(d.get("node_id", "")) + "|" + str(d.get("variant", "default"))
        index[key] = d.duplicate(true)
    return index
