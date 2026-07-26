"""Threshold-based zstd compression helpers."""

from __future__ import annotations

import zstandard as zstd

from relayx.errors import CompressionError


def maybe_compress(data: bytes, enabled: bool, threshold: int) -> tuple[bytes, bool]:
    if not enabled or len(data) < threshold:
        return data, False
    try:
        return zstd.ZstdCompressor().compress(data), True
    except Exception as exc:
        raise CompressionError("compression failed") from exc


def maybe_decompress(data: bytes, compressed: bool, max_size: int) -> bytes:
    if not compressed:
        if len(data) > max_size:
            raise CompressionError("uncompressed payload exceeds maximum size")
        return data
    try:
        return zstd.ZstdDecompressor().decompress(data, max_output_size=max_size)
    except Exception as exc:
        raise CompressionError("decompression failed") from exc
