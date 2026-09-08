extends Node
class_name DmbSfx

## Tiny procedural sound effects (no audio files needed).
## Autoloaded as `Sfx`. Respects the "sound" setting.

const _SaveData = preload("res://client/scripts/save_data.gd")

const SAMPLE_RATE := 22050

var _players: Array = []
var _cache: Dictionary = {}


func _ready() -> void:
	for _i in range(6):
		var p := AudioStreamPlayer.new()
		p.bus = "Master"
		add_child(p)
		_players.append(p)


func enabled() -> bool:
	return bool(_SaveData.get_setting("sound", true))


func tap() -> void:
	_play("tap", 0.5)


func place() -> void:
	_play("place", 0.6)


func clear_slot() -> void:
	_play("clear", 0.45)


func ready_chime() -> void:
	_play("ready", 0.6)


func cast() -> void:
	_play("cast", 0.7)


func rival_cast() -> void:
	_play("rival", 0.55)


func fracture(count: int) -> void:
	_play("fracture%d" % clampi(count, 0, 4), 0.65)


func warning_tick() -> void:
	_play("tick", 0.5)


func victory() -> void:
	_play("victory", 0.8)


func defeat() -> void:
	_play("defeat", 0.8)


func denied() -> void:
	_play("denied", 0.5)


func _play(kind: String, volume: float) -> void:
	if not enabled():
		return
	var stream: AudioStreamWAV = _cache.get(kind)
	if stream == null:
		stream = _build(kind)
		_cache[kind] = stream
	for p in _players:
		if not p.playing:
			p.stream = stream
			p.volume_db = linear_to_db(volume)
			p.play()
			return
	_players[0].stream = stream
	_players[0].volume_db = linear_to_db(volume)
	_players[0].play()


func _build(kind: String) -> AudioStreamWAV:
	var notes: Array = []
	match kind:
		"tap":
			notes = [[880.0, 0.04, "sine"]]
		"place":
			notes = [[660.0, 0.05, "sine"], [990.0, 0.06, "sine"]]
		"clear":
			notes = [[520.0, 0.05, "sine"], [390.0, 0.06, "sine"]]
		"ready":
			notes = [[784.0, 0.08, "sine"], [1046.0, 0.08, "sine"], [1318.0, 0.14, "sine"]]
		"cast":
			notes = [[300.0, 0.05, "saw"], [600.0, 0.06, "saw"], [1200.0, 0.12, "saw"]]
		"rival":
			notes = [[500.0, 0.06, "square"], [350.0, 0.10, "square"]]
		"fracture0":
			notes = [[260.0, 0.14, "sine"]]
		"fracture1":
			notes = [[523.0, 0.10, "sine"]]
		"fracture2":
			notes = [[523.0, 0.08, "sine"], [659.0, 0.10, "sine"]]
		"fracture3":
			notes = [[523.0, 0.07, "sine"], [659.0, 0.07, "sine"], [784.0, 0.12, "sine"]]
		"fracture4":
			notes = [[523.0, 0.07, "sine"], [659.0, 0.07, "sine"], [784.0, 0.07, "sine"], [1046.0, 0.2, "sine"]]
		"tick":
			notes = [[1200.0, 0.03, "square"]]
		"victory":
			notes = [[523.0, 0.12, "sine"], [659.0, 0.12, "sine"], [784.0, 0.12, "sine"], [1046.0, 0.35, "sine"]]
		"defeat":
			notes = [[392.0, 0.16, "saw"], [330.0, 0.16, "saw"], [262.0, 0.4, "saw"]]
		"denied":
			notes = [[220.0, 0.06, "square"], [200.0, 0.08, "square"]]
		_:
			notes = [[440.0, 0.05, "sine"]]
	return _synth(notes)


func _synth(notes: Array) -> AudioStreamWAV:
	var total := 0.0
	for n in notes:
		total += float(n[1])
	var frames := int(total * SAMPLE_RATE)
	var data := PackedByteArray()
	data.resize(frames * 2)
	var idx := 0
	var t_note := 0.0
	for n in notes:
		var freq := float(n[0])
		var dur := float(n[1])
		var wave := str(n[2])
		var count := int(dur * SAMPLE_RATE)
		for i in range(count):
			var t := float(i) / SAMPLE_RATE
			var env := minf(1.0, t / 0.005) * (1.0 - t / dur)
			var phase := fmod(t * freq, 1.0)
			var s := 0.0
			match wave:
				"square":
					s = 1.0 if phase < 0.5 else -1.0
				"saw":
					s = phase * 2.0 - 1.0
				_:
					s = sin(phase * TAU)
			var v := int(clampf(s * env * 0.5, -1.0, 1.0) * 32767.0)
			if idx * 2 + 1 < data.size():
				data.encode_s16(idx * 2, v)
			idx += 1
		t_note += dur
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = SAMPLE_RATE
	stream.stereo = false
	stream.data = data
	return stream
