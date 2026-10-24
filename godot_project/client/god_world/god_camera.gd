extends Node
class_name GodCamera

## The god's free camera and the gesture arbitration of docs/GOD_WORLD_PRD.md section 12.1. One finger (or the mouse) anywhere pans once it has
## moved past the drag threshold; a short press and release without a drag is a tap (`tapped`); two fingers pinch around their midpoint, which
## stays over the same world point, so moving both fingers pans as well. A gesture that became a drag or a pinch never taps on release, and the
## emulated mouse events that accompany touches (and vice versa) are ignored: only ScreenTouch / ScreenDrag drive the pointer logic. The wheel,
## +/- and a trackpad magnify gesture zoom too. The camera is clamped to the board with a margin; zoom runs from the whole-board fit to a close
## view. No avatar, no follow: the camera only moves when the god moves it (or `focus_on` is called at start).

signal tapped(screen_pos: Vector2)
signal moved()

const MAX_ZOOM := 1.3
const DEFAULT_ZOOM := 0.5
const DRAG_DP := 8.0
const PINCH_BLOCK_MS := 250
const TAP_MAX_MS := 600

var camera: Camera2D
var host: Node  # the world scene (for the viewport)
var bounds := Rect2()  # world-space board bounds (pixels)
var margin_px := 200.0
var zoom_level := DEFAULT_ZOOM
var min_zoom := 0.05

var _touches: Dictionary = {}  # index -> position (viewport coordinates)
var _press_pos := Vector2.ZERO
var _press_cam := Vector2.ZERO
var _press_ms := 0
var _dragging := false
var _pinching := false
var _pinch_seen := false
var _pinch_dist := 0.0
var _pinch_world := Vector2.ZERO  # the world point under the midpoint when the pinch began
var _pinch_zoom := 1.0
var _block_until := 0
var pans := 0  # test counters
var pinches := 0
var taps := 0


func setup(p_host: Node, p_camera: Camera2D) -> void:
	host = p_host
	camera = p_camera
	camera.anchor_mode = Camera2D.ANCHOR_MODE_DRAG_CENTER
	camera.position_smoothing_enabled = false
	set_zoom(DEFAULT_ZOOM)


func set_bounds(r: Rect2) -> void:
	bounds = r
	var vis := _vis()
	var fit := minf(vis.x / maxf(r.size.x + 2.0 * margin_px * 0.5, 1.0), vis.y / maxf(r.size.y + 2.0 * margin_px * 0.5, 1.0))
	min_zoom = clampf(fit * 0.98, 0.02, DEFAULT_ZOOM)
	clamp_position()


func _vis() -> Vector2:
	return host.get_viewport().get_visible_rect().size


func drag_threshold() -> float:
	# eight logical dp, in viewport units: dp -> window pixels by density, window pixels -> viewport units by the stretch scale
	var dpi := float(DisplayServer.screen_get_dpi())
	var density := maxf(1.0, dpi / 160.0)
	var win := Vector2(host.get_window().size)
	var vis := _vis()
	var scale := minf(win.x / vis.x, win.y / vis.y) if vis.x > 0.0 and vis.y > 0.0 else 1.0
	return maxf(6.0, DRAG_DP * density / maxf(scale, 0.01))


func screen_to_world(p: Vector2) -> Vector2:
	return host.get_viewport().get_canvas_transform().affine_inverse() * p


func world_to_screen(w: Vector2) -> Vector2:
	return host.get_viewport().get_canvas_transform() * w


func set_zoom(z: float, anchor_screen: Vector2 = Vector2(-1, -1)) -> void:
	z = clampf(z, min_zoom, MAX_ZOOM)
	if anchor_screen.x >= 0.0:
		var before := screen_to_world(anchor_screen)
		zoom_level = z
		camera.zoom = Vector2(z, z)
		# keep the anchored world point under the same screen point
		var centre := _vis() * 0.5
		camera.position = before - (anchor_screen - centre) / z
	else:
		zoom_level = z
		camera.zoom = Vector2(z, z)
	clamp_position()
	moved.emit()


func zoom_by(factor: float, anchor_screen: Vector2 = Vector2(-1, -1)) -> void:
	set_zoom(zoom_level * factor, anchor_screen)


func fit_board() -> void:
	set_zoom(min_zoom)
	camera.position = bounds.get_center()
	clamp_position()
	moved.emit()


func focus_on(world_pos: Vector2, z: float = DEFAULT_ZOOM) -> void:
	set_zoom(z)
	camera.position = world_pos
	clamp_position()
	moved.emit()


func clamp_position() -> void:
	if bounds.size == Vector2.ZERO:
		return
	var half := _vis() * 0.5 / maxf(zoom_level, 0.0001)
	var lo := bounds.position - Vector2(margin_px, margin_px) + half
	var hi := bounds.end + Vector2(margin_px, margin_px) - half
	var p := camera.position
	p.x = (lo.x + hi.x) * 0.5 if lo.x > hi.x else clampf(p.x, lo.x, hi.x)
	p.y = (lo.y + hi.y) * 0.5 if lo.y > hi.y else clampf(p.y, lo.y, hi.y)
	camera.position = p


## Returns true when the event was a world gesture (consumed).
func handle_event(event: InputEvent) -> bool:
	var now := Time.get_ticks_msec()
	if event is InputEventScreenTouch:
		if event.pressed:
			_touches[event.index] = event.position
			if _touches.size() == 1:
				_press_pos = event.position
				_press_cam = camera.position
				_press_ms = now
				_dragging = false
				_pinch_seen = false
			elif _touches.size() >= 2 and not _pinching:
				_begin_pinch()
		else:
			_touches.erase(event.index)
			if _pinching and _touches.size() < 2:
				_pinching = false
				_block_until = now + PINCH_BLOCK_MS
				if _touches.size() == 1:  # the remaining finger pans from where it is, never taps
					_press_pos = _touches.values()[0]
					_press_cam = camera.position
					_dragging = true
			elif _touches.is_empty():
				if not _dragging and not _pinch_seen and now - _press_ms <= TAP_MAX_MS and now >= _block_until:
					taps += 1
					tapped.emit(event.position)
				_dragging = false
		return true
	if event is InputEventScreenDrag:
		_touches[event.index] = event.position
		if _pinching and _touches.size() >= 2:
			_update_pinch()
			return true
		if _touches.size() == 1 and not _pinching:
			var moved_px: float = event.position.distance_to(_press_pos)
			if not _dragging and moved_px >= drag_threshold():
				_dragging = true
				pans += 1
			if _dragging:
				camera.position = _press_cam - (event.position - _press_pos) / maxf(zoom_level, 0.0001)
				clamp_position()
				moved.emit()
		return true
	if event is InputEventMagnifyGesture:
		pinches += 1
		zoom_by(event.factor, event.position)
		return true
	if event is InputEventPanGesture:
		camera.position += event.delta * 2.0 / maxf(zoom_level, 0.0001)
		clamp_position()
		moved.emit()
		return true
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			zoom_by(1.15, event.position)
			return true
		if event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			zoom_by(1.0 / 1.15, event.position)
			return true
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode in [KEY_PLUS, KEY_EQUAL, KEY_KP_ADD]:
			zoom_by(1.15)
			return true
		if event.keycode in [KEY_MINUS, KEY_KP_SUBTRACT]:
			zoom_by(1.0 / 1.15)
			return true
		if event.keycode == KEY_HOME:
			fit_board()
			return true
	return false


func _begin_pinch() -> void:
	_pinching = true
	_pinch_seen = true
	_dragging = false
	pinches += 1
	var pts: Array = _touches.values()
	var a: Vector2 = pts[0]
	var b: Vector2 = pts[1]
	_pinch_dist = maxf(a.distance_to(b), 1.0)
	_pinch_zoom = zoom_level
	_pinch_world = screen_to_world((a + b) * 0.5)


func _update_pinch() -> void:
	var pts: Array = _touches.values()
	var a: Vector2 = pts[0]
	var b: Vector2 = pts[1]
	var d := maxf(a.distance_to(b), 1.0)
	var mid := (a + b) * 0.5
	var z := clampf(_pinch_zoom * d / _pinch_dist, min_zoom, MAX_ZOOM)
	zoom_level = z
	camera.zoom = Vector2(z, z)
	var centre := _vis() * 0.5
	camera.position = _pinch_world - (mid - centre) / z  # the world point that was under the midpoint stays there (midpoint motion pans)
	clamp_position()
	moved.emit()


func gesture_state() -> Dictionary:
	return {"dragging": _dragging, "pinching": _pinching, "touches": _touches.size(), "zoom": zoom_level, "position": camera.position, "pans": pans, "pinches": pinches, "taps": taps}
