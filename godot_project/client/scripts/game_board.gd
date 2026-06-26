extends Control
class_name GameBoard

const _RealtimeSim = preload("res://sim/realtime_duel_sim.gd")
const _MagicPickerScript = preload("res://client/components/magic_picker.gd")
const _Art = preload("res://client/scripts/art.gd")
const _AnimController = preload("res://client/scripts/duel_animation_controller.gd")
const _DuelEvent = preload("res://sim/duel_event.gd")

const HOW_TO_PLAY_TEXT := (
	"How to play:\n"
	+ "• Choose an essence for each locus to set your hidden ward.\n"
	+ "• Lock your ward — the rival wizard sets theirs too.\n"
	+ "• Build attack patterns and Cast when your cast window opens.\n"
	+ "• Fracture = correct essence, correct locus.\n"
	+ "• Echo = correct essence, wrong locus.\n"
	+ "• Fade = no useful match.\n"
	+ "• Feedback is always aggregate — never positional."
)
const HOW_FEEDBACK_TEXT := (
	"How feedback works:\n"
	+ "Each attack tells you how many essences were exactly right, "
	+ "how many were present but displaced, and how many faded. "
	+ "It never tells you which specific locus caused each result.\n\n"
	+ "• Fracture = correct essence, correct locus.\n"
	+ "• Echo = correct essence, wrong locus.\n"
	+ "• Fade = no useful match."
)

signal game_finished

@onready var background: TextureRect = $Background
@onready var status_label: Label = $VBox/StatusLabel
@onready var player_timer_label: Label = $VBox/PlayerTimerLabel
@onready var enemy_timer_label: Label = $VBox/DuelPanel/EnemyColumn/EnemyTimerLabel
@onready var secret_row: HBoxContainer = $VBox/DuelPanel/PlayerColumn/SecretSection/SecretRow
@onready var lock_button: Button = $VBox/DuelPanel/PlayerColumn/SecretSection/SecretRow/LockButton
@onready var bot_board: VBoxContainer = $VBox/DuelPanel/EnemyColumn/BotScroll/BotBoard
@onready var bot_scroll: ScrollContainer = $VBox/DuelPanel/EnemyColumn/BotScroll
@onready var human_attack_section: VBoxContainer = $VBox/DuelPanel/PlayerColumn/HumanAttackSection
@onready var human_history_board: VBoxContainer = $VBox/DuelPanel/PlayerColumn/HumanAttackSection/HumanHistoryScroll/HumanHistoryBoard
@onready var human_history_scroll: ScrollContainer = $VBox/DuelPanel/PlayerColumn/HumanAttackSection/HumanHistoryScroll
@onready var human_guess_section: VBoxContainer = $VBox/HumanGuessSection
@onready var human_guess_row: HBoxContainer = $VBox/HumanGuessSection/HumanGuessRow
@onready var submit_button: Button = $VBox/HumanGuessSection/HumanGuessRow/SubmitButton
@onready var result_panel: PanelContainer = $VBox/ResultPanel
@onready var result_label: Label = $VBox/ResultPanel/ResultLabel
@onready var restart_button: Button = $VBox/RestartButton
@onready var back_to_menu_button: Button = $VBox/BackToMenuButton
@onready var player_wizard: TextureRect = $VBox/DuelPanel/PlayerColumn/PlayerWizardRow/PlayerWizard
@onready var enemy_wizard: TextureRect = $VBox/DuelPanel/EnemyColumn/EnemyWizardRow/EnemyWizard
@onready var enemy_wizard_label: Label = $VBox/DuelPanel/EnemyColumn/EnemyWizardRow/EnemyWizardLabel
@onready var enemy_tell_label: Label = $VBox/DuelPanel/EnemyColumn/EnemyTellLabel
@onready var secret_point_headers: HBoxContainer = $VBox/DuelPanel/PlayerColumn/SecretSection/SecretPointHeaders
@onready var human_point_headers: HBoxContainer = $VBox/HumanGuessSection/HumanPointHeaders
@onready var how_to_play_button: Button = $VBox/HelpRow/HowToPlayButton
@onready var how_feedback_button: Button = $VBox/HelpRow/HowFeedbackButton
@onready var help_content: PanelContainer = $VBox/HelpContent
@onready var help_label: Label = $VBox/HelpContent/HelpLabel
@onready var animation_area: Control = $VBox/AnimationArea
@onready var pause_button: Button = $VBox/PauseRow/PauseButton
@onready var history_toggle: Button = $VBox/PauseRow/HistoryToggle

var game
var sim:
	get:
		return game

var _magic_picker: PanelContainer
var _secret_slots: Array = []
var _guess_slots: Array = []
var _bot_rows: Array = []
var _human_rows: Array = []
var _active_mode: String = ""
var _active_slot: int = -1
var _bot_seed: int = 42
var _ruleset: DmbDuelRuleset
var _active_pool: Array = []
var _help_mode: String = ""
var _paused: bool = false
var _anim
var _history_expanded: bool = true


func _session() -> Node:
	return get_node("/root/EncounterSession")


func _ready() -> void:
	_ruleset = _session().get_ruleset()
	_build_board_from_ruleset()
	_setup_art()
	_apply_encounter_presentation()
	_anim = _AnimController.new()
	_anim.setup(self, animation_area)
	_magic_picker = _MagicPickerScript.new()
	_magic_picker.name = "MagicPicker"
	add_child(_magic_picker)
	_magic_picker.magic_selected.connect(_on_magic_selected)
	lock_button.pressed.connect(_on_lock_pressed)
	submit_button.pressed.connect(_on_submit_pressed)
	restart_button.pressed.connect(_on_restart_pressed)
	back_to_menu_button.pressed.connect(_on_back_to_menu_pressed)
	how_to_play_button.pressed.connect(_on_how_to_play_pressed)
	how_feedback_button.pressed.connect(_on_how_feedback_pressed)
	pause_button.pressed.connect(_on_pause_pressed)
	history_toggle.pressed.connect(_on_history_toggle_pressed)
	lock_button.text = "Lock ward"
	submit_button.text = "Cast"
	start_new_game(_bot_seed)


func _process(delta: float) -> void:
	if game == null or game.phase != _RealtimeSim.Phase.DUELING:
		return
	if _paused:
		return
	game.advance_time(delta)
	_consume_sim_events()
	_refresh_timers()
	_refresh_submit()
	if game.result != null:
		_show_result()


func _build_board_from_ruleset() -> void:
	_secret_slots = _build_slots(secret_row, _ruleset.slot_count, _ruleset.point_names, _on_secret_slot_pressed)
	_guess_slots = _build_slots(human_guess_row, _ruleset.slot_count, _ruleset.point_names, _on_guess_slot_pressed, 1)
	_setup_point_headers(secret_point_headers, _ruleset.point_names)
	_setup_point_headers(human_point_headers, _ruleset.point_names)


func _build_slots(row: HBoxContainer, count: int, point_names: Array, callback: Callable, insert_after: int = 0) -> Array:
	var to_remove: Array = []
	for child in row.get_children():
		if child is PegSlot:
			to_remove.append(child)
	for child in to_remove:
		row.remove_child(child)
		child.queue_free()
	var slots: Array = []
	for i in range(count):
		var slot := PegSlot.new()
		slot.slot_index = i
		if i < point_names.size():
			slot.point_label = str(point_names[i])
		row.add_child(slot)
		row.move_child(slot, insert_after + i)
		slot.slot_pressed.connect(callback)
		slots.append(slot)
	return slots


func _apply_encounter_presentation() -> void:
	enemy_wizard_label.text = _ruleset.enemy_name
	var tex := _Art.enemy_portrait_path(_ruleset.enemy_archetype)
	var enemy_tex := _Art.load_texture(tex)
	if enemy_tex != null:
		enemy_wizard.texture = enemy_tex
	if _ruleset.enemy_visual_hint != "":
		enemy_tell_label.text = "Rival tell: %s" % _ruleset.enemy_visual_hint
		enemy_tell_label.visible = true
	else:
		enemy_tell_label.visible = false


func _setup_art() -> void:
	var bg_tex := _Art.load_texture("sprites/duel_background.png")
	if bg_tex != null:
		background.texture = bg_tex
	else:
		background.visible = false
	var player_tex := _Art.load_texture("sprites/player_wizard.png")
	if player_tex != null:
		player_wizard.texture = player_tex


func _setup_point_headers(container: HBoxContainer, point_names: Array) -> void:
	for c in container.get_children():
		c.queue_free()
	for i in range(point_names.size()):
		var cell := _make_point_header_cell(i, str(point_names[i]))
		container.add_child(cell)


func _make_point_header_cell(point_index: int, point_name: String) -> VBoxContainer:
	var cell := VBoxContainer.new()
	cell.alignment = BoxContainer.ALIGNMENT_CENTER
	cell.custom_minimum_size = Vector2(56, 0)
	var icon_row := HBoxContainer.new()
	icon_row.alignment = BoxContainer.ALIGNMENT_CENTER
	var tex_path := _Art.locus_icon_path(point_index)
	var tex := _Art.load_texture(tex_path)
	if tex != null:
		var icon := TextureRect.new()
		icon.custom_minimum_size = Vector2(20, 20)
		icon.texture = tex
		icon.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon_row.add_child(icon)
	cell.add_child(icon_row)
	var lbl := Label.new()
	lbl.text = point_name
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cell.add_child(lbl)
	return cell


func start_new_game(bot_seed: int = 42) -> void:
	_bot_seed = bot_seed
	_ruleset = _session().get_ruleset()
	var diff = _session().get_difficulty_profile()
	game = _RealtimeSim.new(_ruleset, diff, bot_seed)
	_apply_encounter_presentation()
	_active_mode = ""
	_active_slot = -1
	_paused = false
	_magic_picker.close()
	result_panel.visible = false
	help_content.visible = false
	_help_mode = ""
	_clear_bot_rows()
	_clear_human_rows()
	_refresh_all()


func _on_secret_slot_pressed(slot: int) -> void:
	if game.phase != _RealtimeSim.Phase.WARD_SETUP:
		return
	_active_mode = "secret"
	_active_slot = slot
	_active_pool = _ruleset.secret_magic_pool
	_magic_picker.set_allowed_magics(_active_pool)
	_open_picker_for_slot(_secret_slots[slot])


func _on_guess_slot_pressed(slot: int) -> void:
	if game.phase != _RealtimeSim.Phase.DUELING:
		return
	_active_mode = "attack"
	_active_slot = slot
	_active_pool = _ruleset.attack_magic_pool
	_magic_picker.set_allowed_magics(_active_pool)
	_open_picker_for_slot(_guess_slots[slot])


func _open_picker_for_slot(slot_ctrl: PegSlot) -> void:
	var vp := get_viewport_rect().size
	if vp.y > vp.x:
		_magic_picker.open_bottom_sheet(self)
	else:
		var pos := slot_ctrl.global_position + Vector2(0, slot_ctrl.size.y + 4)
		_magic_picker.open_at(pos)


func _on_magic_selected(colour: int) -> void:
	if _active_slot < 0:
		return
	if _active_mode == "secret":
		game.set_player_ward_locus(_active_slot, colour)
	elif _active_mode == "attack":
		game.set_player_attack_locus(_active_slot, colour)
	_active_slot = -1
	_refresh_all()


func _on_lock_pressed() -> void:
	if not game.can_lock_player_ward():
		return
	game.lock_player_ward_and_start()
	_refresh_all()


func _on_submit_pressed() -> void:
	if not game.can_player_cast():
		return
	if game.submit_player_attack():
		_consume_sim_events()
		_refresh_all()


func _consume_sim_events() -> void:
	var events: Array = game.get_pending_events()
	_anim.consume_events(events)
	for ev in events:
		if ev.type == _DuelEvent.FEEDBACK_REVEALED:
			_add_history_from_event(ev.data)
		if ev.type == _DuelEvent.DUEL_FINISHED:
			_show_result()


func _add_history_from_event(data: Dictionary) -> void:
	var pattern: Array = data.get("pattern_by_locus", [])
	var fracture := int(data.get("fracture_count", 0))
	var echo := int(data.get("echo_count", 0))
	var fade := int(data.get("fade_count", 0))
	var attacker := str(data.get("attacker_id", ""))
	if attacker == "player":
		_add_human_row_data(pattern, fracture, echo, fade)
	else:
		_add_bot_row_data(pattern, fracture, echo, fade)


func _on_restart_pressed() -> void:
	start_new_game(_bot_seed)


func _on_back_to_menu_pressed() -> void:
	get_tree().change_scene_to_file("res://client/scenes/main_menu.tscn")


func _on_pause_pressed() -> void:
	_paused = not _paused
	game.set_paused(_paused)
	pause_button.text = "Resume" if _paused else "Pause"


func _on_history_toggle_pressed() -> void:
	_history_expanded = not _history_expanded
	human_attack_section.visible = _history_expanded and game.phase != _RealtimeSim.Phase.WARD_SETUP
	bot_scroll.visible = _history_expanded
	history_toggle.text = "Show history" if not _history_expanded else "Hide history"


func _on_how_to_play_pressed() -> void:
	_toggle_help("play", HOW_TO_PLAY_TEXT)


func _on_how_feedback_pressed() -> void:
	_toggle_help("feedback", HOW_FEEDBACK_TEXT)


func _toggle_help(mode: String, text: String) -> void:
	if _help_mode == mode and help_content.visible:
		_help_mode = ""
		help_content.visible = false
	else:
		_help_mode = mode
		help_label.text = text
		help_content.visible = true


func _add_bot_row_data(pattern: Array, fracture: int, echo: int, fade: int) -> void:
	if _bot_rows.size() > 0:
		var prev: FeedbackDisplay = _bot_rows[_bot_rows.size() - 1]
		prev.set_highlighted(false)
	var row := FeedbackDisplay.new()
	row.name = "BotRow%d" % _bot_rows.size()
	bot_board.add_child(row)
	row.show_attack(pattern, fracture, echo, fade)
	row.set_highlighted(true)
	_bot_rows.append(row)
	_scroll_bot_board_to_end()


func _add_human_row_data(pattern: Array, fracture: int, echo: int, fade: int) -> void:
	if _human_rows.size() > 0:
		var prev: FeedbackDisplay = _human_rows[_human_rows.size() - 1]
		prev.set_highlighted(false)
	var row := FeedbackDisplay.new()
	row.name = "HumanRow%d" % _human_rows.size()
	human_history_board.add_child(row)
	row.show_attack(pattern, fracture, echo, fade)
	row.set_highlighted(true)
	_human_rows.append(row)
	_scroll_human_board_to_end()


func _scroll_bot_board_to_end() -> void:
	call_deferred("_deferred_scroll", bot_scroll)


func _scroll_human_board_to_end() -> void:
	call_deferred("_deferred_scroll", human_history_scroll)


func _deferred_scroll(scroll: ScrollContainer) -> void:
	await get_tree().process_frame
	var vbar := scroll.get_v_scroll_bar()
	if vbar != null:
		scroll.scroll_vertical = int(vbar.max_value)


func _clear_human_rows() -> void:
	for r in _human_rows:
		r.queue_free()
	_human_rows.clear()
	for c in human_history_board.get_children():
		c.queue_free()


func _clear_bot_rows() -> void:
	for r in _bot_rows:
		r.queue_free()
	_bot_rows.clear()
	for c in bot_board.get_children():
		c.queue_free()


func _refresh_all() -> void:
	_update_status()
	_update_secret_row()
	_update_lock_button()
	_update_magic_picker()
	_update_attack_row()
	_refresh_submit()
	_refresh_timers()


func _update_status() -> void:
	match game.phase:
		_RealtimeSim.Phase.WARD_SETUP:
			status_label.text = "Set your hidden ward pattern"
		_RealtimeSim.Phase.DUELING:
			var st = game.get_current_state()
			status_label.text = (
				"Real-time duel — Casts remaining: %d"
				% int(st.get("player_attacks_remaining", 0))
			)
		_RealtimeSim.Phase.FINISHED:
			status_label.text = "Duel result"


func _refresh_timers() -> void:
	if game.phase != _RealtimeSim.Phase.DUELING:
		player_timer_label.text = ""
		enemy_timer_label.text = ""
		return
	var st = game.get_current_state()
	var p_ready := float(st.get("player_time_until_cast", 0.0))
	var p_auto := float(st.get("player_time_until_auto", 0.0))
	var e_auto := float(st.get("enemy_time_until_auto", 0.0))
	if p_ready > 0.01:
		player_timer_label.text = "Cast in %.1fs" % p_ready
	elif game.can_player_cast():
		player_timer_label.text = "Cast ready"
	else:
		player_timer_label.text = "Auto-cast in %.1fs" % p_auto
	enemy_timer_label.text = "Rival pressure: %.1fs" % e_auto
	if p_auto <= 3.0 and not _ruleset.tutorial_flags.get("suppress_auto_cast_warnings", false):
		player_timer_label.modulate = Color(1.0, 0.7, 0.7)


func _update_secret_row() -> void:
	var setup = game.phase == _RealtimeSim.Phase.WARD_SETUP
	for i in range(_secret_slots.size()):
		var slot: PegSlot = _secret_slots[i]
		if setup:
			slot.disabled = false
			var ward = game.get_player_ward()
			var c = ward[i] if i < ward.size() else null
			slot.set_colour(c if c != null else -1)
		else:
			slot.set_hidden_mode()
	lock_button.visible = setup


func _update_lock_button() -> void:
	lock_button.disabled = not game.can_lock_player_ward()


func _update_magic_picker() -> void:
	var active = (
		game.phase == _RealtimeSim.Phase.WARD_SETUP
		or game.phase == _RealtimeSim.Phase.DUELING
	)
	_magic_picker.set_interactive(active)
	if not active:
		_magic_picker.close()


func _update_attack_row() -> void:
	var in_duel = game.phase == _RealtimeSim.Phase.DUELING
	var finished = game.phase == _RealtimeSim.Phase.FINISHED
	human_attack_section.visible = (in_duel or finished) and _history_expanded
	human_guess_section.visible = in_duel or finished
	bot_scroll.visible = _history_expanded
	for i in range(_guess_slots.size()):
		var slot: PegSlot = _guess_slots[i]
		slot.disabled = not in_duel
		if in_duel:
			var pattern = game.get_player_attack_pattern()
			var c = pattern[i] if i < pattern.size() else null
			slot.set_colour(c if c != null else -1)
		else:
			slot.set_colour(-1)


func _refresh_submit() -> void:
	submit_button.disabled = not game.can_player_cast()


func _show_result() -> void:
	if not result_panel.visible and game.result:
		result_panel.visible = true
		var r = game.result
		var headline = r.message
		var winner := "Draw"
		match r.outcome:
			"victory", "human_win":
				winner = "You"
			"defeat", "bot_win":
				winner = "Rival wizard"
			"clash":
				winner = "Clash"
			"stalemate", "draw":
				winner = "Stalemate"
		result_label.text = (
			"Duel result\n\n"
			+ "%s\n\n" % headline
			+ "Outcome: %s\n\n" % winner
			+ "Your casts: %d\n" % r.human_guess_count
			+ "Rival casts: %d" % r.bot_guess_count
		)
		game_finished.emit()


# --- UI smoke / test API ---

func ui_get_lock_button_enabled() -> bool:
	return not lock_button.disabled


func ui_get_visible_bot_guess_count() -> int:
	return _bot_rows.size()


func ui_get_human_guess_row_active() -> bool:
	return not _guess_slots[0].disabled if _guess_slots.size() > 0 else false


func ui_is_result_visible() -> bool:
	return result_panel.visible


func ui_is_picker_open() -> bool:
	return _magic_picker.is_open()


func ui_action_pick_secret_slot(slot: int) -> void:
	_on_secret_slot_pressed(slot)


func ui_action_pick_magic(colour: int) -> void:
	if not _magic_picker.is_open():
		_fail_smoke_picker()
		return
	_on_magic_selected(colour)


func ui_action_pick_colour(colour: int) -> void:
	ui_action_pick_magic(colour)


func ui_action_lock_secret() -> void:
	_on_lock_pressed()


func ui_action_pick_guess_slot(slot: int) -> void:
	_on_guess_slot_pressed(slot)


func ui_action_submit_guess() -> void:
	_on_submit_pressed()


func ui_action_restart() -> void:
	_on_restart_pressed()


func ui_get_visible_human_guess_count() -> int:
	return _human_rows.size()


func ui_get_human_feedback_text() -> String:
	if _human_rows.is_empty():
		return ""
	var row: FeedbackDisplay = _human_rows[_human_rows.size() - 1]
	return row.get_feedback_text()


func ui_get_phase() -> int:
	return game.phase


func ui_is_human_turn() -> bool:
	return game.phase == _RealtimeSim.Phase.DUELING


func ui_is_bot_turn() -> bool:
	return false


func ui_get_bot_feedback_count() -> int:
	return _bot_rows.size()


func ui_secret_is_hidden() -> bool:
	if _secret_slots.is_empty():
		return false
	return _secret_slots[0].text == "****"


func ui_get_secret_slot_value(slot: int) -> int:
	if slot < 0 or slot >= _secret_slots.size():
		return -1
	return _secret_slots[slot].get_colour_id()


func ui_get_guess_slot_value(slot: int) -> int:
	if slot < 0 or slot >= _guess_slots.size():
		return -1
	return _guess_slots[slot].get_colour_id()


func ui_get_bot_feedback_text() -> String:
	if _bot_rows.is_empty():
		return ""
	var row: FeedbackDisplay = _bot_rows[_bot_rows.size() - 1]
	return row.get_feedback_text()


func ui_set_difficulty(level: String) -> void:
	_session().set_difficulty(level)


func ui_get_difficulty() -> String:
	return _session().selected_difficulty_id


func ui_set_bot_pacing(_delay_sec: float, _skip_immediately: bool = false) -> void:
	game.set_testing_fast_cast(true)


func ui_skip_bot_attacks() -> void:
	pass


func ui_advance_time(seconds: float) -> void:
	game.advance_time_for_test(seconds)
	_consume_sim_events()
	_refresh_all()


func ui_can_player_cast() -> bool:
	return game.can_player_cast()


func ui_has_wizard_portraits() -> bool:
	return player_wizard.texture != null and enemy_wizard.texture != null


func ui_has_point_headers() -> bool:
	return (
		secret_point_headers.get_child_count() == _ruleset.slot_count
		and human_point_headers.get_child_count() == _ruleset.slot_count
	)


func ui_load_encounter(encounter_id: String) -> void:
	_session().set_encounter(encounter_id)
	_ruleset = _session().get_ruleset()
	_build_board_from_ruleset()
	_apply_encounter_presentation()
	start_new_game(_bot_seed)
	game.set_testing_fast_cast(true)


func ui_get_slot_count() -> int:
	return _ruleset.slot_count


func ui_get_visible_magic_count() -> int:
	var count := 0
	for i in range(DmbConstants.NUM_COLOURS):
		if _magic_picker._buttons[i].visible:
			count += 1
	return count


func ui_get_enemy_tell_visible() -> bool:
	return enemy_tell_label.visible and enemy_tell_label.text != ""


func ui_has_help_panel() -> bool:
	return how_to_play_button != null and how_feedback_button != null


func _fail_smoke_picker() -> void:
	push_error("Magic picker not open")
