"""Length-prefixed JSON frame codec."""

from __future__ import annotations

import json
import struct
from typing import Any


MAX_FRAME = 8 * 1024 * 1024


class FrameCodec:
    def __init__(self) -> None:
        self._buffer = bytearray()

    def encode(self, payload: dict[str, Any]) -> bytes:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        if not body or len(body) > MAX_FRAME:
            raise ValueError("invalid frame size")
        return struct.pack(">I", len(body)) + body

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        self._buffer.extend(data)
        frames: list[dict[str, Any]] = []
        while True:
            if len(self._buffer) < 4:
                return frames
            (length,) = struct.unpack(">I", self._buffer[:4])
            if length == 0 or length > MAX_FRAME:
                raise ValueError("malformed or oversize frame")
            if len(self._buffer) < 4 + length:
                return frames
            body = bytes(self._buffer[4 : 4 + length])
            del self._buffer[: 4 + length]
            frames.append(json.loads(body.decode("utf-8")))
