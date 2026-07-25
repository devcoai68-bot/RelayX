"""RelayX v1 message models."""
from __future__ import annotations
from dataclasses import dataclass
from typing import TypeAlias
from relayx.constants import VERSION
from relayx.errors import ProtocolError

HeaderList: TypeAlias = tuple[tuple[str, str], ...]

_ERROR_CODES = {
    "bad_request", "unauthorized", "invalid_packet", "decrypt_failed", "replay_detected",
    "packet_expired", "packet_from_future", "replay_cache_full", "unsupported_version",
    "unsupported_method", "unsupported_transfer_encoding", "request_too_large",
    "response_too_large", "upstream_timeout", "upstream_connection_failed",
    "upstream_protocol_error", "compression_failed", "decompression_failed", "internal_error",
}
_TOKEN_SEPARATORS = set('()<>@,;:\\"/[]?={} \t')

def _has_ctl(value: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in value)

def validate_http_token(value: str, field: str) -> None:
    if not isinstance(value, str) or not value or _has_ctl(value) or any(ch in _TOKEN_SEPARATORS for ch in value):
        raise ProtocolError(f"invalid HTTP {field} token")

def validate_header_list(value: HeaderList) -> HeaderList:
    if not isinstance(value, tuple):
        raise ProtocolError("headers must be a tuple")
    for item in value:
        if not (isinstance(item, tuple) and len(item) == 2 and all(isinstance(x, str) for x in item)):
            raise ProtocolError("headers must contain string pairs")
        name, header_value = item
        validate_http_token(name, "header name")
        if "\r" in header_value or "\n" in header_value:
            raise ProtocolError("header values must not contain CR or LF")
    return value

@dataclass(frozen=True, slots=True)
class RelayRequest:
    request_id: str
    method: str
    scheme: str
    host: str
    port: int | None
    path: str
    query: str
    headers: HeaderList
    body: bytes
    version: int = VERSION
    type: str = "request"
    def __post_init__(self) -> None:
        validate_common(self.version, self.type, self.request_id)
        if self.type != "request": raise ProtocolError("invalid request type")
        validate_http_token(self.method, "method")
        if self.method.upper() == "CONNECT": raise ProtocolError("CONNECT is unsupported")
        if self.scheme not in {"http", "https"}: raise ProtocolError("invalid scheme")
        if not isinstance(self.host, str) or not self.host or _has_ctl(self.host) or any(ch in self.host for ch in "/?#") or "://" in self.host:
            raise ProtocolError("invalid host")
        if self.port is not None and (type(self.port) is not int or not (1 <= self.port <= 65535)):
            raise ProtocolError("invalid port")
        if not isinstance(self.path, str) or not self.path.startswith("/") or _has_ctl(self.path) or "://" in self.path or "?" in self.path:
            raise ProtocolError("invalid path")
        if not isinstance(self.query, str) or _has_ctl(self.query):
            raise ProtocolError("invalid query")
        validate_header_list(self.headers)
        if not isinstance(self.body, bytes): raise ProtocolError("body must be bytes")

@dataclass(frozen=True, slots=True)
class RelayResponse:
    request_id: str
    status_code: int
    reason_phrase: str | None
    headers: HeaderList
    body: bytes
    version: int = VERSION
    type: str = "response"
    def __post_init__(self) -> None:
        validate_common(self.version, self.type, self.request_id)
        if type(self.status_code) is not int or not (100 <= self.status_code <= 599): raise ProtocolError("invalid status code")
        if self.reason_phrase is not None and (not isinstance(self.reason_phrase, str) or "\r" in self.reason_phrase or "\n" in self.reason_phrase): raise ProtocolError("invalid reason")
        validate_header_list(self.headers)
        if not isinstance(self.body, bytes): raise ProtocolError("body must be bytes")

@dataclass(frozen=True, slots=True)
class RelayError:
    request_id: str | None
    error_code: str
    message: str
    retryable: bool
    version: int = VERSION
    type: str = "error"
    def __post_init__(self) -> None:
        if self.request_id is not None:
            validate_request_id(self.request_id)
        if self.version != VERSION or self.type != "error": raise ProtocolError("invalid error metadata")
        if self.error_code not in _ERROR_CODES: raise ProtocolError("invalid error code")
        if not isinstance(self.message, str) or "\r" in self.message or "\n" in self.message or type(self.retryable) is not bool: raise ProtocolError("invalid error fields")

def validate_request_id(request_id: str) -> None:
    if not isinstance(request_id, str) or len(request_id) != 32 or any(c not in "0123456789abcdef" for c in request_id):
        raise ProtocolError("request_id must be 32 lowercase hex characters")

def validate_common(version: int, type_name: str, request_id: str) -> None:
    if type(version) is not int or version != VERSION: raise ProtocolError("unsupported version")
    if type_name not in {"request", "response", "error"}: raise ProtocolError("invalid type")
    validate_request_id(request_id)
