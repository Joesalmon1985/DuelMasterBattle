class_name DmbGameResult
extends RefCounted

var outcome: String
var human_solved: bool
var bot_solved: bool
var human_guess_count: int
var bot_guess_count: int
var message: String


func _init(oc: String, hs: bool, bs: bool, hgc: int, bgc: int, msg: String) -> void:
	outcome = oc
	human_solved = hs
	bot_solved = bs
	human_guess_count = hgc
	bot_guess_count = bgc
	message = msg
