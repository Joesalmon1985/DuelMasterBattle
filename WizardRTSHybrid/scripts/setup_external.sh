#!/usr/bin/env bash
# Ubuntu: sparse, shallow, pinned checkouts of the source labs the importers read.
# Widelands: terrain, resource and map data, terrain-rule C++ (about 30 MB). OpenRA: rules, sequences, tilesets.
# Usage: scripts/setup_external.sh [widelands|openra|all]
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p external
want="${1:-all}"
df_free_gb=$(df --output=avail -BG . | tail -1 | tr -dc 0-9)
if [ "$df_free_gb" -lt 12 ]; then echo "less than 12 GB free; keep 10 GB free" >&2; exit 1; fi

fetch() { # name url sha sparse-paths...
  local name="$1" url="$2" sha="$3"; shift 3
  if [ ! -d "external/$name/.git" ]; then
    git clone --filter=blob:none --no-checkout --depth 1 "$url" "external/$name"
  fi
  (cd "external/$name"
   git fetch --depth 1 origin "$sha"
   git sparse-checkout init --no-cone
   git sparse-checkout set "$@"
   git checkout -q FETCH_HEAD)
}

if [ "$want" = widelands ] || [ "$want" = all ]; then
  fetch widelands https://github.com/widelands/widelands.git 47c5cae8c6cb080e4bf86163a3873bd0847bc0e4 \
    '/data/world/terrains/' '/data/world/resources/' '/data/world/init.lua' '/data/world/map_generation.lua' \
    '/data/world/immovables/' '/data/world/critters/' '/src/logic/map.cc' '/src/logic/map.h' '/src/logic/map_objects/terrain_affinity.*' \
    '/src/map_io/' '/data/maps/Archipelago_Sea.wmf/' '/data/maps/Crater.wmf/' '/data/maps/Twin_Lagoons.wmf/' '/data/maps/Wideworld.wmf/' \
    '/data/tribes/'
fi
if [ "$want" = openra ] || [ "$want" = all ]; then
  fetch openra https://github.com/OpenRA/OpenRA.git e7e9e4ad270221d7fb9725b348c75504d48c1ebd \
    '/mods/ra/rules/' '/mods/ra/weapons/' '/mods/ra/tilesets/' '/mods/ra/sequences/' '/mods/ra/mod.yaml' \
    '/mods/cnc/rules/' '/mods/cnc/weapons/' '/mods/d2k/rules/' '/mods/d2k/weapons/' '/mods/ts/rules/' '/mods/ts/weapons/' \
    '/OpenRA.Mods.Common/Traits/' '/OpenRA.Mods.Common/Pathfinder/' '/OpenRA.Mods.Common/Activities/'
fi
du -sh external/* 
