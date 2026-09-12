extends SceneTree

func _init():
    pass

func _initialize() -> void:
    var area = VillageCompositeProjection.project("E17A")
    print("=== E17A PROJECTION ===")
    print("ID: " + area["id"])
    print("Name: " + area["name"])
    print("Theme: " + area["theme"])
    print("Player Start: " + str(area["player_start"]))
    print("Regions: " + str(area["regions"].keys()))
    print("Semantic Anchors: " + str(area["semantic_anchors"].keys()))
    print("Entities: " + str(area["entities"].size()))
    for e in area["entities"]:
        print("  " + e["kind"] + ": " + e["id"] + " at " + str(e["pos"]))
    print("Rows: " + str(area["rows"].size()) + " x " + str(str(area["rows"][0]).length()))
    
    # Print a sample of the map
    print("\n=== MAP SAMPLE (top-left 80x30) ===")
    for y in range(min(30, area["rows"].size())):
        var row = str(area["rows"][y])
        print(row.substr(0, min(80, row.length())))
    
    var validation = VillageCompositeProjection.validate_projection(area)
    print("\n=== VALIDATION ===")
    print("Valid: " + str(validation["valid"]))
    if not validation["valid"]:
        for err in validation["errors"]:
            print("  ERROR: " + err)
    print("Width: " + str(validation["width"]) + ", Height: " + str(validation["height"]))
    print("=== DONE ===")
    quit()