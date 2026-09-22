extends DmbTestCase
## Regression: clearing a rockfall must free Overworld local collision without a
## full LocalArea rebuild. WorldLayerPresenters alone must not leave stale
## _entity_at blocks (G05 south-road bug).

const _Overworld = preload("res://client/world/overworld.gd")
const _Adventure = preload("res://client/scripts/adventure.gd")

const CORRIDOR := [
	Vector2i(22, 42),
	Vector2i(24, 41),
	Vector2i(26, 42),
	Vector2i(23, 43),
	Vector2i(25, 43),
]
const ASIDE := [
	Vector2i(18, 42),
	Vector2i(19, 41),
	Vector2i(30, 42),
	Vector2i(18, 43),
	Vector2i(30, 43),
]

var _ow = null
var _adv = null


func run() -> void:
	_begin()
	_test_blocking_then_sync_clears_corridor()
	_test_stale_entity_at_without_sync_stays_blocked()
	_test_path_reachable_after_clear()
	_end()


func _begin() -> void:
	_adv = _Adventure.new()
	_ow = _Overworld.new()
	_ow._play.setup(_ow, _adv, null)
	# Minimal open floor so SOLID_TILES do not interfere.
	var row := ".".repeat(48)
	var rows: Array = []
	for _i in 48:
		rows.append(row)
	_ow.area = {"id": "area.test_rockfall", "name": "Test", "rows": rows, "entities": []}
	_ow.grid_w = 48
	_ow.grid_h = 48
	_ow._entities.clear()
	_ow._entity_at.clear()


func _end() -> void:
	if _ow != null:
		_ow.free()
		_ow = null
	if _adv != null:
		_adv.free()
		_adv = null


func _blocking_entity() -> Dictionary:
	var pieces: Array = []
	var tiles: Array = []
	for i in CORRIDOR.size():
		var p: Vector2i = CORRIDOR[i]
		pieces.append({"id": "rockfall:1.stone:%d" % (i + 1), "pos": [p.x, p.y]})
		tiles.append([p.x, p.y])
	return {
		"kind": "rockfall",
		"id": "rockfall:1",
		"pos": [24, 41],
		"label": "Rockfall",
		"status": "blocking",
		"blocks_walk": true,
		"blocked_tiles": tiles,
		"pieces": pieces,
	}


func _cleared_entity() -> Dictionary:
	var pieces: Array = []
	for i in ASIDE.size():
		var p: Vector2i = ASIDE[i]
		pieces.append({"id": "rockfall:1.stone:%d" % (i + 1), "pos": [p.x, p.y]})
	return {
		"kind": "rockfall",
		"id": "rockfall:1",
		"pos": [19, 41],
		"label": "Rockfall",
		"status": "cleared",
		"blocks_walk": false,
		"blocked_tiles": [],
		"pieces": pieces,
	}


func _test_blocking_then_sync_clears_corridor() -> void:
	_ow.sync_dynamic_obstacle(_blocking_entity())
	for t in CORRIDOR:
		assert_eq(_ow.is_walkable(t), false, "blocking rockfall occupies %s" % str(t))
	_ow.sync_dynamic_obstacle(_cleared_entity())
	for t in CORRIDOR:
		assert_eq(_ow.is_walkable(t), true, "after sync cleared corridor tile %s walkable" % str(t))
	# Cleared rockfall is non-solid everywhere for this fix (path usability first).
	for t in ASIDE:
		assert_eq(_ow.is_walkable(t), true, "cleared aside tile %s not forced solid" % str(t))
	assert_true(not _ow._entity_by_id("rockfall:1").is_empty(), "rockfall remains interactable in _entities")


func _test_stale_entity_at_without_sync_stays_blocked() -> void:
	## Documents the pre-fix failure mode: visual payload updates separately
	## from Overworld's stored _entity_at dictionaries (new dict vs old ref).
	_ow._entities.clear()
	_ow._entity_at.clear()
	_ow.sync_dynamic_obstacle(_blocking_entity())
	assert_eq(_ow.is_walkable(CORRIDOR[1]), false, "blocking before stale scenario")
	# Production WorldLayerPresenters receives a NEW cleared payload; it does not
	# mutate the Dictionary objects already stored in _entity_at.
	# Without sync_dynamic_obstacle, those old blocking refs remain.
	assert_eq(_ow.is_walkable(CORRIDOR[1]), false, "stale _entity_at still blocks without sync")
	_ow.sync_dynamic_obstacle(_cleared_entity())
	assert_eq(_ow.is_walkable(CORRIDOR[1]), true, "sync_dynamic_obstacle frees stale corridor")


func _test_path_reachable_after_clear() -> void:
	_ow._entities.clear()
	_ow._entity_at.clear()
	# Full-width wall of rockfall tiles so BFS cannot walk around.
	var wall_tiles: Array = []
	var wall_pieces: Array = []
	for x in range(0, 48):
		wall_tiles.append([x, 41])
		wall_pieces.append({"id": "rockfall:1.stone:%d" % x, "pos": [x, 41]})
	var wall := {
		"kind": "rockfall",
		"id": "rockfall:1",
		"pos": [24, 41],
		"status": "blocking",
		"blocks_walk": true,
		"blocked_tiles": wall_tiles,
		"pieces": wall_pieces,
	}
	_ow.sync_dynamic_obstacle(wall)
	var start := Vector2i(24, 30)
	var exit_tile := Vector2i(24, 46)
	assert_eq(_ow.path_reachable(start, exit_tile), false, "full rockfall wall blocks reachability")
	_ow.sync_dynamic_obstacle({
		"kind": "rockfall",
		"id": "rockfall:1",
		"pos": [19, 41],
		"status": "cleared",
		"blocks_walk": false,
		"blocked_tiles": [],
		"pieces": [{"id": "rockfall:1.stone:1", "pos": [18, 41]}],
	})
	assert_eq(_ow.path_reachable(start, exit_tile), true, "corridor reachable after rockfall sync clear")
