extends RefCounted
class_name DungeonWorldTestRunner
## Disposable Dungeon World Playtest session authority.
## Isolates campaign story (no prologue / Trial Day / Halvard) while the
## fixture runs. Owns the fixture sim reference and the embedded PuzzleKit
## state for the current dungeon-bearing world node — without converting that
## node into a detached puzzle-test level.

const Fixture = preload("res://sim/world/dungeon_world_fixture.gd")
const Emb = preload("res://sim/world/embedded_dungeon.gd")
const Spec = preload("res://sim/world/wizard_dungeon_spec.gd")

const PROFILE := "FX-DUNGEON-WORLD"
const DEFAULT_SEED := 507
const DEFAULT_SIZE := Vector2i(73, 55)

static var active := false
static var fixture = null
static var node_size: Vector2i = DEFAULT_SIZE
static var home_node: int = -1
static var playtest_node: int = -1
static var playtest_type: String = "GW"
static var playtest_reason: String = ""
static var playtest_terrains: Array = []
static var natural_types: Array = []
static var show_test_labels := false
static var show_dungeon_bounds := false
static var tools_open := false
static var intro_seen := false

static var _kit_room: Dictionary = {}
static var _kit_state: Dictionary = {}
static var _kit_node: int = -1
static var _saved_adv_state: Dictionary = {}
static var _saved_adv_prog: Dictionary = {}
static var _has_saved := false
static var _pending := false


static func has_pending() -> bool:
	return _pending and not active


static func is_active() -> bool:
	return active


static func isolates_campaign_story() -> bool:
	return active


static func has_kit() -> bool:
	return not _kit_room.is_empty() and _kit_node >= 0


## True when the loaded area is the dungeon-bearing node with live kit state.
static func kit_active_for_area(area: Dictionary) -> bool:
	return active and has_kit() and int(area.get("fixture_node", -1)) == _kit_node


static func kit_room() -> Dictionary:
	return _kit_room


static func kit_state() -> Dictionary:
	return _kit_state


static func kit_node() -> int:
	return _kit_node


static func prepare(seed: int = DEFAULT_SEED, size: Vector2i = DEFAULT_SIZE) -> void:
	clear()
	node_size = size
	fixture = Fixture.new()
	fixture.setup(seed)
	home_node = fixture.sim.player_home_node()
	_choose_playtest_destination()
	_pending = true
	DmbSettlementLayout.FORCE_DIMS = node_size
	WorldFlow.test_augment = _augment_area


static func begin(adv: Node) -> Vector2i:
	if fixture == null:
		prepare()
	_saved_adv_state = (adv.state as Dictionary).duplicate(true)
	_saved_adv_prog = adv.progression.to_dict()
	_has_saved = true
	adv.test_mode = true
	adv.delete_save()
	adv.new_game()
	# Explicit isolation contract: disposable John inspection, not campaign.
	# Do not enumerate story flags — park phase past prologue/trial and mark
	# opening seen so Overworld will not fire cutscenes.
	if not adv.state.has("story") or not (adv.state["story"] is Dictionary):
		adv.state["story"] = {}
	adv.state["story"]["protagonist"] = "john"
	adv.state["story"]["phase"] = "post_trial_recovery"
	adv.set_flag("opening_seen")
	adv.set_flag("jane_placeholder_seen")
	adv.state["dungeon_world_test"] = true
	adv.state["world_seed"] = fixture.seed
	adv.state["world"] = var_to_str(fixture.sim.to_dict())
	adv.state["world_node"] = home_node
	adv.state["area"] = DmbNodeProjection.area_id(home_node)
	# Spells for optional combat; not required for the three puzzles.
	for sid in [0, 1, 6]:
		adv.learn_spell(sid)
	active = true
	_pending = false
	DmbSettlementLayout.FORCE_DIMS = node_size
	WorldFlow.test_augment = _augment_area
	var area: Dictionary = DmbNodeProjection.area_for(fixture.sim, home_node, adv.state)
	area = _augment_area(area, home_node)
	var start: Array = area.get("player_start", [node_size.x / 2, node_size.y / 2])
	# Prefer plaza / home_door if present.
	var layout: Dictionary = area.get("layout", {})
	if layout.has("plaza"):
		var pl: Array = layout["plaza"]
		if pl.size() >= 4:
			start = [int(pl[0]) + int(pl[2]) / 2, int(pl[1]) + int(pl[3]) / 2]
	if area.has("home_door") and (area.get("home_door") as Array).size() >= 2:
		var hd: Array = area["home_door"]
		start = [int(hd[0]), int(hd[1]) + 1]
	adv.state["pos"] = [int(start[0]), int(start[1])]
	adv.state["facing"] = "down"
	adv.set_location(DmbNodeProjection.area_id(home_node), int(start[0]), int(start[1]), "down")
	return Vector2i(int(start[0]), int(start[1]))


static func end(adv: Node) -> void:
	if _has_saved:
		adv.state = _saved_adv_state.duplicate(true)
		adv.progression = DmbProgression.from_dict(_saved_adv_prog.duplicate(true))
		adv.state_changed.emit()
	_has_saved = false
	_saved_adv_state = {}
	_saved_adv_prog = {}
	adv.test_mode = false
	clear()


static func clear() -> void:
	active = false
	_pending = false
	fixture = null
	home_node = -1
	playtest_node = -1
	_kit_room = {}
	_kit_state = {}
	_kit_node = -1
	intro_seen = false
	tools_open = false
	show_test_labels = false
	show_dungeon_bounds = false
	DmbSettlementLayout.FORCE_DIMS = Vector2i.ZERO
	WorldFlow.test_augment = Callable()


static func reset_dungeon(adv: Node) -> void:
	if not has_kit():
		return
	_kit_state = DmbPuzzleKit.fresh_state(_kit_room)
	DmbPuzzleKit.sync_inventory(_kit_state, adv.items())


static func reset_world(adv: Node) -> Vector2i:
	var seed: int = fixture.seed if fixture else DEFAULT_SEED
	var size := node_size
	end(adv)
	prepare(seed, size)
	return begin(adv)


## Pick lowest-id adjacent node with a natural dungeon type; assign GW as the
## fixture playtest dungeon (explicit fixture-only mapping — production terrain
## rules unchanged). Natural types are recorded for debug.
static func _choose_playtest_destination() -> void:
	var nbs: Array = fixture.sim.board.node_neighbors(home_node)
	nbs.sort()
	playtest_node = -1
	natural_types = []
	playtest_terrains = []
	playtest_reason = ""
	for nid in nbs:
		if fixture.sim.catan.settlements.has(nid):
			continue
		var types: Array = Fixture.types_for_node(fixture.sim.board, nid)
		if types.is_empty():
			continue
		playtest_node = int(nid)
		natural_types = types.duplicate()
		playtest_terrains = Fixture.terrains_at(fixture.sim.board, int(nid))
		playtest_type = "GW"
		playtest_reason = "direct neighbor of home %d; natural types %s on terrains %s; fixture assigns GW Rootbound Sanctuary for the three-puzzle playtest (no forest neighbor on seed %d)" % [
			home_node, str(types), str(playtest_terrains), fixture.seed]
		break
	if playtest_node < 0:
		# Fallback: any non-settlement neighbor.
		for nid in nbs:
			playtest_node = int(nid)
			playtest_type = "GW"
			playtest_terrains = Fixture.terrains_at(fixture.sim.board, int(nid))
			playtest_reason = "fallback neighbor %d; fixture-only GW assignment" % playtest_node
			break


static func _augment_area(area: Dictionary, nid: int) -> Dictionary:
	if not active and not _pending:
		return area
	DmbSettlementLayout.FORCE_DIMS = node_size
	var sized: Dictionary = DmbNodeProjection.area_for(fixture.sim, nid, {})
	# Re-apply FORCE for subsequent queries.
	DmbSettlementLayout.FORCE_DIMS = node_size
	sized["dungeon_world_test"] = true
	sized["fixture_node"] = nid
	if nid == playtest_node:
		var emb: Dictionary = Emb.stamp(sized, playtest_type, true)
		sized["embedded_dungeon"] = emb
		sized["fixture_types"] = [playtest_type]
		sized["playtest_primary"] = true
		if str(emb.get("fit", "")) == "OK" and emb.has("kit_room"):
			_bind_kit(nid, emb["kit_room"])
			_merge_kit_projection(sized)
		_strip_debug(sized)
	else:
		# Optional visual dungeon for other candidates — non-interactive.
		# Kit state for the playtest node persists across visits this session.
		var code: String = fixture.primary_type_for(nid)
		if code != "" and nid != home_node:
			var emb2: Dictionary = Emb.stamp(sized, code, false)
			sized["embedded_dungeon"] = emb2
			sized["fixture_types"] = fixture.types_for(nid)
		_strip_debug(sized)
	return sized


static func _bind_kit(nid: int, room: Dictionary) -> void:
	if _kit_node == nid and not _kit_state.is_empty():
		# Keep puzzle progress; refresh entity geometry from the new stamp.
		var keep: Dictionary = _kit_state.duplicate(true)
		_kit_room = room.duplicate(true)
		_kit_state = keep
		return
	_kit_node = nid
	_kit_room = room.duplicate(true)
	_kit_state = DmbPuzzleKit.fresh_state(_kit_room)


static func sync_inventory(items: Array) -> void:
	if has_kit():
		DmbPuzzleKit.sync_inventory(_kit_state, items)


static func reproject_area(area: Dictionary) -> Dictionary:
	if not has_kit():
		return area
	# Update kit rows from current area geometry if present.
	if area.has("rows"):
		_kit_room["rows"] = []
		for line in area["rows"]:
			_kit_room["rows"].append(str(line))
	_merge_kit_projection(area)
	_apply_water_visuals(area)
	_strip_debug(area)
	return area


static func _merge_kit_projection(area: Dictionary) -> void:
	var projected: Dictionary = DmbPuzzleProjection.area_for(_kit_room, _kit_state)
	# Kit owns dungeon tile art (gates open/closed).
	area["rows"] = projected["rows"]
	var kept: Array = []
	var emb: Dictionary = area.get("embedded_dungeon", {})
	var origin: Array = emb.get("origin", [0, 0])
	var ox := int(origin[0]) if origin.size() >= 2 else 0
	var oy := int(origin[1]) if origin.size() >= 2 else 0
	var res := Rect2i(ox, oy, Spec.RESERVATION_W, Spec.RESERVATION_H)
	for e in area.get("entities", []):
		if bool(e.get("embedded_puzzle", false)):
			continue
		if str(e.get("kind", "")) == "debug_label":
			continue
		# Drop exterior props that sit inside the dungeon footprint.
		var p: Array = e.get("pos", [])
		if p.size() >= 2 and res.has_point(Vector2i(int(p[0]), int(p[1]))):
			if str(e.get("kind", "")) != "exit":
				continue
		kept.append(e)
	for e in projected.get("entities", []):
		var pe: Dictionary = e.duplicate(true)
		pe["embedded_puzzle"] = true
		kept.append(pe)
	# Landmark outside the approach so the ruin reads outdoors.
	if emb.has("approach"):
		var ap: Array = emb["approach"]
		kept.append({
			"kind": "sign", "id": "dungeon_landmark", "pos": [int(ap[0]), maxi(0, int(ap[1]) - 2)],
			"marker": "door_dungeon",
			"text": "A rootbound ruin opens into the land. Paths lead in. No door closes behind you.",
		})
	area["entities"] = kept


static func _apply_water_visuals(area: Dictionary) -> void:
	if not bool(_kit_state.get("flags", {}).get("gw_water_restored", false)):
		return
	var emb: Dictionary = area.get("embedded_dungeon", {})
	var rooms: Array = emb.get("rooms", [])
	if rooms.size() < 3:
		return
	# Room 3 (index 2) — tint a channel strip as water when restored.
	var r: Dictionary = rooms[2]
	var rect: Array = r.get("rect", [])
	if rect.size() < 4:
		return
	var rows: Array = area["rows"]
	var y := int(rect[1]) + int(rect[3]) / 2
	for x in range(int(rect[0]) + 2, int(rect[0]) + int(rect[2]) - 2):
		if y >= 0 and y < rows.size():
			var line: String = rows[y]
			if x >= 0 and x < line.length() and line[x] in [".", ",", ":"]:
				rows[y] = line.substr(0, x) + "~" + line.substr(x + 1)
	area["rows"] = rows
	if has_kit():
		_kit_room["rows"] = rows.duplicate()


static func _strip_debug(area: Dictionary) -> void:
	if show_test_labels and show_dungeon_bounds:
		return
	var ents: Array = []
	for e in area.get("entities", []):
		if str(e.get("kind", "")) == "debug_label":
			if not show_test_labels and not show_dungeon_bounds:
				continue
			var t := str(e.get("text", ""))
			if not show_dungeon_bounds and (t.begins_with("DUNGEON:") or t.begins_with("R")):
				continue
			if not show_test_labels:
				continue
		ents.append(e)
	area["entities"] = ents


static func kit_blocks(pos: Vector2i) -> bool:
	if not has_kit():
		return false
	return DmbPuzzleKit.blocks(_kit_room, _kit_state, pos)


static func playtest_info() -> String:
	return "Home wn_%d → dungeon wn_%d (%s)\n%s" % [home_node, playtest_node, playtest_type, playtest_reason]
