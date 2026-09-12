extends SceneTree

func _init():
    pass

func _initialize() -> void:
    var Catalog = preload("res://sim/world/village_test_catalog.gd")
    var fixtures = Catalog.discover()
    print("=== DISCOVERED FIXTURES ===")
    for f in fixtures:
        print("ID: %s, Name: %s, Valid: %s" % [f["id"], f["name"], f["valid"]])
        if not f["valid"]:
            print("  ERRORS: %s" % f["errors"])
    print("=== DONE ===")
    quit()