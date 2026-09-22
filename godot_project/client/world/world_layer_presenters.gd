extends Node2D
class_name DmbWorldLayerPresenters

## Mounts geometric cart / soldier / hazard / construction / factory overlays
## from overworld_area entities. Presentation-only — never mutates authority.

const VisualLanguage = preload("res://client/world/visual_language.gd")
const HazardActor = preload("res://client/world/hazard_actor.gd")

const TPX := 64.0

var _root: Node2D
var _by_id: Dictionary = {}


func bind_host(actors_root: Node2D) -> void:
	_root = actors_root


func clear() -> void:
	for id in _by_id.keys():
		var n: Node = _by_id[id]
		if is_instance_valid(n):
			n.queue_free()
	_by_id.clear()


func apply_area(area: Dictionary) -> void:
	if _root == null:
		return
	var keep: Dictionary = {}
	for raw in area.get("entities", []):
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var e: Dictionary = raw
		var kind := str(e.get("kind", ""))
		match kind:
			"cart":
				_upsert_cart(e)
				keep[str(e.get("id", ""))] = true
			"soldier":
				_upsert_soldier(e)
				keep[str(e.get("id", ""))] = true
			"hazard":
				_upsert_hazard(e)
				keep[str(e.get("id", ""))] = true
			"boulder", "rockfall":
				_upsert_rockfall(e)
				keep[str(e.get("id", ""))] = true
			"ruin":
				_upsert_ruin(e)
				keep[str(e.get("id", ""))] = true
			"construction":
				_upsert_construction(e)
				keep[str(e.get("id", ""))] = true
			"nature", "deco":
				_upsert_nature(e)
				keep[str(e.get("id", ""))] = true
			"door", "sign":
				if bool(e.get("historic", false)) or str(e.get("era", "")) == "historic":
					_upsert_historic_marker(e)
					keep["era:%s" % str(e.get("id", ""))] = true
				elif bool(e.get("legacy", false)):
					_upsert_legacy_marker(e)
					keep["era:%s" % str(e.get("id", ""))] = true
	for row in area.get("industry_overlay", []):
		if typeof(row) != TYPE_DICTIONARY:
			continue
		if str(row.get("kind", "")) == "factory_meter":
			_upsert_factory_meter(row)
			keep["meter:%s" % str(row.get("building_id", ""))] = true
	# Prune stale
	for id in _by_id.keys():
		if not keep.has(id):
			var n: Node = _by_id[id]
			if is_instance_valid(n):
				n.queue_free()
			_by_id.erase(id)


func _grid_pos(e: Dictionary) -> Vector2:
	var pos = e.get("pos", e.get("grid", [0, 0]))
	return Vector2(float(pos[0]) + 0.5, float(pos[1]) + 0.5) * TPX


func _upsert_cart(e: Dictionary) -> void:
	var id := str(e.get("id", ""))
	var node: Node2D = _by_id.get(id)
	if node == null:
		node = Node2D.new()
		node.name = id
		_root.add_child(node)
		var body := Polygon2D.new()
		body.name = "Body"
		body.polygon = VisualLanguage.cart_rect()
		node.add_child(body)
		var accent := Polygon2D.new()
		accent.name = "Accent"
		accent.polygon = PackedVector2Array([
			Vector2(-16, -10), Vector2(-12, -10), Vector2(-12, 10), Vector2(-16, 10)
		])
		node.add_child(accent)
		var label := Label.new()
		label.name = "Label"
		label.position = Vector2(-28, 12)
		label.add_theme_font_size_override("font_size", 10)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.custom_minimum_size = Vector2(56, 0)
		node.add_child(label)
		var pips := Node2D.new()
		pips.name = "Pips"
		node.add_child(pips)
		_by_id[id] = node
	node.position = _grid_pos(e)
	node.z_index = 6
	var faction := str(e.get("faction_id", ""))
	var color := VisualLanguage.faction_color(faction)
	(node.get_node("Body") as Polygon2D).color = Color(0.55, 0.4, 0.25)
	(node.get_node("Accent") as Polygon2D).color = color
	var cargo: Array = e.get("cargo", [])
	(node.get_node("Label") as Label).text = "cart"
	var pips_node: Node2D = node.get_node("Pips")
	for c in pips_node.get_children():
		c.queue_free()
	for i in cargo.size():
		var pip := Polygon2D.new()
		pip.polygon = PackedVector2Array([
			Vector2(-3, -3), Vector2(3, -3), Vector2(3, 3), Vector2(-3, 3)
		])
		pip.color = VisualLanguage.cargo_color(str(cargo[i]))
		pip.position = Vector2(10 + i * 8, -14)
		pips_node.add_child(pip)


func _upsert_soldier(e: Dictionary) -> void:
	var id := str(e.get("id", ""))
	var node: Node2D = _by_id.get(id)
	if node == null:
		node = Node2D.new()
		node.name = id
		_root.add_child(node)
		var body := Polygon2D.new()
		body.name = "Body"
		node.add_child(body)
		var label := Label.new()
		label.name = "Label"
		label.position = Vector2(-30, 14)
		label.add_theme_font_size_override("font_size", 10)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.custom_minimum_size = Vector2(60, 0)
		node.add_child(label)
		_by_id[id] = node
	node.set_meta("unit_id", str(e.get("unit_id", id)))
	node.set_meta("person_id", str(e.get("person_id", "")))
	node.position = _grid_pos(e)
	node.z_index = 7
	var arch := str(e.get("archetype", "line"))
	(node.get_node("Body") as Polygon2D).polygon = VisualLanguage.archetype_polygon(arch)
	(node.get_node("Body") as Polygon2D).color = VisualLanguage.faction_color(str(e.get("faction_id", "")))
	(node.get_node("Label") as Label).text = str(e.get("name", arch))


func _upsert_hazard(e: Dictionary) -> void:
	var id := str(e.get("cube_id", e.get("id", "")))
	var node: Node2D = _by_id.get(id)
	if node == null:
		var actor = HazardActor.new()
		actor.name = id
		_root.add_child(actor)
		node = actor
		_by_id[id] = node
	if node.has_method("bind_cube"):
		node.bind_cube({
			"id": id,
			"hex_id": str(e.get("hex_id", "")),
			"type": str(e.get("hazard_type", "demon")),
			"active": true,
			"treatment_eligible": true,
			"cube_count": 1,
		})
	node.position = _grid_pos(e)
	node.z_index = 8


func _upsert_boulder(e: Dictionary) -> void:
	_upsert_rockfall(e)


func _upsert_rockfall(e: Dictionary) -> void:
	var id := str(e.get("id", ""))
	if id.is_empty():
		return
	var node: Node2D = _by_id.get(id)
	if node == null:
		node = Node2D.new()
		node.name = id
		_root.add_child(node)
		var stones := Node2D.new()
		stones.name = "Stones"
		node.add_child(stones)
		var label := Label.new()
		label.name = "Label"
		label.text = "Rockfall"
		label.position = Vector2(-40, 36)
		label.add_theme_font_size_override("font_size", 12)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.custom_minimum_size = Vector2(80, 0)
		node.add_child(label)
		_by_id[id] = node
	var stones_root: Node2D = node.get_node("Stones")
	var pieces: Array = e.get("pieces", [])
	if pieces.is_empty():
		pieces = [{"id": "%s.stone:1" % id, "pos_f": e.get("pos_f", e.get("pos", [0, 0]))}]
	# Rebuild stone polygons to match piece count.
	while stones_root.get_child_count() > pieces.size():
		stones_root.get_child(stones_root.get_child_count() - 1).queue_free()
	while stones_root.get_child_count() < pieces.size():
		var body := Polygon2D.new()
		body.name = "Stone_%d" % stones_root.get_child_count()
		var radius := 22.0 + float(stones_root.get_child_count() % 3) * 3.0
		var pts := PackedVector2Array()
		var sides := 8 + (stones_root.get_child_count() % 3)
		for i in sides:
			var a := TAU * float(i) / float(sides)
			pts.append(Vector2(cos(a), sin(a)) * radius)
		body.polygon = pts
		body.color = Color(0.55, 0.55, 0.58)
		stones_root.add_child(body)
	var origin := _grid_pos(e)
	if e.has("pos_f") and typeof(e.get("pos_f")) == TYPE_ARRAY and e["pos_f"].size() >= 2:
		origin = Vector2(float(e["pos_f"][0]), float(e["pos_f"][1])) * TPX + Vector2(TPX * 0.5, TPX * 0.5)
	node.position = origin
	node.z_index = 6
	var status := str(e.get("status", "blocking"))
	var base_col := Color(0.45, 0.45, 0.48) if status in ["moved", "cleared"] else Color(0.55, 0.55, 0.58)
	for i in pieces.size():
		var piece: Dictionary = pieces[i]
		var stone: Polygon2D = stones_root.get_child(i)
		stone.color = base_col
		var pf = piece.get("pos_f", piece.get("pos", []))
		if typeof(pf) == TYPE_ARRAY and pf.size() >= 2:
			var world := Vector2(float(pf[0]), float(pf[1])) * TPX + Vector2(TPX * 0.5, TPX * 0.5)
			stone.position = world - origin
		else:
			stone.position = Vector2.ZERO
	(node.get_node("Label") as Label).text = str(e.get("label", "Rockfall"))


func _upsert_construction(e: Dictionary) -> void:
	var id := str(e.get("id", ""))
	var node: Node2D = _by_id.get(id)
	if node == null:
		node = Node2D.new()
		node.name = id
		_root.add_child(node)
		var outline := Line2D.new()
		outline.name = "Outline"
		outline.width = 2.0
		outline.default_color = Color(1, 0.9, 0.3, 0.85)
		outline.points = PackedVector2Array([
			Vector2(-18, -18), Vector2(18, -18), Vector2(18, 18), Vector2(-18, 18), Vector2(-18, -18)
		])
		node.add_child(outline)
		var label := Label.new()
		label.name = "Label"
		label.position = Vector2(-40, 20)
		label.add_theme_font_size_override("font_size", 10)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.custom_minimum_size = Vector2(80, 0)
		node.add_child(label)
		_by_id[id] = node
	node.position = _grid_pos(e)
	node.z_index = 4
	(node.get_node("Label") as Label).text = "Building %s" % str(e.get("action", "work"))


func _upsert_nature(e: Dictionary) -> void:
	var id := str(e.get("id", ""))
	if id.is_empty():
		return
	var node: Node2D = _by_id.get(id)
	var kind := str(e.get("kind", "nature"))
	var prop_kind := str(e.get("prop_kind", e.get("nature_kind", "")))
	if prop_kind.is_empty():
		# Infer from marker / id fragments for export rows.
		var marker := str(e.get("marker", ""))
		if "tree" in marker:
			prop_kind = "tree"
		elif "animal" in id or bool(e.get("ambient", false)):
			prop_kind = "animal"
		elif "clay" in marker or "charcoal" in marker:
			prop_kind = "clay_patch"
		elif "seed" in marker:
			prop_kind = "field_patch"
		elif "stone" in marker or "rock" in marker:
			prop_kind = "rock"
		elif "mine" in marker or "miner" in marker:
			prop_kind = "mine"
		else:
			prop_kind = "scrub"
	if node == null:
		node = Node2D.new()
		node.name = id
		_root.add_child(node)
		var body := Polygon2D.new()
		body.name = "Body"
		node.add_child(body)
		_by_id[id] = node
	node.position = _grid_pos(e)
	node.z_index = 2 if kind == "deco" else 3
	var terrain := str(e.get("terrain", ""))
	(node.get_node("Body") as Polygon2D).polygon = VisualLanguage.nature_polygon(prop_kind)
	(node.get_node("Body") as Polygon2D).color = VisualLanguage.nature_color(prop_kind, terrain)


func _upsert_factory_meter(row: Dictionary) -> void:
	var bid := str(row.get("building_id", ""))
	var id := "meter:%s" % bid
	var node: Node2D = _by_id.get(id)
	if node == null:
		node = Node2D.new()
		node.name = id
		_root.add_child(node)
		var bg := ColorRect.new()
		bg.name = "Bg"
		bg.size = Vector2(48, 6)
		bg.position = Vector2(-24, -28)
		bg.color = Color(0.1, 0.1, 0.1, 0.8)
		node.add_child(bg)
		var fg := ColorRect.new()
		fg.name = "Fg"
		fg.size = Vector2(1, 6)
		fg.position = Vector2(-24, -28)
		fg.color = Color(0.25, 0.85, 0.4)
		node.add_child(fg)
		var label := Label.new()
		label.name = "Label"
		label.position = Vector2(-40, -44)
		label.add_theme_font_size_override("font_size", 10)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.custom_minimum_size = Vector2(80, 0)
		node.add_child(label)
		_by_id[id] = node
	var grid = row.get("grid", [0, 0])
	node.position = Vector2(float(grid[0]) + 1.5, float(grid[1]) + 0.5) * TPX
	node.z_index = 9
	var pct := float(row.get("meter_progress", row.get("meter_pct", 0.0)))
	if pct > 1.0:
		pct = pct / 100.0
	pct = clampf(pct, 0.0, 1.0)
	(node.get_node("Fg") as ColorRect).size = Vector2(48.0 * pct, 6)
	(node.get_node("Label") as Label).text = str(row.get("unit_label", "Yard"))


func _upsert_ruin(e: Dictionary) -> void:
	var id := str(e.get("id", ""))
	var node: Node2D = _by_id.get(id)
	if node == null:
		node = Node2D.new()
		node.name = id
		_root.add_child(node)
		var body := Polygon2D.new()
		body.name = "Body"
		body.polygon = VisualLanguage.ruin_outline()
		body.color = VisualLanguage.era_building_color("", ruin=true)
		node.add_child(body)
		var label := Label.new()
		label.name = "Label"
		label.text = "Ruins"
		label.position = Vector2(-28, 18)
		label.add_theme_font_size_override("font_size", 11)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.custom_minimum_size = Vector2(56, 0)
		node.add_child(label)
		_by_id[id] = node
	node.position = _grid_pos(e)
	node.z_index = 4


func _upsert_historic_marker(e: Dictionary) -> void:
	var id := "era:%s" % str(e.get("id", ""))
	var node: Node2D = _by_id.get(id)
	if node == null:
		node = Node2D.new()
		node.name = id
		_root.add_child(node)
		var body := Polygon2D.new()
		body.name = "Body"
		body.polygon = VisualLanguage.historic_building_polygon(12.0)
		body.color = VisualLanguage.era_building_color("historic")
		node.add_child(body)
		var label := Label.new()
		label.name = "Label"
		label.position = Vector2(-36, 14)
		label.add_theme_font_size_override("font_size", 10)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.custom_minimum_size = Vector2(72, 0)
		node.add_child(label)
		_by_id[id] = node
	node.position = _grid_pos(e)
	node.z_index = 5
	(node.get_node("Label") as Label).text = str(e.get("text", "HISTORIC"))


func _upsert_legacy_marker(e: Dictionary) -> void:
	var id := "era:%s" % str(e.get("id", ""))
	var node: Node2D = _by_id.get(id)
	if node == null:
		node = Node2D.new()
		node.name = id
		_root.add_child(node)
		var body := Polygon2D.new()
		body.name = "Body"
		body.polygon = PackedVector2Array([
			Vector2(-10, -10), Vector2(10, -10), Vector2(10, 10), Vector2(-10, 10)
		])
		body.color = VisualLanguage.era_building_color("", legacy=true)
		node.add_child(body)
		var label := Label.new()
		label.name = "Label"
		label.position = Vector2(-36, 14)
		label.add_theme_font_size_override("font_size", 10)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.custom_minimum_size = Vector2(72, 0)
		node.add_child(label)
		_by_id[id] = node
	node.position = _grid_pos(e)
	node.z_index = 5
	(node.get_node("Label") as Label).text = str(e.get("text", "LEGACY"))
