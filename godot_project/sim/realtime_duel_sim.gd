class_name DmbRealtimeDuelSim
extends RefCounted

const _BotFactory = preload("res://sim/bot_factory.gd")
const _CastWindow = preload("res://sim/cast_window.gd")
const _AutoCast = preload("res://sim/auto_cast.gd")
const _DifficultyProfiles = preload("res://sim/difficulty_profiles.gd")
const _DuelEvent = preload("res://sim/duel_event.gd")
const _AttackRecord = preload("res://sim/attack_record.gd")

enum Phase { WARD_SETUP, DUELING, FINISHED }

var phase: int = Phase.WARD_SETUP
var result: DmbGameResult = null
var player_history: Array = []
var enemy_history: Array = []
var duel_time: float = 0.0

var _ruleset: DmbDuelRuleset
var _difficulty
var _bot: RefCounted
var _rng: RandomNumberGenerator
var _events: Array = []

var _player_ward: Array = []
var _enemy_ward: Array = []
var _player_attack: Array = []
var _enemy_attack: Array = []

var _player_window
var _enemy_window

var _player_attacks_used: int = 0
var _enemy_attacks_used: int = 0
var _player_ward_broken: bool = false
var _enemy_ward_broken: bool = false
var _player_last_stand_active: bool = false
var _enemy_last_stand_active: bool = false
var _player_last_stand_timer: float = 0.0
var _enemy_last_stand_timer: float = 0.0
var _player_last_stand_attacks_left: int = 0
var _enemy_last_stand_attacks_left: int = 0

var _resolution_queue: Array = []
var _resolving: bool = false
var _paused: bool = false
var _testing_fast_cast_enabled: bool = false


func _init(
	ruleset: DmbDuelRuleset = null,
	difficulty = null,
	bot_seed: int = 42
) -> void:
	_ruleset = ruleset if ruleset != null else DmbEncounters.default_encounter()
	_difficulty = difficulty if difficulty != null else _DifficultyProfiles.get_profile("medium")
	_rng = RandomNumberGenerator.new()
	_rng.seed = bot_seed
	_player_window = _CastWindow.new()
	_enemy_window = _CastWindow.new()
	reset(bot_seed)


func reset(bot_seed: int = -1) -> void:
	if bot_seed >= 0:
		_rng.seed = bot_seed
	_bot = _BotFactory.make_bot(_ruleset, _difficulty, int(_rng.seed))
	phase = Phase.WARD_SETUP
	result = null
	player_history.clear()
	enemy_history.clear()
	duel_time = 0.0
	_events.clear()
	_player_ward = _empty_pattern()
	_enemy_ward = _empty_pattern()
	_player_attack = _empty_pattern()
	_enemy_attack = _empty_pattern()
	_player_attacks_used = 0
	_enemy_attacks_used = 0
	_player_ward_broken = false
	_enemy_ward_broken = false
	_player_last_stand_active = false
	_enemy_last_stand_active = false
	_player_last_stand_timer = 0.0
	_enemy_last_stand_timer = 0.0
	_player_last_stand_attacks_left = 0
	_enemy_last_stand_attacks_left = 0
	_resolution_queue.clear()
	_resolving = false
	_paused = false


func get_ruleset() -> DmbDuelRuleset:
	return _ruleset


func get_difficulty():
	return _difficulty


func set_paused(paused: bool) -> void:
	_paused = paused


func _empty_pattern() -> Array:
	var arr: Array = []
	for _i in range(_ruleset.slot_count):
		arr.append(null)
	return arr


func can_lock_player_ward() -> bool:
	if phase != Phase.WARD_SETUP:
		return false
	for p in _player_ward:
		if p == null:
			return false
	return true


func set_player_ward_locus(index: int, essence: int) -> void:
	assert(phase == Phase.WARD_SETUP)
	if essence < 0:
		_player_ward[index] = null
		return
	DmbCode.validate_colour_in_pool(essence, _ruleset.secret_magic_pool)
	_player_ward[index] = essence


func lock_player_ward_and_start() -> void:
	assert(can_lock_player_ward())
	_enemy_ward = _bot.generate_code() if _bot.has_method("generate_code") else _random_enemy_ward()
	_player_attack = _empty_pattern()
	_enemy_attack = _empty_pattern()
	_begin_duel()


func _random_enemy_ward() -> Array:
	return _AutoCast.random_pattern(
		_ruleset.slot_count, _ruleset.secret_magic_pool, _ruleset.allow_repeats, _rng
	)


func _begin_duel() -> void:
	phase = Phase.DUELING
	var max_attacks := _ruleset.effective_max_attacks()
	var p_min := _effective_min_cast(true)
	var p_max := _effective_max_cast(true)
	var e_min := _effective_min_cast(false)
	var e_max := _effective_max_cast(false)
	_player_window.reset_times(p_min, p_max, max_attacks)
	_enemy_window.reset_times(e_min, e_max, max_attacks)
	_player_window.open_window()
	_enemy_window.open_window()
	if _testing_fast_cast_enabled:
		_apply_fast_cast_to_windows()
	_prepare_enemy_pattern()


func _effective_min_cast(for_player: bool) -> float:
	var base := _ruleset.base_min_cast_time_seconds
	if not for_player:
		base *= _difficulty.bot_min_cast_time_multiplier
	var traits := _ruleset.player_traits if for_player else _ruleset.enemy_traits
	base += float(traits.get("own_min_cast_time_modifier", 0.0))
	if for_player:
		base += float(_ruleset.enemy_traits.get("opponent_min_cast_time_modifier", 0.0))
	else:
		base += float(_ruleset.player_traits.get("opponent_min_cast_time_modifier", 0.0))
	return maxf(0.5, base)


func _effective_max_cast(for_player: bool) -> float:
	var base := _ruleset.base_max_cast_time_seconds
	if not for_player:
		base *= _difficulty.bot_max_cast_time_multiplier
	if for_player:
		base += float(_ruleset.enemy_traits.get("opponent_max_cast_time_modifier", 0.0))
	else:
		base += float(_ruleset.player_traits.get("opponent_max_cast_time_modifier", 0.0))
	return maxf(_effective_min_cast(for_player) + 0.5, base)


func set_player_attack_locus(index: int, essence: int) -> void:
	if phase != Phase.DUELING or _resolving:
		return
	if essence < 0:
		_player_attack[index] = null
		return
	DmbCode.validate_colour_in_pool(essence, _ruleset.attack_magic_pool)
	_player_attack[index] = essence


func get_player_attack_pattern() -> Array:
	return _player_attack.duplicate()


func get_player_ward() -> Array:
	return _player_ward.duplicate()


func can_player_cast() -> bool:
	return (
		phase == Phase.DUELING
		and not _resolving
		and _player_window.can_cast()
		and not _player_cast_blocked()
	)


func _player_cast_blocked() -> bool:
	return _player_attacks_used >= _ruleset.effective_max_attacks() and not _player_last_stand_active


func submit_player_attack() -> bool:
	if not can_player_cast():
		return false
	return _queue_attack("player", _player_attack.duplicate(), false)


func set_testing_fast_cast(enabled: bool) -> void:
	_testing_fast_cast_enabled = enabled
	if enabled:
		_apply_fast_cast_to_windows()


func _apply_fast_cast_to_windows() -> void:
	_player_window.min_cast_time = 0.0
	_enemy_window.min_cast_time = 0.0
	_player_window.state = _CastWindow.State.READY
	_enemy_window.state = _CastWindow.State.READY


func advance_time_for_test(seconds: float) -> void:
	advance_time(seconds, false)


func advance_time(delta_seconds: float, paused: bool = false) -> void:
	if phase != Phase.DUELING or result != null:
		return
	if paused or _paused:
		return
	duel_time += delta_seconds
	_tick_last_stand_timers(delta_seconds)
	if not _resolving:
		_player_window.advance(delta_seconds)
		_enemy_window.advance(delta_seconds)
		_prepare_enemy_pattern()
		_try_auto_cast(_player_window, "player", true)
		_try_auto_cast(_enemy_window, "enemy", false)
	_process_resolution_queue()


func _tick_last_stand_timers(delta: float) -> void:
	if _player_last_stand_active and _ruleset.last_stand_seconds > 0:
		_player_last_stand_timer -= delta
		if _player_last_stand_timer <= 0 and _player_last_stand_attacks_left <= 0:
			_finish_duel("defeat", false, true)
	if _enemy_last_stand_active and _ruleset.last_stand_seconds > 0:
		_enemy_last_stand_timer -= delta
		if _enemy_last_stand_timer <= 0 and _enemy_last_stand_attacks_left <= 0:
			_finish_duel("victory", true, false)


func _prepare_enemy_pattern() -> void:
	if _enemy_window.state == _CastWindow.State.RESOLVING:
		return
	if _enemy_window.state == _CastWindow.State.EXHAUSTED:
		return
	if _bot.has_method("make_guess"):
		_enemy_attack = _bot.make_guess()


func _try_auto_cast(window, attacker_id: String, is_player: bool) -> void:
	if not window.should_auto_cast():
		return
	var pattern: Array
	if is_player:
		pattern = _AutoCast.fill_pattern(
			_player_attack, _ruleset.slot_count, _ruleset.attack_magic_pool,
			_ruleset.allow_repeats, _rng
		)
	else:
		if _bot.has_method("make_guess"):
			pattern = _bot.make_guess()
		else:
			pattern = _AutoCast.random_pattern(
				_ruleset.slot_count, _ruleset.attack_magic_pool, _ruleset.allow_repeats, _rng
			)
	_queue_attack(attacker_id, pattern, true)


func _queue_attack(attacker_id: String, pattern: Array, auto_cast: bool) -> bool:
	var window = _player_window if attacker_id == "player" else _enemy_window
	if window.state == _CastWindow.State.EXHAUSTED and not _is_in_last_stand(attacker_id):
		return false
	if not auto_cast and not window.can_cast():
		return false
	var ts := duel_time
	window.begin_resolve(ts)
	_resolution_queue.append({
		"attacker_id": attacker_id,
		"pattern": pattern,
		"auto_cast": auto_cast,
		"timestamp": ts,
	})
	_events.append(_DuelEvent.new(_DuelEvent.CAST_STARTED, {"attacker_id": attacker_id}))
	_resolving = true
	_process_resolution_queue()
	return true


func _is_in_last_stand(attacker_id: String) -> bool:
	if attacker_id == "player":
		return _player_last_stand_active
	return _enemy_last_stand_active


func _process_resolution_queue() -> void:
	if _resolution_queue.is_empty():
		_resolving = false
		return
	_resolution_queue.sort_custom(func(a, b): return a["timestamp"] < b["timestamp"] or (
		a["timestamp"] == b["timestamp"] and a["attacker_id"] == "player"
	))
	var batch: Array = []
	var frame_ts: float = _resolution_queue[0]["timestamp"]
	for item in _resolution_queue:
		if absf(item["timestamp"] - frame_ts) < 0.001:
			batch.append(item)
		else:
			break
	var player_broke := false
	var enemy_broke := false
	for item in batch:
		var broke := _resolve_single_attack(item)
		if item["attacker_id"] == "player" and broke:
			player_broke = true
		elif item["attacker_id"] == "enemy" and broke:
			enemy_broke = true
	for _i in range(batch.size()):
		_resolution_queue.pop_front()
	if player_broke and enemy_broke:
		_finish_duel("clash", true, true)
	elif player_broke:
		_on_ward_broken("enemy")
	elif enemy_broke:
		_on_ward_broken("player")
	if result == null:
		_finish_windows_after_batch(batch)
		_check_stalemate()
	_resolving = _resolution_queue.size() > 0


func _resolve_single_attack(item: Dictionary) -> bool:
	var attacker: String = item["attacker_id"]
	var pattern: Array = item["pattern"]
	var target_secret := _enemy_ward if attacker == "player" else _player_ward
	var fb := DmbFeedback.score_guess(target_secret, pattern)
	var fractures := fb.x
	var echoes := fb.y
	var fades := _ruleset.slot_count - fractures - echoes
	var broke := fractures == _ruleset.slot_count
	var rec = _AttackRecord.new()
	rec.attacker_id = attacker
	rec.target_id = "enemy" if attacker == "player" else "player"
	rec.cast_time = item["timestamp"]
	rec.was_auto_cast = item["auto_cast"]
	rec.pattern_by_locus = pattern.duplicate()
	rec.fracture_count = fractures
	rec.echo_count = echoes
	rec.fade_count = fades
	rec.broke_ward = broke
	if attacker == "player":
		_player_attacks_used += 1
		rec.attack_number = _player_attacks_used
		player_history.append(rec)
		if _bot.has_method("register_feedback"):
			_bot.register_feedback(pattern, fractures, echoes)
	else:
		_enemy_attacks_used += 1
		rec.attack_number = _enemy_attacks_used
		enemy_history.append(rec)
	_events.append(_DuelEvent.new(_DuelEvent.ATTACK_LAUNCHED, rec.to_ui_dict()))
	_events.append(_DuelEvent.new(_DuelEvent.FEEDBACK_REVEALED, rec.to_ui_dict()))
	if broke:
		_events.append(_DuelEvent.new(_DuelEvent.WARD_BROKEN, {"target": rec.target_id}))
	return broke


func _on_ward_broken(target: String) -> void:
	if result != null:
		return
	if target == "enemy":
		_enemy_ward_broken = true
		if _enemy_last_stand_active:
			_finish_duel("clash", true, true)
			return
		if _enemy_has_last_stand():
			_enemy_last_stand_active = true
			_enemy_last_stand_attacks_left = maxi(1, _ruleset.last_stand_min_attacks)
			_enemy_last_stand_timer = _effective_last_stand_seconds(false)
			_events.append(_DuelEvent.new(_DuelEvent.LAST_STAND_STARTED, {"target": "enemy"}))
		else:
			_finish_duel("victory", true, false)
	else:
		_player_ward_broken = true
		if _player_last_stand_active:
			_finish_duel("clash", true, true)
			return
		if _player_has_last_stand():
			_player_last_stand_active = true
			_player_last_stand_attacks_left = maxi(1, _ruleset.last_stand_min_attacks)
			_player_last_stand_timer = _effective_last_stand_seconds(true)
			_events.append(_DuelEvent.new(_DuelEvent.LAST_STAND_STARTED, {"target": "player"}))
		else:
			_finish_duel("defeat", false, true)


func _enemy_has_last_stand() -> bool:
	return _ruleset.last_stand_min_attacks > 0 or _ruleset.last_stand_seconds > 0


func _player_has_last_stand() -> bool:
	if _ruleset.enemy_traits.get("blocks_opponent_last_stand_min_attacks", false):
		return _ruleset.last_stand_seconds > 0
	return _ruleset.last_stand_min_attacks > 0 or _ruleset.last_stand_seconds > 0


func _effective_last_stand_seconds(for_player: bool) -> float:
	var base := _ruleset.last_stand_seconds
	if for_player:
		base += float(_ruleset.enemy_traits.get("opponent_last_stand_seconds_modifier", 0.0))
	else:
		base += float(_ruleset.player_traits.get("opponent_last_stand_seconds_modifier", 0.0))
	return maxf(0.0, base)


func _finish_windows_after_batch(batch: Array) -> void:
	for item in batch:
		var w = _player_window if item["attacker_id"] == "player" else _enemy_window
		w.finish_resolve()
		if item["attacker_id"] == "player":
			_player_attack = _empty_pattern()
		else:
			_enemy_attack = _empty_pattern()


func _check_stalemate() -> void:
	var max_a := _ruleset.effective_max_attacks()
	if (
		_player_attacks_used >= max_a
		and _enemy_attacks_used >= max_a
		and not _player_ward_broken
		and not _enemy_ward_broken
	):
		_finish_duel("stalemate", false, false)


func _finish_duel(outcome: String, player_solved: bool, enemy_solved: bool) -> void:
	if result != null:
		return
	phase = Phase.FINISHED
	var msg := ""
	match outcome:
		"victory":
			msg = "Victory — the rival's ward collapses."
		"defeat":
			msg = "Defeat — your ward collapses."
		"clash":
			msg = "Clash — both wards shatter at once."
		"stalemate":
			msg = "Stalemate — neither ward was broken."
	result = DmbGameResult.new(
		outcome, player_solved, enemy_solved,
		_player_attacks_used, _enemy_attacks_used, msg
	)
	_events.append(_DuelEvent.new(_DuelEvent.DUEL_FINISHED, {"outcome": outcome}))


func force_finish_for_test(outcome: String) -> void:
	if result != null:
		return
	phase = Phase.DUELING if phase == Phase.WARD_SETUP else phase
	match outcome:
		"victory":
			_finish_duel("victory", true, false)
		"defeat":
			_finish_duel("defeat", false, true)
		"clash":
			_finish_duel("clash", true, true)
		_:
			_finish_duel("stalemate", false, false)


func get_pending_events() -> Array:
	var copy := _events.duplicate()
	_events.clear()
	return copy


func get_current_state() -> Dictionary:
	return {
		"phase": phase,
		"duel_time": duel_time,
		"player_cast_ready": _player_window.can_cast(),
		"player_time_until_cast": _player_window.time_until_cast_ready(),
		"player_time_until_auto": _player_window.time_until_auto_cast(),
		"enemy_time_until_cast": _enemy_window.time_until_cast_ready(),
		"enemy_time_until_auto": _enemy_window.time_until_auto_cast(),
		"player_attacks_remaining": maxi(0, _ruleset.effective_max_attacks() - _player_attacks_used),
		"enemy_attacks_remaining": maxi(0, _ruleset.effective_max_attacks() - _enemy_attacks_used),
		"player_last_stand": _player_last_stand_active,
		"enemy_last_stand": _enemy_last_stand_active,
		"outcome": result.outcome if result else "",
	}
