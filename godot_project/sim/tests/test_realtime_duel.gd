extends DmbTestCase

const _RealtimeSim = preload("res://sim/realtime_duel_sim.gd")
const _Encounters = preload("res://sim/encounters.gd")
const _DifficultyProfiles = preload("res://sim/difficulty_profiles.gd")


func run() -> void:
	_test_min_cast_blocks_player()
	_test_auto_cast_at_max()
	_test_feedback_aggregate_only()
	_test_eight_locus_ruleset()
	_test_pause_does_not_advance()


func _make_sim(encounter_id: String = "blue_apprentice"):
	var rs := _Encounters.get_encounter(encounter_id)
	var diff = _DifficultyProfiles.get_profile("medium")
	var sim = _RealtimeSim.new(rs, diff, 42)
	sim.set_testing_fast_cast(false)
	return sim


func _fill_ward(sim) -> void:
	for i in range(sim.get_ruleset().slot_count):
		sim.set_player_ward_locus(i, sim.get_ruleset().secret_magic_pool[0])
	sim.lock_player_ward_and_start()


func _test_min_cast_blocks_player() -> void:
	var sim = _make_sim()
	for i in range(sim.get_ruleset().slot_count):
		sim.set_player_ward_locus(i, 0)
	sim.lock_player_ward_and_start()
	assert_true(not sim.can_player_cast(), "cannot cast before min time")
	sim.advance_time_for_test(0.1)
	assert_true(not sim.can_player_cast(), "still blocked under min cast")
	sim.advance_time_for_test(10.0)
	assert_true(sim.can_player_cast(), "cast opens after min time")


func _test_auto_cast_at_max() -> void:
	var sim = _make_sim("thorn_adept")
	_fill_ward(sim)
	var max_t: float = sim.get_ruleset().base_max_cast_time_seconds + 1.0
	sim.advance_time_for_test(max_t)
	assert_true(sim.player_history.size() >= 1 or sim.enemy_history.size() >= 1, "auto cast fires")


func _test_feedback_aggregate_only() -> void:
	var sim = _make_sim()
	_fill_ward(sim)
	sim.set_testing_fast_cast(true)
	for i in range(sim.get_ruleset().slot_count):
		sim.set_player_attack_locus(i, 0)
	sim.submit_player_attack()
	var events: Array = sim.get_pending_events()
	for ev in events:
		if ev.type == "feedback_revealed":
			var d: Dictionary = ev.data
			assert_true(d.has("fracture_count"), "has fracture_count")
			assert_true(d.has("echo_count"), "has echo_count")
			assert_true(d.has("fade_count"), "has fade_count")
			assert_true(not d.has("per_locus"), "no per-locus leak key")


func _test_eight_locus_ruleset() -> void:
	var rs := _Encounters.get_encounter("eightfold_warden")
	assert_eq(rs.slot_count, 8, "eightfold has 8 loci")
	assert_eq(rs.point_names.size(), 8, "eight locus names")


func _test_pause_does_not_advance() -> void:
	var sim = _make_sim()
	_fill_ward(sim)
	var t0: float = sim.duel_time
	sim.set_paused(true)
	sim.advance_time(2.0, true)
	assert_eq(sim.duel_time, t0, "paused time frozen")
