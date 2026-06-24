extends DmbTestCase

const _Art = preload("res://client/scripts/art.gd")


func run() -> void:
	for rel in _Art.expected_asset_paths():
		var full: String = "res://assets/" + rel
		assert_true(FileAccess.file_exists(full), "asset exists: %s" % rel)
		var tex: Texture2D = _Art.load_texture(rel)
		assert_true(tex != null, "asset loads: %s" % rel)
	var missing: Texture2D = _Art.load_texture("icons/does_not_exist.png")
	assert_null(missing, "missing asset returns null")
