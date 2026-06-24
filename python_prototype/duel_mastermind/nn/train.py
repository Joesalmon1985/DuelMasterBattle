"""Time-boxed smoke training for NN experiment."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--samples", type=int, default=16)
    args = parser.parse_args()
    try:
        import torch
        import torch.nn as nn
        from duel_mastermind.nn.dataset import generate_traces
        from duel_mastermind.nn.model import build_model
    except ImportError as e:
        print(f"NN training skipped: {e}")
        return
    X, y = generate_traces(num_secrets=args.samples, seed=0)
    model = build_model()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()
    for epoch in range(args.epochs):
        opt.zero_grad()
        logits = model(torch.tensor(X)).view(-1, 4, 10)
        loss = sum(loss_fn(logits[:, i], torch.tensor(y[:, i])) for i in range(4))
        loss.backward()
        opt.step()
        print(f"epoch {epoch+1} loss={loss.item():.4f}")
    print("Smoke training complete (weights not saved by default).")


if __name__ == "__main__":
    main()
