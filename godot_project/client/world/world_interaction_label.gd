extends Control
class_name WorldInteractionLabel

## One anchored semantic interaction surface.
## LABEL, OBSERVATION, SPEECH and RESPONSES are states of this control.
## It presents lines and choices. It does not decide quest consequences.
## Target visibility and presentation placement are separate: an off-screen
## entity hides its label. Clamping only repositions a label whose target is
## still on-screen.

const _Resolver = preload("res://sim/world/world_interaction_resolver.gd")
const _VT = preload("res://client/scripts/visual_theme.gd")

signal activated(knowledge_key: String)
signal interact_requested(knowledge_key: String)
signal response_chosen(knowledge_key: String, index: int)
signal conversation_dismissed(knowledge_key: String)
signal line_done
signal presentation_result(index: int)
signal presentation_entered(state: String)

const STATE_LABEL := "LABEL"
const STATE_OBSERVATION := "OBSERVATION"
const STATE_SPEECH := "SPEECH"
const STATE_RESPONSES := "RESPONSES"

const RESPONSE_WIDTH := 280.0
const RESPONSE_MIN_H := 56.0
const RESPONSE_GAP := 8.0
const VIEW_MARGIN := 8.0
const ANCHOR_HIT := 24.0

var _state := STATE_LABEL

var _semantic: Dictionary = {}
var _entity_id := ""
var _anchor: Node2D
var _adv: Node
var _camera: Camera2D
var _offset := Vector2.ZERO
var _button: Button
var _scroll: ScrollContainer
var _responses: VBoxContainer
var _response_buttons: Array = []
var _speech_lines: Array = []
var _speech_index := 0
var _pending_options: Array = []
var _selected_response := -1
var _awaiting_line := false
var _awaiting_choice := false
var _tracked_world := Vector2.ZERO
var _press_frame := -1
var _target_visible := true
var _suppressed := false
var _foreground := false
var _panel_size := Vector2.ZERO
var _responses_input_armed := true
var _awaiting_pointer_release := false
var _choice_locked := false
var _acknowledging := false
var _ack_generation := 0
var _committed_lines: Array = []
var _committed_options: Array = []
var _choice_trace: Array = []
var _touch_down: Dictionary = {}
var _gesture_down := false
var _fade: Tween
var _knowledge_provider: Callable
var _bridge_view: Dictionary = {}


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	z_as_relative = false
	_button = Button.new()
	_button.focus_mode = Control.FOCUS_NONE
	_button.mouse_filter = Control.MOUSE_FILTER_STOP
	_button.custom_minimum_size = Vector2(280, 72)
	_button.size = Vector2(280, 72)
	_button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_button.clip_text = true
	_VT.style_secondary_button(_button)
	_button.gui_input.connect(_on_button_gui)
	add_child(_button)
	_scroll = ScrollContainer.new()
	_scroll.name = "Responses"
	_scroll.visible = false
	_scroll.mouse_filter = Control.MOUSE_FILTER_STOP
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.clip_contents = true
	add_child(_scroll)
	_responses = VBoxContainer.new()
	_responses.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_responses.add_theme_constant_override("separation", int(RESPONSE_GAP))
	_scroll.add_child(_responses)


func bind(adv: Node, semantic: Dictionary, entity_id: String, anchor: Node2D, camera: Camera2D, offset: Vector2) -> void:
	_adv = adv
	_semantic = semantic.duplicate(true)
	_entity_id = entity_id
	_anchor = anchor
	_camera = camera
	_offset = offset
	if adv != null:
		_connect_adventure()
	refresh()
	_follow()


## Bind without Adventure. The knowledge level comes from `knowledge_provider`
## (called with the knowledge key) or from the filtered bridge view set later.
func bind_bridge(
	semantic: Dictionary,
	entity_id: String,
	anchor: Node2D,
	camera: Camera2D,
	offset: Vector2,
	knowledge_provider: Callable = Callable()
) -> void:
	_knowledge_provider = knowledge_provider
	bind(null, semantic, entity_id, anchor, camera, offset)


## Filtered bridge observation payload: {known, name, label, …}.
func set_bridge_view(view: Dictionary) -> void:
	_bridge_view = view.duplicate(true)
	refresh()


func bridge_view() -> Dictionary:
	return _bridge_view.duplicate(true)


func update_semantic(semantic: Dictionary) -> void:
	_semantic = semantic.duplicate(true)
	refresh()


func rebind_anchor(anchor: Node2D, camera: Camera2D = null) -> void:
	_anchor = anchor
	if camera != null:
		_camera = camera
	_follow()


func knowledge_key() -> String:
	return str(_semantic.get("knowledge_key", ""))


func entity_id() -> String:
	return _entity_id


func display_text() -> String:
	return _button.text if _button != null else ""


func interaction_state() -> String:
	return _state


func is_talking() -> bool:
	return _state == STATE_SPEECH or _state == STATE_RESPONSES


func is_expanded() -> bool:
	return _state != STATE_LABEL


func focus_rank() -> int:
	match _state:
		STATE_RESPONSES:
			return 30
		STATE_SPEECH:
			return 20
		STATE_OBSERVATION:
			return 10
		_:
			return 0


func is_foreground() -> bool:
	return _foreground


func set_foreground(on: bool) -> void:
	_foreground = on
	z_index = focus_rank() if on else 0


## Hide a passive label while another interaction owns RESPONSES.
## Does not change this entity's conversation or quest state.
func set_passive_suppressed(on: bool) -> void:
	if _suppressed == on:
		_apply_shown()
		return
	_suppressed = on
	_apply_shown()


func target_on_screen() -> bool:
	return _intersects_center(_displayed_center())


func _intersects_center(center: Vector2) -> bool:
	if not is_instance_valid(_anchor) or _camera == null or not is_instance_valid(_camera):
		return false
	var world_rect := _anchor_world_rect()
	var origin := _world_to_screen_from(world_rect.position, center)
	var extent := _world_to_screen_from(world_rect.end, center)
	var rect := Rect2(origin, extent - origin).abs()
	if rect.size.x <= 0.5 or rect.size.y <= 0.5:
		return true
	return get_viewport().get_visible_rect().intersects(rect)


func _displayed_center() -> Vector2:
	if _camera == null or not is_instance_valid(_camera):
		return Vector2.ZERO
	return _camera.get_screen_center_position()


func _settled_center() -> Vector2:
	if _camera == null or not is_instance_valid(_camera):
		return Vector2.ZERO
	if not _camera.position_smoothing_enabled:
		return _camera.get_screen_center_position()
	var view := get_viewport().get_visible_rect().size
	var zoom := _camera.zoom
	if zoom.x == 0.0 or zoom.y == 0.0:
		zoom = Vector2.ONE
	var half := view / zoom * 0.5
	var center := _camera.global_position + _camera.offset
	var left := float(_camera.limit_left)
	var right := float(_camera.limit_right)
	var top := float(_camera.limit_top)
	var bottom := float(_camera.limit_bottom)
	if right > left + view.x / zoom.x:
		center.x = clampf(center.x, left + half.x, right - half.x)
	if bottom > top + view.y / zoom.y:
		center.y = clampf(center.y, top + half.y, bottom - half.y)
	return center


func target_screen_rect() -> Rect2:
	if not is_instance_valid(_anchor) or _camera == null or not is_instance_valid(_camera):
		return Rect2()
	var world_rect := _anchor_world_rect()
	var origin := _world_to_screen(world_rect.position)
	var extent := _world_to_screen(world_rect.end)
	return Rect2(origin, extent - origin).abs()


func selected_response() -> int:
	return _selected_response


func response_labels() -> Array:
	var out: Array = []
	for raw in _response_buttons:
		if is_instance_valid(raw):
			out.append(str(raw.text))
	return out


func response_button(index: int) -> Button:
	for raw in _response_buttons:
		if is_instance_valid(raw) and int(raw.get_meta("index")) == index:
			return raw
	return null


func response_rect(index: int) -> Rect2:
	var button := response_button(index)
	if button == null:
		return Rect2()
	return button.get_global_rect()


func tracked_world_position() -> Vector2:
	return _tracked_world


func screen_anchor() -> Vector2:
	if _camera == null or not is_instance_valid(_camera):
		return _tracked_world
	return _world_to_screen(_tracked_world)


func screen_rect() -> Rect2:
	return presentation_rect()


func presentation_rect() -> Rect2:
	if _state == STATE_RESPONSES and _panel_size.y > 1.0:
		return Rect2(global_position, _panel_size)
	if _button != null and _button.visible and _button.size.x > 1.0:
		return _button.get_global_rect()
	return Rect2(global_position, size)


## Where the passive LABEL would sit, even while this label is hidden.
func passive_placement_rect() -> Rect2:
	var label_size := _label_size_for(display_text() if _state == STATE_LABEL else _resolved_label())
	var view := get_viewport().get_visible_rect() if is_inside_tree() else Rect2(0, 0, 720, 1280)
	return Rect2(placed_origin(screen_anchor(), label_size, view), label_size)


func set_dismiss_on_move(on: bool) -> void:
	_semantic["dismiss_on_move"] = on


func responses_input_armed() -> bool:
	return _responses_input_armed


func choice_locked() -> bool:
	return _choice_locked


## True only during the brief selected-choice hold. Movement dismissal is blocked
## for that hold. The captured reply is not waiting on Overworld.
func is_acknowledging() -> bool:
	return _acknowledging


## RESPONSES → CHOICE_ACCEPTED → SPEECH, or LABEL if an explicit dismiss won.
func choice_trace() -> Array:
	return _choice_trace.duplicate()


func refresh_presentation() -> void:
	_follow()


## Production tap. The button uses this path for both mouse and emulated touch,
## matching TouchPad. Tests may call it directly. A speech tap advances one
## beat. A response is chosen only by press_response().
func press() -> void:
	if _press_frame == Engine.get_process_frames():
		return
	_press_frame = Engine.get_process_frames()
	if _state == STATE_SPEECH:
		_advance_speech()
		activated.emit(knowledge_key())
		return
	if _state == STATE_RESPONSES:
		activated.emit(knowledge_key())
		return
	if _state == STATE_OBSERVATION:
		collapse()
		activated.emit(knowledge_key())
		return
	interact_requested.emit(knowledge_key())
	activated.emit(knowledge_key())


func open_observation() -> void:
	_clear_responses()
	_show_observation()


func begin_speech(lines: Array, options_after: Array = []) -> void:
	_awaiting_line = false
	_clear_responses()
	_speech_lines = []
	for raw in lines:
		var text := str(raw).strip_edges()
		if text != "":
			_speech_lines.append(text)
	_speech_index = 0
	_pending_options = options_after.duplicate(true)
	if _speech_lines.is_empty():
		if _pending_options.is_empty():
			collapse()
		else:
			_show_responses(_pending_options)
			_pending_options = []
		return
	_button.text = str(_speech_lines[0])
	_enter_state(STATE_SPEECH)
	_fit_speech()
	_show_speech_button(true)


## One line from an existing handler. The next speech tap finishes the await.
func present_line(text: String) -> void:
	_clear_responses()
	_pending_options = []
	_speech_lines = [text]
	_speech_index = 0
	_awaiting_line = true
	_button.text = text
	_enter_state(STATE_SPEECH)
	_fit_speech()
	_show_speech_button(true)


## Choices from an existing handler. Displaying them selects nothing.
func present_choices(options: Array) -> void:
	_awaiting_line = false
	_awaiting_choice = true
	_show_responses(options)


func press_response(index: int) -> void:
	if _state != STATE_RESPONSES or _choice_locked or not _responses_input_armed:
		return
	if _press_frame == Engine.get_process_frames():
		return
	var found := false
	for raw in _response_buttons:
		if is_instance_valid(raw) and int(raw.get_meta("index")) == index:
			found = true
			break
	if not found:
		return
	_press_frame = Engine.get_process_frames()
	_choice_locked = true
	_selected_response = index
	_record_trace("CHOICE_ACCEPTED")
	_acknowledge_choice(index)
	if _awaiting_choice:
		_awaiting_choice = false
		presentation_result.emit(index)
	response_chosen.emit(knowledge_key(), index)
	activated.emit(knowledge_key())


## Captured reply for a choice already accepted. The hold is presentation only.
## Collapse is the only way the stored lines are not shown.
func present_committed_reply(lines: Array, options_after: Array = []) -> void:
	_committed_lines = []
	for raw in lines:
		var text := str(raw).strip_edges()
		if text != "":
			_committed_lines.append(text)
	_committed_options = options_after.duplicate(true)
	_choice_locked = true
	_acknowledging = true
	_ack_generation += 1
	var generation := _ack_generation
	if not is_inside_tree():
		_reveal_committed_reply(generation)
		return
	var timer := get_tree().create_timer(0.16)
	timer.timeout.connect(_reveal_committed_reply.bind(generation), CONNECT_ONE_SHOT)


func _reveal_committed_reply(generation: int) -> void:
	if generation != _ack_generation or not _acknowledging:
		return
	_acknowledging = false
	begin_speech(_committed_lines, _committed_options)


func notify_player_moved() -> void:
	# The selected-choice hold must finish into the captured reply. A direction
	# already held, or the click that selected the choice, must not cancel it.
	if _acknowledging:
		return
	if _dismisses_on_move():
		collapse()


func collapse() -> void:
	var was_talking := _state == STATE_SPEECH or _state == STATE_RESPONSES
	_acknowledging = false
	_ack_generation += 1
	_committed_lines = []
	_committed_options = []
	_clear_conversation()
	_selected_response = -1
	_choice_locked = false
	_responses_input_armed = true
	_awaiting_pointer_release = false
	_enter_state(STATE_LABEL)
	_show_speech_button(true)
	modulate.a = 1.0
	_fit_label()
	refresh()
	_apply_shown()
	if was_talking:
		conversation_dismissed.emit(knowledge_key())
	if _awaiting_line:
		_awaiting_line = false
		line_done.emit()
	if _awaiting_choice:
		_awaiting_choice = false
		presentation_result.emit(-1)


func _show_observation() -> void:
	var resolved: Dictionary = _resolve()
	_button.text = str(resolved.get("observe_far", ""))
	_enter_state(STATE_OBSERVATION)
	_fit_speech()
	_show_speech_button(true)


func _advance_speech() -> void:
	if _awaiting_line:
		_awaiting_line = false
		line_done.emit()
		return
	if _speech_index + 1 < _speech_lines.size():
		_speech_index += 1
		_button.text = str(_speech_lines[_speech_index])
		return
	if not _pending_options.is_empty():
		var options := _pending_options
		_pending_options = []
		_show_responses(options)
		return
	collapse()


func _show_responses(options: Array) -> void:
	var keep_line := _state == STATE_SPEECH and _button != null and _button.text.strip_edges() != ""
	_clear_responses()
	_selected_response = -1
	_choice_locked = false
	_enter_state(STATE_RESPONSES)
	_show_speech_button(keep_line)
	if _button != null:
		_button.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if _scroll != null:
		_scroll.visible = true
	for raw in options:
		if not (raw is Dictionary):
			continue
		var option: Dictionary = raw
		var button := Button.new()
		button.focus_mode = Control.FOCUS_NONE
		button.mouse_filter = Control.MOUSE_FILTER_STOP
		button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		button.clip_text = true
		button.text = str(option.get("label", ""))
		button.set_meta("index", int(option.get("index", _response_buttons.size())))
		_VT.style_secondary_button(button)
		button.pressed.connect(_on_response_pressed.bind(button))
		button.gui_input.connect(_on_response_gui.bind(button))
		_responses.add_child(button)
		_response_buttons.append(button)
		_size_response_button(button)
	if _response_buttons.is_empty():
		collapse()
		return
	_layout_responses()
	_guard_response_input()


func _on_response_pressed(button: Button) -> void:
	press_response(int(button.get_meta("index")))


func _on_response_gui(event: InputEvent, button: Button) -> void:
	# The gesture that opened these choices must finish before they accept input.
	if not _responses_input_armed or _choice_locked:
		if event is InputEventMouseButton or event is InputEventScreenTouch:
			button.accept_event()
		return
	if event is InputEventScreenTouch and event.pressed:
		press_response(int(button.get_meta("index")))
		button.accept_event()
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		press_response(int(button.get_meta("index")))
		button.accept_event()


func _clear_conversation() -> void:
	_speech_lines = []
	_speech_index = 0
	_pending_options = []
	_clear_responses()


func _clear_responses() -> void:
	for raw in _response_buttons:
		if is_instance_valid(raw):
			raw.queue_free()
	_response_buttons.clear()
	if _responses != null:
		_responses.visible = false
	if _scroll != null:
		_scroll.visible = false


func _on_button_gui(event: InputEvent) -> void:
	# Advance on pointer-down so the same press cannot also land on a choice
	# that this tap is about to create. Release does not advance again.
	var down := false
	if event is InputEventScreenTouch and event.pressed:
		down = true
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		down = true
	if not down:
		return
	_gesture_down = true
	press()
	_button.accept_event()


func refresh() -> void:
	if _button == null:
		return
	if _adv == null and not _has_bridge_source():
		return
	if _state != STATE_LABEL:
		return
	var resolved: Dictionary = _resolve()
	_button.text = str(resolved.get("label", ""))
	_fit_label()


func _resolve(in_range: bool = false) -> Dictionary:
	return _Resolver.resolve(_semantic, _adv, in_range, _knowledge_level())


## -1 keeps the Adventure lookup. Bridge-bound labels supply their own level.
func _knowledge_level() -> int:
	if _knowledge_provider.is_valid():
		return maxi(0, int(_knowledge_provider.call(knowledge_key())))
	if not _bridge_view.is_empty():
		var name := str(_bridge_view.get("name", ""))
		return 1 if name != "" and name != "<null>" else 0
	return -1


func _has_bridge_source() -> bool:
	return _knowledge_provider.is_valid() or not _bridge_view.is_empty()


func _on_state_changed() -> void:
	refresh()


func _process(_delta: float) -> void:
	if _awaiting_pointer_release and not _pointer_held():
		_arm_responses()
	_follow()


func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		if event.pressed:
			_touch_down[event.index] = true
		else:
			_touch_down.erase(event.index)
			_gesture_down = false
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed:
		_gesture_down = false


func _follow() -> void:
	if not is_instance_valid(_anchor):
		return
	_tracked_world = _anchor.global_position + _offset
	# Displayed viewport hides labels. Settled camera view decides collapse, so
	# camera smoothing cannot dismiss a conversation the player is walking toward.
	var displayed := _intersects_center(_displayed_center())
	var settled := _intersects_center(_settled_center())
	_target_visible = displayed
	if not settled:
		if is_expanded() and _dismisses_on_move() and not _acknowledging:
			collapse()
		_apply_shown()
		return
	_apply_shown()
	if not visible:
		return
	var content := _preferred_size()
	_panel_size = content
	var view := get_viewport().get_visible_rect()
	global_position = placed_origin(screen_anchor(), content, view)
	size = content
	custom_minimum_size = content
	if _state == STATE_RESPONSES and _scroll != null:
		_scroll.position = Vector2.ZERO
		_scroll.size = content
		_scroll.custom_minimum_size = content


## Presentation placement only. Do not use this to decide whether the target
## is visible. A label is clamped when its still-visible target would overflow.
static func placed_origin(screen: Vector2, size: Vector2, view: Rect2) -> Vector2:
	var above := screen - Vector2(size.x * 0.5, size.y + 8.0)
	var below := Vector2(screen.x - size.x * 0.5, screen.y + 12.0)
	var pos := above
	if above.y < view.position.y + VIEW_MARGIN:
		pos = below
	var right := view.position.x + view.size.x
	var bottom := view.position.y + view.size.y
	if pos.y + size.y > bottom - VIEW_MARGIN and above.y >= view.position.y + VIEW_MARGIN:
		pos = above
	pos.x = clampf(pos.x, view.position.x + VIEW_MARGIN, maxf(view.position.x + VIEW_MARGIN, right - size.x - VIEW_MARGIN))
	pos.y = clampf(pos.y, view.position.y + VIEW_MARGIN, maxf(view.position.y + VIEW_MARGIN, bottom - size.y - VIEW_MARGIN))
	return pos


func _fit_label() -> void:
	if _button == null:
		return
	var fitted := _label_size_for(_button.text)
	_button.custom_minimum_size = fitted
	_button.size = fitted
	if _state == STATE_LABEL:
		size = fitted
		custom_minimum_size = fitted


func _fit_speech() -> void:
	if _button == null:
		return
	var fitted := _speech_size_for(_button.text)
	_button.custom_minimum_size = fitted
	_button.size = fitted
	if _state != STATE_RESPONSES:
		size = fitted
		custom_minimum_size = fitted
		_panel_size = fitted


func _speech_size_for(text: String) -> Vector2:
	var width := clampf(120.0 + float(text.length()) * 6.5, 168.0, 260.0)
	var height := _text_block_height(text, width, 14.0)
	if text.length() < 42 and height <= 56.0:
		width = clampf(108.0 + float(text.length()) * 7.0, 140.0, 220.0)
		height = _text_block_height(text, width, 14.0)
	var max_h := 180.0
	if is_inside_tree():
		max_h = minf(220.0, get_viewport().get_visible_rect().size.y * 0.28)
	return Vector2(width, clampf(height, 48.0, max_h))


func _preferred_size() -> Vector2:
	if _state == STATE_RESPONSES and _panel_size.y > 1.0:
		return _panel_size
	if _state == STATE_LABEL:
		return _button.custom_minimum_size if _button != null else Vector2(96, 48)
	if _button != null and _button.custom_minimum_size.y > 1.0:
		return _button.custom_minimum_size
	return Vector2(200.0, 56.0)


func _layout_responses() -> void:
	var total := 0.0
	for raw in _response_buttons:
		if not is_instance_valid(raw):
			continue
		total += raw.custom_minimum_size.y
	if _response_buttons.size() > 1:
		total += RESPONSE_GAP * float(_response_buttons.size() - 1)
	var speech_h := 0.0
	if _button != null and _button.visible:
		_button.position = Vector2((RESPONSE_WIDTH - _button.size.x) * 0.5, 0)
		speech_h = _button.size.y + 10.0
	var view_h := 1280.0
	if is_inside_tree():
		view_h = get_viewport().get_visible_rect().size.y
	var max_block := maxf(RESPONSE_MIN_H, view_h - VIEW_MARGIN * 2.0)
	var max_scroll := maxf(RESPONSE_MIN_H, max_block - speech_h)
	var shown := minf(total, max_scroll)
	_responses.custom_minimum_size = Vector2(RESPONSE_WIDTH, total)
	_responses.size = Vector2(RESPONSE_WIDTH, total)
	_responses.visible = true
	_scroll.custom_minimum_size = Vector2(RESPONSE_WIDTH, shown)
	_scroll.size = Vector2(RESPONSE_WIDTH, shown)
	_scroll.position = Vector2(0, speech_h)
	_scroll.visible = true
	if total > max_scroll + 1.0:
		_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	else:
		_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.scroll_vertical = 0
	_panel_size = Vector2(RESPONSE_WIDTH, speech_h + shown)
	size = _panel_size
	custom_minimum_size = _panel_size


func _size_response_button(button: Button) -> void:
	var height := _wrapped_button_height(button)
	button.custom_minimum_size = Vector2(RESPONSE_WIDTH, height)
	button.size = Vector2(RESPONSE_WIDTH, height)
	button.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN


func _wrapped_button_height(button: Button) -> float:
	var font: Font = button.get_theme_font("font")
	if font == null:
		font = ThemeDB.fallback_font
	var font_size := button.get_theme_font_size("font_size")
	if font_size <= 0:
		font_size = _VT.FONT_SECONDARY
	var h_margin := 36.0
	var v_margin := 24.0
	var style: StyleBox = button.get_theme_stylebox("normal")
	if style != null:
		h_margin = style.get_content_margin(SIDE_LEFT) + style.get_content_margin(SIDE_RIGHT) + 4.0
		v_margin = style.get_content_margin(SIDE_TOP) + style.get_content_margin(SIDE_BOTTOM) + 4.0
	var inner := maxf(40.0, RESPONSE_WIDTH - h_margin)
	var text_size := font.get_multiline_string_size(button.text, HORIZONTAL_ALIGNMENT_LEFT, inner, font_size)
	return maxf(RESPONSE_MIN_H, text_size.y + v_margin)


func _label_size_for(text: String) -> Vector2:
	var n := text.length()
	return Vector2(clampf(72.0 + float(n) * 11.0, 96.0, 220.0), 48.0)


func _resolved_label() -> String:
	var resolved: Dictionary = _resolve()
	return str(resolved.get("label", ""))


func _show_speech_button(on: bool) -> void:
	if _button == null:
		return
	_button.visible = on
	_button.mouse_filter = Control.MOUSE_FILTER_STOP if on else Control.MOUSE_FILTER_IGNORE


func _apply_shown() -> void:
	var show := _target_visible and not _suppressed
	visible = show
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _dismisses_on_move() -> bool:
	var resolved: Dictionary = _resolve()
	return bool(resolved.get("dismiss_on_move", true))


func _anchor_world_rect() -> Rect2:
	if _anchor is Sprite2D:
		var sprite := _anchor as Sprite2D
		if sprite.texture != null:
			var local := sprite.get_rect()
			var xf := sprite.get_global_transform()
			var corners: Array[Vector2] = [
				xf * local.position,
				xf * Vector2(local.end.x, local.position.y),
				xf * Vector2(local.position.x, local.end.y),
				xf * local.end,
			]
			var lo := corners[0]
			var hi := corners[0]
			for point in corners:
				lo = lo.min(point)
				hi = hi.max(point)
			if hi.x > lo.x and hi.y > lo.y:
				return Rect2(lo, hi - lo)
	return Rect2(_anchor.global_position - Vector2(ANCHOR_HIT * 0.5, ANCHOR_HIT * 0.5), Vector2(ANCHOR_HIT, ANCHOR_HIT))


func _world_to_screen(world: Vector2) -> Vector2:
	return _world_to_screen_from(world, _displayed_center())


func _world_to_screen_from(world: Vector2, center: Vector2) -> Vector2:
	if _camera == null or not is_instance_valid(_camera):
		return world
	var view := get_viewport().get_visible_rect().size
	return (world - center) * _camera.zoom + view * 0.5


func _enter_state(next: String) -> void:
	var changed := _state != next
	_state = next
	if changed:
		_record_trace(next)
	if changed and next != STATE_LABEL:
		presentation_entered.emit(next)
		_fade_in()
	if _button != null and next == STATE_SPEECH:
		_button.add_theme_color_override("font_color", Color(1.0, 0.96, 0.86))
	elif _button != null and next == STATE_LABEL:
		_button.remove_theme_color_override("font_color")


func _fade_in() -> void:
	if not is_inside_tree():
		modulate.a = 1.0
		return
	if _fade != null and _fade.is_valid():
		_fade.kill()
	modulate.a = 0.28
	_fade = create_tween()
	_fade.tween_property(self, "modulate:a", 1.0, 0.15)


func _record_trace(step: String) -> void:
	if not _choice_trace.is_empty() and str(_choice_trace.back()) == step:
		return
	_choice_trace.append(step)


func _acknowledge_choice(index: int) -> void:
	for raw in _response_buttons:
		if not is_instance_valid(raw):
			continue
		raw.mouse_filter = Control.MOUSE_FILTER_IGNORE
		if int(raw.get_meta("index")) == index:
			raw.modulate = Color(1.0, 0.86, 0.45)
		else:
			raw.modulate = Color(0.62, 0.62, 0.68)


func _guard_response_input() -> void:
	_responses_input_armed = false
	_choice_locked = false
	_awaiting_pointer_release = _pointer_held()
	if _awaiting_pointer_release:
		for raw in _response_buttons:
			if is_instance_valid(raw):
				raw.mouse_filter = Control.MOUSE_FILTER_IGNORE
		return
	_arm_responses()


func _arm_responses() -> void:
	_awaiting_pointer_release = false
	_responses_input_armed = true
	if _choice_locked:
		return
	for raw in _response_buttons:
		if is_instance_valid(raw):
			raw.mouse_filter = Control.MOUSE_FILTER_STOP


func _pointer_held() -> bool:
	if _gesture_down:
		return true
	if Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		return true
	return not _touch_down.is_empty()


func _text_block_height(text: String, width: float, pad_y: float) -> float:
	var font: Font = ThemeDB.fallback_font
	var font_size := _VT.FONT_SECONDARY
	if _button != null:
		var themed: Font = _button.get_theme_font("font")
		if themed != null:
			font = themed
		var sized := _button.get_theme_font_size("font_size")
		if sized > 0:
			font_size = sized
	var inner := maxf(40.0, width - 40.0)
	var text_size := font.get_multiline_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, inner, font_size)
	return text_size.y + pad_y + 16.0


func _connect_adventure() -> void:
	if _adv != null and is_instance_valid(_adv) and not _adv.state_changed.is_connected(_on_state_changed):
		_adv.state_changed.connect(_on_state_changed)


func _disconnect_adventure() -> void:
	if _adv != null and is_instance_valid(_adv) and _adv.state_changed.is_connected(_on_state_changed):
		_adv.state_changed.disconnect(_on_state_changed)


func _notification(what: int) -> void:
	if what == NOTIFICATION_ENTER_TREE:
		_connect_adventure()
	elif what == NOTIFICATION_EXIT_TREE:
		_disconnect_adventure()
