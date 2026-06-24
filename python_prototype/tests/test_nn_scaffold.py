import os

import pytest

try:
    import torch
except ImportError:
    torch = None

from duel_mastermind.nn.dataset import STEP_DIM, MAX_STEPS, generate_traces


@pytest.mark.skipif(torch is None, reason="torch not installed")
class TestNNScaffold:
    def test_dataset_shapes(self):
        X, y = generate_traces(num_secrets=4, seed=0)
        assert X.shape[0] == y.shape[0]
        assert X.shape[1] == MAX_STEPS * STEP_DIM
        assert y.shape[1] == 4

    def test_model_forward(self):
        from duel_mastermind.nn.model import build_model

        X, _ = generate_traces(num_secrets=2, seed=1)
        model = build_model(hidden=32)
        out = model(torch.tensor(X[:1]))
        assert out.shape[-1] == 40

    @pytest.mark.skipif(os.environ.get("DMB_NN_SMOKE_TRAIN") != "1", reason="optional smoke train")
    def test_smoke_train(self):
        from duel_mastermind.nn import train as train_mod

        train_mod.main()
