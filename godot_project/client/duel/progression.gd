extends RefCounted
class_name DmbDuelProgression

## Client helper for authored DmbBattleSim progression (T091).
## Does not own duel secrets or outcomes — Python lease + BattleSim do.

const RULES_PATH := "res://content/source/duel_rules/progression.json"


static func load_rules() -> Dictionary:
	if not FileAccess.file_exists(RULES_PATH):
		return {}
	var f := FileAccess.open(RULES_PATH, FileAccess.READ)
	if f == null:
		return {}
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	return parsed


static func tier_for_era(era: String) -> Dictionary:
	var rules := load_rules()
	var binding: Dictionary = rules.get("era_binding", {})
	var tier_id := str(binding.get(era, rules.get("baseline", {}).get("id", "duel.baseline_c10")))
	for tier in rules.get("progression", []):
		if str(tier.get("id", "")) == tier_id:
			return tier
	return rules.get("baseline", {})


static func score_guess(secret: Array, guess: Array) -> Vector2i:
	## Mirror C10 multiplicity scoring used by DmbFeedback / retained BattleSim.
	return DmbFeedback.score_guess(secret, guess)


static func caps() -> Dictionary:
	var rules := load_rules()
	return rules.get("supported_caps", {"max_slot_count": 6, "max_colour_count": 8})


static func overflow_reward() -> Dictionary:
	var rules := load_rules()
	return rules.get("overflow_reward", {})
