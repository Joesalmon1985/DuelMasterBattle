extends SceneTree

func _initialize():
    var result = JSON.parse_string('{"test":1}')
    print("Result type: " + str(typeof(result)))
    print("Result: " + str(result))
    if result is Array:
        print("It's an array!")
        for i in result.size():
            print("  [" + str(i) + "] = " + str(result[i]))
    elif result is Dictionary:
        print("It's a dictionary!")
        for k in result.keys():
            print("  " + str(k) + " = " + str(result[k]))
    quit()