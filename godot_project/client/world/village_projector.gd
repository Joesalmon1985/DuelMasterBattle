extends RefCounted
class_name DmbVillageProjector

## Presentation binder for LocalProjectionService views (C09 / T078).
## Recreates sprites by authoritative entity ID; never invents people or layouts.

const TILE := 64.0

var _node_id: String = ""
var _view: Dictionary = {}
var _actors: Dictionary = {}  # entity_id -> Node2D placeholder metadata


func clear() -> void:
	_node_id = ""
	_view = {}
	_actors.clear()


func apply_projection(view: Dictionary) -> void:
	## Bind disposable projection view. Destroyed / missing IDs are removed.
	_node_id = str(view.get("node_id", ""))
	_view = view.duplicate(true)
	var live: Dictionary = {}
	for bucket in ["buildings", "people", "carts", "units"]:
		for item in view.get(bucket, []):
			var eid := str(item.get("id", ""))
			if eid.is_empty():
				continue
			live[eid] = {
				"id": eid,
				"kind": bucket,
				"grid": item.get("grid", []),
				"meta": item,
			}
	# Drop actors whose IDs are no longer present (destroyed stay absent).
	var stale: Array = []
	for eid in _actors.keys():
		if not live.has(eid):
			stale.append(eid)
	for eid in stale:
		_actors.erase(eid)
	for eid in live.keys():
		_actors[eid] = live[eid]


func actor_ids() -> Array:
	var ids: Array = _actors.keys()
	ids.sort()
	return ids


func actor_grid(entity_id: String) -> Array:
	var rec = _actors.get(entity_id, {})
	return rec.get("grid", [])


func world_position(entity_id: String) -> Vector2:
	var grid = actor_grid(entity_id)
	if grid.size() < 2:
		return Vector2.ZERO
	return Vector2(float(grid[0]) * TILE, float(grid[1]) * TILE)


func area_size() -> Vector2i:
	return Vector2i(int(_view.get("width", 0)), int(_view.get("height", 0)))


func exits_reachable() -> Array:
	return _view.get("exits_reachable", [])


func destroyed_ids() -> Array:
	return _view.get("destroyed_ids", [])


func has_actor(entity_id: String) -> bool:
	return _actors.has(entity_id)


func node_id() -> String:
	return _node_id
