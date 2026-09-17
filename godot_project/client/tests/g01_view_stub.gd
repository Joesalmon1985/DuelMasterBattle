extends Node
## Tiny view stub for headless FX-CLOCK area construction tests.


func request_view(_scope: String = "player") -> Dictionary:
	return {
		"world_id": "world:g01",
		"world_version": 0,
		"player": {
			"node_id": "node:1",
			"area_id": "area.home",
			"position": [4, 5],
			"facing": "down",
			"pose_generation": 0,
		},
		"clock": {"turn": 0, "game_ms": 0, "paused": false},
		"board": {
			"nodes": {
				"node:1": {
					"id": "node:1",
					"label": "Home Clearing",
					"theme": "grass",
					"area_id": "area.home",
					"exits": {
						"node:2": {
							"exit_id": "home.east",
							"direction": "east",
							"hold_position": [12.0, 5.0],
							"hold_facing": "right",
							"arrival": {
								"node_id": "node:2",
								"area_id": "area.road",
								"position": [1.5, 5.0],
								"facing": "right",
							},
						}
					},
				},
				"node:2": {
					"id": "node:2",
					"label": "Stone Road",
					"theme": "path",
					"area_id": "area.road",
					"exits": {
						"node:1": {
							"exit_id": "road.west",
							"direction": "west",
							"hold_position": [1.0, 5.0],
							"hold_facing": "left",
							"arrival": {
								"node_id": "node:1",
								"area_id": "area.home",
								"position": [12.0, 5.0],
								"facing": "left",
							},
						}
					},
				},
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
