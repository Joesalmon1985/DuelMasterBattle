#!/usr/bin/env bash
# Ubuntu launcher for the directly inspectable scenarios (owner run of 11 Oct 2026, section G).
#   scripts/launch_scenario.sh campaign        primitive campaign start, no God Mode (the shipped profile); play as the wizard
#   scripts/launch_scenario.sh drafting        developer profile, God Mode panel open, a draft offer every 60 game seconds
#   scripts/launch_scenario.sh industry        Modern fixture: drills on existing deposits -> belts -> powered smelter -> factory -> dagger
#   scripts/launch_scenario.sh story           settlement quest, dialogue, dungeon, puzzle, duel, consequence      (M3: NOT IMPLEMENTED YET)
#   scripts/launch_scenario.sh outbreak        hex-region outbreak and treatment                                    (M5: NOT IMPLEMENTED YET)
#   scripts/launch_scenario.sh eras            historic -> modern transition and full-cycle reset                  (M4: NOT IMPLEMENTED YET)
# Developer switches (developer profile only, never in campaign): HYBRID_DRAFT_MS=<ms> draft interval, HYBRID_SEED, HYBRID_MAP,
# HYBRID_FIXTURE_FACTION (default Red). In God Mode use the 16x clock button to watch the industry build up; G returns to the wizard.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
case "${1:-}" in
  campaign) export HYBRID_PROFILE=campaign; exec "$HERE/launch_hybrid.sh" wizard ;;
  drafting) export HYBRID_PROFILE=developer HYBRID_DRAFT_MS="${HYBRID_DRAFT_MS:-60000}"; exec "$HERE/launch_hybrid.sh" god ;;
  industry) export HYBRID_PROFILE=developer HYBRID_FIXTURE=modern_industry HYBRID_ALLOW_SPAWN=1; exec "$HERE/launch_hybrid.sh" god ;;
  story|outbreak|eras) echo "scenario '$1' is not implemented yet: see docs/IMPLEMENTATION_RUN_STATUS.md" >&2; exit 2 ;;
  *) sed -n 2,12p "$0"; exit 1 ;;
esac
