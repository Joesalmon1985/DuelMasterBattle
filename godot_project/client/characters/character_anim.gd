extends RefCounted
class_name DmbCharAnim

## The one animation controller of a character.  It is driven by what is happening (is it moving, is it speaking, was it hurt, is it
## dead), never by free-running timers, and it owns the single decision "which frame of which clip".
##
## Priority, highest first:  DEAD > REVIVE > HURT > reaction (CAST / CELEBRATE / SURPRISE) > TALK > WALK / WORK > IDLE
## A higher state interrupts a lower one; a lower one never interrupts a higher one.  Death holds its last frame until revived.

const Lib = preload("res://client/characters/character_library.gd")
const Bus = preload("res://client/characters/character_bus.gd")

enum S { IDLE, WALK, WORK, TALK, CAST, CELEBRATE, SURPRISE, HURT, DYING, DEAD, REVIVING }

var look
var id := ""
var facing := "down"          # down | left | right | up
var state: int = S.IDLE
var clip := "idle"
var frame := 0
var t := 0.0                  # time inside the clip, seconds
var moving := false
var working := false
var speaking := false
var _blink := 0.0             # >0 while a blink frame is shown
var _next_blink := 2.5
var _idle_phase := 0.0
var _hold := 0.0              # a one-shot reaction in progress: seconds left
var _react_clip := ""
var _walk_pause := 0.0        # hysteresis so a one-frame stall does not flicker the legs
var dead := false
var changed := true           # the drawn cell changed since the last `consume_change()`
var _last_cell := Vector2i(-1, -1)
var _last_flip := false


func _init(look_ = null, id_ := "") -> void:
	look = look_
	id = id_
	if look != null:
		t = look.phase * 3.0
		_next_blink = 1.5 + look.phase * 4.0


func set_look(look_) -> void:
	look = look_


func set_facing(f: String) -> void:
	if f in ["down", "up", "left", "right"]:
		facing = f


static func facing_from_vector(v: Vector2, fallback: String = "down") -> String:
	if v.length() < 0.001:
		return fallback
	if absf(v.x) >= absf(v.y):
		return "right" if v.x > 0.0 else "left"
	return "down" if v.y > 0.0 else "up"


static func facing_from_compass(c: String, fallback: String = "down") -> String:
	match c:
		"n":
			return "up"
		"s":
			return "down"
		"e", "ne", "se":
			return "right"
		"w", "nw", "sw":
			return "left"
		"up", "down", "left", "right":
			return c
	return fallback


func _has(name: String) -> bool:
	return look != null and Lib.clip_available(look.outfit, name)


func _enter(new_state: int, new_clip: String) -> void:
	if new_clip != clip or new_state != state:
		t = 0.0
	state = new_state
	clip = new_clip


## One presentation step.  `is_moving` is what the renderer sees (a position that changes), `is_working` is the simulation's own
## work flag if it has one.  Returns true when the drawn cell changed.
func update(dt: float, is_moving: bool, is_working: bool = false) -> bool:
	if look == null:
		return false
	if is_moving:
		_walk_pause = 0.12
	elif _walk_pause > 0.0:
		_walk_pause -= dt
	moving = is_moving or _walk_pause > 0.0
	working = is_working
	var want_speak := Bus.is_speaking(id)
	speaking = want_speak
	var is_dead := dead or Bus.is_dead(id)
	t += dt
	# ---- death and revival override everything
	if is_dead and state != S.DEAD and state != S.DYING:
		_hold = 0.0
		_enter(S.DYING, "die")
	elif not is_dead and (state == S.DEAD or state == S.DYING):
		_enter(S.REVIVING, "die")
		t = 0.0
	if state == S.DYING:
		var n := Lib.clip_frames("die")
		if t * Lib.fps("die") >= float(n):
			state = S.DEAD
	elif state == S.REVIVING:
		var n2 := Lib.clip_frames("die")
		if t * Lib.fps("revive") >= float(n2):
			_enter(S.IDLE, "idle")
	elif state == S.DEAD:
		pass
	else:
		for kind in Bus.take(id):
			_start_reaction(str(kind))
		if _hold > 0.0:
			_hold -= dt
			if _hold <= 0.0:
				_hold = 0.0
				_enter(S.IDLE, "idle")
		if _hold <= 0.0:
			if moving:
				if state != S.WALK:
					_enter(S.WALK, "walk")
			elif speaking:
				if state != S.TALK:
					_enter(S.TALK, "talk")
			elif is_working and _has("work"):
				if state != S.WORK:
					_enter(S.WORK, "work")
			elif state != S.IDLE:
				_enter(S.IDLE, "idle")
		else:
			# a reaction is playing: walking still takes priority over a harmless idle-ish reaction, but not over HURT / CAST
			if moving and state in [S.SURPRISE, S.CELEBRATE]:
				_hold = 0.0
				_enter(S.WALK, "walk")
	frame = _frame_for_state(dt)
	return _refresh_cell()


func _start_reaction(kind: String) -> void:
	match kind:
		"hurt":
			_enter(S.HURT, "hurt")
			_hold = float(Lib.clip_frames("hurt")) / Lib.fps("hurt") + 0.1
		"cast":
			var c := "cast" if _has("cast") else "surprise"
			_enter(S.CAST, c)
			_hold = float(Lib.clip_frames(c)) / Lib.fps(c) + 0.15
		"celebrate":
			var c2 := "celebrate" if _has("celebrate") else "surprise"
			_enter(S.CELEBRATE, c2)
			_hold = 1.2 if c2 == "celebrate" else float(Lib.clip_frames(c2)) / Lib.fps(c2)
		"surprise":
			_enter(S.SURPRISE, "surprise")
			_hold = float(Lib.clip_frames("surprise")) / Lib.fps("surprise") + 0.5
		"die":
			dead = true
		"revive":
			dead = false
		"respond":   # the player answered: a short talk burst even if nobody is "speaking" on the bus
			Bus.speak(id, 1.4)


func _frame_for_state(dt: float) -> int:
	var n := Lib.clip_frames(clip)
	var fps := Lib.fps(clip)
	match state:
		S.IDLE:
			return _idle_frame(dt)
		S.DEAD:
			return n - 1
		S.REVIVING:
			return clampi(n - 1 - int(t * Lib.fps("revive")), 0, n - 1)
		S.DYING, S.HURT, S.CAST, S.SURPRISE:
			return clampi(int(t * fps), 0, n - 1)
		_:
			return int(t * fps) % n


## Idle breathes slowly and blinks now and then; nothing more, so a crowded village stays calm.
func _idle_frame(dt: float) -> int:
	if _blink > 0.0:
		_blink -= dt
		return 3
	_next_blink -= dt
	if _next_blink <= 0.0:
		_blink = 0.14
		_next_blink = 2.2 + fmod(look.phase * 7.3 + t * 0.37, 3.4)
		return 3
	var cyc := fmod(t + look.phase * 3.0, 3.2)
	if cyc < 1.4:
		return 0
	if cyc < 2.2:
		return 1
	if cyc < 2.6:
		return 2
	return 1


func cell() -> Vector2i:
	var row: int = {"down": 0, "left": 1, "right": 1, "up": 2}[facing]
	return Vector2i(Lib.clip_start(clip) + frame, row)


func flipped() -> bool:
	return facing == "left"


func _refresh_cell() -> bool:
	var c := cell()
	var fl := flipped()
	var diff := c != _last_cell or fl != _last_flip
	_last_cell = c
	_last_flip = fl
	changed = changed or diff
	return diff


func consume_change() -> bool:
	var c := changed
	changed = false
	return c


func state_name() -> String:
	return ["idle", "walk", "work", "talk", "cast", "celebrate", "surprise", "hurt", "dying", "dead", "reviving"][state]
