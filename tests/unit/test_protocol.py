import base64

import pytest

from relayx.constants import AAD_SIZE, HEADER_SIZE
from relayx.crypto.aead import open_packet
from relayx.errors import CryptoError, PacketExpiredError, ReplayDetectedError
from relayx.pipeline import decode_message, encode_message
from relayx.protocol.models import RelayRequest
from relayx.protocol.replay import ReplayCache

KEY = base64.b64encode(b"k" * 32).decode()
KEY_BYTES = b"k" * 32
REQ = RelayRequest(
    "0" * 32, "GET", "https", "example.com", 443, "/", "", (("accept", "*/*"),), b""
)


def test_packet_roundtrip_and_header_sizes():
    packet = encode_message(REQ, KEY_BYTES, compression_enabled=False)
    assert len(packet) >= HEADER_SIZE
    opened = open_packet(packet, KEY_BYTES, 1024 * 1024)
    assert packet[:AAD_SIZE]
    assert opened.type_id == 1
    assert decode_message(packet, KEY_BYTES) == REQ


def test_tampered_aad_fails():
    packet = bytearray(encode_message(REQ, KEY_BYTES, compression_enabled=False))
    packet[2] ^= 1
    with pytest.raises((CryptoError, Exception)):
        decode_message(bytes(packet), KEY_BYTES)


def test_replay_inserts_only_after_authentication():
    cache = ReplayCache(window_seconds=60, max_entries=10)
    packet = bytearray(encode_message(REQ, KEY_BYTES, compression_enabled=False))
    packet[-1] ^= 1
    with pytest.raises(Exception):
        decode_message(bytes(packet), KEY_BYTES, replay_cache=cache)
    good = encode_message(REQ, KEY_BYTES, compression_enabled=False)
    decode_message(good, KEY_BYTES, replay_cache=cache)


def test_duplicate_replay_rejected():
    cache = ReplayCache(window_seconds=60, max_entries=10)
    packet = encode_message(REQ, KEY_BYTES, compression_enabled=False)
    decode_message(packet, KEY_BYTES, replay_cache=cache)
    with pytest.raises(ReplayDetectedError):
        decode_message(packet, KEY_BYTES, replay_cache=cache)


def test_expired_replay_rejected():
    cache = ReplayCache(window_seconds=1, max_entries=10)
    with pytest.raises(PacketExpiredError):
        cache.check_and_store(b"a" * 16, 1000, now_ms=3000)
