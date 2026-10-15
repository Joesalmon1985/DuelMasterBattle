extends Control
class_name DmbCampaignHud

## The Wizard Mode HUD: what matters first. A compact card under the top bar with the era and cycle, and the current objective (the next lesson, or the
## open quest); the full read-out (victory points, era progress) is one tap away behind the title. It hides itself while a conversation, the arrival text,
## the journal, a menu or a duel owns the screen, so it never sits on top of a conversation. Built from the shared narrative style (visual_theme.gd,
## responsive_modal.gd), sized in physical pixels like every narrative panel.

const _VT = preload("res://client/scripts/visual_theme.gd")
const _RM = preload("res://client/ui/responsive_modal.gd")

signal journal_requested()

var world: Node
var panel: PanelContainer
var title_button: Button
var objective_label: Label
var stats_label: Label  # the developer-style read-out ("Cycle 0 | Era: prehistoric | VP ..."); kept as the old era_hud so its text can be checked
var journal_button: Button
var notice_label: Label  # a short message ("Walk closer to talk to X.") that fades after a few seconds
var _notice_until := 0
var _box: VBoxContainer
var _stats_open := false
var objective := ""


func setup(p_world: Node) -> void:
	world = p_world
	name = "CampaignHud"
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel = PanelContainer.new()
	panel.name = "Panel"
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(panel)
	_box = VBoxContainer.new()
	panel.add_child(_box)
	title_button = Button.new()
	title_button.name = "Title"
	title_button.flat = true
	title_button.pressed.connect(toggle_stats)
	_box.add_child(title_button)
	objective_label = Label.new()
	objective_label.name = "Objective"
	objective_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_box.add_child(objective_label)
	stats_label = Label.new()
	stats_label.name = "Stats"
	stats_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	stats_label.visible = false
	_box.add_child(stats_label)
	notice_label = Label.new()
	notice_label.name = "Notice"
	notice_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	notice_label.visible = false
	_box.add_child(notice_label)
	journal_button = Button.new()
	journal_button.name = "JournalButton"
	journal_button.text = "Journal (J)"
	journal_button.pressed.connect(func() -> void: journal_requested.emit())
	_box.add_child(journal_button)
	get_viewport().size_changed.connect(relayout)
	relayout()


func toggle_stats() -> void:
	_stats_open = not _stats_open
	stats_label.visible = _stats_open
	relayout()


func set_state(title: String, stats: String, p_objective: String) -> void:
	title_button.text = title + ("  [-]" if _stats_open else "  [+]")
	stats_label.text = stats
	objective = p_objective
	objective_label.text = p_objective
	objective_label.visible = p_objective != ""
	if panel != null:
		panel.reset_size()


func relayout() -> void:
	if panel == null:
		return
	var info := _RM.window_info(world)
	var m := _RM.metrics(info, "sheet")
	var k: float = info["k"]
	var win: Vector2 = info["win"]
	panel.add_theme_stylebox_override("panel", _VT.narr_hud_style(k))
	var width := minf(win.x * 0.64, 440.0) if win.x > win.y else minf(win.x * 0.7, 360.0)
	panel.custom_minimum_size = Vector2(width * k, 0.0)
	panel.position = Vector2(float(m["margin"]) * k, 58.0 * k)  # below the top bar (the menu and magic buttons)
	_box.add_theme_constant_override("separation", int(round(4.0 * k)))
	title_button.add_theme_font_size_override("font_size", int(round(float(m["small"]) * k * 1.05)))
	title_button.add_theme_color_override("font_color", _VT.COLOR_GOLD)
	title_button.add_theme_color_override("font_hover_color", _VT.COLOR_PARCHMENT)
	title_button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	title_button.custom_minimum_size = Vector2(0, 34.0 * k)
	title_button.focus_mode = Control.FOCUS_NONE
	objective_label.add_theme_font_size_override("font_size", int(round(float(m["small"]) * k * 1.1)))
	objective_label.add_theme_color_override("font_color", _VT.COLOR_PARCHMENT)
	notice_label.add_theme_font_size_override("font_size", int(round(float(m["small"]) * k * 1.05)))
	notice_label.add_theme_color_override("font_color", _VT.COLOR_GOLD)
	stats_label.add_theme_font_size_override("font_size", int(round(float(m["small"]) * k * 0.95)))
	stats_label.add_theme_color_override("font_color", _VT.COLOR_PARCHMENT_DIM)
	_VT.style_narr_button(journal_button, k, "choice", float(m["small"]))
	journal_button.alignment = HORIZONTAL_ALIGNMENT_CENTER
	journal_button.autowrap_mode = TextServer.AUTOWRAP_OFF
	journal_button.custom_minimum_size = Vector2(150.0 * k, maxf(40.0, float(m["small"]) * 2.4) * k)
	journal_button.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	panel.reset_size()


## The whole HUD steps aside while something owns the screen.
func set_covered(covered: bool) -> void:
	visible = not covered


func flash(text: String, seconds := 4.0) -> void:
	notice_label.text = text
	notice_label.visible = true
	_notice_until = Time.get_ticks_msec() + int(seconds * 1000.0)
	if panel != null:
		panel.reset_size()


func _process(_delta: float) -> void:
	if notice_label != null and notice_label.visible and Time.get_ticks_msec() > _notice_until:
		notice_label.visible = false
		panel.reset_size()
