"""The LAN multiplayer wire contract: newline-delimited JSON over TCP, one request -> one reply, platform-neutral.

Versioning: a client sends `protocol` (this integer) and `game` (the game version string) in `hello`; the host rejects a
different `protocol` outright and a different `game` unless the compatibility rule below allows it. Bump PROTOCOL_VERSION
when a message changes shape; bump GAME_VERSION with every release of the app.
"""

from __future__ import annotations

PROTOCOL_VERSION = 4  # 4: the village minigames (minigame_act/leave/view, the `minigame` extra on a choice, the journal's games); 3: mortal apprentices (dead/body/resurrection/ending in the state view), the Trial ops and view, the catch-up page; 2: real-time PvP casts, the narrative ops, single-player save/continue
GAME_VERSION = "0.6.0"  # the app version the APK is built from (also in godot_project/export_presets.cfg version/name)

DEFAULT_PORT = 8765
DISCOVERY_PORT = 8767
DISCOVERY_MAGIC = "DMB_DISCOVER"
MAX_LINE_BYTES = 1 << 20  # a request line larger than this closes the connection
DEFAULT_VIEW_RADIUS = 36  # tiles each way: what a phone receives around its own wizard (the camera sees ~24 x 14 at the default zoom)

# What a connected, authenticated player may ask for. Nothing here moves the clock, commands a faction, spawns, damages or
# reads God Mode views; those server ops are never reachable through the host, whatever the world profile.
PLAYER_OPS = frozenset({
    "ping", "lobby", "start", "state", "move", "leave",
    "terrain", "tile", "resources", "profile", "tech", "cards", "menu",  # read-only world views
    "interact", "resolve", "fire",  # the wizard's own actions (hazard duel lease, fire magic)
    "treat", "talk", "choose", "enter", "dungeon_move", "dungeon_interact", "duel_begin", "duel_guess", "duel_abandon", "story_view",  # story.WIZARD_OPS
    "duel_resolve", "duel_checkpoint", "end_talk", "opening_done", "journal", "call_out", "inspect_building", "inspect_person", "scene_next", "scene_choose",  # the narrative ops (Wizard World)
    "resurrect",  # bring a dead wizard back: a channel beside the body (narrative/mortality.py)
    "pest_fight",  # fight a warehouse rat standing beside it (narrative/pests.py)
    "trial_enter", "trial_move", "trial_interact", "trial_choose", "trial_leave", "trial_view",  # the Trial of Champions (wizard_rts/trial)
    "minigame_act", "minigame_leave", "minigame_view",  # a game at a conversation (wizard_rts/minigames): nothing in the world moves because of it
    "teleport", "trial_teleport",  # headed tests only: the host must run with HYBRID_DEV_OPS=1 (session.py refuses them otherwise)
    "save", "new_game",  # a single-player session only (session._solo_op); a shared world has no save slot of its own
    "pvp_challenge", "pvp_respond", "pvp_ward", "pvp_cast", "pvp_forfeit", "pvp_leave", "pvp_view",
})
PRE_HELLO_OPS = frozenset({"hello", "info", "ping"})
PASSTHROUGH_OPS = frozenset({"terrain", "tile", "resources", "profile", "tech", "cards", "menu", "interact", "resolve", "fire",
                             "treat", "talk", "choose", "enter", "dungeon_move", "dungeon_interact", "duel_begin", "duel_guess", "duel_abandon", "story_view",
                             "duel_resolve", "duel_checkpoint", "end_talk", "opening_done", "journal", "call_out", "inspect_building", "inspect_person",
                             "scene_next", "scene_choose", "resurrect", "pest_fight", "trial_enter", "trial_move", "trial_interact", "trial_choose", "trial_leave", "trial_view",
                             "minigame_act", "minigame_leave", "minigame_view"})
HOST_ONLY_OPS = frozenset({"start", "save", "new_game"})
SOLO_OPS = frozenset({"save", "new_game"})  # allowed only while the session is a one-human private game (max_players == 1)


def game_compatible(client_game: str) -> bool:
    """Same major.minor is compatible (patch releases keep the protocol)."""
    try:
        a = GAME_VERSION.split(".")[:2]
        b = str(client_game).split(".")[:2]
        return a == b
    except Exception:  # noqa: BLE001
        return False
