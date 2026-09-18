extends "res://client/scenes/g01_shell.gd"

## G04 FX-BATTLE playable shell — isolated save g04_battle.

const UnitController = preload("res://client/combat/unit_controller.gd")
const LocalBattle = preload("res://client/combat/local_battle.gd")
const EncounterHost = preload("res://client/encounters/encounter_host.gd")
const G04_BATTLE_SAVE := "g04_battle"
const TILE := 64.0
const CHECKPOINT_EVERY_STEPS := 10

var _battle
var _host
var _units_layer: Node2D
var _unit_nodes: Dictionary = {}
var _obstacle_nodes: Array = []
var _selected_unit: String = ""
var _spell_mode := "destroy"
var _spell_bar: HBoxContainer
var _feedback: Label
var _view_acc := 0.0
var _combat_acc_ms := 0.0
var _lease_opened := false
var _steps_since_checkpoint := 0
var _last_status := ""
var _building_nodes: Dictionary = {}


func _ready() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-BATTLE")
	OS.set_environment("DMB_SEED", "404")
	OS.set_environment("DMB_SAVE_SLOT", G04_BATTLE_SAVE)
	super()
	_battle = LocalBattle.new()
	_host = EncounterHost.new()
	_units_layer = Node2D.new()
	_units_layer.name = "BattleUnits"
	_units_layer.z_index = 20
	_world_host.add_child(_units_layer)
	_build_spell_bar()
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
	# Avoid overlapping the shared prompt with oversized world messages.
	_prompt.text = "Select unit, then Destroy / Shield / AtkSpd / Range. No army orders."
	_set_status("G04 FX-BATTLE — walk + cast; armies fight autonomously")
	call_deferred("_open_battle_lease")


func _build_spell_bar() -> void:
	_spell_bar = HBoxContainer.new()
	_spell_bar.name = "SpellBar"
	_spell_bar.set_anchors_preset(PRESET_BOTTOM_WIDE)
	_spell_bar.offset_left = 8
	_spell_bar.offset_right = -8
	_spell_bar.offset_top = -150
	_spell_bar.offset_bottom = -88
	_spell_bar.add_theme_constant_override("separation", 6)
	_spell_bar.alignment = BoxContainer.ALIGNMENT_CENTER
	_ui_root.add_child(_spell_bar)
	for item in [
		["destroy", "Destroy"],
		["shield", "Shield"],
		["frequency", "Atk Spd"],
		["range", "Range"],
		["cast", "Cast"],
	]:
		var btn := Button.new()
		btn.text = item[1]
		btn.custom_minimum_size = Vector2(72, 40)
		btn.pressed.connect(_on_spell_button.bind(item[0]))
		_spell_bar.add_child(btn)


func _on_spell_button(mode: String) -> void:
	if mode == "cast":
		_cast_selected()
		return
	_spell_mode = mode
	_feedback.text = "Spell ready: %s — select a unit, then Cast" % mode.capitalize()


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
	_sync_unit_nodes_from_battle()
	_draw_obstacles(snap.get("blockers", []))
	_feedback.text = "Battle lease open — units advancing"


func _process(delta: float) -> void:
	super(delta)
	if _client == null:
		return
	# Keyboard supplements only.
	if Input.is_action_just_pressed("ui_accept"):
		_spell_mode = "destroy"
	elif Input.is_key_pressed(KEY_1):
		_spell_mode = "shield"
	elif Input.is_key_pressed(KEY_2):
		_spell_mode = "frequency"
	elif Input.is_key_pressed(KEY_3):
		_spell_mode = "range"
	if Input.is_action_just_pressed("ui_select"):
		_cast_selected()

	_view_acc += delta
	if _view_acc >= 0.35:
		_view_acc = 0.0
		_client.enqueue_view(
			"player",
			["units", "battles", "fx_battle", "buildings", "leases", "player", "clock"],
			{"replaceable": true, "coalesce_key": "view:g04_battle"}
		)

	if _paused or _bridge_down or not _lease_opened or _battle.closed:
		return
	if _area != null and not _area.movement_enabled:
		return
	# Local battle steps use Game Time when unpaused; wall clock when focused play.
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
			return  # HUD / spell bar — do not move wizard or reselect via world
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
		if best != "":
			_select_unit(best)
			get_viewport().set_input_as_handled()


func _select_unit(uid: String) -> void:
	_selected_unit = uid
	for id in _unit_nodes.keys():
		_unit_nodes[id].set_selected(id == uid)
	var node = _unit_nodes.get(uid)
	if node:
		_feedback.text = "Selected %s (%s) — spell=%s" % [uid, node.archetype, _spell_mode]


func _cast_selected() -> void:
	if _selected_unit == "":
		_feedback.text = "Select a unit first"
		return
	var observed: Array = _unit_nodes.keys()
	var reply: Dictionary
	if _spell_mode == "destroy":
		reply = _cmd("CastDestroy", {
			"target_id": _selected_unit,
			"observed_ids": observed,
			"lease_id": _battle.lease_id,
		})
		if str(reply.get("status", "")) == "ACCEPTED":
			_battle.queue_destruction(_selected_unit)
			_feedback.text = "Destroy accepted → %s" % _selected_unit
		else:
			_feedback.text = "Destroy rejected: %s" % reply.get("public_feedback", reply.get("code", "?"))
	else:
		reply = _cmd("CastBuff", {
			"target_id": _selected_unit,
			"buff_kind": _spell_mode,
			"observed_ids": observed,
		})
		if str(reply.get("status", "")) == "ACCEPTED":
			_feedback.text = "%s buff applied → %s" % [_spell_mode.capitalize(), _selected_unit]
			# Reflect buff modifiers locally for immediate readability.
			if _battle.units.has(_selected_unit):
				var u: Dictionary = _battle.units[_selected_unit]
				if _spell_mode == "shield":
					u["shield_remaining"] = int(u.get("shield_remaining", 0)) + int(round(float(u.get("max_health", 1)) * 0.25))
				elif _spell_mode == "frequency":
					u["attack_frequency_mult"] = minf(3.0, float(u.get("attack_frequency_mult", 1.0)) + 0.25)
				elif _spell_mode == "range":
					u["extra_range"] = mini(4, int(u.get("extra_range", 0)) + 1)
				_battle.units[_selected_unit] = u
		else:
			_feedback.text = "Buff rejected: %s" % reply.get("public_feedback", reply.get("code", "?"))


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
			# Register with area selection map so Interact can see soldiers.
			if _area != null and _area.has_method("register_external_actor"):
				_area.register_external_actor(uid, node)
			elif _area != null:
				_area._npc_nodes[uid] = node
		_unit_nodes[uid].bind_unit(state)
		_unit_nodes[uid].set_selected(uid == _selected_unit)
	# Buildings as simple markers
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
			_unit_nodes[uid].queue_free()
		_unit_nodes.clear()
		_open_battle_lease()
