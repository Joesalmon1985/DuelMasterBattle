extends Node

## Wizard Mode / God Mode. One action (toggle) behind both the HUD button and
## the G key. God Mode is an RTS interface over the same sim: it only sends
## the commands the AI uses (build, road, queue, move, order, demolish), so
## the world, its clock and the wizard are shared with Wizard Mode.

var MAP_TILES := Vector2(800.0, 480.0)
const MINI := Vector2(220.0, 132.0)

var world: Node
var active := false
var faction := ""
var tool := ""            # "", "build:<kind>", "road", "move", "attack", "demolish"
var tool_first := ""      # first building of a road
var selected: Array = []  # entity ids
var groups: Dictionary = {}
var menu: Dictionary = {}
var recipes: Dictionary = {}
var locked: Dictionary = {}  # source units that exist but are not implemented yet, with the reason
var message := ""

var layer: CanvasLayer
var mode_btn: Button
var panel: PanelContainer
var faction_row: HBoxContainer
var build_grid: GridContainer
var category_btn: OptionButton
var category := "Core"
var tool_row: HBoxContainer
var info: RichTextLabel
var actions: VBoxContainer
var toast: Label
var minimap: Control

var _cam := Vector2.ZERO
var _saved_zoom := Vector2(0.48, 0.48)
var _drag_from := Vector2.ZERO
var _dragging := false
var _info_acc := 0.0
var _last_actions_key := ""


func setup(p_world: Node) -> void:
	world = p_world
	layer = CanvasLayer.new()
	layer.name = "GodModeLayer"
	layer.layer = 15
	world.add_child(layer)
	mode_btn = Button.new()
	mode_btn.name = "ModeButton"
	mode_btn.text = "God Mode"
	mode_btn.tooltip_text = "Switch between Wizard Mode and God Mode (G)"
	mode_btn.position = Vector2(200, 12)
	mode_btn.custom_minimum_size = Vector2(110, 34)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.22, 0.14, 0.38, 0.95)
	sb.border_color = Color(0.7, 0.6, 1.0)
	sb.set_border_width_all(2)
	sb.set_corner_radius_all(8)
	for state in ["normal", "hover", "pressed", "focus"]:
		var box: StyleBoxFlat = sb.duplicate()
		if state == "hover":
			box.bg_color = Color(0.32, 0.22, 0.52, 0.98)
		mode_btn.add_theme_stylebox_override(state, box)
	mode_btn.pressed.connect(toggle)
	layer.add_child(mode_btn)
	_build_panel()
	_build_minimap()
	toast = Label.new()
	toast.name = "Toast"
	toast.position = Vector2(300, 60)
	toast.add_theme_color_override("font_color", Color(1, 0.95, 0.6))
	toast.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	toast.add_theme_constant_override("outline_size", 6)
	layer.add_child(toast)
	set_active_visuals(false)
	var reply: Dictionary = world._sim.op({"op": "menu"})
	menu = reply.get("build_menu", {})
	recipes = reply.get("recipes", {})
	locked = reply.get("locked", {})
	_fill_build_menu()
	if world.terrain != null:
		MAP_TILES = Vector2(world.terrain.w, world.terrain.h)
	var start := OS.get_environment("HYBRID_START_MODE").to_lower()
	if start == "god" or "--god" in OS.get_cmdline_user_args():
		enter.call_deferred()


func _build_panel() -> void:
	panel = PanelContainer.new()
	panel.name = "GodPanel"
	panel.position = Vector2(12, 58)
	panel.custom_minimum_size = Vector2(250, 0)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	panel.add_child(v)
	var title := Label.new()
	title.text = "GOD MODE - choose a faction"
	v.add_child(title)
	faction_row = HBoxContainer.new()
	faction_row.name = "Factions"
	v.add_child(faction_row)
	var bl := Label.new()
	bl.text = "Build"
	v.add_child(bl)
	category_btn = OptionButton.new()
	category_btn.name = "BuildCategory"
	category_btn.tooltip_text = "Hybrid core buildings, or every runnable building of a Widelands tribe"
	category_btn.item_selected.connect(_on_category)
	v.add_child(category_btn)
	var scroll := ScrollContainer.new()
	scroll.name = "BuildScroll"
	scroll.custom_minimum_size = Vector2(240, 150)
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(scroll)
	build_grid = GridContainer.new()
	build_grid.name = "BuildMenu"
	build_grid.columns = 2
	scroll.add_child(build_grid)
	tool_row = HBoxContainer.new()
	tool_row.name = "Tools"
	v.add_child(tool_row)
	for t in [["Road", "road"], ["Move", "move"], ["A-Move", "amove"], ["Attack", "attack"], ["Rally", "rally"], ["Stop", "stop"], ["Demolish", "demolish"], ["Deposits", "deposits"]]:
		var b := Button.new()
		b.name = "Tool_%s" % t[1]
		b.text = t[0]
		b.pressed.connect(_on_tool.bind(t[1]))
		tool_row.add_child(b)
	info = RichTextLabel.new()
	info.name = "Info"
	info.bbcode_enabled = true
	info.fit_content = true
	info.custom_minimum_size = Vector2(230, 150)
	info.scroll_active = false
	v.add_child(info)
	actions = VBoxContainer.new()
	actions.name = "Actions"
	v.add_child(actions)
	layer.add_child(panel)


func _build_minimap() -> void:
	minimap = Control.new()
	minimap.name = "Minimap"
	minimap.custom_minimum_size = MINI
	minimap.size = MINI
	minimap.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	minimap.position = Vector2(-MINI.x - 12, -MINI.y - 12)
	minimap.offset_left = -MINI.x - 12
	minimap.offset_top = -MINI.y - 12
	minimap.offset_right = -12
	minimap.offset_bottom = -12
	minimap.mouse_filter = Control.MOUSE_FILTER_STOP
	minimap.draw.connect(_draw_minimap)
	minimap.gui_input.connect(_minimap_input)
	layer.add_child(minimap)


func _fill_build_menu() -> void:
	var cats: Array = ["Core"]
	for kind in menu:
		var t := str(menu[kind].get("tribe", ""))
		if t != "" and not cats.has(t.capitalize()):
			cats.append(t.capitalize())
	if category_btn.item_count == 0:
		for c in cats:
			category_btn.add_item(str(c))
	for c in build_grid.get_children():
		c.queue_free()
	var kinds: Array = menu.keys()
	if category != "Core":
		kinds.sort()
	for kind in kinds:
		var spec: Dictionary = menu[kind]
		var tribe := str(spec.get("tribe", "")).capitalize()
		if (category == "Core" and tribe != "") or (category != "Core" and tribe != category):
			continue
		var b := Button.new()
		b.name = "Build_%s" % str(kind).replace(":", "_")
		b.text = str(spec.get("label", kind))
		var cost := ""
		for good in spec.get("cost", {}):
			cost += "%s %d  " % [good, int(spec["cost"][good])]
		b.tooltip_text = "%s
Cost: %s
%s" % [str(spec.get("game", "")), cost, str(spec.get("cost_source", ""))]
		b.pressed.connect(_on_tool.bind("build:%s" % kind))
		build_grid.add_child(b)


func _on_category(index: int) -> void:
	category = category_btn.get_item_text(index)
	_fill_build_menu()


func _fill_factions() -> void:
	for c in faction_row.get_children():
		c.queue_free()
	for f in world._snapshot.get("factions", []):
		var b := Button.new()
		b.name = "Faction_%s" % str(f.get("name", ""))
		b.text = str(f.get("name", "?")).substr(0, 1)
		b.tooltip_text = str(f.get("name", ""))
		b.custom_minimum_size = Vector2(36, 30)
		var col := Color.html(str(f.get("color", "#ffffff")))
		b.add_theme_color_override("font_color", col)
		b.add_theme_color_override("font_hover_color", col)
		b.add_theme_color_override("font_pressed_color", col)
		b.pressed.connect(choose_faction.bind(str(f.get("name", ""))))
		faction_row.add_child(b)


func set_active_visuals(on: bool) -> void:
	panel.visible = on
	minimap.visible = on
	mode_btn.text = "Wizard Mode" if on else "God Mode"
	world._art.show_markers = on


# ---------------------------------------------------------------- mode switch

func toggle() -> void:
	if world._duel_open:
		return
	if active:
		leave()
	else:
		enter()


func enter() -> void:
	active = true
	world._input_locked = true
	world._touch.set_enabled(false)
	world._touch.visible = false
	_saved_zoom = world._camera.zoom
	_cam = world._camera.position
	world.camera_focus = _cam
	_fill_factions()
	set_active_visuals(true)
	if faction == "":
		choose_faction("Red")
	else:
		choose_faction(faction)


func leave() -> void:
	active = false
	tool = ""
	tool_first = ""
	selected.clear()
	world._sim.op({"op": "control", "faction": ""})
	world.camera_focus = Vector2.INF
	world._input_locked = false
	world._touch.set_enabled(true)
	world._touch.visible = true
	world._camera.zoom = _saved_zoom
	world._place_john_from_snapshot()
	set_active_visuals(false)
	world.selected_ids = {}


func choose_faction(name: String) -> void:
	faction = name
	var reply: Dictionary = world._sim.op({"op": "control", "faction": name})
	world._apply_snapshot(reply.get("snapshot", {}))
	selected.clear()
	tool = ""
	for f in world._snapshot.get("factions", []):
		if str(f.get("name", "")) == name:
			_say("Controlling %s" % name)
	_jump_to_capital()


func _jump_to_capital() -> void:
	for e in world._snapshot.get("entities", []):
		if str(e.get("kind", "")) == "warehouse" and str(e.get("faction_name", "")) == faction:
			_cam = (Vector2(float(e["tx"]), float(e["ty"])) + Vector2(0.5, 0.5)) * world.TPX
			world.camera_focus = _cam
			world._camera.zoom = Vector2(0.5, 0.5)
			return


func _say(text: String) -> void:
	message = text
	toast.text = text


# ---------------------------------------------------------------- input

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		var k: InputEventKey = event
		if k.keycode == KEY_G and not world._duel_open:
			toggle()
			get_viewport().set_input_as_handled()
			return
		if not active:
			return
		match k.keycode:
			KEY_ESCAPE:
				tool = ""
				tool_first = ""
				_say("")
			KEY_S:
				_on_tool("stop")
			KEY_A:
				_on_tool("amove")
			KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9:
				var n: int = k.keycode - KEY_0
				if k.ctrl_pressed:
					groups[n] = selected.duplicate()
					_say("Group %d set" % n)
				elif groups.has(n):
					selected = groups[n].duplicate()
		return
	if not active:
		return
	if event is InputEventMouseButton:
		var m: InputEventMouseButton = event
		if m.button_index == MOUSE_BUTTON_WHEEL_UP and m.pressed:
			world._camera.zoom = (world._camera.zoom * 1.1).clamp(Vector2(0.2, 0.2), Vector2(1.5, 1.5))
		elif m.button_index == MOUSE_BUTTON_WHEEL_DOWN and m.pressed:
			world._camera.zoom = (world._camera.zoom / 1.1).clamp(Vector2(0.2, 0.2), Vector2(1.5, 1.5))
		elif m.button_index == MOUSE_BUTTON_LEFT:
			if m.pressed:
				_drag_from = m.position
				_dragging = true
			elif _dragging:
				_dragging = false
				if _drag_from.distance_to(m.position) > 8.0:
					_box_select(Rect2(_drag_from, m.position - _drag_from).abs())
				else:
					_left_click(m.position)
		elif m.button_index == MOUSE_BUTTON_RIGHT and m.pressed:
			if tool != "":
				tool = ""
				tool_first = ""
			else:
				_right_click(m.position)
	elif event is InputEventMouseMotion:
		if _dragging:
			world.queue_redraw()


func _process(delta: float) -> void:
	if not active:
		return
	var dir := Vector2.ZERO
	if Input.is_key_pressed(KEY_LEFT):
		dir.x -= 1
	if Input.is_key_pressed(KEY_RIGHT):
		dir.x += 1
	if Input.is_key_pressed(KEY_UP):
		dir.y -= 1
	if Input.is_key_pressed(KEY_DOWN):
		dir.y += 1
	if Input.is_key_pressed(KEY_W):
		dir.y -= 1
	if Input.is_key_pressed(KEY_D):
		dir.x += 1
	if dir != Vector2.ZERO:
		_cam += dir.normalized() * 900.0 * delta / world._camera.zoom.x
		world.camera_focus = _cam
	_info_acc += delta
	if _info_acc > 0.25:
		_info_acc = 0.0
		_refresh_info()
		minimap.queue_redraw()
	world.selected_ids = {}
	for id in selected:
		world.selected_ids[str(id)] = true


func _on_tool(t: String) -> void:
	tool_first = ""
	if t == "deposits":
		if world.terrain != null:
			world.terrain.show_resources = not world.terrain.show_resources
			world.terrain._res_stamp = -10.0
			_say("Deposits shown: coal, iron, gold, stones, fish" if world.terrain.show_resources else "Deposits hidden")
		return
	if t == "stop":
		var reply: Dictionary = world._sim.op({"op": "stop", "units": _selected_units()})
		world._apply_snapshot(reply.get("snapshot", {}))
		_say("Stop")
		tool = ""
		return
	tool = t
	match t:
		"road":
			_say("Road: click two of your buildings")
		"move":
			_say("Move: click the ground")
		"attack":
			_say("Attack: click an enemy building")
		"amove":
			_say("Attack-move: click the ground; units fight what they meet")
		"rally":
			_say("Rally point: select a barracks or factory, then click the ground")
		"demolish":
			_say("Demolish: click one of your buildings")
		_:
			_say("Place: click a free tile")


# ---------------------------------------------------------------- picking

func _to_world(screen: Vector2) -> Vector2:
	return world.get_viewport().get_canvas_transform().affine_inverse() * screen


func _to_screen(wp: Vector2) -> Vector2:
	return world.get_viewport().get_canvas_transform() * wp


func _anchor(e: Dictionary) -> Vector2:
	return (Vector2(float(e.get("tx", 0)), float(e.get("ty", 0))) + Vector2(0.5, 0.5)) * world.TPX


func entity_by_id(id: String) -> Dictionary:
	for e in world._snapshot.get("entities", []):
		if str(e.get("id", "")) == id:
			return e
	return {}


func pick(screen: Vector2) -> Dictionary:
	var wp := _to_world(screen)
	var best: Dictionary = {}
	var best_d := 1.0e9
	for e in world._snapshot.get("entities", []):
		var kind := str(e.get("kind", ""))
		if str(e.get("class", "")) not in ["unit", "building"]:
			continue
		var a := _anchor(e)
		var rect: Rect2
		var bias := 0.0
		if str(e.get("class", "")) == "unit":
			rect = Rect2(a + Vector2(-30, -60), Vector2(60, 80))
			bias = -40.0  # units win over the building behind them
		elif e.has("hp"):
			rect = Rect2(a + Vector2(-60, -110), Vector2(120, 140))
		else:
			continue
		if not rect.has_point(wp):
			continue
		var d := a.distance_to(wp) + bias
		if d < best_d:
			best_d = d
			best = e
	return best


func _selected_units() -> Array:
	var out: Array = []
	for id in selected:
		var e := entity_by_id(str(id))
		if str(e.get("class", "")) == "unit" and str(e.get("faction_name", "")) == faction:
			out.append(str(id))
	return out


func _box_select(rect: Rect2) -> void:
	selected.clear()
	for e in world._snapshot.get("entities", []):
		if str(e.get("class", "")) != "unit" or str(e.get("faction_name", "")) != faction or not bool(e.get("alive", true)):
			continue
		if rect.has_point(_to_screen(_anchor(e) + Vector2(0, -16))):
			selected.append(str(e.get("id")))
	_say("%d units selected" % selected.size())
	world.queue_redraw()


func _left_click(screen: Vector2) -> void:
	var wp := _to_world(screen)
	var tile := Vector2i(int(floor(wp.x / world.TPX)), int(floor(wp.y / world.TPX)))
	var hit := pick(screen)
	if tool.begins_with("build:"):
		var kind := tool.substr(6)
		var reply: Dictionary = world._sim.op({"op": "build", "faction": faction, "kind": kind, "tx": tile.x, "ty": tile.y})
		world._apply_snapshot(reply.get("snapshot", {}))
		if str(reply.get("status", "")) == "ok":
			_say("Construction started. Connect it with a road.")
			selected = [str(reply.get("id", ""))]
			tool = ""
		else:
			_say("Cannot build: %s" % str(reply.get("reason", "?")))
		return
	if tool == "road":
		if hit.is_empty() or not hit.has("hp") or str(hit.get("faction_name", "")) != faction:
			_say("Road: click one of your buildings")
			return
		if tool_first == "":
			tool_first = str(hit.get("id"))
			_say("Road: now the second building")
			return
		var rr: Dictionary = world._sim.op({"op": "road", "faction": faction, "a": tool_first, "b": str(hit.get("id"))})
		world._apply_snapshot(rr.get("snapshot", {}))
		_say("Road built (%d tiles)" % int(rr.get("length", 0)) if str(rr.get("status", "")) == "ok" else "No road: %s" % str(rr.get("reason", "?")))
		tool_first = ""
		tool = ""
		return
	if tool == "move":
		var mr: Dictionary = world._sim.op({"op": "move", "units": _selected_units(), "tx": tile.x, "ty": tile.y})
		world._apply_snapshot(mr.get("snapshot", {}))
		_say("Moving %d units" % int(mr.get("moved", 0)))
		tool = ""
		return
	if tool == "attack":
		_attack(hit)
		tool = ""
		return
	if tool == "amove":
		var am: Dictionary = world._sim.op({"op": "move", "units": _selected_units(), "tx": tile.x, "ty": tile.y, "attack_move": true})
		world._apply_snapshot(am.get("snapshot", {}))
		_say("Attack-moving %d units" % int(am.get("moved", 0)))
		tool = ""
		return
	if tool == "rally":
		for id in selected:
			var rr2: Dictionary = world._sim.op({"op": "rally", "building": str(id), "tx": tile.x, "ty": tile.y})
			world._apply_snapshot(rr2.get("snapshot", {}))
			_say("Rally point: %s" % str(rr2.get("status", "")))
		tool = ""
		return
	if tool == "demolish":
		if not hit.is_empty() and hit.has("hp") and str(hit.get("faction_name", "")) == faction:
			var dr: Dictionary = world._sim.op({"op": "demolish", "building": str(hit.get("id"))})
			world._apply_snapshot(dr.get("snapshot", {}))
			_say("Demolish: %s" % str(dr.get("status", "")))
		tool = ""
		return
	selected = [str(hit.get("id"))] if not hit.is_empty() else []
	world.queue_redraw()


func _attack(hit: Dictionary) -> void:
	if hit.is_empty() or not hit.has("hp") or str(hit.get("faction_name", "")) == faction or str(hit.get("class", "")) == "unit":
		_say("Attack needs an enemy building")
		return
	var n := 0
	var last: Dictionary = {}
	for uid in _selected_units():
		last = world._sim.op({"op": "order", "unit": uid, "target": str(hit.get("id"))})
		if str(last.get("status", "")) == "ok":
			n += 1
	if not last.is_empty():
		world._apply_snapshot(last.get("snapshot", {}))
	_say("%d units attacking" % n)


func _right_click(screen: Vector2) -> void:
	if _selected_units().is_empty():
		return
	var hit := pick(screen)
	if not hit.is_empty() and hit.has("hp") and str(hit.get("faction_name", "")) != faction and str(hit.get("class", "")) != "unit":
		_attack(hit)
		return
	var wp := _to_world(screen)
	var reply: Dictionary = world._sim.op({"op": "move", "units": _selected_units(), "tx": int(floor(wp.x / world.TPX)), "ty": int(floor(wp.y / world.TPX))})
	world._apply_snapshot(reply.get("snapshot", {}))
	_say("Moving %d units" % int(reply.get("moved", 0)))


# ---------------------------------------------------------------- info panel

func _refresh_info() -> void:
	if selected.is_empty():
		info.text = "[b]%s[/b]\nLeft click: select. Drag: box. Right click: move / attack.\nG: back to the wizard." % faction
		if world.terrain != null:
			var mp := _to_world(world.get_viewport().get_mouse_position())
			info.text += "\n\n" + world.terrain.describe(int(floor(mp.x / world.TPX)), int(floor(mp.y / world.TPX)))
		_set_actions([], "")
		return
	var lines := ""
	var key := ""
	var buttons: Array = []
	for id in selected:
		var e := entity_by_id(str(id))
		if e.is_empty():
			continue
		var kind := str(e.get("kind", ""))
		lines += "[b]%s[/b]  (%s)\n" % [str(e.get("label", kind)), str(e.get("faction_name", ""))]
		if e.has("hp"):
			lines += "Health %d / %d\n" % [int(e.get("hp", 0)) / 100, int(e.get("max_hp", 0)) / 100]
		if e.has("constructing"):
			var c: Dictionary = e["constructing"]
			lines += "Under construction. Needs: %s\nProgress %d%%\n" % [str(c.get("cost", {})), int(100.0 * float(c.get("progress_ms", 0)) / 20000.0)]
		if str(e.get("class", "")) == "unit":
			lines += "Order: %s  status: %s\n" % [str(e.get("order", {}).get("kind", "none")), str(e.get("status", ""))]
		var stock: Dictionary = world._snapshot.get("stocks", {}).get(str(id), {})
		if str(e.get("class", "")) != "unit" and not stock.is_empty():
			var parts := ""
			for g in stock:
				if int(stock[g]) > 0:
					parts += "%s %d  " % [g, int(stock[g])]
			lines += "Stock: %s\n" % parts
		if str(e.get("faction_name", "")) == faction and e.has("queue") or (kind == "barracks" or kind == "vehicle_factory" or kind == "naval_yard" or kind == "sub_pen"):
			var q: Array = e.get("queue", [])
			for i in q.size():
				lines += "Queue %d: %s (%s)\n" % [i + 1, str(q[i].get("unit", "")), str(q[i].get("state", ""))]
			if str(e.get("faction_name", "")) == faction and bool(e.get("operational", true)):
				for ukind in recipes.get(kind, {}):
					buttons.append(["Queue %s" % str(recipes[kind][ukind].get("label", ukind)), "queue", str(id), ukind])
				for i in q.size():
					buttons.append(["Cancel #%d" % (i + 1), "cancel", str(id), str(i)])
			for ldef in locked.get(kind, {}):
				lines += "[color=#999999]Locked: %s[/color]\n" % str(locked[kind][ldef])
			if e.has("footprint"):
				lines += "Ships spawn on the water around this yard\n"
			key += "%s:%d:%s;" % [str(id), q.size(), str(e.get("operational", true))]
	info.text = lines
	_set_actions(buttons, key)


func _set_actions(buttons: Array, key: String) -> void:
	var k := key + str(buttons.size())
	if k == _last_actions_key:
		return
	_last_actions_key = k
	for c in actions.get_children():
		c.queue_free()
	for b in buttons:
		var btn := Button.new()
		btn.name = "Act_%s_%s" % [b[1], b[3]]
		btn.text = b[0]
		btn.pressed.connect(_on_action_button.bind(b))
		actions.add_child(btn)


func _on_action_button(b: Array) -> void:
	var reply: Dictionary
	if b[1] == "queue":
		reply = world._sim.op({"op": "queue", "building": b[2], "unit": b[3]})
	else:
		reply = world._sim.op({"op": "cancel", "building": b[2], "index": int(b[3])})
	world._apply_snapshot(reply.get("snapshot", {}))
	_say("%s: %s" % [b[0], str(reply.get("status", reply.get("reason", "")))])
	_last_actions_key = ""


# ---------------------------------------------------------------- minimap

func _mini_pos(tx: float, ty: float) -> Vector2:
	return Vector2(tx / MAP_TILES.x * MINI.x, ty / MAP_TILES.y * MINI.y)


func _draw_minimap() -> void:
	minimap.draw_rect(Rect2(Vector2.ZERO, MINI), Color(0.05, 0.08, 0.06, 0.9), true)
	if world.terrain != null and world.terrain.overview != null:
		minimap.draw_texture_rect(world.terrain.overview, Rect2(Vector2.ZERO, MINI), false)
	minimap.draw_rect(Rect2(Vector2.ZERO, MINI), Color(0.6, 0.6, 0.7), false, 2.0)
	var colors: Dictionary = {}
	for f in world._snapshot.get("factions", []):
		colors[str(f.get("name", ""))] = Color.html(str(f.get("color", "#ffffff")))
	for e in world._snapshot.get("entities", []):
		var kind := str(e.get("kind", ""))
		if str(e.get("class", "")) not in ["unit", "building"]:
			continue
		var c: Color = colors.get(str(e.get("faction_name", "")), Color.WHITE)
		var p := _mini_pos(float(e.get("tx", 0)), float(e.get("ty", 0)))
		if str(e.get("class", "")) == "unit":
			minimap.draw_circle(p, 2.0, c)
		elif e.has("hp"):
			minimap.draw_rect(Rect2(p - Vector2(2, 2), Vector2(4, 4)), c, true)
	var vp := world.get_viewport().get_visible_rect().size
	var top_left: Vector2 = _to_world(Vector2.ZERO) / float(world.TPX)
	var bottom_right: Vector2 = _to_world(vp) / float(world.TPX)
	minimap.draw_rect(Rect2(_mini_pos(top_left.x, top_left.y), _mini_pos(bottom_right.x - top_left.x, bottom_right.y - top_left.y)), Color.WHITE, false, 1.5)


func _minimap_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var p: Vector2 = event.position
		_cam = Vector2(p.x / MINI.x * MAP_TILES.x, p.y / MINI.y * MAP_TILES.y) * world.TPX
		world.camera_focus = _cam
		get_viewport().set_input_as_handled()


# ---------------------------------------------------------------- placement ghost

## The same rule the simulation applies (terrain build caps, water for yards), read from the received terrain.
## The simulation has the final word; this only colours the ghost.
func _site_ok(tile: Vector2i, size: String) -> bool:
	var t = world.terrain
	if t == null or size == "":
		return true
	if size == "water3":
		for dy in range(-1, 2):
			for dx in range(-1, 2):
				if t.class_name_at(tile.x + dx, tile.y + dy) != "water":
					return false
		return true
	if not t.in_bounds(tile.x, tile.y):
		return false
	var cap: int = t.build[tile.y * t.w + tile.x]
	var base := cap & 7
	match size:
		"mine":
			return base == 4
		"port":
			return (cap & 8) != 0
		"small":
			return base >= 1 and base <= 3
		"medium":
			return base >= 2 and base <= 3
		"big":
			return base == 3
	return base >= 1 and base <= 3


# ---------------------------------------------------------------- overlay in world space

func draw_overlay(canvas: CanvasItem) -> void:
	if not active:
		return
	var tpx: float = world.TPX
	if tool.begins_with("build:"):
		var mp := _to_world(world.get_viewport().get_mouse_position())
		var tile := Vector2(floor(mp.x / tpx), floor(mp.y / tpx))
		var size := str(menu.get(tool.substr(6), {}).get("size", ""))
		var ok := _site_ok(Vector2i(int(tile.x), int(tile.y)), size)
		var col := Color(0.3, 1.0, 0.4) if ok else Color(1.0, 0.3, 0.25)
		var rect := Rect2(tile * tpx, Vector2(tpx, tpx))
		if size == "water3":
			rect = Rect2((tile - Vector2(1, 1)) * tpx, Vector2(tpx * 3, tpx * 3))
		canvas.draw_rect(rect, Color(col.r, col.g, col.b, 0.3), true)
		canvas.draw_rect(rect, col, false, 3.0)
	if tool_first != "":
		var e := entity_by_id(tool_first)
		if not e.is_empty():
			canvas.draw_arc(_anchor(e), 60.0, 0.0, TAU, 32, Color(1, 1, 0.3), 4.0)
	if _dragging and tool == "":
		var cur := world.get_viewport().get_mouse_position()
		if _drag_from.distance_to(cur) > 8.0:
			var a := _to_world(_drag_from)
			var b := _to_world(cur)
			canvas.draw_rect(Rect2(a, b - a).abs(), Color(0.4, 1.0, 0.4, 0.18), true)
			canvas.draw_rect(Rect2(a, b - a).abs(), Color(0.4, 1.0, 0.4), false, 3.0)
