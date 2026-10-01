extends RefCounted
class_name DmbVisualSimHarvester

## Read-only harvest of presentation nodes keyed by simulation IDs.
## Never mutates gameplay or set_meta. Dictionary-only rows are never claimed visible.


static func harvest(shell) -> Dictionary:
	var entities: Array = []
	var seen_instances: Dictionary = {}
	if shell == null:
		return {"layer": "render", "entities": entities, "error": "no_shell"}
	var overworld = shell.get("_overworld")
	var camera = null
	if overworld != null and overworld.get("_camera") != null:
		camera = overworld._camera
	# WorldLayerPresenters actors
	var actors: Node = null
	if overworld != null and overworld.get("_actors_root") != null:
		actors = overworld._actors_root
	if actors != null:
		_walk(actors, entities, seen_instances, "layers", camera, overworld)
	# Player (John)
	if overworld != null and overworld.get("_john") != null and is_instance_valid(overworld._john):
		var john = overworld._john
		_append_described(
			entities,
			seen_instances,
			_describe_node(
				john,
				"player:wizard",
				"player",
				"body",
				"overworld",
				camera,
				overworld
			)
		)
	# Overworld entities with real nodes only
	if overworld != null and overworld.get("_entities") != null and typeof(overworld._entities) == TYPE_ARRAY:
		for raw in overworld._entities:
			if typeof(raw) != TYPE_DICTIONARY:
				continue
			var ed: Dictionary = raw
			var eid := str(ed.get("id", ""))
			var n2 = ed.get("node")
			var kind := str(ed.get("kind", "entity"))
			if typeof(n2) == TYPE_OBJECT and is_instance_valid(n2):
				var role := "body"
				if n2.has_meta("sim_role"):
					role = str(n2.get_meta("sim_role"))
				var sid := eid
				if n2.has_meta("sim_id"):
					sid = str(n2.get_meta("sim_id"))
				_append_described(
					entities,
					seen_instances,
					_describe_node(n2, sid, kind, role, "overworld", camera, overworld)
				)
			else:
				# Explicit unsupported observation — not a visibility PASS.
				entities.append({
					"sim_id": eid,
					"sim_kind": kind,
					"role": "registered",
					"source": "overworld_dict",
					"node_backed": false,
					"visible": false,
					"visible_in_tree": false,
					"in_viewport": false,
					"observation": "dict_only_no_node",
					"grid": ed.get("pos", ed.get("grid")),
					"position": null,
					"viewport_pos": null,
					"godot_instance_id": 0,
				})
	# Props root: catch drawable nodes (and disposable fault clones) not only via dict refs.
	if overworld != null and overworld.get("_props_root") != null:
		_walk(overworld._props_root, entities, seen_instances, "overworld_props", camera, overworld)
	# Scenario-relevant controls
	_harvest_controls(shell, entities, seen_instances)
	var vp := DisplayServer.window_get_size()
	var node_backed := 0
	for e in entities:
		if bool(e.get("node_backed", e.get("godot_instance_id", 0) != 0)):
			node_backed += 1
	return {
		"layer": "render",
		"entities": entities,
		"viewport": [vp.x, vp.y],
		"entity_count": entities.size(),
		"node_backed_count": node_backed,
	}


static func _harvest_controls(shell, entities: Array, seen: Dictionary) -> void:
	var controls: Array = []
	if shell.has_method("fx_era_wait_button"):
		controls.append(["control:wait", shell.fx_era_wait_button()])
	if shell.has_method("world_map_panel"):
		var p = shell.world_map_panel()
		if p != null:
			controls.append(["control:world_map", p])
	if shell.get("_spell_host") != null:
		controls.append(["control:spellbook", shell._spell_host])
	for pair in controls:
		var id: String = pair[0]
		var ctrl = pair[1]
		if ctrl == null or not is_instance_valid(ctrl):
			continue
		if not (ctrl is CanvasItem):
			continue
		var ci := ctrl as CanvasItem
		var rect := Rect2()
		if ctrl is Control:
			rect = (ctrl as Control).get_global_rect()
		var center := rect.get_center() if rect.size != Vector2.ZERO else Vector2.ZERO
		var vp := DisplayServer.window_get_size()
		var in_vp := rect.size != Vector2.ZERO and rect.intersects(Rect2(Vector2.ZERO, Vector2(vp)))
		_append_described(entities, seen, {
			"sim_id": id,
			"sim_kind": "control",
			"role": "control",
			"source": "ui",
			"node_backed": true,
			"visible": ci.is_visible_in_tree(),
			"visible_in_tree": ci.is_visible_in_tree(),
			"in_viewport": in_vp,
			"position": [center.x, center.y],
			"viewport_pos": [center.x, center.y],
			"bounds": [rect.position.x, rect.position.y, rect.size.x, rect.size.y],
			"grid": null,
			"godot_instance_id": ctrl.get_instance_id(),
			"observation": "node",
		})


static func _walk(node: Node, out: Array, seen: Dictionary, source: String, camera, overworld) -> void:
	if node == null:
		return
	# Only harvest nodes that carry identity meta themselves (not label children).
	if node.has_meta("sim_id") or node.has_meta("unit_id"):
		var sid := ""
		if node.has_meta("sim_id"):
			sid = str(node.get_meta("sim_id"))
		elif node.has_meta("unit_id"):
			sid = str(node.get_meta("unit_id"))
		var kind := str(node.get_meta("sim_kind")) if node.has_meta("sim_kind") else ""
		var role := str(node.get_meta("sim_role")) if node.has_meta("sim_role") else "body"
		_append_described(out, seen, _describe_node(node, sid, kind, role, source, camera, overworld))
	for c in node.get_children():
		# Label children of a body: report as label role if named Label.
		if str(c.name) == "Label" and (node.has_meta("sim_id") or node.has_meta("unit_id")):
			var psid := str(node.get_meta("sim_id")) if node.has_meta("sim_id") else str(node.get_meta("unit_id"))
			_append_described(
				out,
				seen,
				_describe_node(c, psid, "label", "label", source, camera, overworld)
			)
		else:
			_walk(c, out, seen, source, camera, overworld)


static func _append_described(out: Array, seen: Dictionary, desc: Dictionary) -> void:
	var iid := int(desc.get("godot_instance_id", 0))
	if iid != 0:
		if seen.has(iid):
			return
		seen[iid] = true
	out.append(desc)


static func _describe_node(node: Node, sim_id: String, kind: String, role: String, source: String, camera, overworld) -> Dictionary:
	var visible := false
	if node is CanvasItem:
		visible = (node as CanvasItem).is_visible_in_tree()
	var world_pos := Vector2.ZERO
	var bounds := Rect2()
	if node is Node2D:
		world_pos = (node as Node2D).global_position
		bounds = Rect2(world_pos, Vector2(32, 32))
	elif node is Control:
		var r := (node as Control).get_global_rect()
		world_pos = r.get_center()
		bounds = r
	var screen := world_pos
	if overworld != null and overworld.has_method("ui_world_to_screen") and node is Node2D:
		screen = overworld.ui_world_to_screen(world_pos)
	elif camera != null and camera.has_method("get_screen_center_position") and node is Node2D:
		var view := DisplayServer.window_get_size()
		screen = (world_pos - camera.get_screen_center_position()) * camera.zoom + Vector2(view) * 0.5
	var vp := DisplayServer.window_get_size()
	var in_vp := screen.x >= -32.0 and screen.y >= -32.0 and screen.x <= float(vp.x) + 32.0 and screen.y <= float(vp.y) + 32.0
	var tpx := 64.0
	return {
		"sim_id": sim_id,
		"sim_kind": kind,
		"role": role,
		"source": source,
		"name": str(node.name),
		"node_backed": true,
		"visible": visible,
		"visible_in_tree": visible,
		"in_viewport": in_vp and visible,
		"position": [world_pos.x, world_pos.y],
		"viewport_pos": [screen.x, screen.y],
		"bounds": [bounds.position.x, bounds.position.y, bounds.size.x, bounds.size.y],
		"grid": [world_pos.x / tpx - 0.5, world_pos.y / tpx - 0.5] if node is Node2D else null,
		"godot_instance_id": node.get_instance_id(),
		"observation": "node",
	}
