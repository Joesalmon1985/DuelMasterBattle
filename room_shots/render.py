"""Render exported Godot puzzle rooms to PNG QA shots (offline, from real sim data)."""
import json, os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))          # .../room_shots
PROJ = os.path.abspath(os.path.join(ROOT, "..", "godot_project"))
OUT = os.path.join(PROJ, "docs", "puzzle_room_shots")
os.makedirs(OUT, exist_ok=True)

def font(sz):
    for p in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except OSError:
            continue
    return ImageFont.load_default()

F_TITLE, F_TXT, F_LBL = font(20), font(13), font(15)
CELL = 36
TILE_COLORS = {"#": (110, 110, 120), ".": (34, 36, 46), "~": (40, 90, 160),
               "T": (60, 120, 70), "=": (150, 120, 60)}
UNKNOWN_TILE = (255, 0, 255)

def lum(rgb):
    r, g, b = rgb[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b

def parse_color(s):
    s = str(s).strip()
    if s.startswith("("):  # Godot Color(r, g, b, a) floats
        parts = [float(x) for x in s.strip("()").split(",")[:3]]
        return tuple(max(0, min(255, int(round(v * 255)))) for v in parts)
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def render(room):
    rows, start = room["rows"], room["start"]
    h, w = len(rows), len(rows[0])
    gw, gh = w * CELL, h * CELL
    panel_w = 430
    img = Image.new("RGB", (gw + panel_w + 30, max(gh + 70, 120)), (18, 18, 24))
    d = ImageDraw.Draw(img)
    d.text((10, 8), "%s — %s" % (room["id"], room["title"]), font=F_TITLE, fill=(240, 240, 240))

    # tiles
    problems = []
    for y, line in enumerate(rows):
        for x, ch in enumerate(line):
            c = TILE_COLORS.get(ch)
            if c is None:
                c = UNKNOWN_TILE
                problems.append("unknown tile %r at %d,%d" % (ch, x, y))
            d.rectangle([10 + x * CELL, 60 + y * CELL, 10 + (x + 1) * CELL - 1, 60 + (y + 1) * CELL - 1], fill=c)

    # world items spawn from kind=item entities: index them by position
    wi_at = set()
    for e in room.get("extra", []):
        if e["key"].startswith("wi_"):
            wi_at.add(tuple(e["pos"]))

    def cell_xy(p):
        return 10 + p[0] * CELL, 60 + p[1] * CELL

    # beams under entities
    for e in room.get("extra", []):
        if e["key"].startswith("beam_"):
            x0, y0 = cell_xy(e["pos"])
            d.rectangle([x0 + 8, y0 + 14, x0 + CELL - 8, y0 + CELL - 14],
                        fill="#" + e["color"][:6])

    # entities
    for e in room["entities"]:
        if not e.get("visible", True) or e["pos"][0] < 0:
            continue
        x0, y0 = cell_xy(e["pos"])
        col = tuple(int(e["color"][i:i + 2], 16) for i in (0, 2, 4))
        if e["shape"] == "frame":
            d.rectangle([x0 + 4, y0 + 4, x0 + CELL - 4, y0 + CELL - 4], outline=col, width=3)
        else:
            d.rectangle([x0 + 3, y0 + 3, x0 + CELL - 3, y0 + CELL - 3], fill=col)
        if e["label"]:
            tc = (20, 20, 20) if lum(col) > 130 else (245, 245, 245)
            d.text((x0 + CELL / 2, y0 + CELL / 2), e["label"], font=F_LBL, fill=tc, anchor="mm")
        # red flag: non-door entity on a solid tile (gates/doors live in walls legitimately)
        line = rows[e["pos"][1]]
        if line[e["pos"][0]] == "#":
            if e["kind"] in ("gate", "plaque"):
                # doors/signs in walls are fine if an adjacent floor tile exists to use them from
                adj = any(0 <= e["pos"][0] + dx < w and 0 <= e["pos"][1] + dy < h
                          and rows[e["pos"][1] + dy][e["pos"][0] + dx] != "#"
                          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if not adj:
                    d.rectangle([x0 + 1, y0 + 1, x0 + CELL - 1, y0 + CELL - 1], outline=(255, 0, 0), width=3)
                    problems.append("%s (%s) sealed in wall" % (e["id"], e["kind"]))
            else:
                d.rectangle([x0 + 1, y0 + 1, x0 + CELL - 1, y0 + CELL - 1], outline=(255, 0, 0), width=3)
                problems.append("%s on wall" % e["id"])
        # NOTE: kind=item entities gated behind `requires` (pz_04 idol, pz_37 key)
        # spawn nothing at fresh state by design; covered by _test_gated_items_appear.

    # world items / extras on top
    for e in room.get("extra", []):
        if e["key"].startswith("wi_"):
            x0, y0 = cell_xy(e["pos"])
            col = tuple(int(e["color"][i:i + 2], 16) for i in (0, 2, 4))
            d.ellipse([x0 + 10, y0 + 10, x0 + CELL - 10, y0 + CELL - 10], fill=col, outline=(255, 255, 255))

    # start marker
    sx, sy = cell_xy(start)
    d.ellipse([sx + 6, sy + 6, sx + CELL - 6, sy + CELL - 6], outline=(80, 255, 120), width=3)

    # side panel
    px = gw + 25
    d.text((px, 60), "entities (%d)" % len(room["entities"]), font=F_TXT, fill=(200, 200, 210))
    y = 82
    for e in room["entities"]:
        col = tuple(int(e["color"][i:i + 2], 16) for i in (0, 2, 4)) if len(e["color"]) >= 6 else (128, 128, 128)
        d.rectangle([px, y, px + 16, y + 16], fill=col)
        d.text((px + 22, y - 1), "%s [%s] %s %s" % (e["id"], e["kind"], e["state"],
               ("'%s'" % e["label"]) if e["label"] else ""), font=F_TXT, fill=(220, 220, 228))
        y += 21
        if y > img.height - 20:
            break
    if problems:
        d.text((10, 62 + gh), "FLAGS: " + "; ".join(problems), font=F_TXT, fill=(255, 120, 120))
    return img, problems

def draw_mini(rows, statics, frame, cell=16):
    """Small frame: tiles + static entity blocks + frame extras + player ring."""
    h, w = len(rows), len(rows[0])
    img = Image.new("RGB", (w * cell + 4, h * cell + 26), (18, 18, 24))
    d = ImageDraw.Draw(img)
    for y, line in enumerate(rows):
        for x, ch in enumerate(line):
            c = TILE_COLORS.get(ch, UNKNOWN_TILE)
            d.rectangle([2 + x * cell, 24 + y * cell, 2 + (x + 1) * cell - 1, 24 + (y + 1) * cell - 1], fill=c)
    ex = frame.get("extra", {})
    for e in statics:
        if not e.get("visible", True) or e["pos"][0] < 0 or e["id"] in ex:
            continue
        x0, y0 = 2 + e["pos"][0] * cell, 24 + e["pos"][1] * cell
        col = tuple(int(e["color"][i:i + 2], 16) for i in (0, 2, 4))
        d.rectangle([x0 + 2, y0 + 2, x0 + cell - 2, y0 + cell - 2], fill=col)
    for key, e in ex.items():
        if "pos" not in e or e["pos"][0] < 0:
            continue
        x0, y0 = 2 + e["pos"][0] * cell, 24 + e["pos"][1] * cell
        col = parse_color(e["color"])
        if e["shape"] == "frame":
            d.rectangle([x0 + 2, y0 + 2, x0 + cell - 2, y0 + cell - 2], outline=col)
        else:
            d.rectangle([x0 + 2, y0 + 2, x0 + cell - 2, y0 + cell - 2], fill=col)
    px, py = frame["player"]
    d.ellipse([2 + px * cell + 2, 24 + py * cell + 2, 2 + (px + 1) * cell - 2, 24 + (py + 1) * cell - 2],
              outline=(80, 255, 120), width=2)
    tag = "step %d%s" % (frame["step"], " SOLVED" if frame["solved"] else "")
    d.text((4, 4), tag, font=F_TXT, fill=(120, 255, 140) if frame["solved"] else (200, 200, 210))
    return img


def render_walk(w):
    rows = w["rows"]
    frames = w["frames"]
    picks = [frames[0]] if len(frames) < 3 else [frames[0], frames[len(frames) // 2], frames[-1]]
    statics = []  # walk export carries visuals per-frame in extra; statics unused
    minis = [draw_mini(rows, statics, f) for f in picks]
    gw = sum(m.width for m in minis) + 8 * (len(minis) + 1)
    gh = max(m.height for m in minis) + 34
    img = Image.new("RGB", (gw, gh), (18, 18, 24))
    d = ImageDraw.Draw(img)
    verdict = "SOLVED in %d steps" % w["steps"] if w["solved"] else "unsolved by walking (needs interaction)"
    d.text((8, 6), "%s — %s: %s" % (w["id"], w["title"], verdict), font=F_TXT,
            fill=(120, 255, 140) if w["solved"] else (255, 210, 120))
    x = 8
    for m in minis:
        img.paste(m, (x, 30))
        x += m.width + 8
    return img


def main():
    rooms = []
    with open(os.path.join(PROJ, "room_export.json"), encoding="utf-8") as f:
        for line in f:
            rooms.append(json.loads(line))
    rooms.sort(key=lambda r: r["num"])
    thumbs, all_flags = [], {}
    for r in rooms:
        img, flags = render(r)
        img.save(os.path.join(OUT, "%s.png" % r["id"]))
        if flags:
            all_flags[r["id"]] = flags
        t = img.copy()
        t.thumbnail((360, 360))
        thumbs.append((r["id"], t))
    # contact sheet 5 x 10
    cw, chh = 360, 300
    sheet = Image.new("RGB", (5 * cw, 10 * (chh + 22)), (18, 18, 24))
    d = ImageDraw.Draw(sheet)
    for i, (rid, t) in enumerate(thumbs):
        ox, oy = (i % 5) * cw, (i // 5) * (chh + 22)
        sheet.paste(t, (ox + (cw - t.width) // 2, oy + 20))
        d.text((ox + 8, oy + 2), rid, font=F_TXT, fill=(240, 240, 240))
    sheet.save(os.path.join(OUT, "_contact_sheet.png"))
    print("rendered %d rooms -> %s" % (len(rooms), OUT))
    print("FLAGS:", json.dumps(all_flags, indent=1) if all_flags else "none")
    # walkthrough strips (start / mid / end frames through the real sim)
    wpath = os.path.join(PROJ, "room_walk.json")
    if os.path.exists(wpath):
        walks = []
        with open(wpath, encoding="utf-8") as f:
            for line in f:
                walks.append(json.loads(line))
        walks.sort(key=lambda r: r["num"])
        wthumbs = []
        for w in walks:
            img = render_walk(w)
            img.save(os.path.join(OUT, "walk_%s.png" % w["id"]))
            t = img.copy()
            t.thumbnail((360, 200))
            wthumbs.append((w["id"], t))
        wsheet = Image.new("RGB", (2 * 360, 25 * (200 + 22)), (18, 18, 24))
        d = ImageDraw.Draw(wsheet)
        for i, (rid, t) in enumerate(wthumbs):
            ox, oy = (i % 2) * 360, (i // 2) * (200 + 22)
            wsheet.paste(t, (ox + (360 - t.width) // 2, oy + 20))
            d.text((ox + 8, oy + 2), rid, font=F_TXT, fill=(240, 240, 240))
        wsheet.save(os.path.join(OUT, "_walk_sheet.png"))
        print("rendered %d walkthroughs" % len(walks))

if __name__ == "__main__":
    main()
