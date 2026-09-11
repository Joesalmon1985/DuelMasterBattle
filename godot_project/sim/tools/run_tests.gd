extends SceneTree

const TESTS := [
	"res://sim/tests/test_code.gd",
	"res://sim/tests/test_feedback.gd",
	"res://sim/tests/test_encounters.gd",
	"res://sim/tests/test_fixtures.gd",
	"res://sim/tests/test_game_state.gd",
	"res://sim/tests/test_realtime_duel.gd",
	"res://sim/tests/test_core_duel.gd",
	"res://sim/tests/test_asymmetric_battle.gd",
	"res://sim/tests/test_solver_bot.gd",
	"res://sim/tests/test_assets.gd",
	"res://sim/tests/test_dd_canon.gd",
	"res://sim/tests/test_trial_run.gd",
	"res://sim/tests/test_story_phase.gd",
	"res://sim/tests/test_early_solver.gd",
	"res://sim/tests/test_hex_board.gd",
	"res://sim/tests/test_catan.gd",
	"res://sim/tests/test_carts.gd",
	"res://sim/tests/test_infection.gd",
	"res://sim/tests/test_units.gd",
	"res://sim/tests/test_world_sim.gd",
	"res://sim/tests/test_projection.gd",
	"res://sim/tests/test_dungeons.gd",
	"res://sim/tests/test_puzzle_rooms.gd",
	"res://sim/tests/test_puzzle_walkable.gd",
	"res://sim/tests/test_puzzle_r01.gd",
	"res://sim/tests/test_quests.gd",
]


func _init() -> void:
	var failed := 0
	var passed := 0
	for path in TESTS:
		var script: GDScript = load(path)
		if script == null or not script.can_instantiate():
			print("FAIL %s" % path)
			print("  - script failed to load/compile")
			failed += 1
			continue
		var inst = script.new()
		inst.run()
		if inst.passed():
			print("PASS %s" % path)
			passed += 1
		else:
			print("FAIL %s" % path)
			for f in inst.failures():
				print("  - %s" % f)
			failed += 1
	print("---")
	print("Passed: %d  Failed: %d" % [passed, failed])
	quit(1 if failed > 0 else 0)
