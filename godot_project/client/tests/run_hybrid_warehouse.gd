extends SceneTree

## Headed acceptance for the village (plan M4, scenario C), against the classic single-process server in the campaign profile: the rats are drawn
## at the real warehouse with the imported Mindustry sprites, the keeper complains and calls them rats, a rat's inspect card offers "Drive it off",
## the duel is fought on the REAL board, a win breaks the rat (one fewer on screen), the warehouse's food stock has been nibbled, and after the last
## rat the keeper thanks the apprentice. Prints HYBRID_WAREHOUSE_OK or HYBRID_WAREHOUSE_FAIL <reasons>.

var _world: Node
var _ui: Node
var _fails: Array = []
var _seq := 0
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("WAREHOUSE %s: %s" % ["ok" if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _shot(name: String) -> void:
	if _dir == "":
		return
	await _frames(3)
	DirAccess.make_dir_recursive_absolute(_dir)
	root.get_viewport().get_texture().get_image().save_png(_dir.path_join(name + ".png"))


func _wait_until(cond: Callable, seconds := 10.0) -> bool:
	var deadline := Time.get_ticks_msec() + int(seconds * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if cond.call():
			return true
		await process_frame
	return cond.call()


func _sim_advance(seconds: int) -> void:
	var left := seconds
	while left > 0:
		var chunk := mini(left, 5)
		left -= chunk
		_seq = int(_world._snapshot.get("clock_sequence", _seq)) + 1
		var reply: Dictionary = _world._sim.op({"op": "advance", "ms": chunk * 1000, "sequence": _seq, "tree_delta": true})
		if str(reply.get("status", "")) == "ok":
			_world._apply_snapshot(reply.get("snapshot", {}))
	await _frames(2)


func _find_all(pred: Callable) -> Array:
	var out: Array = []
	for e in _world._snapshot.get("entities", []):
		if typeof(e) == TYPE_DICTIONARY and pred.call(e):
			out.append(e)
	return out


func _find(pred: Callable) -> Dictionary:
	var all := _find_all(pred)
	return all[0] if not all.is_empty() else {}


func _stand_by(e: Dictionary) -> bool:
	for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1), Vector2i(2, 0), Vector2i(0, 2), Vector2i(-2, 0), Vector2i(0, -2)]:
		var t: Vector2i = Vector2i(int(e["tx"]), int(e["ty"])) + (d as Vector2i)
		if _world.is_walkable(t):
			_world.set_john_pos(t)
			_world._arrived()
			await _frames(3)
			return true
	return false


func _refresh() -> void:
	_world._apply_snapshot(_world._sim.op({"op": "snapshot"}).get("snapshot", {}))
	await _frames(2)


func _set_ward(board: Node, ward: Array) -> bool:
	for sp in ward:
		if not board.ui_pointer_press_tray_spell(int(sp)):
			return false
		await _frames(2)
	if not board.ui_pointer_press_lock_ward():
		return false
	await _frames(3)
	return true


func _cast(board: Node, pattern: Array) -> void:
	for i in pattern.size():
		board.ui_action_select_locus(i)
		board.ui_pointer_press_tray_spell(int(pattern[i]))
		await _frames(1)
	board.ui_action_cast()
	await _frames(2)
	board.ui_advance_time(6.5)
	await _frames(3)


## A careful fight: the rat's Ward is two colours deep (Frost and Vine), so the candidates are few.
func _fight(board: Node, pool: Array) -> int:
	board.ui_set_fast_cast(true)
	await _set_ward(board, [0, 1, 6])
	var candidates: Array = []
	for a in pool:
		for b in pool:
			for c in pool:
				candidates.append([a, b, c])
	var guesses := 0
	while guesses < 8 and not board.game.result and not candidates.is_empty():
		var attack: Array = candidates[0]
		await _cast(board, attack)
		guesses += 1
		if board.game.player_history.size() < guesses:
			continue
		var rec = board.game.player_history[guesses - 1]
		var kept: Array = []
		for cand in candidates:
			var r: Dictionary = DmbFeedback.score_attack(cand, attack)
			if int(r["fracture"]) == int(rec.fracture_count) and int(r["echo"]) == int(rec.echo_count):
				kept.append(cand)
		candidates = kept
	return guesses


func _board() -> Node:
	return _world._adapter._board


func _drive_off(pest: Dictionary) -> String:
	"""Open the rat's inspect card, press Drive it off, fight on the board, press Continue. Returns the board's outcome."""
	await _stand_by(pest)
	_world.wizard_labels.open(str(pest["id"]))
	await _frames(5)
	if not _world.wizard_labels.panel.visible:
		return "no_card"
	if not _world.wizard_labels.panel.activate_choice_id("pest"):
		return "no_action"
	if not await _wait_until(func(): return _world._duel_open and _board() != null and is_instance_valid(_board()), 6.0):
		return "no_board"
	var board := _board()
	var pool: Array = [1, 6] if str(pest.get("pest", {}).get("size", "")) == "small" else [0, 1, 6]
	await _fight(board, pool)
	if board.game.result == null:
		return "unfinished"
	var outcome := str(board.game.result.outcome)
	if not await _wait_until(func(): return board.ui_is_result_visible(), 8.0):
		return "no_result"
	board.ui_pointer_press_overlay_button("Continue")
	await _frames(10)
	await _refresh()
	return outcome


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(450, 800))
	await _frames(40)
	_ui = _world.story_ui
	_ui.finish_opening()
	await _frames(5)
	_world.paused = true
	await _sim_advance(2)
	# 1. the rats are at the real warehouse, drawn, with the keeper beside them
	var warehouse := _find(func(e): return str(e.get("kind", "")) == "warehouse" and str(e.get("faction_name", "")) == "Red")
	_check(not warehouse.is_empty(), "the Red warehouse exists")
	var rats := _find_all(func(e): return str(e.get("class", "")) == "npc" and e.has("pest"))
	_check(rats.size() == 5, "five rats are on screen (%d)" % rats.size())
	var near := 0
	for r in rats:
		if maxi(absi(int(r["tx"]) - int(warehouse.get("tx", 0))), absi(int(r["ty"]) - int(warehouse.get("ty", 0)))) <= 4:
			near += 1
	_check(near == rats.size(), "all of them beside the warehouse (%d of %d)" % [near, rats.size()])
	_check(rats.any(func(r): return str(r.get("figure", "")) == "pest:dagger") and rats.any(func(r): return str(r.get("figure", "")) == "pest:crawler"), "a big one (dagger) and small ones (crawlers)")
	var keeper := _find(func(e): return str(e.get("class", "")) == "npc" and str(e.get("role", "")) == "keeper")
	_check(not keeper.is_empty(), "the keeper stands by the store")
	_world.camera_focus = Vector2((float(warehouse.get("tx", 0)) + 0.5) * float(_world.TPX), (float(warehouse.get("ty", 0)) + 0.5) * float(_world.TPX))
	await _stand_by(rats[1])
	await _frames(10)
	await _shot("w01_rats_at_warehouse")
	# the inspect card describes a machine the keeper calls a rat
	_world.wizard_labels.open(str(rats[1]["id"]))
	await _frames(5)
	_check(_world.wizard_labels.panel.visible and _world.wizard_labels.panel.subtitle_label.text.contains("rat"), "the rat's card: what the villagers call a rat")
	_check(_world.wizard_labels.panel.choice_button("pest") != null, "it offers Drive it off")
	await _shot("w02_rat_card")
	_world.wizard_labels.close()
	# 2. the keeper complains, and insists they are rats
	await _stand_by(keeper)
	var reply: Dictionary = _world._sim.op({"op": "talk", "npc": str(keeper["id"])})
	_check(str(reply.get("status", "")) == "ok" and " ".join(PackedStringArray(reply.get("lines", []))).contains("Rats"), "the keeper complains about rats")
	await _refresh()  # the snapshot now lists the conversation, so the card is not closed as stale
	_ui.show_follow_up(reply)
	await _frames(5)
	await _shot("w03_keeper_complaint")
	_check(_ui.dialog_card.activate_choice_id("what_matter"), "ask what the matter is")
	await _frames(5)
	_check(_ui.dialog_text.text.contains("Stand close to one"), "the keeper says how to deal with them")
	print("WAREHOUSE choices after the complaint: %s" % str(_ui.dialog_card.choice_ids()))
	_check(_ui.dialog_card.activate_choice_id("not_rats"), "say they are machines")
	await _frames(5)
	_check(_ui.dialog_text.text.contains("I know a rat"), "the keeper insists: rats")
	_ui.close_dialog()
	await _frames(5)
	# 3. the food stock shrinks while they are about
	var stock_before: int = int(_world._sim.op({"op": "snapshot"}).get("snapshot", {}).get("stocks", {}).get(str(warehouse["id"]), {}).get("ration", 0))
	_world.paused = false
	await _sim_advance(70)
	_world.paused = true
	var stock_after: int = int(_world._sim.op({"op": "snapshot"}).get("snapshot", {}).get("stocks", {}).get(str(warehouse["id"]), {}).get("ration", 0))
	_check(stock_after < stock_before, "rations are being eaten (%d -> %d)" % [stock_before, stock_after])
	# 4. fight the rats on the real board until the warehouse is clear (a careful fight is usually, not always, won)
	var fights := 0
	var wins := 0
	var left := _find_all(func(e): return str(e.get("class", "")) == "npc" and e.has("pest"))
	var first_shot := false
	while left.size() > 0 and fights < 14:
		var outcome := await _drive_off(left[0])
		fights += 1
		if outcome == "victory":
			wins += 1
		if not first_shot:
			first_shot = true
			await _shot("w04_after_first_fight")
		var now_left := _find_all(func(e): return str(e.get("class", "")) == "npc" and e.has("pest"))
		if outcome == "victory":
			_check(now_left.size() == left.size() - 1, "a won duel breaks the rat: %d left" % now_left.size())
		elif outcome in ["defeat", "stalemate"]:
			_check(now_left.size() == left.size(), "a lost duel leaves the rat (it scurries off)")
		else:
			_check(false, "fight failed: %s" % outcome)
			break
		left = now_left
	_check(left.is_empty(), "the warehouse is clear after %d fights (%d won)" % [fights, wins])
	await _shot("w05_warehouse_clear")
	# 5. the keeper reacts
	await _sim_advance(2)
	keeper = _find(func(e): return str(e.get("class", "")) == "npc" and str(e.get("role", "")) == "keeper")
	await _stand_by(keeper)
	reply = _world._sim.op({"op": "talk", "npc": str(keeper["id"])})
	var thanks := " ".join(PackedStringArray(reply.get("lines", [])))
	_check(thanks.contains("by you") or thanks.contains("last of them"), "the keeper thanks the apprentice who did it: %s" % thanks.substr(0, 60))
	await _refresh()
	_ui.show_follow_up(reply)
	await _frames(5)
	await _shot("w06_keeper_thanks")
	_ui.close_dialog()
	if _fails.is_empty():
		print("HYBRID_WAREHOUSE_OK")
		quit(0)
	else:
		print("HYBRID_WAREHOUSE_FAIL ", ", ".join(_fails))
		quit(1)
