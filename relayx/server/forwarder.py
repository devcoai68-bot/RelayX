"""Fully buffered upstream forwarding with bounded response reads."""

from __future__ import annotations

import httpx

from relayx.http.headers import filter_forward_headers
from relayx.protocol.models import RelayError, RelayRequest, RelayResponse


class Forwarder:
    def __init__(self, client: httpx.AsyncClient, max_response_body_bytes: int) -> None:
        self.client = client
        self.max_response_body_bytes = max_response_body_bytes

    @property
    def is_available(self) -> bool:
        return not self.client.is_closed

    async def forward(self, request: RelayRequest) -> RelayResponse | RelayError:
        port = request.port
        netloc = request.host if port is None else f"{request.host}:{port}"
        url = f"{request.scheme}://{netloc}{request.path}"
        if request.query:
            url += f"?{request.query}"
        try:
            async with self.client.stream(
                request.method,
                url,
                headers=list(filter_forward_headers(request.headers)),
                content=request.body,
            ) as response:
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > self.max_response_body_bytes:
                        return RelayError(
                            request.request_id,
                            "response_too_large",
                            "Upstream response is too large",
                            False,
                        )
                return RelayResponse(
                    request.request_id,
                    response.status_code,
                    response.reason_phrase,
                    tuple(response.headers.multi_items()),
                    bytes(chunks),
                )
        except httpx.TimeoutException:
            return RelayError(
                request.request_id,
                "upstream_timeout",
                "Upstream request timed out",
                True,
            )
        except httpx.ConnectError:
            return RelayError(
                request.request_id,
                "upstream_connection_failed",
                "Could not connect to upstream",
                True,
            )
        except httpx.HTTPError:
            return RelayError(
                request.request_id,
                "upstream_protocol_error",
                "Upstream HTTP error",
                True,
            )
