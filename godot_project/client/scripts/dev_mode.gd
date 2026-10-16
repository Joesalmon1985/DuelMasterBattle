extends RefCounted

## Developer-only switches. A normal player (and every Android build) never has these on: they come from the launching environment, which a phone
## cannot set, so the developer menu (the legacy adventure, Quick Duel, the G01 testing entry and the other test scenes) is not reachable by
## tapping around the game.


static func enabled() -> bool:
	if OS.has_feature("mobile"):
		return false
	if OS.get_environment("DMB_DEV_MENU") == "1":
		return true
	return OS.get_cmdline_user_args().has("--dmb-dev")


## The classic Wizard World server on 127.0.0.1 (scripts/launch_hybrid.*) instead of a private hosted session: how the developer launchers always ran.
static func classic_sim() -> bool:
	return OS.get_environment("DMB_CLASSIC_SIM") == "1" and not OS.has_feature("mobile")
