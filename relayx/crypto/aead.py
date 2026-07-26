"""RelayX v1 binary packet sealing and opening."""

from __future__ import annotations

import secrets
import struct
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from relayx.constants import (
    AAD_SIZE,
    AEAD_NONCE_SIZE,
    ALLOWED_FLAGS,
    FLAG_COMPRESSED,
    HEADER_SIZE,
    MAGIC,
    NONCE_ID_SIZE,
    RESERVED,
    VERSION,
)
from relayx.errors import CryptoError, ProtocolError


@dataclass(frozen=True, slots=True)
class OpenedPacket:
    type_id: int
    compressed: bool
    timestamp_ms: int
    nonce_id: bytes
    plaintext: bytes


def seal(
    plaintext: bytes,
    key: bytes,
    type_id: int,
    compressed: bool,
    timestamp_ms: int | None = None,
) -> bytes:
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    flags = FLAG_COMPRESSED if compressed else 0
    nonce_id = secrets.token_bytes(NONCE_ID_SIZE)
    aead_nonce = secrets.token_bytes(AEAD_NONCE_SIZE)
    aad = _aad(type_id, flags, timestamp_ms, nonce_id, aead_nonce)
    ciphertext = ChaCha20Poly1305(key).encrypt(aead_nonce, plaintext, aad)
    return aad + struct.pack("!I", len(ciphertext)) + ciphertext


def open_packet(packet: bytes, key: bytes, max_ciphertext_bytes: int) -> OpenedPacket:
    if len(packet) < HEADER_SIZE:
        raise ProtocolError("packet is too short")
    aad = packet[:AAD_SIZE]
    magic, version, type_id, flags, reserved, timestamp_ms, nonce_id, aead_nonce = (
        _parse_aad(aad)
    )
    if (
        magic != MAGIC
        or version != VERSION
        or type_id not in {1, 2, 3}
        or flags & ~ALLOWED_FLAGS
        or reserved != RESERVED
    ):
        raise ProtocolError("invalid packet header")
    ciphertext_len = struct.unpack("!I", packet[AAD_SIZE:HEADER_SIZE])[0]
    if ciphertext_len == 0 or ciphertext_len > max_ciphertext_bytes:
        raise ProtocolError("invalid ciphertext length")
    ciphertext = packet[HEADER_SIZE:]
    if len(ciphertext) != ciphertext_len:
        raise ProtocolError("ciphertext length mismatch")
    try:
        plaintext = ChaCha20Poly1305(key).decrypt(aead_nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise CryptoError("packet authentication failed") from exc
    return OpenedPacket(
        type_id, bool(flags & FLAG_COMPRESSED), timestamp_ms, nonce_id, plaintext
    )


def _aad(
    type_id: int, flags: int, timestamp_ms: int, nonce_id: bytes, aead_nonce: bytes
) -> bytes:
    if len(nonce_id) != NONCE_ID_SIZE or len(aead_nonce) != AEAD_NONCE_SIZE:
        raise ProtocolError("invalid nonce size")
    return struct.pack(
        "!4sBBBBQ16s12s",
        MAGIC,
        VERSION,
        type_id,
        flags,
        RESERVED,
        timestamp_ms,
        nonce_id,
        aead_nonce,
    )


def _parse_aad(aad: bytes) -> tuple[bytes, int, int, int, int, int, bytes, bytes]:
    if len(aad) != AAD_SIZE:
        raise ProtocolError("invalid AAD size")
    return struct.unpack("!4sBBBBQ16s12s", aad)
