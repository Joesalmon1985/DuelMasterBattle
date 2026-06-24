class_name DmbGuessRecord
extends RefCounted

var guess: Array
var exact: int
var colour_only: int


func _init(g: Array, e: int, c: int) -> void:
	guess = g.duplicate()
	exact = e
	colour_only = c
