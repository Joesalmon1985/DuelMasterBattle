extends Node
class_name HybridCampaignUi

## Presentation of the opening campaign's scripted moments: the scene cards (the stranger's arrival, the confrontation, the aftermath of the duel) and the
## Game Over screen. No rules live here. The Python world owns the story (narrative/campaign.py): the snapshot's journal carries `campaign.scene` (the page to
## show, who speaks, where the camera should look, which answers are open) and `campaign.game_over`; every button is an op (`scene_choose`, `scene_next`,
## `new_game`). A scene pauses the world while the page is read (the dramatic moments may; ordinary conversations never do) and guides the camera with
## `world.camera_focus` without taking the controls for longer than the scene lasts.

const NarrativeCard = preload("res://client/ui/narrative_card.gd")

var world: Node
var story_ui: Node
var layer: CanvasLayer
var scene_card: Control   # a sheet at the bottom, like a conversation
var over_card: Control    # the Game Over modal
var notice_card: Control  # a sheet for the world's own interruptions: a rung of the magic ladder, the inner voice (one at a time, queued)
var _notices: Array = []
var flash: ColorRect
var scene_active := false
var over_shown := false
var _scene: Dictionary = {}
var _acc := 0.0
var _shake := 0.0
var _focus_set := false


func setup(p_world: Node, p_story_ui: Node) -> void:
	world = p_world
	story_ui = p_story_ui
	layer = CanvasLayer.new()
	layer.name = "CampaignLayer"
	layer.layer = 15
	world.add_child(layer)
	scene_card = NarrativeCard.new()
	layer.add_child(scene_card)
	scene_card.setup(world, "sheet", "CampaignScene")
	scene_card.choice_pressed.connect(_on_choice)
	scene_card.footer_pressed.connect(func(_id: String) -> void: _next())
	over_card = NarrativeCard.new()
	layer.add_child(over_card)
	over_card.setup(world, "modal", "GameOver")
	over_card.footer_pressed.connect(_on_over)
	notice_card = NarrativeCard.new()
	layer.add_child(notice_card)
	notice_card.setup(world, "sheet", "WorldNotice")
	notice_card.footer_pressed.connect(func(_id: String) -> void: _next_notice())
	flash = ColorRect.new()
	flash.name = "SceneFlash"
	flash.color = Color(1, 1, 1, 0)
	flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	flash.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	layer.add_child(flash)


func covering() -> bool:
	return scene_active or over_shown


## The world interrupts (the owner's rule for the magic ladder): a card in the speaker's name over whatever the player was doing, Continue to go on.
## Several in a row are shown one after another. `kind` is "rung" or "inner_voice"; the server already closed any conversation it interrupted.
func show_notice(kind: String, who: String, role: String, body: String) -> void:
	_notices.append({"kind": kind, "who": who, "role": role, "body": body})
	if not notice_card.visible:
		_next_notice()


func _next_notice() -> void:
	if _notices.is_empty():
		notice_card.hide_card()
		return
	var n: Dictionary = _notices.pop_front()
	if story_ui != null and story_ui.dialog.visible:
		story_ui.close_dialog()  # the server ended the conversation; the card goes too
	notice_card.show_card(str(n["who"]), str(n["role"]), str(n["body"]), [], [{"id": "next", "text": "Continue", "kind": "primary"}])
	if str(n["kind"]) == "rung" and world.has_method("_sfx"):
		world._sfx().victory()


func notice_showing() -> bool:
	return notice_card != null and notice_card.visible


func campaign() -> Dictionary:
	var c = story_ui.journal_data().get("campaign", {}) if story_ui != null else {}
	return c if typeof(c) == TYPE_DICTIONARY else {}


func _process(delta: float) -> void:
	if _shake > 0.0:
		_shake = maxf(0.0, _shake - delta)
		world._camera_nudge = Vector2(sin(_shake * 90.0), cos(_shake * 70.0)) * 10.0 * (_shake / 0.5)
		if _shake == 0.0:
			world._camera_nudge = Vector2.ZERO
	if flash.color.a > 0.0:
		flash.color.a = maxf(0.0, flash.color.a - delta * 1.8)
	_acc += delta
	if _acc < 0.1:
		return
	_acc = 0.0
	_sync()


## Start a scene or the Game Over screen when the world says so. While a scene is open the replies to our own ops are the truth (the paused world sends
## no snapshots), so the snapshot is only read to *start* one.
func _sync() -> void:
	var c := campaign()
	if c.is_empty():
		return
	var go = c.get("game_over", {})
	if typeof(go) == TYPE_DICTIONARY and not (go as Dictionary).is_empty() and not world.mp:
		_show_game_over(go)  # the classic single-process server only; a hosted Wizard World shows the session's ending instead (hybrid_world._show_ending)
		return
	if scene_active or world._duel_open:
		return
	var sc = c.get("scene", null)
	if typeof(sc) == TYPE_DICTIONARY and not (sc as Dictionary).is_empty():
		_begin_scene(sc)


func _begin_scene(sc: Dictionary) -> void:
	scene_active = true
	world.paused = true
	world._input_locked = true
	if story_ui != null:
		story_ui.close_dialog()
	if world.wizard_labels != null:
		world.wizard_labels.close()
	_show_page(sc)


func _check_line(c: Dictionary) -> String:
	if c.is_empty():
		return ""
	var parts: PackedStringArray = ["%s %d" % [str(c.get("label", "")), int(c.get("score", 0))]]
	if int(c.get("evidence", 0)) != 0:
		parts.append("+ %d from what you know" % int(c["evidence"]))
	if int(c.get("relationship", 0)) != 0:
		parts.append("%s %d from how they feel about you" % ["+" if int(c["relationship"]) > 0 else "-", absi(int(c["relationship"]))])
	return "[%s = %d against %d: %s]" % [" ".join(parts), int(c.get("total", 0)), int(c.get("threshold", 0)), "success" if bool(c.get("passed", false)) else "failure"]


func _show_page(sc: Dictionary) -> void:
	_scene = sc
	var body := str(sc.get("text", ""))
	var choices: Array = []
	for ch in sc.get("choices", []):
		choices.append({"id": str(ch["id"]), "text": str(ch["text"]), "disabled": not bool(ch.get("available", true))})
	var ans = sc.get("answer", {})
	if typeof(ans) == TYPE_DICTIONARY and not (ans as Dictionary).is_empty():
		var line := _check_line(ans.get("check", {}) if typeof(ans.get("check", {})) == TYPE_DICTIONARY else {})
		if line != "":
			body += "\n\n" + line
		if str(ans.get("text", "")) != "":
			body += "\n\n" + str(ans["text"])
		if str(ans.get("reply", "")) != "":
			body += "\n\n" + str(ans["reply"])
	var who := str(sc.get("name", ""))
	var needs := bool(sc.get("needs_answer", false))
	var footer: Array = []
	if not needs:
		footer.append({"id": "next", "text": "Begin the duel" if bool(sc.get("last", false)) and str(sc.get("final", "")) == "duel" else "Continue", "kind": "primary"})
	var role: String = {"mentor": "Your mentor", "attacker": "The stranger"}.get(str(sc.get("speaker", "")), "")
	scene_card.show_card(who, str(role), body, choices, footer, "%d / %d" % [int(sc.get("i", 0)) + 1, int(sc.get("n", 1))])
	_guide_camera(sc)
	match str(sc.get("fx", "")):
		"flash":
			flash.color = Color(1, 1, 1, 0.85)
		"shake":
			_shake = 0.5
			flash.color = Color(1, 1, 1, 0.5)


func _guide_camera(sc: Dictionary) -> void:
	var f = sc.get("focus", [])
	if typeof(f) == TYPE_ARRAY and (f as Array).size() == 2:
		world.camera_focus = Vector2((float(f[0]) + 0.5) * float(world.TPX), (float(f[1]) + 0.5) * float(world.TPX))
		_focus_set = true


func _on_choice(id: String) -> void:
	var reply: Dictionary = world._sim.op({"op": "scene_choose", "choice": id})
	if str(reply.get("status", "")) == "ok" and typeof(reply.get("scene")) == TYPE_DICTIONARY:
		_show_page(reply["scene"])


func _next() -> void:
	if bool(_scene.get("needs_answer", false)):
		return
	var reply: Dictionary = world._sim.op({"op": "scene_next"})
	if str(reply.get("status", "")) != "ok":
		return
	var sc = reply.get("scene", null)
	if typeof(sc) == TYPE_DICTIONARY and not (sc as Dictionary).is_empty():
		_show_page(sc)
		return
	_end_scene()
	var lease = reply.get("duel_lease", {})
	if typeof(lease) == TYPE_DICTIONARY and not (lease as Dictionary).is_empty():
		world.open_story_duel(lease)


func _end_scene() -> void:
	scene_active = false
	_scene = {}
	scene_card.hide_card()
	if _focus_set:
		world.camera_focus = Vector2.INF
		_focus_set = false
	world.paused = false
	world._input_locked = false
	world._hud_area_lbl.text = "Wizard RTS"
	world.refresh_snapshot()  # the paused world sent none: bring the picture up to date


# ---------------------------------------------------------------- Game Over

func _show_game_over(go: Dictionary) -> void:
	if over_shown:
		return
	over_shown = true
	scene_active = false
	scene_card.hide_card()
	if story_ui != null:
		story_ui.close_dialog()
	if world.wizard_labels != null:
		world.wizard_labels.close()
	world.camera_focus = Vector2.INF
	world.paused = true
	world._input_locked = true
	var buttons: Array = [{"id": "new", "text": "New game", "kind": "primary"}, {"id": "quit", "text": "Quit"}]
	var body := "The stranger's magic was stronger than yours. Your journey ends here."
	if not world.is_solo_session():  # a shared world goes on without you: there is no restarting it for somebody else
		buttons = [{"id": "quit", "text": "Leave game", "kind": "primary"}]
		body = "The stranger's magic was stronger than yours. Your journey ends here, but the world, and your friend, go on."
	over_card.show_card("Game over", str(go.get("text", "The apprentice was defeated.")), body, [], buttons)


func _on_over(id: String) -> void:
	if id == "quit":
		if world.mp:
			world.mp_leave()
		else:
			world.get_tree().quit()
	else:
		new_game()


func new_game() -> void:
	if not world.new_game():
		return
	over_card.hide_card()
	over_shown = false
	scene_active = false


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	var k: InputEventKey = event
	if over_shown:
		if k.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
			over_card.activate_primary()
		get_viewport().set_input_as_handled()  # nothing else (not the pause menu, not Escape) reaches a dead apprentice's game
		return
	if scene_active:
		if k.keycode in [KEY_ENTER, KEY_KP_ENTER, KEY_SPACE]:
			scene_card.activate_primary()
		elif k.keycode >= KEY_1 and k.keycode <= KEY_9:
			scene_card.activate_choice_index(k.keycode - KEY_1)
		get_viewport().set_input_as_handled()
