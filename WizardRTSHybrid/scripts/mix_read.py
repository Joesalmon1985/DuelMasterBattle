"""Read files out of an unencrypted Red Alert .mix archive (the player's own OpenRA content, never committed whole).

Layout: u16 0, u16 flags, u16 count, u32 data size, then count x (u32 id, u32 offset, u32 length); data follows the table.
The id is the classic Westwood hash of the upper-cased file name (OpenRA PackageEntry.HashFilename, PackageHashType.Classic).
"""
from __future__ import annotations

import struct
from pathlib import Path


def classic_hash(name: str) -> int:
    name = name.upper()
    n = len(name)
    pad = (4 - n % 4) % 4
    data = name.encode("ascii") + b"\0" * pad
    h = 0
    for i in range(0, len(data), 4):
        h = ((h << 1) | (h >> 31)) & 0xFFFFFFFF
        h = (h + struct.unpack_from("<I", data, i)[0]) & 0xFFFFFFFF
    return h


class Mix:
    def __init__(self, path: str | Path) -> None:
        self.data = Path(path).read_bytes()
        assert struct.unpack_from("<H", self.data, 0)[0] == 0 and struct.unpack_from("<H", self.data, 2)[0] == 0, "encrypted or old mix"
        count = struct.unpack_from("<H", self.data, 4)[0]
        self.base = 10 + count * 12
        self.entries = {}
        for i in range(count):
            fid, off, ln = struct.unpack_from("<III", self.data, 10 + i * 12)
            self.entries[fid] = (off, ln)

    def read(self, name: str) -> bytes | None:
        e = self.entries.get(classic_hash(name))
        if e is None:
            return None
        return self.data[self.base + e[0]: self.base + e[0] + e[1]]
