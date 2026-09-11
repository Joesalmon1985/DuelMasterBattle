extends Control
## Puzzle test menu: lists the fifty DmbPuzzleRooms catalogue rooms and
## launches the isolated test-room driver for the chosen one.
## Room data comes from DmbPuzzleRooms.all() — the single source of truth —
## so the menu can never drift from the playable rooms.

const Rooms = preload("res://sim/world/puzzle_rooms.gd")
const Runner = preload("res://client/scripts/puzzle_test_runner.gd")

@onready var vbox = $Panel/ScrollContainer/VBoxContainer
@onready var btn_run = $Panel/BottomBar/BtnRun
@onready var btn_close = $Panel/BottomBar/BtnClose
@onready var info_label = $Panel/InfoLabel

var selected_room_id := ""
var room_list: Array = []
var puzzle_buttons: Array[Button] = []

func _ready() -> void:
	_load_rooms()
	_populate_list()
	btn_run.pressed.connect(_on_run_pressed)
	btn_close.pressed.connect(_on_close_pressed)

func _load_rooms() -> void:
	room_list = Rooms.all()
	room_list.sort_custom(func(a, b): return int(a["num"]) < int(b["num"]))

func _populate_list() -> void:
	for r in room_list:
		var rid := str(r["id"])
		var btn = Button.new()
		btn.text = "%02d. %s" % [int(r["num"]), str(r["title"])]
		btn.tooltip_text = "%s\nMechanics: %s" % [str(r.get("hint", "")), str(r.get("mechanics", ""))]
		btn.add_theme_stylebox_override("normal", _make_button_style())
		btn.add_theme_stylebox_override("hover", _make_button_style(Color(0.3, 0.25, 0.45)))
		btn.add_theme_stylebox_override("pressed", _make_button_style(Color(0.2, 0.18, 0.35)))
		btn.add_theme_font_size_override("font_size", 20)
		btn.focus_mode = Control.FOCUS_ALL
		btn.pressed.connect(_on_puzzle_selected.bind(rid))
		vbox.add_child(btn)
		puzzle_buttons.append(btn)

func _make_button_style(bg: Color = Color("#221c3d")) -> StyleBoxFlat:
	var s = StyleBoxFlat.new()
	s.bg_color = bg
	s.set_corner_radius_all(8)
	s.content_margin_left = 16
	s.content_margin_right = 16
	s.content_margin_top = 10
	s.content_margin_bottom = 10
	s.border_color = Color("#6b5ce7")
	s.set_border_width_all(1)
	return s

func _room_by_id(rid: String) -> Dictionary:
	for r in room_list:
		if str(r["id"]) == rid:
			return r
	return {}

func _on_puzzle_selected(rid: String) -> void:
	selected_room_id = rid
	for i in range(puzzle_buttons.size()):
		var btn = puzzle_buttons[i]
		var is_selected = str(room_list[i]["id"]) == rid
		var bg = Color("#3a2f5e") if is_selected else Color("#221c3d")
		btn.add_theme_stylebox_override("normal", _make_button_style(bg))
		btn.add_theme_stylebox_override("hover", _make_button_style(Color("#4a3f7e") if is_selected else Color(0.3, 0.25, 0.45)))
	var r := _room_by_id(rid)
	if not r.is_empty():
		info_label.text = "%s — %s\n%s\nMechanics: %s" % [rid, str(r["title"]), str(r.get("hint", "")), str(r.get("mechanics", ""))]

func _on_run_pressed() -> void:
	if selected_room_id == "" or _room_by_id(selected_room_id).is_empty():
		return
	# Store selection first, then launch the test scene (which reads it in _ready).
	Runner.set_puzzle(selected_room_id)
	get_tree().change_scene_to_file("res://client/scenes/overworld.tscn")

func _on_close_pressed() -> void:
	get_tree().quit()
