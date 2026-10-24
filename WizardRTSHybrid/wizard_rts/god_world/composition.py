"""The deterministic village projection: one warehouse at the node, a district per touching hex with `pips * level` stations, a military
facility and its parade slots. Positions are in board units (hex circumradius 1); the viewer multiplies by its pixel size. Stations are a
picture of expected capacity, never a yield (PRD 7.1): a village with 30 stations still gains one token per matching roll as a settlement."""

from __future__ import annotations

import math
from typing import Any

from . import rules

ROW_CAPACITY = (2, 3, 4, 5, 6)  # stations per row, nearest the warehouse first
ROW_DEPTH0 = 0.30  # fraction of the corner-to-centre distance where the first row sits
ROW_STEP = 0.17
LATERAL = 0.22
PAIR_OFFSET = (0.085, 0.075)  # (depth, lateral) of a station's second building
FACILITY_DEPTH = 0.17
CLEAR_RADIUS = 0.22  # around the warehouse: road approaches and the entrance stay clear


def _norm(dx: float, dy: float) -> tuple[float, float]:
    d = math.hypot(dx, dy) or 1.0
    return dx / d, dy / d


def station_count(token: int, level: int) -> int:
    return rules.pips(token) * max(0, int(level))


def expected_output(board, node: str, level: int) -> float:
    """Tokens per pulse from theoretical odds: level * sum(pips)/36 over the touching productive hexes."""
    return float(level) * sum(rules.pips(t) for _h, _r, t in board.productive_hexes(node)) / 36.0


def station_positions(n: int, pushed: bool = False) -> list[tuple[float, float, int]]:
    """(depth, lateral, row) for `n` stations packed in widening rows away from the corner."""
    out: list[tuple[float, float, int]] = []
    row = 0
    i = 0
    extra = 0.12 if pushed else 0.0
    while i < n:
        cap = ROW_CAPACITY[min(row, len(ROW_CAPACITY) - 1)]
        take = min(cap, n - i)
        depth = ROW_DEPTH0 + extra + ROW_STEP * row
        for j in range(take):
            lateral = (j - (take - 1) / 2.0) * LATERAL
            out.append((depth, lateral, row))
        i += take
        row += 1
    return out


def layout(board, village: dict[str, Any], age: int, level: int | None = None) -> dict[str, Any]:
    """The whole picture of one village for a given age and completed level, with stable ids."""
    vid = str(village["id"])
    node = str(village["node"])
    lvl = int(village.get("level", 1) if level is None else level)
    px, py = board.node_xy(node)
    districts: list[dict[str, Any]] = []
    touching = list(board.node_hexes[node])
    # the military wedge: the touching hex with the fewest stations (a desert first); boundary nodes use the open side instead
    counts = {h: station_count(board.token(h), lvl) if board.role(h) != rules.DESERT else 0 for h in touching}
    mil_hex = min(touching, key=lambda h: (counts[h], h))
    boundary = len(touching) < 3
    for hid in touching:
        role = board.role(hid)
        token = board.token(hid)
        cx, cy = board.hex_xy(hid)
        ux, uy = _norm(cx - px, cy - py)
        vx, vy = -uy, ux
        n = counts[hid]
        pushed = (hid == mil_hex) and not boundary
        stations = []
        arts = rules.role_buildings(age, role) if role != rules.DESERT else []
        for i, (depth, lateral, row) in enumerate(station_positions(n, pushed)):
            sid = f"{vid}:st:{hid}:a{age}:{i}"
            sx = px + ux * depth + vx * lateral
            sy = py + uy * depth + vy * lateral
            buildings = []
            for k, art in enumerate(arts):
                bx = sx + (ux * PAIR_OFFSET[0] + vx * PAIR_OFFSET[1]) * k
                by = sy + (uy * PAIR_OFFSET[0] + vy * PAIR_OFFSET[1]) * k
                buildings.append({"id": f"{sid}:b{k}", "art": art, "x": round(bx, 4), "y": round(by, 4), "part": k})
            stations.append({"id": sid, "index": i, "row": row, "x": round(sx, 4), "y": round(sy, 4), "buildings": buildings})
        districts.append({"hex": hid, "role": role, "token": token, "pips": rules.pips(token) if role != rules.DESERT else 0,
                          "stations": stations, "count": n, "dir": [round(ux, 4), round(uy, 4)],
                          "worker": rules.role_worker(age, role) if role != rules.DESERT else ""})
    if boundary:
        sx = sum(d["dir"][0] for d in districts)
        sy = sum(d["dir"][1] for d in districts)
        mx, my = _norm(-sx, -sy)
    else:
        d = next(d for d in districts if d["hex"] == mil_hex)
        mx, my = d["dir"]
    fx, fy = px + mx * FACILITY_DEPTH, py + my * FACILITY_DEPTH
    spec = rules.military_spec(age)
    slots = []
    wx, wy = -my, mx
    cap = rules.limit("garrison_city")
    for i in range(cap):
        off = (i - (cap - 1) / 2.0) * 0.07
        slots.append([round(fx + wx * off + mx * 0.09, 4), round(fy + wy * off + my * 0.09, 4)])
    return {"village": vid, "node": node, "age": age, "level": lvl, "x": round(px, 4), "y": round(py, 4),
            "warehouse": {"id": f"{vid}:wh", "art": rules.data()["warehouse"], "x": round(px, 4), "y": round(py, 4)},
            "districts": districts, "stations_total": sum(d["count"] for d in districts),
            "military": {"id": f"{vid}:mil", "art": spec["facility"], "name": spec.get("facility_name", "Barracks"), "x": round(fx, 4), "y": round(fy, 4),
                         "dir": [round(mx, 4), round(my, 4)], "slots": slots,
                         "city": {"art": spec.get("city_facility", ""), "name": spec.get("city_facility_name", "")} if lvl >= 2 and spec.get("city_facility") else None}}
