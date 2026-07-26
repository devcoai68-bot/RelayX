import asyncio
import base64

import httpx
import pytest
from fastapi import FastAPI, Request, Response

from relayx.client.relay_client import RelayClient
from relayx.config import RelaySettings
from relayx.protocol.models import RelayRequest, RelayResponse
from relayx.protocol.replay import ReplayCache
from relayx.server.app import create_app
from relayx.server.endpoint import router
from relayx.server.forwarder import Forwarder

KEY = base64.b64encode(b"k" * 32).decode()


def _settings(**overrides):
    values = {"auth_token": "auth", "encryption_key": KEY}
    values.update(overrides)
    return RelaySettings(**values)


@pytest.mark.asyncio
async def test_health_and_ready_endpoints():
    app = create_app(_settings())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://relay.test"
    ) as client:
        health = await client.get("/health")
        ready = await client.get("/ready")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["replay_cache"] == "initialized"
    assert ready.json()["forwarder"] == "available"


@pytest.mark.asyncio
async def test_large_request_and_response_roundtrip():
    upstream = FastAPI()
    response_body = b"r" * 70000

    @upstream.post("/large")
    async def large(request: Request):
        request_body = await request.body()
        return Response(
            response_body + request_body[-16:], media_type="application/octet-stream"
        )

    upstream_transport = httpx.ASGITransport(app=upstream)
    server_settings = _settings(
        max_request_body_bytes=100000,
        max_response_body_bytes=100000,
        max_carrier_body_bytes=200000,
        max_decompressed_bytes=200000,
    )
    relay_app = create_app(server_settings)
    relay_transport = httpx.ASGITransport(app=relay_app)

    async with httpx.AsyncClient(
        transport=upstream_transport, base_url="https://upstream.test"
    ) as upstream_client:
        relay_app.router.routes.clear()
        relay_app.include_router(
            router(server_settings, ReplayCache(), Forwarder(upstream_client, 100000))
        )
        async with httpx.AsyncClient(
            transport=relay_transport, base_url="http://relay.test"
        ) as carrier_client:
            client_settings = _settings(
                relay_url="http://relay.test/relay",
                max_carrier_body_bytes=200000,
                max_decompressed_bytes=200000,
                max_response_body_bytes=100000,
            )
            client = RelayClient(client_settings, carrier_client)
            body = b"q" * 70000
            request = RelayRequest(
                "b" * 32,
                "POST",
                "https",
                "upstream.test",
                None,
                "/large",
                "",
                (("content-type", "application/octet-stream"),),
                body,
            )
            response = await client.send(request)

    assert isinstance(response, RelayResponse)
    assert response.status_code == 200
    assert response.body == response_body + (b"q" * 16)


@pytest.mark.asyncio
async def test_lifespan_graceful_shutdown_waits_for_outstanding_requests_and_closes_client():
    app = create_app(_settings(timeout_seconds=1))
    async with app.router.lifespan_context(app):
        forwarder = app.state.forwarder
        app.state.outstanding_requests = 1

        async def finish_request():
            await asyncio.sleep(0.1)
            app.state.outstanding_requests = 0

        asyncio.create_task(finish_request())

    assert app.state.outstanding_requests == 0
    assert forwarder.client.is_closed
