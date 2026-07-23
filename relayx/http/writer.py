"""HTTP/1.1 response writer."""
from __future__ import annotations
from relayx.http.headers import filter_forward_headers
from relayx.protocol.models import RelayError, RelayResponse

async def write_response(writer, message: RelayResponse | RelayError) -> None:
    if isinstance(message, RelayError):
        body = message.message.encode("utf-8")
        status, reason, headers = 502, "Bad Gateway", (("content-type", "text/plain; charset=utf-8"),)
    else:
        body = message.body
        status, reason, headers = message.status_code, message.reason_phrase or "", filter_forward_headers(message.headers)
    writer.write(f"HTTP/1.1 {status} {reason}\r\n".encode("ascii"))
    for name, value in headers:
        writer.write(f"{name}: {value}\r\n".encode("iso-8859-1"))
    writer.write(f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("ascii") + body)
    await writer.drain()
