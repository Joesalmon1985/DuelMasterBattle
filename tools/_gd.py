import re, os
ROOT = r"C:/Users/joesa/Documents/Cursor/DuelMaster/DuelMasterBattle/godot_project"

def grep(path, pat, limit=60):
    if not path.startswith("C:"):
        path = ROOT + "/" + path
    out = []
    for i, l in enumerate(open(path, encoding="utf-8"), 1):
        if re.search(pat, l):
            out.append(f"{i}: {l.rstrip()}")
    return "\n".join(out[:limit])

def show(path, anchor, n=1200):
    if not path.startswith("C:"):
        path = ROOT + "/" + path
    s = open(path, encoding="utf-8").read()
    i = s.index(anchor)
    return s[i:i+n]
