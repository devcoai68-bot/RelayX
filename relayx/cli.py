"""Minimal RelayX CLI."""
from __future__ import annotations
import argparse
import asyncio
import uvicorn
from relayx.client.app import create_proxy
from relayx.config import RelaySettings
from relayx.logging import configure_logging
from relayx.server.app import create_app

async def _run_client(settings: RelaySettings) -> None:
    proxy = await create_proxy(settings)
    server = await proxy.serve()
    async with server:
        await server.serve_forever()

def main() -> None:
    parser = argparse.ArgumentParser(prog="relayx")
    parser.add_argument("mode", choices=["server", "client"])
    args = parser.parse_args()
    settings = RelaySettings()
    configure_logging(settings.log_level)
    if args.mode == "server":
        uvicorn.run(create_app(settings), host=settings.server_host, port=settings.server_port, http="h11")
    if args.mode == "client":
        asyncio.run(_run_client(settings))
