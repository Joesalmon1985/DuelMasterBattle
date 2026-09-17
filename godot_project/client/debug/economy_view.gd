extends Control
class_name DmbEconomyView

## Developer-only economy inspector. Shows real warehouse/cart/order fields from
## the Python economy/debug view. Not part of release UI.

@export var release_mode: bool = false

var _label: RichTextLabel
var _client = null


func _ready() -> void:
	if release_mode:
		visible = false
		return
	set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_label = RichTextLabel.new()
	_label.bbcode_enabled = true
	_label.fit_content = true
	_label.scroll_active = true
	_label.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	_label.add_theme_font_size_override("normal_font_size", 13)
	add_child(_label)
	_label.text = "[b]Economy debug[/b]\nWaiting for Python view…"


func bind_client(client) -> void:
	_client = client
	refresh()


func refresh() -> void:
	if release_mode or _client == null:
		return
	var view: Dictionary = {}
	if _client.has_method("request_view"):
		view = _client.request_view("economy")
	var fx: Dictionary = view.get("fx_cargo", {})
	var lines: PackedStringArray = PackedStringArray()
	lines.append("[b]FX-CARGO / economy[/b]")
	lines.append("seed=%s cart=%s store=%s" % [str(fx.get("seed", "?")), str(fx.get("cart_id", "?")), str(fx.get("store", "?"))])
	lines.append("N0=%s N1=%s N2=%s block=%s" % [str(fx.get("N0")), str(fx.get("N1")), str(fx.get("N2")), str(fx.get("block_hex"))])
	lines.append("")
	lines.append("[b]Warehouses[/b]")
	var stocks: Dictionary = view.get("stocks", {})
	for store_id in stocks.keys():
		if str(store_id).begins_with("_"):
			continue
		var catan: Dictionary = stocks[store_id].get("catan", {}) if typeof(stocks[store_id]) == TYPE_DICTIONARY else {}
		var bits: PackedStringArray = PackedStringArray()
		for good in catan.keys():
			var entry: Dictionary = catan[good]
			bits.append("%s a=%s r=%s e=%s" % [good, str(entry.get("available", 0)), str(entry.get("reserved", 0)), str(entry.get("escrow", 0))])
		if bits.size() > 0:
			lines.append("%s: %s" % [store_id, ", ".join(bits)])
	lines.append("")
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
		lines.append("%s @%s status=%s cargo=[%s]" % [
			cart_id,
			str(cart.get("current_node")),
			str(cart.get("status")),
			", ".join(cargo_bits),
		])
	lines.append("")
	lines.append("[b]Orders[/b]")
	var orders: Dictionary = view.get("orders", {})
	for oid in orders.keys():
		var order: Dictionary = orders[oid]
		lines.append("%s %s status=%s" % [oid, str(order.get("action")), str(order.get("status"))])
	_label.text = "\n".join(lines)


func add_clear_route_button(on_pressed: Callable) -> void:
	if release_mode:
		return
	var row := HBoxContainer.new()
	add_child(row)
	var place := Button.new()
	place.text = "Place route block"
	place.pressed.connect(func(): on_pressed.call("place"))
	row.add_child(place)
	var clear := Button.new()
	clear.text = "Clear route block"
	clear.pressed.connect(func(): on_pressed.call("clear"))
	row.add_child(clear)
