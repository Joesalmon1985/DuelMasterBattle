extends RefCounted
class_name DmbInventoryUi

## Presentation binder for InventoryService views (T087). Does not mint items.

var _items: Array = []
var _ground: Array = []


func apply_player_items(items: Array) -> void:
	_items = items.duplicate(true)


func apply_ground_items(items: Array) -> void:
	_ground = items.duplicate(true)


func player_ids() -> Array:
	var ids: Array = []
	for item in _items:
		ids.append(str(item.get("id", "")))
	ids.sort()
	return ids


func ground_ids() -> Array:
	var ids: Array = []
	for item in _ground:
		ids.append(str(item.get("id", "")))
	ids.sort()
	return ids


func has_item(item_id: String) -> bool:
	return item_id in player_ids() or item_id in ground_ids()


func equipped_slot(item_id: String) -> String:
	for item in _items:
		if str(item.get("id", "")) == item_id:
			return str(item.get("equipped_slot", ""))
	return ""
