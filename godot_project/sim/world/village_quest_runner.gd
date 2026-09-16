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


static func _entry_exact(npc_id: String, node_id: String, variant: String) -> Dictionary:
    var key := _entry_key(npc_id, node_id, variant)
    if _dialogue_index.has(key):
        return (_dialogue_index[key] as Dictionary).duplicate(true)
    return {}


## Legacy lookup. A missing non-default variant may still resolve to default.
## Player-selected replies must use _entry_exact instead.
static func _entry(npc_id: String, node_id: String, variant: String = "default") -> Dictionary:
    var exact := _entry_exact(npc_id, node_id, variant)
    if not exact.is_empty():
        return exact
    if variant != "default":
        return _entry_exact(npc_id, node_id, "default")
    return {}


## Spoken lines for the moment the player talks to the current node, before a
## choice is resolved. Prefer an authored default/opening entry. A choice node
## whose speech lives only on branch variants still speaks its existing prompt
## so the talk is not silent; the variant turns stay on make_choice.
static func _opening_turns(npc_id: String, node: Dictionary) -> Array:
    for variant in ["default", "opening"]:
        var entry := _entry_exact(npc_id, _current_node, variant)
        var turns := _entry_turns(entry)
        if not turns.is_empty():
            return turns
    var prompt := str(node.get("prompt", node.get("text", "")))
    if prompt == "":
        return []
    return [{"speaker": "npc", "text": prompt}]


static func _entry_turns(entry: Dictionary) -> Array:
    if entry.has("turns") and entry["turns"] is Array:
        return (entry["turns"] as Array).duplicate(true)
    var turns: Array = []
    for line in entry.get("lines", []):
        turns.append({"speaker": "npc", "text": str(line)})
    return turns


## Spoken lines when this NPC is not advancing the current quest node.
## Precedence: phase ambient, generic __ambient__, epilogue after the core
## decisions, then a safe default that is not a branch variant, then a
## non-empty fixture line for anyone who already has authored dialogue.
## Never reads dialogue_context. Never reads branch variants.
static func ambient_turns(npc_id: String) -> Array:
    if is_complete() or _branch_letter("scene_03") != "":
        var ending := _epilogue_turns(npc_id)
        if not ending.is_empty():
            return ending
    var phased := _phased_ambient(npc_id)
    if not phased.is_empty():
        return phased
    var generic := _entry_turns(_entry(npc_id, "__ambient__", "default"))
    if not generic.is_empty():
        return generic
    if not is_complete() and _branch_letter("scene_03") == "" and _current_profile == "E17A":
        var aside := _safe_default_turns(npc_id)
        if not aside.is_empty():
            return aside
    if _speaks_in_fixture(npc_id):
        return [{"speaker": "npc", "text": "They acknowledge you, but have nothing new to say just now."}]
    return []


## Talk to any villager. Quest and ordinary NPCs share one payload:
## opening turns plus the responses the player may select.
static func conversation_for(npc_id: String) -> Dictionary:
    if _current_quest.is_empty():
        return {"success": false, "error": "No active village quest", "turns": [], "options": [], "type": "conversation"}
    if _owns_progression(npc_id):
        return _progression_conversation(npc_id)
    return _ambient_conversation(npc_id)


## Apply a response the player actually selected. Ambient topics never
## mutate quest state. Progression replies are exact or they are refused.
static func respond_to(npc_id: String, choice_index: int) -> Dictionary:
    var offered := conversation_for(npc_id)
    if not bool(offered.get("success", false)):
        return offered
    var selected := _option_at(offered.get("options", []), choice_index)
    if selected.is_empty():
        return {"success": false, "error": "Unknown response", "turns": [], "options": []}
    var kind := str(selected.get("kind", ""))
    if kind == "progression" or kind == "inquiry":
        if not _owns_progression(npc_id):
            return {"success": false, "error": "That response is not available", "turns": []}
        var result := make_choice(int(selected.get("index", choice_index)))
        if bool(result.get("success", false)) and (kind == "inquiry" or bool(result.get("inquiry", false))):
            result["return_options"] = true
            result["options"] = conversation_for(npc_id).get("options", [])
        return result
    var variant := str(selected.get("id", selected.get("variant", "")))
    var turns := _topic_turns(npc_id, variant)
    if _spoken_turns(turns).is_empty():
        return {"success": false, "error": "That reply is not authored", "turns": [], "options": []}
    return {
        "success": true,
        "type": "conversation",
        "kind": "ambient",
        "npc": npc_id,
        "variant": variant,
        "turns": turns,
        "options": offered.get("options", []),
        "return_options": true,
        "current_node": _current_node,
        "objective": objective_text(),
        "progression": false,
    }


static func _owns_progression(npc_id: String) -> bool:
    if is_complete() or npc_id == "":
        return false
    var node := current_node()
    if node.is_empty() or bool(node.get("observer", false)):
        return false
    if str(node.get("npc", "")) != npc_id:
        return false
    if str(node.get("type", "")) not in ["talk", "choice"]:
        return false
    return is_node_accessible(_current_node)


static func _progression_conversation(npc_id: String) -> Dictionary:
    var node := current_node()
    var node_type := str(node.get("type", "talk"))
    if node_type == "choice":
        var choice := current_choice_payload()
        choice["type"] = "conversation"
        choice["turns"] = _opening_turns(npc_id, node)
        choice["progression"] = true
        return choice
    var node_id := _current_node
    var entry := _entry(npc_id, node_id, "default")
    var turns := _entry_turns(entry)
    if turns.is_empty() and str(node.get("text", "")) != "":
        turns.append({"speaker": "npc", "text": str(node["text"])})
    if turns.is_empty():
        turns = ambient_turns(npc_id)
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
        "progression": true,
    }


static func _phased_ambient(npc_id: String) -> Array:
    var scene2 := _branch_letter("scene_02")
    if scene2 != "":
        return _first_exact_turns(npc_id, "__ambient__", [
            "after_scene_2_" + scene2,
            "after_scene_2",
        ])
    var scene1 := _branch_letter("scene_01")
    if scene1 != "":
        return _first_exact_turns(npc_id, "__ambient__", [
            "after_scene_1_" + scene1,
            "after_scene_1",
        ])
    return _turns_exact(npc_id, "__ambient__", "opening")


static func _epilogue_turns(npc_id: String) -> Array:
    var entry := _entry_exact(npc_id, "__epilogue__", _epilogue_variant)
    if entry.is_empty() and _epilogue_variant != "normal":
        entry = _entry_exact(npc_id, "__epilogue__", "normal")
    return _entry_turns(entry)


static func _branch_letter(scene_id: String) -> String:
    if _flags.has(scene_id + "_branch_a"):
        return "a"
    if _flags.has(scene_id + "_branch_b"):
        return "b"
    return ""


static func _speaks_in_fixture(npc_id: String) -> bool:
    var prefix := npc_id + "|" + quest_id() + "|"
    for key in _dialogue_index.keys():
        if str(key).begins_with(prefix):
            return true
    return false


## Existing default lines that are not a branch or inquiry. E17A stores those
## on later scene nodes. Other fixtures stay quiet so a future quest default
## is not spoken early. Never reads branch variants.
static func _safe_default_turns(npc_id: String) -> Array:
    var prefix := npc_id + "|" + quest_id() + "|"
    for key in _dialogue_index.keys():
        var k := str(key)
        if not k.begins_with(prefix) or not k.ends_with("|default"):
            continue
        var entry: Dictionary = _dialogue_index[key]
        if str(entry.get("node_id", "")).begins_with("__"):
            continue
        var turns := _entry_turns(entry)
        if not turns.is_empty():
            return turns
    return []


static func _ambient_result(npc_id: String) -> Dictionary:
    return _ambient_conversation(npc_id)


static func _ambient_conversation(npc_id: String) -> Dictionary:
    return {
        "success": true,
        "type": "conversation",
        "npc": npc_id,
        "turns": _conversation_opening(npc_id),
        "options": _conversation_options(npc_id),
        "current_node": _current_node,
        "objective": objective_text(),
        "progression": false,
    }


## State-aware lines stay the greeting when they exist. Topics are separate,
## so selecting one does not replay the opening.
static func _conversation_opening(npc_id: String) -> Array:
    if is_complete() or _branch_letter("scene_03") != "":
        var ending := _epilogue_turns(npc_id)
        if not ending.is_empty():
            return ending
    var phased := _phased_ambient(npc_id)
    if not phased.is_empty():
        return phased
    var opening := _turns_exact(npc_id, "__conversation__", "opening")
    if not opening.is_empty():
        return opening
    if not is_complete() and _branch_letter("scene_03") == "" and _current_profile == "E17A":
        var aside := _safe_default_turns(npc_id)
        if not aside.is_empty():
            return aside
    if _speaks_in_fixture(npc_id):
        return [{"speaker": "npc", "text": "They acknowledge you, but have nothing new to say just now."}]
    return []


static func _conversation_options(npc_id: String) -> Array:
    var found: Dictionary = {}
    var prefix := _entry_key(npc_id, "__conversation__", "")
    for key in _dialogue_index.keys():
        var k := str(key)
        if not k.begins_with(prefix):
            continue
        var variant := k.substr(prefix.length())
        if variant == "" or variant == "opening":
            continue
        var entry: Dictionary = _dialogue_index[key]
        var label := str(entry.get("choice_label", "")).strip_edges()
        if label == "" or _spoken_turns(_entry_turns(entry)).is_empty():
            continue
        found[variant] = label
    var order: Array = []
    for preferred in ["situation", "work", "village"]:
        if found.has(preferred):
            order.append(preferred)
    var extras: Array = []
    for variant in found.keys():
        if not order.has(variant):
            extras.append(str(variant))
    extras.sort()
    order.append_array(extras)
    var options: Array = []
    for i in range(order.size()):
        var variant := str(order[i])
        options.append({
            "index": i,
            "id": variant,
            "label": str(found[variant]),
            "variant": variant,
            "kind": "ambient",
        })
    return options


static func _topic_turns(npc_id: String, variant: String) -> Array:
    if variant == "situation":
        var phased := _situation_turns(npc_id)
        if not phased.is_empty():
            return phased
    return _turns_exact(npc_id, "__conversation__", variant)


## After a beat, the situation topic uses the authored reaction instead of the
## opening-state line. Opening-phase ambient stays the greeting only.
static func _situation_turns(npc_id: String) -> Array:
    var scene2 := _branch_letter("scene_02")
    if scene2 != "":
        return _first_exact_turns(npc_id, "__ambient__", [
            "after_scene_2_" + scene2,
            "after_scene_2",
        ])
    var scene1 := _branch_letter("scene_01")
    if scene1 != "":
        return _first_exact_turns(npc_id, "__ambient__", [
            "after_scene_1_" + scene1,
            "after_scene_1",
        ])
    return []


static func _turns_exact(npc_id: String, node_id: String, variant: String) -> Array:
    return _entry_turns(_entry_exact(npc_id, node_id, variant))


static func _first_exact_turns(npc_id: String, node_id: String, variants: Array) -> Array:
    for variant in variants:
        var turns := _turns_exact(npc_id, node_id, str(variant))
        if not turns.is_empty():
            return turns
    return []


static func _spoken_turns(turns: Array) -> Array:
    var out: Array = []
    for raw in turns:
        if not (raw is Dictionary):
            continue
        if str((raw as Dictionary).get("text", "")).strip_edges() == "":
            continue
        out.append(raw)
    return out


static func _option_at(options: Array, choice_index: int) -> Dictionary:
    for raw in options:
        if raw is Dictionary and int((raw as Dictionary).get("index", -1)) == choice_index:
            return raw
    return {}


static func _progression_choice_errors() -> Array:
    var errors: Array = []
    var nodes: Dictionary = _current_quest.get("nodes", {})
    for node_id in ["scene_01_a", "scene_02_b", "scene_03_c"]:
        var node: Dictionary = nodes.get(node_id, {})
        if node.is_empty():
            errors.append("missing node %s" % node_id)
            continue
        var npc := str(node.get("npc", ""))
        var prompt := str(node.get("prompt", "")).strip_edges()
        var options: Array = node.get("options", [])
        if options.is_empty():
            errors.append("%s has no choices" % node_id)
        for option in options:
            if not (option is Dictionary):
                errors.append("%s has a malformed choice" % node_id)
                continue
            var variant := str(option.get("variant", ""))
            var entry := _entry_exact(npc, node_id, variant)
            if entry.is_empty():
                errors.append("%s/%s is missing its exact dialogue entry" % [node_id, variant])
                continue
            if str(entry.get("choice_label", "")).strip_edges() == "":
                errors.append("%s/%s is missing choice_label" % [node_id, variant])
            var spoken := _spoken_turns(_entry_turns(entry))
            if spoken.is_empty():
                errors.append("%s/%s has no reply turn" % [node_id, variant])
                continue
            if bool(option.get("inquiry", false)) and prompt != "" and str(spoken[0].get("text", "")).strip_edges() == prompt:
                errors.append("%s/%s repeats the opening prompt" % [node_id, variant])
    return errors


## Interact with an NPC. Talking is not the same as advancing the quest.
static func interact_npc(npc_id: String) -> Dictionary:
    return conversation_for(npc_id)


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


## Selected responses never fall back to a node's opening/default entry.
static func lookup_exact(npc_id: String, node_id: String, variant: String) -> Dictionary:
    return _entry_exact(npc_id, node_id, variant)


static func progression_choice_errors() -> Array:
    return _progression_choice_errors()


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
        var entry := _entry_exact(npc_id, _current_node, variant) if npc_id != "" else {}
        var label := str(entry.get("choice_label", option.get("label", option.get("fallback_label", "Option %d" % [i + 1]))))
        var inquiry := bool(option.get("inquiry", false))
        options_out.append({
            "index": i,
            "id": variant,
            "label": label,
            "variant": variant,
            "kind": "inquiry" if inquiry else "progression",
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
    var npc_id := str(node.get("npc", ""))
    var variant := str(option.get("variant", "default"))
    var entry := _entry_exact(npc_id, _current_node, variant) if npc_id != "" else {}
    var turns := _spoken_turns(_entry_turns(entry))
    if turns.is_empty():
        return {
            "success": false,
            "error": "Missing exact reply for %s/%s" % [_current_node, variant],
            "turns": [],
            "node_id": _current_node,
            "variant": variant,
        }
    if bool(option.get("inquiry", false)):
        return {
            "success": true,
            "inquiry": true,
            "return_options": true,
            "type": "inquiry",
            "node_id": _current_node,
            "variant": variant,
            "turns": turns,
            "next_node": _current_node,
            "options": current_choice_payload().get("options", []),
            "objective": objective_text(),
        }
    _apply_sets(option.get("sets", []))
    var ending_hint := str(option.get("ending_hint", ""))
    if ending_hint in ["normal", "tragic"]:
        _epilogue_variant = ending_hint
    var old_node := _current_node
    _current_node = str(option.get("next", ""))
    # Supporting talk nodes stay in the graph, but they are not a checklist.
    # Once the core choices are resolved, settle the existing conclude so
    # later conversation can use epilogue lines. The returned choice turns
    # are already captured and are not replaced by the conclude sentence.
    _settle_observer_chain()
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
static func _settle_observer_chain() -> void:
    if is_complete():
        return
    var node := current_node()
    if not bool(node.get("observer", false)):
        return
    if _branch_letter("scene_03") == "":
        return
    if not _current_quest.get("nodes", {}).has("complete_story"):
        return
    _current_node = "complete_story"
    execute_current()


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
