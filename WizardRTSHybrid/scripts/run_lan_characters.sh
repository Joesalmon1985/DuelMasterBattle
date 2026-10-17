#!/usr/bin/env bash
# Headed LAN check of the character system: a Python host, a scripted second human (lan_bot.py) and the real Godot client.
# Usage: scripts/run_lan_characters.sh      Shots go to HYBRID_SHOT_DIR (default docs/evidence/characters).
set -u
HYB="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(dirname "$HYB")"
GODOT="${GODOT:-$HOME/godot451/Godot_v4.5.1-stable_linux.x86_64}"
export HYBRID_SHOT_DIR="${HYBRID_SHOT_DIR:-$HYB/docs/evidence/characters}"
mkdir -p "$HYBRID_SHOT_DIR"
port=$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1])")
CODE=1234; SECRET=headed-secret
LOG=/tmp/lan_chars_host_$port.log; BOT=/tmp/lan_chars_bot_$port.log
(cd "$HYB" && HYBRID_AI=1 DMB_NO_NATIVE=1 python3 -u -m wizard_rts.net.host --bind 127.0.0.1 --port "$port" --no-discovery --name headed --code $CODE --secret $SECRET --seed 507 --map small --stats-every 5 > "$LOG" 2>&1 & echo $! > /tmp/lan_chars_host_$port.pid)
for _i in $(seq 1 90); do grep -q HYBRID_HOST_READY "$LOG" 2>/dev/null && break; sleep 1; done
grep -q HYBRID_HOST_READY "$LOG" || { echo "FAIL host did not start"; tail -5 "$LOG"; kill "$(cat /tmp/lan_chars_host_$port.pid)" 2>/dev/null; exit 1; }
(cd "$HYB" && python3 -u scripts/lan_bot.py --host 127.0.0.1 --port "$port" --code $CODE --secret $SECRET --name Alice --start --seconds 300 > "$BOT" 2>&1 & echo $! > /tmp/lan_chars_bot_$port.pid)
out=$(env HYBRID_LAN_HOST=127.0.0.1 HYBRID_LAN_PORT=$port HYBRID_LAN_CODE=$CODE timeout "${TIMEOUT:-400}" "$GODOT" --path "$REPO/godot_project" --disable-vsync --resolution 720x1000 --script res://client/tests/run_lan_characters.gd 2>&1)
kill "$(cat /tmp/lan_chars_bot_$port.pid)" 2>/dev/null
kill "$(cat /tmp/lan_chars_host_$port.pid)" 2>/dev/null
echo "$out" | grep -E "^(ok|FAIL)|HYBRID_LAN|SCRIPT ERROR" | head -40
if echo "$out" | grep -q HYBRID_LAN_CHARACTERS_OK; then echo "PASS lan characters"; exit 0; fi
echo "FAIL lan characters"; echo "$out" | grep -v "^$" | tail -15; exit 1
