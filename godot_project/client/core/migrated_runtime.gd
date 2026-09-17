extends Node
class_name DmbMigratedRuntime

## Marks the G01 migrated runtime: Python owns durable world state.

static var active: bool = false


static func enable() -> void:
	active = true


static func disable_legacy_writers() -> bool:
	return active
