"""Neural drafting module (plan v2 9.2, stage 1): a card scorer over (faction state, card) features, trained to imitate the heuristic
drafter by softmax cross-entropy over the pack, then evaluated in games against it.

The scorer is a small NumPy MLP applied to every card in the pack with the same state vector (permutation-equivariant: the order of
the pack cannot matter). Cards are described from the content graph (era, tribe fit, what they produce, what they consume, cost,
military flag), so the network can score a card it has never seen. Inference needs only NumPy.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from wizard_rts import tech
from wizard_rts.learn import nn

WARE_GROUPS = {
    "food": ("ration", "bread", "fish", "meat", "smoked_fish", "smoked_meat", "cheese", "beer", "wine"),
    "metal": ("iron", "coal", "gold", "iron_ore", "coal_ore", "gold_ore", "bronze", "steel"),
    "wood": ("log", "plank", "blackwood", "ironwood", "rope", "bark"),
    "stone": ("granite", "marble", "brick", "clay", "quartz", "diamond"),
    "cloth": ("cloth", "spidercloth", "fur", "reed", "tabard", "garment"),
}
MILITARY = ("barracks", "vehicle_factory", "war_lodge", "defense", "flame_tower", "tesla_coil", "naval_yard", "sub_pen")
CARD_DIM = 4 + 1 + 4 + 5 + 5 + 5 + 4
STATE_DIM = 4 + 5 + 8 + 5


def _group_flags(wares: list[str]) -> list[float]:
    return [1.0 if any(w in grp for w in wares) else 0.0 for grp in WARE_GROUPS.values()]


def card_features(world: Any, faction: str, cid: str) -> np.ndarray:
    from wizard_rts import ai as base
    from wizard_rts.content import graph

    ents = graph.entities()
    c = tech.lookup()[cid]
    tribe = world.faction_info.get(faction, {}).get("tribe", "")
    v = [1.0 if c["era"] == i else 0.0 for i in range(4)]
    v.append(1.0 if c.get("tribe", "") in ("", tribe) else 0.0)  # usable by this faction's tribe
    es = [ents[e] for e in c.get("entities", []) if e in ents]
    wl = [e for e in es if e["game"] == "widelands"]
    v += [len(es) / 2.0, 1.0 if any(e["type"] == "unit" for e in es) else 0.0, 1.0 if any(e["type"] == "building" for e in es) else 0.0,
          1.0 if any(e["id"] in MILITARY or e.get("producer") in MILITARY for e in es) else 0.0]
    outs = [w for e in wl for w in e.get("outputs", [])]
    ins = [w for e in wl for w in e.get("inputs", [])]
    v += _group_flags(outs)
    v += _group_flags(ins)
    fresh = [w for w in outs if not base._makes(world, faction, w)]
    fed = [w for w in ins if base._makes(world, faction, w) or base._stock(world, faction, w) > 0]
    v += _group_flags(fresh)
    cost = sum(sum(e["cost"].values()) for e in es)
    v += [min(cost / 40.0, 2.0), len(fresh) / 3.0, (len(fed) / max(1, len(ins))) if ins else 1.0, 1.0 if any(e["id"] in tech.FOUNDATION_KINDS for e in es) else 0.0]
    return np.array(v, dtype=np.float64)


def state_features(world: Any, faction: str) -> np.ndarray:
    from wizard_rts import ai as base
    from wizard_rts import ai_plus, territory, vp

    era = int(getattr(world, "era_index", 0))
    v = [1.0 if era == i else 0.0 for i in range(4)]
    st = world.tech.get(faction, {})
    held = [tech.lookup()[c] for c in st.get("cards", [])]
    wh = territory.command_centers(world, faction)
    wh0 = wh[0] if wh else None
    stock = lambda g: min(base._stock(world, faction, g, wh0) / 30.0, 3.0) if wh0 else 0.0  # noqa: E731
    v += [stock("log"), stock("plank"), stock("granite"), stock("ration"), stock("iron")]
    mine = [b for b in world.buildings.values() if b["faction_name"] == faction and "hp" in b and int(b["hp"]) > 0]
    held_outs = [w for c in held for e in c.get("entities", []) for w in __import__("wizard_rts.content.graph", fromlist=["x"]).entities().get(e, {}).get("outputs", [])]
    v += [min(ai_plus._food(world, faction) / 20.0, 3.0), 1.0 if (ai_plus._threats(world, faction) or world.fstats.get(faction, {}).get("building_losses", 0) > 0) else 0.0,
          len(wh) / 8.0, len(mine) / 100.0, len(held) / 14.0, 1.0 if any(k in MILITARY for c in held for k in c.get("kinds", [])) else 0.0,
          1.0 if any(g in held_outs for g in WARE_GROUPS["food"]) else 0.0, vp.totals(world).get(faction, 0) / 10.0]
    rnd = world.__dict__.get("draft", {}).get("round", 0)
    v += [min(rnd, 7) / 7.0, 1.0 if tech.pool(world) and getattr(world, "cardset", "") == "v2" else 0.0, 1.0 if len(wh) <= 1 else 0.0, 0.0, 0.0]
    return np.array(v[:STATE_DIM], dtype=np.float64)


class DraftScorer:
    def __init__(self, hidden: tuple[int, ...] = (48, 24), seed: int = 0) -> None:
        self.net = nn.MLP([STATE_DIM + CARD_DIM, *hidden, 1], seed=seed, out_scale=0.5)

    def scores(self, state: np.ndarray, cards: np.ndarray) -> np.ndarray:
        x = np.concatenate([np.repeat(state[None, :], len(cards), axis=0), cards], axis=1)
        return self.net.predict(x)[:, 0]

    def pick(self, world: Any, faction: str, offers: list[str]) -> str:
        cards = np.stack([card_features(world, faction, c) for c in offers])
        s = self.scores(state_features(world, faction), cards)
        return offers[int(np.argmax(s))]

    def train(self, samples: list[dict[str, Any]], epochs: int = 40, lr: float = 3e-3, seed: int = 0) -> list[float]:
        rng = np.random.RandomState(seed)
        curve = []
        for _ in range(epochs):
            order = rng.permutation(len(samples))
            total = 0.0
            for i in order:
                s = samples[i]
                st, cards, y = np.array(s["state"]), np.array(s["cards"]), int(s["target"])
                x = np.concatenate([np.repeat(st[None, :], len(cards), axis=0), cards], axis=1)
                out, acts = self.net.forward(x)
                loss, g = nn.xent_grad(out.T, None, np.array([y]))
                gW, gb = self.net.backward(g.T, acts)
                self.net.step(gW, gb, lr=lr)
                total += loss
            curve.append(total / max(1, len(samples)))
        return curve

    def accuracy(self, samples: list[dict[str, Any]]) -> float:
        hit = 0
        for s in samples:
            sc = self.scores(np.array(s["state"]), np.array(s["cards"]))
            hit += int(np.argmax(sc)) == int(s["target"])
        return hit / max(1, len(samples))

    def save(self, path: str) -> None:
        self.net.save(path)

    @classmethod
    def load(cls, path: str) -> "DraftScorer":
        d = cls()
        d.net = nn.MLP.load(path)
        return d


def record(world: Any, faction: str, offers: list[str], chosen: str) -> None:
    """Called by the heuristic drafter when `world.draft_recorder` (a list) exists: one imitation sample per pick."""
    rec = world.__dict__.get("draft_recorder")
    if rec is None or chosen not in offers:
        return
    rec.append({"state": state_features(world, faction).tolist(), "cards": [card_features(world, faction, c).tolist() for c in offers],
                "target": offers.index(chosen), "faction": faction, "era": int(getattr(world, "era_index", 0)), "offers": list(offers), "chosen": chosen,
                "game_ms": int(world.dmb.clock.get("game_ms", 0))})
