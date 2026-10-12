"""Minimal reader for Tiberian Dawn / Red Alert .shp sprite files (OpenRA ShpTDSprite loader, format 0x80/0x40/0x20).

OpenRA ships a few of these loose in mods/ra/bits (weap3.shp, the war factory's roll-up door); the rest sit in the player's
own Red Alert content. Frames are returned as palette-index bytes; the palette comes from an already extracted frame.
"""
from __future__ import annotations

import struct


def lcw_decode(src: bytes, start: int, size: int) -> bytes:
    out = bytearray()
    i = start
    n = len(src)
    while i < n:
        c = src[i]
        i += 1
        if c == 0x80:
            break
        if not c & 0x80:  # 0cccpppp pppppppp: copy c+3 bytes from p bytes back
            count = ((c & 0x70) >> 4) + 3
            pos = ((c & 0x0F) << 8) | src[i]
            i += 1
            for _ in range(count):
                out.append(out[len(out) - pos])
        elif not c & 0x40:  # 10cccccc: copy the next c bytes
            count = c & 0x3F
            out += src[i:i + count]
            i += count
        elif c == 0xFE:  # fill
            count, val = struct.unpack_from("<HB", src, i)
            i += 3
            out += bytes([val]) * count
        elif c == 0xFF:  # absolute copy
            count, pos = struct.unpack_from("<HH", src, i)
            i += 4
            for k in range(count):
                out.append(out[pos + k])
        else:  # 11cccccc pppp: copy c+3 bytes from absolute position
            count = (c & 0x3F) + 3
            pos = struct.unpack_from("<H", src, i)[0]
            i += 2
            for k in range(count):
                out.append(out[pos + k])
    return bytes(out)


def xor_delta(base: bytearray, src: bytes) -> bytearray:
    out = bytearray(base)
    i = j = 0
    while i < len(src) and j < len(out):
        c = src[i]
        i += 1
        if not c & 0x80:
            count = c & 0x7F
            if count == 0:  # 0 count: run of xor with a byte
                count = src[i]
                val = src[i + 1]
                i += 2
                for _ in range(count):
                    out[j] ^= val
                    j += 1
            else:
                for _ in range(count):
                    out[j] ^= src[i]
                    i += 1
                    j += 1
        else:
            count = c & 0x7F
            if count == 0:
                count = struct.unpack_from("<H", src, i)[0]
                i += 2
                if count == 0:
                    break
                if count & 0x8000:
                    if count & 0x4000:
                        n = count & 0x3FFF
                        val = src[i]
                        i += 1
                        for _ in range(n):
                            out[j] ^= val
                            j += 1
                    else:
                        n = count & 0x7FFF
                        for _ in range(n):
                            out[j] ^= src[i]
                            i += 1
                            j += 1
                    continue
            j += count  # skip
    return out


def read_shp(data: bytes) -> tuple[int, int, list[bytes]]:
    count, _x, _y, width, height, _delta = struct.unpack_from("<HHHHHI", data, 0)
    heads = []
    for k in range(count):
        word, ref_offset, _ref_fmt = struct.unpack_from("<IHH", data, 14 + k * 8)
        heads.append((word & 0xFFFFFF, word >> 24, ref_offset))
    by_offset = {h[0]: k for k, h in enumerate(heads)}
    frames: list[bytes] = []
    size = width * height
    for k, (offset, fmt, ref_offset) in enumerate(heads):
        raw = data[offset:]
        if fmt == 0x80:
            frame = lcw_decode(raw, 0, size)
        else:  # 0x20 deltas the previous frame, 0x40 the frame at ref_offset; the delta stream is Format40, not LCW
            ref = k - 1 if fmt == 0x20 else by_offset.get(ref_offset, k - 1)
            frame = bytes(xor_delta(bytearray(frames[ref]), raw))
        frames.append(frame[:size].ljust(size, b"\0"))
    return width, height, frames
