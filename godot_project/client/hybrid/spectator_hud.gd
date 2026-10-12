extends Node
class_name HybridSpectatorHud

## God Mode spectator view (owner playtest of 12 Oct 2026, brief P6). Everything here READS the snapshot of the one Python world:
## era progress and why it moves, a table of the six factions, the inspected faction's draft offer (up to seven cards, with their
## explanations, unlocks and countdowns), and a plain-English feed of major events. Clicking a faction row INSPECTS it (camera and
## draft panel) and never takes control; commanding a faction is the separate "Take control" button (and the old faction letters).

const SPEEDS := [1, 2, 4, 8, 16]
const ERA_NAMES := {"prehistoric": "Prehistoric", "historic": "Historic", "modern": "Modern", "dystopian": "Dystopian Future"}

var world: Node
var god: Node
var layer: CanvasLayer
var top: Label
var table: VBoxContainer
var draft_title: Label
var draft_box: VBoxContainer
var feed: RichTextLabel
var control_btn: Button
var pause_btn: Button
var inspected := "Red"
var _acc := 0.0
var _last_draft_key := ""
var _rows: Dictionary = {}
var _mono: SystemFont


func setup(p_world: Node, p_god: Node) -> void:
	world = p_world
	god = p_god
	layer = CanvasLayer.new()
	layer.name = "SpectatorLayer"
	layer.layer = 16
	world.add_child(layer)
	top = _label("SpectatorTop", Vector2(470, 8), 17, Color(1.0, 0.93, 0.7))  # right of the God Mode panel (x 10-450)
	top.custom_minimum_size = Vector2(900, 0)
	top.autowrap_mode = TextServer.AUTOWRAP_WORD
	var speeds := HBoxContainer.new()
	speeds.name = "SpectatorSpeed"
	speeds.position = Vector2(470, 74)
	layer.add_child(speeds)
	pause_btn = Button.new()
	pause_btn.name = "Pause"
	pause_btn.text = "Pause"
	pause_btn.pressed.connect(_toggle_pause)
	speeds.add_child(pause_btn)
	for sp in SPEEDS:
		var b := Button.new()
		b.name = "SpectatorSpeed_%d" % sp
		b.text = "%dx" % sp
		b.pressed.connect(_set_speed.bind(sp))
		speeds.add_child(b)
	control_btn = Button.new()
	control_btn.name = "TakeControl"
	control_btn.text = "Take control of Red"
	control_btn.tooltip_text = "Spectating never disables a faction's AI. This switches the inspected faction to your commands; press again to give it back to its AI."
	control_btn.pressed.connect(_toggle_control)
	speeds.add_child(control_btn)
	var panel := PanelContainer.new()
	panel.name = "FactionTable"
	panel.position = Vector2(-560, 96)
	panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	panel.offset_left = -650
	panel.offset_top = 96
	layer.add_child(panel)
	table = VBoxContainer.new()
	panel.add_child(table)
	_mono = SystemFont.new()  # the faction table is a fixed-width grid: columns line up
	_mono.font_names = PackedStringArray(["DejaVu Sans Mono", "Liberation Mono", "Ubuntu Mono", "Monospace"])
	var dp := PanelContainer.new()
	dp.name = "DraftPanel"
	dp.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	dp.offset_left = -650
	dp.offset_top = 330
	dp.custom_minimum_size = Vector2(638, 0)
	layer.add_child(dp)
	var dv := VBoxContainer.new()
	dp.add_child(dv)
	draft_title = Label.new()
	draft_title.name = "DraftTitle"
	draft_title.autowrap_mode = TextServer.AUTOWRAP_WORD
	draft_title.custom_minimum_size = Vector2(540, 0)
	dv.add_child(draft_title)
	draft_box = VBoxContainer.new()
	draft_box.name = "DraftCards"
	dv.add_child(draft_box)
	var fp := PanelContainer.new()
	fp.name = "EventFeed"
	fp.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	fp.offset_top = -250
	fp.offset_left = 280
	fp.custom_minimum_size = Vector2(620, 236)
	layer.add_child(fp)
	feed = RichTextLabel.new()
	feed.name = "FeedText"
	feed.custom_minimum_size = Vector2(612, 228)
	feed.scroll_following = true
	feed.bbcode_enabled = true
	fp.add_child(feed)
	set_visible(false)


func _label(nm: String, pos: Vector2, size: int, col: Color) -> Label:
	var l := Label.new()
	l.name = nm
	l.position = pos
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.95))
	l.add_theme_constant_override("outline_size", 5)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(l)
	return l


func set_visible(on: bool) -> void:
	for c in layer.get_children():
		c.visible = on
	if on:
		refresh()


static func _mmss(ms: int) -> String:
	var s := int(ms / 1000)
	return "%d:%02d" % [s / 60, s % 60]


func _process(delta: float) -> void:
	if god == null or not god.active:
		return
	_acc += delta
	if _acc >= 0.5:
		_acc = 0.0
		refresh()


func refresh() -> void:
	var snap: Dictionary = world._snapshot
	if snap.is_empty():
		return
	var era: Dictionary = snap.get("era", {})
	var gms := int(snap.get("game_ms", 0))
	var gains: Dictionary = era.get("gains", {})
	var who: PackedStringArray = []
	for f in gains:
		if int(gains[f]) > 0:
			who.append("%s +%d" % [str(f), int(gains[f])])
	var nxt := str(era.get("next_era", ""))
	var line1 := "Game time %s  |  speed %dx%s  |  Era: %s" % [_mmss(gms), int(snap.get("time_scale", 1)), " (PAUSED)" if world.paused else "", ERA_NAMES.get(str(era.get("era", "")), str(era.get("era", "")))]
	var line2 := ""
	if nxt != "":
		line2 = "To reach %s the world must gain %d VP by founding or razing settlements: %d so far (%s). %s in this era; the time limit forces it in %s." % [
			ERA_NAMES.get(nxt, nxt), int(era.get("threshold", 0)), int(era.get("progress", 0)), ", ".join(who) if who.size() > 0 else "none yet",
			_mmss(int(era.get("elapsed_ms", 0))), _mmss(int(era.get("stall_guard_in_ms", 0)))]
	else:
		line2 = "The last era. %d of %d VP gained toward the end of the cycle." % [int(era.get("progress", 0)), int(era.get("threshold", 0))]
	var last := str(era.get("last_reason", ""))
	if last != "":
		line2 += "  Last era change: %s." % ("settlements founded and razed (natural)" if last == "vp_threshold" else "time limit (stall guard)")
	top.text = line1 + "\n" + line2
	_fill_table(snap)
	_fill_draft(snap)
	_fill_feed(snap)
	var controlled := str(snap.get("controlled_faction", ""))
	control_btn.text = ("Give %s back to its AI" % controlled) if controlled != "" else ("Take control of %s" % inspected)
	pause_btn.text = "Resume" if world.paused else "Pause"


func _fill_table(snap: Dictionary) -> void:
	var rows: Array = snap.get("overview", [])
	var seen := {}
	var hdr_key := "_hdr"
	if not _rows.has(hdr_key):
		var h := Label.new()
		h.text = "Faction        tribe        AI     state      set VP crd army food unrest"
		h.text = "%-14s %-12s %-8s %-10s %3s %2s %3s %4s %4s %6s" % ["Faction", "tribe", "AI", "state", "set", "VP", "crd", "army", "food", "unrest"]
		h.add_theme_font_size_override("font_size", 13)
		h.add_theme_font_override("font", _mono)
		table.add_child(h)
		_rows[hdr_key] = h
	for r in rows:
		var name := str(r.get("name", ""))
		seen[name] = true
		var b: Button
		if _rows.has(name):
			b = _rows[name]
		else:
			b = Button.new()
			b.name = "Inspect_%s" % name
			b.alignment = HORIZONTAL_ALIGNMENT_LEFT
			b.add_theme_font_size_override("font_size", 13)
			b.add_theme_font_override("font", _mono)
			b.pressed.connect(inspect.bind(name))
			b.tooltip_text = "Inspect %s (camera, draft offer). The AI keeps playing." % name
			table.add_child(b)
			_rows[name] = b
		var col := Color.html(str(r.get("color", "#ffffff")))
		b.add_theme_color_override("font_color", col)
		b.add_theme_color_override("font_hover_color", col.lightened(0.3))
		var tag := ""
		if bool(r.get("controlled", false)):
			tag = " [YOU]"
		elif name == inspected:
			tag = " <"
		b.text = "%-14s %-12s %-8s %-10s %3d %2d %3d %4d %4d %6.2f%s" % [name.substr(0, 14), str(r.get("tribe", "")).substr(0, 12), str(r.get("policy", "")),
			str(r.get("state", "")), int(r.get("settlements", 0)), int(r.get("vp", 0)), int(r.get("cards", 0)), int(r.get("army", 0)), int(r.get("food", 0)),
			float(r.get("unrest", 0.0)), tag]
	for k in _rows.keys():
		if k != hdr_key and not seen.has(k):
			_rows[k].queue_free()
			_rows.erase(k)


func _fill_draft(snap: Dictionary) -> void:
	var tech: Dictionary = snap.get("tech", {})
	var st: Dictionary = tech.get("factions", {}).get(inspected, {})
	var offers: Array = st.get("offers", [])
	var cat: Dictionary = world.god.card_info if world.god != null else {}
	var key := "%s|%s|%d" % [inspected, ",".join(PackedStringArray(offers)), int(st.get("round", 0))]
	var head := "%s - technology round %d: " % [inspected, int(st.get("round", 0))]
	if offers.size() > 0:
		head += "%d of up to %d cards offered, %d eligible. Selectable for %s; next round in %s." % [offers.size(), int(tech.get("offer_size", 7)), int(st.get("eligible", 0)),
			_mmss(int(st.get("expires_in_ms", 0))), _mmss(int(st.get("next_round_in_ms", 0)))]
	else:
		var lp := str(st.get("last_pick", ""))
		head += "no open offer. Next round in %s.%s" % [_mmss(int(st.get("next_round_in_ms", 0))), (" Last pick: %s." % str(cat.get(lp, {}).get("name", lp))) if lp != "" else ""]
	head += "  Cards held: %d; lapsed offers: %d." % [st.get("cards", []).size(), int(st.get("lapsed", 0))]
	draft_title.text = head
	if key == _last_draft_key:
		return
	_last_draft_key = key
	for c in draft_box.get_children():
		c.queue_free()
	for cid in offers:
		var info: Dictionary = cat.get(str(cid), {})
		var l := Label.new()
		l.autowrap_mode = TextServer.AUTOWRAP_WORD
		l.custom_minimum_size = Vector2(540, 0)
		l.add_theme_font_size_override("font_size", 13)
		var unlocks: PackedStringArray = []
		for k in info.get("kinds", []):
			unlocks.append(str(k).replace("mdy:", ""))
		for u in info.get("units", []):
			unlocks.append(str(u) + " (unit)")
		if info.get("wl_patterns", []).size() > 0:
			unlocks.append("%d Widelands building types" % info.get("wl_patterns", []).size())
		var needs: PackedStringArray = []
		for r in info.get("requires_cards", []):
			needs.append(str(r))
		for r in info.get("requires_working", []):
			needs.append("a working " + str(r).replace("mdy:", ""))
		l.text = "* %s [%s]: %s" % [str(info.get("name", cid)), str(info.get("era", "")), ", ".join(unlocks) if unlocks.size() > 0 else str(info.get("summary", ""))]
		l.tooltip_text = "%s%s" % [str(info.get("summary", "")), ("\nNeeded: " + ", ".join(needs)) if needs.size() > 0 else ""]
		l.mouse_filter = Control.MOUSE_FILTER_PASS
		draft_box.add_child(l)


func _fill_feed(snap: Dictionary) -> void:
	var lines: PackedStringArray = []
	for e in snap.get("feed", []).slice(-14):
		var f := str(e.get("faction", ""))
		var col := "#ffe9a8"
		for r in snap.get("overview", []):
			if str(r.get("name", "")) == f:
				col = str(r.get("color", col))
		lines.append("[color=#aaaaaa]%s[/color] [color=%s]%s[/color]" % [_mmss(int(e.get("game_ms", 0))), col, str(e.get("text", ""))])
	var txt := "\n".join(lines)
	if feed.text != txt:
		feed.text = txt


func inspect(name: String) -> void:
	inspected = name
	_last_draft_key = ""
	if god != null:
		god.inspect(name)
	refresh()


func _toggle_control() -> void:
	var controlled := str(world._snapshot.get("controlled_faction", ""))
	if controlled != "":
		var reply: Dictionary = world._sim.op({"op": "control", "faction": ""})
		world._apply_snapshot(reply.get("snapshot", {}))
		god._say("%s is played by its AI again" % controlled)
	else:
		god.choose_faction(inspected)
	refresh()


func _set_speed(sp: int) -> void:
	world.paused = false
	god._on_speed(sp)
	refresh()


func _toggle_pause() -> void:
	world.paused = not world.paused
	refresh()
