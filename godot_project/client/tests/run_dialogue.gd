extends SceneTree

## DialogueBox regression (CORRECTIVE_PASS_PLAN Phase 9, brief §19/§32):
## short line, long line, multi-paragraph note, rapid taps while typing, tap to
## finish page, tap for next page, final tap closes, choice after long text, and
## the actual Trial-start Halvard note. No text may disappear before display.
##
## godot --headless --path godot_project --script res://client/tests/run_dialogue.gd

const _Dialogue = preload("res://client/world/dialogue_box.gd")
const _World = preload("res://client/world/world_data.gd")

var _failures: Array = []
var _dlg


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	_dlg = _Dialogue.new()
	root.add_child(_dlg)
	await process_frame
	_test_paginate_pure()
	await _test_short_line()
	await _test_long_line_pages()
	await _test_rapid_taps_do_not_skip()
	await _test_choice_after_long_text()
	await _test_halvard_note()
	_report()


func _tap() -> void:
	# The box ignores taps for ~180ms after a page opens (debounce); jump past it.
	_dlg._ignore_until_msec = 0
	_dlg.advance()
	await process_frame


## Pure function: pages rejoin to the original, no page over budget.
func _test_paginate_pure() -> void:
	var t := "Para one is short.\n\nPara two is a little longer than para one but still fits.\n\n" + "word ".repeat(80).strip_edges() + "\n\nTail."
	var pages: Array = _Dialogue.paginate(t, 190)
	assert_true(pages.size() >= 3, "long text splits into ≥3 pages (got %d)" % pages.size())
	for pg in pages:
		assert_true(str(pg).length() <= 190, "page within budget (%d)" % str(pg).length())
	var rejoined := ""
	for pg in pages:
		rejoined += str(pg) + " "
	var norm_in := t.replace("\n\n", " ").replace("  ", " ").strip_edges()
	var norm_out := rejoined.replace("\n\n", " ").replace("  ", " ").strip_edges()
	assert_eq(norm_out, norm_in, "no words lost or duplicated across pages")
	assert_eq(_Dialogue.paginate("", 190), [""], "empty text is one empty page")
	assert_eq(_Dialogue.paginate("hi", 190).size(), 1, "short text is one page")


func _test_short_line() -> void:
	var done := [false]
	_dlg.advanced.connect(func(): done[0] = true, CONNECT_ONE_SHOT)
	_dlg.say("", "A short line.")
	await process_frame
	assert_true(_dlg.is_open(), "opens")
	assert_eq(_dlg.ui_page_count(), 1, "one page")
	await _tap()   # finishes typing
	assert_true(_dlg.is_open() and not _dlg.ui_is_typing(), "first tap completes typing, stays open")
	await _tap()   # closes
	assert_true(not _dlg.is_open(), "second tap closes")
	assert_true(done[0], "advanced emitted")


func _test_long_line_pages() -> void:
	var long := "The Trial wants useful things, not just strong arms. ".repeat(9).strip_edges()
	_dlg.say("Note", long)
	await process_frame
	var n: int = _dlg.ui_page_count()
	assert_true(n >= 2, "long line paginates (%d pages)" % n)
	var seen := ""
	for i in range(n):
		assert_eq(_dlg.ui_page_index(), i, "on page %d" % i)
		await _tap()   # finish typing this page
		assert_true(_dlg.is_open(), "still open after completing page %d" % i)
		seen += _dlg.ui_visible_text() + " "
		await _tap()   # next page (or close on the last)
	assert_true(not _dlg.is_open(), "closes only after the final page")
	assert_eq(seen.replace("  ", " ").strip_edges(), long, "every page was displayed, nothing clipped")


func _test_rapid_taps_do_not_skip() -> void:
	var long := "Rapid tapping must not destroy text. ".repeat(8).strip_edges()
	_dlg.say("", long)
	await process_frame
	var n: int = _dlg.ui_page_count()
	# Two immediate taps: the first completes typing, the second turns the page.
	# Never two page turns from one tap; never a close before the last page.
	await _tap()
	await _tap()
	if n >= 2:
		assert_eq(_dlg.ui_page_index(), 1, "two taps = complete + one page turn")
		assert_true(_dlg.is_open(), "did not close early")
	while _dlg.is_open():
		await _tap()


func _test_choice_after_long_text() -> void:
	var long := "Do you want to do the long thing? ".repeat(7).strip_edges()
	var picked := [""]
	var co := func():
		picked[0] = await _dlg.choose_async(long, ["Yes", "No"])
	co.call()
	await process_frame
	assert_true(_dlg.ui_page_count() >= 2, "choice prompt paginates")
	assert_true(not _dlg.is_waiting_choice(), "no buttons before the last page")
	while _dlg.ui_page_index() < _dlg.ui_page_count() - 1:
		await _tap()
		await _tap()
	assert_true(_dlg.is_waiting_choice(), "buttons appear on the final page")
	_dlg.pick("No")
	await process_frame
	assert_eq(picked[0], "No", "choice resolves after long text")


func _test_halvard_note() -> void:
	var area: Dictionary = _World.get_area("dd_entrance")
	var note := ""
	for e in area["entities"]:
		if str(e.get("id", "")) == "aid_box":
			note = str(e["text"])
	assert_true(note.length() > 0, "found the Halvard box note")
	_dlg.say("", note)
	await process_frame
	var seen := ""
	while _dlg.is_open():
		await _tap()
		if _dlg.is_open():
			seen += _dlg.ui_visible_text() + "\n\n"
			await _tap()
	var norm := func(x: String) -> String: return x.replace("\n\n", " ").replace("  ", " ").strip_edges()
	assert_eq(norm.call(seen), norm.call(note), "the Halvard note is fully readable, nothing lost")


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)
		print("  FAIL: %s" % msg)


func assert_eq(a, b, msg: String) -> void:
	if a != b:
		_failures.append("%s (got %s, expected %s)" % [msg, str(a), str(b)])
		print("  FAIL: %s (got %s, expected %s)" % [msg, str(a), str(b)])


func _report() -> void:
	if _failures.is_empty():
		print("DIALOGUE: ALL PASSED")
		quit(0)
	else:
		print("DIALOGUE: %d FAILURE(S)" % _failures.size())
		quit(1)
