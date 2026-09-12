extends SceneTree

func _init():
    pass

func _initialize():
    var catalog = load("res://sim/world/village_test_catalog.gd").new()
    var discovered = catalog.discover()
    print("=== DISCOVERED VILLAGE FIXTURES ===")
    for m in discovered:
        print("ID: " + str(m["id"]))
        print("  Name: " + str(m.get("name", "N/A")))
        print("  Valid: " + str(m.get("valid", false)))
        print("  Economic Profile: " + str(m.get("economic_profile", "N/A")))
        print("  Cast Count: " + str(m.get("cast_count", 0)))
        print("  Quest Title: " + str(m.get("quest_title", "N/A")))
        print("  Node Count: " + str(m.get("node_count", 0)))
        print("  Regions: " + str(m.get("regions", [])))
        print("  Semantic Anchors: " + str(m.get("semantic_anchors", [])))
        print("  Errors: " + str(m.get("errors", [])))
        print()
    
    print("=== VALIDATION TEST ===")
    for m in discovered:
        if m["valid"]:
            var fixture = catalog.load_fixture(m["id"])
            if fixture:
                print(m["id"] + ": LOAD OK - village=" + str(fixture["village"].has("id")) + " cast=" + str(fixture["cast"].has("cast")) + " quest=" + str(fixture["quest"].has("nodes")) + " dialogue=" + str(fixture["dialogue"].has("dialogue")))
            else:
                print(m["id"] + ": LOAD FAILED")
        else:
            print(m["id"] + ": INVALID - " + str(m.get("errors", [])))
    
    quit()