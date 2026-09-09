extends SceneTree

## Headed screenshot capture for the adventure. Run WITHOUT --headless:
##   godot --path godot_project --resolution 720x1280 --script res://client/tools/capture_adventure_qa.gd -- --screenshot-mode
## Writes qa/screenshots/adventure/*.png

var _out_dir: String
var _world
var _adv


func _init() -> void:
	var root_path := ProjectSettings.globalize_path("res://..")
	_out_dir = root_path + "/qa/screenshots/adventure"
	DirAccess.make_dir_recursive_absolute(_out_dir)
	call_deferred("_run")


func _run() -> void:
	await process_frame
	_ensure_autoloads()
	_adv = root.get_node("Adventure")
	await process_frame

	# 01 main menu (no save) / 02 with save
	_adv.delete_save()
	var menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await _frames(4)
	_capture("01_menu_no_save.png")
	_adv.new_game()
	_adv.learn_spell(1)
	_adv.grow_weave(1)
	_adv.save()
	menu.queue_free()
	await process_frame
	menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await _frames(4)
	_capture("02_menu_with_save.png")
	menu.ui_new_game()
	await _frames(3)
	_capture("03_overwrite_warning.png")
	menu.queue_free()
	await process_frame

	# 04 opening
	_adv.new_game()
	await _new_world()
	await _frames(20)
	_capture("04_opening_text.png")
	_world.ui_dialogue_advance()
	await _frames(2)
	_world.ui_dialogue_advance()
	await _frames(2)
	_world.ui_dialogue_advance()
	await _frames(2)
	_world.ui_dialogue_advance()
	await _frames(20)
	_capture("05_village_free_roam.png")

	# 06 duel aftermath: staff waiting on the road (skip the cutscene via flags)
	await _free_world()
	_adv.set_flag("opening_seen")
	_adv.set_flag("duel_seen")
	_adv.learn_spell(1)
	_adv.grow_weave(1)
	_adv.set_location("village", 10, 9, "up")
	await _new_world()
	await _frames(20)
	_capture("06_duel_aftermath_staff.png")

	# 07 dialogue box
	_world.ui_action()
	await _frames(40)
	_capture("07_pickup_dialogue.png")
	await _drain()
	await _frames(5)
	_capture("08_hud_with_water_magic.png")

	# 09 burnt wood training detour
	await _free_world()
	_adv.set_location("forest_deep", 8, 16, "up")
	await _new_world()
	await _frames(20)
	_capture("09_burnt_wood.png")

	# 10 encounter intro dialogue (imp, facing it)
	await _free_world()
	_adv.set_location("forest_deep", 10, 16, "up")
	await _new_world()
	await _frames(10)
	_world.ui_action()
	await _frames(40)
	_capture("10_encounter_intro.png")
	await _drain()

	# 11 Ashwell vista
	await _free_world()
	_adv.set_location("village", 10, 7, "down")
	await _new_world()
	await _frames(20)
	_capture("11_village.png")
	_world.ui_action()
	await _frames(2)


	# 11b trial road vista
	await _drain()
	await _free_world()
	_adv.set_location("trial_road", 10, 7, "down")
	await _new_world()
	await _frames(20)
	_capture("11b_trial_road.png")


	# 11c trial gate roster
	await _free_world()
	_adv.set_location("trial_gate", 9, 6, "up")
	await _new_world()
	await _frames(20)
	_capture("11c_trial_gate.png")


	# 11d crystal entrance (fresh run state for run-scoped entities)
	await _free_world()
	_adv.start_run()
	await _new_world()
	await _frames(20)
	_capture("11d_crystal_entrance.png")


	# 11e Throm's pit
	await _free_world()
	_adv.set_location("dd_pit", 9, 8, "left")
	await _new_world()
	await _frames(20)
	_capture("11e_throm_pit.png")


	# 11f lower route books alcove
	await _free_world()
	_adv.set_location("dd_lower", 8, 5, "left")
	await _new_world()
	await _frames(20)
	_capture("11f_lower_books.png")


	# 12 pause menu (fresh world for the menu)
	await _free_world()
	_adv.set_location("village", 10, 7, "down")
	await _new_world()
	await _frames(10)
	_world._on_menu()
	await _frames(10)
	_capture("12_pause_menu.png")
	await _free_world()

	# 13-16 battle screens: 2 vs 1 (wrap), 2 vs 4 (outmatched), encounter intro
	await _battle_shots()
	quit(0)


func _battle_shots() -> void:
	_adv.progression = load("res://sim/progression.gd").new()
	_adv.progression.learn_spell(1)
	_adv.progression.learn_spell(0)
	_adv.progression.grow_weave(2)
	_adv.request_battle({"enemy_id": "steam_sprite", "encounter_id": "qa", "kind": "creature"})
	var board = load("res://client/scenes/game_board.tscn").instantiate()
	root.add_child(board)
	await _frames(4)
	_capture("13_battle_intro_steam_sprite.png")
	board.ui_dismiss_overlay()
	await _frames(2)
	_capture("14_battle_ward_setup_2slots.png")
	board.ui_action_pick_spell(1)
	board.ui_action_pick_spell(0)
	board.ui_action_lock_ward()
	await _frames(2)
	board.game.advance_time_for_test(5.5)
	board.ui_action_pick_spell(1)
	board.ui_action_pick_spell(0)
	await _frames(3)
	_capture("15_battle_2v1_wrap_labels.png")
	board.ui_action_cast()
	await _frames(30)
	_capture("16_battle_2v1_after_cast.png")
	board.queue_free()
	await process_frame
	# Outmatched: 2 weave vs Red wizard 4 ward
	_adv.request_battle({"enemy_id": "red_wizard", "encounter_id": "qa2", "kind": "wizard"})
	board = load("res://client/scenes/game_board.tscn").instantiate()
	root.add_child(board)
	await _frames(4)
	board.ui_dismiss_overlay()
	board.ui_action_pick_spell(1)
	board.ui_action_pick_spell(0)
	board.ui_action_lock_ward()
	await _frames(2)
	board.game.advance_time_for_test(5.5)
	board.ui_action_pick_spell(1)
	board.ui_action_pick_spell(0)
	await _frames(3)
	_capture("17_battle_outmatched_2v4.png")
	board.queue_free()
	await process_frame
	# 1v1 wisp
	_adv.progression = load("res://sim/progression.gd").new()
	_adv.progression.learn_spell(1)
	_adv.progression.grow_weave(1)
	_adv.request_battle({"enemy_id": "flame_wisp", "encounter_id": "qa3", "kind": "creature"})
	board = load("res://client/scenes/game_board.tscn").instantiate()
	root.add_child(board)
	await _frames(4)
	board.ui_dismiss_overlay()
	await _frames(2)
	_capture("18_battle_1v1_wisp_setup.png")
	board.ui_action_pick_spell(1)
	board.ui_action_lock_ward()
	board.game.advance_time_for_test(5.5)
	board.ui_action_pick_spell(1)
	await _frames(3)
	_capture("19_battle_1v1_ready.png")
	board.ui_action_cast()
	await _frames(40)
	_capture("20_battle_1v1_victory.png")
	board.queue_free()
	_adv.clear_pending_battle()


func _new_world() -> void:
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	await _frames(2)


func _free_world() -> void:
	if _world and is_instance_valid(_world):
		_world.queue_free()
		_world = null
		await process_frame


func _drain() -> void:
	var guard := 0
	while guard < 2000:
		guard += 1
		await process_frame
		if _world.ui_dialogue_open():
			if _world.ui_dialogue_waiting_choice():
				_world.ui_dialogue_choose("Not yet")
				await process_frame
				continue
			_world.ui_dialogue_advance()
			await process_frame
			_world.ui_dialogue_advance()
			await process_frame
		elif not _world.ui_input_locked():
			return


func _frames(n: int) -> void:
	for i in range(n):
		await process_frame


func _ensure_autoloads() -> void:
	for pair in [["EncounterSession", "res://client/scripts/encounter_session.gd"], ["Sfx", "res://client/scripts/sfx.gd"], ["Adventure", "res://client/scripts/adventure.gd"]]:
		if root.get_node_or_null(pair[0]) == null:
			var n = load(pair[1]).new()
			n.name = pair[0]
			root.add_child(n)


func _capture(file: String) -> void:
	var img: Image = root.get_viewport().get_texture().get_image()
	img.save_png(_out_dir + "/" + file)
	print("shot ", file)
