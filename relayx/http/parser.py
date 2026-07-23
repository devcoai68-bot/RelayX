"""Small buffered HTTP/1.1 request parser for the local proxy."""
from __future__ import annotations
from urllib.parse import urlsplit
from relayx.errors import ProtocolError, RequestTooLargeError
from relayx.http.messages import HTTPRequestMessage

async def read_request(reader, max_header_bytes: int, max_body_bytes: int) -> HTTPRequestMessage:
    data = await _read_headers(reader, max_header_bytes)
    lines = data[:-4].decode("iso-8859-1").split("\r\n")
    try:
        method, target, version = lines[0].split(" ", 2)
    except ValueError as exc:
        raise ProtocolError("malformed request line") from exc
    if version != "HTTP/1.1" or method.upper() == "CONNECT":
        raise ProtocolError("unsupported request")
    headers = []
    for line in lines[1:]:
        if not line or ":" not in line:
            raise ProtocolError("malformed header")
        name, value = line.split(":", 1)
        headers.append((name, value.lstrip(" \t")))
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

def _target(method: str, target: str, headers, body: bytes) -> HTTPRequestMessage:
    host_header = next((v for n, v in headers if n.lower() == "host"), "")
    if target.startswith("http://") or target.startswith("https://"):
        parsed = urlsplit(target)
        scheme, host, port, path, query = parsed.scheme, parsed.hostname or "", parsed.port, parsed.path or "/", parsed.query
    else:
        if not host_header:
            raise ProtocolError("Host header is required")
        scheme = "http"
        host, _, port_s = host_header.partition(":")
        port = int(port_s) if port_s else None
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
