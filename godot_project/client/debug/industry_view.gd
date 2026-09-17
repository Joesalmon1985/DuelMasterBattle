extends Control
class_name DmbIndustryView

signal action_requested(action: String)
signal worker_path_toggled(blocked: bool)

const FIELDS := ["fx_industry", "industry", "buildings", "industry_workers", "stocks"]
const REFRESH_SECONDS := 0.5

var _client
var _label: RichTextLabel
var _pending := ""
var _elapsed := 0.0
var _path_blocked := false
var _last_view: Dictionary = {}


func _ready() -> void:
	set_anchors_preset(PRESET_TOP_RIGHT)
	offset_left = -322
	offset_top = 92
	offset_right = -8
	offset_bottom = 390
	var panel := PanelContainer.new()
	panel.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	add_child(panel)
	var body := VBoxContainer.new()
	panel.add_child(body)
	_label = RichTextLabel.new()
	_label.bbcode_enabled = true
	_label.custom_minimum_size = Vector2(300, 190)
	_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_child(_label)
	var actions := HFlowContainer.new()
	body.add_child(actions)
	_button(actions, "Damage 25%", func(): action_requested.emit("industry_damage"))
	_button(actions, "Strike", func(): action_requested.emit("industry_strike"))
	_button(actions, "Clear strike", func(): action_requested.emit("industry_clear_strike"))
	_button(actions, "Paid repair", func(): action_requested.emit("industry_repair"))
	_button(actions, "Block worker path", _toggle_path)


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
		refresh()


func is_expanded() -> bool:
	return true


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
	var fx: Dictionary = view.get("fx_industry", {})
	var industry: Dictionary = view.get("industry", {})
	var buildings: Dictionary = view.get("buildings", {})
	var processor: Dictionary = buildings.get(str(fx.get("processor_id", "")), {})
	var lines := PackedStringArray()
	lines.append("[b]FX-INDUSTRY[/b] seed=%s  path_blocked=%s" % [fx.get("seed", "?"), _path_blocked])
	lines.append("processor health=%s/%s" % [processor.get("health", "?"), processor.get("max_health", "?")])
	lines.append(street_feedback(view))
	lines.append("")
	lines.append("[b]Allocation / carries[/b]")
	var rates: Dictionary = {}
	var reasons: Dictionary = {}
	for event_variant in industry.get("events", []):
		var event: Dictionary = event_variant
		if event.get("kind") == "industry_rates":
			rates = event.get("rates", {})
		elif event.get("kind") == "industry_shortage":
			reasons = event.get("reasons", {})
	for factory_id in fx.get("factory_ids", []):
		var factory: Dictionary = industry.get("factories", {}).get(factory_id, {})
		lines.append("%s rate=%s carry=%s cause=%s" % [
			factory_id, rates.get(factory_id, "0"), factory.get("meter", "?"),
			reasons.get(factory_id, "running"),
		])
	lines.append("[b]Finite[/b] %s" % finite_diagnostics(view))
	_label.text = "\n".join(lines)


func street_feedback(view: Dictionary) -> String:
	var workers: Array = view.get("industry_workers", [])
	if workers.is_empty():
		return "Street: no assigned worker is visible."
	var worker: Dictionary = workers[0]
	var cue := "idle (path obstruction is visual only)" if _path_blocked else str(worker.get("cue", "idle"))
	var reason = worker.get("bottleneck_reason")
	if reason:
		return "Street: worker is %s because %s." % [cue, reason]
	return "Street: worker is %s on the selected installed route." % cue


func finite_diagnostics(view: Dictionary) -> String:
	var fx: Dictionary = view.get("fx_industry", {})
	var layers: Dictionary = view.get("industry", {}).get("layers", {})
	var layer: Dictionary = layers.get(str(fx.get("finite_layer_id", "")), {})
	return "layer=%s balance=%s retired=%s" % [
		fx.get("finite_layer_id", "?"), layer.get("finite_balance", "?"), layer.get("retired", false)
	]


func _toggle_path() -> void:
	_path_blocked = not _path_blocked
	worker_path_toggled.emit(_path_blocked)
	refresh()
