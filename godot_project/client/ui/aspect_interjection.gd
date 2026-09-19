extends RefCounted
class_name DmbAspectInterjection

## Biased Aspect passive voice for dialogue (C09 / T085).
## Reads only filtered context; does not invent verified facts.

const FALLIBILITY := {
	"reason": "overlooks emotion",
	"empathy": "overtrusts",
	"authority": "overvalues legitimacy",
	"guile": "suspects too much",
	"resolve": "persists unwisely",
	"curiosity": "discounts danger",
	"wonder": "overinterprets patterns",
}


static func line_for(aspect_id: String, filtered_context: Dictionary = {}) -> String:
	var aid := aspect_id.to_lower()
	var bias := str(FALLIBILITY.get(aid, "hesitates"))
	var label := str(filtered_context.get("label", filtered_context.get("role", "them")))
	# Never include hidden economy keys even if passed by mistake.
	if filtered_context.has("stocks") or filtered_context.has("army_strength"):
		label = str(filtered_context.get("label", "them"))
	match aid:
		"empathy":
			return "Your heart leans toward %s — and %s." % [label, bias]
		"guile":
			return "Something about %s feels off — you %s." % [label, bias]
		"curiosity":
			return "You want to know more about %s, even if you %s." % [label, bias]
		_:
			return "(%s: you %s.)" % [aid.capitalize(), bias]


static func is_legible(text: String, max_chars: int = 120) -> bool:
	var t := text.strip_edges()
	return t.length() > 0 and t.length() <= max_chars
