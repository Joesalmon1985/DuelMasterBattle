extends RefCounted
class_name DmbCharBus

## Presentation events from gameplay systems (dialogue, combat, duels) to whoever draws characters.
## Keyed by the character's stable id (an entity id, "john", "lan:p2", a cutscene actor key ...).  Nothing here feeds back into the
## simulation: a renderer asks `is_speaking(id)` and consumes one-shot reactions with `take(id)`.

static var _speaking: Dictionary = {}   # id -> absolute end time in seconds (-1: until stopped)
static var _pending: Dictionary = {}    # id -> Array of reaction names
static var _dead: Dictionary = {}       # id -> true while the character is dead
static var _fake := -1.0                # tests drive time by hand with `set_time`
static var events: Array = []           # last events, for tests and the showcase


static func now() -> float:
	return _fake if _fake >= 0.0 else float(Time.get_ticks_msec()) / 1000.0


static func set_time(t: float) -> void:
	_fake = t


## Seconds a line takes to say: about 22 characters a second, never less than 1.2 s.
static func line_seconds(text: String) -> float:
	return maxf(1.2, float(text.length()) / 22.0)


static func speak(id: String, seconds: float = -1.0) -> void:
	if id == "":
		return
	_speaking[id] = (now() + seconds) if seconds >= 0.0 else -1.0
	_note("speak", id)


static func speak_text(id: String, text: String) -> void:
	speak(id, line_seconds(text))


static func stop_speaking(id: String) -> void:
	_speaking.erase(id)
	_note("stop", id)


static func stop_all() -> void:
	_speaking.clear()
	_note("stop_all", "")


static func is_speaking(id: String) -> bool:
	if not _speaking.has(id):
		return false
	var end: float = _speaking[id]
	if end >= 0.0 and now() >= end:
		_speaking.erase(id)
		return false
	return true


static func react(id: String, kind: String) -> void:
	if id == "":
		return
	if not _pending.has(id):
		_pending[id] = []
	_pending[id].append(kind)
	_note("react:" + kind, id)


static func take(id: String) -> Array:
	if not _pending.has(id):
		return []
	var out: Array = _pending[id]
	_pending.erase(id)
	return out


static func mark_dead(id: String, dead: bool) -> void:
	if dead:
		_dead[id] = true
		_speaking.erase(id)
	else:
		_dead.erase(id)
	_note("dead" if dead else "alive", id)


static func is_dead(id: String) -> bool:
	return _dead.has(id)


static func reset() -> void:
	_speaking.clear()
	_pending.clear()
	_dead.clear()
	events.clear()


static func _note(kind: String, id: String) -> void:
	events.append({"t": now(), "kind": kind, "id": id})
	if events.size() > 200:
		events.pop_front()
