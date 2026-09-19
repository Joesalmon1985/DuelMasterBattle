extends RefCounted
class_name SpellbookNonG01Attach

## Mounts Spellbook onto G02/G03 shells that do not extend g01_shell.

const SpellbookModel = preload("res://client/ui/spellbook/spellbook_model.gd")
const SpellbookHost = preload("res://client/ui/spellbook/spellbook_host.gd")
const SpellbookBinder = preload("res://client/ui/spellbook/spellbook_gate_binder.gd")

var model
var host
var binder
var shell
var classic_hud := false
var _action_bar: Control
var _economy_panel: Control


func mount(s, ui_root: Control, session: String, title: String, mode: String) -> void:
	shell = s
	model = SpellbookModel.new()
	binder = SpellbookBinder.new()
	binder.setup(model, session, title)
	if mode == "g02":
		binder.build_g02_pages()
	elif mode == "g03":
		binder.build_g03_pages()
	else:
		binder.build_g01_pages()
	_register_common()
	if mode == "g02":
		binder.register("eco_start", func(_p): return _eco("start"))
		binder.register("eco_block", func(_p): return _eco("place"))
		binder.register("eco_clear", func(_p): return _eco("clear"))
	elif mode == "g03":
		binder.register("ind_damage", func(_p): return _industry("industry_damage"))
		binder.register("ind_strike", func(_p): return _industry("industry_strike"))
		binder.register("ind_clear_strike", func(_p): return _industry("industry_clear_strike"))
		binder.register("ind_repair", func(_p): return _industry("industry_repair"))
		binder.register("ind_path_block", func(_p): return _path_block())
	host = SpellbookHost.new()
	host.name = "SpellbookHost"
	ui_root.add_child(host)
	host.bind_model(model)
	host.action_requested.connect(func(a, p, t): binder.handle_action(a, p, t); sync_live())
	host.exit_menu_requested.connect(func(): shell._on_back())
	host.classic_hud_toggled.connect(_on_classic)
	model.changed.connect(func(): _gate_movement())
	_action_bar = ui_root.get_node_or_null("ActionBarScroll")
	_apply_classic()
	binder.set_ready()
	sync_live()


func _register_common() -> void:
	binder.register("wait", func(_p): return _wait())
	binder.register("invalid_exit", func(_p): return _invalid())
	binder.register("pause", func(_p): shell._on_pause(); sync_live(); return {"status": "OK", "message": shell._prompt.text})
	binder.register("resume", func(_p): shell._on_resume(); sync_live(); return {"status": "OK", "message": shell._prompt.text})
	binder.register("save", func(_p): shell._on_save(); sync_live(); return {"status": "OK", "message": shell._prompt.text})
	binder.register("load", func(_p): shell._on_load(); sync_live(); return {"status": "OK", "message": shell._prompt.text})
	binder.register("bridge_fail", func(_p): shell._on_bridge_fail(); sync_live(); return {"status": "OK", "message": shell._prompt.text})
	binder.register("toggle_diag", func(_p): shell._toggle_diag(); return {"status": "OK", "message": "Dev panel toggled"})


func sync_live() -> void:
	if binder == null or shell == null:
		return
	binder.sync_live(
		str(shell._status.text) if shell._status else "",
		str(shell._counters.text) if shell._counters else "",
		str(shell._prompt.text) if shell._prompt else "",
		bool(shell._paused) or bool(shell._bridge_down)
	)


func append_log(line: String) -> void:
	if binder:
		binder.append_log(line)


func _on_classic(enabled: bool) -> void:
	classic_hud = enabled
	_apply_classic()


func _apply_classic() -> void:
	if _action_bar:
		_action_bar.visible = classic_hud
	if shell.get("_economy") != null:
		# Keep inspectors available; collapse not required.
		pass


func _gate_movement() -> void:
	if host == null or not shell.has_method("_apply_movement_gate"):
		return
	# Re-run shell gate; shells should also consult host.is_blocking_world if patched.
	shell._apply_movement_gate()


func _wait() -> Dictionary:
	if bool(shell._wait_held):
		shell._prompt.text = "Hold ignored — one Wait per distinct press"
		sync_live()
		return {"status": "REJECTED", "message": shell._prompt.text}
	shell._wait_held = true
	var node := "node:1"
	if shell._client != null and shell._client.has_player_cache():
		node = str(shell._client.cached_player_view().get("player", {}).get("node_id", node))
	var reply: Dictionary = shell._cmd("Wait", {"current_node": node, "press_id": "wait-%s" % Time.get_ticks_msec()})
	shell._prompt.text = "Wait accepted — World Turn +1"
	sync_live()
	shell.get_tree().create_timer(0.4).timeout.connect(func(): shell._wait_held = false)
	return {"status": reply.get("status", "OK"), "message": shell._prompt.text}


func _invalid() -> Dictionary:
	var node := "node:1"
	if shell._client != null and shell._client.has_player_cache():
		node = str(shell._client.cached_player_view().get("player", {}).get("node_id", node))
	var reply: Dictionary = shell._cmd("Travel", {"from_node": node, "to_node": "node:99"})
	if str(reply.get("status", "")) == "REJECTED":
		shell._prompt.text = "Invalid travel rejected — node/turn unchanged"
	sync_live()
	return {"status": reply.get("status", "?"), "message": shell._prompt.text}


func _eco(mode: String) -> Dictionary:
	shell._on_clear_route(mode)
	sync_live()
	return {"status": "OK", "message": shell._prompt.text}


func _industry(action: String) -> Dictionary:
	shell._on_industry_action(action)
	sync_live()
	return {"status": "OK", "message": shell._prompt.text}


func _path_block() -> Dictionary:
	if shell.has_method("_toggle_path"):
		shell._toggle_path()
	elif shell.get("_economy") != null and shell._economy.has_signal("worker_path_toggled"):
		pass
	sync_live()
	return {"status": "OK", "message": "Path block toggled (presentation-only)"}
