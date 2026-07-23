"""Small encode/decode orchestration for RelayX packets."""
from __future__ import annotations
from relayx.compression import maybe_compress, maybe_decompress
from relayx.constants import DEFAULT_COMPRESSION_THRESHOLD_BYTES, DEFAULT_MAX_CARRIER_BODY_BYTES, DEFAULT_MAX_DECOMPRESSED_BYTES, DEFAULT_MAX_REQUEST_BODY_BYTES, DEFAULT_MAX_RESPONSE_BODY_BYTES
from relayx.crypto.aead import open_packet, seal
from relayx.errors import RequestTooLargeError, ResponseTooLargeError
from relayx.protocol import codec
from relayx.protocol.models import RelayError, RelayRequest, RelayResponse
from relayx.protocol.replay import ReplayCache

Message = RelayRequest | RelayResponse | RelayError

def encode_message(message: Message, key: bytes, *, compression_enabled: bool = True, compression_threshold: int = DEFAULT_COMPRESSION_THRESHOLD_BYTES) -> bytes:
    serialized = codec.dumps(message)
    payload, compressed = maybe_compress(serialized, compression_enabled, compression_threshold)
    return seal(payload, key, codec.message_type(message), compressed)

def decode_message(packet: bytes, key: bytes, *, replay_cache: ReplayCache | None = None, max_ciphertext_bytes: int = DEFAULT_MAX_CARRIER_BODY_BYTES, max_decompressed_bytes: int = DEFAULT_MAX_DECOMPRESSED_BYTES, max_request_body_bytes: int = DEFAULT_MAX_REQUEST_BODY_BYTES, max_response_body_bytes: int = DEFAULT_MAX_RESPONSE_BODY_BYTES) -> Message:
    opened = open_packet(packet, key, max_ciphertext_bytes)
    if replay_cache is not None:
        replay_cache.check_and_store(opened.nonce_id, opened.timestamp_ms)
    serialized = maybe_decompress(opened.plaintext, opened.compressed, max_decompressed_bytes)
    message = codec.loads(serialized, expected_type=opened.type_id)
    if isinstance(message, RelayRequest) and len(message.body) > max_request_body_bytes:
        raise RequestTooLargeError("decoded request body is too large")
    if isinstance(message, RelayResponse) and len(message.body) > max_response_body_bytes:
        raise ResponseTooLargeError("decoded response body is too large")
    return message
