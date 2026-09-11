extends Node

## Global autoload singleton to pass selected puzzle data to the test room.

static var selected_puzzle: Dictionary = {}

static func get_puzzle() -> Dictionary:
	return selected_puzzle.duplicate(true)

static func set_puzzle(puzzle: Dictionary) -> void:
	selected_puzzle = puzzle.duplicate(true)

static func clear() -> void:
	selected_puzzle = {}