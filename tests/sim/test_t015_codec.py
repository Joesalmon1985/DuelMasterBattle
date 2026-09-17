"""T015 frame codec shared fixtures."""

from __future__ import annotations

import json
import struct

import pytest

from sim.dmb.bridge.codec import FrameCodec, MAX_FRAME


def test_split_header_and_body() -> None:
    codec = FrameCodec()
    frame = codec.encode({"ok": True})
    assert codec.feed(frame[:2]) == []
    assert codec.feed(frame[2:6]) == []
    assert codec.feed(frame[6:]) == [{"ok": True}]


def test_split_multibyte_text() -> None:
    codec = FrameCodec()
    payload = {"msg": "café"}
    frame = codec.encode(payload)
    mid = len(frame) // 2
    assert codec.feed(frame[:mid]) == []
    assert codec.feed(frame[mid:]) == [payload]


def test_two_frames_per_read() -> None:
    codec = FrameCodec()
    a = codec.encode({"n": 1})
    b = codec.encode({"n": 2})
    assert codec.feed(a + b) == [{"n": 1}, {"n": 2}]


def test_malformed_json_raises() -> None:
    codec = FrameCodec()
    body = b"{not-json"
    frame = struct.pack(">I", len(body)) + body
    with pytest.raises(json.JSONDecodeError):
        codec.feed(frame)


def test_oversize_frame_raises() -> None:
    codec = FrameCodec()
    with pytest.raises(ValueError):
        codec.feed(struct.pack(">I", MAX_FRAME + 1) + b"x")


def test_godot_compatible_envelope_roundtrip() -> None:
    # Godot and Python must agree on big-endian length + UTF-8 JSON.
    codec = FrameCodec()
    payload = {"kind": "Handshake", "protocol_version": 1, "token": "abc"}
    frame = codec.encode(payload)
    assert frame[:4] == struct.pack(">I", len(frame) - 4)
    assert codec.feed(frame) == [payload]
