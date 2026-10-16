extends SceneTree

## Loads imported Widelands/OpenRA art the way an Android export must: from the packaged, imported resources only.
## Run it against the project (`--path godot_project --script ...`) or, to prove the packaged behaviour, against an exported
## pack: `godot --headless --export-pack "Android Client" build/probe.pck` then
## `godot --headless --main-pack build/probe.pck --script res://client/tests/run_art_export_probe.gd`
## (a pack has no source PNGs, exactly like the APK). Prints ART_PROBE_OK or ART_PROBE_FAIL.

const HybridArt = preload("res://client/hybrid/hybrid_art.gd")
const AssetLoader = preload("res://client/scripts/asset_loader.gd")

# One of each kind the phones draw: terrain, a Widelands building, a worker, an animated worker sheet, an OpenRA unit with
# 32 facings (hull and turret layers), an OpenRA building with construction/damage states.
# The Trial's zones are the legacy pixel art (plan M5/M6): cave tiles, props, people, creatures and the pest sprites must load from a pack too.
const TRIAL_PIXEL := ["res://assets/pixel/tiles/ash.png", "res://assets/pixel/tiles/bridge.png", "res://assets/pixel/tiles/cave_floor.png", "res://assets/pixel/tiles/cave_wall.png", "res://assets/pixel/tiles/grass.png", "res://assets/pixel/tiles/path.png", "res://assets/pixel/tiles/water.png", "res://assets/pixel/props/book_black.png", "res://assets/pixel/props/book_red.png", "res://assets/pixel/props/box.png", "res://assets/pixel/props/diamond.png", "res://assets/pixel/props/door_dungeon.png", "res://assets/pixel/props/fire_0.png", "res://assets/pixel/props/idol.png", "res://assets/pixel/props/mirror.png", "res://assets/pixel/props/pendant.png", "res://assets/pixel/props/ring.png", "res://assets/pixel/props/seed.png", "res://assets/pixel/props/sign.png", "res://assets/pixel/props/staff.png", "res://assets/pixel/props/stalagmite.png", "res://assets/pixel/props/stone_shard.png", "res://assets/pixel/chars/assassin_down_0.png", "res://assets/pixel/chars/blue_mage_down_0.png", "res://assets/pixel/chars/dwarf_down_0.png", "res://assets/pixel/chars/elder_down_0.png", "res://assets/pixel/chars/elf_down_0.png", "res://assets/pixel/chars/hedge_mage_down_0.png", "res://assets/pixel/chars/igbut_down_0.png", "res://assets/pixel/chars/ivy_down_0.png", "res://assets/pixel/chars/knight_down_0.png", "res://assets/pixel/chars/official_down_0.png", "res://assets/pixel/chars/red_mage_down_0.png", "res://assets/pixel/chars/throm_down_0.png", "res://assets/pixel/chars/villager_a_down_0.png", "res://assets/pixel/chars/villager_b_down_0.png", "res://assets/pixel/creatures/bloodbeast_world_0.png", "res://assets/pixel/creatures/boa_constrictor_world_0.png", "res://assets/pixel/creatures/cave_troll_world_0.png", "res://assets/pixel/creatures/flying_guardian_world_0.png", "res://assets/pixel/creatures/giant_fly_world_0.png", "res://assets/pixel/creatures/guard_dog_world_0.png", "res://assets/pixel/creatures/manticore_world_0.png", "res://assets/pixel/creatures/mirror_demon_world_0.png", "res://assets/pixel/creatures/rock_grub_world_0.png"]
const PROBE_IDS := ["widelands.meadow1", "widelands.road", "openra.1tnk", "openra.afld", "openra.e1"]


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	print("ART_PROBE_FAIL %s" % msg)
	quit(1)


func _run() -> void:
	var art := HybridArt.new()
	art.load_catalogue()
	if art.items.is_empty():
		_fail("catalogue empty (catalogue.json not packaged?)")
		return
	if art.missing.size() > 0:
		_fail("catalogue references resources the package does not hold: %s" % str(art.missing.slice(0, 12)))
		return
	var loaded := 0
	var kinds := {"sheet": 0, "sequence": 0}
	for id in art.items.keys():
		var item: Dictionary = art.items[id]
		var mode := str(item.get("mode", ""))
		var key := str(id)
		if mode == "sequence":
			var frames: Array = item.get("frames_godot", [])
			if frames.is_empty():
				continue
			key = str(frames[0])
		var tex: Texture2D = art._tex(key)
		if tex == null or tex.get_width() <= 0 or tex.get_height() <= 0:
			_fail("%s (%s) did not load" % [id, key])
			return
		loaded += 1
		kinds[mode] = int(kinds.get(mode, 0)) + 1

	for id in PROBE_IDS:
		if not art.items.has(id):
			continue
		var item: Dictionary = art.items[id]
		var key := str(id)
		if str(item.get("mode", "")) == "sequence":
			key = str(item["frames_godot"][0])
		if art._tex(key) == null:
			_fail("probe %s did not load" % id)
			return
	for p in TRIAL_PIXEL:
		var t: Texture2D = AssetLoader.load_texture(str(p))
		if t == null or t.get_width() <= 0:
			_fail("Trial pixel art did not load: %s" % str(p))
			return
	for pest in ["mindustry.unit.crawler", "mindustry.unit.dagger"]:
		if not art.items.has(pest) or art._tex(pest) == null:
			_fail("the warehouse rats' sprite %s did not load" % pest)
			return
	print("ART_PROBE_TRIAL %d pixel files" % TRIAL_PIXEL.size())
	# An animated sheet really advances: the source rectangle moves with time.
	var animated := ""
	for id in art.items.keys():
		var it: Dictionary = art.items[id]
		if str(it.get("mode", "")) == "sheet" and int(it.get("frames", 1)) > 1 and int(it.get("fps", 0)) > 0 and art._tex(str(id)) != null:
			animated = str(id)
			break
	if animated == "":
		_fail("no animated sheet found")
		return
	# Two state frames of a building through the state path (decoded on first use, registered lazily).
	var state_frames := 0
	for id in art.items.keys():
		var st: Dictionary = art.items[id].get("states", {})
		for s in st.keys():
			for f in st[s].get("files", []):
				if AssetLoader.load_texture(str(f)) == null:
					_fail("state frame %s of %s did not load" % [f, id])
					return
				state_frames += 1
				break
			if state_frames > 60:
				break
		if state_frames > 60:
			break
	# The legacy duel art goes through the same loader.
	var DmbArtScript = load("res://client/scripts/art.gd")
	var legacy_missing := 0
	for p in DmbArtScript.expected_asset_paths():
		if DmbArtScript.load_texture(str(p)) == null:
			legacy_missing += 1
	print("ART_PROBE_STATS items=%d loaded=%d sheets=%d sequences=%d animated=%s state_frames=%d legacy_missing=%d" % [art.items.size(), loaded, kinds["sheet"], kinds["sequence"], animated, state_frames, legacy_missing])
	if legacy_missing > 0:
		_fail("%d legacy duel images did not load" % legacy_missing)
		return
	# Control: in a pack the source PNG is absent, which is exactly why the old Image.load path drew nothing on the phones.
	var sample := "res://client/hybrid/art/openra/1tnk-0000.png"
	var raw := Image.load_from_file(sample)
	print("ART_PROBE_CONTROL source_png_readable=%s imported_texture_loads=%s" % [str(raw != null and not raw.is_empty()), str(AssetLoader.load_texture(sample) != null)])
	print("ART_PROBE_OK")
	quit(0)
