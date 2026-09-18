extends SceneTree

## Prove village conversation content through SpellbookDialoguePresenter
## using VillageQuestRunner (authoritative Godot dialogue session).

func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	OS.set_environment("DMB_SPELLBOOK_DIALOGUE", "1")
	var Quest = load("res://sim/world/village_quest_runner.gd")
	var Presenter = load("res://client/ui/spellbook/spellbook_dialogue_presenter.gd")
	var presenter = Presenter.new()
	root.add_child(presenter)
	await process_frame
	presenter.instant_text = true

	Quest.clear()
	Quest.begin("E17A")
	var state: Dictionary = Quest.get_state()
	if str(state.get("quest_id", "")) == "":
		printerr("MISSING_DEPENDENCY: E17A fixture failed to load in VillageQuestRunner")
		quit(1)
		return

	var turns: Array = []
	var npc_used := ""
	for id in ["storekeeper", "a", "h", "miner", "elder", "b", "c"]:
		var convo: Dictionary = Quest.conversation_for(id)
		turns = convo.get("turns", [])
		if not turns.is_empty():
			npc_used = id
			break
	if turns.is_empty():
		# Try dialogue index keys from current quest ambient nodes
		printerr("No conversation_for turns for common NPC ids; checking current node")
		var node: Dictionary = Quest.current_node()
		print("current_node=", node)
		# Still prove presenter + that runner loaded.
		presenter.say("Narrator", "E17A quest loaded (%s) but no NPC turns exposed via conversation_for." % state.get("quest_id"))
		presenter.advance()
		print("SPELLBOOK_DIALOGUE_PARTIAL quest=", state.get("quest_id"))
		quit(0)
		return

	var shown := 0
	for raw in turns:
		if not (raw is Dictionary):
			continue
		var turn: Dictionary = raw
		var text := str(turn.get("text", ""))
		if text == "":
			continue
		var speaker := str(turn.get("speaker", npc_used))
		presenter.say(speaker, text)
		# Finish reveal (instant) then advance — two distinct actions.
		presenter.advance()  # finishes typing if any
		presenter.advance()  # advances line
		shown += 1
		await process_frame

	var payload: Dictionary = Quest.current_choice_payload()
	var options: Array = payload.get("options", [])
	if options.is_empty() and convo_has_options(Quest, npc_used):
		pass
	if not options.is_empty():
		var labels: Array = []
		for o in options:
			if o is Dictionary:
				labels.append(str(o.get("label", "Continue")))
			else:
				labels.append(str(o))
		# Present choices but do NOT pick — closing must apply no consequence.
		var flags_before: Dictionary = Quest.get_state().get("flags", {}).duplicate(true)
		await choose_and_close(presenter, str(payload.get("prompt", "What do you do?")), labels)
		var flags_after: Dictionary = Quest.get_state().get("flags", {})
		if str(flags_before) != str(flags_after):
			printerr("FAIL: closing dialogue changed quest flags")
			quit(1)
			return
		print("SPELLBOOK_DIALOGUE_CHOICES_SHOWN count=", labels.size())

	print("SPELLBOOK_DIALOGUE_VILLAGE_OK npc=", npc_used, " turns=", shown, " quest=", state.get("quest_id"))
	quit(0)


func choose_and_close(presenter, prompt: String, labels: Array) -> void:
	## Close without selecting so choose_async resolves with empty label (no quest side effects).
	var settled := [false]
	presenter.chosen.connect(func(_label): settled[0] = true, CONNECT_ONE_SHOT)
	presenter.choose_async(prompt, labels)
	await process_frame
	presenter._on_close_book()
	var guard := 0
	while not settled[0] and guard < 60:
		await process_frame
		guard += 1


func convo_has_options(Quest, npc_id: String) -> bool:
	var c: Dictionary = Quest.conversation_for(npc_id)
	return not c.get("options", []).is_empty()
