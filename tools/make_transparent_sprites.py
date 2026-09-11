"""Convert NewSprites JPGs (solid black/white or checkerboard backgrounds) to
transparent RGBA PNGs sized for the game's pixel-asset conventions.

  props : 32x32  (pedestals, hut)
  chars : 16x24  (NPC single-facing sets, 8 files per set)

Background removal: estimate the background colour model from the image rim
(solid median, or dark/light pair when the rim luma is bimodal = checkerboard),
mask near-background pixels with numpy, then flood-fill the mask from the
borders (PIL, C speed) so only the *connected exterior* background is keyed out.
Enclosed regions (subject interior) are preserved. Ground shadows stay attached
and read as grounding once downscaled.
"""
import os
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC = "C:/Users/joesa/Documents/Cursor/DuelMaster/DuelMasterBattle/Spare Sprites/NewSprites"
PIX = "C:/Users/joesa/Documents/Cursor/DuelMaster/DuelMasterBattle/godot_project/assets/pixel"

TOL = {"black": 26.0, "white": 30.0, "checker": 52.0}


def bg_model(arr):
    h, w, _ = arr.shape
    rim = np.concatenate([
        arr[:8].reshape(-1, 3), arr[-8:].reshape(-1, 3),
        arr[:, :8].reshape(-1, 3), arr[:, -8:].reshape(-1, 3),
    ]).astype(np.float32)
    luma = rim @ np.array([0.299, 0.587, 0.114], np.float32)
    order = np.argsort(luma)
    q = len(order) // 4
    dark = rim[order[:q]].mean(axis=0)
    light = rim[order[-q:]].mean(axis=0)
    if float(np.linalg.norm(light - dark)) > 60.0:
        return "checker", [dark, light]
    med = np.median(rim, axis=0)
    kind = "black" if float(med.mean()) < 128 else "white"
    return kind, [med]


def key_out(path, extra_white=False):
    img = path if isinstance(path, Image.Image) else Image.open(path)
    img = img.convert("RGB")
    # Quantize (C speed); any quantized colour touching the image border is
    # background. Subjects are centred and never touch the border, so this
    # is immune to edge vignette/frames that fool rim-median sampling.
    q = img.quantize(colors=256, method=Image.MEDIANCUT)
    qp = np.asarray(q)
    h, w = qp.shape
    border_idx = set(np.concatenate([
        qp[0, :], qp[-1, :], qp[:, 0], qp[:, -1],
        qp[3, :], qp[-4, :], qp[:, 3], qp[:, -4],
    ]).tolist())
    bg = np.isin(qp, list(border_idx))
    fg_img = Image.fromarray((~bg).astype(np.uint8) * 255, "L")
    # 1px erosion: kills the anti-aliased fringe ring (its bins never touch
    # the border so they survive quantization) without visibly thinning the
    # subject at these source resolutions.
    fg_img = fg_img.filter(ImageFilter.MinFilter(3))
    fg = np.asarray(fg_img) > 0
    if extra_white:
        # Door panels: the open doorway interior is enclosed white that never
        # touches the border. Key global near-white too (doors hold no white
        # subject detail at these values).
        bright = np.asarray(img).astype(np.float32).mean(axis=2) > 235
        fg = fg & ~bright
    frac = fg.mean()
    if not 0.005 < frac < 0.95:
        # Subject may touch the border or share one bin with it: retry with
        # only the single most common border colour as background.
        from collections import Counter
        top = Counter(np.concatenate([qp[0, :], qp[-1, :], qp[:, 0], qp[:, -1]]).tolist()).most_common(1)[0][0]
        bg = qp == top
        fg = ~bg
        frac = fg.mean()
    alpha = fg.astype(np.uint8) * 255
    rgba = np.dstack([np.asarray(img), alpha])
    out = Image.fromarray(rgba, "RGBA")
    ys, xs = np.nonzero(fg)
    pad = 6
    x0, x1 = max(0, xs.min() - pad), min(out.width, xs.max() + pad + 1)
    y0, y1 = max(0, ys.min() - pad), min(out.height, ys.max() + pad + 1)
    kind = "edgequant(fg=%.2f)" % frac
    return out.crop((x0, y0, x1, y1)), kind


def place(cropped, size):
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    fit = cropped.copy()
    fit.thumbnail((size[0], size[1]), Image.LANCZOS)
    canvas.alpha_composite(fit, ((size[0] - fit.width) // 2, (size[1] - fit.height) // 2))
    return canvas


def save(cropped, rel, size):
    p = os.path.join(PIX, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    place(cropped, size).save(p)
    return rel, os.path.getsize(p)


def conv(name):
    return key_out(os.path.join(SRC, name))


def split_pair(name):
    """Split a side-by-side closed/open door image into (left, right) RGB imgs.

    Cut column = brightest column (over the middle 60% of rows) inside the
    central band; the white inter-panel gap always wins. key_out() border
    logic cleans any sliver left on either half.
    """
    img = Image.open(os.path.join(SRC, name)).convert("RGB")
    a = np.asarray(img).astype(np.float32).mean(axis=2)
    h, w = a.shape
    mid = a[int(h * 0.2):int(h * 0.8), :]
    score = mid.mean(axis=0)
    lo, hi = int(w * 0.35), int(w * 0.65)
    x = lo + int(np.argmax(score[lo:hi]))
    left, right = img.crop((0, 0, x, h)), img.crop((x, 0, w, h))
    # Paint the cut edges back to white: the gap is white anyway, and this
    # stops a sliver of the neighbour panel's stone from touching the border
    # and poisoning that grey bin inside the subject.
    d = ImageDraw.Draw(left)
    d.rectangle([left.width - 10, 0, left.width - 1, h - 1], fill=(255, 255, 255))
    d = ImageDraw.Draw(right)
    d.rectangle([0, 0, 9, h - 1], fill=(255, 255, 255))
    return left, right


def main():
    log = []
    # --- pedestals: one per riddle alcove ---
    for i in range(1, 5):
        c, kind = conv(f"pedestal{i}.jpg")
        log.append((f"props/pedestal_{i}.png",) + (save(c, f"props/pedestal_{i}.png", (32, 32))[1], kind))
    # --- woodcutter hut prop ---
    c, kind = conv("WoodCutterHouse1.jpg")
    log.append(("props/woodcutter_hut.png", save(c, "props/woodcutter_hut.png", (32, 32))[1], kind))
    # --- woodcutter NPC: male variants across facings (reads as variety at 16px) ---
    faces = {"down": "WoodCutterMale1.jpg", "left": "WoodCutterMale2.jpg",
             "right": "WoodCutterMale3.jpg", "up": "WoodCutterMale4.jpg"}
    for face, fn in faces.items():
        c, kind = conv(fn)
        for fr in ("0", "1"):
            _, n, _ = (f"chars/woodcutter_{face}_{fr}.png", save(c, f"chars/woodcutter_{face}_{fr}.png", (16, 24))[1], kind)
        log.append((f"chars/woodcutter_{face}_*", n, kind))
    # --- farmer NPC: straw-hat variants as walk frames ---
    cf1, k1 = conv("FarmerMale1.jpg")
    cf2, k2 = conv("FarmerMale2.jpg")
    for face in ("down", "left", "right", "up"):
        save(cf1, f"chars/farmer_{face}_0.png", (16, 24))
        save(cf2, f"chars/farmer_{face}_1.png", (16, 24))
    log.append(("chars/farmer_* (8 files)", "-", f"{k1}/{k2}"))
    # --- shepherd NPC: female woodcutter variants as frames ---
    wfs = [conv(f"WoodCutterFemale{i}.jpg") for i in range(1, 5)]
    combos = [("down", 0, 1), ("left", 0, 2), ("right", 1, 3), ("up", 2, 3)]
    for face, a, b in combos:
        save(wfs[a][0], f"chars/shepherd_{face}_0.png", (16, 24))
        save(wfs[b][0], f"chars/shepherd_{face}_1.png", (16, 24))
    log.append(("chars/shepherd_* (8 files)", "-", ",".join(sorted({k for _, k in wfs}))))
    # --- reaper worker: hooded skeleton with scythe ---
    cr, kr = conv("DarkFarmerMale1.jpg")
    for face in ("down", "left", "right", "up"):
        for fr in ("0", "1"):
            save(cr, f"chars/reaper_{face}_{fr}.png", (16, 24))
    log.append(("chars/reaper_* (8 files)", "-", kr))
    # --- batch 2: doors split into closed/open halves ---
    # Door1 (arched): puzzle gates. Door2 (rectangular): dungeon doors.
    # Door3: gate tower. Mine mouth gets the miner house instead.
    d1c, d1o = split_pair("Door1.jpg")
    cc, kc = key_out(d1c, extra_white=True)
    co, ko = key_out(d1o, extra_white=True)
    save(cc, "props/door_closed.png", (16, 22))
    save(co, "props/door_open.png", (16, 22))
    log.append(("props/door_closed/open.png (16x22)", "-", f"{kc}/{ko}"))
    d2c, _d2o = split_pair("Door2.jpg")
    cd, kd = key_out(d2c, extra_white=True)
    save(cd, "props/door_dungeon.png", (32, 32))
    log.append(("props/door_dungeon.png", "-", kd))
    d3c, _d3o = split_pair("Door3.jpg")
    ct, kt = key_out(d3c, extra_white=True)
    save(ct, "props/door_tower.png", (32, 32))
    log.append(("props/door_tower.png", "-", kt))
    # --- batch 2: miner house -> mine mouth building ---
    mh, kmh = conv("MinerHouse1.jpg")
    save(mh, "props/miner_house.png", (32, 32))
    log.append(("props/miner_house.png", "-", kmh))
    # --- batch 2: goddess statue -> shrine ---
    sg, ksg = conv("StatueGoddess.jpg")
    save(sg, "props/statue_goddess.png", (32, 32))
    log.append(("props/statue_goddess.png", "-", ksg))
    # --- batch 2: labourer NPC (brickmaker, carter) ---
    for face, fn in (("down", "WorkerMale1.jpg"), ("left", "WorkerMale2.jpg"),
                     ("right", "WorkerMale3.jpg"), ("up", "WorkerMale4.jpg")):
        cw, kw = conv(fn)
        save(cw, f"chars/worker_{face}_0.png", (16, 24))
        save(cw, f"chars/worker_{face}_1.png", (16, 24))
        log.append((f"chars/worker_{face}_*", "-", kw))
    # --- batch 2: miner NPC (mine workers, digger, smith) ---
    for face, fn in (("down", "MinerMale1.jpg"), ("left", "MinerMale2.jpg"),
                     ("right", "MinerMale3.jpg"), ("up", "MinerFemale1.jpg")):
        cm, km = conv(fn)
        save(cm, f"chars/miner_{face}_0.png", (16, 24))
        save(cm, f"chars/miner_{face}_1.png", (16, 24))
        log.append((f"chars/miner_{face}_*", "-", km))
    # --- batch 2: matron NPC (mother role) ---
    for face, fn in (("down", "WorkerFemale1.jpg"), ("left", "WorkerFemale2.jpg"),
                     ("right", "WorkerFemale3.jpg"), ("up", "WorkerFemale4.jpg")):
        cmt, kmt = conv(fn)
        save(cmt, f"chars/matron_{face}_0.png", (16, 24))
        save(cmt, f"chars/matron_{face}_1.png", (16, 24))
        log.append((f"chars/matron_{face}_*", "-", kmt))
    for rel, size, kind in log:
        print(f"{rel:38s} {size} bytes  bg={kind}")


if __name__ == "__main__":
    sys.exit(main())
