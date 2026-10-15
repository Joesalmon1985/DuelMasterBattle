extends RefCounted
class_name DmbNetDuelSim

## The retained Ward board (`game_board.gd`) drives any object with the DmbBattleSim surface. This one holds no rules:
## the host owns the duel (wizard_rts/net/pvp.py); this object sends the player's ward and casts and mirrors the host's
## view of the duel (phase, feedback, histories, result). The rival's ward is only ever what the host discloses.

const _AttackRecord = preload("res://sim/attack_record.gd")
const _DuelEvent = preload("res://sim/duel_event.gd")

enum Phase { WARD_SETUP, DUELING, FINISHED }

var phase: int = Phase.WARD_SETUP
var result: DmbGameResult = null
var player_history: Array = []
var enemy_history: Array = []
var duel_time: float = 0.0
var player: DmbCombatant
var enemy: DmbCombatant
var forced_defeat_by_cast: int = 0

var _sim  # HybridSimClient
var _view: Dictionary = {}
var _player_ward: Array = []
var _player_attack: Array = []
var _ward_locked := false
var _events: Array = []
var _paused := false
var _rival_cast_pending := true
var _your_cast_pending := true
var _cast_deadline_s: float = -1.0
var _last_error := ""
var duel_id := ""


func _init(sim, view: Dictionary) -> void:
	_sim = sim
	duel_id = str(view.get("duel_id", ""))
	apply_view(view)


## Called by the board once the combatants exist (from the view's `encounter`).
func attach(p_player: DmbCombatant, p_enemy: DmbCombatant) -> void:
	player = p_player
	enemy = p_enemy
	_player_ward = _empty(player.ward_size)
	_player_attack = _empty(player.weave_size)
	var w: Array = _view.get("your_ward", [])
	if not w.is_empty():
		_player_ward = w.duplicate()
		_ward_locked = true


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


func is_network() -> bool:
	return true


func last_error() -> String:
	return _last_error


# --- the host's view ------------------------------------------------------------

## Mirror a duel view from the host (delivered with every state poll or with a cast reply).
func apply_view(view: Dictionary) -> void:
	if view.is_empty():
		return
	_view = view
	var state := str(view.get("state", "setup"))
	_your_cast_pending = bool(view.get("your_cast_pending", false))
	_rival_cast_pending = bool(view.get("rival_cast_pending", false))
	var dl = view.get("cast_deadline_s")
	_cast_deadline_s = float(dl) if dl != null else -1.0
	var w: Array = view.get("your_ward", [])
	if not w.is_empty() and player != null:
		_player_ward = w.duplicate()
		_ward_locked = true
	_sync_history(player_history, view.get("your_history", []), "player", "enemy")
	_sync_history(enemy_history, view.get("rival_history", []), "enemy", "player")
	var new_phase := phase
	match state:
		"setup":
			new_phase = Phase.WARD_SETUP
		"active":
			new_phase = Phase.DUELING
		"finished":
			new_phase = Phase.FINISHED
	if new_phase == Phase.DUELING and phase == Phase.WARD_SETUP:
		_events.append(_DuelEvent.new(_DuelEvent.DUEL_STARTED, {}))
		if player != null:
			_player_attack = _empty(player.weave_size)
	phase = new_phase
	if phase == Phase.FINISHED and result == null and view.has("result"):
		var r: Dictionary = view["result"]
		var outcome := str(r.get("outcome", "stalemate"))
		var reason := str(r.get("reason", ""))
		var rival_name := str(view.get("rival", {}).get("name", "The rival"))
		var your_casts := int(r.get("your_casts", 0))
		var rival_casts := int(r.get("rival_casts", 0))
		var msg := ""
		match outcome:
			"victory":
				msg = "You broke %s's Ward." % rival_name if reason == "solved" else ("%s gave up." % rival_name if reason == "forfeit" else ("%s left the duel." % rival_name if reason == "disconnected" else "You won."))
			"defeat":
				msg = "%s broke your Ward." % rival_name if reason == "solved" else ("You gave up." if reason == "forfeit" else "You lost.")
			"clash":
				msg = "Both Wards shatter at once."
			_:
				msg = "Neither Ward was broken."
		result = DmbGameResult.new(outcome, outcome in ["victory", "clash"], outcome in ["defeat", "clash"], your_casts, rival_casts, msg, reason)
		_events.append(_DuelEvent.new(_DuelEvent.DUEL_FINISHED, {"outcome": outcome, "reason": reason}))


func _sync_history(target: Array, rows: Array, attacker: String, defender: String) -> void:
	while target.size() < rows.size():
		var h: Dictionary = rows[target.size()]
		var rec = _AttackRecord.new()
		rec.attacker_id = attacker
		rec.target_id = defender
		rec.cast_time = duel_time
		rec.was_auto_cast = bool(h.get("auto", false))
		rec.pattern_by_locus = Array(h.get("attack", [])).duplicate()
		rec.fracture_count = int(h.get("fracture", 0))
		rec.echo_count = int(h.get("echo", 0))
		rec.fade_count = int(h.get("fade", 0))
		rec.broke_ward = bool(h.get("broken", false))
		rec.attack_number = int(h.get("n", target.size() + 1))
		target.append(rec)
		var d: Dictionary = rec.to_ui_dict()
		_events.append(_DuelEvent.new(_DuelEvent.ATTACK_LAUNCHED, d))
		_events.append(_DuelEvent.new(_DuelEvent.FEEDBACK_REVEALED, d))
		if rec.broke_ward:
			_events.append(_DuelEvent.new(_DuelEvent.WARD_BROKEN, {"target": defender}))


# --- compatibility accessors (battle screen) --------------------------------------

func get_bot():
	return null


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
	return player.attack_pool.duplicate()


func player_ward_pool() -> Array:
	return player.ward_pool.duplicate()


func player_can_break_enemy() -> bool:
	return true


func enemy_can_break_player() -> bool:
	return true


# --- ward setup -----------------------------------------------------------------------

func can_lock_player_ward() -> bool:
	return phase == Phase.WARD_SETUP and not _ward_locked and _complete(_player_ward)


func set_player_ward_locus(i: int, spell: int) -> void:
	if phase != Phase.WARD_SETUP or _ward_locked or i < 0 or i >= player.ward_size:
		return
	if spell < 0:
		_player_ward[i] = null
	elif _in_pool(spell, player.ward_pool):
		_player_ward[i] = int(spell)


func clear_player_ward() -> void:
	if phase == Phase.WARD_SETUP and not _ward_locked:
		_player_ward = _empty(player.ward_size)


func randomise_player_ward() -> void:
	if phase == Phase.WARD_SETUP and not _ward_locked:
		for i in range(player.ward_size):
			_player_ward[i] = int(player.ward_pool[randi() % player.ward_pool.size()])


## Sends the ward to the host. The duel becomes active when the rival's ward is in too (the next view says so).
func lock_player_ward_and_start() -> void:
	if not can_lock_player_ward():
		return
	var reply: Dictionary = _sim.op({"op": "pvp_ward", "ward": _player_ward.duplicate()})
	if str(reply.get("status", "")) != "ok":
		_last_error = str(reply.get("reason", "rejected"))
		return
	_ward_locked = true
	apply_view(reply.get("duel", {}))


func ward_locked() -> bool:
	return _ward_locked


# --- player attack ----------------------------------------------------------------------

func set_player_attack_locus(i: int, spell: int) -> void:
	if phase != Phase.DUELING or i < 0 or i >= player.weave_size:
		return
	if spell < 0:
		_player_attack[i] = null
	elif _in_pool(spell, player.attack_pool):
		_player_attack[i] = int(spell)


func clear_player_attack() -> void:
	if phase == Phase.DUELING:
		_player_attack = _empty(player.weave_size)


func load_player_attack(pattern: Array) -> void:
	if phase != Phase.DUELING:
		return
	var out := _empty(player.weave_size)
	for i in range(mini(pattern.size(), player.weave_size)):
		if pattern[i] != null and _in_pool(int(pattern[i]), player.attack_pool):
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


## Only what the host disclosed: empty slots until the duel is over.
func get_enemy_ward() -> Array:
	var w: Array = _view.get("rival_ward", [])
	if w.is_empty():
		return _empty(enemy.ward_size if enemy != null else 0)
	return w.duplicate()


func is_player_window_open() -> bool:
	return phase == Phase.DUELING and _your_cast_pending and player_history.size() < player.max_casts


func can_player_cast() -> bool:
	return is_player_window_open() and is_player_attack_complete()


func player_cast_block_reason() -> String:
	if phase != Phase.DUELING:
		return ""
	if player_history.size() >= player.max_casts:
		return "No casts left"
	if not _your_cast_pending:
		return "Waiting for the rival's cast…"
	if not is_player_attack_complete():
		return "Fill all %d spells" % player.weave_size
	return ""


## Sends the cast to the host; the feedback in the reply is the authoritative fracture/echo/fade.
func submit_player_attack() -> bool:
	if not can_player_cast():
		return false
	var cast_seq := int(_view.get("cast_seq", player_history.size())) + 1
	var reply: Dictionary = _sim.op({"op": "pvp_cast", "attack": _player_attack.duplicate(), "cast_seq": cast_seq})
	if str(reply.get("status", "")) != "ok":
		_last_error = str(reply.get("reason", "rejected"))
		if _last_error == "already_cast_this_round":
			_your_cast_pending = false
		return false
	_player_attack = _empty(player.weave_size)
	apply_view(reply.get("duel", {}))
	return true


# --- testing hooks -----------------------------------------------------------------------

func set_testing_fast_cast(_on: bool) -> void:
	pass


func advance_time_for_test(s: float) -> void:
	advance_time(s, false)


func debug_set_enemy_ward(_w: Array) -> void:
	pass


func debug_set_enemy_cast_at(_s: float) -> void:
	pass


## Not authoritative: a forced defeat is a forfeit sent to the host; anything else is ignored.
func force_finish_for_test(outcome: String) -> void:
	if outcome == "defeat" and phase != Phase.FINISHED:
		var reply: Dictionary = _sim.op({"op": "pvp_forfeit"})
		apply_view(reply.get("duel", {}))


func forfeit() -> void:
	force_finish_for_test("defeat")


# --- time ----------------------------------------------------------------------------------

func advance_time(delta: float, paused: bool = false) -> void:
	if phase != Phase.DUELING or result != null or paused or _paused:
		return
	duel_time += delta
	if _cast_deadline_s >= 0.0:
		_cast_deadline_s = maxf(0.0, _cast_deadline_s - delta)


func enemy_cast_progress() -> float:
	if phase != Phase.DUELING:
		return 0.0
	return 0.0 if _rival_cast_pending else 1.0


# --- read model ----------------------------------------------------------------------------

func get_pending_events() -> Array:
	var c := _events.duplicate()
	_events.clear()
	return c


func get_current_state() -> Dictionary:
	var max_c := float(enemy.max_cast_seconds) if enemy != null else 60.0
	var until_auto := _cast_deadline_s if _cast_deadline_s >= 0.0 else max_c
	return {
		"phase": phase,
		"duel_time": duel_time,
		"player_window_open": is_player_window_open(),
		"player_cast_ready": can_player_cast(),
		"player_attack_complete": is_player_attack_complete(),
		"player_time_until_cast": 0.0,
		"player_time_until_auto": until_auto,
		"player_window_elapsed": max_c,
		"player_min_cast": 0.0,
		"player_max_cast": max_c,
		"enemy_time_until_cast": 0.0,
		"enemy_time_until_auto": until_auto,
		"enemy_cast_progress": enemy_cast_progress(),
		"player_attacks_used": player_history.size(),
		"enemy_attacks_used": enemy_history.size(),
		"player_attacks_remaining": maxi(0, (player.max_casts if player != null else 0) - player_history.size()),
		"enemy_attacks_remaining": maxi(0, (enemy.max_casts if enemy != null else 0) - enemy_history.size()),
		"max_attacks": player.max_casts if player != null else 0,
		"enemy_max_attacks": enemy.max_casts if enemy != null else 0,
		"player_last_stand": false,
		"enemy_last_stand": false,
		"outcome": result.outcome if result else "",
		"network": true,
		"your_cast_pending": _your_cast_pending,
		"rival_cast_pending": _rival_cast_pending,
		"rival_ward_locked": bool(_view.get("rival_ward_locked", false)),
	}


static func _in_pool(spell: int, pool: Array) -> bool:
	for v in pool:
		if v != null and int(v) == spell:
			return true
	return false
