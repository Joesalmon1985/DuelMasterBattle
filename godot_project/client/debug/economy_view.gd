extends Control
class_name DmbEconomyView

## Developer-only economy inspector. Bounded collapsible panel — never fullscreen.
## Child controls that should not steal movement input use MOUSE_FILTER_IGNORE;
## only the toggle / action buttons intercept clicks.

@export var release_mode: bool = false

var _client = null
var _panel: PanelContainer
var _body: VBoxContainer
var _label: RichTextLabel
var _toggle: Button
var _expanded := true
var _route_row: HBoxContainer
var _on_route: Callable


func _ready() -> void:
	if release_mode:
		visible = false
		return
	# Anchor top-right; bounded, not PRESET_FULL_RECT.
	set_anchors_preset(PRESET_TOP_RIGHT)
	offset_left = -300
	offset_top = 96
	offset_right = -8
	offset_bottom = 96 + 36
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	grow_vertical = Control.GROW_DIRECTION_BEGIN

	_toggle = Button.new()
	_toggle.text = "Economy ▾"
	_toggle.focus_mode = Control.FOCUS_NONE
	_toggle.mouse_filter = Control.MOUSE_FILTER_STOP
	_toggle.pressed.connect(_on_toggle)
	add_child(_toggle)

	_panel = PanelContainer.new()
	_panel.visible = true
	_panel.set_anchors_preset(PRESET_TOP_WIDE)
	_panel.offset_top = 34
	_panel.offset_bottom = 280
	_panel.offset_left = 0
	_panel.offset_right = 0
	_panel.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_panel)

	_body = VBoxContainer.new()
	_body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_panel.add_child(_body)

	_label = RichTextLabel.new()
	_label.bbcode_enabled = true
	_label.fit_content = false
	_label.scroll_active = true
	_label.custom_minimum_size = Vector2(280, 160)
	_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_label.add_theme_font_size_override("normal_font_size", 12)
	# Text must not steal pad / Wait clicks when the panel is collapsed;
	# when expanded, STOP is fine inside the bounded panel only.
	_label.mouse_filter = Control.MOUSE_FILTER_STOP
	_body.add_child(_label)
	_label.text = "[b]FX-CARGO[/b]\nWaiting…"

	_route_row = HBoxContainer.new()
	_route_row.add_theme_constant_override("separation", 4)
	_body.add_child(_route_row)
	_apply_expanded()


func bind_client(client) -> void:
	_client = client
	refresh()


func add_clear_route_button(on_pressed: Callable) -> void:
	if release_mode:
		return
	_on_route = on_pressed
	for child in _route_row.get_children():
		child.queue_free()
	var start := Button.new()
	start.text = "Start delivery"
	start.focus_mode = Control.FOCUS_NONE
	start.pressed.connect(func(): on_pressed.call("start"))
	_route_row.add_child(start)
	var place := Button.new()
	place.text = "Block"
	place.focus_mode = Control.FOCUS_NONE
	place.pressed.connect(func(): on_pressed.call("place"))
	_route_row.add_child(place)
	var clear := Button.new()
	clear.text = "Clear"
	clear.focus_mode = Control.FOCUS_NONE
	clear.pressed.connect(func(): on_pressed.call("clear"))
	_route_row.add_child(clear)


func _on_toggle() -> void:
	_expanded = not _expanded
	_apply_expanded()


func _apply_expanded() -> void:
	_panel.visible = _expanded
	_toggle.text = "Economy ▾" if _expanded else "Economy ▸"
	if _expanded:
		offset_bottom = 96 + 320
	else:
		offset_bottom = 96 + 36


func refresh() -> void:
	if release_mode or _client == null or _label == null:
		return
	var view: Dictionary = {}
	if _client.has_method("request_view"):
		view = _client.request_view("economy")
	var fx: Dictionary = view.get("fx_cargo", {})
	var lines: PackedStringArray = PackedStringArray()
	lines.append("[b]FX-CARGO[/b] seed=%s" % str(fx.get("seed", "?")))
	lines.append("cart=%s store=%s" % [str(fx.get("cart_id", "?")), str(fx.get("store", "?"))])
	lines.append("route %s→%s→%s" % [str(fx.get("N0")), str(fx.get("N1")), str(fx.get("N2"))])
	lines.append("block=%s delivery=%s" % [str(fx.get("block_node", fx.get("block_hex", "?"))), str(fx.get("delivery_status", "idle"))])
	if fx.get("construction_status"):
		lines.append("construction=%s order=%s" % [str(fx.get("construction_status")), str(fx.get("construction_order_id", "?"))])
	var draft: Dictionary = view.get("tech_draft", {})
	if draft:
		lines.append("tech active=%s pick=%s era=%s" % [
			str(draft.get("active", false)),
			str(draft.get("pick_index", draft.get("resolved_pick_index", "?"))),
			str(draft.get("era", "?")),
		])
		var last = draft.get("last_resolution") or draft.get("resolved") or {}
		if typeof(last) == TYPE_DICTIONARY and not last.is_empty():
			lines.append("tech last=%s" % str(last))
	var factions: Dictionary = view.get("factions", {})
	if not factions.is_empty():
		lines.append("factions=%s" % ", ".join(PackedStringArray(factions.keys())))
	var clock: Dictionary = view.get("clock", {})
	lines.append("turn=%s round=%s seat=%s" % [
		str(clock.get("turn", 0)),
		str(clock.get("round", 0)),
		str(clock.get("active_faction_id", "?")),
	])
	var last_seat = clock.get("last_seat") or clock.get("seat_result") or {}
	if typeof(last_seat) == TYPE_DICTIONARY and last_seat.get("tech_draft") != null:
		lines.append("seat tech=%s" % str(last_seat.get("tech_draft")))
	lines.append("")
	lines.append("[b]Warehouse[/b]")
	var stocks: Dictionary = view.get("stocks", {})
	for store_id in stocks.keys():
		if str(store_id).begins_with("_"):
			continue
		var catan: Dictionary = stocks[store_id].get("catan", {}) if typeof(stocks[store_id]) == TYPE_DICTIONARY else {}
		var bits: PackedStringArray = PackedStringArray()
		for good in catan.keys():
			var entry: Dictionary = catan[good]
			bits.append("%s a=%s r=%s" % [good, str(entry.get("available", 0)), str(entry.get("reserved", 0))])
		if bits.size() > 0:
			lines.append("%s" % store_id)
			lines.append("  " + ", ".join(bits))
	lines.append("[b]Carts[/b]")
	var carts: Dictionary = view.get("carts", {})
	for cart_id in carts.keys():
		var cart: Dictionary = carts[cart_id]
		var cargo_bits: PackedStringArray = PackedStringArray()
		for lot in cart.get("cargo_lots", []):
			if typeof(lot) != TYPE_DICTIONARY:
				continue
			if str(lot.get("status", "")) != "aboard":
				continue
			cargo_bits.append("%sx%s" % [str(lot.get("good_id")), str(lot.get("quantity"))])
		lines.append("%s @%s %s [%s]" % [
			cart_id,
			str(cart.get("current_node")),
			str(cart.get("status")),
			", ".join(cargo_bits),
		])
	lines.append("[b]Orders[/b]")
	var orders: Dictionary = view.get("orders", {})
	if orders.is_empty():
		lines.append("(none)")
	for oid in orders.keys():
		var order: Dictionary = orders[oid]
		lines.append("%s %s → %s" % [str(order.get("action")), str(order.get("status")), str(order.get("target_node", ""))])
	_label.text = "\n".join(lines)
