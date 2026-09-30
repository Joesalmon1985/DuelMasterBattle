extends RefCounted
class_name DmbVisualSimHarvester

## Read-only harvest of presentation nodes keyed by simulation IDs.
## Walks WorldLayerPresenters actors and Overworld entities; never mutates gameplay.


static func harvest(shell) -> Dictionary:
	var entities: Array = []
	if shell == null:
		return {"layer": "render", "entities": entities, "error": "no_shell"}
	var overworld = shell.get("_overworld") if shell.get("_overworld") != null else null
	if overworld == null and shell.has_method("get"):
		overworld = shell.get("overworld")
	# Prefer actors root used by WorldLayerPresenters.
	var actors: Node = null
	if overworld != null and overworld.get("_actors_root") != null:
		actors = overworld._actors_root
	if actors != null:
		_walk(actors, entities, "layers")
	# Overworld keeps an Array of entity dicts with optional "node" refs.
	if overworld != null and overworld.get("_entities") != null:
		var ent_list = overworld._entities
		if typeof(ent_list) == TYPE_ARRAY:
			for raw in ent_list:
				if typeof(raw) != TYPE_DICTIONARY:
					continue
				var ed: Dictionary = raw
				var n2 = ed.get("node")
				var eid := str(ed.get("id", ""))
				if typeof(n2) == TYPE_OBJECT and is_instance_valid(n2):
					if not n2.has_meta("sim_id") and eid != "":
						n2.set_meta("sim_id", eid)
					if not n2.has_meta("sim_kind"):
						n2.set_meta("sim_kind", str(ed.get("kind", "entity")))
					if not n2.has_meta("sim_role"):
						n2.set_meta("sim_role", "body")
					entities.append(_describe(n2, eid, "overworld"))
				elif eid != "":
					# Tile/sign without node — still record authoritative presentation identity.
					entities.append({
						"sim_id": eid,
						"sim_kind": str(ed.get("kind", "entity")),
						"role": "body",
						"source": "overworld_dict",
						"visible": true,
						"visible_in_tree": true,
						"in_viewport": true,
						"grid": ed.get("pos", ed.get("grid")),
						"position": null,
						"godot_instance_id": 0,
					})
	var vp := DisplayServer.window_get_size()
	return {
		"layer": "render",
		"entities": entities,
		"viewport": [vp.x, vp.y],
		"entity_count": entities.size(),
	}


static func _walk(node: Node, out: Array, source: String) -> void:
	if node == null:
		return
	if node.has_meta("sim_id") or node.has_meta("unit_id") or node.has_meta("semantic_id"):
		out.append(_describe(node, "", source))
	for c in node.get_children():
		_walk(c, out, source)


static func _describe(node: Node, fallback_id: String, source: String) -> Dictionary:
	var sim_id := ""
	if node.has_meta("sim_id"):
		sim_id = str(node.get_meta("sim_id"))
	elif node.has_meta("unit_id"):
		sim_id = str(node.get_meta("unit_id"))
	elif fallback_id != "":
		sim_id = fallback_id
	else:
		sim_id = str(node.name)
	var kind := ""
	if node.has_meta("sim_kind"):
		kind = str(node.get_meta("sim_kind"))
	elif node.has_meta("semantic_id"):
		kind = str(node.get_meta("semantic_id"))
	var role := "body"
	if node.has_meta("sim_role"):
		role = str(node.get_meta("sim_role"))
	elif str(node.name).to_lower().find("label") >= 0:
		role = "label"
	var visible := true
	if node is CanvasItem:
		visible = (node as CanvasItem).is_visible_in_tree()
	var pos := Vector2.ZERO
	if node is Node2D:
		pos = (node as Node2D).global_position
	elif node is Control:
		pos = (node as Control).get_global_rect().get_center()
	var tpx := 64.0
	var grid := [pos.x / tpx - 0.5, pos.y / tpx - 0.5]
	var vp := DisplayServer.window_get_size()
	var in_vp := pos.x >= 0.0 and pos.y >= 0.0 and pos.x <= float(vp.x) and pos.y <= float(vp.y)
	return {
		"sim_id": sim_id,
		"sim_kind": kind,
		"role": role,
		"source": source,
		"name": str(node.name),
		"visible": visible,
		"visible_in_tree": visible,
		"in_viewport": in_vp,
		"position": [pos.x, pos.y],
		"grid": grid,
		"godot_instance_id": node.get_instance_id(),
	}
