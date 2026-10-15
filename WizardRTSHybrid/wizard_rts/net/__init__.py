"""LAN multiplayer over the one authoritative HybridWorld (docs/MOBILE_LAN_MULTIPLAYER.md).

protocol.py  the wire contract and op whitelists      session.py  players, commands, views, PvP lifecycle
pvp.py       host-owned human-versus-human Ward duel  host.py     the TCP/UDP host loop and clock
client.py    a Python client of the same protocol      android_entry.py  what the Android plugin calls
"""
