extends Control
class_name GameBoard

const _VT = preload("res://client/scripts/visual_theme.gd")
const _RealtimeSim = preload("res://sim/realtime_duel_sim.gd")
const _MagicPickerScript = preload("res://client/components/magic_picker.gd")
const _Art = preload("res://client/scripts/art.gd")
const _AnimController = preload("res://client/scripts/duel_animation_controller.gd")
const _DuelEvent = preload("res://sim/duel_event.gd")
const _CompositeWizard = preload("res://client/components/composite_wizard.gd")
const _WardBarrier = preload("res://client/components/ward_barrier.gd")
const _CastButton = preload("res://client/components/cast_button.gd")
const _LocusSocket = preload("res://client/components/locus_socket.gd")
const _CastTimer = preload("res://client/components/cast_timer.gd")
const _FeedbackChip = preload("res://client/components/feedback_chip.gd")
const _HistoryRow = preload("res://client/components/history_row.gd")
const _EssenceTray = preload("res://client/components/essence_tray.gd")
const _EssenceToken = preload("res://client/components/essence_token.gd")
const _FtueOverlay = preload("res://client/components/ftue_overlay.gd")
const _RivalCastIndicator = preload("res://client/components/rival_cast_indicator.gd")
const _PlayabilityHaptics = preload("res://client/scripts/playability_haptics.gd")
const _SaveData = preload("res://client/scripts/save_data.gd")

const HOW_TO_PLAY_TEXT := (
	"Choose essences for each locus to set your hidden ward. Lock it, then cast attacks "
	+ "when your cast window opens. Fracture = exact match. Echo = wrong locus. "
	+ "Fade = miss. Feedback is always aggregate."
)

signal game_finished

@onready var background: ColorRect = $Background
@onready var bg_texture: TextureRect = $BgTexture
@onready var status_label: Label = $Margin/MainVBox/TopBar/StatusLabel
@onready var player_timer_label: Label = $Margin/MainVBox/BottomZone/PlayerTimerLabel
@onready var enemy_timer_label: Label = $Margin/MainVBox/TopZone/EnemyRow/EnemyInfo/EnemyTimerLabel
@onready var secret_row: HBoxContainer = $Margin/MainVBox/BottomZone/SecretSection/SecretRow
@onready var lock_button: Button = $Margin/MainVBox/BottomZone/SecretSection/SecretRow/LockButton
@onready var secret_section: VBoxContainer = $Margin/MainVBox/BottomZone/SecretSection
@onready var attack_section: VBoxContainer = $Margin/MainVBox/BottomZone/AttackSection
@onready var bot_board: VBoxContainer = $HistorySheet/SheetVBox/BotScroll/BotBoard
@onready var bot_scroll: ScrollContainer = $HistorySheet/SheetVBox/BotScroll
@onready var human_history_board: VBoxContainer = $HistorySheet/SheetVBox/HumanHistoryScroll/HumanHistoryBoard
@onready var human_history_scroll: ScrollContainer = $HistorySheet/SheetVBox/HumanHistoryScroll
@onready var human_guess_row: HBoxContainer = $Margin/MainVBox/BottomZone/AttackSection/HumanGuessRow
@onready var result_panel: PanelContainer = $ResultPanel
@onready var result_label: Label = $ResultPanel/ResultLabel
@onready var restart_button: Button = $Margin/MainVBox/NavRow/RestartButton
@onready var back_to_menu_button: Button = $Margin/MainVBox/NavRow/BackToMenuButton
@onready var enemy_wizard_host: Control = $Margin/MainVBox/TopZone/EnemyRow/EnemyWizardHost
@onready var player_wizard_host: Control = $Margin/MainVBox/BottomZone/PlayerWizardHost
@onready var ward_host: Control = $Margin/MainVBox/TopZone/WardHost
@onready var enemy_wizard_label: Label = $Margin/MainVBox/TopZone/EnemyRow/EnemyInfo/EnemyWizardLabel
@onready var enemy_tell_label: Label = $Margin/MainVBox/TopZone/EnemyRow/EnemyInfo/EnemyTellLabel
@onready var secret_point_headers: HBoxContainer = $Margin/MainVBox/BottomZone/SecretSection/SecretPointHeaders
@onready var human_point_headers: HBoxContainer = $Margin/MainVBox/BottomZone/AttackSection/HumanPointHeaders
@onready var help_button: Button = $Margin/MainVBox/TopBar/HelpButton
@onready var help_modal: PanelContainer = $HelpModal
@onready var help_label: Label = $HelpModal/HelpLabel
@onready var animation_area: Control = $Margin/MainVBox/MiddleZone/AnimationArea
@onready var attack_travel_layer: Control = $Margin/MainVBox/MiddleZone/AttackTravelLayer
@onready var latest_result_cluster: HBoxContainer = $Margin/MainVBox/MiddleZone/LatestResultCluster
@onready var pause_button: Button = $Margin/MainVBox/TopBar/PauseButton
@onready var history_toggle: Button = $Margin/MainVBox/TopBar/HistoryToggle
@onready var history_sheet: PanelContainer = $HistorySheet
@onready var history_peek: VBoxContainer = $Margin/MainVBox/BottomZone/HistoryPeek
@onready var cast_timer_host: Control = $Margin/MainVBox/BottomZone/CastRow/CastTimerHost
@onready var cast_button_host: Control = $Margin/MainVBox/BottomZone/CastRow/CastButtonHost
@onready var bottom_zone: VBoxContainer = $Margin/MainVBox/BottomZone
@onready var cast_row: HBoxContainer = $Margin/MainVBox/BottomZone/CastRow
@onready var enemy_info: VBoxContainer = $Margin/MainVBox/TopZone/EnemyRow/EnemyInfo

var game
var sim:
	get:
		return game

var _magic_picker: PanelContainer
var _secret_slots: Array = []
var _guess_slots: Array = []
var _bot_rows: Array = []
var _human_rows: Array = []
var _peek_rows: Array = []
var _active_mode: String = ""
var _active_slot: int = -1
var _bot_seed: int = 42
var _ruleset: DmbDuelRuleset
var _active_pool: Array = []
var _paused: bool = false
var _anim
var _history_expanded: bool = false
var _enemy_wizard
var _player_wizard
var _enemy_ward
var _cast_button
var _cast_timer
var _feedback_chips: Array = []
var _debug_hold_animation: bool = false
var _screenshot_mode: bool = false
var _essence_tray
var _ftue_overlay
var _rival_cast_indicator
var _interaction_state: int = _VT.InteractionState.IDLE
var _feedback_locked: bool = false
var _player_cast_count: int = 0
var _ftue_completed: Dictionary = {}
var _drag_ghost: Control
var _drag_essence_id: int = -1
var _warn3_played: bool = false
var _duel_ftue_started: bool = false


func _session() -> Node:
	return get_node("/root/EncounterSession")


func _ready() -> void:
	_screenshot_mode = "--screenshot-mode" in OS.get_cmdline_user_args()
	_apply_theme()
	_ruleset = _session().get_ruleset()
	_build_board_from_ruleset()
	_setup_visual_components()
	_setup_art()
	_apply_encounter_presentation()
	_anim = _AnimController.new()
	_anim.setup(self, animation_area, attack_travel_layer, latest_result_cluster, _enemy_ward)
	_essence_tray = _EssenceTray.new()
	_essence_tray.name = "EssenceTray"
	attack_section.add_child(_essence_tray)
	attack_section.move_child(_essence_tray, 0)
	_essence_tray.essence_selected.connect(_on_tray_essence_selected)
	_essence_tray.essence_drag_started.connect(_on_tray_drag_started)
	_essence_tray.essence_drag_moved.connect(_on_tray_drag_moved)
	_essence_tray.essence_drag_ended.connect(_on_tray_drag_ended)
	_ftue_overlay = _FtueOverlay.new()
	_ftue_overlay.name = "FtueOverlay"
	add_child(_ftue_overlay)
	_ftue_overlay.step_completed.connect(_on_ftue_step_completed)
	_rival_cast_indicator = _RivalCastIndicator.new()
	_rival_cast_indicator.name = "RivalCastIndicator"
	enemy_info.add_child(_rival_cast_indicator)
	enemy_info.move_child(_rival_cast_indicator, 1)
	_apply_left_hand_layout()
	_magic_picker = _MagicPickerScript.new()
	_magic_picker.name = "MagicPicker"
	add_child(_magic_picker)
	_magic_picker.magic_selected.connect(_on_magic_selected)
	lock_button.pressed.connect(_on_lock_pressed)
	_cast_button.cast_pressed.connect(_on_submit_pressed)
	restart_button.pressed.connect(_on_restart_pressed)
	back_to_menu_button.pressed.connect(_on_back_to_menu_pressed)
	help_button.pressed.connect(_on_help_pressed)
	pause_button.pressed.connect(_on_pause_pressed)
	history_toggle.pressed.connect(_on_history_toggle_pressed)
	start_new_game(_bot_seed)


func _apply_theme() -> void:
	background.color = _VT.COLOR_BG_DEEP
	var text_bump := 4 if bool(_SaveData.get_setting("larger_text", false)) else 0
	help_modal.add_theme_stylebox_override("panel", _VT.panel_style())
	history_sheet.add_theme_stylebox_override("panel", _VT.panel_style())
	result_panel.add_theme_stylebox_override("panel", _VT.panel_style())
	_VT.apply_label_primary(status_label)
	status_label.add_theme_font_size_override("font_size", _VT.FONT_PRIMARY + text_bump)
	_VT.apply_label_secondary(player_timer_label)
	player_timer_label.add_theme_font_size_override("font_size", _VT.FONT_SECONDARY + text_bump)
	_VT.apply_label_secondary(enemy_timer_label)
	enemy_timer_label.add_theme_font_size_override("font_size", _VT.FONT_SECONDARY + text_bump)
	_VT.apply_label_primary(enemy_wizard_label)
	_VT.apply_label_secondary(enemy_tell_label)
	lock_button.add_theme_stylebox_override("normal", _VT.gem_button_style())
	restart_button.add_theme_stylebox_override("normal", _VT.secondary_button_style())
	back_to_menu_button.add_theme_stylebox_override("normal", _VT.secondary_button_style())
	pause_button.add_theme_stylebox_override("normal", _VT.secondary_button_style())
	history_toggle.add_theme_stylebox_override("normal", _VT.secondary_button_style())
	help_button.add_theme_stylebox_override("normal", _VT.secondary_button_style())


func _setup_visual_components() -> void:
	_enemy_wizard = _CompositeWizard.new()
	_enemy_wizard.set_anchors_preset(Control.PRESET_FULL_RECT)
	enemy_wizard_host.add_child(_enemy_wizard)
	_player_wizard = _CompositeWizard.new()
	_player_wizard.set_anchors_preset(Control.PRESET_FULL_RECT)
	player_wizard_host.add_child(_player_wizard)
	_player_wizard.load_archetype("player")
	_enemy_ward = _WardBarrier.new()
	_enemy_ward.set_anchors_preset(Control.PRESET_FULL_RECT)
	ward_host.add_child(_enemy_ward)
	_cast_timer = _CastTimer.new()
	_cast_timer.set_anchors_preset(Control.PRESET_FULL_RECT)
	cast_timer_host.add_child(_cast_timer)
	_cast_button = _CastButton.new()
	_cast_button.set_anchors_preset(Control.PRESET_FULL_RECT)
	cast_button_host.add_child(_cast_button)
	for kind in ["fracture", "echo", "fade"]:
		var chip := _FeedbackChip.new()
		latest_result_cluster.add_child(chip)
		chip.setup(kind, 0)
		chip.visible = false
		_feedback_chips.append(chip)


func _process(delta: float) -> void:
	if game == null or game.phase != _RealtimeSim.Phase.DUELING:
		return
	if _paused and not _debug_hold_animation:
		return
	if not _debug_hold_animation:
		game.advance_time(delta)
	_consume_sim_events()
	_refresh_timers()
	_refresh_submit()
	if game.result != null:
		_show_result()


func _build_board_from_ruleset() -> void:
	_secret_slots = _build_slots(secret_row, _ruleset.slot_count, _ruleset.point_names, _on_secret_slot_pressed)
	_guess_slots = _build_slots(human_guess_row, _ruleset.slot_count, _ruleset.point_names, _on_guess_slot_pressed)
	_setup_point_headers(secret_point_headers, _ruleset.point_names)
	_setup_point_headers(human_point_headers, _ruleset.point_names)


func _build_slots(row: HBoxContainer, count: int, point_names: Array, callback: Callable, insert_after: int = 0) -> Array:
	for child in row.get_children():
		if child is PegSlot:
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
		slot.slot_clear_requested.connect(_on_slot_clear_requested)
		slots.append(slot)
	return slots


func _apply_encounter_presentation() -> void:
	enemy_wizard_label.text = _ruleset.enemy_name
	var arch := _Art.wizard_archetype_from_enemy(_ruleset.enemy_archetype)
	_enemy_wizard.load_archetype(arch)
	if _ruleset.enemy_visual_hint != "":
		enemy_tell_label.text = _ruleset.enemy_visual_hint
		enemy_tell_label.visible = true
	else:
		enemy_tell_label.visible = false


func _setup_art() -> void:
	var bg_tex := _Art.load_texture("sprites/duel_background.png")
	if bg_tex != null:
		bg_texture.texture = bg_tex


func _setup_point_headers(container: HBoxContainer, point_names: Array) -> void:
	for c in container.get_children():
		c.queue_free()
	for i in range(point_names.size()):
		var lbl := Label.new()
		lbl.text = str(point_names[i])
		lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lbl.custom_minimum_size = Vector2(_VT.TOUCH_ESSENCE, 0)
		_VT.apply_label_secondary(lbl)
		container.add_child(lbl)


func start_new_game(bot_seed: int = 42) -> void:
	_bot_seed = bot_seed
	_ruleset = _session().get_ruleset()
	var diff = _session().get_difficulty_profile()
	game = _RealtimeSim.new(_ruleset, diff, bot_seed)
	_apply_encounter_presentation()
	_active_mode = ""
	_active_slot = -1
	_paused = false
	_interaction_state = _VT.InteractionState.IDLE
	_feedback_locked = false
	_player_cast_count = 0
	_ftue_completed.clear()
	_duel_ftue_started = false
	_ftue_overlay.hide_step()
	_warn3_played = false
	_magic_picker.close()
	result_panel.visible = false
	help_modal.visible = false
	history_sheet.visible = false
	_clear_bot_rows()
	_clear_human_rows()
	_clear_peek_rows()
	_clear_latest_result()
	_enemy_ward.set_state(_WardBarrier.State.STABLE)
	_refresh_all()


func _on_secret_slot_pressed(slot: int) -> void:
	if game.phase != _RealtimeSim.Phase.WARD_SETUP or _feedback_locked:
		return
	_set_interaction_state(_VT.InteractionState.LOCUS_SELECTED)
	_active_mode = "secret"
	_active_slot = slot
	_active_pool = _ruleset.secret_magic_pool
	_highlight_locus_slots(_secret_slots, slot)
	_populate_essence_controls(_active_pool)
	_open_picker_for_slot(_secret_slots[slot])


func _on_guess_slot_pressed(slot: int) -> void:
	if game.phase != _RealtimeSim.Phase.DUELING or _feedback_locked:
		return
	_set_interaction_state(_VT.InteractionState.LOCUS_SELECTED)
	_active_mode = "attack"
	_active_slot = slot
	_active_pool = _ruleset.attack_magic_pool
	_highlight_locus_slots(_guess_slots, slot)
	_populate_essence_controls(_active_pool)
	_open_picker_for_slot(_guess_slots[slot])
	_update_ftue_after_locus_tap()


func _on_slot_clear_requested(slot: int) -> void:
	if _feedback_locked:
		return
	if game.phase == _RealtimeSim.Phase.WARD_SETUP:
		game.set_player_ward_locus(slot, -1)
	elif game.phase == _RealtimeSim.Phase.DUELING:
		game.set_player_attack_locus(slot, -1)
	_active_slot = -1
	_set_interaction_state(_VT.InteractionState.IDLE)
	_refresh_all()


func _highlight_locus_slots(slots: Array, active: int) -> void:
	for i in range(slots.size()):
		slots[i].set_selected(i == active)


func _populate_essence_controls(pool: Array) -> void:
	_essence_tray.set_allowed_magics(pool)
	_magic_picker.set_allowed_magics(pool)
	_essence_tray.set_highlighted(_active_slot >= 0)


func _open_picker_for_slot(slot_ctrl: PegSlot) -> void:
	var socket = slot_ctrl.get_locus_socket()
	if socket != null:
		_magic_picker.open_above_anchor(socket)
		_set_interaction_state(_VT.InteractionState.ESSENCE_PICKER_OPEN)
	else:
		_magic_picker.open_bottom_sheet(self)


func _on_magic_selected(colour: int) -> void:
	if _active_slot < 0 or _feedback_locked:
		return
	if _active_mode == "secret":
		game.set_player_ward_locus(_active_slot, colour)
	elif _active_mode == "attack":
		game.set_player_attack_locus(_active_slot, colour)
		_guess_slots[_active_slot].get_locus_socket().pulse()
		_update_ftue_after_essence_placed()
	_active_slot = -1
	_highlight_locus_slots(_guess_slots if _active_mode == "attack" else _secret_slots, -1)
	_essence_tray.set_highlighted(false)
	_magic_picker.close()
	_set_interaction_state(_VT.InteractionState.SOCKET_FILLED)
	_PlayabilityHaptics.pulse_light()
	_refresh_all()


func _on_tray_essence_selected(colour: int) -> void:
	if _active_slot < 0:
		if game.phase == _RealtimeSim.Phase.DUELING and not _guess_slots.is_empty():
			_on_guess_slot_pressed(0)
		elif game.phase == _RealtimeSim.Phase.WARD_SETUP and not _secret_slots.is_empty():
			_on_secret_slot_pressed(0)
		else:
			return
	_on_magic_selected(colour)


func _on_lock_pressed() -> void:
	if not game.can_lock_player_ward():
		return
	game.lock_player_ward_and_start()
	_refresh_all()


func _on_submit_pressed() -> void:
	if not game.can_player_cast() or _feedback_locked:
		return
	_set_interaction_state(_VT.InteractionState.CASTING)
	_set_feedback_locked(true)
	_cast_button.bounce_press()
	_player_wizard.play_cast_windup()
	if game.submit_player_attack():
		_player_cast_count += 1
		_consume_sim_events()
		_update_ftue_after_cast()
	_refresh_all()


func _consume_sim_events() -> void:
	var events: Array = game.get_pending_events()
	_anim.consume_events(events)
	for ev in events:
		if ev.type == _DuelEvent.FEEDBACK_REVEALED:
			_add_history_from_event(ev.data)
		if ev.type == _DuelEvent.WARD_BROKEN:
			_enemy_ward.set_state(_WardBarrier.State.FRACTURED)
		if ev.type == _DuelEvent.LAST_STAND_STARTED:
			_enemy_ward.set_state(_WardBarrier.State.UNSTABLE)
			_enemy_wizard.play_last_stand()
		if ev.type == _DuelEvent.DUEL_FINISHED:
			_show_result()


func _show_latest_result(data: Dictionary, animate: bool = true) -> void:
	var fracture := int(data.get("fracture_count", 0))
	var echo := int(data.get("echo_count", 0))
	var fade := int(data.get("fade_count", 0))
	var kinds := ["fracture", "echo", "fade"]
	var values := [fracture, echo, fade]
	for i in range(_feedback_chips.size()):
		_feedback_chips[i].setup(kinds[i], values[i])
		_feedback_chips[i].visible = values[i] > 0 or kinds[i] == "fade"
		if animate:
			_feedback_chips[i].pop_in()
		else:
			_feedback_chips[i].scale = Vector2(0.3, 0.3)
			_feedback_chips[i].modulate.a = 0.0


func _clear_latest_result() -> void:
	for chip in _feedback_chips:
		chip.visible = false


func _start_feedback_sequence(data: Dictionary) -> void:
	_set_feedback_locked(true)
	_show_latest_result(data, false)
	var tree := get_tree()
	var anticipation := _VT.DUR_FEEDBACK_ANTICIPATION
	var emphasis := _VT.DUR_FEEDBACK_EMPHASIS
	var aftermath := _VT.DUR_FEEDBACK_AFTERMATH
	if bool(_SaveData.get_setting("reduce_motion", false)):
		anticipation = 0.05
		emphasis = 0.05
	tree.create_timer(anticipation).timeout.connect(func():
		if _enemy_ward:
			_enemy_ward.set_state(_WardBarrier.State.IMPACTED)
		tree.create_timer(emphasis).timeout.connect(func():
			for chip in _feedback_chips:
				if chip.visible:
					chip.pop_in()
					_PlayabilityHaptics.pulse_light()
			tree.create_timer(aftermath).timeout.connect(_on_feedback_unlock)
		)
	)
	tree.create_timer(_VT.DUR_FEEDBACK_LOCK).timeout.connect(_on_feedback_unlock)


func _on_feedback_unlock() -> void:
	if not _feedback_locked:
		return
	_set_feedback_locked(false)
	_set_interaction_state(_VT.InteractionState.IDLE)
	_refresh_all()
	_update_ftue_after_feedback()


func _set_feedback_locked(on: bool) -> void:
	_feedback_locked = on
	if on:
		_set_interaction_state(_VT.InteractionState.FEEDBACK_LOCKED)
	_essence_tray.set_busy(on)
	for slot in _guess_slots:
		slot.set_busy(on)
	attack_section.modulate = Color(0.82, 0.82, 0.9) if on else Color.WHITE


func _set_interaction_state(state: int) -> void:
	_interaction_state = state
	if state == _VT.InteractionState.CAST_READY and game != null and game.can_player_cast():
		_cast_button.set_cast_ready(true)


func _apply_left_hand_layout() -> void:
	var left_hand := bool(_SaveData.get_setting("left_hand_mode", false))
	if left_hand:
		cast_row.alignment = BoxContainer.ALIGNMENT_BEGIN
		cast_row.move_child(cast_button_host, 0)
		cast_row.move_child(cast_timer_host, 1)
		human_guess_row.alignment = BoxContainer.ALIGNMENT_BEGIN
	else:
		cast_row.alignment = BoxContainer.ALIGNMENT_CENTER
		cast_row.move_child(cast_timer_host, 0)
		cast_row.move_child(cast_button_host, 1)
		human_guess_row.alignment = BoxContainer.ALIGNMENT_CENTER


func _on_tray_drag_started(essence_id: int, global_pos: Vector2) -> void:
	_drag_essence_id = essence_id
	_spawn_drag_ghost(essence_id, global_pos)


func _on_tray_drag_moved(global_pos: Vector2) -> void:
	if _drag_ghost != null:
		_drag_ghost.global_position = global_pos - _drag_ghost.size * 0.5
	_highlight_drop_target(global_pos)


func _on_tray_drag_ended(global_pos: Vector2) -> void:
	var slot := _slot_at_global_point(global_pos)
	if slot >= 0:
		if game.phase == _RealtimeSim.Phase.WARD_SETUP:
			_active_mode = "secret"
			_active_slot = slot
			_on_magic_selected(_drag_essence_id)
		elif game.phase == _RealtimeSim.Phase.DUELING:
			_active_mode = "attack"
			_active_slot = slot
			_on_magic_selected(_drag_essence_id)
	_clear_drag_ghost()
	for s in _guess_slots:
		s.set_drop_highlight(false)
	_drag_essence_id = -1


func _spawn_drag_ghost(essence_id: int, global_pos: Vector2) -> void:
	_clear_drag_ghost()
	var token := _EssenceToken.new()
	token.set_essence(essence_id)
	token.custom_minimum_size = Vector2(_VT.TOUCH_ESSENCE, _VT.TOUCH_ESSENCE)
	token.size = token.custom_minimum_size
	token.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(token)
	token.global_position = global_pos - token.size * 0.5
	_drag_ghost = token


func _clear_drag_ghost() -> void:
	if _drag_ghost != null:
		_drag_ghost.queue_free()
		_drag_ghost = null


func _slot_at_global_point(point: Vector2) -> int:
	var slots := _guess_slots if game.phase == _RealtimeSim.Phase.DUELING else _secret_slots
	for i in range(slots.size()):
		if slots[i].get_global_rect().has_point(point):
			return i
	return -1


func _highlight_drop_target(global_pos: Vector2) -> void:
	var slot := _slot_at_global_point(global_pos)
	for i in range(_guess_slots.size()):
		_guess_slots[i].set_drop_highlight(i == slot and game.phase == _RealtimeSim.Phase.DUELING)


func _is_ftue_encounter() -> bool:
	return _ruleset.id == "blue_apprentice"


func _update_ftue_on_duel_start() -> void:
	if not _is_ftue_encounter():
		return
	if not _ftue_completed.has("locus"):
		_ftue_overlay.show_step("locus", _guess_slots[0], "Tap the locus socket")


func _update_ftue_after_locus_tap() -> void:
	if not _is_ftue_encounter() or _ftue_completed.has("locus"):
		return
	_ftue_overlay.complete_step("locus")
	if not _ftue_completed.has("essence"):
		_ftue_overlay.show_step("essence", _essence_tray, "Pick an essence")


func _update_ftue_after_essence_placed() -> void:
	if not _is_ftue_encounter() or _ftue_completed.has("essence"):
		return
	_ftue_overlay.complete_step("essence")


func _update_ftue_after_cast() -> void:
	if not _is_ftue_encounter():
		return
	if _player_cast_count == 1 and not _ftue_completed.has("cast"):
		_ftue_overlay.complete_step("cast")
	if _player_cast_count == 1 and not _ftue_completed.has("history"):
		_ftue_overlay.show_step("history", latest_result_cluster, "Grouped results — not per locus")
	if _player_cast_count == 2 and not _ftue_completed.has("timer"):
		_ftue_overlay.show_step("timer", _cast_timer, "Watch the cast timer")


func _update_ftue_after_feedback() -> void:
	if not _is_ftue_encounter():
		return
	if _player_cast_count >= 1 and not _ftue_completed.has("history"):
		_ftue_overlay.complete_step("history")
	if _player_cast_count >= 2 and not _ftue_completed.has("timer"):
		_ftue_overlay.complete_step("timer")


func _on_ftue_step_completed(step_id: String) -> void:
	_ftue_completed[step_id] = true
	if step_id == "locus" and game.can_player_cast() and not _ftue_completed.has("cast"):
		_ftue_overlay.show_step("cast", _cast_button, "Cast when ready")


func _refresh_ftue_cast_hint() -> void:
	if not _is_ftue_encounter() or _ftue_completed.has("cast"):
		return
	if game != null and game.can_player_cast() and _ftue_overlay.get_active_step() == "essence":
		_ftue_overlay.complete_step("essence")
		_ftue_overlay.show_step("cast", _cast_button, "Cast when ready")


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
	pause_button.text = "▶" if _paused else "⏸"


func _on_history_toggle_pressed() -> void:
	_history_expanded = not _history_expanded
	history_sheet.visible = _history_expanded
	history_toggle.text = "Close" if _history_expanded else "History"


func _on_help_pressed() -> void:
	help_modal.visible = not help_modal.visible
	if help_modal.visible:
		help_label.text = HOW_TO_PLAY_TEXT


func _add_bot_row_data(pattern: Array, fracture: int, echo: int, fade: int) -> void:
	var row := _HistoryRow.new()
	bot_board.add_child(row)
	row.show_attack(pattern, fracture, echo, fade)
	_bot_rows.append(row)
	_scroll_bot_board_to_end()


func _add_human_row_data(pattern: Array, fracture: int, echo: int, fade: int) -> void:
	var row := _HistoryRow.new()
	human_history_board.add_child(row)
	row.show_attack(pattern, fracture, echo, fade)
	_human_rows.append(row)
	_add_peek_row(pattern, fracture, echo, fade)
	_scroll_human_board_to_end()


func _add_peek_row(pattern: Array, fracture: int, echo: int, fade: int) -> void:
	var row := _HistoryRow.new()
	history_peek.add_child(row)
	row.show_attack(pattern, fracture, echo, fade)
	_peek_rows.append(row)
	while _peek_rows.size() > _VT.HISTORY_PEEK_MAX:
		var old = _peek_rows.pop_front()
		old.queue_free()


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


func _clear_peek_rows() -> void:
	for r in _peek_rows:
		r.queue_free()
	_peek_rows.clear()
	for c in history_peek.get_children():
		c.queue_free()


func _refresh_all() -> void:
	_update_status()
	_update_secret_row()
	_update_lock_button()
	_update_magic_picker()
	_update_attack_row()
	_refresh_submit()
	_refresh_timers()
	if game != null and game.phase == _RealtimeSim.Phase.DUELING and not _duel_ftue_started:
		_duel_ftue_started = true
		_update_ftue_on_duel_start()
	elif game != null and game.phase == _RealtimeSim.Phase.WARD_SETUP:
		_duel_ftue_started = false


func _update_status() -> void:
	match game.phase:
		_RealtimeSim.Phase.WARD_SETUP:
			status_label.text = "Set ward"
		_RealtimeSim.Phase.DUELING:
			var st = game.get_current_state()
			status_label.text = "Casts: %d" % int(st.get("player_attacks_remaining", 0))
		_RealtimeSim.Phase.FINISHED:
			status_label.text = "Result"


func _refresh_timers() -> void:
	if game.phase != _RealtimeSim.Phase.DUELING:
		player_timer_label.text = ""
		enemy_timer_label.text = ""
		_cast_timer.set_progress(0.0, "")
		_rival_cast_indicator.set_progress(0.0, false)
		return
	var st = game.get_current_state()
	var p_ready := float(st.get("player_time_until_cast", 0.0))
	var p_auto := float(st.get("player_time_until_auto", 0.0))
	var max_auto := float(_ruleset.base_max_cast_time_seconds)
	var e_auto := float(st.get("enemy_time_until_auto", 0.0))
	var suppress_warn: bool = _ruleset.tutorial_flags.get("suppress_auto_cast_warnings", false)
	if p_ready > 0.01:
		player_timer_label.text = "Cast in %.0fs" % p_ready
		_cast_timer.set_progress(1.0 - p_ready / maxf(max_auto, 0.1), "")
		_cast_timer.set_tier_seconds(999.0)
		_cast_button.set_visual_state(_CastButton.CastVisualState.CHARGING)
	elif game.can_player_cast():
		player_timer_label.text = "Cast ready"
		_cast_timer.set_progress(1.0, "✓")
		_cast_timer.set_tier_seconds(999.0)
		_cast_button.set_cast_ready(true)
		_set_interaction_state(_VT.InteractionState.CAST_READY)
		_refresh_ftue_cast_hint()
	else:
		player_timer_label.text = "Auto %.0fs" % p_auto
		_cast_timer.set_progress(1.0 - p_auto / maxf(max_auto, 0.1), "!")
		_cast_timer.set_tier_seconds(p_auto)
		_cast_button.set_cast_ready(false)
		if suppress_warn:
			_cast_button.set_visual_state(_CastButton.CastVisualState.DISABLED)
			_cast_timer.set_warning(false)
		else:
			_cast_button.set_auto_cast_tier(p_auto)
			var warn := p_auto <= 3.0
			_cast_timer.set_warning(warn)
			if p_auto <= 3.0 and not _warn3_played:
				_warn3_played = true
				_PlayabilityHaptics.pulse_warning()
	player_timer_label.modulate = Color(1.0, 0.7, 0.7) if p_auto <= 3.0 and not suppress_warn else _VT.COLOR_TEXT_SECONDARY
	enemy_timer_label.text = "Rival casting" if e_auto <= max_auto * 0.25 else "Rival %.0fs" % e_auto
	_rival_cast_indicator.set_progress(1.0 - e_auto / maxf(max_auto, 0.1), e_auto <= max_auto * 0.5)


func _update_secret_row() -> void:
	var setup = game.phase == _RealtimeSim.Phase.WARD_SETUP
	secret_section.visible = setup
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
	var active = game.phase == _RealtimeSim.Phase.WARD_SETUP or game.phase == _RealtimeSim.Phase.DUELING
	_magic_picker.set_interactive(active)
	if not active:
		_magic_picker.close()


func _update_attack_row() -> void:
	var in_duel = game.phase == _RealtimeSim.Phase.DUELING
	var finished = game.phase == _RealtimeSim.Phase.FINISHED
	attack_section.visible = in_duel or finished
	if in_duel:
		_essence_tray.set_allowed_magics(_ruleset.attack_magic_pool)
	elif game.phase == _RealtimeSim.Phase.WARD_SETUP:
		_essence_tray.set_allowed_magics(_ruleset.secret_magic_pool)
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
	var can_cast: bool = game.can_player_cast() and not _feedback_locked
	_cast_button.disabled = not can_cast
	if not can_cast and _cast_button.has_method("set_visual_state"):
		_cast_button.set_visual_state(_CastButton.CastVisualState.DISABLED)


func _show_result() -> void:
	if not result_panel.visible and game.result:
		result_panel.visible = true
		var r = game.result
		var headline = r.message
		var winner := "Draw"
		match r.outcome:
			"victory", "human_win":
				winner = "Victory"
			"defeat", "bot_win":
				winner = "Defeat"
			"clash":
				winner = "Clash"
			"stalemate", "draw":
				winner = "Stalemate"
		result_label.text = "%s\n\n%s\n\nYou: %d · Rival: %d" % [
			winner, headline, r.human_guess_count, r.bot_guess_count,
		]
		game_finished.emit()


# --- UI smoke / screenshot API ---

func ui_get_lock_button_enabled() -> bool:
	return not lock_button.disabled


func ui_get_visible_bot_guess_count() -> int:
	return _bot_rows.size()


func ui_get_human_guess_row_active() -> bool:
	if not attack_section.visible or _guess_slots.is_empty():
		return false
	return not _guess_slots[0].disabled


func ui_is_result_visible() -> bool:
	return result_panel.visible


func ui_is_picker_open() -> bool:
	return _magic_picker.is_open()


func ui_is_help_visible() -> bool:
	return help_modal.visible


func ui_get_visible_history_row_count() -> int:
	return _peek_rows.size()


func ui_set_history_expanded(on: bool) -> void:
	_history_expanded = on
	history_sheet.visible = on


func ui_action_pick_secret_slot(slot: int) -> void:
	_on_secret_slot_pressed(slot)


func ui_action_pick_magic(colour: int) -> void:
	if _active_slot < 0:
		if game.phase == _RealtimeSim.Phase.WARD_SETUP and not _secret_slots.is_empty():
			_on_secret_slot_pressed(0)
		elif game.phase == _RealtimeSim.Phase.DUELING and not _guess_slots.is_empty():
			_on_guess_slot_pressed(0)
	if _active_slot >= 0:
		_on_magic_selected(colour)
		return
	if game.phase == _RealtimeSim.Phase.DUELING:
		var pattern = game.get_player_attack_pattern()
		for i in range(pattern.size()):
			if pattern[i] == null:
				game.set_player_attack_locus(i, colour)
				_refresh_all()
				return
	_fail_smoke_picker()


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
	var row = _human_rows[_human_rows.size() - 1]
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
	return _secret_slots[0].get_locus_socket().is_hidden_mode()


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
	var row = _bot_rows[_bot_rows.size() - 1]
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
	return _enemy_wizard != null and _player_wizard != null


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
	return help_button != null


func ui_get_cast_button_size() -> Vector2:
	return _cast_button.size if _cast_button else Vector2.ZERO


func ui_get_cast_button_center_y_ratio() -> float:
	if _cast_button == null:
		return 0.0
	var center: float = _cast_button.get_global_rect().get_center().y
	return center / maxf(get_viewport_rect().size.y, 1.0)


func ui_is_feedback_locked() -> bool:
	return _feedback_locked


func ui_get_interaction_state() -> int:
	return _interaction_state


func ui_get_picker_above_locus() -> bool:
	if not _magic_picker.is_open() or _guess_slots.is_empty():
		return false
	var picker_rect: Rect2 = _magic_picker.get_global_rect()
	var locus_rect: Rect2 = _guess_slots[0].get_global_rect()
	return picker_rect.position.y < locus_rect.position.y


func ui_get_ftue_active() -> bool:
	return _ftue_overlay != null and _ftue_overlay.get_active_step() != ""


func ui_has_essence_tray() -> bool:
	return _essence_tray != null and _essence_tray.visible


func ui_debug_hold_animation(on: bool) -> void:
	_debug_hold_animation = on


func ui_debug_finish_duel(outcome: String) -> void:
	game.force_finish_for_test(outcome)
	_show_result()


func ui_debug_trigger_last_stand() -> void:
	_enemy_ward.set_state(_WardBarrier.State.UNSTABLE)
	_enemy_wizard.play_last_stand()


func ui_audit_capture() -> Dictionary:
	var touch: Array = []
	var text_nodes: Array = []
	_audit_control(self, touch, text_nodes)
	return {"touch_targets": touch, "text_nodes": text_nodes}


func _audit_control(node: Node, touch: Array, text_nodes: Array) -> void:
	if node is Control and (node as Control).visible:
		var c := node as Control
		if node is Button or node is PegSlot or node.name == "CastButton" or _is_essence_token(node):
			var role := "utility"
			if node.name == "CastButton" or node.get_parent() == cast_button_host:
				role = "cast"
			elif node is PegSlot:
				role = "locus"
			elif _is_essence_token(node):
				role = "essence"
			touch.append({
				"name": node.name,
				"width": c.size.x,
				"height": c.size.y,
				"role": role,
				"global_y": c.get_global_rect().position.y,
			})
		if node is Label or node is Button:
			var t := ""
			if node is Label:
				t = (node as Label).text
			elif node is Button:
				t = (node as Button).text
			if t != "":
				text_nodes.append({"visible": true, "text": t})
	for child in node.get_children():
		_audit_control(child, touch, text_nodes)


func _fail_smoke_picker() -> void:
	push_error("Magic picker not open")


func _is_essence_token(node: Node) -> bool:
	return node.get_script() != null and str(node.get_script().resource_path).ends_with("essence_token.gd")
