#!/usr/bin/env bash
# Ubuntu launcher for the directly inspectable scenarios (owner run of 11 Oct 2026, section G).
#   scripts/launch_scenario.sh campaign        primitive campaign start, no God Mode (the shipped profile); play as the wizard
#   scripts/launch_scenario.sh drafting        developer profile, God Mode panel open, a draft offer every 60 game seconds
#   scripts/launch_scenario.sh industry        Modern fixture: drills on existing deposits -> belts -> powered smelter -> factory -> dagger
#   scripts/launch_scenario.sh story           a dry mine, its miner, the gallery below it, four puzzles, the warden's duel, a changed deposit
#                                              (click the miner; E at the gallery mouth; arrows move, E uses, 1-8 pick an item, Q/F/R spells)
#   scripts/launch_scenario.sh outbreak        cubes in the wizard's hex region, a healer, treatment with T (hold still 8 s)
#   scripts/launch_scenario.sh eras            historic -> modern transition and full-cycle reset                  (HYBRID_ERA_MS / HYBRID_ERA_VP set the pace)
#   scripts/launch_scenario.sh autoplay        SPECTATOR: a normal primitive six-faction world at 16x in God Mode, nothing staged or forced;
#                                              every faction is played by its AI (HYBRID_AI_POLICY=mixed|plus|baseline, default mixed: the
#                                              improved AI on Red, Green, Purple). Click a faction row to inspect it; "Take control" commands it.
# Developer switches (developer profile only, never in campaign): HYBRID_DRAFT_MS=<ms> draft interval, HYBRID_SEED, HYBRID_MAP,
# HYBRID_FIXTURE_FACTION (default Red). In God Mode use the 16x clock button to watch the industry build up; G returns to the wizard.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
case "${1:-}" in
  campaign) export HYBRID_PROFILE=campaign; exec "$HERE/launch_hybrid.sh" wizard ;;
  drafting) export HYBRID_PROFILE=developer HYBRID_DRAFT_MS="${HYBRID_DRAFT_MS:-60000}"; exec "$HERE/launch_hybrid.sh" god ;;
  industry) export HYBRID_PROFILE=developer HYBRID_FIXTURE=modern_industry HYBRID_ALLOW_SPAWN=1; exec "$HERE/launch_hybrid.sh" god ;;
  story) export HYBRID_PROFILE=developer HYBRID_FIXTURE=story; exec "$HERE/launch_hybrid.sh" wizard ;;
  outbreak) export HYBRID_PROFILE=developer HYBRID_FIXTURE=outbreak; exec "$HERE/launch_hybrid.sh" wizard ;;
  autoplay) export HYBRID_PROFILE=developer HYBRID_START_SPEED="${HYBRID_START_SPEED:-16}" HYBRID_AI_POLICY="${HYBRID_AI_POLICY:-mixed}" HYBRID_SEED="${HYBRID_SEED:-507}"; exec "$HERE/launch_hybrid.sh" god ;;
  eras) export HYBRID_PROFILE=developer HYBRID_ERA_MS="${HYBRID_ERA_MS:-120000}" HYBRID_ERA_VP="${HYBRID_ERA_VP:-3}" HYBRID_DRAFT_MS="${HYBRID_DRAFT_MS:-30000}"; exec "$HERE/launch_hybrid.sh" god ;;
  *) sed -n 2,15p "$0"; exit 1 ;;
esac
