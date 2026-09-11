extends Control
class_name PuzzleTestMenu

## Puzzle Test Menu - allows testing all 50 catalogue puzzles in isolation
## Uses placeholder graphics (colored rectangles) to clearly communicate puzzle state

const _Runner = preload("res://client/scripts/puzzle_test_runner.gd")

@onready var vbox = $Panel/ScrollContainer/VBoxContainer
@onready var btn_run = $Panel/BottomBar/BtnRun
@onready var btn_close = $Panel/BottomBar/BtnClose
@onready var info_label = $Panel/InfoLabel

var selected_puzzle_id: int = -1
var puzzle_buttons: Array[Button] = []

# Puzzle catalogue matching docs/Duel_Master_Battle_Puzzle_Catalogue.txt
const PUZZLES: Array[Dictionary] = [
	{"id": 1, "name": "The Four Offerings", "type": "offerings", "mechanics": "M1, M14, M0", "desc": "Place correct objects into four described alcoves"},
	{"id": 2, "name": "Clockwise / Turn Back", "type": "clockwise", "mechanics": "M8, M15, M0", "desc": "Cross a loop in the correct directional sequence"},
	{"id": 3, "name": "The Serpent Path", "type": "serpent", "mechanics": "M7, M0", "desc": "Wind through safe route; shortcuts reset you"},
	{"id": 4, "name": "Drop It Below", "type": "drop_below", "mechanics": "M0, M15", "desc": "Drop object through floor to retrieve it lower"},
	{"id": 5, "name": "Two Ends of the Hall", "type": "two_ends", "mechanics": "M0, M5", "desc": "Two distant mechanisms must both be active"},
	{"id": 6, "name": "Timed Gate Run", "type": "timed_gate", "mechanics": "M5, M6", "desc": "Switch opens gate briefly; traverse before it closes"},
	{"id": 7, "name": "Revealed Pits", "type": "revealed_pits", "mechanics": "M5, M15, M9", "desc": "Plate/lens/spell reveals which tiles are pits"},
	{"id": 8, "name": "Secret Switch Chain", "type": "secret_chain", "mechanics": "M0, M15", "desc": "Hidden switch reveals next, eventually opens route"},
	{"id": 9, "name": "The Old Wish", "type": "old_wish", "mechanics": "M1, M14, M0", "desc": "Place a mundane token in a ceremonial receptacle"},
	{"id": 10, "name": "Release the Cells", "type": "release_cells", "mechanics": "M4, M5, M15", "desc": "Pressure mechanism holds side chambers shut"},
	{"id": 11, "name": "The Useless Object", "type": "useless_object", "mechanics": "M1, M9/M15", "desc": "Item seems useless but essential in special environment"},
	{"id": 12, "name": "Mosaic Floor", "type": "mosaic", "mechanics": "M0, M5", "desc": "Patterned floor with safe/unsafe symbols"},
	{"id": 13, "name": "False Door, Real Drop", "type": "false_door", "mechanics": "M5, M7", "desc": "Inviting door triggers concealed pit"},
	{"id": 14, "name": "Left Lever / Right Lever", "type": "left_right", "mechanics": "M0", "desc": "Two similar controls; clue identifies safe one"},
	{"id": 15, "name": "Damaged Map", "type": "damaged_map", "mechanics": "M0, M1", "desc": "Map fragments; identify landmarks while navigating"},
	{"id": 16, "name": "The Lying Guide", "type": "lying_guide", "mechanics": "M12, M0", "desc": "NPC gives false directions; inconsistencies reveal truth"},
	{"id": 17, "name": "Fair Exchange", "type": "fair_exchange", "mechanics": "M1, M14", "desc": "Take object by leaving acceptable replacement"},
	{"id": 18, "name": "Watch How They Escape", "type": "watch_escape", "mechanics": "M12, M15", "desc": "NPC demonstrates secret mechanism by fleeing"},
	{"id": 19, "name": "The False Treasure", "type": "false_treasure", "mechanics": "M1, M0", "desc": "Ornate container distracts; item in mundane object"},
	{"id": 20, "name": "Missing Gear", "type": "missing_gear", "mechanics": "M1, M14, M13", "desc": "Machine lacks component; find and install it"},
	{"id": 21, "name": "Hold Plate with Object", "type": "hold_plate", "mechanics": "M2, M4, M5", "desc": "Leave heavy object on plate to hold gate open"},
	{"id": 22, "name": "Weapon That Closes Pit", "type": "weapon_pit", "mechanics": "M1+M5, M3+M5", "desc": "Desirable object acts as switch; removing opens pit"},
	{"id": 23, "name": "Take One, Leave One", "type": "take_leave", "mechanics": "M1, M14", "desc": "Two items in cradle; taking both activates trap"},
	{"id": 24, "name": "Ram Gallery", "type": "ram_gallery", "mechanics": "M6, M11", "desc": "Pistons/blades periodically block corridor; read rhythm"},
	{"id": 25, "name": "Cycling Teleport Field", "type": "cycling_teleport", "mechanics": "M6, M7, M11", "desc": "Portal cycles between exit points; enter at right moment"},
	{"id": 26, "name": "Redirect the Energy", "type": "redirect_energy", "mechanics": "M10, M9, M13", "desc": "Rotate reflectors to route energy from emitter to receiver"},
	{"id": 27, "name": "Replace the Burnt Fuse", "type": "replace_fuse", "mechanics": "M1, M14, M13", "desc": "Subsystem dead from failed component; replace it"},
	{"id": 28, "name": "Bring Facility Online", "type": "facility_online", "mechanics": "M13, M0", "desc": "Several puzzles restore subsystems; final machine needs all"},
	{"id": 29, "name": "Throw to Remote Switch", "type": "throw_switch", "mechanics": "M3, M4", "desc": "Throw object onto unreachable floor plate"},
	{"id": 30, "name": "Throw Through Portal", "type": "throw_portal", "mechanics": "M3, M7, M4", "desc": "Throw object into portal to activate remote mechanism"},
	{"id": 31, "name": "Enemy on Plate", "type": "enemy_plate", "mechanics": "M4, enemy", "desc": "Enemy must occupy pressure plate; killing is counterproductive"},
	{"id": 32, "name": "Four Creature Seals", "type": "four_seals", "mechanics": "M4, enemy, M13", "desc": "Several creatures must simultaneously occupy zones"},
	{"id": 33, "name": "Fireball Circuit", "type": "fireball_circuit", "mechanics": "M6, M11, M10/M4", "desc": "Repeating projectile follows loop; create safe windows"},
	{"id": 34, "name": "Magic Rebounds Here", "type": "magic_rebound", "mechanics": "M9, M10/M5", "desc": "Direct spell reflects; force environmental solution"},
	{"id": 35, "name": "Light Reveals False Geometry", "type": "light_reveals", "mechanics": "M9, M15, M5", "desc": "Walls/pits/doors are illusions; Light exposes them"},
	{"id": 36, "name": "Stone Jams Machine", "type": "stone_jams", "mechanics": "M9+M6/M11/M5", "desc": "Stone magic immobilises moving mechanism"},
	{"id": 37, "name": "Water Changes Room", "type": "water_changes", "mechanics": "M9, M5/M13", "desc": "Water magic alters environmental state (fill, cool, reveal)"},
	{"id": 38, "name": "Fire Creates Route", "type": "fire_route", "mechanics": "M9, M15/M13", "desc": "Fire used constructively (burn vines, light braziers, heat metal)"},
	{"id": 39, "name": "Companion Holds Other Side", "type": "companion", "mechanics": "M12, M4/M5", "desc": "Scripted companion operates mechanism while player traverses"},
	{"id": 40, "name": "Room Changes on Prize", "type": "room_changes", "mechanics": "M1, M13, M5/M6", "desc": "Removing reward changes return route (hazards, bridge, lights)"},
	{"id": 41, "name": "Sound Sequence", "type": "sound_sequence", "mechanics": "M0, M8", "desc": "Hear/discover sequence; reproduce with bells/crystals/switches"},
	{"id": 42, "name": "Follow the Footprints", "type": "footprints", "mechanics": "M0, M15", "desc": "Different tracks cross room; follow correct one"},
	{"id": 43, "name": "The Counterweight", "type": "counterweight", "mechanics": "M2, M4/M14, M5", "desc": "Removing object changes paired platform elsewhere"},
	{"id": 44, "name": "Drain / Flood Route Swap", "type": "drain_flood", "mechanics": "M13, M5", "desc": "Choose flooded or drained state; changes passages"},
	{"id": 45, "name": "One-Way Collapsing Floor", "type": "collapsing_floor", "mechanics": "M6, M5, M7", "desc": "Tiles collapse after stepping; commit to movement"},
	{"id": 46, "name": "Door Opens Behind You", "type": "door_behind", "mechanics": "M0, M15", "desc": "Switch opens route outside current view"},
	{"id": 47, "name": "Wrong Answer Changes Dungeon", "type": "wrong_answer", "mechanics": "M0, M13", "desc": "Wrong choices alter environment (release guardian, flood)"},
	{"id": 48, "name": "Object as Clue, Not Key", "type": "object_clue", "mechanics": "M1", "desc": "Inventory item useful for info on it, not fitting a slot"},
	{"id": 49, "name": "Return Later with New Magic", "type": "return_later", "mechanics": "M9, M15/M5", "desc": "Previously unsolvable obstacle solved by new spell"},
	{"id": 50, "name": "Multi-Solution Room", "type": "multi_solution", "mechanics": "Combination", "desc": "One obstacle supports several legitimate solutions"},
]

func _ready() -> void:
	_populate_list()
	btn_run.pressed.connect(_on_run_pressed)
	btn_close.pressed.connect(_on_close_pressed)

func _populate_list() -> void:
	for puzzle in PUZZLES:
		var btn = Button.new()
		btn.text = "%02d. %s" % [puzzle.id, puzzle.name]
		btn.tooltip_text = "%s\nMechanics: %s" % [puzzle.desc, puzzle.mechanics]
		btn.add_theme_stylebox_override("normal", _make_button_style())
		btn.add_theme_stylebox_override("hover", _make_button_style(Color(0.3, 0.25, 0.45)))
		btn.add_theme_stylebox_override("pressed", _make_button_style(Color(0.2, 0.18, 0.35)))
		btn.add_theme_font_size_override("font_size", 20)
		btn.focus_mode = Control.FOCUS_ALL
		btn.pressed.connect(_on_puzzle_selected.bind(puzzle.id))
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

func _get_font(size: int) -> FontFile:
	# Use default theme font
	return ThemeDB.get_fallback_font().duplicate() as FontFile

func _on_puzzle_selected(id: int) -> void:
	selected_puzzle_id = id
	for i in range(puzzle_buttons.size()):
		var btn = puzzle_buttons[i]
		var is_selected = (i + 1) == id
		var bg = Color("#3a2f5e") if is_selected else Color("#221c3d")
		btn.custom_styles.normal = _make_button_style(bg)
	var puzzle = PUZZLES.find(func(p): return p.id == id)
	if puzzle:
		info_label.text = "%02d. %s\n%s\nMechanics: %s" % [puzzle.id, puzzle.name, puzzle.desc, puzzle.mechanics]

func _on_run_pressed() -> void:
	if selected_puzzle_id < 1:
		return
	var puzzle = PUZZLES.find(func(p): return p.id == selected_puzzle_id)
	if not puzzle:
		return
	
	# Store selection first, then launch the test scene (which reads it in _ready).
	_Runner.set_puzzle(puzzle)
	get_tree().change_scene_to_file("res://client/scenes/puzzle_test_room.tscn")

func _on_close_pressed() -> void:
	get_tree().quit()