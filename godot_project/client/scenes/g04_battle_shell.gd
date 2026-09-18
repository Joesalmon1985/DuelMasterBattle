extends "res://client/scenes/g01_shell.gd"

## G04 FX-BATTLE playable shell — isolated save g04_battle.

const UnitController = preload("res://client/combat/unit_controller.gd")
const MagicTargeting = preload("res://client/ui/magic_targeting.gd")
const LocalBattle = preload("res://client/combat/local_battle.gd")
const G04_BATTLE_SAVE := "g04_battle"
const TILE := 48.0

var _battle
var _units_layer: Node2D
var _unit_nodes: Dictionary = {}
var _targeting
var _battle_label: Label
var _spell_mode := "destroy"


func _ready() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-BATTLE")
	OS.set_environment("DMB_SEED", "404")
	OS.set_environment("DMB_SAVE_SLOT", G04_BATTLE_SAVE)
	super()
	_targeting = MagicTargeting.new()
	_battle = LocalBattle.new()
	_units_layer = Node2D.new()
	_units_layer.name = "BattleUnits"
	_world_host.add_child(_units_layer)
	_battle_label = Label.new()
	_battle_label.position = Vector2(12, 64)
	_battle_label.add_theme_font_size_override("font_size", 13)
	_battle_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_battle_label.custom_minimum_size = Vector2(300, 0)
	_ui_root.add_child(_battle_label)
	_set_status("G04 FX-BATTLE — walk and cast; no army orders")
	_prompt.text = "Tap unit: Destroy. Buff keys: 1 shield 2 freq 3 range. Isolated save g04_battle."


func _process(delta: float) -> void:
	super(delta)
	if _client == null:
		return
	var view: Dictionary = _client.request_view("player", ["units", "battles", "fx_battle", "buildings", "player"])
	_refresh_units(view)
	if Input.is_key_pressed(KEY_1):
		_spell_mode = "shield"
	elif Input.is_key_pressed(KEY_2):
		_spell_mode = "frequency"
	elif Input.is_key_pressed(KEY_3):
		_spell_mode = "range"
	elif Input.is_action_just_pressed("ui_accept"):
		_spell_mode = "destroy"
	_battle_label.text = "Spell=%s | units=%d | wizard immune to armies" % [
		_spell_mode, view.get("units", {}).size()
	]


func _refresh_units(view: Dictionary) -> void:
	var units: Dictionary = view.get("units", {})
	var labels: Dictionary = view.get("fx_battle", {}).get("labels", {})
	for uid in units.keys():
		var u: Dictionary = units[uid]
		if not _unit_nodes.has(uid):
			var node := Node2D.new()
			node.set_script(UnitController)
			_units_layer.add_child(node)
			var body := ColorRect.new()
			body.name = "Body"
			body.size = Vector2(24, 24)
			body.position = Vector2(-12, -12)
			node.add_child(body)
			var lab := Label.new()
			lab.name = "Label"
			lab.position = Vector2(-40, -30)
			lab.add_theme_font_size_override("font_size", 11)
			node.add_child(lab)
			_unit_nodes[uid] = node
		var ctrl = _unit_nodes[uid]
		var bind := u.duplicate(true)
		bind["archetype"] = str(labels.get(uid, u.get("archetype", uid)))
		ctrl.bind_unit(bind)
	# Drop missing
	for uid in _unit_nodes.keys():
		if not units.has(uid):
			_unit_nodes[uid].queue_free()
			_unit_nodes.erase(uid)
