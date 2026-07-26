"""In-process RelayX benchmark harness."""
from __future__ import annotations

from collections.abc import Callable

import httpx
from fastapi import FastAPI, Request, Response

from relayx.client.relay_client import RelayClient
from relayx.config import RelaySettings
from relayx.protocol.models import RelayRequest, RelayResponse
from relayx.protocol.replay import ReplayCache
from relayx.server.app import create_app
from relayx.server.endpoint import router
from relayx.server.forwarder import Forwarder
from benchmarks.common import default_settings


class RelayBenchmarkHarness:
    def __init__(self, response_factory: Callable[[bytes], bytes] | None = None, settings: RelaySettings | None = None) -> None:
        self.response_factory = response_factory or (lambda body: body)
        self.settings = settings or default_settings()
        self.upstream = FastAPI()
        self._install_upstream_route()
        self.upstream_client: httpx.AsyncClient | None = None
        self.carrier_client: httpx.AsyncClient | None = None
        self.relay_client: RelayClient | None = None
        self.relay_app = create_app(self.settings)

    def _install_upstream_route(self) -> None:
        @self.upstream.post("/benchmark")
        async def benchmark_endpoint(request: Request):
            body = await request.body()
            return Response(self.response_factory(body), media_type="application/octet-stream")

    async def __aenter__(self) -> "RelayBenchmarkHarness":
        self.upstream_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.upstream), base_url="https://upstream.test")
        self.relay_app.router.routes.clear()
        self.relay_app.include_router(router(self.settings, ReplayCache(), Forwarder(self.upstream_client, self.settings.max_response_body_bytes)))
        self.carrier_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.relay_app), base_url="http://relay.test")
        client_settings = default_settings(relay_url="http://relay.test/relay")
        self.relay_client = RelayClient(client_settings, self.carrier_client)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.carrier_client is not None:
            await self.carrier_client.aclose()
        if self.upstream_client is not None:
            await self.upstream_client.aclose()

    async def send(self, request_id: str, payload: bytes) -> RelayResponse:
        if self.relay_client is None:
            raise RuntimeError("harness not started")
        request = RelayRequest(request_id, "POST", "https", "upstream.test", None, "/benchmark", "", (("content-type", "application/octet-stream"),), payload)
        response = await self.relay_client.send(request)
        if not isinstance(response, RelayResponse):
            raise RuntimeError(f"relay returned error: {response}")
        return response
