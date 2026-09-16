extends RefCounted
class_name DmbSemanticLabels


static func label_for(view: Dictionary) -> String:
	if not bool(view.get("known", false)):
		return "unknown"
	if view.get("name") != null and str(view.get("name")) != "":
		return str(view["name"])
	if view.get("role") != null:
		return str(view["role"])
	return str(view.get("label", "unknown"))
