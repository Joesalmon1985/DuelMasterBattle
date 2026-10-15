"""The forward pass of the whole hierarchy for one decision (execution plan T3.2; design 4.3-4.4).

`Brain(nets).think(obs, cands, memory, since_command_min)` runs, in the order the design gives,

    N1 (buildings) N3 (units, enemies)  ->  N2 (settlements)  ->  N4 N5 N6 N7 N8(+N8card) N13(+slots) N14(+regions)  ->  N9 N10  ->  N12

and then scores every candidate of every head with that head's network. It returns a `Thought`: the coordinator's context (32), memory (16) and domain
priorities (8), the wait score, and one score per candidate. Nothing here touches the simulation; the controller (neuro/controller.py) turns scores into
commands and the imitation recorder reads `inputs`.

SCALES. A candidate's score is (head output + the head's domain priority) / temperature, where the temperature is the head's learned entry in the genome (clamped to
[0.05, 20]); H1 already takes the priorities as input and gets no bias. The wait score is H0's output plus N12's wait logit, unscaled. The cut-off for a candidate
to be issued is therefore "score above the wait score".
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from neuro import features as F
from neuro import schema as S
from neuro.nets import HEAD_DOMAIN, HEAD_NAMES, N12_SPLIT, Nets
from neuro.schema import compose

TEMP_MIN, TEMP_MAX = 0.05, 20.0
F32 = np.float32


def zeros(n: int) -> np.ndarray:
    return np.zeros(n, dtype=F32)


def take(a: np.ndarray, idx: list[int] | np.ndarray, width: int) -> np.ndarray:
    """Rows a[idx] as [len(idx), width]; an index below 0 (or beyond the array) gives a zero row."""
    idx = np.asarray(idx, dtype=np.int64).reshape(-1)
    out = np.zeros((len(idx), width), dtype=F32)
    ok = (idx >= 0) & (idx < len(a))
    if ok.any():
        out[ok] = a[idx[ok]]
    return out


def pool_rows(a: np.ndarray, rows: np.ndarray | list[int] | None, width: int) -> tuple[np.ndarray, np.ndarray]:
    """(mean, max) of the selected rows of a [n, width] (all rows when `rows` is None); zeros for an empty selection."""
    sel = a if rows is None else a[np.asarray(rows, dtype=np.int64)] if len(rows) else a[:0]
    if len(sel) == 0:
        return zeros(width), zeros(width)
    return sel.mean(axis=0, dtype=F32), sel.max(axis=0)


def stack(cands: list, width: int) -> np.ndarray:
    if not cands:
        return np.zeros((0, width), dtype=F32)
    return np.stack([c.features for c in cands]).astype(F32, copy=False)


def tile(v: np.ndarray, n: int) -> np.ndarray:
    return np.broadcast_to(v, (n, len(v)))


@dataclass
class Thought:
    context: np.ndarray
    memory: np.ndarray
    priorities: np.ndarray
    wait: float
    scores: dict[str, np.ndarray]
    enc: dict[str, np.ndarray] = field(default_factory=dict)
    inputs: dict[str, np.ndarray] = field(default_factory=dict)  # per head, the composed input matrices (only when keep_inputs)


class Brain:
    def __init__(self, nets: Nets) -> None:
        self.nets = nets
        self.ks = F.kind_static()

    # ------------------------------------------------------------------------------------------------------------------------ representations
    def encode(self, obs, memory: np.ndarray, since_command_min: float) -> tuple[dict[str, np.ndarray], np.ndarray]:
        n = self.nets
        emb = n.embed
        enc: dict[str, np.ndarray] = {}
        n1 = n.forward("N1", compose("N1", kind_emb=emb(obs.b_kind), raw=obs.b_raw)) if len(obs.b_ids) else np.zeros((0, 16), dtype=F32)
        n3 = n.forward("N3", compose("N3", kind_emb=emb(obs.u_kind), raw=obs.u_raw)) if len(obs.u_ids) else np.zeros((0, 12), dtype=F32)
        n3e = n.forward("N3", compose("N3", kind_emb=emb(obs.e_kind), raw=obs.e_raw)) if len(obs.e_ids) else np.zeros((0, 12), dtype=F32)
        ns = len(obs.s_ids)
        n2 = np.zeros((0, 24), dtype=F32)
        if ns:
            x = []
            for j in range(ns):
                mem = obs.s_members[j]
                mean, mx = pool_rows(n1, mem, 16)
                dmg = n1[int(obs.s_damaged[j])] if int(obs.s_damaged[j]) >= 0 else zeros(16)
                x.append(compose("N2", n1_mean=mean, n1_max=mx, n1_count=np.array([np.log1p(len(mem)) / 5.0], dtype=F32), n1_damaged=dmg, raw=obs.s_raw[j]))
            n2 = n.forward("N2", np.stack(x))
        n2_mean, n2_max = pool_rows(n2, None, 24)
        n2_thr = n2[obs.s_threatened] if 0 <= obs.s_threatened < ns else zeros(24)
        n2_weak = n2[obs.s_weakest] if 0 <= obs.s_weakest < ns else zeros(24)
        n4 = n.forward("N4", compose("N4", raw=obs.n4_raw, n2_mean=n2_mean)[None])[0]
        n5 = n.forward("N5", compose("N5", raw=obs.n5_raw)[None])[0]
        own_mean, own_max = pool_rows(n3, np.flatnonzero(obs.u_armed) if len(obs.u_armed) else [], 12)
        enemy3 = np.concatenate([n3e[k] if k < len(n3e) else zeros(12) for k in range(3)])
        nearest = n3e[0] if len(n3e) else zeros(12)
        n6 = n.forward("N6", compose("N6", n3_own_mean=own_mean, n3_own_max=own_max, n3_nearest_enemy=nearest, n3_enemy_3=enemy3, n2_threatened=n2_thr, raw=obs.n6_raw)[None])[0]
        n7 = n.forward("N7", compose("N7", raw=obs.n7_raw, n2_max=n2_max)[None])[0]
        c_hid, c_score = n.card(obs.card_raw) if len(obs.card_ids) else (np.zeros((0, 16), dtype=F32), zeros(0))
        c_sum = c_hid.sum(axis=0, dtype=F32) if len(c_hid) else zeros(16)
        c_max = c_hid.max(axis=0) if len(c_hid) else zeros(16)
        n8 = n.forward("N8", compose("N8", raw=obs.n8_raw, card_sum=c_sum, card_max=c_max)[None])[0]
        slots = n.forward("N13slot", compose("N13slot", raw=obs.n13_slots)) if len(obs.n13_slots) else np.zeros((0, 8), dtype=F32)
        s_mean, s_max = pool_rows(slots, None, 8)
        n13 = n.forward("N13", compose("N13", slot_mean=s_mean, slot_max=s_max, pressure=np.array([obs.n13_pressure], dtype=F32))[None])[0]
        regions = n.forward("N14region", compose("N14region", raw=obs.n14_regions)) if len(obs.n14_regions) else np.zeros((0, 8), dtype=F32)
        r_mean, r_max = pool_rows(regions, None, 8)
        worst3 = np.concatenate([regions[int(i)] if 0 <= int(i) < len(regions) else zeros(8) for i in obs.n14_worst])
        n14 = n.forward("N14", compose("N14", region_mean=r_mean, region_max=r_max, worst_3=worst3, raw=obs.n14_global, n13=n13)[None])[0]
        n9 = n.forward("N9", compose("N9", n4=n4, n5=n5, n7=n7, n8=n8, n2_mean=n2_mean, n2_max=n2_max, n2_weakest=n2_weak)[None])[0]
        n10 = n.forward("N10", compose("N10", n6=n6, n7=n7, n2_threatened=n2_thr, n13_summary=n13, raw=obs.n10_raw)[None])[0]
        n12_in = compose("N12", n9=n9, n10=n10, n14=n14, n13=n13, n8=n8, raw=obs.n12_raw, memory=memory)[None]
        n12 = n.forward("N12", n12_in)[0]
        enc.update(n1=n1, n3=n3, n3e=n3e, n2=n2, n6=n6, n7=n7, n10=n10, n13slots=slots, card_hidden=c_hid, card_score=c_score)
        return enc, n12

    # ------------------------------------------------------------------------------------------------------------------------ heads
    def head_inputs(self, head: str, cands: list, enc: dict[str, np.ndarray], ctx: np.ndarray, prio: np.ndarray, obs) -> np.ndarray:
        n = len(cands)
        if n == 0:
            return np.zeros((0, S.DIMS[head]), dtype=F32)
        emb = self.nets.embed
        refs = [c.refs for c in cands]
        ctxn = tile(ctx, n)
        if head == "H1":
            kr = [r["kind_row"] for r in refs]
            return compose("H1", kind_emb=emb(kr), raw=stack(cands, S.RAW_DIMS["H1_raw"]), n2=take(enc["n2"], [r["settlement"] for r in refs], 24), ctx=ctxn, prio=tile(prio, n))
        if head == "H2":
            return compose("H2", raw=stack(cands, 6), n1_a=take(enc["n1"], [r["a"] for r in refs], 16), n1_b=take(enc["n1"], [r["b"] for r in refs], 16), ctx=ctxn)
        if head == "H3":
            return compose("H3", kind_emb=emb([r["kind_row"] for r in refs]), raw=stack(cands, 12), n1_factory=take(enc["n1"], [r["factory"] for r in refs], 16),
                           n6=tile(enc["n6"], n), ctx=ctxn)
        if head == "H4":
            return compose("H4", raw=stack(cands, 4), n3_founder=take(enc["n3"], [r["founder"] for r in refs], 12), n7=tile(enc["n7"], n), ctx=ctxn)
        if head == "H5":
            mean = np.zeros((n, 12), dtype=F32)
            mx = np.zeros((n, 12), dtype=F32)
            for i, r in enumerate(refs):
                mean[i], mx[i] = pool_rows(enc["n3"], r["squad"], 12)
            tb = np.asarray([r["target_b"] for r in refs], dtype=np.int64)
            tk = np.asarray([r["target_kind"] for r in refs], dtype=np.int64)
            traw = np.stack([r["target_n1"] for r in refs]).astype(F32)
            target = self.nets.forward("N1", compose("N1", kind_emb=emb(tk), raw=traw))
            own = take(enc["n1"], tb, 16)
            target = np.where((tb >= 0)[:, None], own, target)
            return compose("H5", squad_mean=mean, squad_max=mx, n1_target=target, raw=stack(cands, 8), n10=tile(enc["n10"], n), ctx=ctxn)
        if head == "H6":
            k = [r["card"] for r in refs]
            return compose("H6", card_hidden=take(enc["card_hidden"], k, 16), card_score=take(enc["card_score"][:, None] if len(enc["card_score"]) else np.zeros((0, 1), dtype=F32), k, 1), ctx=ctxn)
        if head in ("H7", "H8"):
            return compose(head, raw=stack(cands, S.RAW_DIMS[head + "_raw"]), slot=take(enc["n13slots"], [r["slot"] for r in refs], 8), ctx=ctxn)
        if head == "H9":
            kr = np.asarray([r["kind_row"] for r in refs], dtype=np.int64)
            return compose("H9", raw=stack(cands, 4), n1=take(enc["n1"], [r["building"] for r in refs], 16), n2=take(enc["n2"], [r["settlement"] for r in refs], 24),
                           kind_static=self.ks[kr], ctx=ctxn)
        raise KeyError(head)

    # ------------------------------------------------------------------------------------------------------------------------ the whole decision
    def think(self, obs, cands: dict[str, list], memory: np.ndarray, since_command_min: float, keep_inputs: bool = False) -> Thought:
        enc, n12 = self.encode(obs, memory, since_command_min)
        a, b = N12_SPLIT["context"]
        ctx = n12[a:b].astype(F32)
        mem = n12[N12_SPLIT["memory"][0]:N12_SPLIT["memory"][1]].astype(F32)
        prio = n12[N12_SPLIT["priorities"][0]:N12_SPLIT["priorities"][1]].astype(F32)
        wait_logit = float(n12[N12_SPLIT["wait"][0]])
        h0 = self.nets.forward("H0", compose("H0", ctx=ctx, prio=prio, raw=np.array([min(since_command_min / 5.0, 5.0)], dtype=F32))[None])[0, 0]
        scores: dict[str, np.ndarray] = {}
        inputs: dict[str, np.ndarray] = {}
        for head, lst in cands.items():
            x = self.head_inputs(head, lst, enc, ctx, prio, obs)
            if keep_inputs:
                inputs[head] = x
            if len(lst) == 0:
                scores[head] = zeros(0)
                continue
            out = self.nets.forward(head, x)[:, 0]
            bias = 0.0 if head == "H1" else float(prio[HEAD_DOMAIN[head]])
            temp = float(np.clip(self.nets.temp[HEAD_NAMES.index(head)], TEMP_MIN, TEMP_MAX))
            scores[head] = ((out + bias) / temp).astype(F32)
        return Thought(ctx, mem, prio, float(h0) + wait_logit, scores, enc, inputs)
