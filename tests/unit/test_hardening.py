import base64

import pytest
from pydantic import ValidationError

from relayx.config import RelaySettings
from relayx.errors import ProtocolError, RequestTooLargeError
from relayx.http.parser import read_request
from relayx.pipeline import decode_message, encode_message
from relayx.protocol import codec
from relayx.protocol.models import RelayRequest
from relayx.protocol.replay import ReplayCache
from relayx.server.endpoint import _error_from_exception, read_limited_body
from relayx.server.forwarder import Forwarder

KEY = b"k" * 32
KEY_B64 = base64.b64encode(KEY).decode()
REQ_ID = "1" * 32


def request(**overrides):
    values = {
        "request_id": REQ_ID,
        "method": "GET",
        "scheme": "https",
        "host": "example.com",
        "port": 443,
        "path": "/",
        "query": "",
        "headers": (("accept", "*/*"),),
        "body": b"",
    }
    values.update(overrides)
    return RelayRequest(**values)


def test_method_token_validation_rejects_invalid_token():
    with pytest.raises(ProtocolError):
        request(method="BAD METHOD")


def test_header_validation_rejects_invalid_name_and_crlf_value():
    with pytest.raises(ProtocolError):
        request(headers=(("bad name", "x"),))
    with pytest.raises(ProtocolError):
        request(headers=(("x-test", "x\r\nInjected: y"),))


def test_codec_rejects_primitive_type_mismatch():
    msg = {
        "version": 1,
        "type": "request",
        "request_id": REQ_ID,
        "method": 123,
        "scheme": "https",
        "host": "example.com",
        "port": 443,
        "path": "/",
        "query": "",
        "headers": [],
        "body": b"",
    }
    import msgpack

    with pytest.raises(Exception):
        codec.loads(msgpack.packb(msg, use_bin_type=True))


def test_decoded_request_body_size_limit():
    packet = encode_message(request(body=b"xx"), KEY, compression_enabled=False)
    with pytest.raises(RequestTooLargeError):
        decode_message(packet, KEY, max_request_body_bytes=1)


class FakeReader:
    def __init__(self, data: bytes):
        self.data = bytearray(data)

    async def read(self, n: int) -> bytes:
        if not self.data:
            return b""
        out = self.data[:n]
        del self.data[:n]
        return bytes(out)

    async def readexactly(self, n: int) -> bytes:
        out = self.data[:n]
        del self.data[:n]
        return bytes(out)


@pytest.mark.asyncio
async def test_bounded_http_header_reading_rejects_before_terminator():
    reader = FakeReader(b"GET / HTTP/1.1\r\n" + b"x" * 20)
    with pytest.raises(RequestTooLargeError):
        await read_request(reader, max_header_bytes=16, max_body_bytes=10)


class FakeRequest:
    def __init__(self, chunks):
        self.chunks = chunks

    async def stream(self):
        for chunk in self.chunks:
            yield chunk


@pytest.mark.asyncio
async def test_bounded_carrier_body_reading():
    with pytest.raises(Exception):
        await read_limited_body(FakeRequest([b"aa", b"bb"]), max_bytes=3)


class FakeStreamResponse:
    status_code = 200
    reason_phrase = "OK"

    class Headers:
        def multi_items(self):
            return []

    headers = Headers()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def aiter_bytes(self):
        yield b"aa"
        yield b"bb"


class FakeClient:
    def stream(self, *args, **kwargs):
        return FakeStreamResponse()


@pytest.mark.asyncio
async def test_streaming_upstream_response_size_enforcement():
    result = await Forwarder(FakeClient(), max_response_body_bytes=3).forward(request())
    assert result.error_code == "response_too_large"


def test_replay_error_mapping():
    from relayx.errors import ReplayDetectedError

    err = _error_from_exception(ReplayDetectedError("duplicate"))
    assert err.error_code == "replay_detected"


def test_config_range_and_secret_validation():
    with pytest.raises(ValidationError):
        RelaySettings(auth_token="x", encryption_key="x")
    with pytest.raises(ValidationError):
        RelaySettings(auth_token="x", encryption_key=KEY_B64, max_request_body_bytes=0)


class FakeCarrierResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self):
        return None


class FakeCarrierClient:
    def __init__(self, content: bytes):
        self.content = content

    async def post(self, *args, **kwargs):
        return FakeCarrierResponse(self.content)


class FakeSettings:
    auth_token = "auth"
    relay_url = "http://relay.test/relay"
    timeout_seconds = 30.0
    compression_enabled = False
    compression_threshold_bytes = 1024
    replay_window_seconds = 300
    replay_cache_max_entries = 100
    allowed_clock_skew_seconds = 30
    max_carrier_body_bytes = 1024 * 1024
    max_decompressed_bytes = 1024 * 1024
    max_request_body_bytes = 1024 * 1024
    max_response_body_bytes = 1024 * 1024

    @property
    def encryption_key_bytes(self):
        return KEY


@pytest.mark.asyncio
async def test_relay_client_validates_response_request_id_correlation():
    from relayx.client.relay_client import RelayClient
    from relayx.protocol.models import RelayResponse

    mismatched = encode_message(
        RelayResponse("2" * 32, 200, "OK", tuple(), b""), KEY, compression_enabled=False
    )
    client = RelayClient(FakeSettings(), FakeCarrierClient(mismatched))
    with pytest.raises(ValueError):
        await client.send(request())


def test_content_length_validation_rejects_duplicates_and_invalid_values():
    from relayx.http.parser import _content_length

    with pytest.raises(ProtocolError):
        _content_length([("Content-Length", "1"), ("Content-Length", "1")])
    with pytest.raises(ProtocolError):
        _content_length([("Content-Length", "-1")])
    with pytest.raises(ProtocolError):
        _content_length([("Content-Length", "abc")])


def test_replay_cache_validates_nonce_size():
    with pytest.raises(ProtocolError):
        ReplayCache().check_and_store(b"short", 1, now_ms=1)


def test_error_mapping_preserves_request_id_when_available():
    from relayx.errors import RequestTooLargeError

    err = _error_from_exception(RequestTooLargeError("large"), REQ_ID)
    assert err.request_id == REQ_ID
    assert err.error_code == "request_too_large"


@pytest.mark.asyncio
async def test_limited_body_rejects_oversized_chunk_before_buffering():
    with pytest.raises(Exception):
        await read_limited_body(FakeRequest([b"a" * 10]), max_bytes=3)
