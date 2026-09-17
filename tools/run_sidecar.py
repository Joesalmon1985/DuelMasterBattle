#!/usr/bin/env python3
"""Launch the authoritative Python sidecar on loopback."""

from __future__ import annotations

import argparse
import secrets
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.dmb.bridge.server import SidecarServer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default="")
    parser.add_argument("--save-root", type=Path, default=ROOT / ".dmb_saves")
    parser.add_argument("--endpoint-file", type=Path, default=ROOT / ".dmb_endpoint.json")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--fixture", default="")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    token = args.token or secrets.token_hex(16)
    server = SidecarServer(
        token=token,
        save_root=args.save_root,
        port=args.port,
        fixture=args.fixture or None,
        seed=args.seed,
    )
    server.endpoint_file(args.endpoint_file)
    print(f"DMB_SIDECAR host={server.host} port={server.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
