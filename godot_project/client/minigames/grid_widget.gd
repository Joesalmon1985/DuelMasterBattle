extends Control

const Tile = preload("res://client/minigames/tile_widget.gd")

## The sliding-blocks board: a grid of cells, blocks of one or more cells in a chalk colour, gates on the rim in the same colours. A tap on a block
## selects it; a tap on a free cell in the same row or column slides it that way (one action per step, the host decides what is legal); the arrow
## keys do the same for the selected block. Area: {w, h, blocks: [{id, cells: [[x, y], ...], colour, text}], gates: [{side, pos, colour}],
## selected, moves: [{"id": "move", "block", "dir"}] (the legal moves, for the arrows), skin: {block, gate}}.

var area: Dictionary = {}
var table: Node = null
var selected := ""
var _cell := 40.0
var _w := 6
var _h := 6
var _origin := Vector2(24, 24)


func configure(p_area: Dictionary, p_table: Node) -> void:
	area = p_area
	table = p_table
	selected = str(p_area.get("selected", p_table._grid_selection if p_table != null else ""))
	_w = maxi(int(p_area.get("w", 6)), 1)
	_h = maxi(int(p_area.get("h", 6)), 1)
	name = "Grid"
	mouse_filter = Control.MOUSE_FILTER_STOP
	focus_mode = Control.FOCUS_ALL
	size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var px := float(p_area.get("size", 40))
	_cell = px
	custom_minimum_size = Vector2(px * _w + 48, px * _h + 48)


func _block_at(x: int, y: int) -> Dictionary:
	for b in area.get("blocks", []):
		for c in b.get("cells", []):
			if int(c[0]) == x and int(c[1]) == y:
				return b
	return {}


func _cell_of(pos: Vector2) -> Vector2i:
	var p := (pos - _origin) / _cell
	return Vector2i(int(floor(p.x)), int(floor(p.y)))


func _move(dir: String) -> void:
	if selected == "" or table == null:
		return
	for m in area.get("moves", []):
		if str(m.get("block", "")) == selected and str(m.get("dir", "")) == dir:
			table._grid_selection = selected
			table.widget_act({"id": "move", "block": selected, "dir": dir})
			return
	var sfx := get_node_or_null("/root/Sfx")
	if sfx:
		sfx.denied()


func _gui_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		var dir := ""
		match (event as InputEventKey).keycode:
			KEY_LEFT, KEY_A: dir = "w"
			KEY_RIGHT, KEY_D: dir = "e"
			KEY_UP, KEY_W: dir = "n"
			KEY_DOWN, KEY_S: dir = "s"
		if dir != "":
			accept_event()
			_move(dir)
		return
	var tap: bool = (event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT) or (event is InputEventScreenTouch and event.pressed)
	if not tap:
		return
	accept_event()
	grab_focus()
	var c := _cell_of(event.position)
	var hit := _block_at(c.x, c.y)
	if not hit.is_empty():
		selected = str(hit.get("id", ""))
		if table != null:
			table._grid_selection = selected
		queue_redraw()
		return
	if selected == "":
		return
	# a free cell: slide the selected block towards it if it is in line with the block
	var sel: Dictionary = {}
	for b in area.get("blocks", []):
		if str(b.get("id", "")) == selected:
			sel = b
	if sel.is_empty():
		return
	var cells: Array = sel.get("cells", [])
	var same_row := false
	var same_col := false
	var cx := 0.0
	var cy := 0.0
	for cc in cells:
		cx += float(cc[0])
		cy += float(cc[1])
		if int(cc[1]) == c.y:
			same_row = true
		if int(cc[0]) == c.x:
			same_col = true
	cx /= maxf(cells.size(), 1)
	cy /= maxf(cells.size(), 1)
	if same_row and not same_col:
		_move("e" if c.x > cx else "w")
	elif same_col and not same_row:
		_move("s" if c.y > cy else "n")
	elif c.x < 0 or c.x >= _w or c.y < 0 or c.y >= _h:  # a tap on the rim: out through the gate on that side
		if c.y < 0:
			_move("n")
		elif c.y >= _h:
			_move("s")
		elif c.x < 0:
			_move("w")
		else:
			_move("e")


func _draw() -> void:
	var font := get_theme_default_font()
	_origin = Vector2(24, 24)
	var board := Rect2(_origin, Vector2(_cell * _w, _cell * _h))
	draw_rect(board, Color(0.26, 0.23, 0.2))
	for x in range(_w + 1):
		draw_line(_origin + Vector2(x * _cell, 0), _origin + Vector2(x * _cell, _cell * _h), Color(0.35, 0.32, 0.28), 1.0)
	for y in range(_h + 1):
		draw_line(_origin + Vector2(0, y * _cell), _origin + Vector2(_cell * _w, y * _cell), Color(0.35, 0.32, 0.28), 1.0)
	for g in area.get("gates", []):
		var col: Color = Tile.colour_of(g.get("colour", -1))
		var pos := int(g.get("pos", 0))
		var span := int(g.get("span", 1))
		var r: Rect2
		match str(g.get("side", "n")):
			"n": r = Rect2(_origin + Vector2(pos * _cell, -14), Vector2(_cell * span, 12))
			"s": r = Rect2(_origin + Vector2(pos * _cell, _cell * _h + 2), Vector2(_cell * span, 12))
			"w": r = Rect2(_origin + Vector2(-14, pos * _cell), Vector2(12, _cell * span))
			_: r = Rect2(_origin + Vector2(_cell * _w + 2, pos * _cell), Vector2(12, _cell * span))
		draw_rect(r, col)
	for b in area.get("blocks", []):
		var col: Color = Tile.colour_of(b.get("colour", -1))
		var is_sel := str(b.get("id", "")) == selected
		var cells: Array = b.get("cells", [])
		for c in cells:
			var r := Rect2(_origin + Vector2(int(c[0]) * _cell + 2, int(c[1]) * _cell + 2), Vector2(_cell - 4, _cell - 4))
			draw_rect(r, col)
			if is_sel:
				draw_rect(r, Color(0.98, 0.9, 0.5), false, 3.0)
		if not cells.is_empty():
			var c0 = cells[0]
			var t := str(b.get("text", ""))
			if t != "":
				draw_string(font, _origin + Vector2(int(c0[0]) * _cell + 6, int(c0[1]) * _cell + _cell * 0.65), t, HORIZONTAL_ALIGNMENT_LEFT, -1, int(_cell * 0.4), Color(0.08, 0.06, 0.1))
