"""Build a tiny valid PNG (pure stdlib: zlib + struct) for vision tests."""
import struct
import sys
import zlib
from pathlib import Path

FIX = Path(__file__).resolve().parent
OUT = FIX / "sample.png"

W, H = 64, 48


def chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def make() -> Path:
    # simple two-tone pattern: dark left half, light right half
    rows = []
    for _ in range(H):
        left = b"\x30" * (W // 2)
        right = b"\xd0" * (W - W // 2)
        rows.append(b"\x00" + left + right)   # filter byte 0 per row
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 0, 0, 0, 0)  # 8-bit grayscale
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
           + chunk(b"IEND", b""))
    OUT.write_bytes(png)
    return OUT


if __name__ == "__main__":
    print("png:", make().name, make().stat().st_size, "bytes")
    print("IMAGE FIXTURE READY")
