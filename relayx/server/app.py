"""FastAPI app factory."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request

from relayx.config import RelaySettings
from relayx.logging import configure_logging
from relayx.protocol.replay import ReplayCache
from relayx.server.endpoint import health_router, router
from relayx.server.forwarder import Forwarder


async def _wait_for_outstanding(app: FastAPI, timeout: float) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while app.state.outstanding_requests > 0 and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.05)


def create_app(settings: RelaySettings | None = None) -> FastAPI:
    settings = settings or RelaySettings()
    configure_logging(settings.log_level)
    client = httpx.AsyncClient(timeout=settings.timeout_seconds)
    replay_cache = ReplayCache(settings.replay_window_seconds, settings.replay_cache_max_entries, settings.allowed_clock_skew_seconds)
    forwarder = Forwarder(client, settings.max_response_body_bytes)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.replay_cache = replay_cache
        app.state.forwarder = forwarder
        app.state.outstanding_requests = 0
        app.state.shutting_down = False
        try:
            yield
        finally:
            app.state.shutting_down = True
            await _wait_for_outstanding(app, settings.timeout_seconds)
            await client.aclose()

    app = FastAPI(lifespan=lifespan)
    app.state.replay_cache = replay_cache
    app.state.forwarder = forwarder
    app.state.outstanding_requests = 0
    app.state.shutting_down = False

    @app.middleware("http")
    async def track_outstanding_requests(request: Request, call_next):
        if request.url.path in {"/health", "/ready"}:
            return await call_next(request)
        request.app.state.outstanding_requests += 1
        try:
            return await call_next(request)
        finally:
            request.app.state.outstanding_requests -= 1

    app.include_router(health_router(replay_cache, forwarder))
    app.include_router(router(settings, replay_cache, forwarder))
    return app
