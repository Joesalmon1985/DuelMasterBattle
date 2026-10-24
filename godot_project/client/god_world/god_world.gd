extends Node2D

## God World (docs/GOD_WORLD_PRD.md): the player is a god watching six autonomous factions on one continuous island. This scene starts the
## authoritative Python world on this device (profile `god_catan_v1`, through the same LanSession host route as Wizard World), connects, and then
## only views: free camera (god_camera.gd), the picture (god_view.gd), two-step labels (god_labels.gd), the HUD (god_hud.gd). No avatar, no
## joystick, no tutorial, no developer flag. Python owns every rule; this node owns polling, camera, selection and playback requests.

const GodCameraScript = preload("res://client/god_world/god_camera.gd")
const GodViewScript = preload("res://client/god_world/god_view.gd")
const GodLabelsScript = preload("res://client/god_world/god_labels.gd")
const GodHudScript = preload("res://client/god_world/god_hud.gd")
const _VT = preload("res://client/scripts/visual_theme.gd")
const SaveData = preload("res://client/scripts/save_data.gd")

const POLL_SECONDS := 0.2
const PROFILE := "god_catan_v1"

var camera: Camera2D
var camera_ctl: GodCameraScript
var view: GodViewScript
var labels: GodLabelsScript
var hud: GodHudScript
var snapshot: Dictionary = {}
var board: Dictionary = {}
var state := "boot"  # boot, hosting, connecting, playing, failed
var status_text := ""
var _seq := 0
var _poll_acc := 0.0
var _host_acc := 0.0
var _poll_pending := false
var _status_lbl: Label
var _status_layer: CanvasLayer
var _focused := false
var _tap_radius_px := 36.0
var polls := 0
var last_poll_ms := 0


func _ready() -> void:
	camera = Camera2D.new()
	camera.name = "GodCamera2D"
	add_child(camera)
	camera.make_current()
	view = GodViewScript.new()
	view.name = "GodView"
	add_child(view)
	camera_ctl = GodCameraScript.new()
	camera_ctl.name = "GodCameraCtl"
	add_child(camera_ctl)
	camera_ctl.setup(self, camera)
	camera_ctl.tapped.connect(_on_tap)
	camera_ctl.moved.connect(func(): view.zoom = camera_ctl.zoom_level; view.queue_redraw())
	hud = GodHudScript.new()
	add_child(hud)
	hud.setup(self)
	labels = GodLabelsScript.new()
	labels.name = "GodLabels"
	add_child(labels)
	labels.setup(self)
	_status_layer = CanvasLayer.new()
	_status_layer.layer = 20
	add_child(_status_layer)
	var bg := ColorRect.new()
	bg.name = "BootShade"
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = _VT.COLOR_BG_DEEP
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_status_layer.add_child(bg)
	_status_lbl = Label.new()
	_status_lbl.name = "BootStatus"
	_status_lbl.set_anchors_preset(Control.PRESET_FULL_RECT)
	_status_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_status_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_status_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_VT.apply_label_primary(_status_lbl)
	_status_layer.add_child(_status_lbl)
	var saved_zoom = SaveData.get_setting("god_zoom", GodCameraScript.DEFAULT_ZOOM)
	camera_ctl.set_zoom(clampf(float(saved_zoom), 0.35, 1.0))  # the world opens near a village at a readable scale, never at the whole-island fit
	get_viewport().size_changed.connect(func(): camera_ctl.clamp_position())
	_begin()


func _set_status(t: String) -> void:
	status_text = t
	_status_lbl.text = t


func _begin() -> void:
	if LanSession.sim != null and LanSession.sim.connected():
		state = "connecting"
		_after_hello()
		return
	state = "hosting"
	_set_status("Raising the island…\n\nThe world is built on this device.")
	LanSession.mode = "host"
	LanSession.private_session = true
	LanSession.profile = PROFILE
	LanSession.player_name = LanSession.default_player_name()
	var seed_ := int(SaveData.get_setting("god_seed", 507))
	if LanSession.new_world:
		seed_ = 1000 + (randi() % 9000)
		SaveData.set_setting("god_seed", seed_)
	var r: Dictionary = LanSession.start_local_host("God World", LanSession.random_code(), seed_, "catan_5_6", true)
	if str(r.get("state", "")) == "failed":
		state = "failed"
		_set_status("The world could not start:\n%s" % str(r.get("error", "")))


func _check_host() -> void:
	var st: Dictionary = LanSession.host_status()
	var s := str(st.get("state", ""))
	if s == "failed":
		state = "failed"
		_set_status("The world could not start:\n%s" % str(st.get("error", "")))
		return
	if s != "ready":
		_set_status("Raising the island… (%s)" % s)
		return
	state = "connecting"
	var reply: Dictionary = LanSession.connect_and_hello("127.0.0.1", LanSession.port, LanSession.join_code, LanSession.player_name, LanSession.host_secret)
	if str(reply.get("status", "")) != "ok":
		state = "failed"
		_set_status("The world started but refused this device: %s" % str(reply.get("reason", "")))
		return
	_after_hello()


func _after_hello() -> void:
	LanSession.sim.op({"op": "start"})
	var st: Dictionary = LanSession.sim.op({"op": "state", "full": true, "seq": 0}, 8000)
	if str(st.get("status", "")) != "ok":
		state = "failed"
		_set_status("No world answered: %s" % str(st.get("reason", "")))
		return
	_apply_state(st)
	state = "playing"
	_status_layer.visible = false


func _process(delta: float) -> void:
	if state == "hosting":
		_host_acc += delta
		if _host_acc >= 0.25:
			_host_acc = 0.0
			_check_host()
		return
	if state != "playing":
		return
	LanSession.sim.poll()
	_poll_acc += delta
	if _poll_acc >= POLL_SECONDS and not _poll_pending:
		_poll_acc = 0.0
		_seq += 1
		_poll_pending = true
		LanSession.sim.request({"op": "state", "seq": _seq, "view": _view_window()}, _on_state_reply)
	if not LanSession.sim.connected():
		state = "failed"
		_status_layer.visible = true
		_set_status("The connection to the world was lost.")


## The camera's world window in tiles: the host sends the living picture (people, workshops, trees) only for villages inside it.
func _view_window() -> Array:
	var xf := get_viewport().get_canvas_transform().affine_inverse()
	var vis := get_viewport().get_visible_rect().size
	var a := xf * Vector2.ZERO
	var b := xf * vis
	var tp: float = GodViewScript.TILE_PX
	return [minf(a.x, b.x) / tp, minf(a.y, b.y) / tp, maxf(a.x, b.x) / tp, maxf(a.y, b.y) / tp]


func _on_state_reply(reply: Dictionary) -> void:
	_poll_pending = false
	if str(reply.get("status", "")) != "ok":
		return
	_apply_state(reply)


func _apply_state(reply: Dictionary) -> void:
	polls += 1
	if reply.has("board"):
		board = reply["board"]
		view.set_board(board)
		camera_ctl.set_bounds(view.board_bounds())
		camera_ctl.margin_px = 200.0
	snapshot = reply.get("snapshot", {})
	last_poll_ms = int(snapshot.get("game_ms", 0))
	view.zoom = camera_ctl.zoom_level
	view.set_snapshot(snapshot)
	hud.apply_snapshot(snapshot)
	labels.refresh_details()
	if not _focused and not snapshot.get("villages", []).is_empty():
		# start near a working village at a readable scale, not at a tiny overview (12.1)
		_focused = true
		var v: Dictionary = snapshot["villages"][0]
		camera_ctl.focus_on(GodViewScript.bu(float(v["x"]), float(v["y"])), camera_ctl.zoom_level)
	elif not _focused and not board.is_empty():
		camera_ctl.focus_on(view.board_bounds().get_center(), camera_ctl.zoom_level)


# ------------------------------------------------------------------ input

func _unhandled_input(event: InputEvent) -> void:
	if state != "playing":
		return
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ESCAPE:
		if not labels.back():
			hud._on_menu()
		get_viewport().set_input_as_handled()
		return
	if hud.covering():
		return
	if camera_ctl.handle_event(event):
		get_viewport().set_input_as_handled()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_GO_BACK_REQUEST:  # Android Back: details -> label -> hidden -> menu
		if labels.back():
			return
		if hud.covering():
			hud.notice.hide_card()
			return
		hud._on_menu()
	elif what == NOTIFICATION_APPLICATION_PAUSED or what == NOTIFICATION_WM_CLOSE_REQUEST:
		if state == "playing" and LanSession.sim != null and LanSession.sim.connected():
			LanSession.sim.op({"op": "pause", "on": true}, 1500)
			LanSession.sim.op({"op": "save", "slot": "quit"}, 3000)
			SaveData.set_setting("god_zoom", camera_ctl.zoom_level)
	elif what == NOTIFICATION_APPLICATION_RESUMED:
		if state == "playing" and LanSession.sim != null and LanSession.sim.connected():
			LanSession.sim.op({"op": "pause", "on": false}, 1500)


func _on_tap(screen_pos: Vector2) -> void:
	var wp: Vector2 = camera_ctl.screen_to_world(screen_pos)
	var radius := _tap_radius_px / maxf(camera_ctl.zoom_level, 0.02)
	var id: String = view.pick(wp, radius)
	if id == "":
		labels.clear()
		return
	if labels.state == GodLabelsScript.State.LABEL and id == labels.selected_id:
		return  # the second gesture goes to the label itself, not to the object again
	labels.select(id)


# ------------------------------------------------------------------ playback and lifecycle (host ops)

func sim_op(message: Dictionary) -> Dictionary:
	if LanSession.sim == null or not LanSession.sim.connected():
		return {"status": "rejected", "reason": "not_connected"}
	return LanSession.sim.op(message, 4000)


func toggle_pause() -> void:
	var on := not bool(snapshot.get("paused", false))
	sim_op({"op": "pause", "on": on})


func set_speed(scale: int) -> void:
	sim_op({"op": "speed", "scale": scale})


func new_world() -> void:
	var r: Dictionary = sim_op({"op": "new_world", "seed": 1000 + (randi() % 9000)})
	if str(r.get("status", "")) == "ok":
		SaveData.set_setting("god_seed", int(r.get("seed", 507)))
		labels.clear()
		_focused = false
		hud._age_shown = 0
		hud._final_shown = false
		var st: Dictionary = LanSession.sim.op({"op": "state", "full": true, "seq": 0}, 8000)
		if str(st.get("status", "")) == "ok":
			_apply_state(st)


func retry_campaign() -> Dictionary:
	var r: Dictionary = sim_op({"op": "retry"})
	if str(r.get("status", "")) == "ok":
		var st: Dictionary = LanSession.sim.op({"op": "state", "full": true, "seq": 0}, 8000)
		if str(st.get("status", "")) == "ok":
			_apply_state(st)
	return r


func leave_to_menu() -> void:
	if LanSession.sim != null and LanSession.sim.connected():
		LanSession.sim.op({"op": "save", "slot": "quit"}, 3000)
	SaveData.set_setting("god_zoom", camera_ctl.zoom_level)
	LanSession.stop_local_host()
	LanSession.reset()
	get_tree().change_scene_to_file("res://client/scenes/main_menu.tscn")


# ------------------------------------------------------------------ test API (headed evidence, client/tests/run_god_world.gd)

func ui_state() -> Dictionary:
	return {"state": state, "status": status_text, "polls": polls, "game_ms": last_poll_ms, "age": int(snapshot.get("age", 0)), "phase": str(snapshot.get("phase", "")),
			"villages": snapshot.get("villages", []).size(), "journeys": snapshot.get("journeys", []).size(), "camera": camera_ctl.gesture_state(), "labels": labels.ui_state(),
			"missing_art": view.missing.duplicate(), "paused": bool(snapshot.get("paused", false)), "speed": int(snapshot.get("speed", 1)),
			"campaign": _campaign_state()}


func _campaign_state() -> Dictionary:
	var camp: Variant = snapshot.get("pandemic")
	if camp == null or typeof(camp) != TYPE_DICTIONARY:
		return {"active": false, "formations": 0, "responders": 0, "posts": 0, "result": "", "gate": snapshot.get("gate", {})}
	var p: Dictionary = camp.get("panel", {})
	return {"active": true, "formations": camp.get("formations", []).size(), "responders": camp.get("responders", []).size(), "posts": camp.get("posts", []).size(),
			"result": str(p.get("result", "")) if p.get("result") != null else "", "turn": int(p.get("turn_count", 0)), "gate": snapshot.get("gate", {}), "panel_visible": hud.campaign.visible}


## The heaviest formation (the one a tester looks at): its world position, or Vector2.INF when none.
func _heaviest_formation() -> Vector2:
	var camp: Variant = snapshot.get("pandemic")
	if camp == null or typeof(camp) != TYPE_DICTIONARY:
		return Vector2.INF
	var best: Dictionary = {}
	for fm in camp.get("formations", []):
		if best.is_empty() or int(fm.get("n", 0)) > int(best.get("n", 0)):
			best = fm
	if best.is_empty():
		return Vector2.INF
	return GodViewScript.bu(float(best["x"]), float(best["y"]))


## Centre the camera on the heaviest formation at village zoom; the camera's transform settles on the next frame, so a position is asked after.
func ui_focus_formation() -> bool:
	var wp := _heaviest_formation()
	if wp == Vector2.INF:
		return false
	camera_ctl.focus_on(wp, 0.5)
	return true


func ui_formation_screen_pos() -> Vector2:
	var wp := _heaviest_formation()
	if wp == Vector2.INF:
		return Vector2(-1, -1)
	return camera_ctl.world_to_screen(wp)


## The operational village nearest the camera's centre, in viewport units (the one a tester taps).
func ui_village_screen_pos() -> Vector2:
	var best := Vector2(-1, -1)
	var best_d := INF
	for v in snapshot.get("villages", []):
		if str(v["status"]) != "operational":
			continue
		var wp: Vector2 = GodViewScript.bu(float(v["x"]), float(v["y"]))
		var d := wp.distance_to(camera.position)
		if d < best_d:
			best_d = d
			best = camera_ctl.world_to_screen(wp)
	return best
