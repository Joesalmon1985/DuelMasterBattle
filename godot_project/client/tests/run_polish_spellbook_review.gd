extends SceneTree

## Spellbook parchment layout regression + smoke.
## godot --path godot_project --script res://client/tests/run_polish_spellbook_review.gd
##
## Asserts every page content viewport sits inside measured parchment-safe rects.
## Captures screenshots under user://polish_spellbook_layout/ (and Pack polish folder when writable).

const Shell = preload("res://client/scenes/g05_shell.gd")
const Model = preload("res://client/ui/spellbook/spellbook_model.gd")
const ReviewBinder = preload("res://client/ui/spellbook/spellbook_review_binder.gd")
const Margins = preload("res://client/ui/spellbook/spellbook_margins.gd")

const SIZES := [
	Vector2i(1280, 720),
	Vector2i(960, 540),
	Vector2i(450, 800),
]


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	OS.set_environment("DMB_PLAYTEST_REVIEW", "1")
	OS.set_environment("DMB_FIXTURE", "FX-MVP")
	OS.set_environment("DMB_SEED", "507")
	OS.set_environment("DMB_SAVE_SLOT", "g05_visual_review")
	OS.set_environment("DMB_REDUCED_MOTION", "1")
	var shell: Control = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 20000
	while Time.get_ticks_msec() < deadline and not shell.is_booted():
		await process_frame
	if not shell.is_booted():
		push_error("polish spellbook review: shell boot timeout")
		print("POLISH_SPELLBOOK_REVIEW_FAIL boot")
		quit(1)
		return
	var model = shell.spellbook_model()
	var host = shell.spellbook_host()
	if model == null or host == null:
		push_error("polish spellbook review: host/model missing")
		print("POLISH_SPELLBOOK_REVIEW_FAIL host")
		quit(1)
		return
	if not ReviewBinder.review_enabled():
		push_error("polish spellbook review: review flag not active")
		print("POLISH_SPELLBOOK_REVIEW_FAIL flag")
		quit(1)
		return
	deadline = Time.get_ticks_msec() + 5000
	while Time.get_ticks_msec() < deadline and model.conn_state != Model.ConnState.READY:
		await process_frame
	var has_review := false
	for p in model.pages:
		if str(p.get("id", "")) == "review":
			has_review = true
			break
	if not has_review:
		push_error("polish spellbook review: missing Review page")
		print("POLISH_SPELLBOOK_REVIEW_FAIL pages")
		quit(1)
		return

	var out_dir := _evidence_dir()
	DirAccess.make_dir_recursive_absolute(out_dir)

	# --- Open / close smoke ---
	shell.invoke_spellbook_for_test()
	await create_timer(0.4).timeout
	if model.host_mode != Model.HostMode.OPEN:
		push_error("polish spellbook review: book did not open (mode=%s)" % model.host_mode)
		print("POLISH_SPELLBOOK_REVIEW_FAIL open")
		quit(1)
		return

	# --- Geometry at each representative size ---
	for sz in SIZES:
		_set_viewport_size(sz)
		await process_frame
		await process_frame
		await create_timer(0.15).timeout
		if host.has_method("_layout_art_slots"):
			host._layout_art_slots()
		if host.has_method("_rebuild_page_content"):
			host._rebuild_page_content()
		await process_frame
		var violations: Array = host.layout_violations() if host.has_method("layout_violations") else ["no layout_violations API"]
		if not violations.is_empty():
			push_error("layout violations @ %sx%s: %s" % [sz.x, sz.y, str(violations)])
			print("POLISH_SPELLBOOK_REVIEW_FAIL layout %sx%s" % [sz.x, sz.y])
			quit(1)
			return
		var geo: Dictionary = host.layout_geometry() if host.has_method("layout_geometry") else {}
		var mode := "spread" if bool(geo.get("use_spread", false)) else "single"
		await _capture(out_dir, "review_%s_%dx%d.png" % [mode, sz.x, sz.y])
		print("POLISH_SPELLBOOK_LAYOUT_OK %sx%s mode=%s" % [sz.x, sz.y, mode])

	# Prefer landscape for scrolled / second-page captures
	_set_viewport_size(Vector2i(1280, 720))
	await process_frame
	await process_frame
	if host.has_method("_layout_art_slots"):
		host._layout_art_slots()
	if host.has_method("_rebuild_page_content"):
		host._rebuild_page_content()
	await process_frame

	# Scroll right/single page to lower controls
	_scroll_page_bottom(host)
	await process_frame
	await _capture(out_dir, "review_scrolled_1280x720.png")

	# Second diagnostic page (Industry if present)
	var industry_idx := _page_index(model, "industry")
	if industry_idx < 0:
		industry_idx = _page_index(model, "economy")
	if industry_idx >= 0:
		model.goto_page(industry_idx)
		await process_frame
		await create_timer(0.1).timeout
		var v2: Array = host.layout_violations() if host.has_method("layout_violations") else []
		if not v2.is_empty():
			push_error("layout violations on diagnostic page: %s" % str(v2))
			print("POLISH_SPELLBOOK_REVIEW_FAIL diagnostic_layout")
			quit(1)
			return
		await _capture(out_dir, "diagnostic_page_1280x720.png")

	# Portrait / single-page
	_set_viewport_size(Vector2i(450, 800))
	await process_frame
	await process_frame
	if host.has_method("_layout_art_slots"):
		host._layout_art_slots()
	if host.has_method("_rebuild_page_content"):
		host._rebuild_page_content()
	await process_frame
	if host.has_method("uses_spread") and host.uses_spread():
		push_error("expected single-page presentation at 450x800")
		print("POLISH_SPELLBOOK_REVIEW_FAIL single_expected")
		quit(1)
		return
	await _capture(out_dir, "review_single_450x800.png")

	# Debug overlay
	OS.set_environment("DMB_SPELLBOOK_LAYOUT_DEBUG", "1")
	_set_viewport_size(Vector2i(1280, 720))
	await process_frame
	if host.has_method("_layout_art_slots"):
		host._layout_art_slots()
	await process_frame
	await _capture(out_dir, "layout_debug_overlay_1280x720.png")
	OS.set_environment("DMB_SPELLBOOK_LAYOUT_DEBUG", "0")

	# Close smoke
	model.close_book()
	await create_timer(0.2).timeout
	if model.host_mode != Model.HostMode.COMPACT:
		push_error("polish spellbook review: book did not close")
		print("POLISH_SPELLBOOK_REVIEW_FAIL close")
		quit(1)
		return

	print("POLISH_SPELLBOOK_REVIEW_OK evidence=%s" % out_dir)
	print("SAFE_RECTS left=%s right=%s page=%s" % [Margins.BOOK_LEFT, Margins.BOOK_RIGHT, Margins.PAGE_CONTENT])
	quit(0)


func _page_index(model, id: String) -> int:
	for i in model.pages.size():
		if str(model.pages[i].get("id", "")) == id:
			return i
	return -1


func _scroll_page_bottom(host) -> void:
	if host == null:
		return
	for prop in ["_scroll_right", "_scroll_single"]:
		var scroll = host.get(prop)
		if scroll is ScrollContainer:
			var sc: ScrollContainer = scroll
			if sc.is_visible_in_tree():
				sc.scroll_vertical = 100000
				return


func _set_viewport_size(sz: Vector2i) -> void:
	DisplayServer.window_set_size(sz)
	var vp := get_root().get_viewport()
	if vp != null:
		vp.size = sz


func _evidence_dir() -> String:
	# Prefer Pack tracking path when the project is opened from the repo.
	var pack := ProjectSettings.globalize_path("res://").path_join(
		"../Pack/DuelMasterBattle_Build_Pack/tracking/polish/spellbook_layout"
	)
	var abs_pack := pack.replace("\\", "/")
	# Fall back to user:// which is always writable.
	var user := ProjectSettings.globalize_path("user://polish_spellbook_layout")
	if DirAccess.make_dir_recursive_absolute(abs_pack) == OK:
		return abs_pack
	DirAccess.make_dir_recursive_absolute(user)
	return user


func _capture(dir: String, filename: String) -> void:
	await process_frame
	var img: Image = get_root().get_viewport().get_texture().get_image()
	if img == null:
		push_warning("screenshot skipped (null image): %s" % filename)
		return
	var path := dir.path_join(filename)
	var err := img.save_png(path)
	if err != OK:
		push_warning("screenshot save failed %s err=%s" % [path, err])
	else:
		print("CAPTURED %s" % path)
