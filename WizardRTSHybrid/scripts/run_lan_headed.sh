#!/usr/bin/env bash
# Headed LAN acceptance on one machine: a Python host, a scripted second human (lan_bot.py, playing the host's wizard),
# and the real Godot client joining over TCP. Usage: scripts/run_lan_headed.sh [two_clients|mortality|trial|parse]
# GODOT defaults to ~/godot451/Godot_v4.5.1-stable_linux.x86_64. Shots go to HYBRID_SHOT_DIR (default docs/evidence/lan).
set -u
HYB="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(dirname "$HYB")"
GODOT="${GODOT:-$HOME/godot451/Godot_v4.5.1-stable_linux.x86_64}"
export HYBRID_SHOT_DIR="${HYBRID_SHOT_DIR:-$HYB/docs/evidence/lan}"
mkdir -p "$HYBRID_SHOT_DIR"
WHICH="${1:-two_clients}"
if [ "$WHICH" = parse ]; then
  out=$(timeout 300 "$GODOT" --path "$REPO/godot_project" --rendering-method forward_plus --script res://client/tests/run_lan_parse.gd 2>&1)
  echo "$out" | grep -E "HYBRID_LAN|parsed" ; echo "$out" | grep -q HYBRID_LAN_PARSE_OK && { echo "PASS parse"; exit 0; } || { echo "FAIL parse"; exit 1; }
fi
port=$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1])")
CODE=1234; SECRET=headed-secret
LOG=/tmp/lan_host_$port.log; BOT=/tmp/lan_bot_$port.log
DEV_OPS=0; if [ "$WHICH" = trial ]; then DEV_OPS=1; fi
(cd "$HYB" && HYBRID_AI=1 DMB_NO_NATIVE=1 HYBRID_DEV_OPS=$DEV_OPS python3 -u -m wizard_rts.net.host --bind 127.0.0.1 --port "$port" --no-discovery --name headed --code $CODE --secret $SECRET --seed 507 --map small --stats-every 5 > "$LOG" 2>&1 & echo $! > /tmp/lan_host_$port.pid)
for _i in $(seq 1 90); do grep -q HYBRID_HOST_READY "$LOG" 2>/dev/null && break; sleep 1; done
grep -q HYBRID_HOST_READY "$LOG" || { echo "FAIL host did not start"; tail -5 "$LOG"; kill "$(cat /tmp/lan_host_$port.pid)" 2>/dev/null; exit 1; }
SCRIPT=run_lan_two_clients.gd; MAXDUELS=1; OKTOKEN=HYBRID_LAN_OK; TOKENS="HYBRID_LAN"
if [ "$WHICH" = mortality ]; then SCRIPT=run_hybrid_mortality.gd; MAXDUELS=3; OKTOKEN=HYBRID_MORTALITY_OK; TOKENS="HYBRID_MORTALITY"; fi
BOTARGS="--accept --challenge-after 2 --ward 1,1,3 --max-duels $MAXDUELS"
if [ "$WHICH" = trial ]; then SCRIPT=run_hybrid_trial_a_d.gd; OKTOKEN=HYBRID_TRIAL_OK; TOKENS="HYBRID_TRIAL|TRIAL "; BOTARGS="--stay --max-duels 0"; fi
(cd "$HYB" && python3 -u scripts/lan_bot.py --host 127.0.0.1 --port "$port" --code $CODE --secret $SECRET --name Alice --start $BOTARGS --seconds 600 > "$BOT" 2>&1 & echo $! > /tmp/lan_bot_$port.pid)
out=$(env HYBRID_LAN_HOST=127.0.0.1 HYBRID_LAN_PORT=$port HYBRID_LAN_CODE=$CODE timeout "${TIMEOUT:-600}" "$GODOT" --path "$REPO/godot_project" --rendering-method forward_plus --script res://client/tests/$SCRIPT 2>&1)
sleep 1
kill "$(cat /tmp/lan_bot_$port.pid)" 2>/dev/null
kill "$(cat /tmp/lan_host_$port.pid)" 2>/dev/null
echo "$out" | grep -E "$TOKENS|SCRIPT ERROR|ERROR" | head -40
echo "--- bot:"; grep -E "LAN_BOT_(HELLO|START|ADJACENT|CHALLENGE|RESPOND|WARD|RESULT|DONE|EXIT)" "$BOT" | head -20
echo "--- host:"; grep -E "HYBRID_HOST_STATS" "$LOG" | tail -1 | cut -c1-400
if echo "$out" | grep -q "$OKTOKEN"; then echo "PASS $WHICH"; exit 0; fi
echo "FAIL $WHICH"; echo "$out" | grep -v "^$" | tail -20; exit 1
