extends Control
class_name DmbPortraitView

## A larger, more detailed bust of the person who is talking, drawn from the same look as their figure in the world.
## The mouth moves while the presentation bus says the character is speaking, the eyes blink, the head bobs a little, and a mood
## (smile / worried / surprised / angry) can replace the neutral face.  It never decides anything: it only shows.

const Lib = preload("res://client/characters/character_library.gd")
const Render = preload("res://client/characters/character_renderer.gd")
const Bus = preload("res://client/characters/character_bus.gd")

var look
var character_id := ""
var mood := "neutral"
var _t := 0.0
var _blink_left := 0.0
var _next_blink := 2.2
var pose := "neutral"
var _frame_cycle := [2, 3, 2, 4, 3, 2, 3, 4]
var shown_poses: Dictionary = {}   # pose -> frames shown (tests read this)

const TALK_POSES := ["talk_a", "talk_b", "talk_a", "talk_c", "talk_b", "talk_a", "talk_b", "talk_c"]


func _init() -> void:
	custom_minimum_size = Vector2(128, 128)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	clip_contents = true


func show_person(look_, id_: String) -> void:
	look = look_
	character_id = id_
	mood = "neutral"
	_t = 0.0
	queue_redraw()


func set_mood(m: String) -> void:
	mood = m


func _process(delta: float) -> void:
	if look == null or not is_visible_in_tree():
		return
	_t += delta
	var next := "neutral"
	if Bus.is_speaking(character_id):
		next = TALK_POSES[int(_t * 9.0) % TALK_POSES.size()]
	else:
		if _blink_left > 0.0:
			_blink_left -= delta
			next = "blink"
		else:
			_next_blink -= delta
			if _next_blink <= 0.0:
				_blink_left = 0.13
				_next_blink = 2.4 + fmod(_t * 1.7, 2.6)
			next = mood if mood != "neutral" else "neutral"
	if next != pose:
		pose = next
		queue_redraw()
	shown_poses[pose] = int(shown_poses.get(pose, 0)) + 1
	if Bus.is_speaking(character_id):
		queue_redraw()


func _draw() -> void:
	var r := Rect2(Vector2.ZERO, size)
	draw_rect(r, Color(0.12, 0.1, 0.17, 1.0), true)
	draw_rect(r, Color(0.85, 0.7, 0.35), false, 2.0)
	if look == null:
		return
	var bob := 0.0
	if Bus.is_speaking(character_id):
		bob = sin(_t * 11.0) * 1.5
	var inner := Rect2(Vector2(2, 2 + bob), size - Vector2(4, 4))
	Render.draw_portrait(self, look, pose, inner)
