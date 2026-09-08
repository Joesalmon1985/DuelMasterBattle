class_name DmbGameResult
extends RefCounted

## outcome: "victory" | "defeat" | "clash" | "stalemate"
## reason:  "solved" | "exhausted" | "both_exhausted" | "forced"
var outcome: String
var reason: String = ""
var human_solved: bool
var bot_solved: bool
var human_guess_count: int
var bot_guess_count: int
var message: String


func _init(oc: String, hs: bool, bs: bool, hgc: int, bgc: int, msg: String, p_reason: String = "") -> void:
	outcome = oc
	human_solved = hs
	bot_solved = bs
	human_guess_count = hgc
	bot_guess_count = bgc
	message = msg
	reason = p_reason


func player_won() -> bool:
	return outcome == "victory"


func player_lost() -> bool:
	return outcome == "defeat"
