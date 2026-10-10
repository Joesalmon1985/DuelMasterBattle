#!/usr/bin/env bash
# Ubuntu: run the headed Godot tests, each against a fresh simulator.
# Usage: scripts/run_headed_suite.sh [name ...]   (names: walk visual duel forestry food god war terrain)
# GODOT defaults to ~/godot451/Godot_v4.5.1-stable_linux.x86_64. Shots go to HYBRID_SHOT_DIR (default docs/evidence/ubuntu).
# The laptop screen is smaller than 1920x1080, so any shot of that size fails here and needs the Windows machine.
set -u
HYB="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(dirname "$HYB")"
GODOT="${GODOT:-$HOME/godot451/Godot_v4.5.1-stable_linux.x86_64}"
export HYBRID_SHOT_DIR="${HYBRID_SHOT_DIR:-$HYB/docs/evidence/ubuntu}"
mkdir -p "$HYBRID_SHOT_DIR"
declare -A SCRIPT=( [walk]=run_hybrid_walk.gd [visual]=run_hybrid_visual.gd [duel]=run_hybrid_duel.gd [forestry]=run_hybrid_forestry.gd [food]=run_hybrid_food.gd [god]=run_hybrid_god.gd [war]=run_hybrid_war.gd [terrain]=run_hybrid_terrain.gd )
declare -A MARK=( [walk]=HYBRID_WALK_OK [visual]=HYBRID_VISUAL_OK [duel]=HYBRID_DUEL_OK [forestry]=HYBRID_FORESTRY_OK [food]=HYBRID_FOOD_OK [god]=HYBRID_GOD_OK [war]=HYBRID_WAR_OK [terrain]=HYBRID_TERRAIN_OK )
declare -A ENVX=( [forestry]="HYBRID_SPEED=4" [food]="HYBRID_SPEED=10" [war]="HYBRID_SPEED=20 HYBRID_WAR_SECONDS=240" )
names=("$@"); [ ${#names[@]} -eq 0 ] && names=(walk visual duel forestry food god war terrain)
port=8900; failed=()
for n in "${names[@]}"; do
  port=$((port+1))
  (cd "$HYB" && HYBRID_SIM_PORT=$port python3 -m wizard_rts.server >/dev/null 2>&1 & echo $! > /tmp/hybrid_sim_$port.pid)
  sleep 6
  out=$(env HYBRID_SIM_PORT=$port ${ENVX[$n]:-} timeout 600 "$GODOT" --path "$REPO/godot_project" --rendering-method forward_plus --script "res://client/tests/${SCRIPT[$n]}" 2>&1)
  kill "$(cat /tmp/hybrid_sim_$port.pid)" 2>/dev/null
  if echo "$out" | grep -q "${MARK[$n]}"; then echo "PASS $n"; else echo "FAIL $n"; echo "$out" | grep -E "FAIL|ERROR|SCRIPT" | head -5 | sed 's/^/  /'; failed+=("$n"); fi
done
[ ${#failed[@]} -gt 0 ] && { echo "HEADED_SUITE_FAILED ${failed[*]}"; exit 1; }
echo HEADED_SUITE_OK
