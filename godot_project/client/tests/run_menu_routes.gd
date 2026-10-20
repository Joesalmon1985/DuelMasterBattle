extends SceneTree

## The player-facing menu is Wizard World and nothing else: four entries, no legacy adventure, no Quick Duel, no G01 testing entry; the three play entries
## route into the one Wizard World implementation (single player = a private hosted session, multiplayer = host / join); the old adventure's save is never
## consulted; the developer menu still exists but is not reachable from the normal menu.
## Prints MENU_ROUTES_OK or MENU_ROUTES_FAIL <why>.

const SHOT_DIR_ENV := "HYBRID_SHOT_DIR"
const BANNED := ["new game", "resume", "quick duel", "g01", "fx-clock", "ashwell", "trial day", "adventure", "village test", "puzzle test"]
var _failed := false


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	print("MENU_ROUTES_FAIL %s" % msg)
	_failed = true


func _texts(node: Node, out: Array) -> void:
	if node is Button:
		out.append((node as Button).text)
	elif node is Label:
		out.append((node as Label).text)
	for c in node.get_children():
		_texts(c, out)


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(720, 1280))
	var lan: Node = root.get_node("LanSession")
	# an old adventure save on disk must not matter: it is the file the legacy menu's RESUME read
	var adv: Node = root.get_node("Adventure")
	var wrote_legacy := false
	if not FileAccess.file_exists(adv.SAVE_PATH):
		var f := FileAccess.open(adv.SAVE_PATH, FileAccess.WRITE)
		f.store_string(JSON.stringify({"state": {"version": 4, "area": "ashwell", "pos": [3, 3], "story": {"phase": "halvard_prologue"}}, "progression": {}}))
		f.close()
		wrote_legacy = true
	var menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	for _i in 4:
		await process_frame
	var entries: Array = menu.ui_visible_entries()
	if entries != ["Play Single Player", "Host Multiplayer", "Join Multiplayer", "Settings"]:
		_fail("entries are %s" % str(entries))
	var texts: Array = []
	_texts(menu, texts)
	for t in texts:
		for banned in BANNED:
			if str(t).to_lower().find(banned) >= 0:
				_fail("the menu shows '%s'" % t)
	# the developer menu is a separate scene, off in a normal run
	if menu.dev_btn != null:
		_fail("developer tools are visible without DMB_DEV_MENU")
	var shot_dir := OS.get_environment(SHOT_DIR_ENV)
	if shot_dir != "":
		DirAccess.make_dir_recursive_absolute(shot_dir)
		await process_frame
		root.get_viewport().get_texture().get_image().save_png(shot_dir.path_join("main_menu_wizard_world.png"))
	if wrote_legacy:
		DirAccess.remove_absolute(ProjectSettings.globalize_path(adv.SAVE_PATH))
	# single player: a private session of the one Wizard World (a new campaign here; continue when a save exists)
	menu._begin_single(false)
	if lan.mode != "host" or not lan.private_session or lan.continue_game:
		_fail("single player flags: mode=%s private=%s continue=%s" % [lan.mode, str(lan.private_session), str(lan.continue_game)])
	for _i in 3:
		await process_frame
	if current_scene == null or current_scene.scene_file_path != "res://client/scenes/lan_menu.tscn":
		_fail("single player did not go to the Wizard World launcher: %s" % (current_scene.scene_file_path if current_scene != null else "none"))
	menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await process_frame
	menu._begin_single(true)
	if not lan.continue_game or not lan.private_session:
		_fail("continue did not set the continue flag")
	menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await process_frame
	menu.ui_press_host()
	if lan.mode != "host" or lan.private_session or lan.continue_game:
		_fail("host flags: mode=%s private=%s" % [lan.mode, str(lan.private_session)])
	menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await process_frame
	menu.ui_press_join()
	if lan.mode != "join" or lan.private_session:
		_fail("join flags: mode=%s private=%s" % [lan.mode, str(lan.private_session)])
	# settings opens in place
	menu = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(menu)
	await process_frame
	menu.ui_show_settings()
	if not menu.ui_overlay_visible():
		_fail("settings did not open")
	# the developer menu still holds the legacy entries (kept, not deleted) for developer launchers
	var dev = load("res://client/scenes/dev_menu.tscn").instantiate()
	root.add_child(dev)
	await process_frame
	var dev_texts: Array = []
	_texts(dev, dev_texts)
	if not (dev_texts.has("NEW GAME") and dev_texts.has("Quick Duel  (4-slot wizard match)")):
		_fail("the developer menu lost the legacy entries")
	# the village of games (docs/PLAN_VILLAGE_MINIGAMES.md) is a developer entry: a private, fresh session on its own saves folder, never the player's
	if dev.find_child("GamesVillageButton", true, false) == null:
		_fail("the developer menu has no games village entry")
	var runs_before: String = lan.runs_dir()
	dev._on_games_village()
	if lan.mode != "host" or not lan.private_session or not lan.fresh_world or not lan.games_village:
		_fail("games village flags: mode=%s private=%s fresh=%s games=%s" % [lan.mode, str(lan.private_session), str(lan.fresh_world), str(lan.games_village)])
	if lan.runs_dir() == runs_before or not lan.runs_dir().ends_with("games_village"):
		_fail("the games village must keep its saves apart from the player's world (runs_dir=%s)" % lan.runs_dir())
	lan.reset()
	if lan.games_village or lan.runs_dir() != runs_before:
		_fail("reset did not clear the games village flag")
	# nothing that a normal run can reach names the old adventure scenes from the player menu script
	var src := FileAccess.get_file_as_string("res://client/scripts/main_menu.gd")
	for needle in ["overworld.tscn", "game_board.tscn", "g01_shell", "Adventure"]:
		if src.find(needle) >= 0:
			_fail("main_menu.gd references %s" % needle)
	lan.reset()
	if _failed:
		quit(1)
		return
	print("MENU_ROUTES_OK")
	quit(0)
