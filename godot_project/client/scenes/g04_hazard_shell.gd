extends "res://client/scenes/g01_shell.gd"

## G04 FX-HAZARD playable shell — isolated save g04_hazard.

const HazardActor = preload("res://client/world/hazard_actor.gd")
const Feedback = preload("res://client/ui/catastrophe_feedback.gd")
const ChoiceCard = preload("res://client/ui/attached_choice_card.gd")
const SemanticLabels = preload("res://client/ui/semantic_labels.gd")
const G04_HAZARD_SAVE := "g04_hazard"
const TILE := 64.0
const INTERACTION_RANGE_TILES := 2.0
const COLOUR_NAMES := ["Red", "Blue", "Green", "Yellow", "Purple", "Orange"]

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
var _pending_hazard_view_id := ""
var _choice_card
var _guess_slots: Array = [0, 0, 0, 0]
var _slot_buttons: Array = []
var _hex_labels: Dictionary = {}


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
	_choice_card = ChoiceCard.new()
	_ui_root.add_child(_choice_card)
	_choice_card.action_chosen.connect(_on_hazard_choice)
	_choice_card.closed.connect(func(): pass)
	if _client != null and not _client.request_finished.is_connected(_on_hazard_request_finished):
		_client.request_finished.connect(_on_hazard_request_finished)
	_set_status("G04 FX-HAZARD — observe / Challenge Mastermind duel")
	_prompt.text = "Click a manifestation: far = Observe, near = Challenge. No Channel shortcut."
	_apply_mode_chrome_visibility()


func _configure_spellbook() -> void:
	super._configure_spellbook()
	_spell_binder.setup(_spell_model, "g04_hazard", "G04 Hazard Spellbook")
	_spell_binder.build_g04_hazard_pages()
	_spell_binder.register("wait", func(_p): return _spell_wait())
	_spell_binder.register("invalid_exit", func(_p): return _spell_invalid())
	_spell_binder.register("pause", func(_p): return _spell_pause())
	_spell_binder.register("resume", func(_p): return _spell_resume())
	_spell_binder.register("save", func(_p): _on_save(); return {"status": "OK", "message": _prompt.text})
	_spell_binder.register("load", func(_p): _on_load(); return {"status": "OK", "message": _prompt.text})
	_spell_binder.register("bridge_fail", func(_p): return _spell_bridge_fail())
	_spell_binder.register("toggle_diag", func(_p): _toggle_diag(); return {"status": "OK", "message": "Dev panel %s" % ("open" if _diag_open else "closed")})
	_spell_binder.register("hazard_treat", func(p): return _spell_treat(p))
	_spell_binder.register("hazard_channel", func(_p): return {"status": "REJECTED", "message": "Channel shortcut removed"})
	_spell_binder.register("hazard_falter", func(_p): return _spell_duel("resign"))
	_spell_binder.register("hazard_guess", func(p): return _spell_guess(p))


func _apply_mode_chrome_visibility() -> void:
	# Permanent Treat toolbar removed — contextual Challenge only.
	if _action_bar:
		_action_bar.visible = false


func _spell_treat(payload: Dictionary) -> Dictionary:
	_selected_cube = str(payload.get("target_id", _selected_cube))
	if _selected_cube == "":
		return {"status": "REJECTED", "message": "Select a hazard first"}
	_on_duel_requested(_selected_cube)
	var ok := _duel_id != ""
	return {"status": "ACCEPTED" if ok else "REJECTED", "message": _prompt.text}


func _spell_duel(action: String) -> Dictionary:
	if _duel_id == "":
		return {"status": "REJECTED", "message": "No active duel"}
	_duel_action(action)
	return {"status": "OK", "message": _duel_label.text if _duel_label else _prompt.text}


func _spell_guess(payload: Dictionary) -> Dictionary:
	if _duel_id == "":
		return {"status": "REJECTED", "message": "No active duel"}
	var guess: Array = payload.get("guess", _guess_slots)
	_submit_guess(guess)
	return {"status": "OK", "message": _duel_label.text if _duel_label else _prompt.text}


func _on_hazard_request_finished(request_id: String, reply: Dictionary) -> void:
	if request_id != _pending_hazard_view_id:
		return
	_pending_hazard_view_id = ""
	if str(reply.get("status", "")) != "ACCEPTED":
		return
	# Apply only when this reply carried hazards (explicit empty = remove; omit handled by merge).
	var view: Dictionary = reply.get("view", {})
	if not view.has("hazards") and _client != null and _client.player_cache_has_field("hazards"):
		view = _client.cached_player_view()
	if view.has("hazards"):
		_apply_hazard_view(view)

func _build_hazard_actions() -> void:
	# Retained empty bar for layout compatibility; hidden permanently.
	_action_bar = HBoxContainer.new()
	_action_bar.visible = false
	_ui_root.add_child(_action_bar)


func _build_duel_panel() -> void:
	_duel_panel = PanelContainer.new()
	_duel_panel.visible = false
	_duel_panel.set_anchors_preset(PRESET_CENTER)
	_duel_panel.offset_left = -200
	_duel_panel.offset_top = -160
	_duel_panel.offset_right = 200
	_duel_panel.offset_bottom = 160
	_ui_root.add_child(_duel_panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	_duel_panel.add_child(v)
	_duel_label = Label.new()
	_duel_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_duel_label.text = "Mastermind duel"
	v.add_child(_duel_label)
	var slots := HBoxContainer.new()
	slots.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_child(slots)
	_slot_buttons.clear()
	_guess_slots = [0, 0, 0, 0]
	for i in range(4):
		var btn := Button.new()
		btn.custom_minimum_size = Vector2(72, 48)
		btn.text = COLOUR_NAMES[0]
		var idx := i
		btn.pressed.connect(func():
			_guess_slots[idx] = (_guess_slots[idx] + 1) % COLOUR_NAMES.size()
			btn.text = COLOUR_NAMES[_guess_slots[idx]]
		)
		slots.add_child(btn)
		_slot_buttons.append(btn)
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_child(row)
	var guess_btn := Button.new()
	guess_btn.text = "Guess"
	guess_btn.custom_minimum_size = Vector2(100, 48)
	guess_btn.pressed.connect(func(): _submit_guess(_guess_slots))
	row.add_child(guess_btn)
	var resign := Button.new()
	resign.text = "Resign"
	resign.custom_minimum_size = Vector2(100, 48)
	resign.pressed.connect(func(): _duel_action("resign"))
	row.add_child(resign)


func _process(delta: float) -> void:
	super(delta)
	if _client == null:
		return
	_view_acc += delta
	if _view_acc >= 0.4:
		_view_acc = 0.0
		_pending_hazard_view_id = _client.enqueue_view(
			"player",
			["hazards", "fx_hazard", "player", "clock", "board", "leases"],
			{"replaceable": true, "coalesce_key": "view:g04_hazard"}
		)


func _apply_hazard_view(view: Dictionary) -> void:
	## Requires view.hazards to be present. Omitted hazards must not reach here.
	if not view.has("hazards"):
		return
	_feedback.update_from_view(view)
	_feedback_label.text = _feedback.summary_text()
	var fx_any = view.get("fx_hazard", {})
	var fx: Dictionary = fx_any if typeof(fx_any) == TYPE_DICTIONARY else {}
	var cat_root = view.get("hazards", {})
	var cat: Dictionary = {}
	if typeof(cat_root) == TYPE_DICTIONARY:
		var cat_any = cat_root.get("catastrophe", {})
		cat = cat_any if typeof(cat_any) == TYPE_DICTIONARY else {}
	var cubes_any = cat.get("cubes", {})
	var cubes: Dictionary = cubes_any if typeof(cubes_any) == TYPE_DICTIONARY else {}
	var anchors_any = fx.get("hex_anchors", {})
	if typeof(anchors_any) != TYPE_DICTIONARY:
		var board_any = view.get("board", {})
		if typeof(board_any) == TYPE_DICTIONARY:
			anchors_any = board_any.get("hex_anchors", {})
	var anchors: Dictionary = anchors_any if typeof(anchors_any) == TYPE_DICTIONARY else {}
	# Count active cubes per hex for labels.
	var counts: Dictionary = {}
	for cube_any in cubes.values():
		if typeof(cube_any) != TYPE_DICTIONARY:
			continue
		var c: Dictionary = cube_any
		if not bool(c.get("active", true)):
			continue
		var hid := str(c.get("hex_id", ""))
		counts[hid] = int(counts.get(hid, 0)) + 1

	var present: Dictionary = {}
	for cube_id in cubes.keys():
		var cube_any2 = cubes[cube_id]
		if typeof(cube_any2) != TYPE_DICTIONARY:
			continue
		var cube: Dictionary = cube_any2
		if not bool(cube.get("active", true)):
			continue
		present[cube_id] = true
		if not _hex_nodes.has(cube_id):
			var actor := Node2D.new()
			actor.set_script(HazardActor)
			_hex_layer.add_child(actor)
			actor.duel_requested.connect(_on_duel_requested)
			_hex_nodes[cube_id] = actor
			if _area != null and _area.has_method("register_external_actor"):
				_area.register_external_actor(cube_id, actor)
		var node = _hex_nodes[cube_id]
		var hid2 := str(cube.get("hex_id", ""))
		var anchor_any = anchors.get(hid2, {})
		var anchor: Dictionary = anchor_any if typeof(anchor_any) == TYPE_DICTIONARY else {}
		var grid = anchor.get("grid", [3.0 + float(_hex_nodes.size()), 3.0])
		var player_any = view.get("player", {})
		var visit_any = {}
		if typeof(player_any) == TYPE_DICTIONARY:
			visit_any = player_any.get("visit", {})
		var treated: Array = []
		if typeof(visit_any) == TYPE_DICTIONARY:
			var t = visit_any.get("treated_hexes", [])
			if typeof(t) == TYPE_ARRAY:
				treated = t
		var eligible := true
		if treated.has(hid2):
			eligible = false
		cube["treatment_eligible"] = eligible
		cube["outbreak_warning"] = int(cat.get("era_outbreaks", 0)) >= int(fx.get("outbreak_warning_at", 7))
		cube["cube_count"] = int(counts.get(hid2, 1))
		var labels_any = fx.get("hex_labels", {})
		var label := hid2
		if typeof(labels_any) == TYPE_DICTIONARY and labels_any.has(hid2):
			label = str(labels_any[hid2])
		elif anchor.has("label"):
			label = str(anchor.get("label"))
		_hex_labels[cube_id] = label
		node.bind_cube(cube)
		node.position = node.grid_to_world(grid)
		node.set_selected(cube_id == _selected_cube)

	# Remove obsolete visuals after treatment (explicit absence from authoritative cubes).
	for cube_id in _hex_nodes.keys():
		if not present.has(cube_id):
			if _area != null and _area.has_method("unregister_external_actor"):
				_area.unregister_external_actor(cube_id)
			_hex_nodes[cube_id].queue_free()
			_hex_nodes.erase(cube_id)
			if _selected_cube == cube_id:
				_selected_cube = ""


func _input(event: InputEvent) -> void:
	if _duel_panel.visible and not (_spell_host != null and _spell_host.accepts_world_target()):
		return
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var hovered := get_viewport().gui_get_hovered_control()
		if hovered != null and not (_spell_host != null and _spell_host.accepts_world_target()):
			if _choice_card != null and _choice_card.visible and _choice_card.is_ancestor_of(hovered):
				return
			return
		if _spell_host != null and _spell_host.is_blocking_world():
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
			var label := _public_hazard_label(best)
			if _is_hazard_nearby(best):
				_choice_card.open_for(best, label, [
					{"id": "observe", "label": "Observe"},
					{"id": "challenge", "label": "Challenge"},
				], _hex_nodes.get(best))
			else:
				_prompt.text = label
				_feedback_label.text = label
			if _spell_host != null and _spell_host.accepts_world_target():
				_spell_model.complete_targeting(best)
			get_viewport().set_input_as_handled()


func _public_hazard_label(cube_id: String) -> String:
	var node = _hex_nodes.get(cube_id)
	if node != null and node.has_method("display_label"):
		return str(node.display_label())
	if _hex_labels.has(cube_id):
		return str(_hex_labels[cube_id])
	return "Hazard manifestation"


func _wizard_tile() -> Array:
	if _area != null and _area.has_method("wizard_grid"):
		return _area.wizard_grid()
	return [7.0, 5.0]


func _hazard_tile(cube_id: String) -> Array:
	var node = _hex_nodes.get(cube_id)
	if node == null:
		return []
	return [snapped(node.position.x / TILE - 0.5, 0.01), snapped(node.position.y / TILE - 0.5, 0.01)]


func _is_hazard_nearby(cube_id: String) -> bool:
	return SemanticLabels.in_interaction_range(_wizard_tile(), _hazard_tile(cube_id), INTERACTION_RANGE_TILES)


func _on_hazard_choice(action_id: String, _payload: Dictionary) -> void:
	var cube_id: String = str(_choice_card.target_id())
	_choice_card.visible = false
	if action_id == "observe":
		_prompt.text = _public_hazard_label(cube_id)
		return
	if action_id == "challenge":
		_on_duel_requested(cube_id)


func _start_selected_duel() -> void:
	if _selected_cube == "":
		_prompt.text = "Select a hazard manifestation first"
		return
	_on_duel_requested(_selected_cube)


func _on_duel_requested(cube_id: String) -> void:
	var reply := _cmd("StartHazardDuel", {"cube_id": cube_id})
	if str(reply.get("status", "")) != "ACCEPTED":
		_prompt.text = "Challenge rejected: %s" % reply.get("public_feedback", reply.get("code", "?"))
		return
	var public: Dictionary = reply.get("payload", {}).get("public", {})
	var duel: Dictionary = reply.get("payload", {}).get("duel", {})
	_duel_id = str(public.get("duel_id", duel.get("id", "")))
	_guess_slots = [0, 0, 0, 0]
	for i in range(_slot_buttons.size()):
		_slot_buttons[i].text = COLOUR_NAMES[0]
	_duel_panel.visible = true
	_duel_label.text = "Mastermind vs %s\n4 slots · 6 colours · 10 casts\nExact + colour feedback. World paused." % [
		_public_hazard_label(cube_id)
	]
	if _area:
		_area.set_movement_enabled(false)
	_set_status("Hazard duel active — world paused")


func _submit_guess(guess: Array) -> void:
	if _duel_id == "":
		return
	var reply := _cmd("HazardDuelAction", {
		"duel_id": _duel_id,
		"action": "guess",
		"guess": guess,
	})
	var payload: Dictionary = reply.get("payload", {})
	var status := str(payload.get("status", ""))
	var fb: Dictionary = payload.get("feedback", {})
	if status == "continue":
		_duel_label.text = "Cast %s — exact %s, colour %s\nAdjust colours and Guess again." % [
			fb.get("cast", "?"), fb.get("exact", "?"), fb.get("colour_only", "?")
		]
		return
	# Solved / exhausted / resign nest into ResolveHazardDuel payload.
	_finish_duel(payload)


func _duel_action(action: String) -> void:
	if _duel_id == "":
		return
	if action == "guess":
		_submit_guess(_guess_slots)
		return
	var reply := _cmd("HazardDuelAction", {"duel_id": _duel_id, "action": action})
	var payload: Dictionary = reply.get("payload", {})
	var status := str(payload.get("status", ""))
	if status in ["success", "failed", "world_resolved", "idempotent"] or payload.has("removal") or payload.has("allowance_spent"):
		_finish_duel(payload)
		return
	if action == "resign":
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
