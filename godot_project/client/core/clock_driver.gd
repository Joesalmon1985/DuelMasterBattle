extends Node
class_name DmbClockDriver

## Client clock accumulator: never awards backlog after focus return.

signal advance_requested(delta_ms: int, sequence: int)

var _accumulator_ms: float = 0.0
var _sequence: int = 0
var _focused := true
var _pause_depth: int = 0
var _pending: Array = []
const STEP_MS := 100.0


func open_pause_screen() -> void:
	_pause_depth += 1


func close_pause_screen() -> void:
	_pause_depth = max(0, _pause_depth - 1)


func is_paused() -> bool:
	return _pause_depth > 0 or not _focused


func notify_focus(has_focus: bool) -> void:
	_focused = has_focus
	# Intentionally drop backlog on focus return.
	_accumulator_ms = 0.0


func tick_render(delta_sec: float) -> int:
	if is_paused():
		return 0
	_accumulator_ms += delta_sec * 1000.0
	var advanced := 0
	while _accumulator_ms >= STEP_MS:
		_accumulator_ms -= STEP_MS
		_sequence += 1
		advanced += int(STEP_MS)
		_pending.append({"delta_ms": int(STEP_MS), "clock_sequence": _sequence})
		advance_requested.emit(int(STEP_MS), _sequence)
	return advanced


func drain_pending() -> Array:
	var out := _pending.duplicate()
	_pending.clear()
	return out
