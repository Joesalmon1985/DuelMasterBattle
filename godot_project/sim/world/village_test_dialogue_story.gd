extends RefCounted
class_name VillageTestDialogueStory

## Test-only sequential story state. It lives in Adventure.state and is never
## saved by this handler, so VillageTestRunner Reset/Exit can restore it.

const STATE_KEY := "village_test_story_progress"

static func interact(adv: Node, entity: Dictionary) -> Dictionary:
    var meta: Dictionary = entity.get("village_test_story", {})
    var story_id := str(meta.get("story_id", "e17a_dialogue_story"))
    var beat_id := str(meta.get("beat", entity.get("id", "")))
    var requires: Array = meta.get("requires", [])
    var sets: Array = meta.get("sets", [])

    var root: Dictionary = adv.state.get(STATE_KEY, {})
    var story_state: Dictionary = root.get(story_id, {})
    var unlocked := true
    for req in requires:
        if not bool(story_state.get(str(req), false)):
            unlocked = false
            break

    var lines: Array = entity.get("lines", []) if unlocked else entity.get("locked_lines", ["You are missing part of this story."])
    if unlocked:
        for flag in sets:
            story_state[str(flag)] = true
        story_state["last_beat"] = beat_id
        root[story_id] = story_state
        adv.state[STATE_KEY] = root

    return {"lines": lines, "unlocked": unlocked, "story_id": story_id, "beat": beat_id}
