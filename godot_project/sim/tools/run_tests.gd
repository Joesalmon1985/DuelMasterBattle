extends SceneTree

const TESTS := [
	"res://sim/tests/test_code.gd",
	"res://sim/tests/test_feedback.gd",
	"res://sim/tests/test_fixtures.gd",
	"res://sim/tests/test_game_state.gd",
]


func _init() -> void:
	var failed := 0
	var passed := 0
	for path in TESTS:
		var script: GDScript = load(path)
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
