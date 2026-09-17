extends Node
class_name DmbClockDriver

## Client clock accumulator: never awards backlog after focus return.
## Pending advances are bounded; the shell drains at most one AdvanceGame in flight.

signal advance_requested(delta_ms: int, sequence: int)

var _accumulator_ms: float = 0.0
var _sequence: int = 0
var _focused := true
var _pause_depth: int = 0
var _pending: Array = []
const STEP_MS := 100.0
## Bound prevents endless catch-up after a delayed reply without dropping
## already-queued legitimate unpaused steps beyond this shallow window.
const MAX_PENDING := 2


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
	_pending.clear()


func tick_render(delta_sec: float) -> int:
	if is_paused():
		return 0
	# While the pending queue is saturated, discard further wall time so a delayed
	# AdvanceGame reply cannot create an unbounded catch-up storm.
	if _pending.size() >= MAX_PENDING:
		return 0
	_accumulator_ms += delta_sec * 1000.0
	var advanced := 0
	while _accumulator_ms >= STEP_MS and _pending.size() < MAX_PENDING:
		_accumulator_ms -= STEP_MS
		_sequence += 1
		advanced += int(STEP_MS)
		_pending.append({"delta_ms": int(STEP_MS), "clock_sequence": _sequence})
		advance_requested.emit(int(STEP_MS), _sequence)
	return advanced


func pending_count() -> int:
	return _pending.size()


func peek_pending() -> Dictionary:
	if _pending.is_empty():
		return {}
	return _pending[0]


func pop_pending() -> Dictionary:
	if _pending.is_empty():
		return {}
	return _pending.pop_front()


func ack_pending(sequence: int) -> void:
	## Remove the matching head (or any matching sequence) after Python accepts.
	if _pending.is_empty():
		return
	if int(_pending[0].get("clock_sequence", -1)) == sequence:
		_pending.pop_front()
		return
	for i in range(_pending.size()):
		if int(_pending[i].get("clock_sequence", -1)) == sequence:
			_pending.remove_at(i)
			return


func drain_pending() -> Array:
	var out := _pending.duplicate()
	_pending.clear()
	return out
