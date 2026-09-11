extends DmbTestCase
## Regression test for the production Kit→Overworld walkability adapter.
## Exercises the REAL Overworld.is_walkable() (res://client/world/overworld.gd),
## not a copy: Kit blocking semantics are `true = blocked`, while
## Overworld.is_walkable() means `true = walkable`, so walkable = NOT blocked.
## Uses pz_01 (closed/open gate) generically — no puzzle-specific production logic.

const _Overworld = preload("res://client/world/overworld.gd")
const _Runner = preload("res://client/scripts/puzzle_test_runner.gd")
const _Adventure = preload("res://client/scripts/adventure.gd")

const FREE := Vector2i(6, 9)  # pz_01 start tile: open floor, no entity
const GATE := Vector2i(6, 2)  # pz_01 gate: closed until o1..o4 installed
const WALL := Vector2i(0, 0)  # border wall: solid in every layer

var _ow = null
var _adv = null
var _prev := ""


func run() -> void:
	_begin()
	_test_free_floor()
	_test_closed_gate()
	_test_static_wall()
	_test_open_gate()
	_end()


func _begin() -> void:
	_prev = str(_Runner.get_puzzle())
	_Runner.set_puzzle("pz_01")
	_adv = _Adventure.new()
	_ow = _Overworld.new()
	_ow._play.setup(_ow, _adv, null)
	_ow.area = _ow._play.puzzle_area()
	var rows: Array = _ow.area["rows"]
	_ow.grid_h = rows.size()
	_ow.grid_w = str(rows[0]).length()
	assert_true(_ow._play.is_kit_puzzle_area(_ow.area), "pz_01 projects as a kit puzzle area")


func _end() -> void:
	if _prev == "":
		_Runner.clear()
	else:
		_Runner.set_puzzle(_prev)
	if _ow != null:
		_ow.free()
		_ow = null
	if _adv != null:
		_adv.free()
		_adv = null


func _test_free_floor() -> void:
	assert_eq(_ow._play.kit_blocks(FREE), false, "pz_01 start tile is not kit-blocked")
	assert_eq(_ow.is_walkable(FREE), true, "REAL Overworld: free puzzle floor is walkable")


func _test_closed_gate() -> void:
	assert_eq(_ow._play.kit_blocks(GATE), true, "pz_01 gate starts closed (kit-blocked)")
	assert_eq(_ow.is_walkable(GATE), false, "REAL Overworld: closed puzzle gate is not walkable")


func _test_static_wall() -> void:
	assert_eq(_ow.is_walkable(WALL), false, "REAL Overworld: solid wall stays blocked")


func _test_open_gate() -> void:
	# Authoritative kit state change through real kit machinery:
	# installing each riddle's correct object sets flags o1..o4, opening the gate.
	var st: Dictionary = _Runner.kit_state()
	st["rec"] = {"o1": "mirror_shard", "o2": "tallow_candle", "o3": "grey_stone", "o4": "copper_coin"}
	_ow.area = _ow._play.puzzle_area()
	assert_eq(_ow._play.kit_blocks(GATE), false, "pz_01 gate opens once offerings installed")
	assert_eq(_ow.is_walkable(GATE), true, "REAL Overworld: open puzzle gate is walkable")
