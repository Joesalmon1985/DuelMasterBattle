extends Control

## God Mode technology inspector (plan v2 8.6): every card of the catalogue with the real imported picture of each building or unit it
## unlocks. Filters by era, source game and "missing or placeholder art"; selecting a card shows animated previews that use the SAME
## frame selection as the world (hybrid_art._sequence_index), eight facing buttons to debug sprite orientation, and building states
## (idle, working, build) where the Lua declared them. Data is the sim's `inspect` / catalogue payload (inspector.catalogue).

const HybridArt = preload("res://client/hybrid/hybrid_art.gd")
const COMPASS := ["n", "ne", "e", "se", "s", "sw", "w", "nw"]

var art := HybridArt.new()
var cards: Array = []
var shown: Array = []
var selected: Dictionary = {}
var facing := "e"
var state := "idle"
var turret_slot := -1  # -1: the turret follows the hull; 0..31: aim (counter-clockwise from north) for layered vehicles
var previews: Array = []  # {entity, item, rect}
var _t := 0.0

var era_filter: OptionButton
var game_filter: OptionButton
var missing_only: CheckBox
var search: LineEdit
var list: ItemList
var detail: VBoxContainer
var title: Label
var summary: Label
var preview_box: HFlowContainer
var count_label: Label


func _ready() -> void:
	art.load_catalogue()
	_build_ui()


func _build_ui() -> void:
	var root := HBoxContainer.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(root)
	var left := VBoxContainer.new()
	left.custom_minimum_size = Vector2(520, 0)
	root.add_child(left)
	var row := HBoxContainer.new()
	left.add_child(row)
	era_filter = OptionButton.new()
	for e in ["all eras", "prehistoric", "historic", "modern", "dystopian"]:
		era_filter.add_item(e)
	era_filter.item_selected.connect(func(_i): apply_filters())
	row.add_child(era_filter)
	game_filter = OptionButton.new()
	for g in ["all games", "widelands", "openra", "mindustry", "hybrid"]:
		game_filter.add_item(g)
	game_filter.item_selected.connect(func(_i): apply_filters())
	row.add_child(game_filter)
	missing_only = CheckBox.new()
	missing_only.text = "missing/placeholder art"
	missing_only.toggled.connect(func(_b): apply_filters())
	left.add_child(missing_only)
	search = LineEdit.new()
	search.placeholder_text = "search"
	search.text_changed.connect(func(_t): apply_filters())
	left.add_child(search)
	count_label = Label.new()
	left.add_child(count_label)
	list = ItemList.new()
	list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	list.item_selected.connect(func(i): select_card(str(shown[i]["id"])))
	left.add_child(list)
	detail = VBoxContainer.new()
	detail.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root.add_child(detail)
	title = Label.new()
	detail.add_child(title)
	summary = Label.new()
	detail.add_child(summary)
	var facing_row := HBoxContainer.new()
	detail.add_child(facing_row)
	for c in COMPASS:
		var b := Button.new()
		b.text = c
		b.pressed.connect(func(): set_facing(c))
		facing_row.add_child(b)
	var state_row := HBoxContainer.new()
	detail.add_child(state_row)
	for s in ["idle", "working", "build"]:
		var sb := Button.new()
		sb.text = s
		sb.pressed.connect(func(): set_state(s))
		state_row.add_child(sb)
	var turret_row := HBoxContainer.new()
	detail.add_child(turret_row)
	var tl := Label.new()
	tl.text = "turret aim (vehicles with a turret): follows hull"
	turret_row.add_child(tl)
	var ts := HSlider.new()
	ts.min_value = -1
	ts.max_value = 31
	ts.step = 1
	ts.value = -1
	ts.custom_minimum_size = Vector2(320, 24)
	ts.value_changed.connect(func(v): _on_turret(v, tl))
	turret_row.add_child(ts)
	preview_box = HFlowContainer.new()
	detail.add_child(preview_box)


func load_catalogue(d: Dictionary) -> void:
	cards = d.get("cards", [])
	apply_filters()


func _games_of(card: Dictionary) -> Array:
	var out: Array = []
	for e in card.get("entities", []):
		var key := str(e.get("art", {}).get("key", ""))
		var g := key.split(".")[0] if key != "" else ""
		if g != "" and not out.has(g):
			out.append(g)
	return out


func _has_missing(card: Dictionary) -> bool:
	for e in card.get("entities", []):
		var st := str(e.get("art", {}).get("status", "missing"))
		if st == "missing" or st == "alias_placeholder":
			return true
	return false


func apply_filters() -> void:
	shown = []
	var era := "" if era_filter == null or era_filter.selected <= 0 else era_filter.get_item_text(era_filter.selected)
	var game := "" if game_filter == null or game_filter.selected <= 0 else game_filter.get_item_text(game_filter.selected)
	var q := "" if search == null else search.text.to_lower()
	for c in cards:
		if era != "" and str(c.get("era", "")) != era:
			continue
		if game != "" and not _games_of(c).has(game):
			continue
		if missing_only != null and missing_only.button_pressed and not _has_missing(c):
			continue
		if q != "" and str(c.get("name", "")).to_lower().find(q) < 0:
			continue
		shown.append(c)
	if list != null:
		list.clear()
		for c in shown:
			list.add_item("%s  [%s]" % [c.get("name", ""), c.get("era", "")])
		count_label.text = "%d of %d cards" % [shown.size(), cards.size()]


func select_card(card_id: String) -> void:
	selected = {}
	for c in cards:
		if str(c.get("id", "")) == card_id:
			selected = c
	previews = []
	if preview_box != null:
		for ch in preview_box.get_children():
			ch.queue_free()
	if selected.is_empty():
		return
	if title != null:
		title.text = "%s (%s)" % [selected.get("name", ""), selected.get("era", "")]
		summary.text = str(selected.get("summary", ""))
	for e in selected.get("entities", []):
		var item: Dictionary = art.items.get(str(e.get("art", {}).get("key", "")), {})
		var rect := TextureRect.new()
		rect.custom_minimum_size = Vector2(260, 260)
		rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		var box := VBoxContainer.new()
		box.add_child(rect)
		var lab := Label.new()
		var st := str(e.get("art", {}).get("status", "missing"))
		lab.text = "%s%s" % [e.get("label", e.get("id", "")), "" if st == "imported" else "  [%s]" % st.to_upper()]
		if st != "imported":
			lab.add_theme_color_override("font_color", Color(1.0, 0.45, 0.35))
		box.add_child(lab)
		if preview_box != null:
			preview_box.add_child(box)
		previews.append({"entity": e, "item": item, "rect": rect})
	_refresh_previews()


func set_facing(f: String) -> void:
	facing = f
	_refresh_previews()


func _on_turret(v: float, label: Label) -> void:
	turret_slot = int(v)
	label.text = "turret aim: follows hull" if turret_slot < 0 else "turret aim slot %d (0 = north, 8 = west, 16 = south, 24 = east)" % turret_slot
	_refresh_previews()


func set_state(s: String) -> void:
	state = s
	_refresh_previews()


func item_for_state(item: Dictionary) -> Dictionary:
	# Widelands buildings keep their state sheets under <id>.working / <id>.build
	var id := str(item.get("id", ""))
	if state != "idle" and art.items.has("%s.%s" % [id, state]):
		return art.items["%s.%s" % [id, state]]
	return item


func preview_texture(item: Dictionary, time: float = 0.0) -> Texture2D:
	var it := item_for_state(item)
	if it.is_empty():
		return null
	if str(it.get("mode", "")) == "sequence" and it.has("layers") and turret_slot >= 0:
		var lt: Array = art.layer_textures(it, {"facing": facing, "status": "idle", "turret": turret_slot})
		if lt[0] != null and lt[1] != null:
			var img: Image = (lt[0] as Texture2D).get_image().duplicate()
			var top: Image = (lt[1] as Texture2D).get_image()
			img.blend_rect(top, Rect2i(Vector2i.ZERO, top.get_size()), Vector2i.ZERO)
			return ImageTexture.create_from_image(img)
	if str(it.get("mode", "")) == "sequence":
		var index := art._sequence_index(it, {"facing": facing, "status": "moving" if state == "working" else "idle"})
		return art._tex("res://client/hybrid/art/openra/%s-%04d.png" % [str(it.get("prefix", "")), index])
	var tex: Texture2D = art._tex(str(it.get("id", "")))
	if tex == null:
		return null
	var cols := maxi(int(it.get("columns", 1)), 1)
	var rows := maxi(int(it.get("rows", 1)), 1)
	var frames := maxi(int(it.get("frames", 1)), 1)
	var frame := 0
	if frames > 1 and int(it.get("fps", 0)) > 0:
		frame = int(time * float(it.get("fps", 1))) % frames
	var at := AtlasTexture.new()
	at.atlas = tex
	var fw := tex.get_width() / cols
	var fh := tex.get_height() / rows
	at.region = Rect2((frame % cols) * fw, (frame / cols) * fh, fw, fh)
	return at


func _refresh_previews() -> void:
	for p in previews:
		p["rect"].texture = preview_texture(p["item"], _t)


func _process(delta: float) -> void:
	_t += delta
	if not previews.is_empty():
		_refresh_previews()
