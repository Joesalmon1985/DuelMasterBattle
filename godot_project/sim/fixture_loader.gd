class_name DmbFixtureLoader
extends RefCounted


static func fixtures_dir() -> String:
	var project_dir := ProjectSettings.globalize_path("res://")
	return project_dir.path_join("..").path_join("shared_fixtures")


static func load_json(filename: String) -> Dictionary:
	var path := fixtures_dir().path_join(filename)
	var f := FileAccess.open(path, FileAccess.READ)
	assert(f != null, "Cannot open fixture: %s" % path)
	var text := f.get_as_text()
	f.close()
	var parsed = JSON.parse_string(text)
	assert(parsed is Dictionary, "Invalid JSON: %s" % filename)
	return parsed
