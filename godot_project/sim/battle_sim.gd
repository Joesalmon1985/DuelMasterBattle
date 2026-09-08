class_name DmbBattleSim
extends RefCounted

## Authoritative real-time battle between two DmbCombatants (player vs enemy).
## Generalises the MVP duel: each side has its own weave size, attack pool, Ward
## size/pool and cast window. Attacks with more slots than the target Ward wrap
## left-to-right (see DmbFeedback.score_attack).
##
## Public surface mirrors DmbRealtimeDuelSim so the battle screen can drive either.

const _CastWindow = preload("res://sim/cast_window.gd")
const _AutoCast = preload("res://sim/auto_cast.gd")
const _DuelEvent = preload("res://sim/duel_event.gd")
const _AttackRecord = preload("res://sim/attack_record.gd")
const _WeaveBot = preload("res://sim/weave_bot.gd")

const BOT_THINK_BUDGET_MSEC := 3.0

enum Phase { WARD_SETUP, DUELING, FINISHED }

var phase: int = Phase.WARD_SETUP
var result: DmbGameResult = null
var player_history: Array = []
var enemy_history: Array = []
var duel_time: float = 0.0

var player: DmbCombatant
var enemy: DmbCombatant

var _bot
var _rng := RandomNumberGenerator.new()
var _seed: int = 42
var _events: Array = []

var _player_ward: Array = []
var _enemy_ward: Array = []
var _player_attack: Array = []

var _player_window
var _enemy_window
var _enemy_cast_at: float = 0.0

var _player_casts: int = 0
var _enemy_casts: int = 0
var _paused: bool = false
var _fast_cast: bool = false


func _init(p_player: DmbCombatant, p_enemy: DmbCombatant, seed: int = 42) -> void:
	player = p_player
	enemy = p_enemy
	_player_window = _CastWindow.new()
	_enemy_window = _CastWindow.new()
	reset(seed)


func reset(seed: int = -1) -> void:
	if seed >= 0:
		_seed = seed
	_rng.seed = _seed
	_bot = _WeaveBot.new(enemy, player, _seed)
	phase = Phase.WARD_SETUP
	result = null
	player_history.clear()
	enemy_history.clear()
	duel_time = 0.0
	_events.clear()
	_player_ward = _empty(player.ward_size)
	_enemy_ward = _empty(enemy.ward_size)
	_player_attack = _empty(player.weave_size)
	_enemy_cast_at = 0.0
	_player_casts = 0
	_enemy_casts = 0
	_paused = false
	_player_window.reset_times(player.min_cast_seconds, player.max_cast_seconds, player.max_casts)
	_enemy_window.reset_times(enemy.min_cast_seconds, enemy.max_cast_seconds, enemy.max_casts)


static func _empty(n: int) -> Array:
	var a: Array = []
	for _i in range(n):
		a.append(null)
	return a


static func _complete(p: Array) -> bool:
	for v in p:
		if v == null:
			return false
	return true


# --- Compatibility accessors (battle screen) ---------------------------------

func get_bot():
	return _bot


func set_paused(on: bool) -> void:
	_paused = on


func is_paused() -> bool:
	return _paused


func player_weave_size() -> int:
	return player.weave_size


func player_ward_size() -> int:
	return player.ward_size


func enemy_ward_size() -> int:
	return enemy.ward_size


func enemy_weave_size() -> int:
	return enemy.weave_size


func player_attack_pool() -> Array:
	return player.attack_pool


func player_ward_pool() -> Array:
	return player.ward_pool


## Can the player's weave ever cover the enemy Ward?
func player_can_break_enemy() -> bool:
	return player.weave_size >= enemy.ward_size


func enemy_can_break_player() -> bool:
	return enemy.weave_size >= player.ward_size


# --- Ward setup ----------------------------------------------------------------

func can_lock_player_ward() -> bool:
	return phase == Phase.WARD_SETUP and _complete(_player_ward)


func set_player_ward_locus(i: int, spell: int) -> void:
	if phase != Phase.WARD_SETUP or i < 0 or i >= player.ward_size:
		return
	if spell < 0:
		_player_ward[i] = null
	elif spell in player.ward_pool:
		_player_ward[i] = spell


func clear_player_ward() -> void:
	if phase == Phase.WARD_SETUP:
		_player_ward = _empty(player.ward_size)


func randomise_player_ward() -> void:
	if phase == Phase.WARD_SETUP:
		_player_ward = _AutoCast.random_pattern(player.ward_size, player.ward_pool, player.allow_repeats, _rng)


func lock_player_ward_and_start() -> void:
	assert(can_lock_player_ward())
	_enemy_ward = _bot.generate_ward()
	_player_attack = _empty(player.weave_size)
	phase = Phase.DUELING
	_player_window.reset_times(player.min_cast_seconds, player.max_cast_seconds, player.max_casts)
	_enemy_window.reset_times(enemy.min_cast_seconds, enemy.max_cast_seconds, enemy.max_casts)
	_player_window.open_window()
	_open_enemy_window()
	if _fast_cast:
		_apply_fast_cast()
	_events.append(_DuelEvent.new(_DuelEvent.DUEL_STARTED, {}))


# --- Player attack -------------------------------------------------------------

func set_player_attack_locus(i: int, spell: int) -> void:
	if phase != Phase.DUELING or i < 0 or i >= player.weave_size:
		return
	if spell < 0:
		_player_attack[i] = null
	elif spell in player.attack_pool:
		_player_attack[i] = spell


func clear_player_attack() -> void:
	if phase == Phase.DUELING:
		_player_attack = _empty(player.weave_size)


func load_player_attack(pattern: Array) -> void:
	if phase != Phase.DUELING:
		return
	var out := _empty(player.weave_size)
	for i in range(mini(pattern.size(), player.weave_size)):
		if pattern[i] != null and int(pattern[i]) in player.attack_pool:
			out[i] = int(pattern[i])
	_player_attack = out


func get_player_attack_pattern() -> Array:
	return _player_attack.duplicate()


func is_player_attack_complete() -> bool:
	return _complete(_player_attack)


func first_empty_attack_locus() -> int:
	for i in range(_player_attack.size()):
		if _player_attack[i] == null:
			return i
	return -1


func get_player_ward() -> Array:
	return _player_ward.duplicate()


func get_enemy_ward() -> Array:
	return _enemy_ward.duplicate()


func is_player_window_open() -> bool:
	return phase == Phase.DUELING and _player_window.can_cast() and _player_casts < player.max_casts


func can_player_cast() -> bool:
	return is_player_window_open() and is_player_attack_complete()


func player_cast_block_reason() -> String:
	if phase != Phase.DUELING:
		return ""
	if _player_casts >= player.max_casts:
		return "No casts left"
	if _player_window.state == _CastWindow.State.LOCKED:
		return "Weaving…"
	if not is_player_attack_complete():
		return "Fill all %d spells" % player.weave_size
	return ""


func submit_player_attack() -> bool:
	if not can_player_cast():
		return false
	_resolve([_attack("player", _player_attack.duplicate(), false)])
	return true


# --- Testing hooks -------------------------------------------------------------

func set_testing_fast_cast(on: bool) -> void:
	_fast_cast = on
	if on:
		_apply_fast_cast()


func _apply_fast_cast() -> void:
	_player_window.min_cast_time = 0.0
	_enemy_window.min_cast_time = 0.0
	if _player_window.state == _CastWindow.State.LOCKED:
		_player_window.state = _CastWindow.State.READY
	if _enemy_window.state == _CastWindow.State.LOCKED:
		_enemy_window.state = _CastWindow.State.READY


func advance_time_for_test(s: float) -> void:
	advance_time(s, false)


func debug_set_enemy_ward(w: Array) -> void:
	_enemy_ward = w.duplicate()


func debug_set_enemy_cast_at(s: float) -> void:
	_enemy_cast_at = s


func force_finish_for_test(outcome: String) -> void:
	if result != null:
		return
	if phase == Phase.WARD_SETUP:
		phase = Phase.DUELING
	match outcome:
		"victory":
			_finish("victory", true, false, "forced")
		"defeat":
			_finish("defeat", false, true, "forced")
		"clash":
			_finish("clash", true, true, "forced")
		_:
			_finish("stalemate", false, false, "forced")


# --- Time ----------------------------------------------------------------------

func advance_time(delta: float, paused: bool = false) -> void:
	if phase != Phase.DUELING or result != null or paused or _paused:
		return
	duel_time += delta
	_player_window.advance(delta)
	_enemy_window.advance(delta)
	if _enemy_window.state != _CastWindow.State.EXHAUSTED:
		_bot.think(BOT_THINK_BUDGET_MSEC)
	var pending: Array = []
	if _player_window.should_auto_cast():
		pending.append(_attack("player", _AutoCast.fill_pattern(
			_player_attack, player.weave_size, player.attack_pool, true, _rng), true))
	if _enemy_should_cast():
		pending.append(_attack("enemy", _bot.planned_guess(), _enemy_window.should_auto_cast()))
	if not pending.is_empty():
		_resolve(pending)


func _open_enemy_window() -> void:
	_enemy_window.open_window()
	if _enemy_window.state == _CastWindow.State.EXHAUSTED:
		return
	var lo := maxf(_enemy_window.min_cast_time, enemy.think_min_seconds)
	var hi := maxf(lo, minf(_enemy_window.max_cast_time - 0.5, enemy.think_max_seconds))
	_enemy_cast_at = _rng.randf_range(lo, hi)
	_bot.begin_planning()


func _enemy_should_cast() -> bool:
	if _enemy_window.state == _CastWindow.State.EXHAUSTED:
		return false
	if _enemy_window.should_auto_cast():
		return true
	if not _enemy_window.can_cast() or _enemy_window.elapsed < _enemy_cast_at:
		return false
	return _bot.is_plan_ready()


func enemy_cast_progress() -> float:
	if phase != Phase.DUELING or _enemy_window.state == _CastWindow.State.EXHAUSTED:
		return 0.0
	return clampf(_enemy_window.elapsed / maxf(_enemy_cast_at, 0.1), 0.0, 1.0)


# --- Resolution ----------------------------------------------------------------

func _attack(who: String, pattern: Array, auto: bool) -> Dictionary:
	return {"attacker_id": who, "pattern": pattern, "auto_cast": auto}


func _resolve(batch: Array) -> void:
	batch.sort_custom(func(a, b): return a["attacker_id"] == "player" and b["attacker_id"] != "player")
	var p_broke := false
	var e_broke := false
	for item in batch:
		var w = _player_window if item["attacker_id"] == "player" else _enemy_window
		if w.state == _CastWindow.State.EXHAUSTED:
			continue
		w.begin_resolve(duel_time)
		var broke := _resolve_one(item)
		if item["attacker_id"] == "player":
			p_broke = p_broke or broke
			_player_attack = _empty(player.weave_size)
		else:
			e_broke = e_broke or broke
	if p_broke and e_broke:
		_finish("clash", true, true, "solved")
	elif p_broke:
		_finish("victory", true, false, "solved")
	elif e_broke:
		_finish("defeat", false, true, "solved")
	if result != null:
		return
	for item in batch:
		if item["attacker_id"] == "player":
			_player_window.finish_resolve()
		else:
			_enemy_window.finish_resolve()
			if _enemy_window.state != _CastWindow.State.EXHAUSTED:
				_open_enemy_window()
				if _fast_cast:
					_apply_fast_cast()
	_check_exhaustion()


func _resolve_one(item: Dictionary) -> bool:
	var who: String = item["attacker_id"]
	var pattern: Array = item["pattern"]
	var target := _enemy_ward if who == "player" else _player_ward
	var r := DmbFeedback.score_attack(target, pattern)
	var rec = _AttackRecord.new()
	rec.attacker_id = who
	rec.target_id = "enemy" if who == "player" else "player"
	rec.cast_time = duel_time
	rec.was_auto_cast = item["auto_cast"]
	rec.pattern_by_locus = pattern.duplicate()
	rec.fracture_count = int(r["fracture"])
	rec.echo_count = int(r["echo"])
	rec.fade_count = int(r["fade"])
	rec.broke_ward = bool(r["broken"])
	if who == "player":
		_player_casts += 1
		rec.attack_number = _player_casts
		player_history.append(rec)
	else:
		_enemy_casts += 1
		rec.attack_number = _enemy_casts
		enemy_history.append(rec)
		if not rec.broke_ward:
			_bot.register_feedback(pattern, rec.fracture_count, rec.echo_count)
	var d := rec.to_ui_dict()
	d["targets"] = r["targets"]
	_events.append(_DuelEvent.new(_DuelEvent.ATTACK_LAUNCHED, d))
	_events.append(_DuelEvent.new(_DuelEvent.FEEDBACK_REVEALED, d))
	if rec.broke_ward:
		_events.append(_DuelEvent.new(_DuelEvent.WARD_BROKEN, {"target": rec.target_id}))
	return rec.broke_ward


func _check_exhaustion() -> void:
	if result != null:
		return
	var p_out := _player_casts >= player.max_casts
	var e_out := _enemy_casts >= enemy.max_casts
	if p_out and e_out:
		_finish("stalemate", false, false, "both_exhausted")
	elif p_out:
		_finish("defeat", false, false, "exhausted")
	elif e_out:
		_finish("victory", false, false, "exhausted")


func _finish(outcome: String, ps: bool, es: bool, reason: String) -> void:
	if result != null:
		return
	phase = Phase.FINISHED
	var msg := ""
	match outcome:
		"victory":
			msg = "You broke %s's Ward." % enemy.display_name if ps else "%s's magic ran dry." % enemy.display_name
		"defeat":
			msg = "%s broke your Ward." % enemy.display_name if es else "You ran out of casts."
		"clash":
			msg = "Both Wards shatter at once."
		"stalemate":
			msg = "Neither Ward was broken."
	result = DmbGameResult.new(outcome, ps, es, _player_casts, _enemy_casts, msg, reason)
	_events.append(_DuelEvent.new(_DuelEvent.DUEL_FINISHED, {"outcome": outcome, "reason": reason}))


# --- Read model ----------------------------------------------------------------

func get_pending_events() -> Array:
	var c := _events.duplicate()
	_events.clear()
	return c


func get_current_state() -> Dictionary:
	return {
		"phase": phase,
		"duel_time": duel_time,
		"player_window_open": is_player_window_open(),
		"player_cast_ready": can_player_cast(),
		"player_attack_complete": is_player_attack_complete(),
		"player_time_until_cast": _player_window.time_until_cast_ready(),
		"player_time_until_auto": _player_window.time_until_auto_cast(),
		"player_window_elapsed": _player_window.elapsed,
		"player_min_cast": _player_window.min_cast_time,
		"player_max_cast": _player_window.max_cast_time,
		"enemy_time_until_cast": _enemy_window.time_until_cast_ready(),
		"enemy_time_until_auto": _enemy_window.time_until_auto_cast(),
		"enemy_cast_progress": enemy_cast_progress(),
		"player_attacks_used": _player_casts,
		"enemy_attacks_used": _enemy_casts,
		"player_attacks_remaining": maxi(0, player.max_casts - _player_casts),
		"enemy_attacks_remaining": maxi(0, enemy.max_casts - _enemy_casts),
		"max_attacks": player.max_casts,
		"enemy_max_attacks": enemy.max_casts,
		"player_last_stand": false,
		"enemy_last_stand": false,
		"outcome": result.outcome if result else "",
	}
