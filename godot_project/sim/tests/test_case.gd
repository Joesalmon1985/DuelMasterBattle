class_name DmbTestCase
extends RefCounted

var _failures: Array = []


func assert_true(cond: bool, msg: String = "") -> void:
	if not cond:
		_failures.append(msg if msg != "" else "assert_true failed")


func assert_eq(actual, expected, msg: String = "") -> void:
	if actual != expected:
		_failures.append("%s expected %s got %s" % [msg, str(expected), str(actual)])


func assert_null(v, msg: String = "") -> void:
	assert_eq(v, null, msg)


func failures() -> Array:
	return _failures


func passed() -> bool:
	return _failures.is_empty()
