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
declare -A SCRIPT=( [walk]=run_hybrid_walk.gd [visual]=run_hybrid_visual.gd [duel]=run_hybrid_duel.gd [forestry]=run_hybrid_forestry.gd [food]=run_hybrid_food.gd [god]=run_hybrid_god.gd [war]=run_hybrid_war.gd [terrain]=run_hybrid_terrain.gd [naval]=run_hybrid_naval.gd [playtest]=run_hybrid_playtest.gd [wizard]=run_hybrid_wizard.gd [mcv]=run_hybrid_mcv.gd [campaign]=run_hybrid_campaign.gd [campaign_dev]=run_hybrid_campaign.gd [industry]=run_hybrid_industry.gd )
declare -A MARK=( [walk]=HYBRID_WALK_OK [visual]=HYBRID_VISUAL_OK [duel]=HYBRID_DUEL_OK [forestry]=HYBRID_FORESTRY_OK [food]=HYBRID_FOOD_OK [god]=HYBRID_GOD_OK [war]=HYBRID_WAR_OK [terrain]=HYBRID_TERRAIN_OK [naval]=HYBRID_NAVAL_OK [playtest]=HYBRID_PLAYTEST_OK [wizard]=HYBRID_WIZARD_OK [mcv]=HYBRID_MCV_OK [campaign]=HYBRID_CAMPAIGN_OK [campaign_dev]=HYBRID_CAMPAIGN_OK [industry]=HYBRID_INDUSTRY_OK )
declare -A ENVX=( [forestry]="HYBRID_SPEED=4" [food]="HYBRID_SPEED=10" [war]="HYBRID_SPEED=60" [naval]="HYBRID_ALLOW_SPAWN=1" [playtest]="HYBRID_ALLOW_SPAWN=1" [wizard]="HYBRID_ALLOW_SPAWN=1" [mcv]="HYBRID_ALLOW_SPAWN=1" [campaign]="HYBRID_PROFILE=campaign HYBRID_EXPECT=campaign" [campaign_dev]="HYBRID_PROFILE=developer HYBRID_EXPECT=developer" [industry]="HYBRID_PROFILE=developer HYBRID_FIXTURE=modern_industry HYBRID_ALLOW_SPAWN=1" )
names=("$@"); [ ${#names[@]} -eq 0 ] && names=(walk visual duel forestry food god war terrain naval playtest wizard mcv campaign campaign_dev industry)
failed=()
for n in "${names[@]}"; do
  # a free port every time (a simulator left behind by an interrupted run must never be reused: its clock would be advanced)
  port=$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1])")
  (cd "$HYB" && env HYBRID_PROFILE=${HYBRID_PROFILE:-test_showcase} HYBRID_SIM_PORT=$port ${ENVX[$n]:-} python3 -u -m wizard_rts.server >/tmp/hybrid_sim_$port.log 2>&1 & echo $! > /tmp/hybrid_sim_$port.pid)
  for _i in $(seq 1 60); do grep -q HYBRID_SIM_READY /tmp/hybrid_sim_$port.log 2>/dev/null && break; sleep 1; done
  out=$(env HYBRID_SIM_PORT=$port ${ENVX[$n]:-} timeout "${TIMEOUT:-1700}" "$GODOT" --path "$REPO/godot_project" --rendering-method forward_plus --script "res://client/tests/${SCRIPT[$n]}" 2>&1)
  kill "$(cat /tmp/hybrid_sim_$port.pid)" 2>/dev/null
  if echo "$out" | grep -q "${MARK[$n]}"; then echo "PASS $n"; else echo "FAIL $n"; echo "$out" | grep -E "FAIL|ERROR|SCRIPT" | head -5 | sed 's/^/  /'; failed+=("$n"); fi
done
[ ${#failed[@]} -gt 0 ] && { echo "HEADED_SUITE_FAILED ${failed[*]}"; exit 1; }
echo HEADED_SUITE_OK
