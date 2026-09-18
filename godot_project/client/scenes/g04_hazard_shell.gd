extends "res://client/scenes/g01_shell.gd"

## G04 FX-HAZARD playable shell — isolated save g04_hazard.

const HazardActor = preload("res://client/world/hazard_actor.gd")
const Feedback = preload("res://client/ui/catastrophe_feedback.gd")
const G04_HAZARD_SAVE := "g04_hazard"
const TILE := 64.0

var _feedback
var _feedback_label: Label
var _hex_layer: Node2D
var _hex_nodes: Dictionary = {}  # cube_id -> HazardActor
var _selected_cube: String = ""
var _duel_panel: PanelContainer
var _duel_label: Label
var _duel_id: String = ""
var _view_acc := 0.0
var _action_bar: HBoxContainer


func _ready() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-HAZARD")
	OS.set_environment("DMB_SEED", "408")
	OS.set_environment("DMB_SAVE_SLOT", G04_HAZARD_SAVE)
	super()
	_feedback = Feedback.new()
	_hex_layer = Node2D.new()
	_hex_layer.name = "HazardHexes"
	# Keep hazard layer above the area props.
	_hex_layer.z_index = 20
	_world_host.add_child(_hex_layer)
	_feedback_label = Label.new()
	_feedback_label.set_anchors_preset(PRESET_TOP_WIDE)
	_feedback_label.offset_left = 12
	_feedback_label.offset_top = 92
	_feedback_label.offset_right = -12
	_feedback_label.offset_bottom = 160
	_feedback_label.add_theme_font_size_override("font_size", 13)
	_feedback_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_feedback_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ui_root.add_child(_feedback_label)
	_build_hazard_actions()
	_build_duel_panel()
	_set_status("G04 FX-HAZARD — select manifestation, Treat starts playable duel")
	_prompt.text = "Select demon diamond, then Treat. Channel 3× to clear that cube only."


func _build_hazard_actions() -> void:
	_action_bar = HBoxContainer.new()
	_action_bar.set_anchors_preset(PRESET_BOTTOM_WIDE)
	_action_bar.offset_left = 8
	_action_bar.offset_right = -8
	_action_bar.offset_top = -150
	_action_bar.offset_bottom = -88
	_action_bar.add_theme_constant_override("separation", 8)
	_action_bar.alignment = BoxContainer.ALIGNMENT_CENTER
	_ui_root.add_child(_action_bar)
	var treat := Button.new()
	treat.text = "Treat (duel)"
	treat.custom_minimum_size = Vector2(120, 40)
	treat.pressed.connect(_start_selected_duel)
	_action_bar.add_child(treat)


func _build_duel_panel() -> void:
	_duel_panel = PanelContainer.new()
	_duel_panel.visible = false
	_duel_panel.set_anchors_preset(PRESET_CENTER)
	_duel_panel.offset_left = -140
	_duel_panel.offset_top = -90
	_duel_panel.offset_right = 140
	_duel_panel.offset_bottom = 90
	_ui_root.add_child(_duel_panel)
	var v := VBoxContainer.new()
	_duel_panel.add_child(v)
	_duel_label = Label.new()
	_duel_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_duel_label.text = "Hazard duel"
	v.add_child(_duel_label)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_child(row)
	var channel := Button.new()
	channel.text = "Channel"
	channel.custom_minimum_size = Vector2(90, 36)
	channel.pressed.connect(func(): _duel_action("channel"))
	row.add_child(channel)
	var falter := Button.new()
	falter.text = "Falter"
	falter.custom_minimum_size = Vector2(90, 36)
	falter.pressed.connect(func(): _duel_action("falter"))
	row.add_child(falter)


func _process(delta: float) -> void:
	super(delta)
	if _client == null:
		return
	_view_acc += delta
	if _view_acc >= 0.4:
		_view_acc = 0.0
		_client.enqueue_view(
			"player",
			["hazards", "fx_hazard", "player", "clock", "board", "leases"],
			{"replaceable": true, "coalesce_key": "view:g04_hazard"}
		)
		if _client.has_player_cache():
			_apply_hazard_view(_client.cached_player_view())


func _apply_hazard_view(view: Dictionary) -> void:
	_feedback.update_from_view(view)
	_feedback_label.text = _feedback.summary_text()
	var fx: Dictionary = view.get("fx_hazard", {})
	var cat: Dictionary = view.get("hazards", {}).get("catastrophe", {})
	var cubes: Dictionary = cat.get("cubes", {})
	var anchors: Dictionary = fx.get("hex_anchors", view.get("board", {}).get("hex_anchors", {}))
	var treated: Dictionary = {}
	var visit = view.get("player", {}).get("visit") or {}
	# Count active cubes per hex for labels.
	var counts: Dictionary = {}
	for cube_any in cubes.values():
		var c: Dictionary = cube_any
		if not bool(c.get("active", true)):
			continue
		var hid := str(c.get("hex_id", ""))
		counts[hid] = int(counts.get(hid, 0)) + 1

	var present: Dictionary = {}
	for cube_id in cubes.keys():
		var cube: Dictionary = cubes[cube_id]
		if not bool(cube.get("active", true)):
			continue
		present[cube_id] = true
		if not _hex_nodes.has(cube_id):
			var actor := Node2D.new()
			actor.set_script(HazardActor)
			_hex_layer.add_child(actor)
			actor.duel_requested.connect(_on_duel_requested)
			_hex_nodes[cube_id] = actor
			if _area != null:
				_area._npc_nodes[cube_id] = actor
		var node = _hex_nodes[cube_id]
		var hid := str(cube.get("hex_id", ""))
		var anchor: Dictionary = anchors.get(hid, {})
		var grid = anchor.get("grid", [3.0 + float(_hex_nodes.size()), 3.0])
		cube["treatment_eligible"] = true  # visit allowance checked on start
		cube["outbreak_warning"] = int(cat.get("era_outbreaks", 0)) >= int(fx.get("outbreak_warning_at", 7))
		cube["cube_count"] = int(counts.get(hid, 1))
		node.bind_cube(cube)
		node.position = node.grid_to_world(grid)
		node.set_selected(cube_id == _selected_cube)

	# Remove obsolete visuals after treatment.
	for cube_id in _hex_nodes.keys():
		if not present.has(cube_id):
			if _area != null:
				_area._npc_nodes.erase(cube_id)
			_hex_nodes[cube_id].queue_free()
			_hex_nodes.erase(cube_id)
			if _selected_cube == cube_id:
				_selected_cube = ""


func _input(event: InputEvent) -> void:
	if _duel_panel.visible:
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var hovered := get_viewport().gui_get_hovered_control()
		if hovered != null:
			return
		var gp: Vector2 = _hex_layer.get_global_mouse_position()
		var best := ""
		var best_d := 48.0
		for cid in _hex_nodes.keys():
			var d: float = _hex_nodes[cid].global_position.distance_to(gp)
			if d < best_d:
				best_d = d
				best = cid
		if best != "":
			_selected_cube = best
			for cid in _hex_nodes.keys():
				_hex_nodes[cid].set_selected(cid == best)
			_prompt.text = "Selected %s — press Treat to open duel" % best
			get_viewport().set_input_as_handled()


func _start_selected_duel() -> void:
	if _selected_cube == "":
		_prompt.text = "Select a hazard manifestation first"
		return
	_on_duel_requested(_selected_cube)


func _on_duel_requested(cube_id: String) -> void:
	var reply := _cmd("StartHazardDuel", {"cube_id": cube_id})
	if str(reply.get("status", "")) != "ACCEPTED":
		_prompt.text = "Treat rejected: %s" % reply.get("public_feedback", reply.get("code", "?"))
		return
	var duel: Dictionary = reply.get("payload", {}).get("duel", {})
	_duel_id = str(duel.get("id", ""))
	_duel_panel.visible = true
	_duel_label.text = "Duel vs %s on %s\nChannel 3 times to banish.\nWorld time frozen." % [
		cube_id, str(duel.get("hex_id", "?"))
	]
	if _area:
		_area.set_movement_enabled(false)
	_set_status("Hazard duel active — world paused")


func _duel_action(action: String) -> void:
	if _duel_id == "":
		return
	var reply := _cmd("HazardDuelAction", {"duel_id": _duel_id, "action": action})
	var payload: Dictionary = reply.get("payload", {})
	var status := str(payload.get("status", ""))
	if payload.has("progress") and status == "":
		_duel_label.text = "Channel %s / 3\nKeep focusing the manifestation." % payload.get("progress")
		return
	if status in ["success", "failed", "world_resolved", "idempotent"] or payload.has("removal") or payload.has("allowance_spent"):
		_finish_duel(payload)
		return
	if action == "falter":
		_finish_duel(payload)


func _finish_duel(payload: Dictionary) -> void:
	_duel_panel.visible = false
	_duel_id = ""
	if _area and not _paused and not _bridge_down:
		_area.set_movement_enabled(true)
	var status := str(payload.get("status", reply_status(payload)))
	if status == "success" or payload.get("allowance_spent") == true:
		_prompt.text = "Cube banished — hex updates; treatment recorded"
		_selected_cube = ""
	elif status == "failed":
		_prompt.text = "Duel failed — no treatment spent; try again if eligible"
	else:
		_prompt.text = "Duel ended: %s" % status
	_set_status("G04 FX-HAZARD — select manifestation, Treat starts playable duel")
	# Force refresh of manifestations / blockage.
	_view_acc = 1.0


func reply_status(payload: Dictionary) -> String:
	return str(payload.get("status", "?"))


func _on_save() -> void:
	var reply := _cmd("Save", {"slot": G04_HAZARD_SAVE})
	if str(reply.get("status", "")) == "ACCEPTED":
		_prompt.text = "Saved isolated slot %s" % G04_HAZARD_SAVE


func _on_load() -> void:
	var reply := _cmd("Load", {"slot": G04_HAZARD_SAVE})
	if str(reply.get("status", "")) == "ACCEPTED":
		_prompt.text = "Loaded %s — visit treatment ledger preserved" % G04_HAZARD_SAVE
		_duel_panel.visible = false
		_duel_id = ""
		for cid in _hex_nodes.keys():
			_hex_nodes[cid].queue_free()
		_hex_nodes.clear()
		_view_acc = 1.0
