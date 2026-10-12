extends SceneTree

## Run one sim test: godot --headless --path godot_project --script res://sim/tools/run_one.gd -- res://sim/tests/test_dungeons.gd


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var script: GDScript = load(args[0])
	var inst = script.new()
	inst.run()
	if inst.passed():
		print("PASS %s" % args[0])
		quit(0)
	else:
		print("FAIL %s" % args[0])
		for f in inst.failures():
			print("  - %s" % f)
		quit(1)
