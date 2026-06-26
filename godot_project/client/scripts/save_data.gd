class_name DmbSaveData
extends RefCounted

const PATH := "user://save.cfg"

static func load_config() -> ConfigFile:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return cfg
	return cfg


static func save_config(cfg: ConfigFile) -> void:
	cfg.save(PATH)


static func get_setting(key: String, default_value) -> Variant:
	var cfg := load_config()
	return cfg.get_value("settings", key, default_value)


static func set_setting(key: String, value) -> void:
	var cfg := load_config()
	cfg.set_value("settings", key, value)
	save_config(cfg)


static func get_last_difficulty() -> String:
	return str(get_setting("last_difficulty", "medium"))


static func set_last_difficulty(id: String) -> void:
	set_setting("last_difficulty", id)
