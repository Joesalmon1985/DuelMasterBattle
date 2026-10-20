extends Control

## Local Wi-Fi play: Host (this device runs the authoritative world and plays), Join (find or type a host), Lobby.
## Everything is touch-sized. The world scene is entered when the host starts the session.

const _VT = preload("res://client/scripts/visual_theme.gd")
const _Discovery = preload("res://client/net/lan_discovery.gd")

var page := "home"
var _root: VBoxContainer
var _status_lbl: Label
var _discovery = null
var _probe_acc := 0.0
var _lobby_acc := 0.0
var _host_acc := 0.0
var _hosting_started := false
var _entering_world := false
var _lobby_state := ""
var _name_edit: LineEdit
var _session_edit: LineEdit
var _code_edit: LineEdit
var _join_code_edit: LineEdit
var _join_name_edit: LineEdit
var _ip_edit: LineEdit
var _port_edit: LineEdit
var _map_btn: OptionButton
var _host_list: VBoxContainer
var _lobby_players: VBoxContainer
var _lobby_title: Label
var _lobby_info: Label
var _start_btn: Button
var _host_go_btn: Button
var _join_go_btn: Button
var _busy := false
var last_hosts: Array = []


func _ready() -> void:
	_build_background()
	_root = VBoxContainer.new()
	_root.add_theme_constant_override("separation", 14)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right"]:
		margin.add_theme_constant_override("margin_" + side, 24)
	margin.add_theme_constant_override("margin_top", 40)
	margin.add_theme_constant_override("margin_bottom", 24)
	add_child(margin)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroll)
	_root.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_root)
	match LanSession.mode:
		"host":
			show_page("private" if LanSession.private_session else "host")
		"join":
			show_page("join")
		_:
			show_page("home")


func _build_background() -> void:
	var bg := ColorRect.new()
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = _VT.COLOR_BG_DEEP
	add_child(bg)
	var pano := TextureRect.new()
	pano.set_anchors_preset(Control.PRESET_FULL_RECT)
	if ResourceLoader.exists("res://assets/pixel/backdrops/title_panorama.png"):
		pano.texture = load("res://assets/pixel/backdrops/title_panorama.png")
	pano.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	pano.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	pano.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	pano.mouse_filter = Control.MOUSE_FILTER_IGNORE
	pano.modulate = Color(0.6, 0.6, 0.7)
	add_child(pano)


# ---------------------------------------------------------------- page building

func _clear() -> void:
	for c in _root.get_children():
		_root.remove_child(c)
		c.queue_free()


func _title(text: String) -> void:
	var t := Label.new()
	t.text = text
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t.add_theme_font_size_override("font_size", 44)
	t.add_theme_color_override("font_color", _VT.COLOR_ACCENT_GOLD)
	t.add_theme_color_override("font_outline_color", Color(0.05, 0.03, 0.08))
	t.add_theme_constant_override("outline_size", 8)
	_root.add_child(t)


func _text(text: String, secondary: bool = true) -> Label:
	var l := Label.new()
	l.text = text
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	if secondary:
		_VT.apply_label_secondary(l)
	else:
		_VT.apply_label_primary(l)
	l.add_theme_font_size_override("font_size", 22)
	_root.add_child(l)
	return l


func _button(text: String, primary: bool, cb: Callable, height: int = 72) -> Button:
	var b := Button.new()
	b.text = text
	b.name = "Btn_" + text.replace(" ", "_")
	b.custom_minimum_size = Vector2(0, height)
	if primary:
		_VT.style_primary_button(b)
		b.add_theme_font_size_override("font_size", 28)
	else:
		_VT.style_secondary_button(b)
		b.add_theme_font_size_override("font_size", 24)
	b.pressed.connect(cb)
	_root.add_child(b)
	return b


func _field(label: String, value: String, numeric: bool = false, placeholder: String = "") -> LineEdit:
	var l := Label.new()
	l.text = label
	_VT.apply_label_secondary(l)
	l.add_theme_font_size_override("font_size", 20)
	_root.add_child(l)
	var e := LineEdit.new()
	e.text = value
	e.placeholder_text = placeholder
	e.custom_minimum_size = Vector2(0, 64)
	e.add_theme_font_size_override("font_size", 28)
	if numeric:
		e.virtual_keyboard_type = LineEdit.KEYBOARD_TYPE_NUMBER
	_root.add_child(e)
	return e


func _panel() -> VBoxContainer:
	var p := PanelContainer.new()
	p.add_theme_stylebox_override("panel", _VT.flat_panel_style(Color(0.08, 0.06, 0.14, 0.9), 16))
	_root.add_child(p)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	p.add_child(v)
	return v


func _status(text: String, danger: bool = false) -> void:
	if _status_lbl != null and is_instance_valid(_status_lbl):
		_status_lbl.text = text
		_status_lbl.add_theme_color_override("font_color", _VT.COLOR_DANGER if danger else _VT.COLOR_ACCENT_CYAN)


func show_page(name: String) -> void:
	page = name
	_clear()
	if _discovery != null and name != "join":
		_discovery.stop()
		_discovery = null
	match name:
		"home":
			_build_home()
		"host":
			_build_host()
		"private":
			_build_private()
		"join":
			_build_join()
		"lobby":
			_build_lobby()
		"catching_up":
			_build_catching_up()
	_status_lbl = Label.new()
	_status_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_status_lbl.add_theme_font_size_override("font_size", 22)
	_status_lbl.add_theme_color_override("font_color", _VT.COLOR_ACCENT_CYAN)
	_root.add_child(_status_lbl)


func _build_home() -> void:
	_title("Local Wi-Fi Play")
	_text("Two phones, one Wi-Fi, one living world. No internet needed.")
	_button("HOST LOCAL GAME", true, func(): LanSession.mode = "host"; show_page("host"))
	_button("JOIN LOCAL GAME", true, func(): LanSession.mode = "join"; show_page("join"))
	_button("Back", false, _back_to_main)


func _build_host() -> void:
	_title("Host a game")
	if not LanSession.can_host_locally():
		_text("This build cannot run the world on this device (no Python runtime). Use the host-capable APK or a desktop host.")
		_button("Back", false, func(): show_page("home"))
		return
	var v := _panel()
	_root.remove_child(v.get_parent())
	_name_edit = _field("Your name", LanSession.default_player_name())
	_session_edit = _field("Game name", "%s's world" % LanSession.default_player_name())
	_code_edit = _field("Join code (tell your friend)", LanSession.random_code(), true)
	var ml := Label.new()
	ml.text = "Map size"
	_VT.apply_label_secondary(ml)
	_root.add_child(ml)
	_map_btn = OptionButton.new()
	_map_btn.custom_minimum_size = Vector2(0, 60)
	_map_btn.add_theme_font_size_override("font_size", 24)
	for m in ["small", "standard"]:
		_map_btn.add_item(m)
	_map_btn.select(0)
	_root.add_child(_map_btn)
	var addrs := LanSession.local_addresses()
	_text("Your Wi-Fi address: %s" % (", ".join(addrs) if addrs.size() > 0 else "not connected to Wi-Fi yet"))
	_host_go_btn = _button("START HOSTING", true, _on_start_hosting)
	_button("Back", false, func(): LanSession.stop_local_host(); LanSession.reset(); show_page("home"))


func _build_private() -> void:
	var title := "Preparing your world"
	var body := "The world is being built on this device…"
	if LanSession.games_village:
		title = "The village of games"
		body = "A village is being built where every game has its player: the mentor, the mother, the keeper, the sawyer at the sawmill, the water-carrier at the well, the lumberjack, the forester, the mason, the hunter, the carriers, and a fire on the green. Nobody is coming. Walk up to anyone."
	elif LanSession.fresh_world:
		title = "Total reset"
		body = "Every saved world is being deleted and a new one built from nothing…"
	elif LanSession.new_world:
		title = "A new world"
		body = "The old world is put aside and a new one is being built…"
	elif LanSession.new_wizard:
		title = "A new apprentice"
		body = "The world saved on this device is being opened for a new apprentice…"
	elif LanSession.continue_game:
		title = "Opening your world"
		body = "The world saved on this device is being opened…"
	_title(title)
	_text(body)
	_hosting_started = false
	call_deferred("_start_private")


## The world was owed some time for the days it was closed (plan amendment 10): the host pays it with the real simulation while this page shows
## how far it has got; Enter now forfeits what is left.
var _cu_label: Label
var _cu_acc := 0.0


func _build_catching_up() -> void:
	_title("The world turned while you were away")
	_text("The village and its neighbours went on without you. Give it a moment to catch up, or walk in now.")
	_cu_label = _text("", false)
	_button("Enter now", true, _enter_now)
	_button("Back", false, _back_to_main)
	_poll_catch_up()


func _poll_catch_up() -> void:
	if LanSession.sim == null or not LanSession.sim.connected():
		_status("Connection to the host lost.", true)
		return
	var r: Dictionary = LanSession.sim.op({"op": "lobby"})
	if str(r.get("status", "")) != "ok":
		return
	var cu: Dictionary = r.get("session", {}).get("catch_up", {})
	var owed := int(cu.get("owed_ms", 0))
	var paid := int(cu.get("paid_ms", 0))
	if _cu_label != null and is_instance_valid(_cu_label):
		_cu_label.text = "%d of %d minutes" % [int(paid / 60000), int(ceil(float(owed) / 60000.0))]
	if not bool(cu.get("active", false)):
		_enter_now()


func _enter_now() -> void:
	if _entering_world or LanSession.sim == null:
		return
	LanSession.sim.op({"op": "start"})
	_enter_world()


func _start_private() -> void:
	LanSession.mode = "host"
	LanSession.player_name = LanSession.default_player_name()
	# a world built afresh ("Start a new world", the total reset) gets a new map: a new seed; a continued world ignores the seed (its save is the world)
	var seed_ := 507 if (LanSession.games_village or not (LanSession.new_world or LanSession.fresh_world)) else 1000 + (randi() % 9000)
	var r: Dictionary = LanSession.start_local_host("Solo", LanSession.random_code(), seed_, "small", true)
	if str(r.get("state", "")) == "failed":
		_status(str(r.get("error", "could not start")), true)
		_button("Back", false, _back_to_main)
		return
	_hosting_started = true


func _on_start_hosting() -> void:
	if _busy:
		return
	var name := _name_edit.text.strip_edges()
	var code := _code_edit.text.strip_edges()
	if name == "":
		_status("Type your name first.", true)
		return
	if code.length() < 4:
		_status("The join code needs at least four digits.", true)
		return
	LanSession.player_name = name
	_host_go_btn.disabled = true
	_busy = true
	_status("Building the world on this device (this takes a few seconds)…")
	var map_size: String = _map_btn.get_item_text(_map_btn.selected)
	var r: Dictionary = LanSession.start_local_host(_session_edit.text.strip_edges(), code, 507 + (randi() % 1000), map_size, false)
	if str(r.get("state", "")) == "failed":
		_status(str(r.get("error", "could not start the host")), true)
		_host_go_btn.disabled = false
		_busy = false
		return
	_hosting_started = true


func _build_join() -> void:
	_title("Join a game")
	_join_name_edit = _field("Your name", LanSession.default_player_name())
	_join_code_edit = _field("Join code", LanSession.join_code, true, "the host's 4 digits")
	var hl := Label.new()
	hl.text = "Games on this Wi-Fi"
	_VT.apply_label_primary(hl)
	hl.add_theme_font_size_override("font_size", 24)
	_root.add_child(hl)
	_host_list = _panel()
	var none := Label.new()
	none.name = "None"
	none.text = "Searching…"
	_VT.apply_label_secondary(none)
	_host_list.add_child(none)
	var ml := Label.new()
	ml.text = "Or type the host's address"
	_VT.apply_label_primary(ml)
	ml.add_theme_font_size_override("font_size", 24)
	_root.add_child(ml)
	_ip_edit = _field("Wi-Fi address", LanSession.host_address if LanSession.host_address != "127.0.0.1" else "", false, "192.168.x.x")
	_port_edit = _field("Port", str(LanSession.DEFAULT_PORT), true)
	_join_go_btn = _button("JOIN", true, func(): _join(_ip_edit.text.strip_edges(), int(_port_edit.text)))
	_button("Back", false, func(): LanSession.reset(); show_page("home"))
	_discovery = _Discovery.new()
	if not _discovery.start(LanSession.DISCOVERY_PORT):
		_status("Could not open a discovery socket (%s); type the address instead." % _discovery.last_error, true)
	else:
		_discovery.probe()


func _refresh_host_list() -> void:
	if _host_list == null or not is_instance_valid(_host_list):
		return
	last_hosts = _discovery.hosts(5000) if _discovery != null else []
	for c in _host_list.get_children():
		_host_list.remove_child(c)
		c.queue_free()
	if last_hosts.is_empty():
		var none := Label.new()
		none.name = "None"
		none.text = "No games found yet (both phones on the same Wi-Fi? host on the Host screen?)"
		none.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_VT.apply_label_secondary(none)
		_host_list.add_child(none)
		return
	for h in last_hosts:
		var b := Button.new()
		var same := str(h.get("game", "")) == LanSession.GAME_VERSION
		b.text = "%s  ·  %d/%d players  ·  %s%s" % [str(h.get("name", "?")), int(h.get("players", 0)), int(h.get("max_players", 2)), str(h.get("state", "")), "" if same else "  (version %s)" % str(h.get("game", "?"))]
		b.name = "Host_" + str(h.get("host", "")).replace(".", "_")
		b.custom_minimum_size = Vector2(0, 64)
		b.add_theme_font_size_override("font_size", 20)
		_VT.style_secondary_button(b)
		var host_ip := str(h.get("host", ""))
		var host_port := int(h.get("port", LanSession.DEFAULT_PORT))
		b.pressed.connect(func(): _ip_edit.text = host_ip; _port_edit.text = str(host_port); _join(host_ip, host_port))
		_host_list.add_child(b)


func _join(address: String, port: int) -> void:
	if _busy:
		return
	var name := _join_name_edit.text.strip_edges()
	var code := _join_code_edit.text.strip_edges()
	if name == "":
		_status("Type your name first.", true)
		return
	if address == "":
		_status("Pick a game from the list or type the host's Wi-Fi address.", true)
		return
	if code == "":
		_status("Type the host's join code.", true)
		return
	_busy = true
	_status("Connecting to %s…" % address)
	LanSession.mode = "join"
	LanSession.player_name = name
	var reply: Dictionary = LanSession.connect_and_hello(address, port, code, name)
	_busy = false
	if str(reply.get("status", "")) != "ok":
		_status(LanSession.describe_error(str(reply.get("reason", LanSession.last_error))), true)
		return
	show_page("lobby")


func _build_lobby() -> void:
	_title("Lobby")
	_lobby_title = _text(LanSession.session_name, false)
	_lobby_info = _text("")
	var pl := Label.new()
	pl.text = "Wizards"
	_VT.apply_label_primary(pl)
	pl.add_theme_font_size_override("font_size", 24)
	_root.add_child(pl)
	_lobby_players = _panel()
	if LanSession.is_host:
		var addrs := LanSession.local_addresses()
		_lobby_info.text = "Tell your friend: Wi-Fi address %s, join code %s" % [", ".join(addrs) if addrs.size() > 0 else "(no Wi-Fi address)", LanSession.join_code]
		_start_btn = _button("START THE WORLD", true, _on_start_world)
	else:
		_lobby_info.text = "Waiting for the host to start the world…"
	_button("Leave", false, _leave_lobby)
	_poll_lobby()


func _leave_lobby() -> void:
	if LanSession.sim != null:
		LanSession.sim.op({"op": "leave"})
	LanSession.stop_local_host()
	LanSession.reset()
	show_page("home")


func _on_start_world() -> void:
	if LanSession.sim == null:
		return
	_start_btn.disabled = true
	var r: Dictionary = LanSession.sim.op({"op": "start"})
	if str(r.get("status", "")) != "ok":
		_status("Could not start: %s" % str(r.get("reason", "")), true)
		_start_btn.disabled = false
		return
	_enter_world()


func _poll_lobby() -> void:
	if LanSession.sim == null or not LanSession.sim.connected():
		_status("Connection to the host lost.", true)
		return
	var r: Dictionary = LanSession.sim.op({"op": "lobby"})
	if str(r.get("status", "")) != "ok":
		return
	var s: Dictionary = r.get("session", {})
	_lobby_state = str(s.get("state", ""))
	var cu: Dictionary = s.get("catch_up", {})
	if bool(cu.get("active", false)) and _lobby_info != null and is_instance_valid(_lobby_info) and LanSession.is_host:
		_lobby_info.text = "The world is catching up on the time it was closed: %d of %d minutes. START THE WORLD walks in now." % [int(int(cu.get("paid_ms", 0)) / 60000), int(ceil(float(cu.get("owed_ms", 0)) / 60000.0))]
	if _lobby_players != null and is_instance_valid(_lobby_players):
		for c in _lobby_players.get_children():
			_lobby_players.remove_child(c)
			c.queue_free()
		for p in s.get("players", []):
			var l := Label.new()
			l.text = "%s%s%s" % [str(p.get("name", "")), "  (host)" if bool(p.get("host", false)) else "", "" if bool(p.get("connected", true)) else "  — away"]
			l.name = "Player_" + str(p.get("id", ""))
			l.add_theme_font_size_override("font_size", 26)
			_VT.apply_label_primary(l)
			l.add_theme_color_override("font_color", Color.html(str(p.get("colour", "#ffffff"))))
			_lobby_players.add_child(l)
	if _lobby_state == "playing":
		_enter_world()


func _enter_world() -> void:
	if _entering_world:
		return
	_entering_world = true
	get_tree().change_scene_to_file("res://client/scenes/hybrid_world.tscn")


func _back_to_main() -> void:
	LanSession.stop_local_host()
	LanSession.reset()
	get_tree().change_scene_to_file("res://client/scenes/main_menu.tscn")


# ---------------------------------------------------------------- per frame

func _process(delta: float) -> void:
	if page == "join" and _discovery != null:
		_discovery.poll()
		_probe_acc += delta
		if _probe_acc >= 1.0:
			_probe_acc = 0.0
			_discovery.probe()
			_refresh_host_list()
	elif page == "lobby":
		_lobby_acc += delta
		if _lobby_acc >= 0.5:
			_lobby_acc = 0.0
			_poll_lobby()
	elif page == "catching_up":
		_cu_acc += delta
		if _cu_acc >= 0.25:
			_cu_acc = 0.0
			_poll_catch_up()
	elif page in ["host", "private"] and _hosting_started:
		_host_acc += delta
		if _host_acc >= 0.25:
			_host_acc = 0.0
			_check_host()


func _check_host() -> void:
	var st: Dictionary = LanSession.host_status()
	var state := str(st.get("state", ""))
	if state == "failed":
		_hosting_started = false
		_busy = false
		_status("The world could not start: %s" % str(st.get("error", "")), true)
		if _host_go_btn != null and is_instance_valid(_host_go_btn):
			_host_go_btn.disabled = false
		return
	if state != "ready":
		_status("Building the world on this device… (%s)" % state)
		return
	_hosting_started = false
	var reply: Dictionary = LanSession.connect_and_hello("127.0.0.1", LanSession.port, LanSession.join_code, LanSession.player_name, LanSession.host_secret)
	_busy = false
	if str(reply.get("status", "")) != "ok":
		_status("The host started but refused this device: %s" % str(reply.get("reason", "")), true)
		return
	if LanSession.private_session:
		var lob: Dictionary = LanSession.sim.op({"op": "lobby"})
		if bool(lob.get("session", {}).get("catch_up", {}).get("active", false)):
			show_page("catching_up")
			return
		LanSession.sim.op({"op": "start"})
		_enter_world()
	else:
		show_page("lobby")


# ---------------------------------------------------------------- test API

func ui_set_fields(name: String, code: String, address: String = "", port: int = 0) -> void:
	if _name_edit != null and is_instance_valid(_name_edit):
		_name_edit.text = name
		_code_edit.text = code
	if _join_name_edit != null and is_instance_valid(_join_name_edit):
		_join_name_edit.text = name
		_join_code_edit.text = code
		if address != "":
			_ip_edit.text = address
		if port > 0:
			_port_edit.text = str(port)


func ui_press(label: String) -> bool:
	for c in _root.get_children():
		if c is Button and c.text == label and not c.disabled:
			c.pressed.emit()
			return true
	return false


func ui_status() -> String:
	return _status_lbl.text if _status_lbl != null else ""


func ui_page() -> String:
	return page


func ui_catch_up_text() -> String:
	return _cu_label.text if _cu_label != null and is_instance_valid(_cu_label) else ""
