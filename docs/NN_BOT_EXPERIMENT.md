# Neural Network Bot Experiment

Python-only experiment. **Not used by the Godot game.** No PyTorch/TensorFlow dependency in Godot.

## Approach
- **Teacher:** deterministic `SolverBot` (candidate elimination + minimax).
- **Student:** small PyTorch MLP in `python_prototype/duel_mastermind/nn/model.py`.
- **Data:** play traces from random secrets encoded as guess+feedback history tensors.
- **Goal:** scaffold evaluation and optional smoke training — not a production bot.

## What was completed
- `nn/dataset.py` — trace generation + encoding
- `nn/model.py` — MLP policy head
- `nn/policy_bot.py` — wrapper (falls back to solver)
- `nn/train.py` — time-boxed smoke training (2 epochs, 16 secrets default)
- `scripts/evaluate_bots.py` — difficulty metrics for Easy/Normal/Hard/Expert
- `tests/test_nn_scaffold.py` — shape/forward-pass tests (1 skipped optional full train)

## Metrics reported (not “wins in exactly X”)
- average guesses
- median guesses
- solved-within-12 percentage
- worst case on validation set
- failure count

Run evaluation:
```bash
cd python_prototype && python3 scripts/evaluate_bots.py
```

Optional smoke training (slow; not in default pytest):
```bash
DMB_NN_SMOKE_TRAIN=1 cd python_prototype && python3 -m pytest tests/test_nn_scaffold.py -k smoke_train
# or
cd python_prototype && python3 -m duel_mastermind.nn.train --epochs 2 --samples 16
```

## What remains
- Save/load trained weights and compare NN vs solver on full validation set
- Larger dataset and longer training (manual, time-boxed)
- No Godot integration planned
