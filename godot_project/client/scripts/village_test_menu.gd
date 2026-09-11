extends Control
## Village test menu: lists available village test profiles and
## launches the normal production overworld.tscn for the chosen one.

const Profiles = preload("res://sim/world/village_test_profiles.gd")
const Runner = preload("res://client/scripts/village_test_runner.gd")

@onready var vbox = $Panel/ScrollContainer/VBoxContainer
@onready var btn_run = $Panel/BottomBar/BtnRun
@onready var btn_close = $Panel/BottomBar/BtnClose
@onready var info_label = $Panel/InfoLabel
@onready var profile_details = $Panel/ProfileDetails

var selected_profile_id := ""
var profile_list: Array = []
var profile_buttons: Array[Button] = []

func _ready() -> void:
	_load_profiles()
	_populate_list()
	btn_run.pressed.connect(_on_run_pressed)
	btn_close.pressed.connect(_on_close_pressed)

func _load_profiles() -> void:
	profile_list = Profiles.all()
	# Sort by ID
	profile_list.sort_custom(func(a, b): return str(a["id"]) < str(b["id"]))

func _populate_list() -> void:
	for p in profile_list:
		var pid := str(p["id"])
		var btn = Button.new()
		btn.text = pid + " — " + str(p["name"])
		btn.tooltip_text = str(p["description"])
		btn.add_theme_stylebox_override("normal", _make_button_style())
		btn.add_theme_stylebox_override("hover", _make_button_style(Color(0.3, 0.25, 0.45)))
		btn.add_theme_stylebox_override("pressed", _make_button_style(Color(0.2, 0.18, 0.35)))
		btn.add_theme_font_size_override("font_size", 20)
		btn.focus_mode = Control.FOCUS_ALL
		btn.pressed.connect(_on_profile_selected.bind(pid))
		vbox.add_child(btn)
		profile_buttons.append(btn)
	
	# Auto-select first
	if profile_list.size() > 0:
		_on_profile_selected(str(profile_list[0]["id"]))

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

func _profile_by_id(pid: String) -> Dictionary:
	for p in profile_list:
		if str(p["id"]) == pid:
			return p
	return {}

func _on_profile_selected(pid: String) -> void:
	selected_profile_id = pid
	for i in range(profile_buttons.size()):
		var btn = profile_buttons[i]
		var is_selected = str(profile_list[i]["id"]) == pid
		var bg = Color("#3a2f5e") if is_selected else Color("#221c3d")
		btn.add_theme_stylebox_override("normal", _make_button_style(bg))
		btn.add_theme_stylebox_override("hover", _make_button_style(Color("#4a3f7e") if is_selected else Color(0.3, 0.25, 0.45)))
	
	var p := _profile_by_id(pid)
	if not p.is_empty():
		var hexes = ", ".join(p["hexes"])
		var primary = ", ".join(p["primary_workers"])
		var processing = ", ".join(p["processing_buildings"])
		var generic = ", ".join(p["generic_cast"])
		var stories = ""
		for s in p["pilot_stories"]:
			stories += "\n  • " + s["id"] + ": " + s["title"]
		
		info_label.text = "[b]Economic Profile:[/b] %s\n[b]Resources:[/b] %s\n[b]Primary Workers:[/b] %s\n[b]Processing:[/b] %s\n[b]Civic Cast:[/b] %s\n[b]Pilot Stories:[/b]%s" % [
			str(p["economic_profile"]), hexes, primary, processing, generic, stories
		]

func _on_run_pressed() -> void:
	if selected_profile_id == "" or _profile_by_id(selected_profile_id).is_empty():
		return
	Runner.set_profile(selected_profile_id)
	get_tree().change_scene_to_file("res://client/scenes/overworld.tscn")

func _on_close_pressed() -> void:
	get_tree().quit()