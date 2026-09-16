extends Node
## Tiny view stub for headless FX-CLOCK area construction tests.


func request_view(_scope: String = "player") -> Dictionary:
	return {
		"world_id": "world:g01",
		"world_version": 0,
		"player": {"node_id": "node:1", "position": [4, 5], "facing": "down"},
		"clock": {"turn": 0, "game_ms": 0, "paused": false},
		"board": {
			"nodes": {
				"node:1": {"id": "node:1", "label": "Home Clearing", "exits": ["node:2"], "theme": "grass"},
				"node:2": {"id": "node:2", "label": "Stone Road", "exits": ["node:1"], "theme": "path"},
			}
		},
		"people": {
			"person:1": {
				"entity_id": "person:1",
				"known": false,
				"label": "unknown",
				"name": null,
				"node_id": "node:1",
				"grid": [10, 3],
			}
		},
	}


func legacy_writers_blocked() -> bool:
	return true
