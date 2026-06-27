extends RefCounted
class_name PlayabilityHaptics

const _SaveData = preload("res://client/scripts/save_data.gd")


static func enabled() -> bool:
	return bool(_SaveData.get_setting("haptics", true))


static func pulse_light() -> void:
	if enabled():
		Input.vibrate_handheld(20)


static func pulse_medium() -> void:
	if enabled():
		Input.vibrate_handheld(40)


static func pulse_warning() -> void:
	if enabled():
		Input.vibrate_handheld(30)
