"""Client application entrypoint helpers."""

from __future__ import annotations

from relayx.client.proxy import LocalProxy
from relayx.client.relay_client import RelayClient
from relayx.config import RelaySettings


async def create_proxy(settings: RelaySettings | None = None) -> LocalProxy:
    settings = settings or RelaySettings()
    return LocalProxy(settings, RelayClient(settings))
