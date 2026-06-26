class_name DmbCastWindow
extends RefCounted

enum State { LOCKED, READY, RESOLVING, EXHAUSTED }

var min_cast_time: float = 5.0
var max_cast_time: float = 16.0
var elapsed: float = 0.0
var state: int = State.LOCKED
var attacks_remaining: int = 12
var pending_pattern: Array = []
var cast_timestamp: float = 0.0


func reset_times(min_t: float, max_t: float, attacks: int) -> void:
	min_cast_time = min_t
	max_cast_time = max_t
	attacks_remaining = attacks
	elapsed = 0.0
	state = State.LOCKED if attacks > 0 else State.EXHAUSTED
	pending_pattern.clear()
	cast_timestamp = 0.0


func open_window() -> void:
	if state == State.EXHAUSTED:
		return
	elapsed = 0.0
	state = State.LOCKED
	pending_pattern.clear()
	cast_timestamp = 0.0


func advance(delta: float) -> void:
	if state == State.EXHAUSTED or state == State.RESOLVING:
		return
	elapsed += delta
	if state == State.LOCKED and elapsed >= min_cast_time:
		state = State.READY


func can_cast() -> bool:
	return state == State.READY and attacks_remaining > 0


func should_auto_cast() -> bool:
	return (
		(state == State.LOCKED or state == State.READY)
		and attacks_remaining > 0
		and elapsed >= max_cast_time
	)


func time_until_cast_ready() -> float:
	return maxf(0.0, min_cast_time - elapsed)


func time_until_auto_cast() -> float:
	return maxf(0.0, max_cast_time - elapsed)


func begin_resolve(timestamp: float) -> void:
	state = State.RESOLVING
	cast_timestamp = timestamp
	attacks_remaining = maxi(0, attacks_remaining - 1)


func finish_resolve() -> void:
	if attacks_remaining <= 0:
		state = State.EXHAUSTED
	else:
		open_window()
