extends SceneTree

## Visual Sim QA kernel — single live session for authority + render + pixels.
## Env:
##   DMB_VISUAL_SIM_OUT, DMB_FIXTURE, DMB_SEED, DMB_SAVE_SLOT
##   DMB_VISUAL_SIM_MODE = smoke|construction|combat|oracle_fault|ui_move
##   DMB_RESOLUTION, DMB_SESSION_ID

const Driver = preload("res://client/tests/auto_gate_driver.gd")
const Harvester = preload("res://client/tests/visual_sim_harvester.gd")

var _driver
var _out_dir := ""
var _session_id := ""
var _capture_seq := 0
var _mode := "smoke"
var _variations := 5
var _clock_seq := 0
## Small camera/player nudges for multi-shot review (v0 = canonical).
const _NUDGES := [
	Vector2(0, 0),
	Vector2(56, 0),
	Vector2(-56, 0),
	Vector2(0, 56),
	Vector2(0, -56),
]

func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_out_dir = OS.get_environment("DMB_VISUAL_SIM_OUT").strip_edges()
	if _out_dir == "":
		push_error("DMB_VISUAL_SIM_OUT required")
		_finish(2)
		return
	_session_id = OS.get_environment("DMB_SESSION_ID")
	if _session_id == "":
		_session_id = "sess_%d" % Time.get_unix_time_from_system()
	_mode = OS.get_environment("DMB_VISUAL_SIM_MODE")
	if _mode == "":
		_mode = "smoke"
	var var_env := OS.get_environment("DMB_VISUAL_SIM_VARIATIONS")
	if var_env != "":
		_variations = clampi(int(var_env), 1, 5)
	elif _mode in ["construction", "combat", "ui_move"]:
		_variations = 5
	else:
		_variations = 1
	print("VISUAL_SIM_KERNEL_START mode=%s variations=%s" % [_mode, _variations])
	DirAccess.make_dir_recursive_absolute(_out_dir)
	for sub in ["shots", "render", "authority", "logs", "checkpoints"]:
		DirAccess.make_dir_recursive_absolute(_out_dir.path_join(sub))

	var fixture := OS.get_environment("DMB_FIXTURE")
	if fixture == "":
		fixture = "FX-MVP"
	var seed := int(OS.get_environment("DMB_SEED")) if OS.get_environment("DMB_SEED") != "" else 507
	_driver = Driver.new(self)
	var ok: bool = await _driver.launch_fixture("VISUAL_SIM", fixture, seed, "visual_sim_%s_%s" % [_mode, _session_id])
	if not ok:
		_write_json(_out_dir.path_join("logs/boot_failed.json"), {"error": "boot_failed", "errors": _driver.script_errors})
		print("VISUAL_SIM_KERNEL_FAIL boot")
		_finish(1)
		return
	var res := OS.get_environment("DMB_RESOLUTION")
	if res != "":
		var parts := res.split("x")
		if parts.size() == 2:
			await _driver.force_size(Vector2i(int(parts[0]), int(parts[1])))
	await _driver.wait_state(func(): return _driver.shell != null and _driver.shell.is_booted(), 45000, "booted")
	await process_frame
	await process_frame

	var result_code := 0
	match _mode:
		"smoke":
			result_code = await _run_smoke()
		"construction":
			result_code = await _run_construction()
		"combat":
			result_code = await _run_combat()
		"oracle_fault":
			result_code = await _run_oracle_fault()
		"ui_move":
			result_code = await _run_ui_move()
		_:
			result_code = await _run_smoke()
	_teardown()
	if result_code == 0:
		print("VISUAL_SIM_KERNEL_OK mode=%s session=%s captures=%s" % [_mode, _session_id, _capture_seq])
	else:
		print("VISUAL_SIM_KERNEL_FAIL mode=%s code=%s" % [_mode, result_code])
	_finish(result_code)


func _run_smoke() -> int:
	var cp := await _checkpoint("SMOKE_BOOT", "after", "fixture_boot", "Overworld shell nonblank; player present")
	if not bool(cp.get("ok")):
		return 1
	return 0


func _run_construction() -> int:
	## Advance industry briefly, Wait until an order is reserved/in-progress (scaffold),
	## then Wait until committed; capture before/transition/after/aftermath.
	await _checkpoint("CONSTRUCT_BEFORE", "before", "setup", "World before construction waits")
	var reserved_id := ""
	var committed_id := ""
	var action_kind := ""
	for i in range(45):
		_advance_seconds(1)
		await process_frame
	await _checkpoint("CONSTRUCT_INDUSTRY", "before", "AdvanceGame", "After industry advance")
	for i in range(200):
		await _wait_once("construct-w%d" % i)
		if i % 20 == 0:
			print("VISUAL_SIM_CONSTRUCT_WAIT i=%s reserved=%s" % [i, reserved_id])
		var auth: Dictionary = _live_authority()
		if auth.has("error"):
			print("VISUAL_SIM_CONSTRUCT_AUTH_ERR %s" % auth.get("error"))
			continue
		for oid in auth.get("orders", {}).keys():
			var o: Dictionary = auth["orders"][oid]
			var st := str(o.get("status", ""))
			var act := str(o.get("action", ""))
			if st in ["reserved", "ready", "in_progress", "delivering"] and reserved_id == "":
				reserved_id = oid
				action_kind = act
				await _checkpoint("CONSTRUCT_SCAFFOLD", "transition", "Wait", "Scaffold/order %s (%s) active" % [oid, act])
			if st == "committed":
				committed_id = oid
				action_kind = act
				break
		if committed_id != "":
			break
		if i % 8 == 7:
			_advance_seconds(1)
			await process_frame
	if committed_id == "":
		_write_json(_out_dir.path_join("logs/construction_incomplete.json"), {"reserved": reserved_id, "action": action_kind, "counts": _live_authority().get("counts", {})})
		await _checkpoint("CONSTRUCT_INCOMPLETE", "after", "Wait", "No committed construction order")
		# Emit planned IDs so the matrix rows are not MISSING — oracle will FAIL on committed expectations.
		await _checkpoint("CONSTRUCT_SCAFFOLD", "transition", "Wait", "INCOMPLETE: no scaffold/order observed")
		await _checkpoint("CONSTRUCT_DONE", "after", "Wait", "INCOMPLETE: no committed order")
		await _checkpoint("CONSTRUCT_AFTERMATH", "aftermath", "Wait", "INCOMPLETE: no construction aftermath")
		return 2
	if reserved_id == "":
		await _checkpoint("CONSTRUCT_SCAFFOLD", "transition", "Wait", "Committed without observed scaffold phase; order %s (%s)" % [committed_id, action_kind])
	await _checkpoint("CONSTRUCT_DONE", "after", "Wait", "Order %s committed (%s); scaffold must be gone" % [committed_id, action_kind])
	await _wait_once("construct-aftermath")
	await _checkpoint("CONSTRUCT_AFTERMATH", "aftermath", "Wait", "World after construction; no stale scaffold %s" % committed_id)
	_write_json(_out_dir.path_join("logs/construction_result.json"), {
		"committed_id": committed_id,
		"action": action_kind,
		"scenario_note": "road is construction-order not building-body" if action_kind == "road" else "building_or_settlement",
	})
	return 0


func _run_combat() -> int:
	## Industry → Wait until PENDING battle → host LocalBattle → tick → return.
	## FX-MVP needs ~120 AdvanceGame ticks before military units/formations exist.
	print("VISUAL_SIM_COMBAT_ADVANCE")
	for i in range(120):
		_advance_seconds(1)
		await process_frame
		if i % 20 == 0:
			var mid: Dictionary = _live_authority()
			print("VISUAL_SIM_COMBAT_ADV i=%s units=%s formations=%s" % [
				i,
				_count_field(mid, "units"),
				_count_field(mid, "formations"),
			])
	await _checkpoint("COMBAT_BEFORE", "before", "AdvanceGame", "Units/formations after industry")
	var battle_id := ""
	var battle_node := ""
	for i in range(100):
		await _wait_once("combat-w%d" % i)
		if i % 15 == 0:
			print("VISUAL_SIM_COMBAT_WAIT i=%s" % i)
		var auth: Dictionary = _live_authority()
		if auth.has("error"):
			continue
		for bid in auth.get("battles", {}).keys():
			var b: Dictionary = auth["battles"][bid]
			var st := str(b.get("state", ""))
			if st in ["PENDING", "LOCAL", "ACTIVE", "READY"]:
				battle_id = bid
				battle_node = str(b.get("node_id", ""))
				break
		if battle_id != "":
			break
		if i % 6 == 5:
			_advance_seconds(1)
			await process_frame
	if battle_id == "":
		_write_json(_out_dir.path_join("logs/combat_no_battle.json"), {"ok": false, "authority": _live_authority().get("counts", {})})
		await _checkpoint("COMBAT_NO_BATTLE", "after", "Wait", "No battle reached")
		return 2
	print("VISUAL_SIM_COMBAT_FOUND %s at %s" % [battle_id, battle_node])
	await _checkpoint("COMBAT_CONTACT", "transition", "Wait", "Battle %s contacted at %s" % [battle_id, battle_node])
	if battle_node != "":
		_driver.shell._spectator_node = battle_node
	if _driver.shell.has_method("reproject_from_python"):
		_driver.shell.reproject_from_python()
	var lease_reply: Dictionary = {}
	if _driver.shell.has_method("_cmd"):
		lease_reply = _driver.shell._cmd("OpenBattleLease", {"battle_id": battle_id})
		_write_json(_out_dir.path_join("logs/lease_open.json"), lease_reply)
		if str(lease_reply.get("status", "")) == "ACCEPTED" and _driver.shell.get("_battle") == null:
			var LocalBattle = load("res://client/combat/local_battle.gd")
			var EncounterHost = load("res://client/encounters/encounter_host.gd")
			var payload: Dictionary = lease_reply.get("payload", {})
			if typeof(payload) != TYPE_DICTIONARY:
				payload = {}
			var lease: Dictionary = payload.get("lease", {})
			if typeof(lease) != TYPE_DICTIONARY:
				lease = {}
			var snap: Dictionary = payload.get("snapshot", {})
			if typeof(snap) != TYPE_DICTIONARY:
				snap = {}
			if snap.is_empty() and typeof(lease.get("checkpoint")) == TYPE_DICTIONARY:
				snap = lease.get("checkpoint")
			var battle = LocalBattle.new()
			var host = EncounterHost.new()
			if host.has_method("acknowledge"):
				host.acknowledge(lease)
			battle.bind_lease({
				"lease_id": lease.get("lease_id"),
				"version": lease.get("version"),
				"checkpoint_hash": lease.get("checkpoint_hash"),
				"snapshot": snap,
			})
			_driver.shell._battle = battle
			_driver.shell._battle_host = host
			_driver.shell._battle_lease_opened = true
			_driver.shell._hosted_battle_id = battle_id
	var ticks := 0
	for _t in range(90):
		await process_frame
		if _driver.shell.get("_battle") != null and _driver.shell._battle.has_method("tick"):
			_driver.shell._battle.tick(50.0)
			ticks += 1
		if _driver.shell.get("_battle") != null and bool(_driver.shell._battle.closed):
			break
	_write_json(_out_dir.path_join("logs/combat_ticks.json"), {"ticks": ticks, "battle_id": battle_id})
	await _checkpoint("COMBAT_ATTENDED", "transition", "OpenBattleLease+tick", "Attended LocalBattle ticks=%s for %s" % [ticks, battle_id])
	var auth2: Dictionary = _live_authority()
	var battles2 = auth2.get("battles")
	var b2: Dictionary = {}
	if typeof(battles2) == TYPE_DICTIONARY and battles2.has(battle_id) and typeof(battles2[battle_id]) == TYPE_DICTIONARY:
		b2 = battles2[battle_id]
	var lid := str(b2.get("lease_id", ""))
	if lid == "" and _driver.shell.get("_battle") != null:
		lid = str(_driver.shell._battle.lease_id)
	if lid != "" and _driver.shell.has_method("_cmd"):
		var close_reply: Dictionary = _driver.shell._cmd("CloseBattleLease", {"lease_id": lid, "battle_id": battle_id})
		_write_json(_out_dir.path_join("logs/lease_close.json"), close_reply)
	if _driver.shell.has_method("_close_local_battle_lease"):
		_driver.shell._close_local_battle_lease()
	_driver.shell._spectator_node = ""
	await process_frame
	await process_frame
	await _checkpoint("COMBAT_RETURN", "aftermath", "CloseBattleLease", "Returned to world after battle %s" % battle_id)
	return 0


func _run_ui_move() -> int:
	await _checkpoint("UI_BEFORE", "before", "boot", "HUD before map open")
	if _driver.shell.has_method("invoke_world_map_for_test"):
		_driver.shell.invoke_world_map_for_test()
		await _driver.wait_state(func():
			var p = _driver.shell.world_map_panel()
			return p != null and p.visible
		, 8000, "map_open")
	await _checkpoint("UI_MAP_OPEN", "transition", "open_world_map", "World map panel open")
	# Actual pointer press on wait if available
	var wait_btn = _driver.shell.fx_era_wait_button() if _driver.shell.has_method("fx_era_wait_button") else null
	if wait_btn != null and wait_btn.visible:
		await _driver.press_ui(wait_btn, "wait_pointer")
		await process_frame
	await _checkpoint("UI_AFTER_WAIT", "after", "pointer_Wait", "After pointer Wait")
	if _driver.shell.has_method("invoke_world_map_for_test"):
		var p2 = _driver.shell.world_map_panel()
		if p2 != null and p2.visible:
			_driver.shell.invoke_world_map_for_test()
	await _checkpoint("UI_MAP_CLOSED", "aftermath", "close_world_map", "Map closed")
	return 0


func _run_oracle_fault() -> int:
	## Disposable mutations on frozen shell; write healthy + fault harvests for Python verdict.
	await _checkpoint("FAULT_HEALTHY", "before", "boot", "Healthy harvest baseline")
	if _driver.shell != null:
		_driver.shell.set_process(false)
		_driver.shell.set_physics_process(false)
	var target: Node = _find_fault_target()
	if target == null:
		print("VISUAL_SIM_ORACLE_FAIL no_target")
		return 1
	var sid := str(target.get_meta("sim_id"))
	var parent: Node = target.get_parent()
	var layers = _driver.shell.get("_layers")
	# Duplicate
	var clone: Node = target.duplicate()
	clone.set_meta("sim_id", sid)
	clone.set_meta("sim_kind", str(target.get_meta("sim_kind")) if target.has_meta("sim_kind") else "entity")
	clone.set_meta("sim_role", "body")
	parent.add_child(clone)
	await process_frame
	_write_json(_out_dir.path_join("render/fault_duplicate.json"), Harvester.harvest(_driver.shell))
	if clone.get_parent() != null:
		clone.get_parent().remove_child(clone)
	clone.free()
	await process_frame
	# Hide
	if target is CanvasItem:
		(target as CanvasItem).visible = false
	await process_frame
	_write_json(_out_dir.path_join("render/fault_hidden.json"), Harvester.harvest(_driver.shell))
	if target is CanvasItem:
		(target as CanvasItem).visible = true
	# Move
	if target is Node2D:
		var orig: Vector2 = (target as Node2D).position
		(target as Node2D).position = orig + Vector2(800, 800)
		await process_frame
		_write_json(_out_dir.path_join("render/fault_moved.json"), Harvester.harvest(_driver.shell))
		(target as Node2D).position = orig
	# Remove
	if layers != null and layers.get("_by_id") != null:
		layers._by_id.erase(sid)
	if target.get_parent() != null:
		target.get_parent().remove_child(target)
	target.free()
	await process_frame
	_write_json(_out_dir.path_join("render/fault_missing.json"), Harvester.harvest(_driver.shell))
	_write_json(_out_dir.path_join("logs/fault_target.json"), {"sim_id": sid})
	print("VISUAL_SIM_ORACLE_FAULTS_WRITTEN target=%s" % sid)
	return 0


func _find_fault_target() -> Node:
	## Prefer WorldLayerPresenters bodies; fall back to overworld entity nodes; never invent IDs.
	if _driver.shell == null:
		return null
	var layers = _driver.shell.get("_layers")
	if layers != null and layers.get("_by_id") != null:
		var by: Dictionary = layers._by_id
		for id in by.keys():
			var n = by[id]
			if n != null and is_instance_valid(n) and n.has_meta("sim_id"):
				return n
	var ow = _driver.shell.get("_overworld")
	if ow != null and ow.get("_entities") != null and typeof(ow._entities) == TYPE_ARRAY:
		for raw in ow._entities:
			if typeof(raw) != TYPE_DICTIONARY:
				continue
			var n2 = raw.get("node")
			if typeof(n2) == TYPE_OBJECT and is_instance_valid(n2) and n2.has_meta("sim_id"):
				if str(n2.get_meta("sim_id")) == "player:wizard":
					continue
				return n2
	if ow != null and ow.get("_actors_root") != null:
		for c in ow._actors_root.get_children():
			if c.has_meta("sim_id") and str(c.get_meta("sim_id")) != "player:wizard":
				return c
	if ow != null and ow.get("_john") != null and is_instance_valid(ow._john):
		return ow._john
	return null


func _checkpoint(capture_id: String, phase: String, action: String, should_see: String) -> Dictionary:
	## Capture up to _variations shots with small camera/player movement between them.
	var last := {}
	var ow = _driver.shell.get("_overworld") if _driver.shell != null else null
	var cam = ow.get("_camera") if ow != null else null
	var john = ow.get("_john") if ow != null else null
	var orig_cam_offset := Vector2.ZERO
	var orig_john_pos := Vector2.ZERO
	var orig_cam_pos := Vector2.ZERO
	if cam != null and is_instance_valid(cam):
		orig_cam_offset = cam.offset
		orig_cam_pos = cam.position
	if john != null and is_instance_valid(john):
		orig_john_pos = john.position
	for vi in range(_variations):
		var cid := capture_id if _variations == 1 else "%s_v%d" % [capture_id, vi]
		var nudge: Vector2 = _NUDGES[vi] if vi < _NUDGES.size() else Vector2.ZERO
		if cam != null and is_instance_valid(cam):
			cam.offset = orig_cam_offset + nudge
			if john != null and is_instance_valid(john) and vi > 0:
				john.position = orig_john_pos + nudge
				cam.position = john.position + Vector2(32, 32)
			if cam.has_method("reset_smoothing"):
				cam.reset_smoothing()
			if cam.has_method("force_update_scroll"):
				cam.force_update_scroll()
		await process_frame
		await process_frame
		last = await _capture_once(cid, phase, action, should_see, vi, capture_id)
		print("VISUAL_SIM_CAPTURE %s ok=%s" % [cid, last.get("ok")])
	# Restore presentation pose after variation burst.
	if john != null and is_instance_valid(john):
		john.position = orig_john_pos
	if cam != null and is_instance_valid(cam):
		cam.offset = orig_cam_offset
		cam.position = orig_cam_pos
		if cam.has_method("reset_smoothing"):
			cam.reset_smoothing()
	await process_frame
	return last


func _capture_once(capture_id: String, phase: String, action: String, should_see: String, variation: int, base_id: String) -> Dictionary:
	_capture_seq += 1
	var auth: Dictionary = _live_authority()
	var world_version := int(auth.get("world_version", 0))
	if variation == 0 and _driver.shell.has_method("reproject_from_python"):
		_driver.shell.reproject_from_python()
		await process_frame
	await process_frame
	var harvest: Dictionary = Harvester.harvest(_driver.shell)
	harvest["ui_overlaps"] = _detect_ui_overlaps()
	harvest["session_id"] = _session_id
	harvest["capture_id"] = capture_id
	harvest["base_capture_id"] = base_id
	harvest["variation"] = variation
	harvest["world_version"] = world_version
	harvest["capture_seq"] = _capture_seq
	_write_json(_out_dir.path_join("authority/%s.json" % capture_id), auth)
	_write_json(_out_dir.path_join("render/%s.json" % capture_id), harvest)
	await process_frame
	var vp: Viewport = get_root().get_viewport()
	var tex: ViewportTexture = vp.get_texture() if vp != null else null
	var img: Image = tex.get_image() if tex != null else null
	var shot_rel := ""
	var err := FAILED
	var w := 0
	var h := 0
	if img != null:
		w = img.get_width()
		h = img.get_height()
		shot_rel = "shots/%s_%dx%d.png" % [capture_id, w, h]
		err = img.save_png(_out_dir.path_join(shot_rel))
	var meta := {
		"capture_id": capture_id,
		"base_capture_id": base_id,
		"variation": variation,
		"checkpoint": phase,
		"action": action,
		"should_be_visible": should_see,
		"session_id": _session_id,
		"world_version": world_version,
		"capture_seq": _capture_seq,
		"image_rel": shot_rel,
		"save_error": err,
		"width": w,
		"height": h,
		"node_backed_count": harvest.get("node_backed_count", 0),
		"scenario_mode": _mode,
		"nudge": [_NUDGES[variation].x, _NUDGES[variation].y] if variation < _NUDGES.size() else [0, 0],
	}
	_write_json(_out_dir.path_join("checkpoints/%s.json" % capture_id), meta)
	var ok := err == OK and w > 0
	meta["ok"] = ok
	return meta


func _live_authority() -> Dictionary:
	if _driver.shell == null or _driver.shell.get("_client") == null:
		return {"error": "no_client", "layer": "authority"}
	var client = _driver.shell._client
	var view_raw = client.request_view("player", [
		"visual_sim_authority", "orders", "battles", "units", "buildings", "formations", "roads", "leases", "clock", "player"
	])
	if typeof(view_raw) != TYPE_DICTIONARY:
		return {"error": "bad_view", "layer": "authority", "view_type": typeof(view_raw)}
	var view: Dictionary = view_raw
	var auth: Dictionary = {}
	if typeof(view.get("visual_sim_authority")) == TYPE_DICTIONARY:
		auth = view["visual_sim_authority"]
	else:
		var player: Dictionary = view["player"] if typeof(view.get("player")) == TYPE_DICTIONARY else {}
		var orders: Dictionary = view["orders"] if typeof(view.get("orders")) == TYPE_DICTIONARY else {}
		var battles: Dictionary = view["battles"] if typeof(view.get("battles")) == TYPE_DICTIONARY else {}
		var units: Dictionary = view["units"] if typeof(view.get("units")) == TYPE_DICTIONARY else {}
		var buildings: Dictionary = view["buildings"] if typeof(view.get("buildings")) == TYPE_DICTIONARY else {}
		var formations: Dictionary = view["formations"] if typeof(view.get("formations")) == TYPE_DICTIONARY else {}
		var roads: Dictionary = view["roads"] if typeof(view.get("roads")) == TYPE_DICTIONARY else {}
		var leases: Dictionary = view["leases"] if typeof(view.get("leases")) == TYPE_DICTIONARY else {}
		var clock: Dictionary = view["clock"] if typeof(view.get("clock")) == TYPE_DICTIONARY else {}
		auth = {
			"layer": "authority",
			"world_id": view.get("world_id", ""),
			"world_version": int(view.get("world_version", 0)),
			"player": player,
			"player_node_id": str(player.get("node_id", "")),
			"clock": clock,
			"orders": orders,
			"battles": battles,
			"units": units,
			"buildings": buildings,
			"formations": formations,
			"roads": roads,
			"leases": leases,
			"counts": {
				"orders": orders.size(),
				"battles": battles.size(),
				"units": units.size(),
				"buildings": buildings.size(),
				"formations": formations.size(),
				"roads": roads.size(),
				"leases": leases.size(),
			},
			"source": "view_fallback",
		}
	auth["session_id"] = _session_id
	auth["sidecar"] = true
	return auth


func _count_field(auth: Dictionary, key: String) -> int:
	var counts = auth.get("counts")
	if typeof(counts) != TYPE_DICTIONARY:
		return 0
	return int(counts.get(key, 0))


func _wait_once(press_id: String) -> void:
	if _driver.shell == null:
		return
	if _driver.shell.has_method("_cmd"):
		var auth: Dictionary = _live_authority()
		var player = auth.get("player")
		var node := "node:35"
		if typeof(player) == TYPE_DICTIONARY:
			node = str(player.get("node_id", node))
		elif auth.get("player_node_id"):
			node = str(auth.get("player_node_id"))
		_driver.shell._cmd("Wait", {"current_node": node, "press_id": press_id})
	elif _driver.shell.has_method("invoke_fx_era_wait_for_test"):
		_driver.shell.invoke_fx_era_wait_for_test()
	await process_frame
	await process_frame


func _advance_seconds(n: int) -> void:
	## AdvanceGame requires clock_sequence == current + 1 or it applies zero quanta.
	if _driver.shell == null or not _driver.shell.has_method("_cmd"):
		return
	if _clock_seq <= 0:
		var auth0: Dictionary = _live_authority()
		var clock0 = auth0.get("clock")
		if typeof(clock0) == TYPE_DICTIONARY:
			_clock_seq = int(clock0.get("clock_sequence", 0))
	for i in range(n):
		_clock_seq += 1
		var reply: Dictionary = _driver.shell._cmd("AdvanceGame", {"delta_ms": 1000, "clock_sequence": _clock_seq})
		if str(reply.get("status", "")) != "ACCEPTED":
			print("VISUAL_SIM_ADVANCE_REJECT seq=%s reply=%s" % [_clock_seq, reply])
			# Resync sequence from live clock and retry once.
			var auth: Dictionary = _live_authority()
			var clock = auth.get("clock")
			if typeof(clock) == TYPE_DICTIONARY:
				_clock_seq = int(clock.get("clock_sequence", _clock_seq))
				_clock_seq += 1
				reply = _driver.shell._cmd("AdvanceGame", {"delta_ms": 1000, "clock_sequence": _clock_seq})
				print("VISUAL_SIM_ADVANCE_RETRY seq=%s status=%s" % [_clock_seq, reply.get("status")])


func _detect_ui_overlaps() -> Array:
	var overlaps: Array = []
	var controls: Array = []
	if _driver.shell == null:
		return overlaps
	if _driver.shell.has_method("fx_era_wait_button"):
		controls.append(_driver.shell.fx_era_wait_button())
	if _driver.shell.get("_time_hud") != null:
		controls.append(_driver.shell._time_hud)
	if _driver.shell.get("_status") != null:
		controls.append(_driver.shell._status)
	var rects: Array = []
	for c in controls:
		if c == null or not is_instance_valid(c) or not (c is Control):
			continue
		var ctrl := c as Control
		if not ctrl.visible:
			continue
		rects.append({"name": str(ctrl.name), "rect": ctrl.get_global_rect()})
	for i in range(rects.size()):
		for j in range(i + 1, rects.size()):
			var a: Rect2 = rects[i]["rect"]
			var b: Rect2 = rects[j]["rect"]
			if a.intersects(b):
				overlaps.append({"a": rects[i]["name"], "b": rects[j]["name"]})
	return overlaps


func _teardown() -> void:
	if _driver == null:
		return
	var shell = _driver.shell
	if shell != null and is_instance_valid(shell):
		if shell.get("_launcher") != null and shell._launcher.has_method("stop"):
			shell._launcher.stop()
		shell.queue_free()
	_driver.shell = null


func _finish(code: int) -> void:
	await process_frame
	quit(code)


func _write_json(path: String, data: Dictionary) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		push_error("cannot write %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()
