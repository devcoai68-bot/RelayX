import base64
import pytest
import httpx
from fastapi import FastAPI, Request, Response
from relayx.client.relay_client import RelayClient
from relayx.config import RelaySettings
from relayx.protocol.models import RelayRequest, RelayResponse
from relayx.server.app import create_app

KEY = base64.b64encode(b"k" * 32).decode()

@pytest.mark.asyncio
async def test_client_server_upstream_roundtrip():
    upstream = FastAPI()

    @upstream.post("/echo")
    async def echo(request: Request):
        body = await request.body()
        return Response(body, media_type="application/octet-stream", headers={"x-upstream": "yes"})

    upstream_transport = httpx.ASGITransport(app=upstream)
    server_settings = RelaySettings(auth_token="auth", encryption_key=KEY, max_request_body_bytes=1024, max_response_body_bytes=1024)
    relay_app = create_app(server_settings)
    relay_transport = httpx.ASGITransport(app=relay_app)

    async with httpx.AsyncClient(transport=upstream_transport, base_url="https://upstream.test") as upstream_client:
        relay_app.router.routes.clear()
        from relayx.protocol.replay import ReplayCache
        from relayx.server.endpoint import router
        from relayx.server.forwarder import Forwarder
        relay_app.include_router(router(server_settings, ReplayCache(), Forwarder(upstream_client, 1024)))
        async with httpx.AsyncClient(transport=relay_transport, base_url="http://relay.test") as carrier_client:
            client_settings = RelaySettings(auth_token="auth", encryption_key=KEY, relay_url="http://relay.test/relay")
            client = RelayClient(client_settings, carrier_client)
            request = RelayRequest("a" * 32, "POST", "https", "upstream.test", None, "/echo", "", (("content-type", "application/octet-stream"),), b"hello")
            response = await client.send(request)
            assert isinstance(response, RelayResponse)
            assert response.status_code == 200
            assert response.body == b"hello"
