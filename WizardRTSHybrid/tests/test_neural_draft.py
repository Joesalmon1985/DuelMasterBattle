"""The neural drafting module (plan v2 9.2): features, imitation training, persistence and the module-swap hook."""
import numpy as np

from wizard_rts import ai_plus, draft
from wizard_rts.learn import draft_module as dm
from wizard_rts.world import HybridWorld


def world():
    w = HybridWorld(507, profile="campaign")
    w.ai_enabled = False
    w.cardset, w.draft_v2 = "v2", True
    w._seq = 0
    for _ in range(3):
        w._seq += 1
        w.advance(1000, w._seq, snapshot=False)
    return w


def test_feature_shapes_and_permutation_equivariance():
    w = world()
    f = draft.state(w)["ring"][0]
    offers = list(w.tech[f]["offers"])
    s = dm.state_features(w, f)
    cards = np.stack([dm.card_features(w, f, c) for c in offers])
    assert s.shape == (dm.STATE_DIM,) and cards.shape == (len(offers), dm.CARD_DIM) and np.isfinite(cards).all()
    sc = dm.DraftScorer(seed=3)
    a = sc.scores(s, cards)
    perm = np.random.RandomState(1).permutation(len(offers))
    assert np.allclose(sc.scores(s, cards[perm]), a[perm])  # the order of the pack cannot matter


def test_training_learns_a_separable_choice_and_save_load_agree(tmp_path):
    rng = np.random.RandomState(0)
    samples = []
    for _ in range(80):
        cards = rng.rand(5, dm.CARD_DIM)
        cards[:, 0] = 0
        t = int(rng.randint(5))
        cards[t, 0] = 1.0  # the card with this flag is the heuristic's choice
        samples.append({"state": rng.rand(dm.STATE_DIM).tolist(), "cards": cards.tolist(), "target": t})
    sc = dm.DraftScorer(seed=1)
    curve = sc.train(samples, epochs=30, lr=5e-3)
    assert curve[-1] < 0.5 * curve[0] and sc.accuracy(samples) > 0.95
    path = tmp_path / "m.json"
    sc.save(str(path))
    other = dm.DraftScorer.load(str(path))
    s = samples[0]
    assert np.allclose(other.scores(np.array(s["state"]), np.array(s["cards"])), sc.scores(np.array(s["state"]), np.array(s["cards"])))


def test_module_swap_hook_drafts_with_the_learned_scorer_and_the_recorder_logs_heuristic_picks():
    w = world()
    ring = draft.state(w)["ring"]
    f_neural, f_heur = ring[0], ring[1]

    class First:
        def pick(self, world, faction, offers):
            return sorted(offers)[-1]  # a recognisable rule that differs from the heuristic's score

    w.neural_drafters = {f_neural: First()}
    w.draft_recorder = []
    assert ai_plus.pick_card(w, f_neural) == sorted(w.tech[f_neural]["offers"])[-1]
    ai_plus.pick_card(w, f_heur)
    assert len(w.draft_recorder) == 1 and w.draft_recorder[0]["faction"] == f_heur  # only heuristic picks are recorded
    rec = w.draft_recorder[0]
    assert rec["chosen"] == rec["offers"][rec["target"]] and len(rec["state"]) == dm.STATE_DIM
