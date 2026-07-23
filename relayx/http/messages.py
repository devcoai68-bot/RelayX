"""Buffered HTTP message containers."""
from __future__ import annotations
from dataclasses import dataclass
from relayx.protocol.models import HeaderList

@dataclass(frozen=True, slots=True)
class HTTPRequestMessage:
    method: str
    scheme: str
    host: str
    port: int | None
    path: str
    query: str
    headers: HeaderList
    body: bytes

@dataclass(frozen=True, slots=True)
class HTTPResponseMessage:
    status_code: int
    reason_phrase: str | None
    headers: HeaderList
    body: bytes
