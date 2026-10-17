"""Outfit specs -> primitives.  An outfit is a dict (garments, hat, prop, colours); `draw_outfit` dresses a posed Figure."""
from __future__ import annotations

from . import face as face_mod
from . import garments
from .rig import Figure

OUTFITS: dict[str, dict] = {}


def draw_outfit(f: Figure, spec: dict, detail: float = 1.0) -> None:
    f.ears = spec.get("ears", "round")
    f.body()
    garments.draw_clothes(f, spec)
    from . import hats, props
    if spec.get("hat"):
        hats.draw(f, spec["hat"], spec)
    face_mod.draw(f, detail, hidden=bool(spec.get("face_hidden")), glow=spec.get("glow_eyes"), eye_color=spec.get("eye_color", face_mod.INK))
    if spec.get("prop"):
        props.draw(f, spec["prop"], spec)
    if spec.get("back"):
        props.draw_back(f, spec["back"], spec)
    if spec.get("extra"):
        spec["extra"](f, spec)
