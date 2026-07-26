"""Encryption key loading."""

from __future__ import annotations

import base64
import binascii

from relayx.errors import ConfigError


def decode_encryption_key(value: str) -> bytes:
    try:
        key = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ConfigError("RELAYX_ENCRYPTION_KEY must be base64") from exc
    if len(key) != 32:
        raise ConfigError("RELAYX_ENCRYPTION_KEY must decode to 32 bytes")
    return key
