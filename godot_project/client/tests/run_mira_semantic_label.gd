extends SceneTree

## Mira must use WorldInteractionLabel like Bram/Greta/Mara — FX + Ashwell paths.
## godot --headless --path godot_project --script res://client/tests/run_mira_semantic_label.gd

const G01Shell = preload("res://client/scenes/g01_shell.gd")
const WIL = preload("res://client/world/world_interaction_label.gd")

var _failures: Array = []


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	for pair in [["EncounterSession", "res://client/scripts/encounter_session.gd"], ["Sfx", "res://client/scripts/sfx.gd"], ["Adventure", "res://client/scripts/adventure.gd"]]:
		if root.get_node_or_null(pair[0]) == null:
			var n = load(pair[1]).new()
			n.name = pair[0]
			root.add_child(n)
	await _test_ashwell_mira()
	await _test_fx_mira()
	if _failures.is_empty():
		print("MIRA_SEMANTIC_OK")
		quit(0)
	else:
		for f in _failures:
			push_error(str(f))
		print("MIRA_SEMANTIC_FAIL count=", _failures.size())
		quit(1)


func _assert(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func _test_ashwell_mira() -> void:
	var adv = root.get_node("Adventure")
	adv.delete_save()
	adv.new_game()
	await process_frame
	var world = load("res://client/scenes/overworld.tscn").instantiate()
	world.test_mode = true
	root.add_child(world)
	for _i in 20:
		await process_frame
	var by_name := {}
	for raw in world.ui_semantic_labels():
		by_name[str(raw.get("text", ""))] = raw
	_assert(by_name.has("Mira"), "Ashwell Mira WorldInteractionLabel missing")
	_assert(by_name.has("Bram"), "Bram label missing")
	_assert(by_name.has("Greta"), "Greta label missing")
	_assert(by_name.has("Mara"), "Mara label missing")
	if by_name.has("Mira"):
		_assert(str(by_name["Mira"].get("state", "")) == "LABEL", "Mira should start in LABEL")
		var mira = world.ui_semantic_label(str(by_name["Mira"].get("key", "")))
		_assert(mira != null, "Mira label node missing")
		if mira != null:
			var bram = world.ui_semantic_label(str(by_name["Bram"].get("key", "")))
			_assert(bram != null and mira.get_script() == bram.get_script(), "Mira script must match Bram")
			var anchor = mira._anchor if "_anchor" in mira else null
			if anchor != null:
				var fb = anchor.get_node_or_null("fallback_label")
				_assert(fb == null or not fb.visible, "Mira fallback_label must be hidden")
			if mira.has_method("begin_speech"):
				mira.begin_speech(["The hill road is north."], ["Thanks."])
				await process_frame
				var st := str(mira.interaction_state())
				_assert(st == "SPEECH" or st == "RESPONSES", "Mira speech state got %s" % st)
			if mira.has_method("tracked_world_position") and mira._anchor != null:
				var before: Vector2 = mira.tracked_world_position()
				mira._anchor.position += Vector2(16, 0)
				await process_frame
				_assert(mira.tracked_world_position().x > before.x, "Mira label must follow sprite")
	print("MIRA_ASHWELL_SEMANTIC_OK")
	world.queue_free()
	await process_frame


func _test_fx_mira() -> void:
	OS.set_environment("DMB_FIXTURE", "")
	OS.set_environment("DMB_SEED", "7")
	var shell: Control = G01Shell.new()
	root.add_child(shell)
	await create_timer(2.0).timeout
	_assert(shell._client != null and shell._area != null, "G01 shell failed")
	if shell._client == null:
		return
	var people: Dictionary = shell._client.request_view("player").get("people", {})
	var mira_id := ""
	for pid in people.keys():
		var info: Dictionary = people[pid]
		if str(info.get("role", "")) == "guide" or str(info.get("name", "")) == "Mira":
			mira_id = str(pid)
			break
	if mira_id == "" and people.size() == 1:
		mira_id = str(people.keys()[0])
	_assert(mira_id != "", "FX Mira person missing")
	shell._on_people_presentation_changed(people)
	await process_frame
	_assert(shell._people_presenter != null, "G01 people presenter missing")
	var fx_lbl = shell._people_presenter.label_for(mira_id) if shell._people_presenter else null
	_assert(fx_lbl != null, "FX Mira WorldInteractionLabel missing")
	_assert(fx_lbl != null and fx_lbl.get_script() == WIL, "FX Mira must use WorldInteractionLabel script")
	shell._on_observe(mira_id)
	await create_timer(0.2).timeout
	shell._on_interact(mira_id)
	await create_timer(0.25).timeout
	fx_lbl = shell._people_presenter.label_for(mira_id)
	var view: Dictionary = fx_lbl.bridge_view() if fx_lbl != null and fx_lbl.has_method("bridge_view") else {}
	var shown := str(fx_lbl.display_text()) if fx_lbl != null and fx_lbl.has_method("display_text") else ""
	_assert(str(view.get("name", "")) == "Mira" or shown.find("Mira") >= 0, "FX label did not resolve to Mira")
	var spr = shell._area.selectable_actor(mira_id)
	if spr != null:
		var fallback = spr.get_node_or_null("fallback_label")
		_assert(fallback == null or not fallback.visible, "FX fallback_label still visible")
	print("MIRA_FX_SEMANTIC_OK id=", mira_id)
	shell.queue_free()
	await process_frame
