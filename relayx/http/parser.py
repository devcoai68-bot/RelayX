"""Small buffered HTTP/1.1 request parser for the local proxy."""

from __future__ import annotations

from urllib.parse import urlsplit

from relayx.errors import ProtocolError, RequestTooLargeError
from relayx.http.messages import HTTPRequestMessage
from relayx.protocol.models import validate_header_list, validate_http_token


async def read_request(
    reader, max_header_bytes: int, max_body_bytes: int
) -> HTTPRequestMessage:
    data = await _read_headers(reader, max_header_bytes)
    lines = data[:-4].decode("iso-8859-1").split("\r\n")
    try:
        method, target, version = lines[0].split(" ", 2)
    except ValueError as exc:
        raise ProtocolError("malformed request line") from exc
    validate_http_token(method, "method")
    if version != "HTTP/1.1" or method.upper() == "CONNECT":
        raise ProtocolError("unsupported request")
    headers = []
    for line in lines[1:]:
        if not line or line[0] in " \t" or ":" not in line:
            raise ProtocolError("malformed header")
        name, value = line.split(":", 1)
        headers.append((name, value.lstrip(" \t")))
    validate_header_list(tuple(headers))
    if any(n.lower() == "transfer-encoding" for n, _ in headers):
        raise ProtocolError("transfer encoding is unsupported")
    body_len = _content_length(headers)
    if body_len > max_body_bytes:
        raise RequestTooLargeError("body too large")
    body = await reader.readexactly(body_len) if body_len else b""
    return _target(method, target, tuple(headers), body)


def _content_length(headers: list[tuple[str, str]]) -> int:
    values = [value for name, value in headers if name.lower() == "content-length"]
    if not values:
        return 0
    if len(values) > 1:
        raise ProtocolError("duplicate Content-Length is unsupported")
    value = values[0]
    if not value.isdecimal():
        raise ProtocolError("invalid Content-Length")
    return int(value)


def _single_host_header(headers: tuple[tuple[str, str], ...]) -> str:
    values = [value for name, value in headers if name.lower() == "host"]
    if len(values) != 1:
        raise ProtocolError("exactly one Host header is required")
    return values[0]


def _target(
    method: str, target: str, headers: tuple[tuple[str, str], ...], body: bytes
) -> HTTPRequestMessage:
    host_header = _single_host_header(headers)
    if target.startswith("http://") or target.startswith("https://"):
        parsed = urlsplit(target)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ProtocolError("invalid target port") from exc
        scheme, host, path, query = (
            parsed.scheme,
            parsed.hostname or "",
            parsed.path or "/",
            parsed.query,
        )
        authority = parsed.netloc.rsplit("@", 1)[-1].lower()
        if authority != host_header.lower():
            raise ProtocolError("absolute-form target authority must match Host header")
    else:
        scheme = "http"
        host, _, port_s = host_header.partition(":")
        try:
            port = int(port_s) if port_s else None
        except ValueError as exc:
            raise ProtocolError("invalid Host port") from exc
        parsed = urlsplit(target)
        path, query = parsed.path or "/", parsed.query
    return HTTPRequestMessage(method, scheme, host, port, path, query, headers, body)


async def _read_headers(reader, max_header_bytes: int) -> bytes:
    data = bytearray()
    while b"\r\n\r\n" not in data:
        if len(data) >= max_header_bytes:
            raise RequestTooLargeError("headers too large")
        chunk = await reader.read(1)
        if not chunk:
            raise ProtocolError("incomplete headers")
        data.extend(chunk)
    if len(data) > max_header_bytes:
        raise RequestTooLargeError("headers too large")
    return bytes(data)
