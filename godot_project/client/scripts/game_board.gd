extends Control
class_name GameBoard

## The duel screen. One portrait layout, three phases:
##   WARD_SETUP – build your 4-spell ward, then Lock Ward
##   DUELING    – build guesses, cast inside the 5–60 s window, read results
##   FINISHED   – result overlay with both wards revealed, Play Again / Menu
##
## The sim (DmbRealtimeDuelSim) is authoritative; this script only renders state
## and forwards taps.

const _VT = preload("res://client/scripts/visual_theme.gd")
const _RealtimeSim = preload("res://sim/realtime_duel_sim.gd")
const _DuelEvent = preload("res://sim/duel_event.gd")
const _Art = preload("res://client/scripts/art.gd")
const _SpellSlot = preload("res://client/components/spell_slot.gd")
const _FeedbackPips = preload("res://client/components/feedback_pips.gd")
const _CastButton = preload("res://client/components/cast_button.gd")
const _CompositeWizard = preload("res://client/components/composite_wizard.gd")
const _SpellVfx = preload("res://client/components/spell_vfx.gd")
const _PlayabilityHaptics = preload("res://client/scripts/playability_haptics.gd")
const _SaveData = preload("res://client/scripts/save_data.gd")

signal game_finished

const HOW_TO_PLAY := [
	"You and the rival wizard each hide a Ward of four spells. Spells may repeat.",
	"Take turns guessing each other's Ward. After every cast you learn how many spells were right — never which ones.",
	"●  green — right spell in the right place\n○  amber ring — right spell in the wrong place\n·  grey — spell not in the Ward at all",
	"You can cast 5 seconds after your window opens. Cast within 60 seconds or the spell fires as it stands.",
	"Break the rival's Ward first to win. Ten casts each.",
]

var game
var sim:
	get:
		return game

var _ruleset: DmbDuelRuleset
var _bot_seed: int = 42
var _screenshot_mode: bool = false
var _reduce_motion: bool = false

# Layout nodes
var _root_vbox: VBoxContainer
var _top_bar: HBoxContainer
var _menu_btn: Button
var _phase_lbl: Label
var _help_btn: Button

var _rival_panel: PanelContainer
var _rival_wizard
var _rival_name_lbl: Label
var _rival_status_lbl: Label
var _rival_progress: ProgressBar
var _rival_casts_lbl: Label
var _rival_ward_row: HBoxContainer
var _rival_ward_slots: Array = []
var _rival_last_lbl: Label

var _result_banner: PanelContainer
var _result_title_lbl: Label
var _result_pips
var _result_text_lbl: Label
var _result_slots_row: HBoxContainer
var _result_slots: Array = []

var _history_panel: PanelContainer
var _history_tabs: HBoxContainer
var _history_tab_you: Button
var _history_tab_rival: Button
var _history_scroll: ScrollContainer
var _history_list: VBoxContainer
var _history_showing_rival: bool = false
var _history_empty_lbl: Label

var _intro_panel: PanelContainer
var _intro_lbl: Label

var _build_header: HBoxContainer
var _build_title_lbl: Label
var _clear_btn: Button
var _random_btn: Button
var _hint_lbl: Label
var _loci_row: HBoxContainer
var _loci_slots: Array = []
var _tray: HBoxContainer
var _tray_slots: Array = []

var _action_row: HBoxContainer
var _cast_button
var _lock_btn: Button
var _your_casts_lbl: Label
var _your_ward_row: HBoxContainer
var _your_ward_slots: Array = []
var _your_ward_lbl: Label

var _overlay: ColorRect
var _overlay_panel: PanelContainer
var _overlay_vbox: VBoxContainer

var _toast: PanelContainer
var _toast_lbl: Label
var _toast_tween: Tween

var _fx_layer: Control

# Interaction state
var _selected_locus: int = 0
var _paused_by_menu: bool = false
var _warn_ticks_played: Dictionary = {}
var _rival_cast_flash: float = 0.0
var _last_rival_state: String = ""
var _first_ready_announced: bool = false
var _result_shown: bool = false
var _history_rows: Array = []
var _time_since_start: float = 0.0


func _session() -> Node:
	return get_node("/root/EncounterSession")


func _ready() -> void:
	_screenshot_mode = "--screenshot-mode" in OS.get_cmdline_user_args()
	_reduce_motion = bool(_SaveData.get_setting("reduce_motion", false))
	_ruleset = _session().get_ruleset()
	_build_ui()
	start_new_game(_bot_seed)
	if not _screenshot_mode and not bool(_SaveData.get_setting("seen_how_to_play", false)):
		_show_help_overlay(true)


# ---------------------------------------------------------------------------
# UI construction
# ---------------------------------------------------------------------------

func _build_ui() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var bg := ColorRect.new()
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = _VT.COLOR_BG_DEEP
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)
	var glow := _Vignette.new()
	glow.set_anchors_preset(Control.PRESET_FULL_RECT)
	glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(glow)

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", _VT.PADDING_OUTER)
	margin.add_theme_constant_override("margin_right", _VT.PADDING_OUTER)
	margin.add_theme_constant_override("margin_top", 16)
	margin.add_theme_constant_override("margin_bottom", 20)
	add_child(margin)
	_root_vbox = VBoxContainer.new()
	_root_vbox.add_theme_constant_override("separation", 10)
	margin.add_child(_root_vbox)

	_build_top_bar()
	_build_rival_panel()
	_build_result_banner()
	_build_history_panel()
	_build_intro_panel()
	_build_builder()
	_build_action_row()
	_build_your_ward_strip()

	_fx_layer = Control.new()
	_fx_layer.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fx_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_fx_layer)

	_build_toast()
	_build_overlay()


func _build_top_bar() -> void:
	_top_bar = HBoxContainer.new()
	_top_bar.add_theme_constant_override("separation", 8)
	_root_vbox.add_child(_top_bar)
	_menu_btn = Button.new()
	_menu_btn.text = "≡"
	_menu_btn.custom_minimum_size = Vector2(_VT.TOUCH_SECONDARY, _VT.TOUCH_SECONDARY)
	_VT.style_secondary_button(_menu_btn)
	_menu_btn.add_theme_font_size_override("font_size", 28)
	_menu_btn.pressed.connect(_on_menu_pressed)
	_top_bar.add_child(_menu_btn)
	_phase_lbl = Label.new()
	_phase_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_phase_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_phase_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_VT.apply_label_primary(_phase_lbl)
	_top_bar.add_child(_phase_lbl)
	_help_btn = Button.new()
	_help_btn.text = "?"
	_help_btn.custom_minimum_size = Vector2(_VT.TOUCH_SECONDARY, _VT.TOUCH_SECONDARY)
	_VT.style_secondary_button(_help_btn)
	_help_btn.add_theme_font_size_override("font_size", 26)
	_help_btn.pressed.connect(func(): _show_help_overlay(false))
	_top_bar.add_child(_help_btn)


func _build_rival_panel() -> void:
	_rival_panel = PanelContainer.new()
	_rival_panel.add_theme_stylebox_override("panel", _VT.flat_panel_style(Color("#221c3d")))
	_root_vbox.add_child(_rival_panel)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 14)
	_rival_panel.add_child(h)
	var host := Control.new()
	host.custom_minimum_size = Vector2(96, 112)
	h.add_child(host)
	_rival_wizard = _CompositeWizard.new()
	_rival_wizard.set_anchors_preset(Control.PRESET_FULL_RECT)
	host.add_child(_rival_wizard)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	v.add_theme_constant_override("separation", 4)
	h.add_child(v)
	var name_row := HBoxContainer.new()
	v.add_child(name_row)
	_rival_name_lbl = Label.new()
	_VT.apply_label_primary(_rival_name_lbl)
	_rival_name_lbl.add_theme_font_size_override("font_size", 24)
	_rival_name_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_row.add_child(_rival_name_lbl)
	_rival_casts_lbl = Label.new()
	_VT.apply_label_secondary(_rival_casts_lbl)
	_rival_casts_lbl.add_theme_font_size_override("font_size", 19)
	_rival_casts_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	name_row.add_child(_rival_casts_lbl)
	_rival_status_lbl = Label.new()
	_VT.apply_label_secondary(_rival_status_lbl)
	_rival_status_lbl.add_theme_font_size_override("font_size", 19)
	v.add_child(_rival_status_lbl)
	_rival_progress = ProgressBar.new()
	_rival_progress.custom_minimum_size = Vector2(0, 10)
	_rival_progress.show_percentage = false
	_rival_progress.min_value = 0
	_rival_progress.max_value = 1
	var pbg := StyleBoxFlat.new()
	pbg.bg_color = Color("#14102a")
	pbg.set_corner_radius_all(5)
	var pfill := StyleBoxFlat.new()
	pfill.bg_color = Color("#8a7be8")
	pfill.set_corner_radius_all(5)
	_rival_progress.add_theme_stylebox_override("background", pbg)
	_rival_progress.add_theme_stylebox_override("fill", pfill)
	v.add_child(_rival_progress)
	var ward_row := HBoxContainer.new()
	ward_row.add_theme_constant_override("separation", 10)
	v.add_child(ward_row)
	var ward_lbl := Label.new()
	ward_lbl.text = "Their Ward"
	_VT.apply_label_caption(ward_lbl)
	ward_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	ward_row.add_child(ward_lbl)
	_rival_ward_row = HBoxContainer.new()
	_rival_ward_row.add_theme_constant_override("separation", 6)
	ward_row.add_child(_rival_ward_row)
	_rival_last_lbl = Label.new()
	_VT.apply_label_secondary(_rival_last_lbl)
	_rival_last_lbl.add_theme_font_size_override("font_size", 18)
	_rival_last_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_rival_last_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_rival_last_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	ward_row.add_child(_rival_last_lbl)


func _build_result_banner() -> void:
	_result_banner = PanelContainer.new()
	_result_banner.add_theme_stylebox_override("panel", _VT.flat_panel_style(Color("#2a2350")))
	_root_vbox.add_child(_result_banner)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 4)
	_result_banner.add_child(v)
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 12)
	v.add_child(top)
	_result_title_lbl = Label.new()
	_VT.apply_label_caption(_result_title_lbl)
	_result_title_lbl.text = "Your last cast"
	_result_title_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	top.add_child(_result_title_lbl)
	_result_slots_row = HBoxContainer.new()
	_result_slots_row.add_theme_constant_override("separation", 6)
	top.add_child(_result_slots_row)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(spacer)
	_result_pips = _FeedbackPips.new()
	_result_pips.pip_size = 26
	top.add_child(_result_pips)
	_result_text_lbl = Label.new()
	_VT.apply_label_secondary(_result_text_lbl)
	_result_text_lbl.add_theme_font_size_override("font_size", 22)
	_result_text_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(_result_text_lbl)


func _build_history_panel() -> void:
	_history_panel = PanelContainer.new()
	_history_panel.add_theme_stylebox_override("panel", _VT.flat_panel_style(Color("#1b1633")))
	_history_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_history_panel.custom_minimum_size = Vector2(0, 150)
	_root_vbox.add_child(_history_panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	_history_panel.add_child(v)
	_history_tabs = HBoxContainer.new()
	_history_tabs.add_theme_constant_override("separation", 8)
	v.add_child(_history_tabs)
	_history_tab_you = Button.new()
	_history_tab_you.text = "Your casts"
	_history_tab_you.custom_minimum_size = Vector2(0, 44)
	_history_tab_you.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_VT.style_secondary_button(_history_tab_you)
	_history_tab_you.add_theme_font_size_override("font_size", 18)
	_history_tab_you.pressed.connect(func(): _set_history_tab(false))
	_history_tabs.add_child(_history_tab_you)
	_history_tab_rival = Button.new()
	_history_tab_rival.text = "Rival's casts"
	_history_tab_rival.custom_minimum_size = Vector2(0, 44)
	_history_tab_rival.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_VT.style_secondary_button(_history_tab_rival)
	_history_tab_rival.add_theme_font_size_override("font_size", 18)
	_history_tab_rival.pressed.connect(func(): _set_history_tab(true))
	_history_tabs.add_child(_history_tab_rival)
	_history_scroll = ScrollContainer.new()
	_history_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_history_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	v.add_child(_history_scroll)
	_history_list = VBoxContainer.new()
	_history_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_history_list.add_theme_constant_override("separation", 4)
	_history_scroll.add_child(_history_list)
	_history_empty_lbl = Label.new()
	_VT.apply_label_caption(_history_empty_lbl)
	_history_empty_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_history_empty_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_history_empty_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_history_list.add_child(_history_empty_lbl)


func _build_intro_panel() -> void:
	_intro_panel = PanelContainer.new()
	_intro_panel.add_theme_stylebox_override("panel", _VT.flat_panel_style(Color("#1b1633")))
	_intro_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_root_vbox.add_child(_intro_panel)
	var v := VBoxContainer.new()
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_theme_constant_override("separation", 10)
	_intro_panel.add_child(v)
	var t := Label.new()
	t.text = "Set your secret Ward"
	_VT.apply_label_primary(t)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(t)
	_intro_lbl = Label.new()
	_intro_lbl.text = "Pick four spells below. Repeats are allowed.\nThe rival will try to guess this — you will try to guess theirs."
	_VT.apply_label_secondary(_intro_lbl)
	_intro_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_intro_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(_intro_lbl)
	var legend_title := Label.new()
	legend_title.text = "After each cast you learn how many spells were:"
	_VT.apply_label_caption(legend_title)
	legend_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(legend_title)
	var legend := VBoxContainer.new()
	legend.add_theme_constant_override("separation", 6)
	legend.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_child(legend)
	for entry in [["fracture", "right spell, right place"], ["echo", "right spell, wrong place"], ["fade", "not in the Ward at all"]]:
		var row := HBoxContainer.new()
		row.alignment = BoxContainer.ALIGNMENT_CENTER
		row.add_theme_constant_override("separation", 12)
		var pip = _FeedbackPips.new()
		pip.pip_size = 24
		row.add_child(pip)
		var counts := [1 if entry[0] == "fracture" else 0, 1 if entry[0] == "echo" else 0, 1 if entry[0] == "fade" else 0]
		pip.call_deferred("show_counts", 1, counts[0], counts[1], counts[2])
		var l := Label.new()
		l.text = entry[1]
		l.custom_minimum_size = Vector2(260, 0)
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		_VT.apply_label_secondary(l)
		row.add_child(l)
		legend.add_child(row)


func _build_builder() -> void:
	_build_header = HBoxContainer.new()
	_build_header.add_theme_constant_override("separation", 8)
	_root_vbox.add_child(_build_header)
	_build_title_lbl = Label.new()
	_VT.apply_label_primary(_build_title_lbl)
	_build_title_lbl.add_theme_font_size_override("font_size", 22)
	_build_title_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_build_title_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_build_header.add_child(_build_title_lbl)
	_random_btn = Button.new()
	_random_btn.text = "Random"
	_random_btn.custom_minimum_size = Vector2(0, 44)
	_VT.style_secondary_button(_random_btn)
	_random_btn.add_theme_font_size_override("font_size", 18)
	_random_btn.pressed.connect(_on_random_pressed)
	_build_header.add_child(_random_btn)
	_clear_btn = Button.new()
	_clear_btn.text = "Clear"
	_clear_btn.custom_minimum_size = Vector2(0, 44)
	_VT.style_secondary_button(_clear_btn)
	_clear_btn.add_theme_font_size_override("font_size", 18)
	_clear_btn.pressed.connect(_on_clear_pressed)
	_build_header.add_child(_clear_btn)

	_loci_row = HBoxContainer.new()
	_loci_row.alignment = BoxContainer.ALIGNMENT_CENTER
	_loci_row.add_theme_constant_override("separation", 14)
	_root_vbox.add_child(_loci_row)
	for i in range(_ruleset.slot_count):
		var slot = _SpellSlot.new()
		slot.slot_index = i
		slot.slot_size = _VT.TOUCH_ESSENCE
		slot.caption = str(i + 1)
		slot.tooltip_text = str(_ruleset.point_names[i]) if i < _ruleset.point_names.size() else ""
		slot.slot_tapped.connect(_on_locus_tapped)
		_loci_row.add_child(slot)
		_loci_slots.append(slot)

	_hint_lbl = Label.new()
	_VT.apply_label_secondary(_hint_lbl)
	_hint_lbl.add_theme_font_size_override("font_size", 18)
	_hint_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_hint_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_root_vbox.add_child(_hint_lbl)

	_tray = HBoxContainer.new()
	_tray.alignment = BoxContainer.ALIGNMENT_CENTER
	_tray.add_theme_constant_override("separation", 10)
	_root_vbox.add_child(_tray)
	for id in _ruleset.attack_magic_pool:
		var tok = _SpellSlot.new()
		tok.slot_index = int(id)
		tok.slot_size = _VT.TOUCH_TRAY
		tok.caption = DmbColourData.essence_name(int(id))
		tok.slot_tapped.connect(_on_tray_tapped)
		_tray.add_child(tok)
		_tray_slots.append(tok)


func _build_action_row() -> void:
	_action_row = HBoxContainer.new()
	_action_row.alignment = BoxContainer.ALIGNMENT_CENTER
	_action_row.add_theme_constant_override("separation", 20)
	_root_vbox.add_child(_action_row)
	var left := Control.new()
	left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_action_row.add_child(left)
	_cast_button = _CastButton.new()
	_cast_button.cast_pressed.connect(_on_cast_pressed)
	_cast_button.blocked_pressed.connect(_on_cast_blocked_pressed)
	_action_row.add_child(_cast_button)
	_lock_btn = Button.new()
	_lock_btn.text = "Lock Ward"
	_lock_btn.custom_minimum_size = Vector2(240, 72)
	_VT.style_primary_button(_lock_btn)
	_lock_btn.pressed.connect(_on_lock_pressed)
	_action_row.add_child(_lock_btn)
	var right := VBoxContainer.new()
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right.alignment = BoxContainer.ALIGNMENT_CENTER
	_action_row.add_child(right)
	_your_casts_lbl = Label.new()
	_VT.apply_label_secondary(_your_casts_lbl)
	_your_casts_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_your_casts_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right.add_child(_your_casts_lbl)


func _build_your_ward_strip() -> void:
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 10)
	_root_vbox.add_child(row)
	_your_ward_lbl = Label.new()
	_your_ward_lbl.text = "Your Ward"
	_VT.apply_label_caption(_your_ward_lbl)
	_your_ward_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	row.add_child(_your_ward_lbl)
	_your_ward_row = HBoxContainer.new()
	_your_ward_row.add_theme_constant_override("separation", 6)
	row.add_child(_your_ward_row)
	for i in range(_ruleset.slot_count):
		var s = _SpellSlot.new()
		s.slot_size = 44
		s.disabled = true
		_your_ward_row.add_child(s)
		_your_ward_slots.append(s)


func _build_toast() -> void:
	_toast = PanelContainer.new()
	_toast.add_theme_stylebox_override("panel", _VT.panel_style(14))
	_toast.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_toast.visible = false
	_toast.modulate.a = 0.0
	add_child(_toast)
	_toast_lbl = Label.new()
	_VT.apply_label_secondary(_toast_lbl)
	_toast_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_toast_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_toast_lbl.custom_minimum_size = Vector2(440, 0)
	_toast.add_child(_toast_lbl)


func _build_overlay() -> void:
	_overlay = ColorRect.new()
	_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay.color = Color(0.05, 0.03, 0.1, 0.78)
	_overlay.visible = false
	_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_overlay)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay.add_child(center)
	_overlay_panel = PanelContainer.new()
	_overlay_panel.add_theme_stylebox_override("panel", _VT.panel_style(20))
	_overlay_panel.custom_minimum_size = Vector2(560, 0)
	center.add_child(_overlay_panel)
	_overlay_vbox = VBoxContainer.new()
	_overlay_vbox.add_theme_constant_override("separation", 14)
	_overlay_panel.add_child(_overlay_vbox)


# ---------------------------------------------------------------------------
# Game lifecycle
# ---------------------------------------------------------------------------

func start_new_game(bot_seed: int = -1) -> void:
	if bot_seed < 0:
		bot_seed = randi() % 1000000
	_bot_seed = bot_seed
	_ruleset = _session().get_ruleset()
	game = _RealtimeSim.new(_ruleset, _session().get_difficulty_profile(), bot_seed)
	_rival_name_lbl.text = _ruleset.enemy_name
	_rival_wizard.load_archetype(_Art.wizard_archetype_from_enemy(_ruleset.enemy_archetype))
	_selected_locus = 0
	_paused_by_menu = false
	_warn_ticks_played.clear()
	_last_rival_state = ""
	_first_ready_announced = false
	_result_shown = false
	_time_since_start = 0.0
	_history_showing_rival = false
	_clear_history_rows()
	_overlay.visible = false
	_result_banner.visible = false
	for s in _rival_ward_slots:
		s.queue_free()
	_rival_ward_slots.clear()
	for i in range(_ruleset.slot_count):
		var s = _SpellSlot.new()
		s.slot_size = 40
		s.disabled = true
		_rival_ward_row.add_child(s)
		_rival_ward_slots.append(s)
		s.call_deferred("set_hidden")
	_refresh_all()


func _process(delta: float) -> void:
	if game == null:
		return
	if game.phase == _RealtimeSim.Phase.DUELING and not _paused_by_menu:
		game.advance_time(delta)
		_time_since_start += delta
	_consume_events()
	if game.phase == _RealtimeSim.Phase.DUELING:
		_refresh_timers()
		_refresh_rival_status()
	if game.result != null and not _result_shown:
		_show_result()


# ---------------------------------------------------------------------------
# Input handlers
# ---------------------------------------------------------------------------

func _pattern_in_builder() -> Array:
	if game.phase == _RealtimeSim.Phase.WARD_SETUP:
		return game.get_player_ward()
	return game.get_player_attack_pattern()


func _set_builder_locus(index: int, spell: int) -> void:
	if game.phase == _RealtimeSim.Phase.WARD_SETUP:
		game.set_player_ward_locus(index, spell)
	elif game.phase == _RealtimeSim.Phase.DUELING:
		game.set_player_attack_locus(index, spell)


func _on_locus_tapped(index: int) -> void:
	if game.phase == _RealtimeSim.Phase.FINISHED:
		return
	var pattern := _pattern_in_builder()
	if _selected_locus == index and pattern[index] != null:
		_set_builder_locus(index, -1)
		_sfx("clear_slot")
		_PlayabilityHaptics.pulse_light()
	else:
		_selected_locus = index
		_sfx("tap")
	_refresh_builder()


func _on_tray_tapped(spell_id: int) -> void:
	if game.phase == _RealtimeSim.Phase.FINISHED:
		return
	var pattern := _pattern_in_builder()
	var target := _selected_locus
	if target < 0 or target >= pattern.size():
		target = 0
	_set_builder_locus(target, spell_id)
	_loci_slots[target].pop()
	_sfx("place")
	_PlayabilityHaptics.pulse_light()
	# Advance selection to the next empty locus (wrapping), else stay.
	var next := -1
	pattern = _pattern_in_builder()
	for k in range(1, pattern.size() + 1):
		var j := (target + k) % pattern.size()
		if pattern[j] == null:
			next = j
			break
	_selected_locus = next if next >= 0 else target
	_refresh_builder()
	_refresh_cast_button()


func _on_clear_pressed() -> void:
	if game.phase == _RealtimeSim.Phase.WARD_SETUP:
		game.clear_player_ward()
	elif game.phase == _RealtimeSim.Phase.DUELING:
		game.clear_player_attack()
	_selected_locus = 0
	_sfx("clear_slot")
	_refresh_builder()
	_refresh_cast_button()


func _on_random_pressed() -> void:
	if game.phase != _RealtimeSim.Phase.WARD_SETUP:
		return
	game.randomise_player_ward()
	_selected_locus = 0
	_sfx("place")
	for s in _loci_slots:
		s.pop()
	_refresh_builder()


func _on_lock_pressed() -> void:
	if not game.can_lock_player_ward():
		_sfx("denied")
		_show_toast("Choose a spell for every locus first")
		for i in range(_loci_slots.size()):
			if game.get_player_ward()[i] == null:
				_loci_slots[i].flash_wrong()
		return
	game.lock_player_ward_and_start()
	_selected_locus = 0
	_sfx("cast")
	_PlayabilityHaptics.pulse_medium()
	_refresh_all()
	_show_toast("Ward locked! Your first cast opens in 5 seconds.")


func _on_cast_pressed() -> void:
	if not game.can_player_cast():
		_on_cast_blocked_pressed()
		return
	var pattern: Array = game.get_player_attack_pattern()
	if game.submit_player_attack():
		_sfx("cast")
		_launch_bolts(pattern)
		_selected_locus = 0
		_consume_events()
		_refresh_all()


func _on_cast_blocked_pressed() -> void:
	var reason: String = game.player_cast_block_reason()
	_sfx("denied")
	if reason.begins_with("Fill"):
		var pattern: Array = game.get_player_attack_pattern()
		for i in range(_loci_slots.size()):
			if pattern[i] == null:
				_loci_slots[i].flash_wrong()
		_show_toast("Choose all four spells before casting")
	elif reason.begins_with("Weaving"):
		_show_toast("Your cast opens in %.0f s" % ceil(float(game.get_current_state()["player_time_until_cast"])))
	elif reason != "":
		_show_toast(reason)


func _on_history_row_tapped(pattern: Array) -> void:
	if game.phase != _RealtimeSim.Phase.DUELING:
		return
	game.load_player_attack(pattern)
	_selected_locus = 0
	_sfx("place")
	for s in _loci_slots:
		s.pop()
	_refresh_builder()
	_refresh_cast_button()
	_show_toast("Copied into your guess — change what you like")


func _on_menu_pressed() -> void:
	_show_menu_overlay()


# ---------------------------------------------------------------------------
# Events from the sim
# ---------------------------------------------------------------------------

func _consume_events() -> void:
	for ev in game.get_pending_events():
		match ev.type:
			_DuelEvent.FEEDBACK_REVEALED:
				_on_feedback(ev.data)
			_DuelEvent.WARD_BROKEN:
				pass
			_DuelEvent.DUEL_FINISHED:
				pass


func _on_feedback(data: Dictionary) -> void:
	var attacker := str(data.get("attacker_id", ""))
	var pattern: Array = data.get("pattern_by_locus", [])
	var fr := int(data.get("fracture_count", 0))
	var ec := int(data.get("echo_count", 0))
	var fa := int(data.get("fade_count", 0))
	var auto := bool(data.get("was_auto_cast", false))
	_add_history_row(attacker, int(data.get("attack_number", 0)), pattern, fr, ec, fa, auto)
	if attacker == "player":
		_show_player_result(pattern, fr, ec, fa, auto)
		if auto:
			_show_toast("Time ran out — your spell was cast as it stood")
		_sfx("fracture", fr)
		if fr > 0:
			_PlayabilityHaptics.pulse_medium()
	else:
		_rival_last_lbl.text = "Last: %s" % _describe_short(fr, ec, fa)
		_rival_cast_flash = 1.0
		_sfx("rival_cast")
		_flash_your_ward(fr)
	_refresh_counts()


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

func _refresh_all() -> void:
	var setup: bool = game.phase == _RealtimeSim.Phase.WARD_SETUP
	var dueling: bool = game.phase == _RealtimeSim.Phase.DUELING
	_intro_panel.visible = setup
	_history_panel.visible = not setup
	_result_banner.visible = not setup and game.player_history.size() > 0
	_random_btn.visible = setup
	_lock_btn.visible = setup
	_cast_button.visible = not setup
	_your_ward_lbl.get_parent().visible = not setup
	_rival_progress.visible = dueling or game.phase == _RealtimeSim.Phase.FINISHED
	_build_title_lbl.text = "Your Ward" if setup else "Your guess"
	_phase_lbl.text = "Set your Ward" if setup else "Ward Duel"
	if setup:
		_rival_status_lbl.text = "The rival is weaving a Ward…"
		_rival_last_lbl.text = ""
		_rival_progress.value = 0
	_refresh_builder()
	_refresh_counts()
	_refresh_cast_button()
	_refresh_your_ward()
	_refresh_history()


func _refresh_builder() -> void:
	var pattern := _pattern_in_builder()
	var setup: bool = game.phase == _RealtimeSim.Phase.WARD_SETUP
	var finished: bool = game.phase == _RealtimeSim.Phase.FINISHED
	for i in range(_loci_slots.size()):
		var s = _loci_slots[i]
		var v = pattern[i] if i < pattern.size() else null
		s.set_spell(int(v) if v != null else -1)
		s.set_selected(i == _selected_locus and not finished)
		s.disabled = finished
		s.set_dim(finished)
	for t in _tray_slots:
		t.set_spell(t.slot_index)
		t.disabled = finished
		t.set_dim(finished)
	_clear_btn.disabled = finished or not _any_filled(pattern)
	_lock_btn.disabled = not game.can_lock_player_ward()
	if setup:
		var missing := _count_empty(pattern)
		if missing == 0:
			_lock_btn.text = "Lock Ward"
		elif missing == _ruleset.slot_count:
			_lock_btn.text = "Choose %d spells" % missing
		else:
			_lock_btn.text = "Pick %d more spell%s" % [missing, "" if missing == 1 else "s"]
	if setup:
		_hint_lbl.text = "Tap a spell to put it in the glowing slot. Tap a filled slot twice to clear it." if not _all_filled(pattern) else "Happy with it? Lock your Ward to begin."
	elif finished:
		_hint_lbl.text = ""
	else:
		_hint_lbl.text = _duel_hint(pattern)


func _duel_hint(pattern: Array) -> String:
	if not _all_filled(pattern):
		var n := 0
		for p in pattern:
			if p == null:
				n += 1
		return "Choose %d more spell%s for your guess." % [n, "" if n == 1 else "s"]
	if game.is_player_window_open():
		return "Ready — tap CAST, or keep adjusting."
	return "Guess ready. Casting opens when the ring fills."


func _refresh_counts() -> void:
	var st: Dictionary = game.get_current_state()
	var remaining := int(st.get("player_attacks_remaining", 0))
	var max_a := int(st.get("max_attacks", 10))
	if game.phase == _RealtimeSim.Phase.WARD_SETUP:
		_your_casts_lbl.text = ""
		_rival_casts_lbl.text = ""
	else:
		_your_casts_lbl.text = "%d of %d\ncasts left" % [remaining, max_a]
		_rival_casts_lbl.text = "%d casts left" % int(st.get("enemy_attacks_remaining", 0))


func _refresh_cast_button() -> void:
	if game.phase != _RealtimeSim.Phase.DUELING:
		_cast_button.set_state(_CastButton.State.DISABLED, 0.0, 0.0, "", "")
		return
	_refresh_timers()


func _refresh_timers() -> void:
	var st: Dictionary = game.get_current_state()
	var until_cast := float(st.get("player_time_until_cast", 0.0))
	var until_auto := float(st.get("player_time_until_auto", 0.0))
	var min_c := maxf(float(st.get("player_min_cast", 5.0)), 0.01)
	var max_c := maxf(float(st.get("player_max_cast", 60.0)), 0.01)
	var elapsed := float(st.get("player_window_elapsed", 0.0))
	var window_open := bool(st.get("player_window_open", false))
	var complete := bool(st.get("player_attack_complete", false))
	var remaining := int(st.get("player_attacks_remaining", 0))
	if remaining <= 0:
		_cast_button.set_state(_CastButton.State.DISABLED, 0.0, 0.0, "", "No casts left")
		return
	if not window_open:
		var charge := clampf(elapsed / min_c, 0.0, 1.0)
		_cast_button.set_state(_CastButton.State.CHARGING, charge, 1.0, "%d" % int(ceil(until_cast)), "")
		return
	var remaining_ratio := clampf(until_auto / maxf(max_c - min_c, 0.01), 0.0, 1.0)
	var secs := int(ceil(until_auto))
	var warning := until_auto <= _VT.WARNING_SECONDS
	if warning and not _warn_ticks_played.has(secs) and secs > 0:
		_warn_ticks_played[secs] = true
		_sfx("warning_tick")
		if secs <= 3:
			_PlayabilityHaptics.pulse_warning()
	if not complete:
		_cast_button.set_state(_CastButton.State.BLOCKED, 1.0, remaining_ratio, "%ds" % secs, "pick %d more" % _count_empty(game.get_player_attack_pattern()))
	elif warning:
		_cast_button.set_state(_CastButton.State.WARNING, 1.0, remaining_ratio, "%ds left!" % secs, "")
	else:
		if not _first_ready_announced:
			_first_ready_announced = true
			_sfx("ready_chime")
		_cast_button.set_state(_CastButton.State.READY, 1.0, remaining_ratio, "%ds left" % secs, "")
	if window_open and complete and _hint_lbl.text.begins_with("Guess ready"):
		_hint_lbl.text = _duel_hint(game.get_player_attack_pattern())
	if not _warn_ticks_played.is_empty() and until_auto > _VT.WARNING_SECONDS:
		_warn_ticks_played.clear()


func _refresh_rival_status() -> void:
	var st: Dictionary = game.get_current_state()
	var progress := float(st.get("enemy_cast_progress", 0.0))
	_rival_progress.value = progress
	var state := ""
	if int(st.get("enemy_attacks_remaining", 0)) <= 0:
		state = "spent"
	elif _rival_cast_flash > 0.0:
		state = "cast"
	elif progress < 0.55:
		state = "studying"
	else:
		state = "weaving"
	if _rival_cast_flash > 0.0:
		_rival_cast_flash = maxf(0.0, _rival_cast_flash - get_process_delta_time() * 0.7)
	if state != _last_rival_state:
		_last_rival_state = state
		match state:
			"studying":
				_rival_status_lbl.text = "Studying your Ward…"
				_rival_status_lbl.add_theme_color_override("font_color", _VT.COLOR_TEXT_SECONDARY)
			"weaving":
				_rival_status_lbl.text = "Weaving a spell…"
				_rival_status_lbl.add_theme_color_override("font_color", _VT.COLOR_ACCENT_GOLD)
			"cast":
				_rival_status_lbl.text = "Cast!"
				_rival_status_lbl.add_theme_color_override("font_color", _VT.COLOR_DANGER)
				_rival_wizard.play_cast_windup()
			"spent":
				_rival_status_lbl.text = "Out of casts"
				_rival_status_lbl.add_theme_color_override("font_color", _VT.COLOR_TEXT_SECONDARY)


func _refresh_your_ward() -> void:
	var ward: Array = game.get_player_ward()
	for i in range(_your_ward_slots.size()):
		var v = ward[i] if i < ward.size() else null
		_your_ward_slots[i].set_spell(int(v) if v != null else -1)


func _show_player_result(pattern: Array, fr: int, ec: int, fa: int, auto: bool) -> void:
	_result_banner.visible = true
	for s in _result_slots:
		s.queue_free()
	_result_slots.clear()
	for v in pattern:
		var s = _SpellSlot.new()
		s.slot_size = 40
		s.disabled = true
		_result_slots_row.add_child(s)
		s.call_deferred("set_spell", int(v))
		_result_slots.append(s)
	_result_pips.show_counts(_ruleset.slot_count, fr, ec, fa)
	if not _reduce_motion:
		_result_pips.call_deferred("pop_in")
	_result_title_lbl.text = "Your cast #%d%s" % [game.player_history.size(), " (auto)" if auto else ""]
	_result_text_lbl.text = _describe_long(fr, ec, fa)
	if fr == _ruleset.slot_count:
		_result_text_lbl.text = "All four exact — the rival's Ward breaks!"


static func _describe_short(fr: int, ec: int, fa: int) -> String:
	if fr == 0 and ec == 0:
		return "nothing matched"
	var parts: Array = []
	if fr > 0:
		parts.append("%d exact" % fr)
	if ec > 0:
		parts.append("%d close" % ec)
	if fa > 0:
		parts.append("%d miss" % fa)
	return ", ".join(PackedStringArray(parts))


func _describe_long(fr: int, ec: int, fa: int) -> String:
	var parts: Array = []
	if fr > 0:
		parts.append("%d right spell in the right place" % fr)
	if ec > 0:
		parts.append("%d right spell in the wrong place" % ec)
	if fa > 0:
		parts.append("%d not in their Ward" % fa)
	if parts.is_empty():
		return "Nothing matched."
	return " · ".join(PackedStringArray(parts))


# --- History ---------------------------------------------------------------

func _add_history_row(attacker: String, number: int, pattern: Array, fr: int, ec: int, fa: int, auto: bool) -> void:
	_history_rows.append({
		"attacker": attacker, "number": number, "pattern": pattern.duplicate(),
		"fr": fr, "ec": ec, "fa": fa, "auto": auto,
	})
	_refresh_history()


func _clear_history_rows() -> void:
	_history_rows.clear()
	_refresh_history_list()


func _set_history_tab(rival: bool) -> void:
	_history_showing_rival = rival
	_sfx("tap")
	_refresh_history()


func _refresh_history() -> void:
	var you_n := 0
	var rival_n := 0
	for r in _history_rows:
		if r["attacker"] == "player":
			you_n += 1
		else:
			rival_n += 1
	_history_tab_you.text = "Your casts (%d)" % you_n
	_history_tab_rival.text = "Rival's casts (%d)" % rival_n
	var active := _VT.secondary_button_style()
	active.bg_color = Color("#3d3580")
	active.border_color = _VT.COLOR_ACCENT_GOLD
	var idle := _VT.secondary_button_style()
	idle.bg_color = Color("#1b1633")
	idle.border_color = Color("#3a3160")
	_history_tab_you.add_theme_stylebox_override("normal", idle if _history_showing_rival else active)
	_history_tab_rival.add_theme_stylebox_override("normal", active if _history_showing_rival else idle)
	_refresh_history_list()


func _refresh_history_list() -> void:
	for c in _history_list.get_children():
		if c != _history_empty_lbl:
			c.queue_free()
	var shown := 0
	var rows := _history_rows.duplicate()
	rows.reverse()
	for r in rows:
		var is_player: bool = r["attacker"] == "player"
		if is_player == _history_showing_rival:
			continue
		_history_list.add_child(_make_history_row(r))
		shown += 1
	_history_empty_lbl.visible = shown == 0
	if _history_showing_rival:
		_history_empty_lbl.text = "The rival has not cast yet.\nTheir results show how close they are to your Ward."
	else:
		_history_empty_lbl.text = "Your casts and their results will appear here.\nTap a past cast to copy it into your guess."
	_history_list.move_child(_history_empty_lbl, 0)


func _make_history_row(r: Dictionary) -> Control:
	var btn := Button.new()
	btn.focus_mode = Control.FOCUS_NONE
	btn.custom_minimum_size = Vector2(0, 52)
	var style := _VT.flat_panel_style(Color("#241d40"), 10)
	style.content_margin_top = 4
	style.content_margin_bottom = 4
	var pressed_style := _VT.flat_panel_style(Color("#2f2760"), 10)
	btn.add_theme_stylebox_override("normal", style)
	btn.add_theme_stylebox_override("hover", style)
	btn.add_theme_stylebox_override("pressed", pressed_style)
	btn.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	var is_player: bool = r["attacker"] == "player"
	if is_player:
		var pat: Array = r["pattern"]
		btn.pressed.connect(func(): _on_history_row_tapped(pat))
	else:
		btn.disabled = true
		btn.add_theme_stylebox_override("disabled", style)
	var h := HBoxContainer.new()
	h.mouse_filter = Control.MOUSE_FILTER_IGNORE
	h.set_anchors_preset(Control.PRESET_FULL_RECT)
	h.add_theme_constant_override("separation", 10)
	btn.add_child(h)
	var num := Label.new()
	num.text = "%d" % int(r["number"])
	num.custom_minimum_size = Vector2(28, 0)
	num.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	num.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_VT.apply_label_caption(num)
	h.add_child(num)
	var icons := HBoxContainer.new()
	icons.add_theme_constant_override("separation", 5)
	h.add_child(icons)
	for v in r["pattern"]:
		var s = _SpellSlot.new()
		s.slot_size = 40
		s.disabled = true
		s.mouse_filter = Control.MOUSE_FILTER_IGNORE
		icons.add_child(s)
		s.call_deferred("set_spell", int(v))
	if bool(r["auto"]):
		var a := Label.new()
		a.text = "auto"
		_VT.apply_label_caption(a)
		a.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		h.add_child(a)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(spacer)
	var pips = _FeedbackPips.new()
	pips.pip_size = 26
	h.add_child(pips)
	pips.call_deferred("show_counts", _ruleset.slot_count, int(r["fr"]), int(r["ec"]), int(r["fa"]))
	var pad := Control.new()
	pad.custom_minimum_size = Vector2(6, 0)
	h.add_child(pad)
	return btn


# --- Effects ---------------------------------------------------------------

func _launch_bolts(pattern: Array) -> void:
	if _reduce_motion or _fx_layer == null:
		return
	var target: Vector2 = _rival_ward_row.get_global_rect().get_center()
	for i in range(pattern.size()):
		if pattern[i] == null:
			continue
		var bolt := _SpellVfx.new()
		_fx_layer.add_child(bolt)
		bolt.setup(int(pattern[i]))
		bolt.scale = Vector2(0.45, 0.45)
		bolt.global_position = _loci_slots[i].get_global_rect().get_center()
		var tw := bolt.launch_toward(target + Vector2((i - 1.5) * 24, 0), _VT.DUR_PROJECTILE)
		tw.finished.connect(bolt.queue_free)
	var tree := get_tree()
	tree.create_timer(_VT.DUR_PROJECTILE).timeout.connect(func():
		if is_instance_valid(_fx_layer):
			_SpellVfx.spawn_impact(_fx_layer, target)
	)


func _flash_your_ward(fractures: int) -> void:
	var col := Color(1.4, 0.8, 0.8) if fractures > 0 else Color(1.15, 1.15, 1.3)
	var row := _your_ward_row.get_parent()
	var tw := create_tween()
	tw.tween_property(row, "modulate", col, 0.12)
	tw.tween_property(row, "modulate", Color.WHITE, 0.35)


func _show_toast(text_value: String) -> void:
	_toast_lbl.text = text_value
	_toast.visible = true
	_toast.reset_size()
	var vp := get_viewport_rect().size
	_toast.position = Vector2((vp.x - _toast.size.x) * 0.5, vp.y * 0.56)
	if _toast_tween != null and _toast_tween.is_valid():
		_toast_tween.kill()
	_toast.modulate.a = 0.0
	_toast_tween = create_tween()
	_toast_tween.tween_property(_toast, "modulate:a", 1.0, 0.12)
	_toast_tween.tween_interval(1.4)
	_toast_tween.tween_property(_toast, "modulate:a", 0.0, 0.3)
	_toast_tween.tween_callback(func(): _toast.visible = false)


func _sfx(kind: String, arg: int = 0) -> void:
	var sfx := get_node_or_null("/root/Sfx")
	if sfx == null:
		return
	match kind:
		"fracture":
			sfx.fracture(arg)
		_:
			if sfx.has_method(kind):
				sfx.call(kind)


# --- Overlays --------------------------------------------------------------

func _clear_overlay() -> void:
	for c in _overlay_vbox.get_children():
		c.queue_free()


func _overlay_title(text_value: String, colour: Color = _VT.COLOR_ACCENT_GOLD) -> void:
	var t := Label.new()
	t.text = text_value
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t.add_theme_font_size_override("font_size", _VT.FONT_TITLE)
	t.add_theme_color_override("font_color", colour)
	_overlay_vbox.add_child(t)


func _overlay_text(text_value: String, secondary: bool = true) -> Label:
	var l := Label.new()
	l.text = text_value
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	if secondary:
		_VT.apply_label_secondary(l)
	else:
		_VT.apply_label_primary(l)
	_overlay_vbox.add_child(l)
	return l


func _overlay_button(text_value: String, primary: bool, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text_value
	b.custom_minimum_size = Vector2(0, 64)
	if primary:
		_VT.style_primary_button(b)
	else:
		_VT.style_secondary_button(b)
	b.pressed.connect(cb)
	_overlay_vbox.add_child(b)
	return b


func _overlay_ward_row(label: String, ward: Array) -> void:
	var h := HBoxContainer.new()
	h.alignment = BoxContainer.ALIGNMENT_CENTER
	h.add_theme_constant_override("separation", 10)
	_overlay_vbox.add_child(h)
	var l := Label.new()
	l.text = label
	l.custom_minimum_size = Vector2(130, 0)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(l)
	h.add_child(l)
	for v in ward:
		var s = _SpellSlot.new()
		s.slot_size = 56
		s.disabled = true
		h.add_child(s)
		s.call_deferred("set_spell", int(v) if v != null else -1)


func _set_paused(on: bool) -> void:
	_paused_by_menu = on
	game.set_paused(on)


func _show_menu_overlay() -> void:
	_clear_overlay()
	var in_duel: bool = game.phase == _RealtimeSim.Phase.DUELING
	_set_paused(true)
	_overlay_title("Paused" if in_duel else "Menu")
	if in_duel:
		_overlay_text("The duel is paused. The rival waits too.")
	_overlay_button("Resume", true, func():
		_overlay.visible = false
		_set_paused(false)
	)
	_overlay_button("How to play", false, func(): _show_help_overlay(false))
	_overlay_button("Restart duel", false, func():
		_overlay.visible = false
		start_new_game(-1)
		_sfx("tap")
	)
	_overlay_button("Quit to menu", false, _go_to_main_menu)
	_overlay.visible = true


func _show_help_overlay(first_time: bool) -> void:
	_clear_overlay()
	var was_paused := _paused_by_menu
	_set_paused(true)
	_overlay_title("How to play")
	for line in HOW_TO_PLAY:
		_overlay_text(line)
	_overlay_button("Got it" if first_time else "Back", true, func():
		_SaveData.set_setting("seen_how_to_play", true)
		if first_time or not was_paused:
			_overlay.visible = false
			_set_paused(false)
		else:
			_show_menu_overlay()
	)
	_overlay.visible = true


func _show_result() -> void:
	_result_shown = true
	var r = game.result
	for i in range(_rival_ward_slots.size()):
		var w: Array = game.get_enemy_ward()
		_rival_ward_slots[i].set_spell(int(w[i]))
	_rival_progress.value = 0
	_rival_status_lbl.text = ""
	_refresh_builder()
	_refresh_cast_button()
	game_finished.emit()
	_clear_overlay()
	var title := "Stalemate"
	var colour := _VT.COLOR_TEXT_PRIMARY
	match r.outcome:
		"victory":
			title = "Victory!"
			colour = _VT.COLOR_FRACTURE
			_sfx("victory")
		"defeat":
			title = "Defeat"
			colour = _VT.COLOR_DANGER
			_sfx("defeat")
		"clash":
			title = "Clash!"
			colour = _VT.COLOR_ECHO
			_sfx("victory")
	_overlay_title(title, colour)
	_overlay_text(r.message, false)
	_overlay_ward_row("Their Ward", game.get_enemy_ward())
	_overlay_ward_row("Your Ward", game.get_player_ward())
	_overlay_text("You cast %d · Rival cast %d" % [r.human_guess_count, r.bot_guess_count], false)
	_overlay_button("Play again", true, func():
		_overlay.visible = false
		start_new_game(-1)
		_sfx("tap")
	)
	_overlay_button("Menu", false, _go_to_main_menu)
	if _screenshot_mode:
		_overlay.visible = true
	else:
		get_tree().create_timer(0.9).timeout.connect(func():
			if is_instance_valid(self) and game != null and game.result != null:
				_overlay.visible = true
		)


func _go_to_main_menu() -> void:
	get_tree().change_scene_to_file("res://client/scenes/main_menu.tscn")


# --- helpers -----------------------------------------------------------------

class _Vignette:
	extends Control
	func _draw() -> void:
		var c := size * Vector2(0.5, 0.42)
		var r := size.length() * 0.55
		for i in range(12):
			var t := float(i) / 12.0
			var col := Color(0.28, 0.22, 0.5, 0.06 * (1.0 - t))
			draw_circle(c, r * (0.25 + 0.75 * t), col)


static func _all_filled(p: Array) -> bool:
	for v in p:
		if v == null:
			return false
	return true


static func _any_filled(p: Array) -> bool:
	for v in p:
		if v != null:
			return true
	return false


static func _count_empty(p: Array) -> int:
	var n := 0
	for v in p:
		if v == null:
			n += 1
	return n


# ---------------------------------------------------------------------------
# UI smoke / screenshot API
# ---------------------------------------------------------------------------

func ui_get_phase() -> int:
	return game.phase


func ui_is_result_visible() -> bool:
	return _overlay.visible and _result_shown


func ui_is_overlay_visible() -> bool:
	return _overlay.visible


func ui_dismiss_overlay() -> void:
	_overlay.visible = false
	_set_paused(false)


func ui_action_select_locus(i: int) -> void:
	_on_locus_tapped(i)


func ui_action_pick_spell(spell_id: int) -> void:
	_on_tray_tapped(spell_id)


func ui_action_clear() -> void:
	_on_clear_pressed()


func ui_action_lock_ward() -> void:
	_on_lock_pressed()


func ui_action_cast() -> void:
	_on_cast_pressed()


func ui_action_play_again() -> void:
	_overlay.visible = false
	start_new_game(-1)


func ui_action_menu() -> void:
	_on_menu_pressed()


func ui_action_history_tab(rival: bool) -> void:
	_set_history_tab(rival)


func ui_action_tap_history_row(index_from_latest: int) -> void:
	var count := 0
	var rows := _history_rows.duplicate()
	rows.reverse()
	for r in rows:
		if r["attacker"] == "player":
			if count == index_from_latest:
				_on_history_row_tapped(r["pattern"])
				return
			count += 1


func ui_advance_time(seconds: float) -> void:
	game.advance_time_for_test(seconds)
	_consume_events()
	_refresh_all()


func ui_get_locus_values() -> Array:
	var out: Array = []
	for s in _loci_slots:
		out.append(s.spell_id)
	return out


func ui_get_selected_locus() -> int:
	return _selected_locus


func ui_get_visible_history_count() -> int:
	var n := 0
	for r in _history_rows:
		if (r["attacker"] == "player") != _history_showing_rival:
			n += 1
	return n


func ui_get_result_banner_visible() -> bool:
	return _result_banner.visible


func ui_get_result_text() -> String:
	return _result_text_lbl.text


func ui_get_hint_text() -> String:
	return _hint_lbl.text


func ui_get_cast_button_state() -> int:
	return _cast_button.state


func ui_get_cast_button_rect() -> Rect2:
	return _cast_button.get_global_rect()


func ui_get_tray_count() -> int:
	return _tray_slots.size()


func ui_can_player_cast() -> bool:
	return game.can_player_cast()


func ui_get_rival_ward_revealed() -> bool:
	for s in _rival_ward_slots:
		if s.hidden_mode:
			return false
	return true


func ui_set_fast_cast(on: bool) -> void:
	game.set_testing_fast_cast(on)


func ui_debug_finish_duel(outcome: String) -> void:
	game.force_finish_for_test(outcome)
	_show_result()


func ui_audit_capture() -> Dictionary:
	var touch: Array = []
	var text_nodes: Array = []
	_audit_control(self, touch, text_nodes)
	return {"touch_targets": touch, "text_nodes": text_nodes}


func _audit_control(node: Node, touch: Array, text_nodes: Array) -> void:
	if node is Control and (node as Control).is_visible_in_tree():
		var c := node as Control
		if node is Button and not (node as Button).disabled:
			var role := "utility"
			if node.get_parent() == _cast_button:
				role = "cast"
			elif node in _loci_slots:
				role = "locus"
			elif node in _tray_slots:
				role = "essence"
			touch.append({
				"name": node.name if node.name != "" else node.get_class(),
				"width": c.size.x, "height": c.size.y, "role": role,
				"global_y": c.get_global_rect().position.y,
			})
		if node is Label and (node as Label).text != "":
			text_nodes.append({"visible": true, "text": (node as Label).text})
	for child in node.get_children():
		_audit_control(child, touch, text_nodes)
