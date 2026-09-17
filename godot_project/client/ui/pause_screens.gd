extends RefCounted
class_name DmbPauseScreens

var _driver: DmbClockDriver
var _open: Array = []


func setup(driver: DmbClockDriver) -> void:
	_driver = driver


func open(name: String) -> void:
	_open.append(name)
	_driver.open_pause_screen()


func close(name: String) -> void:
	if name in _open:
		_open.erase(name)
		_driver.close_pause_screen()


func depth() -> int:
	return _open.size()
