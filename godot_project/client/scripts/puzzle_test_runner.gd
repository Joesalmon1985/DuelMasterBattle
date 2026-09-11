extends Node

## Global autoload singleton to pass the selected room id (e.g. "pz_01")
## from the puzzle test menu to the test room scene.

static var selected_puzzle = ""

static func get_puzzle():
	return selected_puzzle

static func set_puzzle(puzzle) -> void:
	selected_puzzle = puzzle

static func clear() -> void:
	selected_puzzle = ""
