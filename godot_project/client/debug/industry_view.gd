extends Control
class_name DmbIndustryView

signal action_requested(action: String)
signal worker_path_toggled(blocked: bool)

const FIELDS := [
	"fx_industry", "industry", "buildings", "industry_workers",
	"industry_connections", "industry_factories", "stocks", "units",
]
const REFRESH_SECONDS := 0.5

var _client
var _panel: PanelContainer
var _label: RichTextLabel
var _toggle: Button
var _pending := ""
var _elapsed := 0.0
var _path_blocked := false
var _expanded := true
var _last_view: Dictionary = {}
var _body: VBoxContainer
var _actions: HFlowContainer


func _ready() -> void:
	set_anchors_preset(PRESET_TOP_RIGHT)
	_apply_layout()
	mouse_filter = Control.MOUSE_FILTER_STOP
	_panel = PanelContainer.new()
	_panel.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	add_child(_panel)
	_body = VBoxContainer.new()
	_panel.add_child(_body)
	_toggle = Button.new()
	_toggle.text = "Hide Industry inspector"
	_toggle.focus_mode = Control.FOCUS_NONE
	_toggle.pressed.connect(_toggle_expanded)
	_body.add_child(_toggle)
	_label = RichTextLabel.new()
	_label.bbcode_enabled = true
	_label.fit_content = false
	_label.scroll_active = true
	_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_label.custom_minimum_size = Vector2(300, 160)
	_body.add_child(_label)
	_actions = HFlowContainer.new()
	_body.add_child(_actions)
	_button(_actions, "Set health to 25%", func(): action_requested.emit("industry_damage"))
	_button(_actions, "Strike", func(): action_requested.emit("industry_strike"))
	_button(_actions, "Clear strike", func(): action_requested.emit("industry_clear_strike"))
	_button(_actions, "Paid repair", func(): action_requested.emit("industry_repair"))
	_button(_actions, "Block worker path", _toggle_path)
	_label.text = "[b]FX-INDUSTRY[/b]\nWaiting…"


func _apply_layout() -> void:
	var portrait := get_viewport_rect().size.x <= 600.0
	if portrait:
		offset_left = -318
		offset_top = 84
		offset_right = -6
		offset_bottom = 360
	else:
		offset_left = -360
		offset_top = 72
		offset_right = -12
		offset_bottom = 420


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED:
		_apply_layout()


func _button(parent: Control, title: String, callback: Callable) -> void:
	var button := Button.new()
	button.text = title
	button.focus_mode = Control.FOCUS_NONE
	button.pressed.connect(callback)
	parent.add_child(button)


func bind_client(client) -> void:
	_client = client
	if not _client.request_finished.is_connected(_on_finished):
		_client.request_finished.connect(_on_finished)
	refresh()


func _process(delta: float) -> void:
	_elapsed += delta
	if _elapsed >= REFRESH_SECONDS:
		_elapsed = 0.0
		if _expanded:
			refresh()


func is_expanded() -> bool:
	return _expanded


func refresh(_force: bool = false) -> void:
	if _client == null or _pending != "":
		return
	_pending = _client.enqueue_view(
		"economy", FIELDS, {"replaceable": true, "coalesce_key": "view:industry"}
	)


func _on_finished(request_id: String, reply: Dictionary) -> void:
	if request_id != _pending:
		return
	_pending = ""
	if str(reply.get("status", "")) == "ACCEPTED":
		_apply_view(reply.get("view", {}))


func _apply_view(view: Dictionary) -> void:
	_last_view = view
	if not _expanded:
		return
	var fx: Dictionary = view.get("fx_industry", {})
	var industry: Dictionary = view.get("industry", {})
	var buildings: Dictionary = view.get("buildings", {})
	var stocks: Dictionary = view.get("stocks", {})
	var units: Dictionary = view.get("units", {})
	var processor: Dictionary = buildings.get(str(fx.get("processor_id", "")), {})
	var health := float(processor.get("health", 0))
	var max_health := maxf(float(processor.get("max_health", 1)), 1.0)
	var health_pct := int(round(100.0 * health / max_health))
	var rates: Dictionary = {}
	var reasons: Dictionary = {}
	for event_variant in industry.get("events", []):
		var event: Dictionary = event_variant
		if event.get("kind") == "industry_rates":
			rates = event.get("rates", {})
		elif event.get("kind") == "industry_shortage":
			reasons = event.get("reasons", {})
	var lines := PackedStringArray()
	lines.append("[b]FX-INDUSTRY[/b] seed=%s" % fx.get("seed", "?"))
	lines.append("Processor health: [b]%d%%[/b] (%d/%d)" % [health_pct, int(health), int(max_health)])
	lines.append(street_feedback(view))
	lines.append("")
	lines.append("[b]Connections[/b]")
	var connections: Array = view.get("industry_connections", [])
	for conn_variant in connections:
		var conn: Dictionary = conn_variant
		lines.append(
			"%s → %s  [%s]  %.3f/s  carriers=%s"
			% [
				conn.get("from_id", "?"),
				conn.get("to_id", "?"),
				conn.get("resource_label", "?"),
				float(conn.get("throughput_per_sec", 0)),
				conn.get("carrier_count", 0),
			]
		)
	lines.append("")
	lines.append("[b]Factories[/b]")
	var factory_rows: Array = view.get("industry_factories", [])
	if factory_rows.is_empty():
		for factory_id in fx.get("factory_ids", []):
			var factory: Dictionary = industry.get("factories", {}).get(factory_id, {})
			var meter := _frac(factory.get("meter", 0))
			var rate := _frac(rates.get(factory_id, 0))
			var short := str(factory_id).replace("factory:fx-", "")
			lines.append(
				"%s  progress [b]%d%%[/b]  rate [b]%.3f/s[/b]  (%s)"
				% [short.capitalize(), int(round(meter * 100.0)), rate, reasons.get(factory_id, "running")]
			)
	else:
		for row_variant in factory_rows:
			var row: Dictionary = row_variant
			lines.append(
				"%s  progress [b]%d%%[/b]  rate [b]%.3f/s[/b]  done=%s  (%s)"
				% [
					row.get("unit_label", row.get("factory_id", "?")),
					int(round(float(row.get("meter_pct", 0)))),
					float(row.get("rate_per_sec", 0)),
					row.get("completed_units", 0),
					row.get("bottleneck_reason", "running"),
				]
			)
	var unit_counts := {}
	for unit in units.values():
		var def_id := str(unit.get("definition_id", "?"))
		unit_counts[def_id] = int(unit_counts.get(def_id, 0)) + 1
	lines.append("[b]Units[/b] %s" % (str(unit_counts) if not unit_counts.is_empty() else "none yet"))
	lines.append("[b]Finite[/b] %s" % finite_diagnostics(view))
	var repair_store: String = str(fx.get("repair_store_id", ""))
	var cost: Dictionary = fx.get("repair_cost", {"brick": 1, "ore": 1})
	var store_bucket: Dictionary = stocks.get(repair_store, {})
	var available: Dictionary = store_bucket.get("catan", {})
	lines.append(
		"[b]Repair cost[/b] brick %s (have %s), ore %s (have %s)"
		% [
			cost.get("brick", 1),
			available.get("brick", {}).get("available", 0),
			cost.get("ore", 1),
			available.get("ore", {}).get("available", 0),
		]
	)
	lines.append("Path obstruction (visual only): %s" % ("ON" if _path_blocked else "off"))
	_label.text = "\n".join(lines)


func street_feedback(view: Dictionary) -> String:
	var workers: Array = view.get("industry_workers", [])
	var carriers: Array = []
	for worker_variant in workers:
		var worker: Dictionary = worker_variant
		if str(worker.get("role", "")) == "carrier":
			carriers.append(worker)
	if carriers.is_empty():
		return "Street: no carriers on active connections."
	var sample: Dictionary = carriers[0]
	var cue := str(sample.get("activity", sample.get("cue", "idle")))
	if _path_blocked and cue != "on_strike":
		cue = "blocked"
	return "Street: %d carriers; e.g. %s is [b]%s[/b] on %s→%s (%s)." % [
		carriers.size(),
		sample.get("name", "carrier"),
		cue,
		sample.get("from_id", "?"),
		sample.get("to_id", "?"),
		sample.get("resource_label", "?"),
	]


func finite_diagnostics(view: Dictionary) -> String:
	var fx: Dictionary = view.get("fx_industry", {})
	var layers: Dictionary = view.get("industry", {}).get("layers", {})
	var layer: Dictionary = layers.get(str(fx.get("finite_layer_id", "")), {})
	var balance := _frac(layer.get("finite_balance", 0))
	return "Flint layer balance [b]%.1f[/b] (retired=%s)" % [balance, layer.get("retired", false)]


func _frac(value) -> float:
	if typeof(value) == TYPE_DICTIONARY:
		var den := float(value.get("denominator", 1))
		if den == 0.0:
			return 0.0
		return float(value.get("numerator", 0)) / den
	return float(value)


func _toggle_path() -> void:
	_path_blocked = not _path_blocked
	worker_path_toggled.emit(_path_blocked)
	refresh(true)


func _toggle_expanded() -> void:
	_expanded = not _expanded
	_label.visible = _expanded
	_toggle.text = "Hide Industry inspector" if _expanded else "Show Industry inspector"
	# Keep damage/strike/repair/path controls visible while collapsing diagnostics text.
	if _expanded:
		_apply_layout()
		refresh(true)
	else:
		offset_bottom = offset_top + 118
