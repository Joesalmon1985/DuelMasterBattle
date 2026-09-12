extends RefCounted
class_name VillageQuestRunner

## Executes a portable quest graph for village test mode.
## Manages quest state, dialogue variant selection, and node transitions.

const Catalog = preload("res://sim/world/village_test_catalog.gd")

static var _current_quest: Dictionary = {}
static var _current_profile: String = ""
static var _flags: Dictionary = {}
static var _current_node: String = ""
static var _dialogue_variants: Dictionary = {}
static var _completed_endings: Array = []

## Initialize quest runner for a profile
static func begin(profile_id: String) -> void:
    _current_profile = profile_id
    var fixture = Catalog.load_fixture(profile_id)
    if fixture.is_empty():
        push_error("VillageQuestRunner: Failed to load fixture " + profile_id)
        return
    
    _current_quest = fixture.get("quest", {})
    _flags = {}
    _current_node = _current_quest.get("start_node", "")
    _dialogue_variants = _build_dialogue_index(fixture.get("dialogue", {}))
    _completed_endings = []
    
    # Seed initial flags from quest if any
    var start_node_data = _current_quest.get("nodes", {}).get(_current_node, {})
    if start_node_data.has("sets"):
        for flag in start_node_data["sets"]:
            _flags[flag] = true

## Get current quest state
static func get_state() -> Dictionary:
    return {
        "profile": _current_profile,
        "quest_id": _current_quest.get("id", ""),
        "quest_title": _current_quest.get("title", ""),
        "current_node": _current_node,
        "flags": _flags.duplicate(true),
        "completed_endings": _completed_endings.duplicate()
    }

## Check if a dialogue variant is available for an NPC at current quest state
static func get_dialogue_variant(npc_id: String, quest_id: String, node_id: String) -> String:
    # Determine variant based on flags
    var variant = "default"
    
    # Check for specific variants based on flags
    if _flags.has("retrieved_ledger"):
        if _flags.has("choice_return_to_reve"):
            variant = "after_confession"
        elif _flags.has("choice_give_to_mara"):
            variant = "victorious"
        elif _flags.has("choice_burn_ledger"):
            variant = "unaware"
    elif _flags.has("confronted_reve_with_evidence") or _flags.has("found_burnt_letter"):
        variant = "after_reveal"
    elif _flags.has("confronted_reve"):
        variant = "after_reveal"
    
    # Per-NPC variant logic
    if npc_id == "reve_edric":
        if _flags.has("ending_redemption_achieved"):
            variant = "after_confession"
        elif _flags.has("ending_mara_victory_achieved"):
            variant = "arrested"
        elif _flags.has("ending_status_quo_achieved"):
            variant = "unaware"
        elif _flags.has("confronted_reve_with_evidence"):
            variant = "default"  # confront_reve_with_evidence node
        elif _flags.has("confronted_reve"):
            variant = "default"  # confront_reve_kiln node
    elif npc_id == "mara_potter":
        if _flags.has("ending_redemption_achieved"):
            variant = "forgiving"
        elif _flags.has("ending_mara_victory_achieved"):
            variant = "victorious"
        elif _flags.has("ending_status_quo_achieved"):
            variant = "unaware"
        elif _flags.has("found_burnt_letter") or _flags.has("retrieved_ledger"):
            variant = "after_reveal"
    elif npc_id == "healer_elara":
        if _flags.has("ending_redemption_achieved"):
            variant = "relieved"
        elif _flags.has("ending_mara_victory_achieved"):
            variant = "concerned"
        elif _flags.has("ending_status_quo_achieved"):
            variant = "knowing"
    elif npc_id == "scavenger_jory":
        if _flags.has("ending_redemption_achieved"):
            variant = "accepting"
        elif _flags.has("ending_mara_victory_achieved"):
            variant = "partner"
        elif _flags.has("ending_status_quo_achieved"):
            variant = "patient"
        elif _flags.has("made_deal_with_jory"):
            variant = "deal_made"
        elif _flags.has("threatened_jory"):
            variant = "threatened"
    elif npc_id == "kiln_master_brand":
        if _flags.has("ending_redemption_achieved"):
            variant = "defeated"
        elif _flags.has("ending_mara_victory_achieved"):
            variant = "litigating"
        elif _flags.has("ending_status_quo_achieved"):
            variant = "victorious"
    elif npc_id == "farmstead_anna":
        if _flags.has("ending_redemption_achieved"):
            variant = "hopeful"
        elif _flags.has("ending_mara_victory_achieved"):
            variant = "worried"
        elif _flags.has("ending_status_quo_achieved"):
            variant = "resigned"
    elif npc_id == "tavern_keep":
        if _flags.has("ending_redemption_achieved"):
            variant = "satisfied"
        elif _flags.has("ending_mara_victory_achieved"):
            variant = "watchful"
        elif _flags.has("ending_status_quo_achieved"):
            variant = "knowing"
    elif npc_id == "blacksmith_tomas":
        if _flags.has("ending_redemption_achieved"):
            variant = "principled"
        elif _flags.has("ending_mara_victory_achieved"):
            variant = "struggling"
        elif _flags.has("ending_status_quo_achieved"):
            variant = "steady"
    elif npc_id == "general_store_keep":
        if _flags.has("ending_redemption_achieved"):
            variant = "optimistic"
        elif _flags.has("ending_mara_victory_achieved"):
            variant = "cautious"
        elif _flags.has("ending_status_quo_achieved"):
            variant = "steady"
    elif npc_id == "woodcutter_garrick":
        if _flags.has("ending_redemption_achieved"):
            variant = "approving"
        elif _flags.has("ending_mara_victory_achieved"):
            variant = "concerned"
        elif _flags.has("ending_status_quo_achieved"):
            variant = "indifferent"
    
    return variant

## Get dialogue lines for an NPC at current quest state
static func get_dialogue(npc_id: String, quest_id: String, node_id: String = "") -> Array:
    var variant = get_dialogue_variant(npc_id, quest_id, node_id)
    var key = npc_id + "|" + quest_id + "|" + node_id + "|" + variant
    var fallback_key = npc_id + "|" + quest_id + "|" + node_id + "|default"
    
    if _dialogue_variants.has(key):
        return _dialogue_variants[key].duplicate(true)
    if _dialogue_variants.has(fallback_key):
        return _dialogue_variants[fallback_key].duplicate(true)
    
    # Return empty array - will fall back to NPC default lines in projection
    return []

## Execute a quest node (talk, investigate, choice, etc.)
static func execute_node(node_id: String) -> Dictionary:
    var nodes = _current_quest.get("nodes", {})
    var node = nodes.get(node_id, {})
    if node.is_empty():
        return {"success": false, "error": "Node not found: " + node_id}
    
    var node_type = node.get("type", "talk")
    
    # Check requirements
    if node.has("requires"):
        for req in node["requires"]:
            if not _flags.has(req):
                return {"success": false, "error": "Requirements not met: " + req, "requires": node["requires"]}
    
    # Execute node effects
    if node.has("sets"):
        for flag in node["sets"]:
            _flags[flag] = true
    
    # Handle different node types
    match node_type:
        "talk":
            _current_node = node.get("next", "")
            return {
                "success": true,
                "type": "talk",
                "npc": node.get("npc", ""),
                "anchor": node.get("anchor", ""),
                "text": node.get("text", ""),
                "next_node": _current_node
            }
        "investigate":
            _current_node = node.get("next", "")
            return {
                "success": true,
                "type": "investigate",
                "anchor": node.get("anchor", ""),
                "text": node.get("text", ""),
                "next_node": _current_node
            }
        "branch":
            # Branch nodes just present options, handled by UI
            return {
                "success": true,
                "type": "branch",
                "options": node.get("options", [])
            }
        "choice":
            # Choice nodes present options, actual choice handled by player input
            return {
                "success": true,
                "type": "choice",
                "prompt": node.get("prompt", ""),
                "options": node.get("options", [])
            }
        "conclude":
            var ending_state = node.get("final_state", "unknown")
            _completed_endings.append(ending_state)
            return {
                "success": true,
                "type": "conclude",
                "text": node.get("text", ""),
                "ending_state": ending_state
            }
    
    return {"success": false, "error": "Unknown node type: " + node_type}

## Make a choice in a choice node
static func make_choice(choice_index: int) -> Dictionary:
    var nodes = _current_quest.get("nodes", {})
    var node = nodes.get(_current_node, {})
    if node.get("type") != "choice":
        return {"success": false, "error": "Not at a choice node"}
    
    var options = node.get("options", [])
    if choice_index < 0 or choice_index >= options.size():
        return {"success": false, "error": "Invalid choice index"}
    
    var choice = options[choice_index]
    if choice.has("sets"):
        for flag in choice["sets"]:
            _flags[flag] = true
    
    _current_node = choice.get("next", "")
    return {"success": true, "next_node": _current_node, "ending_state": choice.get("final_state", "")}

## Check if a node is accessible (requirements met)
static func is_node_accessible(node_id: String) -> bool:
    var nodes = _current_quest.get("nodes", {})
    var node = nodes.get(node_id, {})
    if node.is_empty():
        return false
    if node.has("requires"):
        for req in node["requires"]:
            if not _flags.has(req):
                return false
    return true

## Get available next nodes from current position
static func get_available_next_nodes() -> Array:
    var nodes = _current_quest.get("nodes", {})
    var current = nodes.get(_current_node, {})
    var available: Array = []
    
    if current.has("next"):
        var next_id = current["next"]
        if is_node_accessible(next_id):
            available.append(next_id)
    elif current.has("options"):
        for opt in current["options"]:
            if opt.has("next") and is_node_accessible(opt["next"]):
                available.append(opt["next"])
    
    return available

## Reset quest state
static func reset() -> void:
    _flags.clear()
    _current_node = _current_quest.get("start_node", "")
    _completed_endings.clear()
    
    var start_node_data = _current_quest.get("nodes", {}).get(_current_node, {})
    if start_node_data.has("sets"):
        for flag in start_node_data["sets"]:
            _flags[flag] = true

## Check if quest is complete
static func is_complete() -> bool:
    return _completed_endings.size() > 0

## Get current flags for debug display
static func get_flags() -> Dictionary:
    return _flags.duplicate(true)

## Internal: build dialogue index for fast lookup
static func _build_dialogue_index(dialogue_data: Dictionary) -> Dictionary:
    var index: Dictionary = {}
    var dialogues = dialogue_data.get("dialogue", [])
    for d in dialogues:
        var key = str(d["npc_id"]) + "|" + str(d["quest_id"]) + "|" + str(d["node_id"]) + "|" + str(d["variant"])
        index[key] = d["lines"]
    return index