"""FastAPI app factory."""
from __future__ import annotations
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI
from relayx.config import RelaySettings
from relayx.protocol.replay import ReplayCache
from relayx.server.endpoint import router
from relayx.server.forwarder import Forwarder

def create_app(settings: RelaySettings | None = None) -> FastAPI:
    settings = settings or RelaySettings()
    client = httpx.AsyncClient(timeout=settings.timeout_seconds)
    replay_cache = ReplayCache(settings.replay_window_seconds, settings.replay_cache_max_entries, settings.allowed_clock_skew_seconds)
    forwarder = Forwarder(client, settings.max_response_body_bytes)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            await client.aclose()

    app = FastAPI(lifespan=lifespan)
    app.include_router(router(settings, replay_cache, forwarder))
    return app
