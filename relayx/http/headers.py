"""HTTP header filtering utilities."""
from __future__ import annotations
from relayx.constants import HOP_BY_HOP_HEADERS, PROXY_ONLY_HEADERS
from relayx.protocol.models import HeaderList

def filter_forward_headers(headers: HeaderList) -> HeaderList:
    connection_tokens = set()
    for name, value in headers:
        if name.lower() == "connection":
            connection_tokens.update(token.strip().lower() for token in value.split(",") if token.strip())
    blocked = HOP_BY_HOP_HEADERS | PROXY_ONLY_HEADERS | connection_tokens
    return tuple((name, value) for name, value in headers if name.lower() not in blocked)
