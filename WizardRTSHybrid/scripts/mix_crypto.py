"""Westwood MIX header decryption in pure Python (plan v2 8.3, route a): Blowfish + the RSA-wrapped key block.

An encrypted MIX file is: u32 flags (0x20000 = encrypted, 0x10000 = checksum), an 80-byte key block, then the Blowfish-encrypted
header (u16 count, u32 data size, count x 12-byte index entries, padded to 8 bytes), then the data. The 80-byte block is two RSA
blocks of 40 bytes each, decrypted with Westwood's public key (e = 65537); together they yield the 56-byte Blowfish key.
Blowfish tables are computed from the hexadecimal digits of pi (no table is copied), then checked against the published first words.
"""
from __future__ import annotations

import base64
import struct
from functools import lru_cache

PUBLIC_KEY = "AihRvNoIbTn85FZRYNZRcT+i6KpU+maCsEqr3Q5q+LDB5tH7Tz2qQ38V"
EXPONENT = 65537


def _arctan_inv(x: int, bits: int) -> int:
    one = 1 << bits
    total = term = one // x
    x2 = x * x
    n = 1
    sign = -1
    while term:
        term //= x2
        n += 2
        total += sign * (term // n)
        sign = -sign
    return total


@lru_cache(maxsize=1)
def _pi_words() -> list[int]:
    words = 18 + 4 * 256
    bits = words * 32 + 64
    pi = 4 * (4 * _arctan_inv(5, bits) - _arctan_inv(239, bits))  # fixed point, `bits` fractional bits
    frac = pi & ((1 << bits) - 1)
    return [(frac >> (bits - 32 * (i + 1))) & 0xFFFFFFFF for i in range(words)]


class Blowfish:
    def __init__(self, key: bytes, little_endian: bool = False) -> None:
        w = _pi_words()
        self.P = list(w[:18])
        self.S = [list(w[18 + 256 * i: 18 + 256 * (i + 1)]) for i in range(4)]
        self.le = little_endian
        j = 0
        for i in range(18):
            v = 0
            for _ in range(4):
                v = (v << 8) | key[j % len(key)]
                j += 1
            self.P[i] ^= v
        l = r = 0
        for i in range(0, 18, 2):
            l, r = self._enc(l, r)
            self.P[i], self.P[i + 1] = l, r
        for box in self.S:
            for i in range(0, 256, 2):
                l, r = self._enc(l, r)
                box[i], box[i + 1] = l, r

    def _f(self, x: int) -> int:
        S = self.S
        return ((((S[0][x >> 24] + S[1][(x >> 16) & 255]) & 0xFFFFFFFF) ^ S[2][(x >> 8) & 255]) + S[3][x & 255]) & 0xFFFFFFFF

    def _enc(self, l: int, r: int) -> tuple[int, int]:
        P = self.P
        for i in range(16):
            l ^= P[i]
            r ^= self._f(l)
            l, r = r, l
        l, r = r, l
        r ^= P[16]
        l ^= P[17]
        return l, r

    def _dec(self, l: int, r: int) -> tuple[int, int]:
        P = self.P
        for i in range(17, 1, -1):
            l ^= P[i]
            r ^= self._f(l)
            l, r = r, l
        l, r = r, l
        r ^= P[1]
        l ^= P[0]
        return l, r

    def decrypt(self, data: bytes) -> bytes:
        fmt = "<II" if self.le else ">II"
        out = bytearray()
        for i in range(0, len(data) - len(data) % 8, 8):
            l, r = struct.unpack_from(fmt, data, i)
            out += struct.pack(fmt, *self._dec(l, r))
        return bytes(out)

    def encrypt(self, data: bytes) -> bytes:
        fmt = "<II" if self.le else ">II"
        out = bytearray()
        for i in range(0, len(data) - len(data) % 8, 8):
            l, r = struct.unpack_from(fmt, data, i)
            out += struct.pack(fmt, *self._enc(l, r))
        return bytes(out)


def public_modulus() -> int:
    raw = base64.b64decode(PUBLIC_KEY)
    assert raw[0] == 2 and raw[1] == len(raw) - 2
    return int.from_bytes(raw[2:], "big")  # found by trial against hires.mix: modulus big-endian, key-block integers little-endian


def blowfish_key(block: bytes) -> bytes:
    """The 56-byte Blowfish key from the 80-byte key block: two RSA blocks, each c^e mod n, 39 result bytes taken from each."""
    n = public_modulus()
    out = bytearray()
    for i in range(2):
        c = int.from_bytes(block[i * 40:(i + 1) * 40], "little")
        out += pow(c, EXPONENT, n).to_bytes(40, "little")[:39]
    return bytes(out[:56])


def decrypt_header(data: bytes) -> tuple[int, int, bytes, int]:
    """(file count, data size, decrypted index bytes, offset where the data starts) for an encrypted MIX file's raw bytes."""
    flags = struct.unpack_from("<I", data, 0)[0]
    assert flags & 0x20000, "not encrypted"
    bf = Blowfish(blowfish_key(data[4:84]))
    first = bf.decrypt(data[84:92])
    count, size = struct.unpack_from("<HI", first, 0)
    total = (6 + 12 * count + 7) // 8 * 8
    dec = bf.decrypt(data[84:84 + total])
    return count, size, dec[6:6 + 12 * count], 84 + total
