class_name DmbRealtimeDuelSim
extends RefCounted

## Authoritative real-time duel between the player and the rival wizard.
##
## Both duelists run independent cast windows. The player must wait
## `min_cast` seconds before casting and is auto-cast at `max_cast`. The rival
## plans its next guess incrementally (never stalling a frame) and casts at a
## difficulty-driven moment inside its own window.
##
## Win rules (core duel):
##   * break the rival's ward (all loci exact)            → victory
##   * rival breaks yours                                  → defeat
##   * both break in the same instant                      → clash
##   * you run out of casts without breaking their ward    → defeat
##   * the rival runs out of casts first                   → victory
##   * both run out in the same instant                    → stalemate
## Last Stand (comeback window after a broken ward) is supported for rulesets
## that enable it; the core duel does not.

const _BotFactory = preload("res://sim/bot_factory.gd")
const _CastWindow = preload("res://sim/cast_window.gd")
const _AutoCast = preload("res://sim/auto_cast.gd")
const _DifficultyProfiles = preload("res://sim/difficulty_profiles.gd")
const _DuelEvent = preload("res://sim/duel_event.gd")
const _AttackRecord = preload("res://sim/attack_record.gd")

const BOT_THINK_BUDGET_MSEC := 3.0

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

var _player_window
var _enemy_window
var _enemy_cast_at: float = 0.0

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

var _paused: bool = false
var _testing_fast_cast_enabled: bool = false
var _bot_seed: int = 42


func _init(
	ruleset: DmbDuelRuleset = null,
	difficulty = null,
	bot_seed: int = 42
) -> void:
	_ruleset = ruleset if ruleset != null else DmbEncounters.default_encounter()
	_difficulty = difficulty if difficulty != null else _DifficultyProfiles.get_profile("medium")
	_rng = RandomNumberGenerator.new()
	_player_window = _CastWindow.new()
	_enemy_window = _CastWindow.new()
	reset(bot_seed)


func reset(bot_seed: int = -1) -> void:
	if bot_seed >= 0:
		_bot_seed = bot_seed
	_rng.seed = _bot_seed
	_bot = _BotFactory.make_bot(_ruleset, _difficulty, _bot_seed)
	phase = Phase.WARD_SETUP
	result = null
	player_history.clear()
	enemy_history.clear()
	duel_time = 0.0
	_events.clear()
	_player_ward = _empty_pattern()
	_enemy_ward = _empty_pattern()
	_player_attack = _empty_pattern()
	_enemy_cast_at = 0.0
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
	_paused = false
	_player_window.reset_times(_effective_min_cast(true), _effective_max_cast(true), _ruleset.effective_max_attacks())
	_enemy_window.reset_times(_effective_min_cast(false), _effective_max_cast(false), _ruleset.effective_max_attacks())


func get_ruleset() -> DmbDuelRuleset:
	return _ruleset


func get_difficulty():
	return _difficulty


func get_bot() -> RefCounted:
	return _bot


func set_paused(paused: bool) -> void:
	_paused = paused


func is_paused() -> bool:
	return _paused


func _empty_pattern() -> Array:
	var arr: Array = []
	for _i in range(_ruleset.slot_count):
		arr.append(null)
	return arr


static func _is_complete(pattern: Array) -> bool:
	for p in pattern:
		if p == null:
			return false
	return true


# --- Ward setup -----------------------------------------------------------

func can_lock_player_ward() -> bool:
	return phase == Phase.WARD_SETUP and _is_complete(_player_ward)


func set_player_ward_locus(index: int, essence: int) -> void:
	if phase != Phase.WARD_SETUP or index < 0 or index >= _ruleset.slot_count:
		return
	if essence < 0:
		_player_ward[index] = null
		return
	DmbCode.validate_colour_in_pool(essence, _ruleset.secret_magic_pool)
	_player_ward[index] = essence


func clear_player_ward() -> void:
	if phase == Phase.WARD_SETUP:
		_player_ward = _empty_pattern()


func randomise_player_ward() -> void:
	if phase != Phase.WARD_SETUP:
		return
	_player_ward = _AutoCast.random_pattern(
		_ruleset.slot_count, _ruleset.secret_magic_pool, _ruleset.allow_repeats, _rng
	)


func lock_player_ward_and_start() -> void:
	assert(can_lock_player_ward())
	_enemy_ward = _bot.generate_code() if _bot.has_method("generate_code") else _random_enemy_ward()
	_player_attack = _empty_pattern()
	_begin_duel()


func _random_enemy_ward() -> Array:
	return _AutoCast.random_pattern(
		_ruleset.slot_count, _ruleset.secret_magic_pool, _ruleset.allow_repeats, _rng
	)


func _begin_duel() -> void:
	phase = Phase.DUELING
	var max_attacks := _ruleset.effective_max_attacks()
	_player_window.reset_times(_effective_min_cast(true), _effective_max_cast(true), max_attacks)
	_enemy_window.reset_times(_effective_min_cast(false), _effective_max_cast(false), max_attacks)
	_player_window.open_window()
	_open_enemy_window()
	if _testing_fast_cast_enabled:
		_apply_fast_cast_to_windows()
	_events.append(_DuelEvent.new(_DuelEvent.DUEL_STARTED, {}))


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


# --- Player attack building -----------------------------------------------

func set_player_attack_locus(index: int, essence: int) -> void:
	if phase != Phase.DUELING or index < 0 or index >= _ruleset.slot_count:
		return
	if essence < 0:
		_player_attack[index] = null
		return
	DmbCode.validate_colour_in_pool(essence, _ruleset.attack_magic_pool)
	_player_attack[index] = essence


func clear_player_attack() -> void:
	if phase == Phase.DUELING:
		_player_attack = _empty_pattern()


## Copy a previous cast back into the attack builder so it can be tweaked.
func load_player_attack(pattern: Array) -> void:
	if phase != Phase.DUELING:
		return
	var out := _empty_pattern()
	for i in range(mini(pattern.size(), _ruleset.slot_count)):
		if pattern[i] != null:
			out[i] = int(pattern[i])
	_player_attack = out


func get_player_attack_pattern() -> Array:
	return _player_attack.duplicate()


func is_player_attack_complete() -> bool:
	return _is_complete(_player_attack)


func first_empty_attack_locus() -> int:
	for i in range(_player_attack.size()):
		if _player_attack[i] == null:
			return i
	return -1


func get_player_ward() -> Array:
	return _player_ward.duplicate()


func get_enemy_ward() -> Array:
	return _enemy_ward.duplicate()


## Window is open (min time passed) and casts remain. Does not check the guess.
func is_player_window_open() -> bool:
	return phase == Phase.DUELING and _player_window.can_cast() and not _player_cast_blocked()


## Everything needed to cast right now: open window and a complete guess.
func can_player_cast() -> bool:
	return is_player_window_open() and is_player_attack_complete()


## Human-readable reason the cast button is unavailable ("" when castable).
func player_cast_block_reason() -> String:
	if phase != Phase.DUELING:
		return ""
	if _player_cast_blocked():
		return "No casts left"
	if _player_window.state == _CastWindow.State.LOCKED:
		return "Weaving…"
	if not is_player_attack_complete():
		return "Fill all %d spells" % _ruleset.slot_count
	return ""


func _player_cast_blocked() -> bool:
	return _player_attacks_used >= _ruleset.effective_max_attacks() and not _player_last_stand_active


func submit_player_attack() -> bool:
	if not can_player_cast():
		return false
	_resolve_attacks([_make_attack("player", _player_attack.duplicate(), false)])
	return true


# --- Testing hooks ----------------------------------------------------------

func set_testing_fast_cast(enabled: bool) -> void:
	_testing_fast_cast_enabled = enabled
	if enabled:
		_apply_fast_cast_to_windows()


func _apply_fast_cast_to_windows() -> void:
	_player_window.min_cast_time = 0.0
	_enemy_window.min_cast_time = 0.0
	if _player_window.state == _CastWindow.State.LOCKED:
		_player_window.state = _CastWindow.State.READY
	if _enemy_window.state == _CastWindow.State.LOCKED:
		_enemy_window.state = _CastWindow.State.READY


func advance_time_for_test(seconds: float) -> void:
	advance_time(seconds, false)


## Force the rival's ward (tests / scripted scenarios). Only valid once dueling.
func debug_set_enemy_ward(ward: Array) -> void:
	_enemy_ward = ward.duplicate()


func debug_set_enemy_cast_at(seconds: float) -> void:
	_enemy_cast_at = seconds


# --- Time -------------------------------------------------------------------

func advance_time(delta_seconds: float, paused: bool = false) -> void:
	if phase != Phase.DUELING or result != null:
		return
	if paused or _paused:
		return
	duel_time += delta_seconds
	_tick_last_stand_timers(delta_seconds)
	if result != null:
		return
	_player_window.advance(delta_seconds)
	_enemy_window.advance(delta_seconds)
	_think_enemy()
	var pending: Array = []
	if _player_window.should_auto_cast():
		pending.append(_make_attack("player", _AutoCast.fill_pattern(
			_player_attack, _ruleset.slot_count, _ruleset.attack_magic_pool,
			_ruleset.allow_repeats, _rng
		), true))
	if _enemy_should_cast():
		pending.append(_make_attack("enemy", _bot_guess(), _enemy_window.should_auto_cast()))
	if not pending.is_empty():
		_resolve_attacks(pending)


func _tick_last_stand_timers(delta: float) -> void:
	if _player_last_stand_active and _ruleset.last_stand_seconds > 0:
		_player_last_stand_timer -= delta
		if _player_last_stand_timer <= 0 and _player_last_stand_attacks_left <= 0:
			_finish_duel("defeat", false, true, "last_stand_expired")
	if _enemy_last_stand_active and _ruleset.last_stand_seconds > 0:
		_enemy_last_stand_timer -= delta
		if _enemy_last_stand_timer <= 0 and _enemy_last_stand_attacks_left <= 0:
			_finish_duel("victory", true, false, "last_stand_expired")


# --- Rival ------------------------------------------------------------------

func _open_enemy_window() -> void:
	_enemy_window.open_window()
	if _enemy_window.state == _CastWindow.State.EXHAUSTED:
		return
	var lo := maxf(_enemy_window.min_cast_time, float(_difficulty.bot_think_min_seconds))
	var hi := minf(_enemy_window.max_cast_time - 0.5, float(_difficulty.bot_think_max_seconds))
	hi = maxf(lo, hi)
	_enemy_cast_at = _rng.randf_range(lo, hi)
	if _bot.has_method("begin_planning"):
		_bot.begin_planning()


func _think_enemy() -> void:
	if _enemy_window.state == _CastWindow.State.EXHAUSTED:
		return
	if _bot.has_method("think"):
		_bot.think(BOT_THINK_BUDGET_MSEC)


func _enemy_should_cast() -> bool:
	if _enemy_window.state == _CastWindow.State.EXHAUSTED:
		return false
	if _enemy_window.should_auto_cast():
		return true
	if not _enemy_window.can_cast():
		return false
	if _enemy_window.elapsed < _enemy_cast_at:
		return false
	if _bot.has_method("is_plan_ready") and not _bot.is_plan_ready():
		return false
	return true


func _bot_guess() -> Array:
	if _bot.has_method("planned_guess"):
		return _bot.planned_guess()
	if _bot.has_method("make_guess"):
		return _bot.make_guess()
	return _AutoCast.random_pattern(
		_ruleset.slot_count, _ruleset.attack_magic_pool, _ruleset.allow_repeats, _rng
	)


## 0..1 progress of the rival towards its next cast — for the UI only.
func enemy_cast_progress() -> float:
	if phase != Phase.DUELING or _enemy_window.state == _CastWindow.State.EXHAUSTED:
		return 0.0
	return clampf(_enemy_window.elapsed / maxf(_enemy_cast_at, 0.1), 0.0, 1.0)


# --- Resolution -------------------------------------------------------------

func _make_attack(attacker_id: String, pattern: Array, auto_cast: bool) -> Dictionary:
	return {"attacker_id": attacker_id, "pattern": pattern, "auto_cast": auto_cast}


func _resolve_attacks(batch: Array) -> void:
	# Player first so a same-frame clash still lists the player's cast first.
	batch.sort_custom(func(a, b): return a["attacker_id"] == "player" and b["attacker_id"] != "player")
	var player_broke := false
	var enemy_broke := false
	for item in batch:
		var w = _player_window if item["attacker_id"] == "player" else _enemy_window
		if w.state == _CastWindow.State.EXHAUSTED and not _is_in_last_stand(item["attacker_id"]):
			continue
		w.begin_resolve(duel_time)
		var broke := _resolve_single_attack(item)
		if item["attacker_id"] == "player":
			player_broke = player_broke or broke
			_player_attack = _empty_pattern()
		else:
			enemy_broke = enemy_broke or broke
	if player_broke and enemy_broke:
		_finish_duel("clash", true, true, "solved")
	elif player_broke:
		_on_ward_broken("enemy")
	elif enemy_broke:
		_on_ward_broken("player")
	if result != null:
		return
	for item in batch:
		if item["attacker_id"] == "player":
			_player_window.finish_resolve()
		else:
			_enemy_window.finish_resolve()
			_open_enemy_window_if_needed()
	_check_exhaustion()


func _open_enemy_window_if_needed() -> void:
	# finish_resolve reopened the window; re-roll cast timing + start planning.
	if _enemy_window.state == _CastWindow.State.LOCKED or _enemy_window.state == _CastWindow.State.READY:
		_open_enemy_window()
		if _testing_fast_cast_enabled:
			_apply_fast_cast_to_windows()


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
	rec.cast_time = duel_time
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
		if _player_last_stand_active:
			_player_last_stand_attacks_left = maxi(0, _player_last_stand_attacks_left - 1)
	else:
		_enemy_attacks_used += 1
		rec.attack_number = _enemy_attacks_used
		enemy_history.append(rec)
		if _bot.has_method("register_feedback") and not broke:
			_bot.register_feedback(pattern, fractures, echoes)
		if _enemy_last_stand_active:
			_enemy_last_stand_attacks_left = maxi(0, _enemy_last_stand_attacks_left - 1)
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
			_finish_duel("clash", true, true, "solved")
			return
		if _enemy_has_last_stand():
			_enemy_last_stand_active = true
			_enemy_last_stand_attacks_left = maxi(1, _ruleset.last_stand_min_attacks)
			_enemy_last_stand_timer = _effective_last_stand_seconds(false)
			_events.append(_DuelEvent.new(_DuelEvent.LAST_STAND_STARTED, {"target": "enemy"}))
		else:
			_finish_duel("victory", true, false, "solved")
	else:
		_player_ward_broken = true
		if _player_last_stand_active:
			_finish_duel("clash", true, true, "solved")
			return
		if _player_has_last_stand():
			_player_last_stand_active = true
			_player_last_stand_attacks_left = maxi(1, _ruleset.last_stand_min_attacks)
			_player_last_stand_timer = _effective_last_stand_seconds(true)
			_events.append(_DuelEvent.new(_DuelEvent.LAST_STAND_STARTED, {"target": "player"}))
		else:
			_finish_duel("defeat", false, true, "solved")


func _is_in_last_stand(attacker_id: String) -> bool:
	return _player_last_stand_active if attacker_id == "player" else _enemy_last_stand_active


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


func _check_exhaustion() -> void:
	if result != null:
		return
	var max_a := _ruleset.effective_max_attacks()
	var player_out := _player_attacks_used >= max_a and not _player_ward_broken and not _player_last_stand_active
	var enemy_out := _enemy_attacks_used >= max_a and not _enemy_ward_broken and not _enemy_last_stand_active
	if _player_last_stand_active or _enemy_last_stand_active:
		return
	if player_out and enemy_out:
		_finish_duel("stalemate", false, false, "both_exhausted")
	elif player_out:
		_finish_duel("defeat", false, false, "exhausted")
	elif enemy_out:
		_finish_duel("victory", false, false, "exhausted")


func _finish_duel(outcome: String, player_solved: bool, enemy_solved: bool, reason: String = "") -> void:
	if result != null:
		return
	phase = Phase.FINISHED
	var msg := ""
	match outcome:
		"victory":
			msg = "You broke the rival's ward." if player_solved else "The rival's magic ran dry."
		"defeat":
			msg = "The rival broke your ward." if enemy_solved else "You ran out of casts."
		"clash":
			msg = "Both wards shatter at once."
		"stalemate":
			msg = "Neither ward was broken."
	result = DmbGameResult.new(
		outcome, player_solved, enemy_solved,
		_player_attacks_used, _enemy_attacks_used, msg, reason
	)
	_events.append(_DuelEvent.new(_DuelEvent.DUEL_FINISHED, {"outcome": outcome, "reason": reason}))


func force_finish_for_test(outcome: String) -> void:
	if result != null:
		return
	if phase == Phase.WARD_SETUP:
		phase = Phase.DUELING
	match outcome:
		"victory":
			_finish_duel("victory", true, false, "forced")
		"defeat":
			_finish_duel("defeat", false, true, "forced")
		"clash":
			_finish_duel("clash", true, true, "forced")
		_:
			_finish_duel("stalemate", false, false, "forced")


# --- Read model -----------------------------------------------------------

func get_pending_events() -> Array:
	var copy := _events.duplicate()
	_events.clear()
	return copy


func get_current_state() -> Dictionary:
	var max_a := _ruleset.effective_max_attacks()
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
		"player_attacks_used": _player_attacks_used,
		"enemy_attacks_used": _enemy_attacks_used,
		"player_attacks_remaining": maxi(0, max_a - _player_attacks_used),
		"enemy_attacks_remaining": maxi(0, max_a - _enemy_attacks_used),
		"max_attacks": max_a,
		"player_last_stand": _player_last_stand_active,
		"enemy_last_stand": _enemy_last_stand_active,
		"outcome": result.outcome if result else "",
	}
