"""Generate (or re-validate) the God World terrain embedding of the Catan graph on a Widelands map.

    python WizardRTSHybrid/scripts/god_world_embed.py [--map Egyptian_Mandala_v1.2] [--check] [--ascii]

Writes data/god_world/embedding_<map>.json and prints EMBEDDING_OK with the validation report. `--check` only validates the checked-in file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
for entry in (str(_HERE), str(_HERE.parent)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from wizard_rts import terrain as T  # noqa: E402
from wizard_rts import wl_map  # noqa: E402
from wizard_rts.god_world import embedding  # noqa: E402
from wizard_rts.god_world.board import GodBoard, catan_5_6_cells  # noqa: E402


def ascii_picture(emb: dict, grid: T.TerrainGrid, step: int = 3) -> str:
    rows = []
    marks: dict[tuple[int, int], str] = {}
    for poly in emb["corridors"].values():
        for i in range(len(poly) - 1):
            (ax, ay), (bx, by) = poly[i], poly[i + 1]
            n = int(max(abs(bx - ax), abs(by - ay)) * 2) + 1
            for k in range(n + 1):
                t = k / n
                marks.setdefault((int(ax + (bx - ax) * t) // step, int(ay + (by - ay) * t) // step), "+")
    for n, (x, y) in emb["nodes"].items():
        marks[(int(x) // step, int(y) // step)] = "O"
    for by in range(0, grid.h, step):
        row = ""
        for bx in range(0, grid.w, step):
            m = marks.get((bx // step, by // step))
            if m:
                row += m
                continue
            c = grid.cls[by * grid.w + bx]
            row += {T.WATER: "~", T.UNREACHABLE: "#", T.UNWALKABLE: "^", T.MINEABLE: "m", T.WALKABLE: ".", T.ARABLE: ","}.get(c, "?")
        rows.append(row)
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=embedding.DEFAULT_MAP)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--ascii", action="store_true")
    args = ap.parse_args(argv)
    grid = wl_map.load(args.map)
    board = GodBoard(catan_5_6_cells())
    if args.check:
        emb = embedding.load(args.map)
        if emb is None:
            print("EMBEDDING_MISSING")
            return 1
    else:
        base = embedding.load(args.map[:-3]) if args.map.endswith("@2x") else None
        emb = embedding.build_scaled(board, grid, args.map, base) if base else embedding.build(board, grid, args.map)
        path = embedding.embedding_path(args.map)
        path.write_text(json.dumps(emb, separators=(",", ":")), encoding="utf-8")
        print("wrote", path)
    report = embedding.validate(emb, board, grid)
    if args.ascii:
        print(ascii_picture(emb, grid))
    print("EMBEDDING_OK " + json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
