extends "res://client/scenes/g01_shell.gd"

## G04 FX-BATTLE playable shell — isolated save g04_battle.
## Target-first interaction: distant Observe; nearby attached Observe/Buff/Destroy.

const UnitController = preload("res://client/combat/unit_controller.gd")
const LocalBattle = preload("res://client/combat/local_battle.gd")
const EncounterHost = preload("res://client/encounters/encounter_host.gd")
const ChoiceCard = preload("res://client/ui/attached_choice_card.gd")
const SemanticLabels = preload("res://client/ui/semantic_labels.gd")
const ContextActions = preload("res://client/ui/context_actions.gd")
const TargetSession = preload("res://client/ui/target_session.gd")
const BridgePresenter = preload("res://client/world/bridge_interaction_presenter.gd")
const G04_BATTLE_SAVE := "g04_battle"
const TILE := 64.0
const CHECKPOINT_EVERY_STEPS := 10
const INTERACTION_RANGE_TILES := 2.0

var _battle
var _host
var _units_layer: Node2D
var _unit_nodes: Dictionary = {}
var _obstacle_nodes: Array = []
var _selected_unit: String = ""
var _feedback: Label
var _view_acc := 0.0
var _lease_opened := false
var _steps_since_checkpoint := 0
var _building_nodes: Dictionary = {}
var _choice_card
var _router
var _choice_pause_token := ""
var _choice_open := false
var _fx_labels: Dictionary = {}
var _session
var _presenter


func _ready() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-BATTLE")
	OS.set_environment("DMB_SEED", "404")
	OS.set_environment("DMB_SAVE_SLOT", G04_BATTLE_SAVE)
	super()
	_battle = LocalBattle.new()
	_host = EncounterHost.new()
	_router = ContextActions.new()
	_units_layer = Node2D.new()
	_units_layer.name = "BattleUnits"
	_units_layer.z_index = 20
	_world_host.add_child(_units_layer)
	_choice_card = ChoiceCard.new()
	_choice_card.name = "ChoiceCard"
	_ui_root.add_child(_choice_card)
	_session = TargetSession.new()
	_session.setup(_choice_card, Callable(self, "_acquire_choice_pause"), Callable(self, "_release_choice_pause"))
	_session.observation_requested.connect(_on_session_observe)
	_session.action_requested.connect(_on_session_action)
	_session.dismissed.connect(func(_id): _choice_open = false)
	_presenter = BridgePresenter.new()
	_ui_root.add_child(_presenter)
	_presenter.setup(_ui_root, null, Callable(self, "_cmd"))
	_feedback = Label.new()
	_feedback.set_anchors_preset(PRESET_TOP_WIDE)
	_feedback.offset_left = 12
	_feedback.offset_top = 92
	_feedback.offset_right = -12
	_feedback.offset_bottom = 140
	_feedback.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_feedback.add_theme_font_size_override("font_size", 13)
	_feedback.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_ui_root.add_child(_feedback)
	_prompt.text = "Click a unit: far = Observe, near = choices. No permanent spell bar."
	_set_status("G04 FX-BATTLE — walk + target choices; armies fight autonomously")
	_apply_mode_chrome_visibility()
	call_deferred("_open_battle_lease")


func _configure_spellbook() -> void:
	super._configure_spellbook()
	_spell_binder.setup(_spell_model, "g04_battle", "G04 Battle Spellbook")
	_spell_binder.build_g04_battle_pages()
	_spell_binder.register("wait", func(_p): return _spell_wait())
	_spell_binder.register("invalid_exit", func(_p): return _spell_invalid())
	_spell_binder.register("pause", func(_p): return _spell_pause())
	_spell_binder.register("resume", func(_p): return _spell_resume())
	_spell_binder.register("save", func(_p): return _spell_save_battle())
	_spell_binder.register("load", func(_p): return _spell_load_battle())
	_spell_binder.register("bridge_fail", func(_p): return _spell_bridge_fail())
	_spell_binder.register("toggle_diag", func(_p): _toggle_diag(); return {"status": "OK", "message": "Dev panel %s" % ("open" if _diag_open else "closed")})
	_spell_binder.register("spell_destroy", func(p): return _spell_cast_targeted(p, "destroy"))
	_spell_binder.register("spell_shield", func(p): return _spell_cast_targeted(p, "shield"))
	_spell_binder.register("spell_frequency", func(p): return _spell_cast_targeted(p, "frequency"))
	_spell_binder.register("spell_range", func(p): return _spell_cast_targeted(p, "range"))


func _apply_mode_chrome_visibility() -> void:
	# Permanent spell toolbar removed — contextual cards only.
	pass


func _spell_save_battle() -> Dictionary:
	_on_save()
	return {"status": "OK", "message": _prompt.text}


func _spell_load_battle() -> Dictionary:
	_on_load()
	return {"status": "OK", "message": _prompt.text}


func _spell_cast_targeted(payload: Dictionary, mode: String) -> Dictionary:
	_selected_unit = str(payload.get("target_id", ""))
	if _selected_unit == "":
		return {"status": "REJECTED", "message": "No target"}
	if mode == "destroy":
		_apply_destroy(_selected_unit)
	else:
		_apply_buff(_selected_unit, mode)
	var ok: bool = _feedback.text.find("rejected") < 0 and _feedback.text.find("Select") < 0
	return {"status": "ACCEPTED" if ok else "REJECTED", "message": _feedback.text}


func _open_battle_lease() -> void:
	if _client == null or _lease_opened:
		return
	var reply := _cmd("OpenBattleLease", {"battle_id": "battle:fx"})
	if str(reply.get("status", "")) != "ACCEPTED":
		_feedback.text = "Battle lease failed: %s" % reply.get("public_feedback", reply.get("code", "?"))
		return
	var payload: Dictionary = reply.get("payload", {})
	var lease: Dictionary = payload.get("lease", {})
	var snap: Dictionary = payload.get("snapshot", lease.get("checkpoint", {}))
	_host.acknowledge(lease)
	_battle.bind_lease({
		"lease_id": lease.get("lease_id"),
		"version": lease.get("version"),
		"checkpoint_hash": lease.get("checkpoint_hash"),
		"snapshot": snap,
	})
	_lease_opened = true
	if _client.has_player_cache():
		var view: Dictionary = _client.cached_player_view()
		_fx_labels = view.get("fx_battle", {}).get("labels", {})
	_sync_unit_nodes_from_battle()
	_draw_obstacles(snap.get("blockers", []))
	_feedback.text = "Battle lease open — click units to Observe or choose spells"


func _public_label(uid: String) -> String:
	if _fx_labels.has(uid):
		return str(_fx_labels[uid])
	var node = _unit_nodes.get(uid)
	if node == null:
		return "Unit"
	var view := {
		"faction_id": node.faction_id if "faction_id" in node else "",
		"archetype": node.archetype if "archetype" in node else "",
		"known": true,
	}
	return SemanticLabels.label_for(view)


func _wizard_tile() -> Array:
	if _area != null and _area.has_method("wizard_grid"):
		return _area.wizard_grid()
	return [4.0, 5.0]


func _unit_tile(uid: String) -> Array:
	var node = _unit_nodes.get(uid)
	if node == null:
		return []
	return [snapped(node.position.x / TILE - 0.5, 0.01), snapped(node.position.y / TILE - 0.5, 0.01)]


func _is_nearby(uid: String) -> bool:
	var w := _wizard_tile()
	var t := _unit_tile(uid)
	if t.is_empty():
		return false
	return SemanticLabels.in_interaction_range(w, t, INTERACTION_RANGE_TILES)


func _collect_local_poses() -> Dictionary:
	var poses := {"wizard": _wizard_tile()}
	for uid in _unit_nodes.keys():
		poses[uid] = _unit_tile(uid)
	return poses


func _acquire_choice_pause() -> void:
	if _choice_pause_token != "":
		return
	var reply := _cmd("Pause", {"reason": "choice"})
	if str(reply.get("status", "")) == "ACCEPTED":
		_choice_pause_token = str(reply.get("payload", {}).get("token", ""))
	_choice_open = true


func _release_choice_pause() -> void:
	if _choice_pause_token != "":
		_cmd("Resume", {"token": _choice_pause_token})
		_choice_pause_token = ""
	_choice_open = false


func _open_observation(uid: String) -> void:
	_on_session_observe(uid, "unit")


func _on_session_observe(uid: String, _kind: String) -> void:
	_selected_unit = uid
	for id in _unit_nodes.keys():
		_unit_nodes[id].set_selected(id == uid)
	var reply := _cmd("Observe", {
		"entity_id": uid,
		"local_poses": _collect_local_poses(),
	})
	var view: Dictionary = reply.get("payload", {})
	var label := str(view.get("label", _public_label(uid)))
	_fx_labels[uid] = label
	_feedback.text = str(view.get("description", label))
	_prompt.text = label
	if _presenter:
		_presenter.show_observation(uid, _unit_nodes.get(uid), view)


func _on_session_action(uid: String, action_id: String, payload: Dictionary) -> void:
	_selected_unit = uid
	match action_id:
		"buff_shield", "buff_frequency", "buff_range":
			var kind := str(payload.get("buff_kind", action_id.replace("buff_", "")))
			_apply_buff(uid, kind)
		"destroy":
			_apply_destroy(uid)
		_:
			pass
	_choice_open = false


func _open_choice_card(uid: String) -> void:
	_selected_unit = uid
	for id in _unit_nodes.keys():
		_unit_nodes[id].set_selected(id == uid)
	var label := _public_label(uid)
	_choice_open = true
	_session.handle_target_click(uid, true, "unit", label, _unit_nodes.get(uid))
	_feedback.text = "Choose an action for %s" % label


func _on_choice_action(action_id: String, payload: Dictionary) -> void:
	# Retained for older tests; TargetSession owns the live card.
	_on_session_action(str(_choice_card.target_id()), action_id, payload)


func _on_choice_closed() -> void:
	_release_choice_pause()
	_choice_open = false
	_router.cancel_choice(_selected_unit)


func _close_choice_card(applied: bool) -> void:
	if _session != null:
		_session.close(applied)
	else:
		_choice_card.visible = false
		_release_choice_pause()
	_choice_open = false
	if not applied:
		_feedback.text = "Choice closed — nothing cast"


func _apply_destroy(uid: String) -> void:
	if not _is_nearby(uid):
		_feedback.text = "Destroy rejected: out_of_range"
		return
	var reply := _cmd("CastDestroy", {
		"target_id": uid,
		"lease_id": _battle.lease_id,
		"local_poses": _collect_local_poses(),
	})
	if str(reply.get("status", "")) == "ACCEPTED":
		_battle.queue_destruction(uid)
		_feedback.text = "Destroy accepted → %s" % _public_label(uid)
	else:
		_feedback.text = "Destroy rejected: %s" % reply.get("public_feedback", reply.get("code", "?"))


func _apply_buff(uid: String, buff_kind: String) -> void:
	if not _is_nearby(uid):
		_feedback.text = "Buff rejected: out_of_range"
		return
	var reply := _cmd("CastBuff", {
		"target_id": uid,
		"buff_kind": buff_kind,
		"local_poses": _collect_local_poses(),
	})
	if str(reply.get("status", "")) == "ACCEPTED":
		_feedback.text = "%s on %s" % [buff_kind.capitalize(), _public_label(uid)]
		if _battle.units.has(uid):
			var u: Dictionary = _battle.units[uid]
			if buff_kind == "shield":
				u["shield_remaining"] = int(u.get("shield_remaining", 0)) + int(round(float(u.get("max_health", 1)) * 0.25))
			elif buff_kind == "frequency":
				u["attack_frequency_mult"] = minf(3.0, float(u.get("attack_frequency_mult", 1.0)) + 0.25)
			elif buff_kind == "range":
				u["extra_range"] = mini(4, int(u.get("extra_range", 0)) + 1)
			_battle.units[uid] = u
			if _unit_nodes.has(uid):
				_unit_nodes[uid].bind_unit(u)
	else:
		_feedback.text = "Buff rejected: %s" % reply.get("public_feedback", reply.get("code", "?"))


func _process(delta: float) -> void:
	super(delta)
	if _client == null:
		return
	# Walk-away closes the choice card without casting (keyboard, pad, shared intent).
	if _choice_open and _session != null:
		if _session.poll_keyboard_movement_intent():
			_choice_open = false
			if _presenter:
				_presenter.notify_player_moved()
	_view_acc += delta
	if _view_acc >= 0.35:
		_view_acc = 0.0
		_client.enqueue_view(
			"player",
			["units", "battles", "fx_battle", "buildings", "leases", "player", "clock"],
			{"replaceable": true, "coalesce_key": "view:g04_battle"}
		)
		if _client.has_player_cache():
			var view: Dictionary = _client.cached_player_view()
			if view.has("fx_battle"):
				_fx_labels = view.get("fx_battle", {}).get("labels", _fx_labels)

	if _paused or _choice_open or _bridge_down or not _lease_opened or _battle.closed:
		return
	if _area != null and not _area.movement_enabled:
		return
	var step_ms := delta * 1000.0
	var results: Array = _battle.tick(step_ms)
	for result in results:
		_apply_step_visuals(result)
		_steps_since_checkpoint += 1
	if _steps_since_checkpoint >= CHECKPOINT_EVERY_STEPS:
		_submit_checkpoint()
		_steps_since_checkpoint = 0


func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		var hovered := get_viewport().gui_get_hovered_control()
		if hovered != null:
			if _choice_card != null and _choice_card.visible and _choice_card.is_ancestor_of(hovered):
				return
			if _spell_host != null and _spell_host.accepts_world_target():
				pass
			else:
				return
		if _spell_host != null and _spell_host.is_blocking_world():
			return
		var gp: Vector2 = _units_layer.get_global_mouse_position() if _units_layer else get_global_mouse_position()
		var best := ""
		var best_d := 40.0
		for uid in _unit_nodes.keys():
			var node = _unit_nodes[uid]
			if not node.alive:
				continue
			var d: float = node.global_position.distance_to(gp)
			if d < best_d:
				best_d = d
				best = uid
		if best == "":
			if _session != null and _session.is_open():
				_session.notify_movement_intent()
				_choice_open = false
				if _presenter:
					_presenter.notify_player_moved()
			return
		_router.consume_pointer()
		if _spell_host != null and _spell_host.accepts_world_target():
			_selected_unit = best
			_spell_model.complete_targeting(best)
			get_viewport().set_input_as_handled()
			return
		var label := _public_label(best)
		var route: String = _session.handle_target_click(best, _is_nearby(best), "unit", label, _unit_nodes.get(best))
		_choice_open = route == "choice"
		get_viewport().set_input_as_handled()


func _apply_step_visuals(result: Dictionary) -> void:
	for uid in result.get("fired", []):
		if _unit_nodes.has(uid):
			_unit_nodes[uid].flash_attack()
	_sync_unit_nodes_from_battle()


func _sync_unit_nodes_from_battle() -> void:
	for uid in _battle.units.keys():
		var state: Dictionary = _battle.units[uid]
		if str(state.get("status", "")) == "reserve":
			continue
		if not _unit_nodes.has(uid):
			var node := Node2D.new()
			node.set_script(UnitController)
			_units_layer.add_child(node)
			_unit_nodes[uid] = node
			if _area != null and _area.has_method("register_external_actor"):
				_area.register_external_actor(uid, node)
		_unit_nodes[uid].bind_unit(state)
		_unit_nodes[uid].set_selected(uid == _selected_unit)
	for bid in _battle.buildings.keys():
		var b: Dictionary = _battle.buildings[bid]
		if not _building_nodes.has(bid):
			var marker := ColorRect.new()
			marker.size = Vector2(40, 40)
			marker.color = Color(0.45, 0.35, 0.25) if "red" in bid else Color(0.25, 0.35, 0.55)
			_units_layer.add_child(marker)
			_building_nodes[bid] = marker
			var lab := Label.new()
			lab.text = str(b.get("label", bid))
			lab.position = Vector2(0, -16)
			lab.add_theme_font_size_override("font_size", 10)
			marker.add_child(lab)
		var pos = b.get("position", [0, 0])
		_building_nodes[bid].position = Vector2(float(pos[0]) * TILE, float(pos[1]) * TILE)
		_building_nodes[bid].modulate = Color(1, 1, 1) if bool(b.get("alive", true)) else Color(0.3, 0.3, 0.3)


func _draw_obstacles(blockers: Array) -> void:
	for n in _obstacle_nodes:
		n.queue_free()
	_obstacle_nodes.clear()
	for block_any in blockers:
		var block: Dictionary = block_any
		var pos = block.get("position", [0, 0])
		var rect := ColorRect.new()
		rect.size = Vector2(TILE * 0.9, TILE * 0.9)
		rect.color = Color(0.35, 0.32, 0.28, 0.9)
		rect.position = Vector2(float(pos[0]) * TILE + TILE * 0.05, float(pos[1]) * TILE + TILE * 0.05)
		_units_layer.add_child(rect)
		_obstacle_nodes.append(rect)
		var lab := Label.new()
		lab.text = str(block.get("label", "cover"))
		lab.position = Vector2(4, 4)
		lab.add_theme_font_size_override("font_size", 10)
		rect.add_child(lab)


func _submit_checkpoint() -> void:
	if not _lease_opened:
		return
	var cp: Dictionary = _battle.checkpoint()
	var reply := _cmd("BattleCheckpoint", {
		"lease_id": _battle.lease_id,
		"version": _battle.lease_version,
		"base_checkpoint_hash": _host.checkpoint_hash,
		"delta": cp,
		"checkpoint": cp,
	})
	if str(reply.get("status", "")) == "ACCEPTED":
		var lease: Dictionary = reply.get("payload", {}).get("lease", {})
		if lease.has("checkpoint_hash"):
			_host.checkpoint_hash = str(lease["checkpoint_hash"])
		if lease.has("version"):
			_battle.lease_version = int(lease["version"])
			_host.lease_version = int(lease["version"])


func _on_save() -> void:
	_submit_checkpoint()
	var reply := _cmd("Save", {"slot": G04_BATTLE_SAVE})
	_feedback.text = "Saved %s → %s" % [G04_BATTLE_SAVE, reply.get("status", "?")]
	if str(reply.get("status", "")) == "ACCEPTED":
		_prompt.text = "Saved isolated slot %s" % G04_BATTLE_SAVE


func _on_load() -> void:
	var reply := _cmd("Load", {"slot": G04_BATTLE_SAVE})
	_feedback.text = "Loaded %s → %s" % [G04_BATTLE_SAVE, reply.get("status", "?")]
	if str(reply.get("status", "")) == "ACCEPTED":
		_prompt.text = "Loaded %s — casualties preserved" % G04_BATTLE_SAVE
		_lease_opened = false
		for uid in _unit_nodes.keys():
			if _area != null and _area.has_method("unregister_external_actor"):
				_area.unregister_external_actor(uid)
			_unit_nodes[uid].queue_free()
		_unit_nodes.clear()
		_open_battle_lease()


# Compatibility shims for older tests that still call private helpers.
func _select_unit(uid: String) -> void:
	if _is_nearby(uid):
		_open_choice_card(uid)
	else:
		_open_observation(uid)


func _cast_selected() -> void:
	if _selected_unit == "":
		_feedback.text = "Select a unit first"
		return
	_apply_destroy(_selected_unit)
