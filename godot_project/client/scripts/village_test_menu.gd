extends Control
## Village test menu: discovers available village test profiles and
## launches the normal production overworld.tscn for the chosen one.

const Catalog = preload("res://sim/world/village_test_catalog.gd")
const Runner = preload("res://client/scripts/village_test_runner.gd")

@onready var vbox = $Panel/ScrollContainer/VBoxContainer
@onready var btn_run = $Panel/BottomBar/BtnRun
@onready var btn_close = $Panel/BottomBar/BtnClose
@onready var details_panel = $Panel/DetailsPanel
@onready var search_box = $Panel/TopBar/SearchBox
@onready var filter_profile = $Panel/TopBar/FilterProfile
@onready var status_label = $Panel/TopBar/StatusLabel

var all_fixtures: Array = []
var filtered_fixtures: Array = []
var profile_buttons: Array[Button] = []
var selected_profile_id := ""
var current_filter_profile := ""
var search_text := ""
## Generated (production) settlements: world seed + turns typed in the top bar;
## every settlement/town node of that world is listed as "gen:<seed>:<node>:<turns>".
var gen_seed := 5
var gen_turns := Runner.DEFAULT_TURNS
var seed_box: SpinBox
var turns_box: SpinBox
const GEN_PROFILE_LABEL := "Generated (seed/node)"

func _ready() -> void:
    _build_generated_controls()
    _discover_fixtures()
    _apply_filters()
    _populate_list()
    btn_run.pressed.connect(_on_run_pressed)
    btn_close.pressed.connect(_on_close_pressed)
    search_box.text_changed.connect(_on_search_changed)
    filter_profile.item_selected.connect(_on_filter_changed)
    _update_run_button()

func _build_generated_controls() -> void:
    var top = $Panel/TopBar
    var lbl = Label.new()
    lbl.text = "World seed"
    lbl.add_theme_font_size_override("font_size", 14)
    top.add_child(lbl)
    top.move_child(lbl, 1)
    seed_box = SpinBox.new()
    seed_box.min_value = 0
    seed_box.max_value = 999999
    seed_box.value = gen_seed
    seed_box.custom_minimum_size = Vector2(110, 0)
    seed_box.value_changed.connect(_on_gen_changed)
    top.add_child(seed_box)
    top.move_child(seed_box, 2)
    var lbl2 = Label.new()
    lbl2.text = "Turns"
    lbl2.add_theme_font_size_override("font_size", 14)
    top.add_child(lbl2)
    top.move_child(lbl2, 3)
    turns_box = SpinBox.new()
    turns_box.min_value = 0
    turns_box.max_value = 200
    turns_box.value = gen_turns
    turns_box.custom_minimum_size = Vector2(90, 0)
    turns_box.value_changed.connect(_on_gen_changed)
    top.add_child(turns_box)
    top.move_child(turns_box, 4)

func _on_gen_changed(_v: float) -> void:
    gen_seed = int(seed_box.value)
    gen_turns = int(turns_box.value)
    _discover_fixtures()
    _apply_filters()
    _populate_list()

## Production settlements of the chosen world, in the same list shape as fixtures.
func _generated_entries() -> Array:
    var out: Array = []
    for c in Runner.generated_choices(gen_seed, gen_turns):
        var nid := int(c["node"])
        out.append({
            "id": Runner.generated_id(gen_seed, nid, gen_turns),
            "name": "%s — node %d%s" % [str(c["name"]), nid, " (John's home)" if bool(c["home"]) else ""],
            "valid": true,
            "generated": true,
            "economic_profile": GEN_PROFILE_LABEL,
            "description": str(c["summary"]),
            "kind": str(c["kind"]), "owner": str(c["owner"]), "node": nid, "seed": gen_seed, "turns": gen_turns,
        })
    return out

func _discover_fixtures() -> void:
    all_fixtures = _generated_entries() + Catalog.discover()
    # Populate filter dropdown
    filter_profile.clear()
    filter_profile.add_item("All Profiles", -1)
    var profiles_seen: Array = []
    for f in all_fixtures:
        var ep = str(f.get("economic_profile", "Unknown"))
        if not profiles_seen.has(ep):
            profiles_seen.append(ep)
            filter_profile.add_item(ep, profiles_seen.size() - 1)
    var gen_n := 0
    for f in all_fixtures:
        if bool(f.get("generated", false)):
            gen_n += 1
    status_label.text = "%d generated settlement(s) in world %d @ turn %d, %d authored fixture(s)" % [gen_n, gen_seed, gen_turns, all_fixtures.size() - gen_n]

func _apply_filters() -> void:
    filtered_fixtures.clear()
    for f in all_fixtures:
        var match_search = search_text == "" or \
            str(f["id"]).to_lower().contains(search_text.to_lower()) or \
            str(f["name"]).to_lower().contains(search_text.to_lower())
        var match_profile = current_filter_profile == "" or \
            str(f.get("economic_profile", "")) == current_filter_profile
        if match_search and match_profile:
            filtered_fixtures.append(f)

func _on_search_changed(text: String) -> void:
    search_text = text
    _apply_filters()
    _populate_list()

func _on_filter_changed(idx: int) -> void:
    current_filter_profile = filter_profile.get_item_metadata(idx)
    _apply_filters()
    _populate_list()

func _populate_list() -> void:
    # Clear existing buttons
    for btn in profile_buttons:
        btn.queue_free()
    profile_buttons.clear()
    
    # Create new buttons
    for f in filtered_fixtures:
        var fid := str(f["id"])
        var btn = Button.new()
        var display_name = fid
        if f.get("valid", true):
            display_name += " — " + str(f["name"])
        else:
            display_name += " — INVALID"
        btn.text = display_name
        btn.tooltip_text = str(f.get("description", ""))
        btn.add_theme_stylebox_override("normal", _make_button_style(f.get("valid", true)))
        btn.add_theme_stylebox_override("hover", _make_button_style(f.get("valid", true), Color(0.3, 0.25, 0.45)))
        btn.add_theme_stylebox_override("pressed", _make_button_style(f.get("valid", true), Color(0.2, 0.18, 0.35)))
        btn.add_theme_font_size_override("font_size", 18)
        btn.focus_mode = Control.FOCUS_ALL
        # Allow selection of invalid fixtures for inspection, but they can't be played
        btn.pressed.connect(_on_profile_selected.bind(fid))
        vbox.add_child(btn)
        profile_buttons.append(btn)
    
    # Auto-select first (valid or invalid)
    selected_profile_id = ""
    for f in filtered_fixtures:
        _on_profile_selected(str(f["id"]))
        break
    _update_run_button()

func _make_button_style(valid: bool = true, bg: Color = Color("#221c3d")) -> StyleBoxFlat:
    var s = StyleBoxFlat.new()
    s.bg_color = bg if valid else Color("#3d1c1c")
    s.set_corner_radius_all(8)
    s.content_margin_left = 16
    s.content_margin_right = 16
    s.content_margin_top = 10
    s.content_margin_bottom = 10
    s.border_color = Color("#6b5ce7") if valid else Color("#e75c5c")
    s.set_border_width_all(1)
    return s

func _on_profile_selected(fid: String) -> void:
    selected_profile_id = fid
    for i in range(profile_buttons.size()):
        var btn = profile_buttons[i]
        var f = filtered_fixtures[i]
        var is_selected = str(f["id"]) == fid
        var base_bg = Color("#3a2f5e") if is_selected else (Color("#221c3d") if f.get("valid", true) else Color("#3d1c1c"))
        var hover_bg = Color("#4a3f7e") if is_selected else (Color(0.3, 0.25, 0.45) if f.get("valid", true) else Color("#5d2c2c"))
        btn.add_theme_stylebox_override("normal", _make_button_style(f.get("valid", true), base_bg))
        btn.add_theme_stylebox_override("hover", _make_button_style(f.get("valid", true), hover_bg))
    
    # Update details panel
    var fixture = _fixture_by_id(fid)
    if not fixture.is_empty():
        _update_details_panel(fixture)

func _fixture_by_id(fid: String) -> Dictionary:
    for f in filtered_fixtures:
        if str(f["id"]) == fid:
            return f
    return {}

func _update_details_panel(f: Dictionary) -> void:
    if bool(f.get("generated", false)):
        _update_generated_details(f)
        return
    if not f.get("valid", true):
        details_panel.get_node("ValidLabel").text = "[color=red]INVALID FIXTURE[/color]"
        details_panel.get_node("ValidLabel").visible = true
        details_panel.get_node("DetailsContent").visible = false
        
        # Show validation errors prominently
        var errors = f.get("errors", [])
        var error_text = ""
        for err in errors:
            error_text += "[color=red]• " + str(err) + "[/color]\n"
        if error_text == "":
            error_text = "[color=red]• Unknown validation error[/color]"
        details_panel.get_node("ValidLabel").text = "[color=red]INVALID FIXTURE[/color]\n\n" + error_text
        return
    
    details_panel.get_node("ValidLabel").visible = false
    details_panel.get_node("DetailsContent").visible = true
    
    details_panel.get_node("DetailsContent/IdLabel").text = str(f["id"])
    details_panel.get_node("DetailsContent/NameLabel").text = str(f["name"])
    details_panel.get_node("DetailsContent/EconomyLabel").text = "Economic Profile: " + str(f.get("economic_profile", "Unknown"))
    details_panel.get_node("DetailsContent/CastLabel").text = "Cast: %d characters" % f.get("cast_count", 0)
    details_panel.get_node("DetailsContent/QuestLabel").text = "Quest: " + str(f.get("quest_title", "None"))
    details_panel.get_node("DetailsContent/PremiseLabel").text = str(f.get("quest_premise", ""))
    details_panel.get_node("DetailsContent/NodesLabel").text = "Story nodes: %d" % f.get("node_count", 0)
    details_panel.get_node("DetailsContent/RegionsLabel").text = "Regions: " + ", ".join(f.get("regions", []))
    details_panel.get_node("DetailsContent/AnchorsLabel").text = "Anchors: %d" % f.get("semantic_anchors", []).size()
    var ms = f.get("map_size", {})
    details_panel.get_node("DetailsContent/MapLabel").text = "Map: %dx%d" % [ms.get("width", 0), ms.get("height", 0)]
    
    # Errors if any
    var errors = f.get("errors", [])
    if errors.size() > 0:
        details_panel.get_node("DetailsContent/ErrorsLabel").text = "[color=yellow]Warnings: " + ", ".join(errors) + "[/color]"
        details_panel.get_node("DetailsContent/ErrorsLabel").visible = true
    else:
        details_panel.get_node("DetailsContent/ErrorsLabel").visible = false

## Details for a production settlement: the canonical profile behind the node,
## rendered from the same DmbWorldSim the test will boot.
func _update_generated_details(f: Dictionary) -> void:
    details_panel.get_node("ValidLabel").visible = false
    details_panel.get_node("DetailsContent").visible = true
    var sim: DmbWorldSim = Runner.build_generated_sim(int(f["seed"]), int(f["turns"]))
    var nid := int(f["node"])
    var p := DmbSettlementProfile.describe(sim, nid)
    var area := DmbNodeProjection.area_for(sim, nid)
    var lay: Dictionary = area.get("layout", {})
    var counts := {}
    for e in area["entities"]:
        counts[str(e["kind"])] = int(counts.get(str(e["kind"]), 0)) + 1
    var terr: Array = []
    for t in p["terrains"]:
        terr.append("%s x%d" % [str(t), int(p["terrains"][t])])
    var prod: Array = []
    for pr in p["production"]:
        prod.append("%d %s%s" % [int(pr["n"]), str(pr["building"]), " (idle)" if bool(pr.get("idle", false)) else ""])
    details_panel.get_node("DetailsContent/IdLabel").text = str(f["id"])
    details_panel.get_node("DetailsContent/NameLabel").text = str(f["name"])
    details_panel.get_node("DetailsContent/EconomyLabel").text = "%s of %s — dev %d, housing %d, infection %d%s" % [str(p["kind"]).capitalize(), DmbFactions.name_of(str(p["owner"])), int(p["development"]), int(p["housing"]), int(p["infection"]), (", mood " + str(p["mood"])) if str(p["mood"]) != "" else ""]
    details_panel.get_node("DetailsContent/CastLabel").text = "Terrain: %s | Production: %s" % [", ".join(PackedStringArray(terr)), ", ".join(PackedStringArray(prod))]
    details_panel.get_node("DetailsContent/QuestLabel").text = "Works: %s | Civic: %s" % [", ".join(PackedStringArray(p["processing"])) if not p["processing"].is_empty() else "none", ", ".join(PackedStringArray(p["civic"]))]
    details_panel.get_node("DetailsContent/PremiseLabel").text = str(f.get("description", ""))
    details_panel.get_node("DetailsContent/NodesLabel").text = "Entities: %s" % str(counts)
    details_panel.get_node("DetailsContent/RegionsLabel").text = "Production path: DmbWorldSim(%d) +%d turns -> DmbSettlementProfile -> DmbNodeProjection" % [int(f["seed"]), int(f["turns"])]
    details_panel.get_node("DetailsContent/AnchorsLabel").text = "Spawn: %s" % str(area.get("player_start", []))
    details_panel.get_node("DetailsContent/MapLabel").text = "Map: %dx%d" % [int(lay.get("w", 0)), int(lay.get("h", 0))]
    details_panel.get_node("DetailsContent/ErrorsLabel").visible = false

func _update_run_button() -> void:
    var valid_selection = selected_profile_id != "" and _fixture_by_id(selected_profile_id).get("valid", true)
    btn_run.disabled = not valid_selection
    btn_run.text = "PLAY TEST" if valid_selection else "SELECT VALID VILLAGE"

func _on_run_pressed() -> void:
    if selected_profile_id == "" or not _fixture_by_id(selected_profile_id).get("valid", true):
        return
    Runner.set_profile(selected_profile_id)
    get_tree().change_scene_to_file("res://client/scenes/overworld.tscn")

func _on_close_pressed() -> void:
    get_tree().quit()