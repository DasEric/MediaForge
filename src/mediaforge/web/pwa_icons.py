"""PWA icon generation (stdlib-only PNG writer)."""

import struct
import zlib

from ..logger import get_logger

logger = get_logger(__name__)


def _generate_pwa_icons():
    """Generate icon-192.png and icon-512.png in the static directory if missing.

    Uses only Python stdlib (struct + zlib) — no Pillow required.
    The icons are a solid #7c3aed (purple) square.

    Used by: app.py, called once during create_app() startup so the PWA
    manifest always has icon files to point to.
    """
    import os as _os
    static_dir = _os.path.join(_os.path.dirname(__file__), "static")

    def _png_bytes(size: int) -> bytes:
        """Create a minimal valid PNG: solid #7c3aed square of given size."""
        r, g, b = 0x7C, 0x3A, 0xED

        # Build raw image data: one filter byte (0) + RGB pixels per row
        row = bytes([0]) + bytes([r, g, b] * size)
        raw = row * size

        def _chunk(tag: bytes, data: bytes) -> bytes:
            length = struct.pack(">I", len(data))
            crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            return length + tag + data + crc

        signature = b"\x89PNG\r\n\x1a\n"
        ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        idat = _chunk(b"IDAT", zlib.compress(raw, 9))
        iend = _chunk(b"IEND", b"")
        return signature + ihdr + idat + iend

    for size in (192, 512):
        path = _os.path.join(static_dir, f"icon-{size}.png")
        if not _os.path.exists(path):
            try:
                with open(path, "wb") as f:
                    f.write(_png_bytes(size))
                logger.debug("[PWA] Generated %s", path)
            except Exception as exc:
                logger.warning("[PWA] Could not generate icon-%s.png: %s", size, exc)
