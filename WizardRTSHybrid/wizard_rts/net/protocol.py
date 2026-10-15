"""The LAN multiplayer wire contract: newline-delimited JSON over TCP, one request -> one reply, platform-neutral.

Versioning: a client sends `protocol` (this integer) and `game` (the game version string) in `hello`; the host rejects a
different `protocol` outright and a different `game` unless the compatibility rule below allows it. Bump PROTOCOL_VERSION
when a message changes shape; bump GAME_VERSION with every release of the app.
"""

from __future__ import annotations

PROTOCOL_VERSION = 1
GAME_VERSION = "0.1.0"  # the app version the APK is built from (also in godot_project/export_presets.cfg version/name)

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
    "pvp_challenge", "pvp_respond", "pvp_ward", "pvp_cast", "pvp_forfeit", "pvp_leave", "pvp_view",
})
PRE_HELLO_OPS = frozenset({"hello", "info", "ping"})
PASSTHROUGH_OPS = frozenset({"terrain", "tile", "resources", "profile", "tech", "cards", "menu", "interact", "resolve", "fire",
                             "treat", "talk", "choose", "enter", "dungeon_move", "dungeon_interact", "duel_begin", "duel_guess", "duel_abandon", "story_view"})
HOST_ONLY_OPS = frozenset({"start"})


def game_compatible(client_game: str) -> bool:
    """Same major.minor is compatible (patch releases keep the protocol)."""
    try:
        a = GAME_VERSION.split(".")[:2]
        b = str(client_game).split(".")[:2]
        return a == b
    except Exception:  # noqa: BLE001
        return False
