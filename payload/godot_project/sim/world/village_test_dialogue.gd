extends RefCounted
class_name VillageTestDialogue

## Data boundary for locally generated dialogue.
## user://village_test_dialogue.json wins over the checked-in test file.

const PROJECT_PATH := "res://content/village_test_dialogue.json"
const USER_PATH := "user://village_test_dialogue.json"

static func load_data() -> Dictionary:
    for path in [USER_PATH, PROJECT_PATH]:
        if not FileAccess.file_exists(path):
            continue
        var file := FileAccess.open(path, FileAccess.READ)
        if file == null:
            continue
        var parsed = JSON.parse_string(file.get_as_text())
        if typeof(parsed) == TYPE_DICTIONARY:
            return parsed
    push_warning("VillageTestDialogue: no valid dialogue JSON; using fallback.")
    return _fallback()

static func npc(data: Dictionary, npc_id: String, fallback_name: String, fallback_lines: Array) -> Dictionary:
    var rec: Dictionary = data.get("npcs", {}).get(npc_id, {})
    return {
        "name": str(rec.get("name", fallback_name)),
        "sprite": str(rec.get("sprite", "npc")),
        "lines": _as_lines(rec.get("lines", fallback_lines)),
        "locked_lines": _as_lines(rec.get("locked_lines", ["I have nothing more for you yet."])),
    }

static func _as_lines(value) -> Array:
    var out: Array = []
    if typeof(value) == TYPE_ARRAY:
        for item in value:
            out.append(str(item))
    elif str(value) != "":
        out.append(str(value))
    return out

static func _fallback() -> Dictionary:
    return {
        "npcs": {
            "reeve": {"name": "Reeve", "lines": ["A production ledger has vanished. Start with the logging camp."]},
            "woodcutter": {"name": "Woodcutter", "lines": ["I carried the tally to the mill myself."]},
            "miller": {"name": "Miller", "lines": ["The miner knew the ledger was missing before anyone told him."]},
            "miner": {"name": "Miner", "lines": ["I found it on the ore road. The figures prove somebody has been shaving shipments."]},
        }
    }
